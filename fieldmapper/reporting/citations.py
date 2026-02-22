from __future__ import annotations

import re
from typing import Any


def _clean(text: Any) -> str:
    return str(text).strip()


def _parse_first_author(file_name: str) -> str:
    stem = _clean(file_name).rsplit("/", 1)[-1]
    if stem.lower().endswith(".pdf"):
        stem = stem[:-4]
    parts = [p.strip() for p in stem.split(" - ")]
    if len(parts) >= 3:
        author_block = parts[1]
        author = author_block.split(",")[0].split("&")[0].split(" and ")[0].strip()
        author = author.split(" et al")[0].strip()
        if author:
            return author
    return "Unknown"


def build_citation_registry(structured_papers: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    registry: dict[str, dict[str, str]] = {}
    for paper in structured_papers:
        paper_id = _clean(paper.get("paper_id"))
        if not paper_id:
            continue
        year = _clean(paper.get("year")) or "n.d."
        title = _clean(paper.get("title"))
        first_author = _parse_first_author(_clean(paper.get("file_name")))
        short = f"{first_author}, {year}"
        registry[paper_id] = {
            "paper_id": paper_id,
            "year": year,
            "title": title,
            "first_author": first_author,
            "short": short,
            "canonical": f"({short})",
        }
    return registry


def _bib_safe(value: Any) -> str:
    text = str(value or "").strip()
    return text.replace("{", "\\{").replace("}", "\\}")


def _bib_key(item: dict[str, str]) -> str:
    author = re.sub(r"[^A-Za-z0-9]+", "", item.get("first_author", "unknown")) or "unknown"
    year = re.sub(r"[^0-9a-zA-Z]+", "", item.get("year", "nd")) or "nd"
    paper_id = re.sub(r"[^A-Za-z0-9]+", "", item.get("paper_id", "paper"))
    return f"{author}{year}_{paper_id}"


def render_bibtex_from_registry(registry: dict[str, dict[str, str]]) -> str:
    entries: list[str] = []
    for paper_id in sorted(registry):
        item = registry[paper_id]
        key = _bib_key(item)
        author = _bib_safe(item.get("first_author", "Unknown"))
        year = _bib_safe(item.get("year", "n.d."))
        title = _bib_safe(item.get("title", "Untitled"))
        lines = [
            f"@article{{{key},",
            f"  author = {{{author}}},",
            f"  title = {{{title}}},",
            f"  year = {{{year}}},",
            f"  note = {{{_bib_safe(item.get('paper_id', ''))}}}",
            "}",
        ]
        entries.append("\n".join(lines))
    if not entries:
        return ""
    return "\n\n".join(entries) + "\n"


def render_citation_registry_markdown(registry: dict[str, dict[str, str]]) -> str:
    lines: list[str] = []
    for paper_id in sorted(registry):
        item = registry[paper_id]
        title = item.get("title", "")
        lines.append(f"- {paper_id}: {item['short']} | {title}")
    return "\n".join(lines)


def normalize_citation_style(text: str, registry: dict[str, dict[str, str]]) -> str:
    out = text

    # Drop explicit paper-id suffix when model outputs "(Author, Year; paper_XXX)".
    out = re.sub(r"\(\s*([^()]+?)\s*;\s*paper_\d{3}\s*\)", r"(\1)", out)

    # Normalize explicit paper-id parenthetical citations.
    def _replace_id_year(m: re.Match[str]) -> str:
        pid = f"paper_{m.group(1)}"
        item = registry.get(pid)
        return item["canonical"] if item else ""

    out = re.sub(r"\(\s*paper_(\d{3})\s*,\s*\d{4}\s*\)", _replace_id_year, out)
    out = re.sub(r"\(\s*paper_(\d{3})\s*\)", _replace_id_year, out)

    # Normalize exact title(year) patterns into canonical style.
    for pid, item in registry.items():
        title = item.get("title", "").strip()
        year = item.get("year", "").strip()
        if not title or not year:
            continue
        # Plain title
        out = re.sub(re.escape(f"{title} ({year})"), item["canonical"], out)
        # Markdown-italic title
        out = re.sub(re.escape(f"*{title}* ({year})"), item["canonical"], out)

    # Normalize standalone paper ids.
    def _replace_standalone(m: re.Match[str]) -> str:
        pid = m.group(0)
        item = registry.get(pid)
        return item["canonical"] if item else ""

    out = re.sub(r"\bpaper_\d{3}\b", _replace_standalone, out)

    # Cleanup: remove accidental double parentheses and punctuation artifacts.
    for _ in range(3):
        out = re.sub(r"\(\s*\(([^()]+)\)\s*\)", r"(\1)", out)
    out = re.sub(r"\(\s*,\s*", "(", out)
    out = re.sub(r"\(\s*\)", "", out)
    # Preserve newlines: only collapse repeated spaces/tabs inside a line.
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\(\s+", "(", out)
    out = re.sub(r"\s+\)", ")", out)
    out = re.sub(r"\(\(", "(", out)
    out = re.sub(r"\)\)", ")", out)

    # Remove markdown backticks around citation-like fragments.
    out = re.sub(r"`\s*(\([^`]*\d{4}[^`]*\))\s*`", r"\1", out)
    out = re.sub(r"`\s*([^`]*\([A-Za-z][^`]*\d{4}[^`]*\)[^`]*)\s*`", r"\1", out)
    out = re.sub(r"`\s*([A-Z][^`,]{0,80}?,\s*\d{4}[a-z]?)\s*`", r"\1", out)
    return out
