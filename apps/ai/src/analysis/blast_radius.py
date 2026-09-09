from dataclasses import dataclass, field
from typing import List
from src.graph.client import Neo4jClient
from src.graph.reader import get_dependents


@dataclass
class AffectedSymbol:
    qualified_name: str
    file_path: str
    depth: int
    fan_in: int = 1


@dataclass
class BlastRadiusResult:
    changed_symbols: List[str]
    affected_symbols: List[AffectedSymbol] = field(default_factory=list)
    risk_score: float = 0.0

    @property
    def total_affected(self) -> int:
        return len(self.affected_symbols)


async def compute_blast_radius(
    client: Neo4jClient, repo_id: str, branch: str, changed_symbols: List[str], max_depth: int = 3
) -> BlastRadiusResult:
    """Traverse graph per repo_id to find all transitive dependents of changed_symbols and compute risk score."""
    result = BlastRadiusResult(changed_symbols=changed_symbols)
    if not changed_symbols:
        return result

    seen_symbols = {}
    expanded_target_symbols = []

    # Expand any file path inputs to their defined symbols
    for item in changed_symbols:
        item_clean = item.strip()
        # Check if item matches a File node or has a file extension
        file_sym_query = """
        MATCH (f:File {repo_id: $repo_id, branch: $branch})
        WHERE f.file_path = $fp 
           OR toLower(f.file_path) ENDS WITH toLower('/' + $fp)
           OR toLower(f.file_path) CONTAINS toLower($fp)
        MATCH (f)-[:DEFINES]->(s:Symbol)
        RETURN s.name AS name, s.qualified_name AS qualified_name
        """
        file_syms = await client.execute_query(file_sym_query, {"repo_id": repo_id, "branch": branch, "fp": item_clean})
        if file_syms:
            for s in file_syms:
                sym_identifier = s.get("name") or s.get("qualified_name")
                if sym_identifier:
                    expanded_target_symbols.append(sym_identifier)

        if not expanded_target_symbols:
            sym_name = item_clean.split("::")[-1].split(".")[-1]
            expanded_target_symbols.append(sym_name)

    for sym_name in set(expanded_target_symbols):
        dependents = await get_dependents(client, repo_id, branch, callee_name=sym_name, max_depth=max_depth)

        for dep in dependents:
            qname = dep.get("qualified_name")
            if not qname or qname in changed_symbols:
                continue

            depth = dep.get("depth", 1)
            file_path = dep.get("file_path", "")

            if qname not in seen_symbols:
                seen_symbols[qname] = AffectedSymbol(qualified_name=qname, file_path=file_path, depth=depth, fan_in=1)
            else:
                seen_symbols[qname].fan_in += 1
                seen_symbols[qname].depth = min(seen_symbols[qname].depth, depth)

    affected_list = list(seen_symbols.values())
    result.affected_symbols = affected_list

    # Risk score calculation: weighted sum of affected count divided by depth + fan_in boost
    score = 0.0
    for aff in affected_list:
        score += (1.0 / aff.depth) * (1.0 + 0.5 * (aff.fan_in - 1))
    result.risk_score = round(score, 2)

    return result

