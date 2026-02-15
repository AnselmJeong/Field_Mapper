from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from typing import Any

from fieldmapper.extraction.ollama_client import OllamaClient
from fieldmapper.extraction.prompts import (
    SECTION_SYNTHESIS_SYSTEM_PROMPT,
    SECTION_SYNTHESIS_USER_TEMPLATE,
)

LOGGER = logging.getLogger(__name__)

SECTION_SPECS: list[tuple[str, str]] = [
    ("executive_overview", "Executive Overview"),
    ("concept_taxonomy", "Concept Taxonomy"),
    ("major_theoretical_models", "Major Theoretical Models"),
    ("methodological_landscape", "Methodological Landscape"),
    ("controversies", "Controversies"),
    ("research_trajectory", "Research Trajectory"),
    ("open_problems", "Open Problems"),
]


def _compact_papers(papers: list[dict], limit: int = 50) -> list[dict]:
    compact: list[dict] = []
    for paper in papers[:limit]:
        compact.append(
            {
                "paper_id": paper.get("paper_id", ""),
                "title": paper.get("title", ""),
                "year": paper.get("year", ""),
                "paper_type": paper.get("paper_type", ""),
                "core_problem": paper.get("core_problem", ""),
                "main_claim": paper.get("main_claim", ""),
                "limitations": paper.get("limitations", ""),
                "key_concepts": list(paper.get("key_concepts", []))[:8],
                "theoretical_framework": list(paper.get("theoretical_framework", []))[:6],
                "method_category": list(paper.get("method_category", []))[:6],
            }
        )
    return compact


def _compact_clusters(clusters: list[dict], limit: int = 40) -> list[dict]:
    compact: list[dict] = []
    for cluster in clusters[:limit]:
        compact.append(
            {
                "cluster_id": cluster.get("cluster_id", ""),
                "representative_label": cluster.get("representative_label", ""),
                "paper_count": cluster.get("paper_count", 0),
                "concepts": list(cluster.get("concepts", []))[:10],
                "paper_ids": list(cluster.get("paper_ids", []))[:12],
            }
        )
    return compact


def _top_counts(items: list[str], top_n: int) -> list[dict[str, Any]]:
    counter = Counter(x for x in items if x)
    return [{"name": name, "count": count} for name, count in counter.most_common(top_n)]


def _build_evidence_index(papers: list[dict], clusters: list[dict]) -> dict[str, Any]:
    papers_compact = _compact_papers(papers)
    clusters_compact = _compact_clusters(clusters)

    theories: list[str] = []
    methods: list[str] = []
    limitations: list[str] = []
    yearly: dict[str, int] = defaultdict(int)

    for paper in papers_compact:
        theories.extend(str(x).strip() for x in paper.get("theoretical_framework", []) if str(x).strip())
        methods.extend(str(x).strip() for x in paper.get("method_category", []) if str(x).strip())
        limitation = str(paper.get("limitations", "")).strip()
        if limitation:
            limitations.append(limitation)
        year = str(paper.get("year", "")).strip()
        if year:
            yearly[year] += 1

    timeline = [{"year": y, "paper_count": c} for y, c in sorted(yearly.items())]

    return {
        "meta": {
            "paper_count": len(papers),
            "cluster_count": len(clusters),
        },
        "top_theories": _top_counts(theories, top_n=20),
        "top_methods": _top_counts(methods, top_n=20),
        "common_limitations": limitations[:20],
        "timeline": timeline,
        "papers": papers_compact,
        "clusters": clusters_compact,
    }


def _section_evidence(section_key: str, evidence: dict[str, Any]) -> dict[str, Any]:
    base = {
        "meta": evidence.get("meta", {}),
        "top_theories": evidence.get("top_theories", []),
        "top_methods": evidence.get("top_methods", []),
        "timeline": evidence.get("timeline", []),
    }
    if section_key == "concept_taxonomy":
        base["clusters"] = evidence.get("clusters", [])
        base["papers"] = evidence.get("papers", [])[:20]
    elif section_key == "major_theoretical_models":
        base["papers"] = evidence.get("papers", [])
        base["common_limitations"] = evidence.get("common_limitations", [])
    elif section_key == "methodological_landscape":
        base["papers"] = evidence.get("papers", [])[:28]
        base["common_limitations"] = evidence.get("common_limitations", [])
    elif section_key == "controversies":
        base["papers"] = evidence.get("papers", [])
        base["common_limitations"] = evidence.get("common_limitations", [])
    elif section_key == "research_trajectory":
        base["papers"] = evidence.get("papers", [])
        base["clusters"] = evidence.get("clusters", [])[:20]
    elif section_key == "open_problems":
        base["papers"] = evidence.get("papers", [])[:28]
        base["common_limitations"] = evidence.get("common_limitations", [])
    else:
        base["papers"] = evidence.get("papers", [])[:28]
        base["clusters"] = evidence.get("clusters", [])[:20]
    return base


def _fallback_section(section_key: str, evidence: dict[str, Any]) -> str:
    meta = evidence.get("meta", {})
    top_theories = evidence.get("top_theories", [])
    top_methods = evidence.get("top_methods", [])
    common_limitations = evidence.get("common_limitations", [])
    timeline = evidence.get("timeline", [])
    papers = evidence.get("papers", [])

    theory_text = ", ".join(t["name"] for t in top_theories[:8]) or "No dominant theory labels extracted"
    method_text = ", ".join(m["name"] for m in top_methods[:8]) or "No dominant method labels extracted"
    years = ", ".join(f"{x['year']}({x['paper_count']})" for x in timeline[:10]) or "No year metadata"
    sample_limitations = " | ".join(common_limitations[:3]) or "No explicit limitations extracted"
    sample_claims = " | ".join(str(p.get("main_claim", "")).strip() for p in papers[:3] if str(p.get("main_claim", "")).strip())
    sample_claims = sample_claims or "No strong main-claim snippets extracted"

    return (
        f"This section was generated from extracted evidence without full narrative synthesis. "
        f"Corpus size: {meta.get('paper_count', 0)} papers and {meta.get('cluster_count', 0)} clusters. "
        f"Frequent theory labels include {theory_text}. Frequent methods include {method_text}. "
        f"Observed timeline density by year: {years}. Representative claims: {sample_claims}. "
        f"Common stated limitations include: {sample_limitations}. "
        "These constraints should be interpreted as unresolved targets for the next synthesis pass."
    )


def _generate_section(
    section_key: str,
    section_name: str,
    evidence: dict[str, Any],
    llm_model: str,
    client: OllamaClient,
) -> str:
    prompt = SECTION_SYNTHESIS_USER_TEMPLATE.format(
        section_name=section_name,
        section_key=section_key,
        evidence_json=json.dumps(_section_evidence(section_key, evidence), ensure_ascii=False),
    )

    try:
        text = client.chat(
            model=llm_model,
            system=SECTION_SYNTHESIS_SYSTEM_PROMPT,
            user=prompt,
            temperature=0.2,
            timeout=1800,
        ).strip()
        if text:
            return text
    except Exception as exc:
        LOGGER.warning("Section synthesis failed for %s: %s: %s", section_key, type(exc).__name__, exc)
    return _fallback_section(section_key, evidence)


def synthesize_field_report(
    papers: list[dict],
    clusters: list[dict],
    llm_model: str,
    client: OllamaClient,
) -> dict[str, Any]:
    evidence = _build_evidence_index(papers, clusters)
    payload: dict[str, Any] = {}
    for key, name in SECTION_SPECS:
        payload[key] = _generate_section(
            section_key=key,
            section_name=name,
            evidence=evidence,
            llm_model=llm_model,
            client=client,
        )
    return payload
