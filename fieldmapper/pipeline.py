from __future__ import annotations

import re
from pathlib import Path

from tqdm import tqdm

from fieldmapper.clustering.concept_cluster import build_cooccurrence_edges, cluster_concepts
from fieldmapper.config import PipelineConfig
from fieldmapper.embedding.embedder import collect_concepts, embed_concepts
from fieldmapper.embedding.vector_store import persist_vectors
from fieldmapper.extraction.ollama_client import OllamaClient
from fieldmapper.extraction.paper_extractor import extract_paper_structures
from fieldmapper.ingestion.pdf_loader import load_pdf_texts
from fieldmapper.io_utils import ensure_dir, read_json, write_json
from fieldmapper.reporting.citations import build_citation_registry, render_bibtex_from_registry
from fieldmapper.reporting.knowledge_base import build_concept_method_knowledge_base
from fieldmapper.reporting.openalex import enrich_report_with_openalex
from fieldmapper.reporting.report_generator import generate_report_markdown, write_report
from fieldmapper.reporting.review_writer import generate_review_report_markdown
from fieldmapper.synthesis.field_synthesizer import synthesize_field_report
from fieldmapper.synthesis.theory_extractor import build_theory_genealogy, extract_theory_units
from fieldmapper.visualization.concept_map import render_concept_map, render_concept_map_html

EMBEDDING_MODEL = "qwen3-embedding:latest"


def _model_slug(model_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", model_name.strip().lower())
    slug = slug.strip("._-")
    return slug or "model"


def _write_report_variants(
    out_dir: Path,
    content: str,
    llm_model: str,
    write_model_tagged_report: bool,
    write_report_bib: bool,
    citation_registry: dict[str, dict[str, str]] | None = None,
    bib_content_override: str = "",
) -> dict[str, Path]:
    outputs: dict[str, Path] = {}
    bib_content = ""
    if write_report_bib:
        bib_content = bib_content_override or render_bibtex_from_registry(citation_registry or {})

    report_path = out_dir / "report.md"
    write_report(report_path, content)
    outputs["report"] = report_path
    if bib_content:
        report_bib_path = report_path.with_suffix(".bib")
        report_bib_path.write_text(bib_content, encoding="utf-8")
        outputs["report_bib"] = report_bib_path

    if write_model_tagged_report:
        tagged_report_path = out_dir / f"report.{_model_slug(llm_model)}.md"
        write_report(tagged_report_path, content)
        outputs["report_model_tagged"] = tagged_report_path
        if bib_content:
            tagged_bib_path = tagged_report_path.with_suffix(".bib")
            tagged_bib_path.write_text(bib_content, encoding="utf-8")
            outputs["report_model_tagged_bib"] = tagged_bib_path

    return outputs


def run_pipeline(config: PipelineConfig) -> dict[str, Path]:
    out_dir = ensure_dir(config.output_dir)
    client = OllamaClient(base_url=config.ollama_url)

    # ── Stage 1: Ingestion ──────────────────────────────────────────────────
    papers = load_pdf_texts(config.input_dir)
    if not papers:
        raise ValueError(f"No PDF files found in: {config.input_dir}")

    # ── Stage 2: Paper-level extraction ────────────────────────────────────
    structured = extract_paper_structures(papers, config=config, client=client)
    structured_path = out_dir / "papers_structured.json"
    write_json(structured_path, structured)

    citation_registry = build_citation_registry(structured)
    citation_registry_path = out_dir / "citation_registry.json"
    write_json(citation_registry_path, citation_registry)

    concept_method_kb = build_concept_method_knowledge_base(structured)
    concept_method_kb_path = out_dir / "concept_method_kb.json"
    write_json(concept_method_kb_path, concept_method_kb)

    # ── Stage 3: Embedding + clustering ────────────────────────────────────
    concept_rows = collect_concepts(structured)
    embedded_rows = []
    for row in tqdm(concept_rows, desc="Embedding concepts"):
        embedded_rows.extend(embed_concepts([row], model=EMBEDDING_MODEL, client=client))

    vectors_path = persist_vectors(embedded_rows, out_dir)

    clusters = cluster_concepts(embedded_rows, similarity_threshold=config.similarity_threshold)
    clusters_path = out_dir / "concept_clusters.json"
    write_json(clusters_path, clusters)

    edges = build_cooccurrence_edges(clusters)
    edges_path = out_dir / "cluster_edges.json"
    write_json(edges_path, edges)

    # ── Stage A: Theory Unit Extraction ────────────────────────────────────
    print("Extracting theory units...")
    theory_units = extract_theory_units(
        papers=structured,
        clusters=clusters,
        concept_method_kb=concept_method_kb,
        client=client,
        llm_model=config.llm_model,
    )
    theory_units_path = out_dir / "theory_units.json"
    write_json(theory_units_path, theory_units)

    # ── Stage B: Theory Genealogy ───────────────────────────────────────────
    print("Building theory genealogy...")
    theory_genealogy = build_theory_genealogy(
        theory_units=theory_units,
        papers=structured,
        client=client,
        llm_model=config.llm_model,
    )
    theory_genealogy_path = out_dir / "theory_genealogy.json"
    write_json(theory_genealogy_path, theory_genealogy)

    # ── Stage C: Field-Level Synthesis (sequential, cross-aware) ───────────
    print("Synthesizing field report sections...")
    synthesis = synthesize_field_report(
        papers=structured,
        clusters=clusters,
        llm_model=config.llm_model,
        client=client,
        concept_method_kb=concept_method_kb,
        theory_units=theory_units,
        theory_genealogy=theory_genealogy,
    )
    synthesis_path = out_dir / "field_report_sections.json"
    write_json(synthesis_path, synthesis)

    # ── Stage D: Monograph Assembly ─────────────────────────────────────────
    raw_report = generate_report_markdown(
        synthesis=synthesis,
        clusters=clusters,
        concept_method_kb=concept_method_kb,
        theory_units=theory_units,
        theory_genealogy=theory_genealogy,
    )
    raw_report_path = out_dir / "raw_report.md"
    write_report(raw_report_path, raw_report)

    # ── Stage E: Sequential Narrative Rewrite ──────────────────────────────
    print("Rewriting narrative sections...")
    review_report = generate_review_report_markdown(
        synthesis=synthesis,
        clusters=clusters,
        raw_report=raw_report,
        concept_method_kb=concept_method_kb,
        citation_registry_map=citation_registry,
        report_language=config.report_language,
        llm_model=config.llm_model,
        client=client,
    )

    # ── Citation enrichment via OpenAlex ───────────────────────────────────
    enriched = enrich_report_with_openalex(review_report, citation_registry)
    final_report = enriched["report_text"]
    openalex_matches_path = out_dir / "openalex_citation_matches.json"
    openalex_unresolved_path = out_dir / "openalex_unresolved_citations.json"
    openalex_meta_path = out_dir / "openalex_resolution_meta.json"
    write_json(openalex_matches_path, enriched["matches"])
    write_json(openalex_unresolved_path, enriched["unresolved"])
    write_json(
        openalex_meta_path,
        {
            "api_key_present": enriched.get("api_key_present", False),
            "stats": enriched.get("stats", {}),
        },
    )

    report_outputs = _write_report_variants(
        out_dir=out_dir,
        content=final_report,
        llm_model=config.llm_model,
        write_model_tagged_report=config.write_model_tagged_report,
        write_report_bib=config.write_report_bib,
        citation_registry=citation_registry,
        bib_content_override=enriched.get("bibtex", ""),
    )

    # ── Visualization ───────────────────────────────────────────────────────
    map_path = out_dir / "concept_map.png"
    render_concept_map(clusters, edges, map_path)
    map_html_path = out_dir / "concept_map.html"
    render_concept_map_html(clusters, edges, map_html_path)

    outputs: dict[str, Path] = {
        "papers_structured": structured_path,
        "citation_registry": citation_registry_path,
        "concept_method_kb": concept_method_kb_path,
        "vectors": vectors_path,
        "clusters": clusters_path,
        "edges": edges_path,
        "theory_units": theory_units_path,
        "theory_genealogy": theory_genealogy_path,
        "sections": synthesis_path,
        "raw_report": raw_report_path,
        "openalex_citation_matches": openalex_matches_path,
        "openalex_unresolved_citations": openalex_unresolved_path,
        "openalex_resolution_meta": openalex_meta_path,
        "concept_map": map_path,
        "concept_map_html": map_html_path,
    }
    outputs.update(report_outputs)
    return outputs


def regenerate_report_from_output(
    output_dir: Path,
    llm_model: str,
    report_language: str = "English",
    ollama_url: str = "http://127.0.0.1:11434",
    write_model_tagged_report: bool = True,
    write_report_bib: bool = True,
) -> dict[str, Path]:
    out_dir = output_dir.expanduser().resolve()
    if not out_dir.exists():
        raise ValueError(f"Output directory does not exist: {out_dir}")

    synthesis_path = out_dir / "field_report_sections.json"
    clusters_path = out_dir / "concept_clusters.json"
    concept_method_kb_path = out_dir / "concept_method_kb.json"

    missing: list[str] = []
    for p in (synthesis_path, clusters_path, concept_method_kb_path):
        if not p.exists():
            missing.append(p.name)
    if missing:
        missing_list = ", ".join(missing)
        raise ValueError(f"Cannot regenerate report: missing required files in output directory: {missing_list}")

    synthesis = read_json(synthesis_path)
    clusters = read_json(clusters_path)
    concept_method_kb = read_json(concept_method_kb_path)

    # Load theory units and genealogy if available (optional — new outputs only)
    theory_units_path = out_dir / "theory_units.json"
    theory_genealogy_path = out_dir / "theory_genealogy.json"
    theory_units: list[dict] = read_json(theory_units_path) if theory_units_path.exists() else []
    theory_genealogy: dict = read_json(theory_genealogy_path) if theory_genealogy_path.exists() else {}

    # Always regenerate raw_report from synthesis so headings use the new 8-section structure.
    # generate_report_markdown() falls back to old synthesis keys (executive_overview, etc.)
    # so this is backwards-compatible with output folders produced by the old pipeline.
    raw_report_path = out_dir / "raw_report.md"
    raw_report = generate_report_markdown(
        synthesis=synthesis,
        clusters=clusters,
        concept_method_kb=concept_method_kb,
        theory_units=theory_units or None,
        theory_genealogy=theory_genealogy or None,
    )
    write_report(raw_report_path, raw_report)

    citation_registry_path = out_dir / "citation_registry.json"
    citation_registry: dict[str, dict[str, str]] = {}
    if citation_registry_path.exists():
        citation_registry = read_json(citation_registry_path)
    else:
        structured_path = out_dir / "papers_structured.json"
        if structured_path.exists():
            structured = read_json(structured_path)
            citation_registry = build_citation_registry(structured)
            write_json(citation_registry_path, citation_registry)

    client = OllamaClient(base_url=ollama_url)
    review_report = generate_review_report_markdown(
        synthesis=synthesis,
        clusters=clusters,
        raw_report=raw_report,
        concept_method_kb=concept_method_kb,
        citation_registry_map=citation_registry,
        report_language=report_language,
        llm_model=llm_model,
        client=client,
    )
    enriched = enrich_report_with_openalex(review_report, citation_registry)
    final_report = enriched["report_text"]
    openalex_matches_path = out_dir / "openalex_citation_matches.json"
    openalex_unresolved_path = out_dir / "openalex_unresolved_citations.json"
    openalex_meta_path = out_dir / "openalex_resolution_meta.json"
    write_json(openalex_matches_path, enriched["matches"])
    write_json(openalex_unresolved_path, enriched["unresolved"])
    write_json(
        openalex_meta_path,
        {
            "api_key_present": enriched.get("api_key_present", False),
            "stats": enriched.get("stats", {}),
        },
    )

    report_outputs = _write_report_variants(
        out_dir=out_dir,
        content=final_report,
        llm_model=llm_model,
        write_model_tagged_report=write_model_tagged_report,
        write_report_bib=write_report_bib,
        citation_registry=citation_registry,
        bib_content_override=enriched.get("bibtex", ""),
    )

    outputs: dict[str, Path] = {
        "sections": synthesis_path,
        "clusters": clusters_path,
        "concept_method_kb": concept_method_kb_path,
        "raw_report": raw_report_path,
        "openalex_citation_matches": openalex_matches_path,
        "openalex_unresolved_citations": openalex_unresolved_path,
        "openalex_resolution_meta": openalex_meta_path,
    }
    if citation_registry_path.exists():
        outputs["citation_registry"] = citation_registry_path
    if theory_units_path.exists():
        outputs["theory_units"] = theory_units_path
    if theory_genealogy_path.exists():
        outputs["theory_genealogy"] = theory_genealogy_path
    outputs.update(report_outputs)
    return outputs
