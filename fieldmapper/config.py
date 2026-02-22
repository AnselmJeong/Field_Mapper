from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class PipelineConfig:
    input_dir: Path
    output_dir: Path
    llm_model: str = "mistral-large-3:675b-cloud"
    ollama_url: str = "http://127.0.0.1:11434"
    report_language: str = "English"
    write_model_tagged_report: bool = True
    write_report_bib: bool = True
    similarity_threshold: float = 0.82
    max_intro_chars: int = 9000
    max_discussion_chars: int = 9000
    max_abstract_chars: int = 4000


@dataclass(slots=True)
class PaperRecord:
    paper_id: str
    file_name: str
    raw_text: str
