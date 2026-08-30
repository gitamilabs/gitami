import asyncio
import json
import dataclasses
from pathlib import Path
from typing import Optional
import click

from ai_service.graph.client import Neo4jClient
from ai_service.vector.client import VectorKBClient
from ai_service.jobs.init_job import run_init_job
from ai_service.jobs.pr_eval_job import run_pr_eval_job


@click.group()
def main():
    """AI Service CLI for Repository Analysis & PR Evaluation."""
    pass


@main.command()
@click.option("--repo-id", required=True, help="Unique identifier for the target repository.")
@click.option("--branch", default="main", help="Target branch name.")
@click.option("--repo-dir", required=True, type=click.Path(exists=True), help="Path to cloned repository.")
def init(repo_id: str, branch: str, repo_dir: str):
    """Run repository initialization indexing job (dual-writes to Graph DB & Vector DB)."""
    async def _run():
        graph_client = Neo4jClient()
        await graph_client.connect()
        vector_client = VectorKBClient()
        try:
            res = await run_init_job(
                repo_id=repo_id,
                branch=branch,
                repo_dir=Path(repo_dir),
                client=graph_client,
                vector_client=vector_client,
            )
            click.echo(json.dumps(dataclasses.asdict(res), indent=2))
        finally:
            await graph_client.close()

    asyncio.run(_run())


@main.command()
@click.option("--repo-id", required=True, help="Unique identifier for the target repository.")
@click.option("--branch", default="main", help="Target branch name.")
@click.option("--repo-dir", required=True, type=click.Path(exists=True), help="Path to repository.")
@click.option("--base-ref", required=True, help="Base commit hash or branch.")
@click.option("--head-ref", required=True, help="Head commit hash or branch.")
@click.option("--agent/--no-agent", default=True, help="Enable Agentic LLM PR reviewer mode.")
def eval_pr(repo_id: str, branch: str, repo_dir: str, base_ref: str, head_ref: str, agent: bool):
    """Run PR evaluation job using graph structural and vector semantic context."""
    async def _run():
        graph_client = Neo4jClient()
        await graph_client.connect()
        vector_client = VectorKBClient()
        try:
            res = await run_pr_eval_job(
                repo_id=repo_id,
                branch=branch,
                repo_dir=Path(repo_dir),
                base_ref=base_ref,
                head_ref=head_ref,
                client=graph_client,
                vector_client=vector_client,
                use_agent=agent,
            )
            click.echo(json.dumps(dataclasses.asdict(res), indent=2))
        finally:
            await graph_client.close()

    asyncio.run(_run())


@main.command()
@click.option("--query", required=True, help="Semantic search query string.")
@click.option("--repo-id", help="Filter by repo ID.")
@click.option("--n-results", default=5, help="Number of results to return.")
def vector_search(query: str, repo_id: Optional[str], n_results: int):
    """Run semantic similarity search on ChromaDB vector knowledge base."""
    from ai_service.mcp.tools import tool_vector_search
    vector_client = VectorKBClient()
    res = tool_vector_search(vector_client, query_text=query, repo_id=repo_id, n_results=n_results)
    click.echo(res)


@main.command()
@click.option("--repo-id", required=True, help="Target repository ID.")
@click.option("--query", required=True, help="Search query string.")
@click.option("--branch", default="main", help="Target branch name.")
@click.option("--n-results", default=5, help="Number of results to return.")
def hybrid_search(repo_id: str, query: str, branch: str, n_results: int):
    """Run hybrid search combining semantic vector search and structural graph lookup."""
    async def _run():
        graph_client = Neo4jClient()
        await graph_client.connect()
        vector_client = VectorKBClient()
        try:
            from ai_service.mcp.tools import tool_hybrid_search
            res = await tool_hybrid_search(graph_client, vector_client, repo_id=repo_id, query_text=query, branch=branch, n_results=n_results)
            click.echo(res)
        finally:
            await graph_client.close()

    asyncio.run(_run())


@main.command()
def mcp():
    """Start FastMCP server for Knowledge Base tool integration."""
    from ai_service.mcp.server import run_mcp_server
    run_mcp_server()


@main.command()
@click.option("--host", default="0.0.0.0", help="Host address to bind server. Defaults to 0.0.0.0 for external access.")
@click.option("--port", default=None, type=int, help="Port to bind server. Defaults to PORT env var or 8000.")
def serve(host: str, port: Optional[int]):
    """Start FastAPI HTTP server for Chat API & Agent Tool Visualizer backend."""
    import uvicorn
    import os
    if port is None:
        port = int(os.environ.get("PORT", 8000))
    uvicorn.run("ai_service.web.app:app", host=host, port=port, reload=False)



@main.command()
@click.option("--repo-dir", required=True, type=click.Path(exists=True), help="Path to target codebase.")
@click.option("--output", default="kb_graph.html", help="Output HTML file path.")
def visualize(repo_dir: str, output: str):
    """Generate an interactive HTML visual graph of the vectorless Knowledge Base."""
    from ai_service.parsing.parser import CodeParser
    from ai_service.visualize import generate_graph_html

    parser = CodeParser()
    results = parser.parse_directory(Path(repo_dir))
    out_path = generate_graph_html(results, output_path=output)

    click.echo(f"Successfully generated interactive Knowledge Base graph at: {out_path.resolve()}")


@main.command()
@click.option("--repo-id", required=True, help="Target repository ID to clean.")
@click.option("--branch", help="Optional target branch to clean.")
def reset(repo_id: str, branch: Optional[str]):
    """Reset and purge Knowledge Base data (Vector DB & Graph DB) for a repository."""
    async def _run():
        graph_client = Neo4jClient()
        await graph_client.connect()
        vector_client = VectorKBClient()
        try:
            from ai_service.graph.writer import delete_repo_data
            await delete_repo_data(graph_client, repo_id=repo_id, branch=branch)
            try:
                where_clause = {"repo": repo_id}
                if branch:
                    where_clause["branch"] = branch
                vector_client.delete(where=where_clause)
            except Exception:
                pass
            click.echo(f"Successfully purged Knowledge Base data for repo '{repo_id}'" + (f" (branch: {branch})" if branch else ""))
        finally:
            await graph_client.close()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
