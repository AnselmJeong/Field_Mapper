from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fieldmapper.reporting.knowledge_base import render_method_dossiers_markdown, render_theory_dossiers_markdown

# Section headings used by both this module and review_writer.py
REPORT_HEADINGS = [
    "# Field Landscape",
    "# Conceptual Architecture",
    "# Theory Genealogy",
    "# Major Theoretical Models",
    "# Methodological Landscape",
    "# Theoretical Fault Lines",
    "# Research Trajectory",
    "# Open Problems",
]

# Mapping from synthesis dict keys to headings
_KEY_TO_HEADING = {
    "field_landscape": "# Field Landscape",
    "conceptual_architecture": "# Conceptual Architecture",
    "theory_genealogy_section": "# Theory Genealogy",
    "major_theoretical_models": "# Major Theoretical Models",
    "methodological_landscape": "# Methodological Landscape",
    "theoretical_fault_lines": "# Theoretical Fault Lines",
    "research_trajectory": "# Research Trajectory",
    "open_problems": "# Open Problems",
}


def _to_title(key: str) -> str:
    return key.replace("_", " ").strip().title()


def _format_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value).strip()


def _render_markdown(value: Any, indent: int = 0) -> str:
    pad = "  " * indent

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ""
        if stripped[0] in "[{":
            try:
                parsed = json.loads(stripped)
                return _render_markdown(parsed, indent=indent)
            except Exception:
                return stripped
        return stripped

    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            title = _to_title(str(key))
            if isinstance(item, (dict, list)):
                nested = _render_markdown(item, indent=indent + 1)
                if nested:
                    lines.append(f"{pad}- **{title}**")
                    lines.append(nested)
            else:
                scalar = _format_scalar(item)
                if scalar:
                    lines.append(f"{pad}- **{title}**: {scalar}")
        return "\n".join(lines)

    if isinstance(value, list):
        lines: list[str] = []
        for item in value:
            if isinstance(item, dict):
                lead = ""
                for key in ("model_name", "title", "name", "label", "cluster"):
                    candidate = _format_scalar(item.get(key))
                    if candidate:
                        lead = candidate
                        break

                remaining = dict(item)
                for key in ("model_name", "title", "name", "label", "cluster"):
                    remaining.pop(key, None)

                if lead:
                    lines.append(f"{pad}- **{lead}**")
                    nested = _render_markdown(remaining, indent=indent + 1)
                    if nested:
                        lines.append(nested)
                else:
                    nested = _render_markdown(item, indent=indent + 1)
                    if nested:
                        lines.append(f"{pad}-")
                        lines.append(nested)
            elif isinstance(item, list):
                nested = _render_markdown(item, indent=indent + 1)
                if nested:
                    lines.append(f"{pad}-")
                    lines.append(nested)
            else:
                scalar = _format_scalar(item)
                if scalar:
                    lines.append(f"{pad}- {scalar}")
        return "\n".join(lines)

    return _format_scalar(value)


def _section_text(value: Any) -> str:
    rendered = _render_markdown(value).strip()
    return rendered or "Not enough extracted data."


def _render_causal_chains(chains: list[dict]) -> str:
    """Render theory genealogy causal chains as a structured Markdown list."""
    if not chains:
        return "No causal chain data available."
    lines: list[str] = []
    for chain in chains:
        from_t = chain.get("from_theory", "Unknown")
        limitation = chain.get("limitation", "")
        to_t = chain.get("to_theory", "Unknown")
        trigger = chain.get("trigger_mechanism", "")
        period = chain.get("approximate_period", "")
        header = f"**{from_t}** → **{to_t}**"
        if period:
            header += f" ({period})"
        lines.append(f"- {header}")
        if limitation:
            lines.append(f"  - Limitation driving transition: {limitation}")
        if trigger:
            lines.append(f"  - Triggering mechanism/finding: {trigger}")
    return "\n".join(lines)


def _render_paradigm_shifts(shifts: list[str]) -> str:
    if not shifts:
        return ""
    return "\n".join(f"- {s}" for s in shifts)


def _render_theory_profiles(theory_units: list[dict]) -> str:
    """Render theory units as deep dossier entries for the raw report."""
    if not theory_units:
        return "No theory unit profiles extracted."
    lines: list[str] = []
    for unit in theory_units:
        name = unit.get("name", "Unnamed Theory")
        lines.append(f"### {name}")
        status = unit.get("current_status", "")
        if status:
            lines.append(f"- **Current status**: {status}")

        origin = unit.get("origin_problem", "")
        if origin:
            lines.append(f"- **Origin problem**: {origin}")

        mechanism = unit.get("core_mechanism", "")
        if mechanism:
            lines.append(f"- **Core mechanism**: {mechanism}")

        gain = unit.get("novel_explanatory_gain", "")
        if gain:
            lines.append(f"- **Novel explanatory gain**: {gain}")

        predecessors = unit.get("predecessor_theories", [])
        if predecessors:
            lines.append(f"- **Predecessor theories**: {', '.join(predecessors)}")

        evidence = unit.get("key_evidence", [])
        if evidence:
            lines.append(f"- **Key evidence**: {'; '.join(evidence[:4])}")

        criticisms = unit.get("main_criticisms", [])
        if criticisms:
            lines.append(f"- **Main criticisms**: {'; '.join(criticisms[:3])}")

        successor = unit.get("successor_or_revision", "")
        if successor:
            lines.append(f"- **Successor/revision**: {successor}")

        anchors = unit.get("paper_anchors", [])
        if anchors:
            lines.append(f"- **Paper anchors**: {', '.join(anchors[:6])}")

        lines.append("")
    return "\n".join(lines).strip()


def generate_report_markdown(
    synthesis: dict,
    clusters: list[dict],
    concept_method_kb: dict[str, Any] | None = None,
    theory_units: list[dict] | None = None,
    theory_genealogy: dict | None = None,
) -> str:
    taxonomy_lines = [
        f"- **{c['representative_label']}** ({c['paper_count']} papers): {', '.join(c['concepts'][:8])}"
        for c in clusters[:20]
    ]
    kb = concept_method_kb or {"theories": [], "methods": []}
    theory_dossiers = render_theory_dossiers_markdown(kb, limit=24)
    method_dossiers = render_method_dossiers_markdown(kb, limit=24)

    tu = theory_units or []
    tg = theory_genealogy or {}

    # Theory Genealogy section content
    genealogy_narrative = tg.get("narrative", "").strip()
    causal_chains = tg.get("causal_chains", [])
    paradigm_shifts = tg.get("dominant_paradigm_shifts", [])

    genealogy_section_lines: list[str] = []
    # Use LLM-generated synthesis text if available
    synthesis_genealogy = _section_text(synthesis.get("theory_genealogy_section", ""))
    genealogy_section_lines.append(synthesis_genealogy)
    if causal_chains:
        genealogy_section_lines.append("\n## Causal Chain Index\n")
        genealogy_section_lines.append(_render_causal_chains(causal_chains))
    if paradigm_shifts:
        genealogy_section_lines.append("\n## Major Paradigm Shifts\n")
        genealogy_section_lines.append(_render_paradigm_shifts(paradigm_shifts))
    if genealogy_narrative and not synthesis.get("theory_genealogy_section"):
        # Fallback: use the raw genealogy narrative if synthesis section is empty
        genealogy_section_lines.insert(0, genealogy_narrative)

    # Major Theoretical Models: synthesis text + deep theory profiles
    theory_profiles = _render_theory_profiles(tu)

    sections = [
        "# Field Landscape",
        _section_text(synthesis.get("field_landscape", synthesis.get("executive_overview", ""))),
        "",
        "# Conceptual Architecture",
        _section_text(synthesis.get("conceptual_architecture", synthesis.get("concept_taxonomy", ""))),
        "",
        "## Cluster Inventory",
        *taxonomy_lines,
        "",
        "# Theory Genealogy",
        "\n".join(genealogy_section_lines),
        "",
        "# Major Theoretical Models",
        _section_text(synthesis.get("major_theoretical_models", "")),
        "",
        "## Theory Unit Profiles (Evidence-Tracked)",
        theory_profiles or "No detailed theory unit profiles extracted.",
        "",
        "## Theory Dossiers (Knowledge Base)",
        theory_dossiers or "No detailed theory dossiers extracted.",
        "",
        "# Methodological Landscape",
        _section_text(synthesis.get("methodological_landscape", "")),
        "",
        "## Method Dossiers (Evidence-Tracked)",
        method_dossiers or "No detailed method dossiers extracted.",
        "",
        "# Theoretical Fault Lines",
        _section_text(synthesis.get("theoretical_fault_lines", synthesis.get("controversies", ""))),
        "",
        "# Research Trajectory",
        _section_text(synthesis.get("research_trajectory", "")),
        "",
        "# Open Problems",
        _section_text(synthesis.get("open_problems", "")),
        "",
    ]

    return "\n".join(sections)


def write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
