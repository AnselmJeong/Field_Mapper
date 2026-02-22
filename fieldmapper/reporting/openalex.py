from __future__ import annotations

import os
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import requests

OPENALEX_WORKS_API = "https://api.openalex.org/works"
PAREN_BLOCK_PATTERN = re.compile(r"\(([^()\n]{1,240})\)")
BACKTICK_PATTERN = re.compile(r"`([^`\n]{1,200})`")
NARRATIVE_PAREN_PATTERN = re.compile(
    r"(?P<full>(?P<author>\*?[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'`\-]+(?:\s+(?:et al\.|and\s+[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'`\-]+|&\s*[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'`\-]+))?\*?)\s*\((?P<year>\d{4}[a-z]?)\))"
)
NARRATIVE_COMMA_PATTERN = re.compile(
    r"(?P<full>(?P<author>\*?[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'`\-]+(?:\s+(?:et al\.|and\s+[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'`\-]+|&\s*[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'`\-]+))?\*?)\s*,\s*(?P<year>\d{4}[a-z]?))"
)
BAD_SINGLE_AUTHORS = {
    "rest",
    "review",
    "model",
    "models",
    "theory",
    "theories",
    "framework",
    "analysis",
    "dynamics",
    "network",
    "networks",
    "system",
    "systems",
    "brain",
    "brains",
    "landscape",
    "landscapes",
}


def _clean(text: Any) -> str:
    return str(text or "").strip()


def _norm_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _norm_author_token(author: str) -> str:
    return re.sub(r"[^a-z]", "", author.lower())


def _strip_leading_marker(text: str) -> str:
    value = _norm_space(text)
    value = re.sub(r"^(e\.g\.|i\.e\.|cf\.|see|see also|e\.g)\s*,?\s*", "", value, flags=re.IGNORECASE)
    return value.strip(" ,.;:")


def _extract_first_author(citation: str) -> str:
    head = citation.split(",", 1)[0].strip()
    head = re.split(r"\set al\.?$|\sand\s|&", head, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    if not head:
        return ""
    return head.split()[-1].strip(".")


def _parse_citation_atom(text: str) -> str | None:
    candidate = _strip_leading_marker(text)
    match = re.match(r"^(.+?),\s*(\d{4}[a-z]?)$", candidate, flags=re.IGNORECASE)
    if not match:
        return None
    author = _norm_space(match.group(1))
    year = match.group(2)
    if not re.search(r"[A-Za-z]", author):
        return None
    if len(author) > 80:
        return None
    author_plain = author.replace("*", "").strip()
    lower_plain = author_plain.lower().strip(". ")
    if "et al" not in lower_plain and " and " not in lower_plain and "&" not in author_plain:
        tokens = author_plain.split()
        if len(tokens) == 1 and tokens[0].lower() in BAD_SINGLE_AUTHORS:
            return None
    return f"{author}, {year}"


def _citation_key(citation: str) -> str:
    year = citation.rsplit(",", 1)[-1].strip()
    first_author = _norm_author_token(_extract_first_author(citation))
    return f"{first_author}|{year}"


def _extract_citation_atoms(report_text: str) -> list[str]:
    atoms: set[str] = set()
    for match in PAREN_BLOCK_PATTERN.finditer(report_text):
        parts = [p.strip() for p in match.group(1).split(";")]
        for part in parts:
            atom = _parse_citation_atom(part)
            if atom:
                atoms.add(atom)
    for match in BACKTICK_PATTERN.finditer(report_text):
        atom = _parse_citation_atom(match.group(1))
        if atom:
            atoms.add(atom)
    for pattern in (NARRATIVE_PAREN_PATTERN, NARRATIVE_COMMA_PATTERN):
        for match in pattern.finditer(report_text):
            author = _norm_space(match.group("author").replace("*", ""))
            year = match.group("year")
            atom = _parse_citation_atom(f"{author}, {year}")
            if atom:
                atoms.add(atom)
    return sorted(atoms)


def _extract_title_hints(report_text: str) -> dict[str, list[str]]:
    hints: dict[str, list[str]] = {}
    pattern = re.compile(r"\*([^*\n]{3,240})\*\s*\(([^()\n]{1,120})\)")
    for match in pattern.finditer(report_text):
        title = _norm_space(match.group(1))
        atom = _parse_citation_atom(_norm_space(match.group(2)))
        if not atom:
            continue
        key = _citation_key(atom)
        bucket = hints.setdefault(key, [])
        if title not in bucket:
            bucket.append(title)
    return hints


def _read_env_api_key() -> str:
    for key in ("OPENALEX_API_KEY", "OPENALEX_APIKEY", "api_key", "OPENALEX_KEY"):
        value = _clean(os.environ.get(key))
        if value:
            return value

    env_paths = [Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"]
    for path in env_paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            k, v = raw.split("=", 1)
            if k.strip() in ("OPENALEX_API_KEY", "OPENALEX_APIKEY", "api_key", "OPENALEX_KEY"):
                v = v.strip().strip("'").strip('"')
                if v:
                    return v
    return ""


def _registry_candidates(citation: str, citation_registry: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    year = citation.rsplit(",", 1)[-1].strip()
    author_norm = _norm_author_token(_extract_first_author(citation))
    out: list[dict[str, str]] = []
    for item in citation_registry.values():
        item_author = _norm_author_token(_clean(item.get("first_author")))
        item_year = _clean(item.get("year"))
        if item_year == year and item_author and item_author == author_norm:
            out.append(item)
    return out


def _select_registry_title(citation: str, candidates: list[dict[str, str]], title_hints: dict[str, list[str]]) -> str:
    if not candidates:
        return ""
    if len(candidates) == 1:
        return _clean(candidates[0].get("title"))

    hints = title_hints.get(_citation_key(citation), [])
    if len(hints) != 1:
        return ""
    hint = hints[0]
    scored: list[tuple[float, str]] = []
    for item in candidates:
        title = _clean(item.get("title"))
        if title:
            scored.append((SequenceMatcher(None, hint.lower(), title.lower()).ratio(), title))
    if not scored:
        return ""
    scored.sort(key=lambda x: x[0], reverse=True)
    if scored[0][0] >= 0.72:
        return scored[0][1]
    return ""


def _pick_doi(work: dict[str, Any]) -> str:
    doi = _clean(work.get("doi"))
    if doi:
        return doi
    ids = work.get("ids") or {}
    return _clean(ids.get("doi"))


def _pick_url(work: dict[str, Any]) -> str:
    doi = _pick_doi(work)
    return doi or _clean(work.get("id"))


def _work_title(work: dict[str, Any]) -> str:
    return _clean(work.get("display_name"))


def _work_year(work: dict[str, Any]) -> str:
    year = work.get("publication_year")
    return str(year) if year is not None else ""


def _work_authors(work: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for authorship in work.get("authorships") or []:
        author = authorship.get("author") or {}
        name = _clean(author.get("display_name"))
        if name:
            names.append(name)
    return names


def _first_author_lastname(work: dict[str, Any]) -> str:
    names = _work_authors(work)
    if not names:
        return ""
    return _norm_author_token(names[0].split()[-1])


def _score_work(work: dict[str, Any], citation: str, hinted_title: str = "") -> float:
    score = 0.0
    expected_author = _norm_author_token(_extract_first_author(citation))
    expected_year = citation.rsplit(",", 1)[-1].strip()

    work_year = _work_year(work)
    if work_year == expected_year:
        score += 4.0

    author_names = _work_authors(work)
    author_norms = [_norm_author_token(a.split()[-1]) for a in author_names if a.strip()]
    first_author_norm = _first_author_lastname(work)
    if expected_author and expected_author == first_author_norm:
        score += 3.0
    elif expected_author and expected_author in author_norms:
        score += 1.0

    if hinted_title:
        ratio = SequenceMatcher(None, hinted_title.lower(), _work_title(work).lower()).ratio()
        score += ratio * 3.0

    if _pick_doi(work):
        score += 0.5
    return score


def _query_openalex(query: str, year: str, api_key: str, per_page: int = 12) -> list[dict[str, Any]]:
    params = {"search": query, "filter": f"publication_year:{year}", "per-page": str(per_page)}
    if api_key:
        params["api_key"] = api_key
    response = requests.get(OPENALEX_WORKS_API, params=params, timeout=30)
    response.raise_for_status()
    return (response.json() or {}).get("results") or []


def _query_openalex_title(title: str, year: str, api_key: str, per_page: int = 12) -> list[dict[str, Any]]:
    params = {"search": title, "filter": f"publication_year:{year}", "per-page": str(per_page)}
    if api_key:
        params["api_key"] = api_key
    response = requests.get(OPENALEX_WORKS_API, params=params, timeout=30)
    response.raise_for_status()
    return (response.json() or {}).get("results") or []


@dataclass(slots=True)
class CitationResolution:
    citation: str
    source: str
    confidence: float
    work_id: str
    title: str
    year: str
    doi_or_url: str
    authors: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "citation": self.citation,
            "source": self.source,
            "confidence": round(self.confidence, 4),
            "work_id": self.work_id,
            "title": self.title,
            "year": self.year,
            "doi_or_url": self.doi_or_url,
            "authors": self.authors,
        }

    def to_bibtex(self, key_suffix: str) -> str:
        key_author = re.sub(r"[^A-Za-z0-9]+", "", _extract_first_author(self.citation) or "ref")
        key_year = re.sub(r"[^0-9a-zA-Z]+", "", self.year or "nd")
        key = f"{key_author}{key_year}_{key_suffix}"
        safe_title = self.title.replace("{", "\\{").replace("}", "\\}")
        safe_author = " and ".join(self.authors) if self.authors else _extract_first_author(self.citation) or "Unknown"
        safe_author = safe_author.replace("{", "\\{").replace("}", "\\}")
        lines = [
            f"@article{{{key},",
            f"  author = {{{safe_author}}},",
            f"  title = {{{safe_title}}},",
            f"  year = {{{self.year or 'n.d.'}}},",
        ]
        if self.doi_or_url.startswith("https://doi.org/"):
            lines.append(f"  doi = {{{self.doi_or_url.removeprefix('https://doi.org/')}}},")
            lines.append(f"  url = {{{self.doi_or_url}}},")
        elif self.doi_or_url:
            lines.append(f"  url = {{{self.doi_or_url}}},")
        if self.work_id:
            lines.append(f"  note = {{{self.work_id}}},")
        lines.append("}")
        return "\n".join(lines)


def _link_parenthetical_citations(text: str, link_map: dict[str, str]) -> str:
    def _replace_block(match: re.Match[str]) -> str:
        parts = [p.strip() for p in match.group(1).split(";")]
        changed = False
        new_parts: list[str] = []
        for part in parts:
            atom = _parse_citation_atom(part)
            key = _citation_key(atom) if atom else ""
            if atom and key in link_map:
                new_parts.append(f"[{atom}]({link_map[key]})")
                changed = True
            else:
                new_parts.append(part)
        if not changed:
            return match.group(0)
        return f"({'; '.join(new_parts)})"

    return PAREN_BLOCK_PATTERN.sub(_replace_block, text)


def _link_narrative_citations(text: str, link_map: dict[str, str]) -> str:
    out = text

    def _replace(match: re.Match[str]) -> str:
        start = match.start("full")
        end = match.end("full")
        if start > 0 and out[start - 1] == "[" and out[end : end + 2] == "](":
            return match.group("full")

        full = match.group("full")
        if full.count("*") == 1:
            return full
        author = _norm_space(match.group("author").replace("*", ""))
        year = match.group("year")
        atom = _parse_citation_atom(f"{author}, {year}")
        if not atom:
            return full
        key = _citation_key(atom)
        url = link_map.get(key)
        if not url:
            return full
        return f"[{full}]({url})"

    out = NARRATIVE_PAREN_PATTERN.sub(_replace, out)
    out = NARRATIVE_COMMA_PATTERN.sub(_replace, out)
    return out


def _drop_citation_backticks(text: str) -> str:
    out = text
    out = re.sub(r"`\s*\(([^`()]{1,120}?,\s*\d{4}[a-z]?)\)\s*`", r"(\1)", out, flags=re.IGNORECASE)
    out = re.sub(r"`\s*([^`()]{1,120}?,\s*\d{4}[a-z]?)\s*`", r"\1", out, flags=re.IGNORECASE)
    return out


def _cleanup_citation_parentheses(text: str) -> str:
    out = text
    for _ in range(3):
        out = re.sub(
            r"\(\s*\(\s*(\[[^\]\n]{1,200}\]\(https?://[^\)\n]+\)|[A-Za-z][^()\n]{0,120}?,\s*\d{4}[a-z]?)\s*\)\s*\)",
            r"(\1)",
            out,
        )
    out = re.sub(r"\(\s+\[", "([", out)
    out = re.sub(r"\]\s+\)", "])", out)
    return out


def _unlink_existing_citation_links(text: str) -> str:
    return re.sub(r"\[([^\]\n]{1,200}?\d{4}[a-z]?[^\]\n]{0,80})\]\(https?://[^\)\n]+\)", r"\1", text)


def _references_markdown(matched: list[CitationResolution], unresolved: list[str]) -> str:
    lines = ["# References (OpenAlex-verified)", ""]
    if matched:
        for item in sorted(matched, key=lambda x: (x.citation.lower(), x.year)):
            author_text = ", ".join(item.authors[:6]) if item.authors else _extract_first_author(item.citation)
            year = item.year or item.citation.rsplit(",", 1)[-1].strip()
            link = item.doi_or_url or item.work_id
            lines.append(f"- {author_text} ({year}). {item.title}. [{link}]({link})")
    else:
        lines.append("- No references could be verified via OpenAlex.")

    lines.extend(["", "## Unresolved Citations", ""])
    if unresolved:
        for cit in sorted(set(unresolved), key=str.lower):
            lines.append(f"- {cit}")
    else:
        lines.append("- None")
    return "\n".join(lines).strip() + "\n"


def _build_bibtex(matched: list[CitationResolution]) -> str:
    if not matched:
        return ""
    entries = [item.to_bibtex(f"openalex{i+1:03d}") for i, item in enumerate(matched)]
    return "\n\n".join(entries).strip() + "\n"


def enrich_report_with_openalex(report_text: str, citation_registry: dict[str, dict[str, str]]) -> dict[str, Any]:
    api_key = _read_env_api_key()
    citations = _extract_citation_atoms(report_text)
    title_hints = _extract_title_hints(report_text)

    matched: list[CitationResolution] = []
    unresolved: list[str] = []
    link_map: dict[str, str] = {}
    cache: dict[str, CitationResolution | None] = {}

    for citation in citations:
        if citation in cache:
            cached = cache[citation]
            if cached:
                matched.append(cached)
                link_map[_citation_key(citation)] = cached.doi_or_url
            else:
                unresolved.append(citation)
            continue

        year = citation.rsplit(",", 1)[-1].strip()
        first_author = _extract_first_author(citation)
        candidates = _registry_candidates(citation, citation_registry)
        hinted_title = _select_registry_title(citation, candidates, title_hints)
        source = "registry+openalex" if hinted_title and candidates else "openalex_search"

        if not hinted_title and not candidates:
            hint_from_context = title_hints.get(_citation_key(citation), [])
            if len(hint_from_context) == 1:
                hinted_title = hint_from_context[0]
                source = "context_title+openalex"

        try:
            if hinted_title:
                works = _query_openalex_title(title=hinted_title, year=year[:4], api_key=api_key)
                if not works:
                    works = _query_openalex(query=f"{hinted_title} {year}", year=year[:4], api_key=api_key)
            elif candidates:
                # Corpus citation but ambiguous title: avoid risky linking.
                works = []
            else:
                works = _query_openalex(query=f"{first_author} {year}", year=year[:4], api_key=api_key)
        except Exception:
            works = []

        best_work: dict[str, Any] | None = None
        best_score = -1.0
        second_score = -1.0
        for work in works:
            score = _score_work(work, citation, hinted_title=hinted_title)
            if score > best_score:
                second_score = best_score
                best_score = score
                best_work = work
            elif score > second_score:
                second_score = score

        expected_author = _norm_author_token(_extract_first_author(citation))
        has_exact_year = bool(best_work and _work_year(best_work) == year[:4])
        has_exact_first_author = bool(best_work and _first_author_lastname(best_work) == expected_author)
        title_ratio = 0.0
        if best_work and hinted_title:
            title_ratio = SequenceMatcher(None, hinted_title.lower(), _work_title(best_work).lower()).ratio()

        verified = False
        if best_work:
            if candidates:
                verified = has_exact_year and has_exact_first_author and title_ratio >= 0.86
            elif hinted_title:
                verified = has_exact_year and has_exact_first_author and title_ratio >= 0.72
            else:
                score_gap = best_score - max(second_score, -1.0)
                verified = has_exact_year and has_exact_first_author and best_score >= 7.0 and score_gap >= 1.5

        if best_work and verified:
            resolved = CitationResolution(
                citation=citation,
                source=source,
                confidence=best_score,
                work_id=_clean(best_work.get("id")),
                title=_work_title(best_work),
                year=_work_year(best_work) or year,
                doi_or_url=_pick_url(best_work),
                authors=_work_authors(best_work),
            )
            cache[citation] = resolved
            matched.append(resolved)
            link_map[_citation_key(citation)] = resolved.doi_or_url
        else:
            cache[citation] = None
            unresolved.append(citation)

    deduped: dict[str, CitationResolution] = {}
    for item in matched:
        deduped[item.citation] = item
    matched = list(deduped.values())

    body = report_text
    body = _unlink_existing_citation_links(body)
    body = _drop_citation_backticks(body)
    body = _link_parenthetical_citations(body, link_map)
    body = _link_narrative_citations(body, link_map)
    body = _cleanup_citation_parentheses(body)
    body = body.rstrip() + "\n\n" + _references_markdown(matched, unresolved)

    return {
        "report_text": body,
        "matches": [m.as_dict() for m in matched],
        "unresolved": sorted(set(unresolved)),
        "link_map": link_map,
        "bibtex": _build_bibtex(matched),
        "api_key_present": bool(api_key),
        "stats": {
            "citation_count": len(citations),
            "matched_count": len(matched),
            "unresolved_count": len(sorted(set(unresolved))),
            "corpus_citation_count": sum(1 for c in citations if _registry_candidates(c, citation_registry)),
        },
    }
