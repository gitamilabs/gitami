import asyncio
import json
import dataclasses
from pathlib import Path
from typing import Optional
import click

from src.graph.client import Neo4jClient
from src.vector.client import VectorKBClient
from src.jobs.pr_eval_job import run_pr_eval_job
from src.indexer.pipeline import RepositoryIndexer
from src.indexer.contracts import IndexJobType


@click.group()
def main():
    """AI Service CLI for Repository Analysis & PR Evaluation."""
    pass


@main.command()
@click.option("--repo-id", required=True, help="Unique identifier for the target repository.")
@click.option("--commit", default="HEAD", help="Target commit SHA to index.")
@click.option("--repo-dir", required=True, type=click.Path(exists=True), help="Path to cloned repository.")
@click.option("--branch", default="main", help="Target branch name.")
@click.option("--project-id", default="default", help="Parent Project identifier.")
@click.option("--validate-only", is_flag=True, default=False, help="Run discovery, AST parsing, and validation without writing to Neo4j.")
@click.option("--enable-semantic", is_flag=True, default=False, help="Enable semantic vector indexing in addition to structural graph indexing.")
def index(repo_id: str, commit: str, repo_dir: str, branch: str, project_id: str, validate_only: bool, enable_semantic: bool):
    """Run canonical V1 repository indexing against an explicit commit SHA."""
    async def _run():
        graph_client = None
        if not validate_only:
            try:
                graph_client = Neo4jClient()
                await graph_client.connect()
            except Exception as e:
                click.echo(f"Warning: Neo4j not available ({e}), falling back to validate-only mode.", err=True)
                validate_only_mode = True
            else:
                validate_only_mode = False
        else:
            validate_only_mode = True

        vector_client = VectorKBClient() if enable_semantic else None
        indexer = RepositoryIndexer(graph_client=graph_client, vector_client=vector_client)
        try:
            job, state, report = await indexer.run(
                repo_dir=Path(repo_dir),
                repo_id=repo_id,
                target_commit_sha=commit,
                branch=branch,
                project_id=project_id,
                validate_only=validate_only_mode,
            )
            output = {
                "job": job.model_dump(mode="json"),
                "state": state.model_dump(mode="json"),
                "validation": report.model_dump(mode="json"),
            }
            click.echo(json.dumps(output, indent=2))
        finally:
            if graph_client:
                await graph_client.close()

    asyncio.run(_run())


@main.command()
@click.option("--repo-id", required=True, help="Unique identifier for the target repository.")
@click.option("--branch", default="main", help="Target branch name.")
@click.option("--repo-dir", required=True, type=click.Path(exists=True), help="Path to cloned repository.")
@click.option("--commit", default="HEAD", help="Target commit SHA (defaults to HEAD).")
@click.option("--enable-semantic", is_flag=True, default=False, help="Enable semantic vector indexing.")
def init(repo_id: str, branch: str, repo_dir: str, commit: str, enable_semantic: bool):
    """Run repository initialization indexing job (compatibility wrapper over V1 Indexer)."""
    async def _run():
        graph_client = Neo4jClient()
        try:
            await graph_client.connect()
        except Exception:
            graph_client = None

        vector_client = VectorKBClient() if enable_semantic else None
        indexer = RepositoryIndexer(graph_client=graph_client, vector_client=vector_client)
        try:
            job, state, report = await indexer.run(
                repo_dir=Path(repo_dir),
                repo_id=repo_id,
                target_commit_sha=commit,
                branch=branch,
                validate_only=(graph_client is None),
            )
            output = {
                "status": state.status.value,
                "symbols_count": state.stats.get("entities_created", 0),
                "edges_count": state.stats.get("relationships_created", 0),
                "duration_seconds": state.stats.get("duration_seconds", 0.0),
                "indexed_commit_sha": state.indexed_commit_sha,
                "validation_passed": report.is_valid,
            }
            click.echo(json.dumps(output, indent=2))
        finally:
            if graph_client:
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
    """Run semantic similarity search on vector knowledge base."""
    async def _run():
        from src.mcp.tools import tool_vector_search
        vector_client = VectorKBClient()
        res = await tool_vector_search(vector_client, query_text=query, repo_id=repo_id, n_results=n_results)
        click.echo(res)

    asyncio.run(_run())


@main.command()
def doctor():
    """Diagnose connectivity and health of Neo4j, Vector DB, and Gemini LLM."""
    from src.config import settings
    import time

    async def _run():
        click.echo("Running AI Service diagnostics...\n")

        # 1. Neo4j
        neo_status = "FAILED"
        neo_latency = 0.0
        neo_details = ""
        try:
            g_start = time.perf_counter()
            gc = Neo4jClient()
            await gc.connect()
            recs = await gc.execute_query("RETURN 1 as ping")
            neo_latency = (time.perf_counter() - g_start) * 1000
            node_counts = await gc.execute_query("MATCH (n) RETURN count(n) as cnt")
            cnt = node_counts[0]["cnt"] if node_counts else 0
            neo_status = "OK"
            neo_details = f"{cnt} nodes in DB ({settings.neo4j_uri or 'bolt://localhost:7687'})"
            await gc.close()
        except Exception as e:
            neo_details = str(e)

        # 2. Vector DB
        vec_status = "FAILED"
        vec_latency = 0.0
        vec_details = ""
        try:
            v_start = time.perf_counter()
            vc = VectorKBClient()
            v_count = vc.count()
            vec_latency = (time.perf_counter() - v_start) * 1000
            vec_status = "OK"
            vec_details = f"Active backend: {settings.vector_db} ({v_count} vectors)"
        except Exception as e:
            vec_details = str(e)

        # 3. Gemini / LLM
        llm_status = "FAILED"
        llm_details = ""
        try:
            if settings.gemini_api_key:
                masked_key = f"{settings.gemini_api_key[:6]}...{settings.gemini_api_key[-4:]}"
                llm_status = "CONFIGURED"
                llm_details = f"Key: {masked_key}"
            else:
                llm_status = "MISSING KEY"
                llm_details = "GEMINI_API_KEY environment variable not set"
        except Exception as e:
            llm_details = str(e)

        click.echo(f"  [Neo4j Graph DB]  {neo_status:10} ({neo_latency:6.1f}ms) - {neo_details}")
        click.echo(f"  [Vector DB]       {vec_status:10} ({vec_latency:6.1f}ms) - {vec_details}")
        click.echo(f"  [Gemini LLM]      {llm_status:10}           - {llm_details}")

    asyncio.run(_run())


@main.group()
def graph():
    """Graph database inspection and repair commands."""
    pass


@graph.command(name="inspect")
@click.option("--repo-id", help="Filter inspection to a specific repository ID.")
def graph_inspect(repo_id: Optional[str]):
    """Inspect Neo4j node counts, edge relationships, and orphan symbols."""
    from src.graph.reader import inspect_graph

    async def _run():
        gc = Neo4jClient()
        await gc.connect()
        try:
            res = await inspect_graph(gc, repo_id=repo_id)
            click.echo(json.dumps(res, indent=2))
        finally:
            await gc.close()

    asyncio.run(_run())


@graph.command(name="repair")
@click.option("--repo-id", help="Filter repair to a specific repository ID.")
def graph_repair(repo_id: Optional[str]):
    """Rebuild missing Directory nodes and ensure file imports strictly connect File to File."""
    from src.graph.writer import repair_graph_hierarchy, repair_import_edges

    async def _run():
        gc = Neo4jClient()
        await gc.connect()
        try:
            click.echo("Repairing graph hierarchy...")
            res_hier = await repair_graph_hierarchy(gc, repo_id=repo_id)
            click.echo(json.dumps(res_hier, indent=2))

            click.echo("Repairing file import relationships (File -> File)...")
            res_imp = await repair_import_edges(gc, repo_id=repo_id)
            click.echo(json.dumps(res_imp, indent=2))

            click.echo("Graph repair completed successfully.")
        finally:
            await gc.close()

    asyncio.run(_run())


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
            from src.mcp.tools import tool_hybrid_search
            res = await tool_hybrid_search(graph_client, vector_client, repo_id=repo_id, query_text=query, branch=branch, n_results=n_results)
            click.echo(res)
        finally:
            await graph_client.close()

    asyncio.run(_run())


@main.command()
def mcp():
    """Start FastMCP server for Knowledge Base tool integration."""
    from src.mcp.server import run_mcp_server
    run_mcp_server()


@main.command()
@click.option("--host", default="0.0.0.0", help="Host address to bind server. Defaults to 0.0.0.0 for external access.")
@click.option("--port", default=None, type=int, help="Port to bind server. Defaults to PORT env var or 8000.")
@click.option("--reload", is_flag=True, default=False, help="Enable auto-reload on code changes.")
def serve(host: str, port: Optional[int], reload: bool):
    """Start FastAPI HTTP server for Chat API & Agent Tool Visualizer backend."""
    import uvicorn
    import os
    if port is None:
        port = int(os.environ.get("PORT", 8000))
    uvicorn.run("src.web.app:app", host=host, port=port, reload=reload)




@main.command()
@click.option("--repo-dir", required=True, type=click.Path(exists=True), help="Path to target codebase.")
@click.option("--output", default="kb_graph.html", help="Output HTML file path.")
def visualize(repo_dir: str, output: str):
    """Generate an interactive HTML visual graph of the vectorless Knowledge Base."""
    from src.parsing.parser import CodeParser
    from src.visualize import generate_graph_html

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
            from src.graph.writer import delete_repo_data
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


@main.command()
@click.option("--repo-id", required=True, help="Target repository ID to analyze.")
@click.option("--branch", default="main", help="Target branch name.")
@click.option("--out-dir", default="graphify-out", help="Output directory for the reports.")
def analyze(repo_id: str, branch: str, out_dir: str):
    """Run Graphify architectural analysis (God nodes, communities, cycles) and generate report."""
    async def _run():
        graph_client = Neo4jClient()
        await graph_client.connect()
        try:
            from src.graph.reader import get_entire_graph
            from src.analysis.graph_analysis import (
                build_networkx_graph, cluster_graph, find_god_nodes, 
                find_surprising_connections, find_import_cycles
            )
            from src.analysis.report import generate_graph_report
            
            click.echo(f"Fetching graph from Neo4j for {repo_id}...")
            graph_data = await get_entire_graph(graph_client, repo_id=repo_id, branch=branch)
            click.echo(f"Building NetworkX graph with {len(graph_data['nodes'])} nodes and {len(graph_data['edges'])} edges...")
            G = build_networkx_graph(graph_data)
            
            click.echo("Running Louvain community detection...")
            communities = cluster_graph(G)
            click.echo("Detecting God Nodes...")
            god_nodes = find_god_nodes(G)
            click.echo("Finding surprising connections...")
            surprising = find_surprising_connections(G, communities)
            click.echo("Finding import cycles...")
            cycles = find_import_cycles(G)
            
            click.echo(f"Generating report in {out_dir}...")
            md_path = generate_graph_report(
                repo_id=repo_id,
                nodes=graph_data["nodes"],
                edges=graph_data["edges"],
                communities=communities,
                god_nodes=god_nodes,
                surprising=surprising,
                cycles=cycles,
                out_dir=out_dir
            )
            click.echo(f"Successfully generated architectural report at: {md_path.resolve()}")
            
        finally:
            await graph_client.close()

    asyncio.run(_run())


# Register Benchmark Subsystem Commands
from src.benchmark.cli import benchmark_group
main.add_command(benchmark_group)


if __name__ == "__main__":
    main()
