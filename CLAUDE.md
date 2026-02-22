# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run (interactive CLI)
uv run main.py
uv run fieldmapper   # installed entrypoint

# Install dependencies
uv sync

# Add a dependency
uv add <package>
```

There are no tests currently in this project.

## Architecture

FieldMapper is a local CLI pipeline that takes a folder of academic PDFs and produces a structured field report (`report.md`), a raw structured intermediate (`raw_report.md`), and a concept map (`concept_map.png` + `concept_map.html`).

**All LLM calls go through Ollama** running locally at `http://127.0.0.1:11434`. The embedding model is hardcoded to `qwen3-embedding:latest`; the LLM is selected interactively at runtime (default: `mistral-large-3:675b-cloud`). The only optional internet dependency is the OpenAlex API for citation verification (reads API key from `.env`).

### Pipeline stages (`fieldmapper/pipeline.py`)

`run_pipeline()` orchestrates the following stages sequentially; each stage writes intermediate JSON to a timestamped subfolder under `<input_dir>/output/<YYYYMMDD_HHMMSS>/`:

| Stage | Module | Output file(s) |
|---|---|---|
| 1 – PDF ingestion | `ingestion/pdf_loader.py`, `ingestion/section_parser.py` | — (in-memory `PaperRecord`) |
| 2 – Structured extraction | `extraction/paper_extractor.py` | `papers_structured.json` |
| Citation registry | `reporting/citations.py` | `citation_registry.json` |
| Concept/method KB | `reporting/knowledge_base.py` | `concept_method_kb.json` |
| 3 – Embedding + clustering | `embedding/embedder.py`, `clustering/concept_cluster.py` | `concept_vectors.json`, `concept_clusters.json`, `cluster_edges.json` |
| **A – Theory Unit Extraction** | `synthesis/theory_extractor.py` | `theory_units.json` |
| **B – Theory Genealogy** | `synthesis/theory_extractor.py` | `theory_genealogy.json` |
| **C – Field Synthesis** (sequential, cross-aware) | `synthesis/field_synthesizer.py` | `field_report_sections.json` |
| **D – Monograph Assembly** | `reporting/report_generator.py` | `raw_report.md` |
| **E – Narrative Rewrite** (sequential, accumulated context) | `reporting/review_writer.py`, `reporting/openalex.py` | `report.md`, `report.bib` |
| Visualization | `visualization/concept_map.py` | `concept_map.png`, `concept_map.html` |

`regenerate_report_from_output()` re-runs from Stage C onward using cached JSON. It is backwards-compatible: if `theory_units.json`/`theory_genealogy.json` are absent (old output folders), it falls back gracefully.

### Report section structure (8 sections)
```
# Field Landscape
# Conceptual Architecture
# Theory Genealogy
# Major Theoretical Models
# Methodological Landscape
# Theoretical Fault Lines
# Research Trajectory
# Open Problems
```
Per-section instructions and word targets are in `synthesis/field_synthesizer.py::SECTION_INSTRUCTIONS` and `SECTION_WORD_TARGETS`. Target total: 15,000–25,000 words.

### Key data structures

- **`PaperRecord`** (`config.py`): `paper_id`, `file_name`, `raw_text` — intermediate after PDF load.
- **`papers_structured.json`**: list of dicts with keys `title`, `year`, `paper_type`, `core_problem`, `key_concepts`, `theoretical_framework`, `method_category`, `concept_explanations`, `method_explanations`, `main_claim`, `limitations`, `cited_foundational_concepts`, `paper_id`, `file_name`.
- **`concept_clusters.json`**: list of cluster dicts — `cluster_id`, `representative_label`, `concepts`, `paper_count`, `paper_ids`.
- **`PipelineConfig`** (`config.py`): all runtime settings; similarity threshold controls clustering granularity (Balanced: 0.82, Fast: 0.86, Detailed: 0.78).

### Citation pipeline

Citations flow through two layers:
1. **`reporting/citations.py`** — builds `citation_registry` from `papers_structured` using filename convention `YEAR - Author(s) - Title.pdf`. Produces `(Author, Year)` canonical forms and BibTeX.
2. **`reporting/openalex.py`** — after report text is generated, parses inline citations (parenthetical, narrative, backtick patterns), queries the OpenAlex Works API to verify and hyperlink them, and produces a `References` section + `.bib` sidecar. Controlled by the `OPENALEX_API_KEY` env var or `.env` file entry (`OPENALEX_API_KEY`, `OPENALEX_APIKEY`, `api_key`, or `OPENALEX_KEY`).

### Clustering algorithm

`cluster_concepts()` uses cosine similarity on `qwen3-embedding` vectors + graph connected-components (not HDBSCAN or k-means). The `similarity_threshold` is the single tuning knob.

### Input filename convention

The citation registry parser expects filenames in the format:
```
YEAR - Author et al. - Title.pdf
```
The first-author name is extracted from the second `" - "` segment.
