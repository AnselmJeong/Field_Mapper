from __future__ import annotations

from collections.abc import Iterable

from fieldmapper.extraction.ollama_client import OllamaClient


def collect_concepts(structured_papers: list[dict]) -> list[dict]:
    rows: list[dict] = []
    seen = set()
    for paper in structured_papers:
        paper_id = paper.get("paper_id", "")
        year = str(paper.get("year", ""))
        concept_fields = [
            ("key_concepts", paper.get("key_concepts", [])),
            ("theoretical_framework", paper.get("theoretical_framework", [])),
            ("core_problem", [paper.get("core_problem", "")]),
        ]

        for source, concepts in concept_fields:
            for concept in concepts:
                concept_text = str(concept).strip()
                if not concept_text:
                    continue

                row_key = (paper_id, concept_text.lower(), source)
                if row_key in seen:
                    continue
                seen.add(row_key)

                rows.append(
                    {
                        "paper_id": paper_id,
                        "year": year,
                        "source": source,
                        "concept": concept_text,
                    }
                )
    return rows


def embed_concepts(rows: Iterable[dict], model: str, client: OllamaClient) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        emb = client.embeddings(model, row["concept"])
        enriched = dict(row)
        enriched["embedding"] = emb
        out.append(enriched)
    return out
