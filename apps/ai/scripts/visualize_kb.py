"""Generate an interactive HTML graph visualization from Neo4j data."""
import asyncio
import json
from src.graph.client import Neo4jClient


async def export_graph():
    """Query all nodes and edges and export as vis.js-compatible JSON."""
    c = Neo4jClient()
    await c.connect()

    nodes = []
    edges = []
    node_ids = {}

    # 1. File nodes
    res = await c.execute_query(
        "MATCH (f:File) RETURN f.file_path AS path, f.language AS lang, f.repo_id AS repo"
    )
    for r in res:
        nid = f"file:{r['path']}"
        short = r["path"].split("/")[-1]
        node_ids[r["path"]] = nid
        nodes.append({
            "id": nid,
            "label": short,
            "group": "file",
            "title": f"📁 {r['path']}<br>Language: {r['lang']}<br>Repo: {r['repo']}",
            "shape": "box",
            "font": {"size": 14, "face": "monospace"},
        })

    # 2. Symbol nodes
    res = await c.execute_query(
        "MATCH (f:File)-[:DEFINES]->(s:Symbol) RETURN s.qualified_name AS qn, s.name AS name, s.kind AS kind, s.file_path AS fp, s.start_line AS sl, s.end_line AS el, s.signature AS sig, f.repo_id AS repo"
    )
    for r in res:
        nid = f"sym:{r['qn']}"
        node_ids[r["qn"]] = nid
        kind = r["kind"]
        shape_map = {
            "class": "diamond",
            "component": "star",
            "function": "dot",
            "method": "triangle",
        }
        color_map = {
            "class": "#e74c3c",
            "component": "#9b59b6",
            "function": "#3498db",
            "method": "#2ecc71",
        }
        nodes.append({
            "id": nid,
            "label": r["name"],
            "group": kind,
            "title": f"{'🔴' if kind == 'class' else '🟣' if kind == 'component' else '🔵' if kind == 'function' else '🟢'} {kind}: {r['name']}<br>File: {r['fp']}<br>Lines: {r['sl']}-{r['el']}<br>Sig: {r['sig']}<br>Repo: {r['repo']}",
            "shape": shape_map.get(kind, "dot"),
            "color": color_map.get(kind, "#95a5a6"),
            "font": {"size": 12},
        })

    # 3. Package nodes
    res = await c.execute_query(
        "MATCH (p:Package) RETURN DISTINCT p.name AS name, p.repo_id AS repo"
    )
    for r in res:
        nid = f"pkg:{r['name']}:{r['repo']}"
        node_ids[f"pkg:{r['name']}:{r['repo']}"] = nid
        nodes.append({
            "id": nid,
            "label": r["name"],
            "group": "package",
            "title": f"📦 External: {r['name']}<br>Repo: {r['repo']}",
            "shape": "hexagon",
            "color": "#f39c12",
            "font": {"size": 11},
        })

    # 4. DEFINES edges
    res = await c.execute_query(
        "MATCH (f:File)-[:DEFINES]->(s:Symbol) RETURN f.file_path AS fp, s.qualified_name AS qn"
    )
    for r in res:
        edges.append({
            "from": f"file:{r['fp']}",
            "to": f"sym:{r['qn']}",
            "label": "DEFINES",
            "color": {"color": "#bdc3c7"},
            "arrows": "to",
            "dashes": False,
            "width": 1,
        })

    # 5. CALLS edges
    res = await c.execute_query(
        "MATCH (a:Symbol)-[r:CALLS]->(b:Symbol) RETURN a.qualified_name AS caller_qn, b.qualified_name AS callee_qn, r.line AS line"
    )
    for r in res:
        edges.append({
            "from": f"sym:{r['caller_qn']}",
            "to": f"sym:{r['callee_qn']}",
            "label": "CALLS",
            "color": {"color": "#e74c3c"},
            "arrows": "to",
            "width": 2,
        })

    # 6. IMPORTS edges
    res = await c.execute_query(
        "MATCH (f:File)-[r:IMPORTS]->(s:Symbol) RETURN f.file_path AS fp, s.qualified_name AS qn, r.module_path AS mp"
    )
    for r in res:
        edges.append({
            "from": f"file:{r['fp']}",
            "to": f"sym:{r['qn']}",
            "label": "IMPORTS",
            "color": {"color": "#2ecc71"},
            "arrows": "to",
            "dashes": True,
            "width": 1.5,
        })

    # 7. DEPENDS_ON_FILE edges (Internal file-to-file dependencies)
    res = await c.execute_query(
        "MATCH (a:File)-[:DEPENDS_ON_FILE]->(b:File) RETURN a.file_path AS importer, b.file_path AS imported"
    )
    for r in res:
        edges.append({
            "from": f"file:{r['importer']}",
            "to": f"file:{r['imported']}",
            "label": "DEPENDS_ON_FILE",
            "color": {"color": "#3498db"},
            "arrows": "to",
            "dashes": True,
            "width": 2,
        })

    # 8. DEPENDS_ON edges (External packages)
    res = await c.execute_query(
        "MATCH (f:File)-[r:DEPENDS_ON]->(p:Package) RETURN f.file_path AS fp, p.name AS pkg, f.repo_id AS repo, r.imported_symbol AS sym"
    )
    for r in res:
        edges.append({
            "from": f"file:{r['fp']}",
            "to": f"pkg:{r['pkg']}:{r['repo']}",
            "label": f"uses {r['sym']}",
            "color": {"color": "#f39c12"},
            "arrows": "to",
            "dashes": True,
            "width": 1,
        })

    await c.close()
    return nodes, edges


def generate_html(nodes, edges):
    """Generate a self-contained vis.js HTML visualization."""
    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Knowledge Base Graph — Vectorless KB</title>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background: #1a1a2e; color: #eee; }}
        #graph {{ width: 100vw; height: 100vh; }}
        #legend {{
            position: fixed; top: 16px; right: 16px; background: rgba(22,22,44,0.95);
            border: 1px solid #333; border-radius: 10px; padding: 16px; z-index: 10;
            font-size: 13px; min-width: 200px;
        }}
        #legend h3 {{ margin-bottom: 10px; font-size: 15px; color: #aaa; }}
        .legend-row {{ display: flex; align-items: center; gap: 8px; margin: 6px 0; }}
        .legend-dot {{ width: 14px; height: 14px; border-radius: 50%; display: inline-block; }}
        #title {{
            position: fixed; top: 16px; left: 16px; background: rgba(22,22,44,0.95);
            border: 1px solid #333; border-radius: 10px; padding: 16px; z-index: 10;
        }}
        #title h2 {{ font-size: 18px; margin-bottom: 4px; }}
        #title p {{ font-size: 12px; color: #888; }}
        #stats {{
            position: fixed; bottom: 16px; left: 16px; background: rgba(22,22,44,0.95);
            border: 1px solid #333; border-radius: 10px; padding: 12px; z-index: 10;
            font-size: 12px; color: #888;
        }}
    </style>
</head>
<body>
    <div id="title">
        <h2>🧠 Vectorless Knowledge Base</h2>
        <p>Code structure graph — AST parsed with tree-sitter</p>
    </div>
    <div id="legend">
        <h3>Legend</h3>
        <div class="legend-row"><span class="legend-dot" style="background:#7f8c8d;border-radius:2px"></span> File (📁)</div>
        <div class="legend-row"><span class="legend-dot" style="background:#e74c3c"></span> Class</div>
        <div class="legend-row"><span class="legend-dot" style="background:#9b59b6"></span> Component (React)</div>
        <div class="legend-row"><span class="legend-dot" style="background:#3498db"></span> Function</div>
        <div class="legend-row"><span class="legend-dot" style="background:#2ecc71"></span> Method</div>
        <div class="legend-row"><span class="legend-dot" style="background:#f39c12;border-radius:0"></span> External Package</div>
        <hr style="border-color:#333;margin:8px 0">
        <div class="legend-row"><span style="color:#bdc3c7">—</span> DEFINES</div>
        <div class="legend-row"><span style="color:#e74c3c;font-weight:bold">→</span> CALLS</div>
        <div class="legend-row"><span style="color:#2ecc71">- -→</span> IMPORTS</div>
        <div class="legend-row"><span style="color:#f39c12">- -→</span> DEPENDS_ON</div>
    </div>
    <div id="stats">
        Nodes: {len(nodes)} | Edges: {len(edges)}
    </div>
    <div id="graph"></div>
    <script>
        var nodes = new vis.DataSet({json.dumps(nodes, indent=2)});
        var edges = new vis.DataSet({json.dumps(edges, indent=2)});

        var container = document.getElementById('graph');
        var data = {{ nodes: nodes, edges: edges }};
        var options = {{
            nodes: {{
                borderWidth: 2,
                shadow: true,
                font: {{ color: '#eee' }},
            }},
            edges: {{
                smooth: {{ type: 'curvedCCW', roundness: 0.2 }},
                font: {{ size: 9, color: '#888', strokeWidth: 0 }},
            }},
            groups: {{
                file: {{ color: {{ background: '#34495e', border: '#7f8c8d' }}, shape: 'box' }},
                "function": {{ color: {{ background: '#2980b9', border: '#3498db' }}, shape: 'dot', size: 20 }},
                "class": {{ color: {{ background: '#c0392b', border: '#e74c3c' }}, shape: 'diamond', size: 22 }},
                component: {{ color: {{ background: '#8e44ad', border: '#9b59b6' }}, shape: 'star', size: 22 }},
                method: {{ color: {{ background: '#27ae60', border: '#2ecc71' }}, shape: 'triangle', size: 16 }},
                "package": {{ color: {{ background: '#d35400', border: '#f39c12' }}, shape: 'hexagon', size: 16 }},
            }},
            physics: {{
                forceAtlas2Based: {{
                    gravitationalConstant: -40,
                    centralGravity: 0.005,
                    springLength: 150,
                    springConstant: 0.06,
                    damping: 0.5,
                }},
                solver: 'forceAtlas2Based',
                stabilization: {{ iterations: 200 }},
            }},
            interaction: {{
                hover: true,
                tooltipDelay: 100,
                navigationButtons: true,
                keyboard: true,
            }},
            layout: {{ improvedLayout: true }},
        }};
        var network = new vis.Network(container, data, options);
    </script>
</body>
</html>"""


async def main():
    nodes, edges = await export_graph()
    html = generate_html(nodes, edges)
    out_path = "tests/kb_visualization.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {len(nodes)} nodes, {len(edges)} edges to {out_path}")
    print("Open this file in your browser to see the interactive graph.")


asyncio.run(main())
