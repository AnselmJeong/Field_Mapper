from __future__ import annotations

from collections import defaultdict

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


def _connected_components(num_nodes: int, edges: list[tuple[int, int]]) -> list[list[int]]:
    adj: dict[int, list[int]] = {i: [] for i in range(num_nodes)}
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)

    visited = set()
    components: list[list[int]] = []

    for node in range(num_nodes):
        if node in visited:
            continue
        stack = [node]
        comp: list[int] = []
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            comp.append(cur)
            stack.extend(adj[cur])
        components.append(comp)

    return components


def cluster_concepts(embedded_rows: list[dict], similarity_threshold: float = 0.82) -> list[dict]:
    if not embedded_rows:
        return []

    matrix = np.array([row["embedding"] for row in embedded_rows], dtype=float)
    sim = cosine_similarity(matrix)

    edges: list[tuple[int, int]] = []
    n = len(embedded_rows)
    for i in range(n):
        for j in range(i + 1, n):
            if sim[i, j] >= similarity_threshold:
                edges.append((i, j))

    components = _connected_components(n, edges)

    clusters: list[dict] = []
    for idx, comp in enumerate(components, start=1):
        concepts = [embedded_rows[i]["concept"] for i in comp]
        paper_ids = {embedded_rows[i]["paper_id"] for i in comp}
        label = sorted(concepts, key=len)[0] if concepts else f"Cluster {idx}"
        clusters.append(
            {
                "cluster_id": idx,
                "representative_label": label,
                "concepts": sorted(set(concepts)),
                "paper_count": len(paper_ids),
                "paper_ids": sorted(paper_ids),
            }
        )

    clusters.sort(key=lambda c: c["paper_count"], reverse=True)
    for new_idx, cluster in enumerate(clusters, start=1):
        cluster["cluster_id"] = new_idx
    return clusters


def build_cooccurrence_edges(clusters: list[dict]) -> list[dict]:
    paper_to_clusters: dict[str, list[int]] = defaultdict(list)
    for cluster in clusters:
        cid = int(cluster["cluster_id"])
        for paper_id in cluster.get("paper_ids", []):
            paper_to_clusters[paper_id].append(cid)

    edge_weights: dict[tuple[int, int], int] = defaultdict(int)
    for ids in paper_to_clusters.values():
        unique_ids = sorted(set(ids))
        for i in range(len(unique_ids)):
            for j in range(i + 1, len(unique_ids)):
                edge_weights[(unique_ids[i], unique_ids[j])] += 1

    return [
        {"source": s, "target": t, "weight": w}
        for (s, t), w in sorted(edge_weights.items(), key=lambda item: item[1], reverse=True)
    ]
