from __future__ import annotations

import json
import logging
from typing import Any

from fieldmapper.config import PaperRecord, PipelineConfig
from fieldmapper.extraction.ollama_client import OllamaClient
from fieldmapper.extraction.prompts import EXTRACTION_SYSTEM_PROMPT, EXTRACTION_USER_TEMPLATE
from fieldmapper.ingestion.section_parser import split_sections

LOGGER = logging.getLogger(__name__)


def _extract_json_blob(text: str) -> str:
    text = text.strip()
    if not text:
        raise ValueError("Empty model response")

    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            _, end = decoder.raw_decode(text[idx:])
            return text[idx : idx + end]
        except json.JSONDecodeError:
            continue

    raise ValueError("No valid JSON object found in model response")


def _empty_payload(paper: PaperRecord) -> dict[str, Any]:
    return {
        "title": "",
        "year": "",
        "paper_type": "",
        "core_problem": "",
        "key_concepts": [],
        "theoretical_framework": [],
        "method_category": [],
        "concept_explanations": [],
        "method_explanations": [],
        "main_claim": "",
        "limitations": "",
        "cited_foundational_concepts": [],
        "paper_id": paper.paper_id,
        "file_name": paper.file_name,
    }


def _normalize_structured(data: dict[str, Any], paper: PaperRecord) -> dict[str, Any]:
    data.setdefault("title", "")
    data.setdefault("year", "")
    data.setdefault("paper_type", "")
    data.setdefault("core_problem", "")
    data.setdefault("key_concepts", [])
    data.setdefault("theoretical_framework", [])
    data.setdefault("method_category", [])
    data.setdefault("concept_explanations", [])
    data.setdefault("method_explanations", [])
    data.setdefault("main_claim", "")
    data.setdefault("limitations", "")
    data.setdefault("cited_foundational_concepts", [])

    for key in ("key_concepts", "theoretical_framework", "method_category", "cited_foundational_concepts"):
        value = data.get(key)
        if isinstance(value, str):
            data[key] = [value] if value.strip() else []
        elif not isinstance(value, list):
            data[key] = []

    for key in ("concept_explanations", "method_explanations"):
        value = data.get(key)
        if not isinstance(value, list):
            data[key] = []
            continue
        normalized_items: list[dict[str, str]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            normalized_items.append({str(k): str(v).strip() for k, v in item.items() if str(v).strip()})
        data[key] = normalized_items

    data["paper_id"] = paper.paper_id
    data["file_name"] = paper.file_name
    return data


def extract_paper_structures(
    papers: list[PaperRecord],
    config: PipelineConfig,
    client: OllamaClient,
) -> list[dict[str, Any]]:
    structured: list[dict[str, Any]] = []

    for paper in papers:
        sections = split_sections(paper.raw_text)
        user_prompt = EXTRACTION_USER_TEMPLATE.format(
            file_name=paper.file_name,
            abstract=(sections.get("abstract", "")[: config.max_abstract_chars]),
            introduction=(sections.get("introduction", "")[: config.max_intro_chars]),
            discussion=(sections.get("discussion", "")[: config.max_discussion_chars]),
        )

        payload: dict[str, Any] | None = None
        errors: list[str] = []

        for attempt in range(1, 4):
            attempt_user_prompt = user_prompt
            if attempt > 1:
                attempt_user_prompt = (
                    user_prompt
                    + "\n\nIMPORTANT: Your previous output was invalid JSON. "
                    "Return STRICT valid JSON only, with double quotes on all keys/strings."
                )
            try:
                raw = client.chat(
                    model=config.llm_model,
                    system=EXTRACTION_SYSTEM_PROMPT,
                    user=attempt_user_prompt,
                )
                payload = json.loads(_extract_json_blob(raw))
                break
            except Exception as exc:
                errors.append(f"attempt_{attempt}: {type(exc).__name__}: {exc}")

        if payload is None:
            LOGGER.warning(
                "Extraction failed for %s after retries. Using empty payload. %s",
                paper.file_name,
                " | ".join(errors),
            )
            structured.append(_empty_payload(paper))
            continue

        structured.append(_normalize_structured(payload, paper))

    return structured
