from __future__ import annotations

import re

SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "abstract": ("abstract",),
    "introduction": ("introduction", "background"),
    "methods": ("methods", "materials and methods", "methodology"),
    "results": ("results",),
    "discussion": ("discussion", "conclusion", "general discussion"),
}


def split_sections(raw_text: str) -> dict[str, str]:
    normalized = "\n" + raw_text
    markers: list[tuple[int, str]] = []

    for section, aliases in SECTION_ALIASES.items():
        for alias in aliases:
            pattern = re.compile(rf"\n\s*{re.escape(alias)}\s*\n", re.IGNORECASE)
            m = pattern.search(normalized)
            if m:
                markers.append((m.start(), section))
                break

    markers.sort(key=lambda item: item[0])
    extracted: dict[str, str] = {key: "" for key in SECTION_ALIASES}

    if not markers:
        extracted["introduction"] = raw_text[:12000]
        extracted["discussion"] = raw_text[-12000:]
        return extracted

    for i, (start, sec_name) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(normalized)
        extracted[sec_name] = normalized[start:end].strip()

    return extracted
