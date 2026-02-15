from __future__ import annotations

from pathlib import Path

import pdfplumber

from fieldmapper.config import PaperRecord


def load_pdf_texts(input_dir: Path) -> list[PaperRecord]:
    papers: list[PaperRecord] = []
    pdf_paths = sorted(input_dir.glob("*.pdf"))

    for idx, pdf_path in enumerate(pdf_paths, start=1):
        pages_text: list[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    pages_text.append(page_text)

        papers.append(
            PaperRecord(
                paper_id=f"paper_{idx:03d}",
                file_name=pdf_path.name,
                raw_text="\n\n".join(pages_text),
            )
        )

    return papers
