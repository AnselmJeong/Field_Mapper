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
    ("field_landscape", "Field Landscape"),
    ("conceptual_architecture", "Conceptual Architecture"),
    ("theory_genealogy_section", "Theory Genealogy"),
    ("major_theoretical_models", "Major Theoretical Models"),
    ("methodological_landscape", "Methodological Landscape"),
    ("theoretical_fault_lines", "Theoretical Fault Lines"),
    ("research_trajectory", "Research Trajectory"),
    ("open_problems", "Open Problems"),
]

# Per-section instructions passed into the prompt template
SECTION_INSTRUCTIONS: dict[str, str] = {
    "field_landscape": (
        "Explain why this scientific field exists as a distinct discipline. "
        "What specific phenomenon or empirical observation could NOT be explained by theories that preceded this field? "
        "Describe the intellectual void — the precise gap — that this field was created to fill. "
        "State the core field-defining question as one precise question, not a list. "
        "Explain the historical and intellectual conditions that made this field possible. "
        "Do NOT summarize what the field found. Focus entirely on the foundational problem. "
        "Do NOT enumerate all theories — focus on the problem space and why it was compelling. "
        "Target: 1200-1800 words."
    ),
    "conceptual_architecture": (
        "Organize the core concepts of this field by their epistemic role into four categories: "
        "(1) Explanatory primitives — fundamental concepts that serve as the building blocks of theoretical explanations; "
        "(2) Mechanism variables — concepts describing causal processes linking primitives to outcomes; "
        "(3) Measurement/operational proxies — observable quantities used as stand-ins for theoretical constructs; "
        "(4) Outcome/phenotype-level constructs — what the field ultimately aims to explain. "
        "For each category, name 3-5 concepts and explain WHY they belong in that role. "
        "Then describe how these categories interact causally — how measurement proxies constrain mechanism claims, "
        "how explanatory primitives limit what outcomes can be explained, etc. "
        "This is NOT a glossary. Every concept must be placed in a causal role and connected to at least one other concept. "
        "Target: 1200-1800 words."
    ),
    "theory_genealogy_section": (
        "Reconstruct the causal history of theoretical development in this field using the genealogy data provided. "
        "For each major theoretical transition, cover: "
        "(a) The predecessor theory and its central mechanism; "
        "(b) The specific empirical anomaly or logical contradiction that the predecessor could not resolve; "
        "(c) The successor theory and exactly what mechanistic innovation it introduced; "
        "(d) What empirical finding or methodological advance validated the transition. "
        "Use the structure: THEORY A [limitation: X] → THEORY B [enabled by: Y] → THEORY C ... "
        "Do NOT produce a chronological summary. Produce a causal narrative of intellectual necessity. "
        "Use (Author, Year) citations for each transition. "
        "Target: 2000-3500 words."
    ),
    "major_theoretical_models": (
        "For each of the 4-6 most important theoretical models identified in the theory units, "
        "provide a complete intellectual reconstruction. Cover ALL of these points per theory: "
        "(1) Origin problem: What specific gap or anomaly prompted this theory? "
        "(2) Core mechanism: What exactly does this theory claim happens, step by step mechanistically? "
        "(3) Novel explanatory gain: What could this theory explain that its predecessors could not? "
        "(4) Key supporting evidence: Which specific experiments or findings were decisive? "
        "(5) Main criticisms: What are the most substantive objections, and who raised them? "
        "(6) Evolution: How was this theory modified in response to criticisms? "
        "(7) Current status: Is it dominant, contested, partially superseded, or integrated into a broader model? "
        "Write 400-700 words per theory in analytical prose (not bullet points). "
        "Target: 2500-4000 words total."
    ),
    "methodological_landscape": (
        "Analyze how specific methods enabled or constrained specific theoretical claims. "
        "For each major method: "
        "(a) What aspect of the phenomenon can this method measure and what can it NOT measure? "
        "(b) Which theoretical claims depend critically on this method's results? "
        "(c) What inferential limitations create theoretical blind spots? "
        "(d) Has this method's limitation caused or prolonged a theoretical dispute? "
        "Then analyze HOW specific methodological advances changed the theoretical landscape: "
        "when a new method became available, which previously untestable claims became testable, "
        "and what happened to the field as a result? "
        "Do NOT simply list methods with descriptions. "
        "Analyze the method-theory relationship and show how methods shape what theories are even possible. "
        "Target: 1500-2500 words."
    ),
    "theoretical_fault_lines": (
        "Identify 3-5 active, substantive theoretical disputes in this field. "
        "For each dispute: "
        "(a) State Claim A and Claim B precisely — not 'there is debate about X' but the actual competing claims; "
        "(b) Identify what specific data or findings each side relies on; "
        "(c) Explain exactly where the two interpretations diverge — "
        "is it about mechanism, measurement validity, scope, or theoretical assumptions? "
        "(d) Specify what evidence or experimental design would definitively adjudicate the dispute. "
        "Do NOT write 'there is controversy' or 'researchers disagree.' "
        "Write about WHAT exactly is disputed, WHY it has not been resolved, "
        "and what would resolve it. "
        "Target: 1500-2500 words."
    ),
    "research_trajectory": (
        "Describe where this field has been going and where it is now heading. "
        "Do NOT repeat the genealogy — focus on present trajectories and future directions, not historical transitions. "
        "Identify 3-5 current research frontiers using specific evidence from the corpus papers. "
        "For each frontier: "
        "(a) Explain what earlier theoretical or empirical work opened this direction; "
        "(b) Describe what new questions have emerged that did not exist before; "
        "(c) Identify what technical, conceptual, or empirical obstacles remain. "
        "Conclude by synthesizing: what kind of field is this becoming, "
        "and what does resolution of the remaining questions require? "
        "Target: 1500-2000 words."
    ),
    "open_problems": (
        "Define 4-6 unresolved mechanistic questions precisely. "
        "For each open problem: "
        "(a) State exactly what is unknown — not 'more research is needed' "
        "but 'the mechanism connecting X to Y is unknown'; "
        "(b) Explain why existing theories fail to answer it — "
        "what specific mechanism is missing, wrong, or untested; "
        "(c) Describe what decisive empirical test, if conducted and successful, would resolve it. "
        "These must be mechanistic gaps, not data-collection gaps. "
        "The problems must be substantively different from the disputes identified in Theoretical Fault Lines. "
        "Target: 1500-2500 words."
    ),
}

SECTION_WORD_TARGETS: dict[str, str] = {
    "field_landscape": "1200-1800 words",
    "conceptual_architecture": "1200-1800 words",
    "theory_genealogy_section": "2000-3500 words",
    "major_theoretical_models": "2500-4000 words",
    "methodological_landscape": "1500-2500 words",
    "theoretical_fault_lines": "1500-2500 words",
    "research_trajectory": "1500-2000 words",
    "open_problems": "1500-2500 words",
}


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


def _compact_theory_units_for_section(theory_units: list[dict], section_key: str) -> list[dict]:
    """Return a section-appropriate subset of theory unit fields to avoid token bloat."""
    if not theory_units:
        return []

    if section_key == "major_theoretical_models":
        # Full detail
        return theory_units

    if section_key in ("theory_genealogy_section", "research_trajectory"):
        return [
            {
                "theory_id": u.get("theory_id", ""),
                "name": u.get("name", ""),
                "origin_problem": u.get("origin_problem", ""),
                "predecessor_theories": u.get("predecessor_theories", []),
                "successor_or_revision": u.get("successor_or_revision", ""),
                "current_status": u.get("current_status", ""),
                "paper_anchors": u.get("paper_anchors", [])[:4],
                "key_evidence": u.get("key_evidence", [])[:3],
            }
            for u in theory_units
        ]

    if section_key == "theoretical_fault_lines":
        return [
            {
                "theory_id": u.get("theory_id", ""),
                "name": u.get("name", ""),
                "main_criticisms": u.get("main_criticisms", []),
                "current_status": u.get("current_status", ""),
                "paper_anchors": u.get("paper_anchors", [])[:4],
            }
            for u in theory_units
        ]

    if section_key == "open_problems":
        return [
            {
                "theory_id": u.get("theory_id", ""),
                "name": u.get("name", ""),
                "main_criticisms": u.get("main_criticisms", []),
                "successor_or_revision": u.get("successor_or_revision", ""),
                "current_status": u.get("current_status", ""),
            }
            for u in theory_units
        ]

    if section_key == "conceptual_architecture":
        return [
            {
                "theory_id": u.get("theory_id", ""),
                "name": u.get("name", ""),
                "core_mechanism": u.get("core_mechanism", ""),
                "cluster_ids": u.get("cluster_ids", []),
            }
            for u in theory_units
        ]

    # field_landscape and methodological_landscape: brief overview
    return [
        {
            "theory_id": u.get("theory_id", ""),
            "name": u.get("name", ""),
            "current_status": u.get("current_status", ""),
        }
        for u in theory_units
    ]


def _genealogy_excerpt_for_section(theory_genealogy: dict, section_key: str) -> str:
    """Return a section-appropriate excerpt of the genealogy data."""
    if not theory_genealogy:
        return "No genealogy data available."

    if section_key == "theory_genealogy_section":
        narrative = theory_genealogy.get("narrative", "")
        chains = theory_genealogy.get("causal_chains", [])
        shifts = theory_genealogy.get("dominant_paradigm_shifts", [])
        return json.dumps(
            {"narrative": narrative[:6000], "causal_chains": chains, "dominant_paradigm_shifts": shifts},
            ensure_ascii=False,
        )

    if section_key in ("research_trajectory", "theoretical_fault_lines"):
        chains = theory_genealogy.get("causal_chains", [])
        shifts = theory_genealogy.get("dominant_paradigm_shifts", [])
        return json.dumps({"causal_chains": chains, "dominant_paradigm_shifts": shifts}, ensure_ascii=False)

    if section_key == "field_landscape":
        shifts = theory_genealogy.get("dominant_paradigm_shifts", [])
        narrative_head = theory_genealogy.get("narrative", "")[:800]
        return json.dumps({"dominant_paradigm_shifts": shifts, "narrative_intro": narrative_head}, ensure_ascii=False)

    return json.dumps(
        {"dominant_paradigm_shifts": theory_genealogy.get("dominant_paradigm_shifts", [])},
        ensure_ascii=False,
    )


def _build_evidence_index(
    papers: list[dict],
    clusters: list[dict],
    concept_method_kb: dict[str, Any] | None = None,
    theory_units: list[dict] | None = None,
    theory_genealogy: dict | None = None,
) -> dict[str, Any]:
    papers_compact = _compact_papers(papers)
    clusters_compact = _compact_clusters(clusters)
    kb = concept_method_kb or {}

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
        "kb_theories": kb.get("theories", [])[:20],
        "kb_methods": kb.get("methods", [])[:20],
        "theory_units": theory_units or [],
        "theory_genealogy": theory_genealogy or {},
    }


def _section_evidence(section_key: str, evidence: dict[str, Any]) -> dict[str, Any]:
    base: dict[str, Any] = {
        "meta": evidence.get("meta", {}),
        "top_theories": evidence.get("top_theories", []),
        "top_methods": evidence.get("top_methods", []),
        "timeline": evidence.get("timeline", []),
    }

    if section_key == "field_landscape":
        base["papers"] = evidence.get("papers", [])[:20]
        base["clusters"] = evidence.get("clusters", [])[:15]

    elif section_key == "conceptual_architecture":
        base["clusters"] = evidence.get("clusters", [])
        base["papers"] = evidence.get("papers", [])[:20]
        base["kb_theories"] = evidence.get("kb_theories", [])[:10]

    elif section_key == "theory_genealogy_section":
        base["papers"] = evidence.get("papers", [])
        # Genealogy content is passed separately via genealogy_excerpt

    elif section_key == "major_theoretical_models":
        base["papers"] = evidence.get("papers", [])
        base["kb_theories"] = evidence.get("kb_theories", [])
        base["common_limitations"] = evidence.get("common_limitations", [])

    elif section_key == "methodological_landscape":
        base["papers"] = evidence.get("papers", [])[:28]
        base["kb_methods"] = evidence.get("kb_methods", [])
        base["common_limitations"] = evidence.get("common_limitations", [])

    elif section_key == "theoretical_fault_lines":
        base["papers"] = evidence.get("papers", [])
        base["common_limitations"] = evidence.get("common_limitations", [])
        base["kb_theories"] = evidence.get("kb_theories", [])[:10]

    elif section_key == "research_trajectory":
        base["papers"] = evidence.get("papers", [])[:25]
        base["clusters"] = evidence.get("clusters", [])[:20]

    elif section_key == "open_problems":
        base["papers"] = evidence.get("papers", [])[:28]
        base["common_limitations"] = evidence.get("common_limitations", [])
        base["kb_theories"] = evidence.get("kb_theories", [])[:10]

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
    sample_claims = " | ".join(
        str(p.get("main_claim", "")).strip() for p in papers[:3] if str(p.get("main_claim", "")).strip()
    )
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
    context_so_far: str,
    theory_units_compact: list[dict],
    genealogy_excerpt: str,
    llm_model: str,
    client: OllamaClient,
) -> str:
    section_evidence = _section_evidence(section_key, evidence)
    instructions = SECTION_INSTRUCTIONS.get(section_key, f"Write analytically about {section_name}.")
    word_target = SECTION_WORD_TARGETS.get(section_key, "1000-1500 words")

    prompt = SECTION_SYNTHESIS_USER_TEMPLATE.format(
        section_name=section_name,
        section_key=section_key,
        context_so_far=context_so_far or "None yet — this is the first section.",
        theory_units_json=json.dumps(theory_units_compact, ensure_ascii=False),
        genealogy_excerpt=genealogy_excerpt,
        evidence_json=json.dumps(section_evidence, ensure_ascii=False),
        section_instructions=instructions,
        word_target=word_target,
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
    concept_method_kb: dict[str, Any] | None = None,
    theory_units: list[dict] | None = None,
    theory_genealogy: dict | None = None,
) -> dict[str, Any]:
    evidence = _build_evidence_index(
        papers,
        clusters,
        concept_method_kb=concept_method_kb,
        theory_units=theory_units,
        theory_genealogy=theory_genealogy,
    )

    payload: dict[str, Any] = {}
    context_summaries: list[tuple[str, str]] = []

    for key, name in SECTION_SPECS:
        # Build accumulated context from previously written sections (brief summary per section)
        if context_summaries:
            context_so_far = "\n".join(
                f"- {n}: {s}" for n, s in context_summaries
            )
        else:
            context_so_far = ""

        theory_units_compact = _compact_theory_units_for_section(theory_units or [], key)
        genealogy_excerpt = _genealogy_excerpt_for_section(theory_genealogy or {}, key)

        section_text = _generate_section(
            section_key=key,
            section_name=name,
            evidence=evidence,
            context_so_far=context_so_far,
            theory_units_compact=theory_units_compact,
            genealogy_excerpt=genealogy_excerpt,
            llm_model=llm_model,
            client=client,
        )
        payload[key] = section_text

        # Accumulate: first 250 chars as a summary tag for next sections
        summary = section_text.replace("\n", " ").strip()[:250]
        context_summaries.append((name, summary + ("..." if len(section_text) > 250 else "")))

    return payload
