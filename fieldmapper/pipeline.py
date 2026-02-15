from __future__ import annotations

from pathlib import Path

from tqdm import tqdm

from fieldmapper.clustering.concept_cluster import build_cooccurrence_edges, cluster_concepts
from fieldmapper.config import PipelineConfig
from fieldmapper.embedding.embedder import collect_concepts, embed_concepts
from fieldmapper.embedding.vector_store import persist_vectors
from fieldmapper.extraction.ollama_client import OllamaClient
from fieldmapper.extraction.paper_extractor import extract_paper_structures
from fieldmapper.ingestion.pdf_loader import load_pdf_texts
from fieldmapper.io_utils import ensure_dir, write_json
from fieldmapper.reporting.citations import build_citation_registry
from fieldmapper.reporting.knowledge_base import build_concept_method_knowledge_base
from fieldmapper.reporting.report_generator import generate_report_markdown, write_report
from fieldmapper.reporting.review_writer import generate_review_report_markdown
from fieldmapper.synthesis.field_synthesizer import synthesize_field_report
from fieldmapper.visualization.concept_map import render_concept_map, render_concept_map_html

EMBEDDING_MODEL = "qwen3-embedding:latest"


def run_pipeline(config: PipelineConfig) -> dict[str, Path]:
    out_dir = ensure_dir(config.output_dir)
    client = OllamaClient(base_url=config.ollama_url)

    papers = load_pdf_texts(config.input_dir)
    if not papers:
        raise ValueError(f"No PDF files found in: {config.input_dir}")

    structured = extract_paper_structures(papers, config=config, client=client)
    structured_path = out_dir / "papers_structured.json"
    write_json(structured_path, structured)

    citation_registry = build_citation_registry(structured)
    citation_registry_path = out_dir / "citation_registry.json"
    write_json(citation_registry_path, citation_registry)

    concept_method_kb = build_concept_method_knowledge_base(structured)
    concept_method_kb_path = out_dir / "concept_method_kb.json"
    write_json(concept_method_kb_path, concept_method_kb)

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

    synthesis = synthesize_field_report(structured, clusters, llm_model=config.llm_model, client=client)
    synthesis_path = out_dir / "field_report_sections.json"
    write_json(synthesis_path, synthesis)

    raw_report = generate_report_markdown(synthesis, clusters, concept_method_kb=concept_method_kb)
    raw_report_path = out_dir / "raw_report.md"
    write_report(raw_report_path, raw_report)

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
    report_path = out_dir / "report.md"
    write_report(report_path, review_report)

    map_path = out_dir / "concept_map.png"
    render_concept_map(clusters, edges, map_path)
    map_html_path = out_dir / "concept_map.html"
    render_concept_map_html(clusters, edges, map_html_path)

    return {
        "papers_structured": structured_path,
        "citation_registry": citation_registry_path,
        "concept_method_kb": concept_method_kb_path,
        "vectors": vectors_path,
        "clusters": clusters_path,
        "edges": edges_path,
        "sections": synthesis_path,
        "raw_report": raw_report_path,
        "report": report_path,
        "concept_map": map_path,
        "concept_map_html": map_html_path,
    }
