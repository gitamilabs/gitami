from typing import Optional
from fastapi import APIRouter, Query
from src.web.deps import get_shared_graph_client, get_shared_vector_client
from src.graph.writer import delete_repo_data

router = APIRouter(prefix="/api/repos", tags=["Repositories"])


@router.get("")
async def list_repositories():
    """List indexed repositories from Vector KB and Graph DB."""
    try:
        vector_client = get_shared_vector_client()
        vector_repos = set(vector_client.get_distinct_repos())
        vector_count = vector_client.count()

        graph_repos = set()
        try:
            graph_client = await get_shared_graph_client()
            records = await graph_client.execute_query("MATCH (f:File) RETURN DISTINCT f.repo_id AS repo")
            for r in records:
                if r.get("repo"):
                    graph_repos.add(r["repo"])
        except Exception:
            pass

        all_repos = sorted(list(vector_repos.union(graph_repos)))

        return {
            "repos": all_repos,
            "vector_count": vector_count,
            "graph_repos": list(graph_repos),
        }
    except Exception as e:
        return {"repos": [], "error": str(e)}


@router.delete("/{repo_id:path}")
async def delete_repository(repo_id: str, branch: Optional[str] = Query(None)):
    """
    Purge all data for a repository from Neo4j Graph DB and Chroma Vector DB.
    Optionally scoped to a specific branch if provided.
    """
    deleted_graph = False
    deleted_vector = False
    error_msgs = []

    # 1. Purge from Neo4j
    try:
        graph_client = await get_shared_graph_client()
        await delete_repo_data(graph_client, repo_id=repo_id, branch=branch)
        deleted_graph = True
    except Exception as e:
        error_msgs.append(f"Graph deletion error: {str(e)}")

    # 2. Purge from Chroma Vector DB
    try:
        vector_client = get_shared_vector_client()
        where_filter = {"repo": repo_id}
        if branch:
            where_filter = {"$and": [{"repo": repo_id}, {"branch": branch}]}
        vector_client.delete(where=where_filter)
        deleted_vector = True
    except Exception as e:
        error_msgs.append(f"Vector deletion error: {str(e)}")

    return {
        "success": len(error_msgs) == 0,
        "repo_id": repo_id,
        "branch": branch,
        "deleted_graph": deleted_graph,
        "deleted_vector": deleted_vector,
        "errors": error_msgs,
    }
