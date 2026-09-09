from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set

from src.context.contracts import (
    AuthorizedScope,
    ContextItem,
    ContextItemType,
    ContextSource,
)
from src.context.provenance import create_source
from src.graph.client import Neo4jClient

logger = logging.getLogger(__name__)


class GraphRetriever:
    """
    Retrieves entity definitions and relationship-aware neighborhoods from Neo4j.
    Strictly scoped to AuthorizedScope.allowed_repo_ids.
    """

    def __init__(self, client: Neo4jClient):
        self.client = client

    async def retrieve(
        self,
        query: str,
        scope: AuthorizedScope,
        hops: int = 1,
        limit: int = 15,
    ) -> List[ContextItem]:
        if not scope.allowed_repo_ids:
            return []

        allowed_repos = list(scope.allowed_repo_ids)
        tokens = [t for t in re.findall(r"[A-Za-z0-9_]+", query) if len(t) >= 2]
        query_clean = query.strip()

        items: List[ContextItem] = []
        seen_uids: Set[str] = set()

        # 1. Entity Lookup: Direct symbol or file match
        entity_query = """
        MATCH (n)
        WHERE (n:Function OR n:Class OR n:Method OR n:Interface OR n:Type OR n:File OR n:Test)
          AND n.repo_id IN $allowed_repos
          AND (
            toLower(n.name) CONTAINS toLower($query_clean)
            OR toLower(n.file_path) CONTAINS toLower($query_clean)
            OR n.uid = $query_clean
            OR any(tok IN $tokens WHERE toLower(n.name) = toLower(tok))
          )
        RETURN labels(n) AS labels, properties(n) AS props
        LIMIT $limit
        """
        try:
            records = await self.client.execute_query(
                entity_query,
                {
                    "allowed_repos": allowed_repos,
                    "query_clean": query_clean,
                    "tokens": tokens,
                    "limit": limit,
                },
            )
        except Exception as e:
            logger.error(f"GraphRetriever entity query failed: {e}")
            raise e

        matched_uids: List[str] = []
        for rec in records:
            props = rec.get("props", {})
            labels = rec.get("labels", [])
            uid = props.get("uid")
            if not uid or uid in seen_uids:
                continue

            seen_uids.add(uid)
            matched_uids.append(uid)

            repo_id = props.get("repo_id", "")
            file_path = props.get("file_path", "")
            name = props.get("name", uid)
            kind = props.get("kind", labels[0] if labels else "symbol")
            sig = props.get("signature", "")
            doc = props.get("docstring", "")
            start_line = props.get("start_line")
            end_line = props.get("end_line")
            commit_sha = props.get("commit_sha")

            content_lines = [f"Entity: {kind} {name}"]
            if sig:
                content_lines.append(f"Signature: {sig}")
            if file_path:
                line_info = f" [lines {start_line}-{end_line}]" if start_line and end_line else ""
                content_lines.append(f"Location: {file_path}{line_info}")
            if doc:
                content_lines.append(f"Docstring: {doc}")

            item_type = ContextItemType.FILE if "File" in labels else ContextItemType.SYMBOL

            source = create_source(
                kind="graph",
                repository_id=repo_id,
                file_path=file_path,
                entity_uid=uid,
                commit_sha=commit_sha,
                start_line=start_line,
                end_line=end_line,
            )

            items.append(
                ContextItem(
                    id=f"graph:{uid}",
                    type=item_type,
                    title=f"{kind.capitalize()}: {name}",
                    content="\n".join(content_lines),
                    relevance_score=0.9,
                    source=source,
                    metadata={
                        "kind": kind,
                        "name": name,
                        "hop_distance": 1,
                    },
                )
            )

        # 2. Neighborhood Expansion (Bounded 1-hop relationships for matched entities)
        if matched_uids and hops >= 1:
            rel_query = """
            MATCH (n)-[r]->(m)
            WHERE n.uid IN $matched_uids
              AND n.repo_id IN $allowed_repos
              AND (m.repo_id IS NULL OR m.repo_id IN $allowed_repos)
            RETURN n.uid AS src_uid, n.name AS src_name, type(r) AS rel,
                   m.uid AS tgt_uid, m.name AS tgt_name, labels(m) AS tgt_labels,
                   properties(m) AS tgt_props, n.repo_id AS repo_id
            UNION
            MATCH (m)-[r]->(n)
            WHERE n.uid IN $matched_uids
              AND n.repo_id IN $allowed_repos
              AND (m.repo_id IS NULL OR m.repo_id IN $allowed_repos)
            RETURN m.uid AS src_uid, m.name AS src_name, type(r) AS rel,
                   n.uid AS tgt_uid, n.name AS tgt_name, labels(n) AS tgt_labels,
                   properties(n) AS tgt_props, n.repo_id AS repo_id
            LIMIT 30
            """
            try:
                rel_records = await self.client.execute_query(
                    rel_query,
                    {"allowed_repos": allowed_repos, "matched_uids": matched_uids},
                )
                for r in rel_records:
                    rel_type = r.get("rel")
                    src_uid = r.get("src_uid")
                    tgt_uid = r.get("tgt_uid")
                    src_name = r.get("src_name") or src_uid
                    tgt_name = r.get("tgt_name") or tgt_uid
                    repo_id = r.get("repo_id") or allowed_repos[0]
                    tgt_props = r.get("tgt_props", {})

                    item_id = f"rel:{src_uid}:{rel_type}:{tgt_uid}"
                    if item_id in seen_uids:
                        continue
                    seen_uids.add(item_id)

                    if rel_type == "CALLS":
                        c_type = ContextItemType.CALL_GRAPH
                        title = f"Call: {src_name} -> {tgt_name}"
                        desc = f"'{src_name}' calls '{tgt_name}'"
                    elif rel_type in ("EXTENDS", "IMPLEMENTS"):
                        c_type = ContextItemType.HERITAGE
                        title = f"Heritage: {src_name} {rel_type.lower()} {tgt_name}"
                        desc = f"'{src_name}' {rel_type.lower()} '{tgt_name}'"
                    elif rel_type == "TESTS":
                        c_type = ContextItemType.TEST
                        title = f"Test: {src_name} tests {tgt_name}"
                        desc = f"Test '{src_name}' exercises symbol '{tgt_name}'"
                    elif rel_type in ("IMPORTS", "DEPENDS_ON_FILE"):
                        c_type = ContextItemType.DEPENDENCY
                        title = f"Dependency: {src_name} imports {tgt_name}"
                        desc = f"File/Symbol '{src_name}' depends on '{tgt_name}'"
                    else:
                        continue

                    source = create_source(
                        kind="graph",
                        repository_id=repo_id,
                        file_path=tgt_props.get("file_path"),
                        entity_uid=tgt_uid,
                        commit_sha=tgt_props.get("commit_sha"),
                    )

                    items.append(
                        ContextItem(
                            id=item_id,
                            type=c_type,
                            title=title,
                            content=f"{desc} [repo: {repo_id}]",
                            relevance_score=0.8,
                            source=source,
                            metadata={
                                "relationship": rel_type,
                                "source_uid": src_uid,
                                "target_uid": tgt_uid,
                                "hop_distance": 2,
                            },
                        )
                    )
            except Exception as e:
                logger.warning(f"GraphRetriever neighborhood expansion warning: {e}")

        return items
