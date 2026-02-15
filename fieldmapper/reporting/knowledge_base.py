from __future__ import annotations

from collections import defaultdict
from typing import Any


def _clean(text: Any) -> str:
    return str(text).strip()


def _paper_ref(paper: dict[str, Any]) -> str:
    year = _clean(paper.get("year"))
    title = _clean(paper.get("title")) or _clean(paper.get("file_name")) or _clean(paper.get("paper_id"))
    if year:
        return f"{year} - {title}"
    return title


def _append_unique(target: list[str], value: str, limit: int) -> None:
    if not value or value in target:
        return
    if len(target) < limit:
        target.append(value)


def _aggregate_theories(structured_papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bucket: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "name": "",
            "paper_refs": [],
            "explanations": [],
            "mechanisms": [],
            "supporting_evidence": [],
            "criticisms_or_limits": [],
            "main_claims": [],
        }
    )

    for paper in structured_papers:
        ref = _paper_ref(paper)
        paper_claim = _clean(paper.get("main_claim"))
        paper_limit = _clean(paper.get("limitations"))
        by_name: dict[str, dict[str, Any]] = {}

        for item in paper.get("concept_explanations", []):
            name = _clean(item.get("concept")).lower()
            if not name:
                continue
            row = by_name.setdefault(name, {"concept": _clean(item.get("concept")), "items": []})
            row["items"].append(item)

        for theory_name in paper.get("theoretical_framework", []):
            name = _clean(theory_name).lower()
            if not name:
                continue
            row = by_name.setdefault(name, {"concept": _clean(theory_name), "items": []})
            if paper_claim:
                row["items"].append({"explanation": paper_claim})
            if paper_limit:
                row["items"].append({"criticisms_or_limits": paper_limit})

        for name, row in by_name.items():
            slot = bucket[name]
            slot["name"] = row["concept"] or slot["name"] or name
            _append_unique(slot["paper_refs"], ref, limit=20)
            if paper_claim:
                _append_unique(slot["main_claims"], paper_claim, limit=8)
            if paper_limit:
                _append_unique(slot["criticisms_or_limits"], paper_limit, limit=8)

            for item in row["items"]:
                _append_unique(slot["explanations"], _clean(item.get("explanation")), limit=8)
                _append_unique(slot["mechanisms"], _clean(item.get("mechanism")), limit=8)
                _append_unique(slot["supporting_evidence"], _clean(item.get("supporting_evidence")), limit=8)
                _append_unique(slot["criticisms_or_limits"], _clean(item.get("criticisms_or_limits")), limit=8)

    out = list(bucket.values())
    out.sort(key=lambda x: len(x["paper_refs"]), reverse=True)
    for row in out:
        row["occurrences"] = len(row["paper_refs"])
    return out


def _aggregate_methods(structured_papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bucket: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "name": "",
            "paper_refs": [],
            "what_it_measures_or_tests": [],
            "how_used": [],
            "strengths": [],
            "limitations": [],
        }
    )

    for paper in structured_papers:
        ref = _paper_ref(paper)
        by_name: dict[str, dict[str, Any]] = {}

        for item in paper.get("method_explanations", []):
            name = _clean(item.get("method")).lower()
            if not name:
                continue
            row = by_name.setdefault(name, {"method": _clean(item.get("method")), "items": []})
            row["items"].append(item)

        for method_name in paper.get("method_category", []):
            name = _clean(method_name).lower()
            if not name:
                continue
            by_name.setdefault(name, {"method": _clean(method_name), "items": []})

        for name, row in by_name.items():
            slot = bucket[name]
            slot["name"] = row["method"] or slot["name"] or name
            _append_unique(slot["paper_refs"], ref, limit=20)

            for item in row["items"]:
                _append_unique(slot["what_it_measures_or_tests"], _clean(item.get("what_it_measures_or_tests")), limit=8)
                _append_unique(slot["how_used"], _clean(item.get("how_it_is_used_in_this_paper")), limit=8)
                _append_unique(slot["strengths"], _clean(item.get("strengths")), limit=8)
                _append_unique(slot["limitations"], _clean(item.get("limitations")), limit=8)

    out = list(bucket.values())
    out.sort(key=lambda x: len(x["paper_refs"]), reverse=True)
    for row in out:
        row["occurrences"] = len(row["paper_refs"])
    return out


def build_concept_method_knowledge_base(structured_papers: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "theories": _aggregate_theories(structured_papers),
        "methods": _aggregate_methods(structured_papers),
    }


def _join_items(items: list[str], fallback: str, limit: int = 3) -> str:
    selected = [x for x in items if x][:limit]
    return "; ".join(selected) if selected else fallback


def render_theory_dossiers_markdown(kb: dict[str, Any], limit: int = 20) -> str:
    lines: list[str] = []
    for row in kb.get("theories", [])[:limit]:
        name = _clean(row.get("name")) or "Unnamed Theory"
        occ = int(row.get("occurrences", 0))
        refs = ", ".join(row.get("paper_refs", [])[:6]) or "No paper refs"
        explanation = _join_items(row.get("explanations", []), "No explicit explanation extracted.")
        mechanism = _join_items(row.get("mechanisms", []), "No explicit mechanism extracted.")
        evidence = _join_items(row.get("supporting_evidence", []), "No explicit supporting evidence extracted.")
        criticism = _join_items(row.get("criticisms_or_limits", []), "No explicit criticism/limits extracted.")
        claims = _join_items(row.get("main_claims", []), "No representative main claims extracted.")

        lines.extend(
            [
                f"### {name}",
                f"- Mentions across corpus: {occ}",
                f"- Representative paper anchors: {refs}",
                f"- Explanation summary: {explanation}",
                f"- Mechanistic content: {mechanism}",
                f"- Supporting evidence: {evidence}",
                f"- Criticisms or limitations: {criticism}",
                f"- Related paper-level claims: {claims}",
                "",
            ]
        )
    return "\n".join(lines).strip()


def render_method_dossiers_markdown(kb: dict[str, Any], limit: int = 20) -> str:
    lines: list[str] = []
    for row in kb.get("methods", [])[:limit]:
        name = _clean(row.get("name")) or "Unnamed Method"
        occ = int(row.get("occurrences", 0))
        refs = ", ".join(row.get("paper_refs", [])[:6]) or "No paper refs"
        measures = _join_items(row.get("what_it_measures_or_tests", []), "No explicit measurement target extracted.")
        usage = _join_items(row.get("how_used", []), "No explicit per-paper usage extracted.")
        strengths = _join_items(row.get("strengths", []), "No explicit strengths extracted.")
        limitations = _join_items(row.get("limitations", []), "No explicit limitations extracted.")

        lines.extend(
            [
                f"### {name}",
                f"- Mentions across corpus: {occ}",
                f"- Representative paper anchors: {refs}",
                f"- What it measures/tests: {measures}",
                f"- How used in papers: {usage}",
                f"- Strengths: {strengths}",
                f"- Limitations: {limitations}",
                "",
            ]
        )
    return "\n".join(lines).strip()
