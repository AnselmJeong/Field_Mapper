from __future__ import annotations

import json
from pathlib import Path

import networkx as nx


def render_concept_map(clusters: list[dict], edges: list[dict], output_path: Path) -> None:
    import matplotlib.pyplot as plt

    graph = nx.Graph()

    for c in clusters:
        graph.add_node(
            c["cluster_id"],
            label=c["representative_label"],
            size=max(300, c["paper_count"] * 280),
        )

    for edge in edges:
        graph.add_edge(edge["source"], edge["target"], weight=edge["weight"])

    plt.figure(figsize=(14, 10))
    pos = nx.spring_layout(graph, seed=7, k=1.2)

    node_sizes = [graph.nodes[n]["size"] for n in graph.nodes]
    weights = [graph.edges[e]["weight"] for e in graph.edges] if graph.edges else []

    nx.draw_networkx_nodes(graph, pos, node_size=node_sizes, node_color="#0ea5e9", alpha=0.9)
    if graph.edges:
        nx.draw_networkx_edges(
            graph,
            pos,
            width=[1 + w * 0.8 for w in weights],
            edge_color="#64748b",
            alpha=0.55,
        )

    labels = {n: graph.nodes[n]["label"] for n in graph.nodes}
    nx.draw_networkx_labels(graph, pos, labels=labels, font_size=9, font_color="#0f172a")

    plt.title("FieldMapper Concept Map", fontsize=16)
    plt.axis("off")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=220)
    plt.close()


def render_concept_map_html(clusters: list[dict], edges: list[dict], output_path: Path) -> None:
    graph = nx.Graph()

    for c in clusters:
        node_id = str(c["cluster_id"])
        graph.add_node(
            node_id,
            label=c["representative_label"],
            paper_count=int(c["paper_count"]),
            concepts=c.get("concepts", []),
        )

    for edge in edges:
        source = str(edge["source"])
        target = str(edge["target"])
        if source != target:
            graph.add_edge(source, target, weight=float(edge.get("weight", 1.0)))

    pos = nx.spring_layout(graph, seed=7, k=1.2) if graph.nodes else {}

    nodes_payload: list[dict] = []
    for node_id, attrs in graph.nodes(data=True):
        x, y = pos.get(node_id, (0.0, 0.0))
        nodes_payload.append(
            {
                "id": node_id,
                "label": attrs.get("label", node_id),
                "x": float(x),
                "y": float(y),
                "size": max(10.0, min(28.0, 10.0 + attrs.get("paper_count", 1) * 0.9)),
                "paper_count": attrs.get("paper_count", 0),
                "concepts": attrs.get("concepts", [])[:12],
                "color": "#0ea5e9",
            }
        )

    edges_payload: list[dict] = []
    for idx, (s, t, attrs) in enumerate(graph.edges(data=True), start=1):
        weight = float(attrs.get("weight", 1.0))
        edges_payload.append(
            {
                "id": f"e{idx}",
                "source": s,
                "target": t,
                "weight": weight,
                "size": max(0.8, min(4.0, 0.8 + weight * 0.5)),
                "color": "#94a3b8",
            }
        )

    payload = {"nodes": nodes_payload, "edges": edges_payload}
    payload_json = json.dumps(payload, ensure_ascii=False)

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>FieldMapper Concept Map</title>
  <style>
    html, body {{
      margin: 0;
      height: 100%;
      background: #0b1020;
      color: #e2e8f0;
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    #app {{
      display: grid;
      grid-template-columns: 1fr 320px;
      height: 100%;
    }}
    #sigma-container {{
      width: 100%;
      height: 100%;
      background: radial-gradient(circle at 20% 20%, #111827, #020617 70%);
    }}
    #panel {{
      border-left: 1px solid #1e293b;
      padding: 16px;
      overflow: auto;
      background: #0f172a;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 22px;
      color: #7dd3fc;
    }}
    .muted {{
      color: #94a3b8;
      font-size: 14px;
      margin-bottom: 14px;
    }}
    .label {{
      font-size: 15px;
      color: #cbd5e1;
      margin-top: 10px;
      font-weight: 600;
    }}
    .control {{
      margin-top: 8px;
      background: #111827;
      border: 1px solid #1f2937;
      border-radius: 8px;
      padding: 10px;
      font-size: 14px;
    }}
    input[type="range"] {{
      width: 100%;
      margin-top: 8px;
    }}
    .box {{
      margin-top: 6px;
      background: #111827;
      border: 1px solid #1f2937;
      border-radius: 8px;
      padding: 10px;
      font-size: 17px;
      line-height: 1.6;
      white-space: pre-wrap;
    }}
    #neighbor-list {{
      max-height: 220px;
      overflow: auto;
    }}
  </style>
</head>
<body>
  <div id="app">
    <div id="sigma-container"></div>
    <aside id="panel">
      <h1>Concept Map</h1>
      <div class="muted">Zoom, pan, and click nodes to inspect clusters.</div>
      <div class="label">Filter</div>
      <div class="control">
        <div>Min edge weight: <strong id="edge-weight-value">1</strong></div>
        <input id="edge-weight-slider" type="range" min="1" max="1" step="1" value="1" />
      </div>
      <div class="label">Node</div>
      <div id="node-name" class="box">Click a node</div>
      <div class="label">Details</div>
      <div id="node-detail" class="box">Paper count and representative concepts will appear here.</div>
      <div class="label">Connected Nodes</div>
      <div id="neighbor-list" class="box">Connected node labels will appear here.</div>
    </aside>
  </div>

  <script type="module">
    import Graph from "https://cdn.jsdelivr.net/npm/graphology@0.25.4/+esm";
    import {{ Sigma }} from "https://cdn.jsdelivr.net/npm/sigma@2.4.0/+esm";

    const payload = {payload_json};
    const graph = new Graph();

    payload.nodes.forEach((node) => graph.addNode(node.id, node));
    payload.edges.forEach((edge) => {{
      if (graph.hasNode(edge.source) && graph.hasNode(edge.target)) {{
        graph.addEdgeWithKey(edge.id, edge.source, edge.target, edge);
      }}
    }});

    const drawNodeLabel = (context, data, settings) => {{
      if (!data.label) return;
      // Skip base label while hovered to avoid double-drawn text.
      if (data.highlighted) return;
      const size = settings.labelSize || 16;
      const font = settings.labelFont || "ui-sans-serif, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif";
      const weight = settings.labelWeight || "600";
      context.font = `${{weight}} ${{size}}px ${{font}}`;
      context.textAlign = "left";
      context.textBaseline = "middle";
      const x = data.x + data.size + 6;
      const y = data.y;

      // Dark stroke behind light text keeps labels legible on dense edges.
      context.lineWidth = Math.max(2, size * 0.18);
      context.strokeStyle = "rgba(2, 6, 23, 0.95)";
      context.strokeText(data.label, x, y);

      context.fillStyle = data.labelColor || "#e5edf8";
      context.fillText(data.label, x, y);
    }};

    const drawNodeHover = (context, data, settings) => {{
      // Override Sigma's default hover label (white rectangle) with high-contrast text only.
      if (!data.label) return;
      const size = Math.max(16, settings.labelSize || 16);
      const font = settings.labelFont || "ui-sans-serif, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif";
      const weight = "700";
      context.font = `${{weight}} ${{size}}px ${{font}}`;
      context.textAlign = "left";
      context.textBaseline = "middle";
      const x = data.x + data.size + 8;
      const y = data.y;

      context.lineWidth = Math.max(2.5, size * 0.2);
      context.strokeStyle = "rgba(2, 6, 23, 0.98)";
      context.strokeText(data.label, x, y);

      context.fillStyle = data.labelColor || "#f59e0b";
      context.fillText(data.label, x, y);
    }};

    const renderer = new Sigma(graph, document.getElementById("sigma-container"), {{
      renderLabels: true,
      labelRenderedSizeThreshold: 0,
      labelDensity: 1,
      labelGridCellSize: 120,
      labelColor: {{ color: "#e2e8f0" }},
      labelRenderer: drawNodeLabel,
      hoverRenderer: drawNodeHover,
      defaultEdgeType: "line",
      minCameraRatio: 0.25,
      maxCameraRatio: 8,
      zIndex: true,
      nodeReducer: (node, attrs) => {{
        const showLabel = !!attrs.alwaysLabel || !!attrs.emphasisLabel;
        return {{
          ...attrs,
          label: showLabel ? (attrs.shortLabel || attrs.label) : undefined,
        }};
      }},
    }});

    const nodeName = document.getElementById("node-name");
    const nodeDetail = document.getElementById("node-detail");
    const neighborList = document.getElementById("neighbor-list");
    const slider = document.getElementById("edge-weight-slider");
    const sliderValue = document.getElementById("edge-weight-value");
    let selectedNode = null;
    let draggedNode = null;
    let isDragging = false;

    const BASE_NODE_COLOR = "#93c5fd";
    const MUTED_NODE_COLOR = "#334155";
    const SELECTED_NODE_COLOR = "#f59e0b";
    const NEIGHBOR_NODE_COLOR = "#22d3ee";
    const BASE_EDGE_COLOR = "#475569";
    const HIGHLIGHT_EDGE_COLOR = "#8b5cf6";
    const MUTED_EDGE_COLOR = "#1e293b";

    const edgeWeights = payload.edges.map((e) => Number(e.weight || 1));
    const maxEdgeWeight = Math.max(...edgeWeights, 1);
    slider.max = String(maxEdgeWeight);
    slider.value = "1";
    sliderValue.textContent = "1";

    const labelBudget = Math.max(24, Math.min(48, Math.floor(graph.order * 0.32)));
    const labelRank = graph
      .nodes()
      .map((node) => {{
        const attrs = graph.getNodeAttributes(node);
        const paperCount = Number(attrs.paper_count || 0);
        const degree = graph.degree(node) || 0;
        const score = paperCount * 10 + degree;
        return {{ node, score }};
      }})
      .sort((a, b) => b.score - a.score)
      .slice(0, labelBudget);
    const alwaysLabelNodes = new Set(labelRank.map((item) => item.node));

    function shortenLabel(text, maxLen = 34) {{
      const raw = String(text || "");
      if (raw.length <= maxLen) return raw;
      return raw.slice(0, maxLen - 1).trimEnd() + "…";
    }}

    graph.forEachNode((node, attrs) => {{
      graph.setNodeAttribute(node, "color", attrs.color || BASE_NODE_COLOR);
      graph.setNodeAttribute(node, "baseColor", attrs.color || BASE_NODE_COLOR);
      graph.setNodeAttribute(node, "baseSize", attrs.size || 10);
      graph.setNodeAttribute(node, "labelColor", "#e5edf8");
      graph.setNodeAttribute(node, "shortLabel", shortenLabel(attrs.label || node));
      graph.setNodeAttribute(node, "alwaysLabel", alwaysLabelNodes.has(node));
      graph.setNodeAttribute(node, "emphasisLabel", false);
    }});
    graph.forEachEdge((edge, attrs) => {{
      graph.setEdgeAttribute(edge, "color", attrs.color || BASE_EDGE_COLOR);
      graph.setEdgeAttribute(edge, "baseColor", attrs.color || BASE_EDGE_COLOR);
      graph.setEdgeAttribute(edge, "baseSize", attrs.size || 1.2);
    }});

    function hasVisibleEdge(nodeId) {{
      return graph.edges(nodeId).some((eid) => !graph.getEdgeAttribute(eid, "hidden"));
    }}

    function clearSelectionVisuals() {{
      graph.forEachNode((node, attrs) => {{
        if (graph.getNodeAttribute(node, "hidden")) return;
        graph.setNodeAttribute(node, "color", attrs.baseColor || BASE_NODE_COLOR);
        graph.setNodeAttribute(node, "size", attrs.baseSize || 10);
        graph.setNodeAttribute(node, "labelColor", "#e5edf8");
        graph.setNodeAttribute(node, "emphasisLabel", false);
      }});
      graph.forEachEdge((edge, attrs) => {{
        if (graph.getEdgeAttribute(edge, "hidden")) return;
        graph.setEdgeAttribute(edge, "color", attrs.baseColor || BASE_EDGE_COLOR);
        graph.setEdgeAttribute(edge, "size", attrs.baseSize || 1.2);
      }});
    }}

    function visibleNeighbors(nodeId) {{
      return graph.neighbors(nodeId).filter((nid) => {{
        if (graph.getNodeAttribute(nid, "hidden")) return false;
        const between = graph.edges(nodeId, nid);
        return between.some((eid) => !graph.getEdgeAttribute(eid, "hidden"));
      }});
    }}

    function applySelectionVisuals(nodeId) {{
      const neighbors = new Set(visibleNeighbors(nodeId));
      graph.forEachNode((node, attrs) => {{
        const hidden = graph.getNodeAttribute(node, "hidden");
        if (hidden) return;
        if (node === nodeId) {{
          graph.setNodeAttribute(node, "color", SELECTED_NODE_COLOR);
          graph.setNodeAttribute(node, "size", (attrs.baseSize || 10) * 1.35);
          graph.setNodeAttribute(node, "labelColor", "#f59e0b");
          graph.setNodeAttribute(node, "emphasisLabel", true);
        }} else if (neighbors.has(node)) {{
          graph.setNodeAttribute(node, "color", NEIGHBOR_NODE_COLOR);
          graph.setNodeAttribute(node, "size", (attrs.baseSize || 10) * 1.12);
          graph.setNodeAttribute(node, "labelColor", "#dbeafe");
          graph.setNodeAttribute(node, "emphasisLabel", true);
        }} else {{
          graph.setNodeAttribute(node, "color", MUTED_NODE_COLOR);
          graph.setNodeAttribute(node, "labelColor", "#94a3b8");
        }}
      }});
      graph.forEachEdge((edge, attrs, source, target) => {{
        const hidden = graph.getEdgeAttribute(edge, "hidden");
        if (hidden) return;
        if (source === nodeId || target === nodeId) {{
          graph.setEdgeAttribute(edge, "color", HIGHLIGHT_EDGE_COLOR);
          graph.setEdgeAttribute(edge, "size", Math.max(2.0, (attrs.baseSize || 1.2) * 1.8));
        }} else {{
          graph.setEdgeAttribute(edge, "color", MUTED_EDGE_COLOR);
        }}
      }});
    }}

    function setNodePanel(nodeId) {{
      const attrs = graph.getNodeAttributes(nodeId);
      nodeName.textContent = attrs.label || nodeId;
      const concepts = (attrs.concepts || []).slice(0, 10).join(", ");
      const neighbors = visibleNeighbors(nodeId).map((nid) => graph.getNodeAttribute(nid, "label") || nid);
      const neighborCount = neighbors.length;
      nodeDetail.textContent =
        "paper_count: " + attrs.paper_count +
        "\\nconnected_nodes: " + neighborCount +
        "\\nsummary: " + (concepts || "n/a");
      neighborList.textContent = neighbors.length ? neighbors.join("\\n") : "No visible connected nodes.";
    }}

    function applyEdgeFilter(minWeight) {{
      graph.forEachEdge((edge, attrs) => {{
        graph.setEdgeAttribute(edge, "hidden", Number(attrs.weight || 1) < minWeight);
      }});
      graph.forEachNode((node) => {{
        graph.setNodeAttribute(node, "hidden", !hasVisibleEdge(node));
      }});
      renderer.refresh();
    }}

    slider.addEventListener("input", (event) => {{
      const minWeight = Number(event.target.value || 1);
      sliderValue.textContent = String(minWeight);
      applyEdgeFilter(minWeight);
      if (selectedNode && graph.hasNode(selectedNode) && !graph.getNodeAttribute(selectedNode, "hidden")) {{
        setNodePanel(selectedNode);
        clearSelectionVisuals();
        applySelectionVisuals(selectedNode);
      }} else {{
        selectedNode = null;
        nodeName.textContent = "Click a node";
        nodeDetail.textContent = "Paper count and representative concepts will appear here.";
        neighborList.textContent = "Connected node labels will appear here.";
        clearSelectionVisuals();
      }}
      renderer.refresh();
    }});

    renderer.on("clickNode", (event) => {{
      const node = event.node;
      selectedNode = node;
      setNodePanel(node);
      clearSelectionVisuals();
      applySelectionVisuals(node);
      renderer.refresh();
    }});

    renderer.on("clickStage", () => {{
      selectedNode = null;
      nodeName.textContent = "Click a node";
      nodeDetail.textContent = "Paper count and representative concepts will appear here.";
      neighborList.textContent = "Connected node labels will appear here.";
      clearSelectionVisuals();
      renderer.refresh();
    }});

    renderer.on("downNode", (event) => {{
      isDragging = true;
      draggedNode = event.node;
      if (!renderer.getCustomBBox()) renderer.setCustomBBox(renderer.getBBox());
    }});

    renderer.on("moveBody", (payload) => {{
      if (!isDragging || !draggedNode) return;
      const event = payload && payload.event ? payload.event : payload;
      if (!event) return;
      const pos = renderer.viewportToGraph(event);
      graph.setNodeAttribute(draggedNode, "x", pos.x);
      graph.setNodeAttribute(draggedNode, "y", pos.y);
      if (event.preventSigmaDefault) event.preventSigmaDefault();
      if (event.original) {{
        event.original.preventDefault();
        event.original.stopPropagation();
      }}
    }});

    const handleUp = () => {{
      isDragging = false;
      draggedNode = null;
    }};
    renderer.on("upNode", handleUp);
    renderer.on("upStage", handleUp);

    applyEdgeFilter(1);

    window.addEventListener("beforeunload", () => {{
      renderer.kill();
    }});
  </script>
</body>
</html>
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
