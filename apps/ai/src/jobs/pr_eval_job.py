import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from git import Repo

from src.graph.client import Neo4jClient
from src.graph.writer import delete_file_data, upsert_symbols, upsert_call_edges, upsert_import_edges
from src.vector.client import VectorKBClient
from src.repo.differ import get_changed_files, get_changed_symbols
from src.parsing.parser import CodeParser
from src.analysis.blast_radius import compute_blast_radius, BlastRadiusResult
from src.analysis.conventions import check_conventions
from src.analysis.decision import make_decision, DecisionResult


@dataclass
class PrEvalResult:
    status: str
    decision: Optional[DecisionResult] = None
    changed_symbols: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)


async def run_pr_eval_job(
    repo_id: str,
    branch: str,
    repo_dir: str | Path,
    base_ref: str,
    head_ref: str,
    client: Neo4jClient,
    vector_client: Optional[VectorKBClient] = None,
    use_agent: bool = True,
) -> PrEvalResult:
    """Flow 2 — Pull Request Evaluation job: incremental graph/vector update -> blast radius -> convention check -> decision gate."""
    start_time = time.time()
    root = Path(repo_dir)

    if vector_client is None:
        vector_client = VectorKBClient()

    try:
        changed_files = get_changed_files(root, base_ref, head_ref)
        changed_symbols = get_changed_symbols(root, base_ref, head_ref)

        parser = CodeParser()
        all_symbols = []

        # Update incremental graph data for changed files
        for cf in changed_files:
            rel_path = cf.file_path.replace("\\", "/")
            await delete_file_data(client, repo_id=repo_id, branch=branch, file_path=rel_path)

            if cf.status in ("added", "modified"):
                abs_path = root / cf.file_path
                parse_res = parser.parse_file(abs_path)
                if parse_res:
                    all_symbols.extend(parse_res.symbols)
                    await upsert_symbols(client, repo_id=repo_id, branch=branch, symbols=parse_res.symbols)
                    await upsert_call_edges(client, repo_id=repo_id, branch=branch, calls=parse_res.calls)
                    await upsert_import_edges(client, repo_id=repo_id, branch=branch, imports=parse_res.imports)

                    # Update vector KB entries for modified/added file symbols
                    for sym in parse_res.symbols:
                        vector_client.add_code_entry(
                            repo=repo_id,
                            branch=branch,
                            file_path=sym.file_path,
                            symbol=sym.name,
                            signature=sym.signature,
                            description=sym.docstring or f"Symbol {sym.name} ({sym.kind}) in {sym.file_path}",
                            commit_hash=head_ref,
                            start_line=sym.start_line,
                            code_body=sym.code_body,
                        )

        # Run import resolution pass for updated files
        from src.graph.resolver import resolve_repo_imports
        await resolve_repo_imports(client, repo_id=repo_id, branch=branch)

        # Get raw diff text from Git Repo
        try:
            git_repo = Repo(root, search_parent_directories=True)
            raw_diff_text = git_repo.git.diff(base_ref, head_ref)
            git_repo.close()
        except Exception:
            raw_diff_text = f"Diff between {base_ref} and {head_ref}"

        if use_agent:
            from src.agents.reviewer import run_agentic_pr_review
            agent_res = await run_agentic_pr_review(
                client=client,
                repo_id=repo_id,
                branch=branch,
                changed_symbols=changed_symbols,
                raw_diff_text=raw_diff_text,
                symbols=all_symbols,
                vector_client=vector_client,
            )
            decision = agent_res.decision
        else:
            # 1. Blast radius calculation
            blast_radius = await compute_blast_radius(
                client=client,
                repo_id=repo_id,
                branch=branch,
                changed_symbols=changed_symbols,
            )

            # 2. Convention checks
            violations = check_conventions(all_symbols)

            # 3. Decision gate
            decision = make_decision(blast_radius=blast_radius, violations=violations)

        duration = round(time.time() - start_time, 3)
        return PrEvalResult(
            status="SUCCESS",
            decision=decision,
            changed_symbols=changed_symbols,
            duration_seconds=duration,
        )
    except Exception as e:
        return PrEvalResult(status="ERROR", errors=[str(e)])
