from __future__ import annotations

import re
from typing import Any

from fieldmapper.extraction.ollama_client import OllamaClient
from fieldmapper.extraction.prompts import REVIEW_SECTION_REWRITE_USER_TEMPLATE, REVIEW_WRITER_SYSTEM_PROMPT
from fieldmapper.reporting.citations import normalize_citation_style, render_citation_registry_markdown
from fieldmapper.reporting.knowledge_base import render_method_dossiers_markdown, render_theory_dossiers_markdown

SECTION_PATTERN = re.compile(r"(^# .+?$)(.*?)(?=^# |\Z)", re.MULTILINE | re.DOTALL)
EXPECTED_HEADINGS = [
    "# Executive Overview",
    "# Concept Taxonomy",
    "# Major Theoretical Models",
    "# Methodological Landscape",
    "# Controversies",
    "# Research Trajectory",
    "# Open Problems",
]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _looks_like_json_dump(text: str) -> bool:
    stripped = text.strip()
    return stripped.startswith("[{") or stripped.startswith("{") or "'model_name'" in stripped


def _split_sections(markdown: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    for match in SECTION_PATTERN.finditer(markdown):
        heading = match.group(1).strip()
        body = match.group(2).strip()
        if heading:
            sections.append((heading, body))
    return sections


def _repair_markdown_structure(markdown: str) -> str:
    text = markdown.replace("\r\n", "\n").strip()
    if not text:
        return text

    # Ensure each expected heading starts on its own line.
    for heading in EXPECTED_HEADINGS:
        text = text.replace(heading, f"\n\n{heading}\n\n")

    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    # If text is suspiciously collapsed, add soft paragraph breaks every few sentences.
    line_count = text.count("\n") + 1
    if line_count <= 20 and len(text) > 20000:
        repaired_sections: list[str] = []
        parts = _split_sections(text)
        for heading, body in parts:
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body.strip()) if s.strip()]
            if not sentences:
                repaired_sections.append(f"{heading}\n")
                continue
            chunks: list[str] = []
            for i in range(0, len(sentences), 4):
                chunks.append(" ".join(sentences[i : i + 4]))
            repaired_sections.append(f"{heading}\n\n" + "\n\n".join(chunks))
        if repaired_sections:
            text = "\n\n".join(repaired_sections).strip()

    return text + "\n"


def _rewrite_one_section(
    heading: str,
    body: str,
    supplemental_context: str,
    citation_registry: str,
    report_language: str,
    llm_model: str,
    client: OllamaClient,
) -> str:
    source_section = f"{heading}\n{body}".strip()
    prompt = REVIEW_SECTION_REWRITE_USER_TEMPLATE.format(
        language=report_language,
        supplemental_context=supplemental_context,
        citation_registry=citation_registry,
        section_markdown=source_section,
    )

    try:
        text = client.chat(
            model=llm_model,
            system=REVIEW_WRITER_SYSTEM_PROMPT,
            user=prompt,
            temperature=0.25,
            timeout=1800,
        ).strip()
    except Exception:
        return source_section

    if not text:
        return source_section

    if _looks_like_json_dump(text):
        return source_section

    if _normalize(text) == _normalize(source_section):
        return source_section

    if heading not in text:
        text = f"{heading}\n\n{text}"

    return text.strip()


def generate_review_report_markdown(
    synthesis: dict,
    clusters: list[dict],
    raw_report: str,
    concept_method_kb: dict[str, Any],
    citation_registry_map: dict[str, dict[str, str]],
    report_language: str,
    llm_model: str,
    client: OllamaClient,
) -> str:
    del synthesis, clusters  # Section rewrite uses raw report plus compact supplemental context.

    theory_context = render_theory_dossiers_markdown(concept_method_kb, limit=24)
    method_context = render_method_dossiers_markdown(concept_method_kb, limit=24)
    citation_registry = render_citation_registry_markdown(citation_registry_map)

    sections = _split_sections(raw_report)
    if not sections:
        raise RuntimeError("Failed to parse raw report sections")

    rewritten_sections: list[str] = []
    headings_seen: list[str] = []

    for heading, body in sections:
        supplemental_context = "No additional context."
        if heading == "# Major Theoretical Models":
            supplemental_context = theory_context or supplemental_context
        elif heading == "# Methodological Landscape":
            supplemental_context = method_context or supplemental_context

        rewritten = _rewrite_one_section(
            heading=heading,
            body=body,
            supplemental_context=supplemental_context,
            citation_registry=citation_registry,
            report_language=report_language,
            llm_model=llm_model,
            client=client,
        )
        rewritten_sections.append(rewritten)
        headings_seen.append(heading)

    for heading in EXPECTED_HEADINGS:
        if heading not in headings_seen:
            raise RuntimeError(f"Missing expected section in raw report: {heading}")

    final_report = "\n\n".join(part.strip() for part in rewritten_sections if part.strip()).strip() + "\n"
    final_report = normalize_citation_style(final_report, citation_registry_map)
    final_report = _repair_markdown_structure(final_report)
    return final_report
