import json
from pathlib import Path
from typing import List
from src.parsing.models import ParseResult


def generate_graph_html(parse_results: List[ParseResult], output_path: str | Path = "kb_graph.html") -> Path:
    """Generate an interactive Vis.js HTML page visualizing the Knowledge Base graph."""
    nodes = []
    edges = []
    node_ids = set()

    # Color palette for node kinds
    color_map = {
        "function": "#3b82f6",  # Blue
        "method": "#6366f1",    # Indigo
        "class": "#a855f7",     # Purple
        "component": "#ec4899", # Pink (React)
        "module": "#10b981",    # Emerald
    }

    for pr in parse_results:
        # Add Module node
        mod_id = f"module:{pr.file_path}"
        if mod_id not in node_ids:
            node_ids.add(mod_id)
            nodes.append({
                "id": mod_id,
                "label": Path(pr.file_path).name,
                "title": f"File: {pr.file_path}\nLanguage: {pr.language}",
                "color": {"background": "#10b981", "border": "#059669"},
                "shape": "folder",
                "font": {"color": "#ffffff"}
            })

        # Add Symbol nodes
        for sym in pr.symbols:
            if sym.qualified_name not in node_ids:
                node_ids.add(sym.qualified_name)
                color = color_map.get(sym.kind, "#64748b")
                nodes.append({
                    "id": sym.qualified_name,
                    "label": f"{sym.name}\n({sym.kind})",
                    "title": f"Symbol: {sym.qualified_name}\nKind: {sym.kind}\nFile: {sym.file_path}\nLines: {sym.start_line}-{sym.end_line}",
                    "color": {"background": color, "border": "#334155"},
                    "shape": "box" if sym.kind in ("class", "component") else "ellipse",
                    "font": {"color": "#ffffff"}
                })

            # Edge: Module CONTAINS Symbol
            edges.append({
                "from": mod_id,
                "to": sym.qualified_name,
                "label": "contains",
                "color": {"color": "#475569"},
                "arrows": "to"
            })

        # Add Call Edges
        for c in pr.calls:
            if c.caller_symbol in node_ids:
                # Find matching target symbol
                target_id = next((s.qualified_name for pr_item in parse_results for s in pr_item.symbols if s.name == c.callee_name), None)
                if not target_id:
                    target_id = f"external:{c.callee_name}"
                    if target_id not in node_ids:
                        node_ids.add(target_id)
                        nodes.append({
                            "id": target_id,
                            "label": c.callee_name,
                            "title": f"External/Built-in: {c.callee_name}",
                            "color": {"background": "#64748b", "border": "#475569"},
                            "shape": "diamond",
                            "font": {"color": "#ffffff"}
                        })
                edges.append({
                    "from": c.caller_symbol,
                    "to": target_id,
                    "label": f"calls (L{c.line})",
                    "color": {"color": "#f59e0b"},
                    "arrows": "to"
                })

        # Add Import Edges
        for imp in pr.imports:
            imp_id = f"import:{imp.module_path}"
            if imp_id not in node_ids:
                node_ids.add(imp_id)
                nodes.append({
                    "id": imp_id,
                    "label": imp.module_path,
                    "title": f"Import Module: {imp.module_path}",
                    "color": {"background": "#06b6d4", "border": "#0891b2"},
                    "shape": "database",
                    "font": {"color": "#ffffff"}
                })
            edges.append({
                "from": mod_id,
                "to": imp_id,
                "label": "imports",
                "color": {"color": "#06b6d4"},
                "arrows": "to"
            })

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vectorless Knowledge Base — Interactive Call & Import Graph</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #0f172a;
            color: #f8fafc;
            margin: 0;
            padding: 24px;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 1px solid #334155;
        }}
        .title {{
            font-size: 1.5rem;
            font-weight: 700;
            color: #38bdf8;
        }}
        .legend {{
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }}
        .pill {{
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 0.8rem;
            font-weight: 600;
            color: #ffffff;
        }}
        #network {{
            width: 100%;
            height: 720px;
            background-color: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="title">🧠 Vectorless Knowledge Base — Interactive Code Graph</div>
        <div class="legend">
            <span class="pill" style="background-color: #10b981;">File / Module</span>
            <span class="pill" style="background-color: #3b82f6;">Function</span>
            <span class="pill" style="background-color: #6366f1;">Method</span>
            <span class="pill" style="background-color: #a855f7;">Class</span>
            <span class="pill" style="background-color: #ec4899;">React Component</span>
            <span class="pill" style="background-color: #06b6d4;">Import</span>
        </div>
    </div>
    <div id="network"></div>
    <script>
        const nodes = new vis.DataSet({json.dumps(nodes)});
        const edges = new vis.DataSet({json.dumps(edges)});
        const container = document.getElementById('network');
        const data = {{ nodes: nodes, edges: edges }};
        const options = {{
            nodes: {{
                font: {{ size: 14, color: '#ffffff' }},
                borderWidth: 2,
                shadow: true
            }},
            edges: {{
                width: 2,
                font: {{ size: 11, align: 'middle', color: '#94a3b8' }},
                smooth: {{ type: 'cubicBezier' }}
            }},
            physics: {{
                barnesHut: {{ gravConstant: -3000, centralGravity: 0.3, springLength: 120 }}
            }}
        }};
        const network = new vis.Network(container, data, options);
    </script>
</body>
</html>
"""
    out_file = Path(output_path)
    out_file.write_text(html_content, encoding="utf-8")
    return out_file
