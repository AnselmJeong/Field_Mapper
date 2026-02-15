from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fieldmapper.reporting.knowledge_base import render_method_dossiers_markdown, render_theory_dossiers_markdown


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


def generate_report_markdown(
    synthesis: dict,
    clusters: list[dict],
    concept_method_kb: dict[str, Any] | None = None,
) -> str:
    taxonomy_lines = [
        f"- **{c['representative_label']}** ({c['paper_count']} papers): {', '.join(c['concepts'][:8])}"
        for c in clusters[:20]
    ]
    kb = concept_method_kb or {"theories": [], "methods": []}
    theory_dossiers = render_theory_dossiers_markdown(kb, limit=24)
    method_dossiers = render_method_dossiers_markdown(kb, limit=24)

    return "\n".join(
        [
            "# Executive Overview",
            _section_text(synthesis.get("executive_overview", "")),
            "",
            "# Concept Taxonomy",
            _section_text(synthesis.get("concept_taxonomy", "")),
            "",
            "## Cluster Inventory",
            *taxonomy_lines,
            "",
            "# Major Theoretical Models",
            _section_text(synthesis.get("major_theoretical_models", "")),
            "",
            "## Theory Dossiers (Evidence-Tracked)",
            theory_dossiers or "No detailed theory dossiers extracted.",
            "",
            "# Methodological Landscape",
            _section_text(synthesis.get("methodological_landscape", "")),
            "",
            "## Method Dossiers (Evidence-Tracked)",
            method_dossiers or "No detailed method dossiers extracted.",
            "",
            "# Controversies",
            _section_text(synthesis.get("controversies", "")),
            "",
            "# Research Trajectory",
            _section_text(synthesis.get("research_trajectory", "")),
            "",
            "# Open Problems",
            _section_text(synthesis.get("open_problems", "")),
            "",
        ]
    )


def write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
