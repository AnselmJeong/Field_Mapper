from __future__ import annotations

from pathlib import Path

from fieldmapper.io_utils import write_json


def persist_vectors(rows: list[dict], output_dir: Path) -> Path:
    """Persist vectors to JSON for portability.

    A production setup can swap this with LanceDB/Chroma integration.
    """
    path = output_dir / "concept_vectors.json"
    write_json(path, rows)
    return path
