from __future__ import annotations

import json
import logging
from collections import Counter
from typing import Any

from fieldmapper.extraction.ollama_client import OllamaClient
from fieldmapper.extraction.prompts import (
    THEORY_GENEALOGY_SYSTEM_PROMPT,
    THEORY_GENEALOGY_USER_TEMPLATE,
    THEORY_UNIT_EXTRACTION_SYSTEM_PROMPT,
    THEORY_UNIT_EXTRACTION_USER_TEMPLATE,
)

LOGGER = logging.getLogger(__name__)


def _extract_json_blob(text: str) -> str:
    """Extract the first valid JSON object or array from arbitrary model output."""
    text = text.strip()
    if not text:
        raise ValueError("Empty model response")
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch not in ("{", "["):
            continue
        try:
            _, end = decoder.raw_decode(text[idx:])
            return text[idx : idx + end]
        except json.JSONDecodeError:
            continue
    raise ValueError("No valid JSON object or array found in model response")


def _compact_papers(papers: list[dict], limit: int = 30) -> list[dict]:
    out = []
    for paper in papers[:limit]:
        out.append(
            {
                "paper_id": paper.get("paper_id", ""),
                "title": paper.get("title", ""),
                "year": paper.get("year", ""),
                "paper_type": paper.get("paper_type", ""),
                "core_problem": paper.get("core_problem", ""),
                "main_claim": paper.get("main_claim", ""),
                "theoretical_framework": list(paper.get("theoretical_framework", []))[:6],
                "key_concepts": list(paper.get("key_concepts", []))[:6],
            }
        )
    return out


def _compact_clusters(clusters: list[dict], limit: int = 20) -> list[dict]:
    out = []
    for cluster in clusters[:limit]:
        out.append(
            {
                "cluster_id": cluster.get("cluster_id", ""),
                "representative_label": cluster.get("representative_label", ""),
                "paper_count": cluster.get("paper_count", 0),
                "concepts": list(cluster.get("concepts", []))[:12],
            }
        )
    return out


def _normalize_theory_unit(raw: Any, idx: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {
        "theory_id": f"theory_{idx:03d}",
        "name": str(raw.get("name", f"Theory {idx}")).strip(),
        "origin_problem": str(raw.get("origin_problem", "")).strip(),
        "core_mechanism": str(raw.get("core_mechanism", "")).strip(),
        "predecessor_theories": [str(x) for x in raw.get("predecessor_theories", []) if x],
        "novel_explanatory_gain": str(raw.get("novel_explanatory_gain", "")).strip(),
        "key_evidence": [str(x) for x in raw.get("key_evidence", []) if x],
        "main_criticisms": [str(x) for x in raw.get("main_criticisms", []) if x],
        "successor_or_revision": str(raw.get("successor_or_revision", "")).strip(),
        "current_status": str(raw.get("current_status", "unknown")).strip(),
        "paper_anchors": [str(x) for x in raw.get("paper_anchors", []) if x],
        "cluster_ids": [int(x) for x in raw.get("cluster_ids", []) if str(x).isdigit()],
    }


def extract_theory_units(
    papers: list[dict],
    clusters: list[dict],
    concept_method_kb: dict[str, Any],
    client: OllamaClient,
    llm_model: str,
) -> list[dict[str, Any]]:
    """Stage A: Identify and reconstruct discrete theory units from the corpus."""
    clusters_compact = _compact_clusters(clusters)
    papers_compact = _compact_papers(papers)
    kb_theories = concept_method_kb.get("theories", [])[:30]

    user_prompt = THEORY_UNIT_EXTRACTION_USER_TEMPLATE.format(
        clusters_json=json.dumps(clusters_compact, ensure_ascii=False),
        kb_theories_json=json.dumps(kb_theories, ensure_ascii=False),
        papers_compact_json=json.dumps(papers_compact, ensure_ascii=False),
    )

    errors: list[str] = []
    for attempt in range(1, 4):
        prompt = user_prompt
        if attempt > 1:
            prompt += (
                "\n\nIMPORTANT: Your previous output was invalid JSON. "
                "Return STRICT valid JSON array only, with double quotes on all keys/strings."
            )
        try:
            raw = client.chat(
                model=llm_model,
                system=THEORY_UNIT_EXTRACTION_SYSTEM_PROMPT,
                user=prompt,
                temperature=0.1,
                timeout=1800,
            )
            blob = _extract_json_blob(raw)
            parsed = json.loads(blob)

            # Accept both a bare array and a {"theories": [...]} wrapper
            if isinstance(parsed, dict):
                for key in ("theories", "theory_units", "results"):
                    if isinstance(parsed.get(key), list):
                        parsed = parsed[key]
                        break

            if isinstance(parsed, list):
                units = [
                    u
                    for u in (_normalize_theory_unit(item, i + 1) for i, item in enumerate(parsed))
                    if u.get("name")
                ]
                LOGGER.info("Extracted %d theory units", len(units))
                return units

        except Exception as exc:
            errors.append(f"attempt_{attempt}: {type(exc).__name__}: {exc}")

    LOGGER.warning("Theory unit extraction failed after retries: %s", " | ".join(errors))
    return []


def _normalize_causal_chain(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {
        "from_theory": str(raw.get("from_theory", "")).strip(),
        "limitation": str(raw.get("limitation", "")).strip(),
        "to_theory": str(raw.get("to_theory", "")).strip(),
        "trigger_mechanism": str(raw.get("trigger_mechanism", "")).strip(),
        "approximate_period": str(raw.get("approximate_period", "")).strip(),
    }


def build_theory_genealogy(
    theory_units: list[dict[str, Any]],
    papers: list[dict],
    client: OllamaClient,
    llm_model: str,
) -> dict[str, Any]:
    """Stage B: Reconstruct the causal genealogy of theoretical development."""
    if not theory_units:
        LOGGER.warning("No theory units provided; skipping genealogy construction.")
        return {"narrative": "", "causal_chains": [], "dominant_paradigm_shifts": []}

    year_counter: Counter = Counter()
    for paper in papers:
        year = str(paper.get("year", "")).strip()
        if year:
            year_counter[year] += 1
    timeline = [{"year": y, "paper_count": c} for y, c in sorted(year_counter.items())]

    user_prompt = THEORY_GENEALOGY_USER_TEMPLATE.format(
        theory_units_json=json.dumps(theory_units, ensure_ascii=False),
        timeline_json=json.dumps(timeline, ensure_ascii=False),
    )

    errors: list[str] = []
    for attempt in range(1, 4):
        prompt = user_prompt
        if attempt > 1:
            prompt += (
                "\n\nIMPORTANT: Your previous output was invalid JSON. "
                "Return STRICT valid JSON with keys: narrative, causal_chains, dominant_paradigm_shifts."
            )
        try:
            raw = client.chat(
                model=llm_model,
                system=THEORY_GENEALOGY_SYSTEM_PROMPT,
                user=prompt,
                temperature=0.15,
                timeout=1800,
            )
            blob = _extract_json_blob(raw)
            parsed = json.loads(blob)

            if isinstance(parsed, dict):
                chains = [
                    c
                    for c in (_normalize_causal_chain(x) for x in parsed.get("causal_chains", []))
                    if c.get("from_theory") or c.get("to_theory")
                ]
                shifts = [str(x).strip() for x in parsed.get("dominant_paradigm_shifts", []) if x]
                result = {
                    "narrative": str(parsed.get("narrative", "")).strip(),
                    "causal_chains": chains,
                    "dominant_paradigm_shifts": shifts,
                }
                LOGGER.info(
                    "Built theory genealogy: %d causal chains, %d paradigm shifts, narrative %d chars",
                    len(result["causal_chains"]),
                    len(result["dominant_paradigm_shifts"]),
                    len(result["narrative"]),
                )
                return result

        except Exception as exc:
            errors.append(f"attempt_{attempt}: {type(exc).__name__}: {exc}")

    LOGGER.warning("Theory genealogy building failed: %s", " | ".join(errors))
    return {"narrative": "", "causal_chains": [], "dominant_paradigm_shifts": []}
