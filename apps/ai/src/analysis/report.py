import json
from pathlib import Path
from typing import Dict, Any, List


def generate_graph_report(
    repo_id: str,
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    communities: Dict[int, List[str]],
    god_nodes: List[Dict[str, Any]],
    surprising: List[Dict[str, Any]],
    cycles: List[List[str]],
    out_dir: str | Path = "."
) -> Path:
    """Generate GRAPH_REPORT.md and graph.json (Graphify Stage 6)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Export JSON
    graph_data = {
        "repo_id": repo_id,
        "nodes": nodes,
        "edges": edges,
        "communities": communities,
        "analysis": {
            "god_nodes": god_nodes,
            "surprising_connections": surprising,
            "import_cycles": cycles
        }
    }
    json_path = out_dir / "graph.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, indent=2)

    # 2. Export Markdown Report
    md_path = out_dir / "GRAPH_REPORT.md"
    
    lines = [
        f"# Graphify Architectural Report: {repo_id}",
        "",
        "## Summary Statistics",
        f"- **Total Nodes**: {len(nodes)}",
        f"- **Total Edges**: {len(edges)}",
        f"- **Number of Communities**: {len(communities)}",
        "",
        "## Communities",
        "Communities represent clusters of highly connected files/symbols."
    ]
    
    for c_id, members in communities.items():
        lines.append(f"- **Community {c_id}**: {len(members)} nodes")
        # List up to 5 members as preview
        preview = members[:5]
        if len(members) > 5:
            preview.append("...")
        lines.append(f"  - Members: {', '.join(preview)}")
        
    lines.append("")
    lines.append("## God Nodes (Highest Degree)")
    lines.append("These are the most central, highly coupled nodes in the architecture.")
    lines.append("| Node | Type | Total Degree | In-Degree | Out-Degree |")
    lines.append("|------|------|--------------|-----------|------------|")
    for n in god_nodes:
        lines.append(f"| `{n['label']}` | {n['type']} | {n['degree']} | {n['in_degree']} | {n['out_degree']} |")
        
    lines.append("")
    lines.append("## Surprising Connections (Cross-Community)")
    lines.append("These connections bridge different modules/communities and may indicate architectural leakage.")
    if not surprising:
        lines.append("*No surprising cross-community connections found.*")
    else:
        lines.append("| Source (Comm) | Relation | Target (Comm) |")
        lines.append("|---------------|----------|---------------|")
        for s in surprising:
            lines.append(f"| `{s['source_label']}` ({s['source_community']}) | {s['relation']} | `{s['target_label']}` ({s['target_community']}) |")

    lines.append("")
    lines.append("## Import Cycles")
    lines.append("Circular dependencies detected in the codebase.")
    if not cycles:
        lines.append("*No import cycles detected.*")
    else:
        for idx, cycle in enumerate(cycles):
            lines.append(f"**Cycle {idx+1}**:")
            cycle_str = " -> ".join([f"`{node}`" for node in cycle]) + f" -> `{cycle[0]}`"
            lines.append(f"- {cycle_str}")
            
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        
    return md_path
