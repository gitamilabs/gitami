import networkx as nx
from typing import Dict, Any, List, Set, Tuple


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
            G.add_edge(src, tgt, relation=edge["relation"], **edge.get("props", {}))
            
    return G


def cluster_graph(G: nx.DiGraph) -> Dict[int, List[str]]:
    """Run Louvain community detection to group nodes into modules."""
    # Louvain works on undirected graphs
    undirected_G = G.to_undirected()
    
    # Remove isolated nodes to avoid trivial communities
    undirected_G.remove_nodes_from(list(nx.isolates(undirected_G)))
    
    if len(undirected_G) == 0:
        return {}

    # Since networkx 3.0, louvain is built-in
    try:
        communities = nx.community.louvain_communities(undirected_G)
        result = {}
        for idx, comm in enumerate(communities):
            result[idx] = list(comm)
        return result
    except Exception as e:
        # Fallback if algo fails for some reason
        return {0: list(G.nodes())}


def find_god_nodes(G: nx.DiGraph, top_n: int = 10) -> List[Dict[str, Any]]:
    """Find the most highly connected nodes (hubs/god nodes)."""
    # Calculate degree centrality
    in_degrees = dict(G.in_degree())
    out_degrees = dict(G.out_degree())
    total_degrees = {n: in_degrees.get(n, 0) + out_degrees.get(n, 0) for n in G.nodes()}
    
    # Filter out synthetic 'File' nodes if we only want Symbols, but let's keep it simple for now
    # We'll just filter for actual symbols and packages
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
            
    # Sort by total degree descending
    hub_nodes.sort(key=lambda x: x["degree"], reverse=True)
    return hub_nodes[:top_n]


def find_surprising_connections(G: nx.DiGraph, communities: Dict[int, List[str]]) -> List[Dict[str, Any]]:
    """Find edges that cross community boundaries."""
    # Map node to community id
    node_to_comm = {}
    for c_id, members in communities.items():
        for m in members:
            node_to_comm[m] = c_id
            
    surprising = []
    for u, v, data in G.edges(data=True):
        comm_u = node_to_comm.get(u)
        comm_v = node_to_comm.get(v)
        
        # If they belong to different communities and both are actually in a community
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
            
    # Sort them loosely by some metric or just return top ones
    return surprising[:50]  # Cap at 50 to avoid massive lists


def find_import_cycles(G: nx.DiGraph) -> List[List[str]]:
    """Find circular dependency chains (e.g., A -> B -> C -> A)."""
    # Only consider IMPORTS and CALLS edges? For architecture, usually file imports are what matter.
    # We'll filter the graph to just those edges.
    sub_G = nx.DiGraph()
    for u, v, data in G.edges(data=True):
        if data.get("relation") in ("IMPORTS", "CALLS"):
            sub_G.add_edge(u, v)
            
    try:
        # nx.simple_cycles can be expensive, we cap the length or number of cycles
        cycles = list(nx.simple_cycles(sub_G, length_bound=5))
        return cycles[:20]  # Cap at 20
    except (nx.NetworkXError, nx.NetworkXNotImplemented, TypeError):
        # Fallback if length_bound is not supported in this nx version
        # We manually filter the generator
        gen = nx.simple_cycles(sub_G)
        cycles = []
        for i, c in enumerate(gen):
            if len(c) <= 5:
                cycles.append(c)
            if len(cycles) >= 20 or i > 1000:
                break
        return cycles
