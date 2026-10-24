import os
import networkx as nx
from typing import Dict, Any, List, Set, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def build_networkx_graph(graph_data: Dict[str, Any]) -> nx.DiGraph:
    """Build a networkx directed graph from Neo4j node/edge data."""
    G = nx.DiGraph()

    for node in graph_data.get("nodes", []):
        node_id = node["id"]
        G.add_node(node_id, **node)

    for edge in graph_data.get("edges", []):
        src = edge["source"]
        tgt = edge["target"]
        if src in G and tgt in G:
            G.add_edge(src, tgt, relation=edge.get("relation", "DEPENDS_ON"), **edge.get("props", {}))

    return G


def detect_communities(G: nx.DiGraph) -> Dict[int, List[str]]:
    """
    Topology-based community detection using Leiden (via graspologic) as primary implementation.
    Falls back to NetworkX Louvain only if graspologic.partition is unavailable.
    """
    undirected_G = G.to_undirected()
    undirected_G.remove_nodes_from(list(nx.isolates(undirected_G)))

    if len(undirected_G) == 0:
        # If no connected edges, group isolated nodes by directory/package
        return _fallback_directory_partition(G)

    # 1. Primary: Leiden algorithm via graspologic
    try:
        from graspologic.partition import leiden
        node_to_comm = leiden(undirected_G)
        result: Dict[int, List[str]] = {}
        for node, c_id in node_to_comm.items():
            result.setdefault(c_id, []).append(node)
        logger.info(f"Leiden community detection succeeded: {len(result)} communities found.")
        return result
    except Exception as e:
        logger.warning(f"Leiden community detection unavailable or failed ({e}), falling back to Louvain.")

    # 2. Fallback: NetworkX Louvain
    try:
        communities = nx.community.louvain_communities(undirected_G)
        result = {idx: list(comm) for idx, comm in enumerate(communities)}
        return result
    except Exception as e:
        logger.warning(f"Louvain fallback failed ({e}), using directory partition.")
        return _fallback_directory_partition(G)


def _fallback_directory_partition(G: nx.DiGraph) -> Dict[int, List[str]]:
    """Fallback partition based on file directory / module paths."""
    dir_map: Dict[str, List[str]] = {}
    for node_id, data in G.nodes(data=True):
        fpath = data.get("props", {}).get("file_path") or data.get("props", {}).get("path") or node_id
        parts = [p for p in fpath.replace("\\", "/").split("/") if p]
        key = "/".join(parts[:2]) if len(parts) > 1 else "Root Files"
        dir_map.setdefault(key, []).append(node_id)
    return {idx: members for idx, members in enumerate(dir_map.values())}


def handle_oversized_communities(
    communities: Dict[int, List[str]],
    G: nx.DiGraph,
    max_size: int = 45,
) -> Dict[int, List[str]]:
    """
    Graphify-inspired oversized-community handling:
    If a detected community contains too many nodes (> max_size),
    recursively partition the sub-graph to maintain balanced, readable clusters.
    """
    refined_communities: Dict[int, List[str]] = {}
    current_id = 0

    for c_id, members in communities.items():
        if len(members) <= max_size:
            refined_communities[current_id] = members
            current_id += 1
            continue

        # Sub-cluster oversized community
        sub_G = G.subgraph(members).to_undirected()
        sub_G.remove_nodes_from(list(nx.isolates(sub_G)))

        if len(sub_G) > 0:
            try:
                from graspologic.partition import leiden
                sub_partition = leiden(sub_G)
                sub_groups: Dict[int, List[str]] = {}
                for node, sub_c in sub_partition.items():
                    sub_groups.setdefault(sub_c, []).append(node)

                # Add isolated sub-nodes that had zero intra-edges
                handled_nodes = set(sub_partition.keys())
                unhandled = [m for m in members if m not in handled_nodes]
                if unhandled:
                    sub_groups.setdefault(-1, []).extend(unhandled)

                for g in sub_groups.values():
                    if g:
                        refined_communities[current_id] = g
                        current_id += 1
                continue
            except Exception:
                pass

        refined_communities[current_id] = members
        current_id += 1

    return refined_communities


def derive_community_label(members: List[str], G: nx.DiGraph) -> str:
    """
    Derives an architectural code-area label for a community using semantic cues,
    directory prefixes, and dominant high-degree symbols.
    """
    path_counts: Dict[str, int] = {}
    combined_text = []

    for node_id in members:
        data = G.nodes.get(node_id, {})
        props = data.get("props", {})
        fpath = props.get("file_path") or props.get("path") or (node_id if "/" in node_id else "")
        label = data.get("label") or node_id.split("/")[-1]
        combined_text.append(fpath.lower())
        combined_text.append(label.lower())

        if fpath:
            parts = [p for p in fpath.replace("\\", "/").split("/") if p and p != "src"]
            if parts:
                key = "/".join(parts[:2]) if len(parts) > 1 else parts[0]
                path_counts[key] = path_counts.get(key, 0) + 1

    all_tokens = " ".join(combined_text)

    # 1. Semantic domain matches (Graphify-style)
    if "admin" in all_tokens:
        return "Admin User Management"
    if "relation" in all_tokens and ("schema" in all_tokens or "db" in all_tokens or "drizzle" in all_tokens):
        return "Database Relations"
    if ("schema" in all_tokens or "user" in all_tokens) and ("table" in all_tokens or "pg" in all_tokens or "column" in all_tokens):
        return "User Account Schema"
    if "auth" in all_tokens or "jwt" in all_tokens or "token" in all_tokens or "password" in all_tokens:
        return "Authentication & Auth Middleware"
    if "route" in all_tokens or "router" in all_tokens or "controller" in all_tokens or "endpoint" in all_tokens:
        return "API Routes & Controllers"
    if "config" in all_tokens or "env" in all_tokens or "constant" in all_tokens or "logger" in all_tokens:
        return "Core Infrastructure & Config"
    if "middleware" in all_tokens or "error" in all_tokens:
        return "Middlewares & Error Handling"
    if "test" in all_tokens or "spec" in all_tokens:
        return "Test Suites & Mocks"

    # 2. Directory prefix fallback with clean Title Case
    if path_counts:
        best_dir = max(path_counts.items(), key=lambda x: x[1])[0]
        parts = best_dir.split("/")
        last_part = parts[-1].replace("_", " ").replace("-", " ").title()
        if "util" in last_part.lower():
            return "Shared Utilities"
        if "db" in last_part.lower():
            return "Database Layer"
        if "config" in last_part.lower():
            return "Configuration"
        return f"{last_part} Module"

    # 3. High degree symbol fallback
    symbol_names = []
    for node_id in members:
        deg = G.degree(node_id) if node_id in G else 0
        data = G.nodes.get(node_id, {})
        label = data.get("label") or node_id.split("/")[-1]
        symbol_names.append((label, deg))

    if symbol_names:
        symbol_names.sort(key=lambda x: x[1], reverse=True)
        return symbol_names[0][0]

    return "Core System"


def compute_graph_presentation(graph_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Full graph transformation pipeline:
    1. Builds directed graph
    2. Runs Leiden community detection (with Louvain fallback)
    3. Handles oversized communities
    4. Computes node degree, in-degree, out-degree, importance (PageRank)
    5. Formats structured nodes, edges, communities, and stats
    """
    G = build_networkx_graph(graph_data)

    # Community detection
    raw_communities = detect_communities(G)
    communities_map = handle_oversized_communities(raw_communities, G)

    # Node to community mapping
    node_to_comm_id: Dict[str, int] = {}
    node_to_comm_label: Dict[str, str] = {}
    community_summaries: List[Dict[str, Any]] = []

    # Palette assignments
    PALETTE = [
        {"bg": "#0ea5e9", "border": "#0284c7", "name": "Sky"},
        {"bg": "#10b981", "border": "#059669", "name": "Emerald"},
        {"bg": "#8b5cf6", "border": "#7c3aed", "name": "Violet"},
        {"bg": "#f59e0b", "border": "#d97706", "name": "Amber"},
        {"bg": "#f43f5e", "border": "#e11d48", "name": "Rose"},
        {"bg": "#06b6d4", "border": "#0891b2", "name": "Cyan"},
        {"bg": "#6366f1", "border": "#4f46e5", "name": "Indigo"},
        {"bg": "#84cc16", "border": "#65a30d", "name": "Lime"},
        {"bg": "#ec4899", "border": "#db2777", "name": "Pink"},
        {"bg": "#64748b", "border": "#475569", "name": "Slate"},
    ]

    for c_id, members in communities_map.items():
        label = derive_community_label(members, G)
        pal = PALETTE[c_id % len(PALETTE)]
        for m in members:
            node_to_comm_id[m] = c_id
            node_to_comm_label[m] = label

        community_summaries.append({
            "id": c_id,
            "label": label,
            "size": len(members),
            "color": pal["bg"],
            "borderColor": pal["border"],
            "paletteName": pal["name"],
        })

    # PageRank for importance
    try:
        pagerank = nx.pagerank(G, alpha=0.85, max_iter=100)
    except Exception:
        pagerank = {n: 1.0 / max(len(G), 1) for n in G.nodes()}

    # Format nodes
    formatted_nodes = []
    for node in graph_data.get("nodes", []):
        n_id = node["id"]
        c_id = node_to_comm_id.get(n_id, 0)
        c_label = node_to_comm_label.get(n_id, "Core System")
        in_deg = G.in_degree(n_id) if n_id in G else 0
        out_deg = G.out_degree(n_id) if n_id in G else 0
        total_deg = in_deg + out_deg
        imp = pagerank.get(n_id, 0.0)

        pal = PALETTE[c_id % len(PALETTE)]

        formatted_nodes.append({
            "id": n_id,
            "label": node.get("label") or n_id.split("/")[-1],
            "type": node.get("type", "Symbol"),
            "communityId": c_id,
            "communityLabel": c_label,
            "communityColor": pal["bg"],
            "communityBorder": pal["border"],
            "degree": total_deg,
            "inDegree": in_deg,
            "outDegree": out_deg,
            "importance": round(imp * 1000, 2),
            "props": node.get("props", {}),
        })

    # Format edges
    formatted_edges = []
    for idx, edge in enumerate(graph_data.get("edges", [])):
        src = edge["source"]
        tgt = edge["target"]
        rel = edge.get("relation", "DEPENDS_ON")
        formatted_edges.append({
            "id": f"edge-{idx}-{src}-{tgt}",
            "source": src,
            "target": tgt,
            "relation": rel,
            "type": rel,
            "props": edge.get("props", {}),
        })

    raw_stats = graph_data.get("stats", {})
    extracted_cnt = raw_stats.get(
        "extractedCount",
        sum(1 for n in formatted_nodes if n.get("props", {}).get("provenance") != "INFERRED" and n.get("type") != "Inferred")
    )
    inferred_cnt = raw_stats.get(
        "inferredCount",
        sum(1 for n in formatted_nodes if n.get("props", {}).get("provenance") == "INFERRED" or n.get("type") == "Inferred")
    )

    return {
        "nodes": formatted_nodes,
        "edges": formatted_edges,
        "communities": community_summaries,
        "stats": {
            "nodeCount": len(formatted_nodes),
            "edgeCount": len(formatted_edges),
            "communityCount": len(community_summaries),
            "extractedCount": extracted_cnt,
            "inferredCount": inferred_cnt,
            "synthesizedCount": raw_stats.get("synthesizedCount", 0),
            "observedCount": raw_stats.get("observedCount", 0),
        },
    }


def find_god_nodes(G: nx.DiGraph, top_n: int = 10) -> List[Dict[str, Any]]:
    """Find the most highly connected nodes (hubs/god nodes)."""
    in_degrees = dict(G.in_degree())
    out_degrees = dict(G.out_degree())
    total_degrees = {n: in_degrees.get(n, 0) + out_degrees.get(n, 0) for n in G.nodes()}

    hub_nodes = []
    for node, deg in total_degrees.items():
        node_data = G.nodes[node]
        if node_data.get("type") in ("Symbol", "Package"):
            hub_nodes.append({
                "id": node,
                "label": node_data.get("label", node),
                "type": node_data.get("type"),
                "degree": deg,
                "in_degree": in_degrees.get(node, 0),
                "out_degree": out_degrees.get(node, 0)
            })

    hub_nodes.sort(key=lambda x: x["degree"], reverse=True)
    return hub_nodes[:top_n]


def find_surprising_connections(G: nx.DiGraph, communities: Dict[int, List[str]]) -> List[Dict[str, Any]]:
    """Find edges that cross community boundaries."""
    node_to_comm = {}
    for c_id, members in communities.items():
        for m in members:
            node_to_comm[m] = c_id

    surprising = []
    for u, v, data in G.edges(data=True):
        comm_u = node_to_comm.get(u)
        comm_v = node_to_comm.get(v)

        if comm_u is not None and comm_v is not None and comm_u != comm_v:
            surprising.append({
                "source": u,
                "source_label": G.nodes[u].get("label", u),
                "source_community": comm_u,
                "target": v,
                "target_label": G.nodes[v].get("label", v),
                "target_community": comm_v,
                "relation": data.get("relation", "UNKNOWN")
            })

    return surprising[:50]


def cluster_graph(G: nx.DiGraph) -> Dict[int, List[str]]:
    """Legacy alias calling detect_communities."""
    return detect_communities(G)


def find_import_cycles(G: nx.DiGraph, max_cycles: int = 50) -> List[List[str]]:
    """
    Detect circular dependencies (cycles) in the directed code graph.
    Returns up to max_cycles cycles as lists of node identifiers.
    """
    cycles: List[List[str]] = []
    try:
        for cycle in nx.simple_cycles(G):
            cycles.append([str(node) for node in cycle])
            if len(cycles) >= max_cycles:
                break
    except Exception as e:
        logger.warning(f"Error computing simple cycles: {e}")
    return cycles
