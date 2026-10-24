from dataclasses import asdict
from fastapi import APIRouter, HTTPException

from src.web.schemas import ContextApiRequest
from src.web.deps import get_shared_graph_client, get_shared_vector_client
from src.context import ContextEngine, ContextRequest, AuthorizationError

router = APIRouter(tags=["Governed Context Engine"])


@router.post("/projects/{project_id}/context")
@router.post("/api/projects/{project_id}/context")
async def retrieve_project_context(project_id: str, body: ContextApiRequest):
    """
    Governed Context Engine retrieval endpoint for Gitami.
    Enforces Organization -> Project -> Repository authorization before querying
    Neo4j graph, semantic vectors, Git snapshots, and GitHub evidence.
    """
    graph_client = await get_shared_graph_client()
    vector_client = get_shared_vector_client()
    engine = ContextEngine(graph_client=graph_client, vector_client=vector_client)

    req = ContextRequest(
        project_id=project_id,
        query=body.query,
        repository_ids=body.repository_ids or [],
        branch=body.branch or "main",
        commit_sha=body.commit_sha,
        max_items=body.max_items or 20,
        max_tokens=body.max_tokens or 8000,
        include_graph=body.include_graph if body.include_graph is not None else True,
        include_semantic=body.include_semantic if body.include_semantic is not None else True,
        include_source=body.include_source if body.include_source is not None else True,
        include_github=body.include_github if body.include_github is not None else True,
        hops=body.hops or 1,
    )

    try:
        res = await engine.retrieve(req)
        return asdict(res)
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
