import re
from typing import Any, Dict, List, Optional
from src.graph.client import Neo4jClient
from src.vector.client import VectorKBClient


class UnifiedKB:
    """
    Unified Knowledge Base facade managing both structural Graph DB (Neo4j)
    and semantic Vector DB (ChromaDB).
    """

    def __init__(
        self,
        neo4j_client: Optional[Neo4jClient] = None,
        vector_client: Optional[VectorKBClient] = None,
    ):
        self.graph = neo4j_client or Neo4jClient()
        self.vector = vector_client or VectorKBClient()

    async def connect(self) -> None:
        """Connect to underlying Graph DB driver."""
        await self.graph.connect()

    async def close(self) -> None:
        """Close underlying Graph DB connections."""
        await self.graph.close()

    async def hybrid_search(
        self,
        repo_id: str,
        query_text: str,
        branch: str = "main",
        n_results: int = 5,
    ) -> Dict[str, Any]:
        """
        Perform a hybrid search:
        1. Vector similarity search over ChromaDB code/PR/commit/issue embeddings.
        2. Intelligent token-based symbol and file matching in Neo4j graph DB.
        Returns a dictionary combining both vector and graph hits.
        """
        # 1. Vector similarity search
        vector_res = self.vector.query(
            query_texts=[query_text],
            n_results=n_results,
            where={"repo": repo_id},
        )

        vector_hits = []
        if vector_res and vector_res.get("documents") and len(vector_res["documents"]) > 0 and vector_res["documents"][0]:
            docs = vector_res["documents"][0]
            metas = vector_res["metadatas"][0] if vector_res.get("metadatas") else [{}] * len(docs)
            dists = vector_res["distances"][0] if vector_res.get("distances") else [0.0] * len(docs)
            for doc, meta, dist in zip(docs, metas, dists):
                vector_hits.append({"document": doc, "metadata": meta, "distance": dist})

        # 2. Tokenized Graph symbol and file search
        stop_words = {
            'use', 'the', 'graph', 'mcp', 'to', 'locate', 'me', 'which', 'nodes', 'noddes',
            'will', 'directly', 'be', 'affected', 'from', 'editing', 'find', 'show', 'get',
            'what', 'how', 'does', 'in', 'of', 'for', 'a', 'an', 'and', 'or', 'with', 'is', 'it'
        }
        words = re.findall(r'[a-zA-Z0-9_-]+', query_text.lower())
        tokens = [w for w in words if w not in stop_words and len(w) > 2]
        if len(tokens) >= 2:
            tokens.append("".join(tokens))
            tokens.append(tokens[0] + tokens[1].capitalize())

        if not tokens:
            tokens = [query_text.lower()]

        # Query Cypher for symbols matching any token
        graph_query = """
        MATCH (s:Symbol {repo_id: $repo_id})
        WHERE ANY(t IN $tokens WHERE toLower(s.name) CONTAINS t OR toLower(s.qualified_name) CONTAINS t)
        RETURN properties(s) AS symbol
        LIMIT $limit
        """
        graph_hits = []
        try:
            graph_recs = await self.graph.execute_query(
                graph_query,
                {"repo_id": repo_id, "tokens": tokens, "limit": n_results},
            )
            graph_hits = [r["symbol"] for r in graph_recs if "symbol" in r]

            # If symbol hits are fewer than limit, search File nodes
            if len(graph_hits) < n_results:
                file_query = """
                MATCH (f:File {repo_id: $repo_id})
                WHERE ANY(t IN $tokens WHERE toLower(f.file_path) CONTAINS t)
                RETURN {name: f.file_path, qualified_name: f.file_path, kind: "file", file_path: f.file_path, language: f.language} AS symbol
                LIMIT $limit
                """
                file_recs = await self.graph.execute_query(
                    file_query,
                    {"repo_id": repo_id, "tokens": tokens, "limit": n_results - len(graph_hits)},
                )
                file_hits = [r["symbol"] for r in file_recs if "symbol" in r]
                graph_hits.extend(file_hits)
        except Exception as e:
            pass

        # Deduplicate graph hits by unique symbol identifier
        unique_hits = []
        seen_keys = set()
        for hit in graph_hits:
            key = hit.get("qualified_name") or hit.get("name") or hit.get("file_path")
            if key and key not in seen_keys:
                seen_keys.add(key)
                unique_hits.append(hit)
            elif not key:
                unique_hits.append(hit)
        graph_hits = unique_hits

        return {
            "query": query_text,
            "repo_id": repo_id,
            "branch": branch,
            "tokens_matched": tokens,
            "vector_hits": vector_hits,
            "graph_hits": graph_hits,
        }
