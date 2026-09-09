from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Set

from src.context.contracts import AuthorizedScope, ContextRequest
from src.graph.client import Neo4jClient

logger = logging.getLogger(__name__)


class AuthorizationError(Exception):
    """Raised when access to an unauthorized project or repository is attempted."""
    pass


class ProjectAuthResolver(Protocol):
    """Protocol for resolving authorized repositories and root paths for a project."""
    async def resolve_project_repositories(
        self, project_id: str
    ) -> Dict[str, Optional[Path]]:
        """Return mapping of repo_id -> optional filesystem Path."""
        ...


class StaticAuthResolver:
    """In-memory resolver for explicit project-to-repository permissions."""

    def __init__(self, project_repos: Optional[Dict[str, Dict[str, Optional[Path]]]] = None):
        # project_id -> {repo_id: Path or None}
        self._project_repos: Dict[str, Dict[str, Optional[Path]]] = project_repos or {}

    def register_project_repo(
        self, project_id: str, repo_id: str, repo_path: Optional[str | Path] = None
    ) -> None:
        if project_id not in self._project_repos:
            self._project_repos[project_id] = {}
        self._project_repos[project_id][repo_id] = Path(repo_path).resolve() if repo_path else None

    async def resolve_project_repositories(
        self, project_id: str
    ) -> Dict[str, Optional[Path]]:
        return dict(self._project_repos.get(project_id, {}))


class Neo4jAuthResolver:
    """Graph-backed fallback resolver for project-to-repository mappings."""

    def __init__(self, client: Neo4jClient):
        self.client = client

    async def resolve_project_repositories(
        self, project_id: str
    ) -> Dict[str, Optional[Path]]:
        query = """
        MATCH (r:Repository)
        WHERE r.project_id = $project_id OR r.repo_id = $project_id
        RETURN r.repo_id AS repo_id
        """
        try:
            records = await self.client.execute_query(query, {"project_id": project_id})
            repos: Dict[str, Optional[Path]] = {}
            for rec in records:
                rid = rec.get("repo_id")
                if rid:
                    repos[rid] = None
            return repos
        except Exception as e:
            logger.warning(f"Failed to query Neo4j for project repositories ({project_id}): {e}")
            return {}


class ContextAuthorizer:
    """
    Enforces the Organization -> Project -> Repository security boundary
    before any retrieval provider is accessed.
    """

    def __init__(
        self,
        resolver: Optional[ProjectAuthResolver] = None,
        graph_client: Optional[Neo4jClient] = None,
    ):
        self._resolver = resolver
        self._graph_client = graph_client

    def set_resolver(self, resolver: ProjectAuthResolver) -> None:
        self._resolver = resolver

    async def authorize(self, request: ContextRequest) -> AuthorizedScope:
        """
        Validates that request.project_id is valid and all requested repositories
        are authorized for this project.
        
        Raises:
            AuthorizationError: If project has no access, or if any requested
                                repository is outside the authorized project scope.
        """
        if not request.project_id:
            raise AuthorizationError("Authorization failed: project_id is required")

        allowed_repos: Dict[str, Optional[Path]] = {}

        # 1. Primary: Use configured resolver (control-plane authority)
        if self._resolver:
            allowed_repos = await self._resolver.resolve_project_repositories(request.project_id)

        # 2. Fallback: Query Neo4j repository associations if resolver returned nothing
        if not allowed_repos and self._graph_client:
            neo_resolver = Neo4jAuthResolver(self._graph_client)
            allowed_repos = await neo_resolver.resolve_project_repositories(request.project_id)

        # 3. If no repositories belong to this project, deny access
        if not allowed_repos:
            raise AuthorizationError(
                f"Project '{request.project_id}' is not authorized or contains no connected repositories"
            )

        allowed_repo_ids = set(allowed_repos.keys())

        # 4. If caller explicitly requested specific repository_ids, verify all are authorized
        if request.repository_ids:
            requested_set = set(request.repository_ids)
            unauthorized = requested_set - allowed_repo_ids
            if unauthorized:
                raise AuthorizationError(
                    f"Access denied: Repositories {sorted(list(unauthorized))} are not authorized for project '{request.project_id}'"
                )
            final_repo_ids = requested_set
        else:
            final_repo_ids = allowed_repo_ids

        repo_paths: Dict[str, Path] = {
            rid: path for rid, path in allowed_repos.items() if path is not None and rid in final_repo_ids
        }

        return AuthorizedScope(
            project_id=request.project_id,
            allowed_repo_ids=final_repo_ids,
            repo_paths=repo_paths,
            default_branch=request.branch,
        )
