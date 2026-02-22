from __future__ import annotations

import json
from pathlib import Path

import networkx as nx


_PALETTE: list[str] = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
    "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#a9cce3",
    "#3a86ff", "#fb5607", "#ff006e", "#8338ec", "#06d6a0",
    "#f72585", "#4cc9f0", "#7bf1a8", "#f8961e", "#43aa8b",
    "#90be6d", "#f9844a", "#277da1", "#577590", "#4d908e",
]

_CONCEPT_MAP_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>FieldMapper Concept Map</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; }
    html, body {
      margin: 0;
      height: 100%;
      background: #050b18;
      color: #e2e8f0;
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      overflow: hidden;
    }
    #app {
      display: flex;
      height: 100%;
    }
    #canvas-wrap {
      flex: 1;
      position: relative;
      min-width: 0;
    }
    svg#graph {
      width: 100%;
      height: 100%;
      display: block;
    }
    #hud {
      position: absolute;
      top: 12px;
      left: 12px;
      display: flex;
      align-items: center;
      gap: 8px;
      background: rgba(5,11,24,0.82);
      border: 1px solid #1e293b;
      border-radius: 20px;
      padding: 5px 12px;
      font-size: 12px;
      color: #64748b;
      pointer-events: none;
      backdrop-filter: blur(4px);
    }
    #hud-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #22c55e;
      animation: pulse 1s ease-in-out infinite;
    }
    #hud-dot.settled {
      background: #475569;
      animation: none;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.3; }
    }
    #zoom-btns {
      position: absolute;
      bottom: 20px;
      left: 16px;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .zoom-btn {
      width: 32px;
      height: 32px;
      background: rgba(15,23,42,0.85);
      border: 1px solid #334155;
      border-radius: 6px;
      color: #94a3b8;
      font-size: 18px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      user-select: none;
    }
    .zoom-btn:hover { background: #1e293b; color: #e2e8f0; }
    #panel {
      width: 300px;
      min-width: 300px;
      border-left: 1px solid #1e293b;
      padding: 16px;
      overflow: hidden;
      background: #0a1020;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    #legend-section {
      flex: 1;
      min-height: 0;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    h1 { margin: 0; font-size: 18px; color: #7dd3fc; }
    .panel-muted { font-size: 12px; color: #475569; margin-top: -4px; }
    .panel-label {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #475569;
      margin-bottom: 4px;
    }
    .panel-box {
      background: #0d1a2e;
      border: 1px solid #1e293b;
      border-radius: 8px;
      padding: 10px;
      font-size: 13px;
      line-height: 1.55;
      color: #cbd5e1;
      white-space: pre-wrap;
    }
    .panel-box.name {
      font-size: 15px;
      font-weight: 600;
      color: #e2e8f0;
      white-space: normal;
    }
    input[type="range"] {
      width: 100%;
      margin-top: 6px;
      accent-color: #3b82f6;
    }
    #legend-search {
      width: 100%;
      background: #0d1a2e;
      border: 1px solid #1e293b;
      border-radius: 6px;
      padding: 6px 10px;
      color: #e2e8f0;
      font-size: 12px;
      outline: none;
      box-sizing: border-box;
    }
    #legend-search:focus { border-color: #3b82f6; }
    #legend-search::placeholder { color: #475569; }
    #legend-list {
      flex: 1;
      min-height: 0;
      overflow-y: auto;
    }
    .legend-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 4px 6px;
      border-radius: 5px;
      cursor: pointer;
      font-size: 12px;
      line-height: 1.4;
    }
    .legend-item:hover { background: #1e293b; }
    .legend-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
    .legend-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #94a3b8; }
    #node-detail { max-height: 100px; overflow-y: auto; }
    #neighbor-list { max-height: 120px; overflow-y: auto; }
  </style>
</head>
<body>
<div id="app">
  <div id="canvas-wrap">
    <svg id="graph">
      <defs>
        <filter id="glow-normal" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="5" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <filter id="glow-strong" x="-100%" y="-100%" width="300%" height="300%">
          <feGaussianBlur stdDeviation="10" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>
      <rect id="bg-rect" width="100%" height="100%" fill="#050b18"/>
      <g id="zoom-g">
        <g id="edges-g"/>
        <g id="nodes-g"/>
        <g id="labels-g"/>
      </g>
    </svg>
    <div id="hud">
      <div id="hud-dot"></div>
      <span id="hud-text">Simulating\u2026</span>
    </div>
    <div id="zoom-btns">
      <button class="zoom-btn" id="zoom-in">+</button>
      <button class="zoom-btn" id="zoom-out">&#8722;</button>
      <button class="zoom-btn" id="zoom-reset" style="font-size:13px;" title="Fit all nodes">&#8285;</button>
    </div>
  </div>
  <aside id="panel">
    <h1>Concept Map</h1>
    <p class="panel-muted">Click nodes to inspect. Drag to reposition.</p>
    <div>
      <div class="panel-label">Min edge weight</div>
      <div class="panel-box">
        <span id="edge-weight-value">1</span>
        <input id="edge-weight-slider" type="range" min="1" max="1" step="1" value="1"/>
      </div>
    </div>
    <div>
      <div class="panel-label">Selected node</div>
      <div id="node-name" class="panel-box name">Click a node</div>
    </div>
    <div>
      <div class="panel-label">Details</div>
      <div id="node-detail" class="panel-box">Paper count and concepts will appear here.</div>
    </div>
    <div>
      <div class="panel-label">Connected nodes</div>
      <div id="neighbor-list" class="panel-box">Connected nodes will appear here.</div>
    </div>
    <div id="legend-section">
      <div class="panel-label">Legend</div>
      <input id="legend-search" type="search" placeholder="Filter nodes\u2026" autocomplete="off" />
      <div id="legend-list" class="panel-box" style="padding:6px;"></div>
    </div>
  </aside>
</div>

<script type="module">
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7/+esm";

const raw = __PAYLOAD_JSON__;
const nodes = raw.nodes.map(n => ({...n}));
const links = raw.edges.map(e => ({
  id: e.id, source: e.source, target: e.target, weight: e.weight,
}));
const nodeById = new Map(nodes.map(n => [n.id, n]));
const maxWeight = d3.max(links, d => d.weight) || 1;

// --- SVG setup ---
const svg = d3.select("#graph");
const zoomG = svg.select("#zoom-g");
const edgesG = zoomG.select("#edges-g");
const nodesG = zoomG.select("#nodes-g");
const labelsG = zoomG.select("#labels-g");

// Dynamic label visibility: show label when node's screen radius >= threshold px
let currentK = 1;
const LABEL_MIN_SCREEN_R = 6; // px

function updateLabelVisibility() {
  labelSel.attr("display", d => {
    if (hiddenNodes.has(d.id)) return "none";
    if (selectedId) return null;  // selection mode: show all non-hidden labels
    return d.r * currentK >= LABEL_MIN_SCREEN_R ? null : "none";
  });
}

// --- Force simulation ---
const simulation = d3.forceSimulation(nodes)
  .alphaDecay(0.013)
  .velocityDecay(0.36)
  .force("link", d3.forceLink(links)
    .id(d => d.id)
    .distance(d => 50 + 100 * (1 - d.weight / maxWeight))
    .strength(d => 0.2 + 0.6 * (d.weight / maxWeight))
  )
  .force("charge", d3.forceManyBody().strength(d => -100 - d.r * 8))
  .force("center", d3.forceCenter(0, 0).strength(0.04))
  .force("collide", d3.forceCollide(d => d.r + 8));

// --- Edges ---
const edgeSel = edgesG.selectAll("line")
  .data(links)
  .join("line")
    .attr("stroke", "#162840")
    .attr("stroke-opacity", 0.6)
    .attr("stroke-width", d => Math.max(0.6, Math.min(3.5, 0.6 + d.weight * 0.25)));

// --- Nodes ---
let wasDragged = false;
const nodeSel = nodesG.selectAll("circle")
  .data(nodes)
  .join("circle")
    .attr("r", d => d.r)
    .attr("fill", d => d.color)
    .attr("fill-opacity", 0.88)
    .attr("stroke", d => {
      const c = d3.color(d.color);
      return c ? c.brighter(0.6).formatHex() : "#ffffff";
    })
    .attr("stroke-width", 1.2)
    .style("cursor", "pointer")
    .call(d3.drag()
      .on("start", (event, d) => {
        wasDragged = false;
        if (!event.active) simulation.alphaTarget(0.25).restart();
        d.fx = d.x; d.fy = d.y;
        document.getElementById("hud-dot").classList.remove("settled");
        document.getElementById("hud-text").textContent = "Simulating\u2026";
      })
      .on("drag", (event, d) => {
        wasDragged = true;
        d.fx = event.x; d.fy = event.y;
      })
      .on("end", (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null; d.fy = null;
      })
    )
    .on("click", (event, d) => {
      event.stopPropagation();
      if (wasDragged) { wasDragged = false; return; }
      if (hiddenNodes.has(d.id)) return;
      selectNode(d);
    })
    .on("mouseover", (event, d) => {
      if (selectedId || hiddenNodes.has(d.id)) return;
      d3.select(event.currentTarget).attr("filter", "url(#glow-normal)");
    })
    .on("mouseout", (event) => {
      if (selectedId) return;
      d3.select(event.currentTarget).attr("filter", null);
    });

// --- Labels (all nodes; visibility managed dynamically by zoom) ---
const labelSel = labelsG.selectAll("text")
  .data(nodes)
  .join("text")
    .attr("font-size", 11)
    .attr("font-weight", "600")
    .attr("fill", "#c8d6e8")
    .attr("stroke", "#050b18")
    .attr("stroke-width", 2.8)
    .attr("paint-order", "stroke")
    .style("pointer-events", "none")
    .style("user-select", "none")
    .text(d => d.label.length > 30 ? d.label.slice(0, 29) + "\u2026" : d.label);

// --- Tick ---
simulation.on("tick", () => {
  edgeSel
    .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
    .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
  nodeSel.attr("cx", d => d.x).attr("cy", d => d.y);
  labelSel.attr("x", d => d.x + d.r + 5).attr("y", d => d.y + 4);
});

simulation.on("end", () => {
  document.getElementById("hud-dot").classList.add("settled");
  document.getElementById("hud-text").textContent = "Settled";
  if (!userHasZoomed) fitGraph();
});

// --- Zoom ---
let userHasZoomed = false;
const zoom = d3.zoom()
  .scaleExtent([0.05, 12])
  .on("zoom", e => {
    zoomG.attr("transform", e.transform);
    currentK = e.transform.k;
    if (e.sourceEvent) userHasZoomed = true;
    updateLabelVisibility();
  });
svg.call(zoom);

d3.select("#bg-rect").on("click", clearSelection);

function fitGraph() {
  const svgEl = svg.node();
  const w = svgEl.clientWidth, h = svgEl.clientHeight;
  if (!w || !h || !nodes.length) return;
  const xs = nodes.map(n => n.x), ys = nodes.map(n => n.y);
  const x0 = d3.min(xs) - 50, x1 = d3.max(xs) + 50;
  const y0 = d3.min(ys) - 50, y1 = d3.max(ys) + 50;
  const bw = x1 - x0 || 1, bh = y1 - y0 || 1;
  const scale = Math.min(0.92, w / bw, h / bh);
  const tx = w / 2 - scale * (x0 + x1) / 2;
  const ty = h / 2 - scale * (y0 + y1) / 2;
  svg.transition().duration(750)
    .call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
}

document.getElementById("zoom-in").onclick = () =>
  svg.transition().duration(280).call(zoom.scaleBy, 1.45);
document.getElementById("zoom-out").onclick = () =>
  svg.transition().duration(280).call(zoom.scaleBy, 1 / 1.45);
document.getElementById("zoom-reset").onclick = () => { userHasZoomed = false; fitGraph(); };

// --- Selection state ---
let selectedId = null;
const hiddenEdges = new Set();
const hiddenNodes = new Set();

function clearSelection() {
  selectedId = null;
  nodeSel
    .attr("fill-opacity", n => hiddenNodes.has(n.id) ? 0 : 0.88)
    .attr("filter", null)
    .attr("display", n => hiddenNodes.has(n.id) ? "none" : null);
  edgeSel
    .attr("display", l => hiddenEdges.has(l.id) ? "none" : null)
    .attr("stroke", "#162840")
    .attr("stroke-opacity", 0.6);
  labelSel.attr("fill", "#c8d6e8");
  updateLabelVisibility();
  document.getElementById("node-name").textContent = "Click a node";
  document.getElementById("node-detail").textContent = "Paper count and concepts will appear here.";
  document.getElementById("neighbor-list").textContent = "Connected nodes will appear here.";
}

function selectNode(d) {
  selectedId = d.id;
  const neighborIds = new Set();
  links.forEach(l => {
    if (hiddenEdges.has(l.id)) return;
    const sid = l.source.id !== undefined ? l.source.id : l.source;
    const tid = l.target.id !== undefined ? l.target.id : l.target;
    if (sid === d.id) neighborIds.add(tid);
    else if (tid === d.id) neighborIds.add(sid);
  });

  nodeSel
    .attr("fill-opacity", nd =>
      hiddenNodes.has(nd.id) ? 0 :
      nd.id === d.id || neighborIds.has(nd.id) ? 0.96 : 0.10
    )
    .attr("filter", nd =>
      nd.id === d.id ? "url(#glow-strong)" :
      neighborIds.has(nd.id) ? "url(#glow-normal)" : null
    )
    .attr("display", nd => hiddenNodes.has(nd.id) ? "none" : null);

  edgeSel
    .attr("display", l => hiddenEdges.has(l.id) ? "none" : null)
    .attr("stroke", l => {
      if (hiddenEdges.has(l.id)) return "#162840";
      const sid = l.source.id !== undefined ? l.source.id : l.source;
      const tid = l.target.id !== undefined ? l.target.id : l.target;
      return (sid === d.id || tid === d.id) ? "#8b5cf6" : "#162840";
    })
    .attr("stroke-opacity", l => {
      if (hiddenEdges.has(l.id)) return 0;
      const sid = l.source.id !== undefined ? l.source.id : l.source;
      const tid = l.target.id !== undefined ? l.target.id : l.target;
      return (sid === d.id || tid === d.id) ? 0.9 : 0.05;
    });

  labelSel.attr("fill", nd =>
    nd.id === d.id || neighborIds.has(nd.id) ? "#f0f9ff" : "#2d3f55"
  );
  updateLabelVisibility();

  document.getElementById("node-name").textContent = d.label;
  document.getElementById("node-detail").textContent =
    "paper_count: " + d.paper_count +
    "\\nconnected: " + neighborIds.size +
    "\\nconcepts: " + ((d.concepts || []).slice(0, 10).join(", ") || "n/a");
  document.getElementById("neighbor-list").textContent =
    [...neighborIds].map(id => nodeById.get(id)?.label || id).join("\\n") ||
    "No connected nodes above threshold.";
}

// --- Edge weight filter ---
const slider = document.getElementById("edge-weight-slider");
const sliderVal = document.getElementById("edge-weight-value");
const allMaxW = d3.max(links, l => l.weight) || 1;
slider.max = String(allMaxW);

slider.addEventListener("input", e => {
  const minW = Number(e.target.value);
  sliderVal.textContent = String(minW);
  hiddenEdges.clear();
  hiddenNodes.clear();
  links.forEach(l => { if (l.weight < minW) hiddenEdges.add(l.id); });
  if (links.length) {
    nodes.forEach(n => {
      const vis = links.some(l => {
        if (hiddenEdges.has(l.id)) return false;
        const sid = l.source.id !== undefined ? l.source.id : l.source;
        const tid = l.target.id !== undefined ? l.target.id : l.target;
        return sid === n.id || tid === n.id;
      });
      if (!vis) hiddenNodes.add(n.id);
    });
  }
  edgeSel.attr("display", l => hiddenEdges.has(l.id) ? "none" : null);
  nodeSel.attr("display", n => hiddenNodes.has(n.id) ? "none" : null);
  if (selectedId && hiddenNodes.has(selectedId)) {
    clearSelection();
  } else if (selectedId) {
    const nd = nodeById.get(selectedId);
    if (nd) selectNode(nd);
  } else {
    updateLabelVisibility();
  }
});

// --- Legend (all nodes, searchable) ---
const legendList = document.getElementById("legend-list");
const legendSearch = document.getElementById("legend-search");
const sortedNodes = [...nodes].sort((a, b) => b.paper_count - a.paper_count);

sortedNodes.forEach(n => {
  const item = document.createElement("div");
  item.className = "legend-item";
  item.title = n.label;
  item.dataset.label = n.label.toLowerCase();
  const dot = document.createElement("div");
  dot.className = "legend-dot";
  dot.style.background = n.color;
  const txt = document.createElement("div");
  txt.className = "legend-text";
  txt.textContent = n.label;
  item.append(dot, txt);
  item.addEventListener("click", () => {
    const svgEl = svg.node();
    const scale = 2.2;
    const tx = svgEl.clientWidth / 2 - scale * (n.x || 0);
    const ty = svgEl.clientHeight / 2 - scale * (n.y || 0);
    svg.transition().duration(600)
      .call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
    if (!hiddenNodes.has(n.id)) selectNode(n);
  });
  legendList.appendChild(item);
});

legendSearch.addEventListener("input", () => {
  const q = legendSearch.value.trim().toLowerCase();
  legendList.querySelectorAll(".legend-item").forEach(item => {
    item.style.display = q && !item.dataset.label.includes(q) ? "none" : "";
  });
});

// --- ResizeObserver: update center force on panel resize ---
new ResizeObserver(() => {
  simulation.force("center", d3.forceCenter(0, 0).strength(0.04));
}).observe(document.getElementById("canvas-wrap"));

// Initial label visibility pass (before first zoom event fires)
updateLabelVisibility();
</script>
</body>
</html>"""


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
    nodes_payload: list[dict] = []
    for i, c in enumerate(clusters):
        color = _PALETTE[i % len(_PALETTE)]
        paper_count = int(c.get("paper_count", 1))
        nodes_payload.append(
            {
                "id": str(c["cluster_id"]),
                "label": c["representative_label"],
                "r": max(8.0, min(30.0, 8.0 + paper_count * 1.4)),
                "paper_count": paper_count,
                "concepts": c.get("concepts", [])[:12],
                "color": color,
            }
        )

    seen_pairs: set[tuple[str, str]] = set()
    edges_payload: list[dict] = []
    for idx, edge in enumerate(edges, start=1):
        source = str(edge["source"])
        target = str(edge["target"])
        if source == target:
            continue
        pair: tuple[str, str] = (min(source, target), max(source, target))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        edges_payload.append(
            {
                "id": f"e{idx}",
                "source": source,
                "target": target,
                "weight": int(edge.get("weight", 1)),
            }
        )

    payload = {"nodes": nodes_payload, "edges": edges_payload}
    payload_json = json.dumps(payload, ensure_ascii=False)

    html = _CONCEPT_MAP_HTML_TEMPLATE.replace("__PAYLOAD_JSON__", payload_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
