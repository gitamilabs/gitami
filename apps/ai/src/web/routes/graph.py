from pathlib import Path
import tempfile
from typing import Optional

from fastapi import APIRouter, HTTPException

from src.analysis.graph_analysis import (
    build_networkx_graph,
    cluster_graph,
    compute_graph_presentation,
    find_god_nodes,
    find_import_cycles,
    find_surprising_connections,
)
from src.analysis.report import generate_graph_report
from src.graph.reader import get_entire_graph
from src.web.deps import get_shared_graph_client

router = APIRouter(tags=["graph"])


@router.get("/api/graph/{repo_id:path}")
async def get_graph_data(
    repo_id: str,
    branch: str = "main",
    max_nodes: int = 500,
    project_id: Optional[str] = None,
):
    """
    Returns actual Neo4j nodes and edges for the interactive knowledge graph.
    """
    try:
        graph_client = await get_shared_graph_client()
        raw_data = await get_entire_graph(
            graph_client,
            repo_id=repo_id,
            branch=branch,
            max_nodes=max_nodes,
            project_id=project_id,
        )
        presentation = compute_graph_presentation(raw_data)
        return {
            "status": "success",
            "repo_id": repo_id,
            "branch": branch,
            "nodes": presentation["nodes"],
            "edges": presentation["edges"],
            "communities": presentation["communities"],
            "stats": presentation["stats"],
            "total_nodes": presentation["stats"]["nodeCount"],
            "total_edges": presentation["stats"]["edgeCount"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/graph-report/{repo_id:path}")
async def get_graph_report(repo_id: str, branch: str = "main"):
    """
    Generates and returns the Graphify architectural report (GRAPH_REPORT.md).
    Runs community clustering, god node detection, and import cycle analysis.
    """
    try:
        graph_client = await get_shared_graph_client()
        graph_data = await get_entire_graph(graph_client, repo_id=repo_id, branch=branch)
        G = build_networkx_graph(graph_data)

        communities = cluster_graph(G)
        god_nodes = find_god_nodes(G)
        surprising = find_surprising_connections(G, communities)
        cycles = find_import_cycles(G)

        tmp_dir = Path(tempfile.gettempdir()) / "graphify_reports" / repo_id.replace("/", "_")
        md_path = generate_graph_report(
            repo_id=repo_id,
            nodes=graph_data["nodes"],
            edges=graph_data["edges"],
            communities=communities,
            god_nodes=god_nodes,
            surprising=surprising,
            cycles=cycles,
            out_dir=tmp_dir,
        )

        if md_path.exists():
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()
            return {"status": "success", "repo_id": repo_id, "report_markdown": content}
        else:
            raise HTTPException(status_code=500, detail="Failed to generate report file.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
