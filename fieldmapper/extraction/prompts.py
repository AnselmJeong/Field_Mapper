EXTRACTION_SYSTEM_PROMPT = (
    "You are an information extraction engine for scientific papers. "
    "Extract conceptual structure only and return strict JSON. "
    "Do not include explanations or markdown."
)

EXTRACTION_USER_TEMPLATE = """
Extract the following JSON structure from this paper text.
Use concise phrases. If unknown, use an empty string or empty array.

Target schema:
{{
  "title": "",
  "year": "",
  "paper_type": "review | original",
  "core_problem": "",
  "key_concepts": [],
  "theoretical_framework": [],
  "method_category": [],
  "concept_explanations": [
    {{
      "concept": "",
      "explanation": "",
      "mechanism": "",
      "supporting_evidence": "",
      "criticisms_or_limits": ""
    }}
  ],
  "method_explanations": [
    {{
      "method": "",
      "what_it_measures_or_tests": "",
      "how_it_is_used_in_this_paper": "",
      "strengths": "",
      "limitations": ""
    }}
  ],
  "main_claim": "",
  "limitations": "",
  "cited_foundational_concepts": []
}}

Constraints:
- Keep strings concise but information-dense.
- concept_explanations: up to 12 items.
- method_explanations: up to 10 items.
- Use only claims grounded in the provided sections.

Paper file name: {file_name}

Abstract:
{abstract}

Introduction:
{introduction}

Discussion:
{discussion}

Return ONLY valid JSON.
""".strip()

SYNTHESIS_SYSTEM_PROMPT = (
    "You are reconstructing the intellectual evolution of a scientific field. "
    "Do NOT summarize topics. Reconstruct theories as historical and mechanistic explanatory systems. "
    "Generic summaries are unacceptable."
)

SYNTHESIS_USER_TEMPLATE = """
Input structured papers JSON:
{papers_json}

Input concept clusters JSON:
{clusters_json}

Generate a JSON object with these keys:
- executive_overview
- concept_taxonomy
- major_theoretical_models
- methodological_landscape
- controversies
- research_trajectory
- open_problems

Critical objective:
- Reconstruct theory units, theory genealogy, and mechanistic integration.
- Do not produce topic-level summaries.

Hard constraints:
- Minimum total length across all section values: 6000 words.
- Short answers are unacceptable.
- Every section must contain concrete causal language ("A led to B because X mechanism").
- Preserve evidence traceability with paper/year anchors when possible.

Section requirements:
1) executive_overview
- Explain the core field-defining problem and why earlier explanations were insufficient.
- Provide a high-level causal map of theory evolution (early model -> limitation -> successor model).
- Include the dominant unresolved tensions.

2) concept_taxonomy
- This is not a glossary. Group concepts by theoretical role:
  - explanatory primitives
  - mechanism variables
  - measurement/operational proxies
  - outcome/phenotype-level constructs
- Explain how these concept groups interact in causal chains.

3) major_theoretical_models
- Reconstruct each major theory as a full intellectual object:
  - Origin problem
  - Core mechanism
  - Novel explanatory gain vs predecessors
  - Key supporting evidence
  - Main criticisms
  - Later revisions/replacements
  - Current status (dominant/contested/declining)
- Include at least 4 distinct theories when evidence allows.
- For each theory, write substantial detail, not bullet fragments.

4) methodological_landscape
- Explain how methods enabled or constrained theory claims.
- Compare methods by inferential power, blind spots, and reproducibility risks.
- Explicitly connect methodological choices to theoretical disputes.

5) controversies
- Map concrete conflict structures:
  - claim A vs claim B
  - what data each side relies on
  - where interpretations diverge
  - what evidence would adjudicate the dispute
- Avoid vague "there are debates" wording.

6) research_trajectory
- Reconstruct the genealogy:
  THEORY A -> limitation/anomaly -> THEORY B -> empirical conflict -> THEORY C ...
- Explain why transitions happened, not just chronological listing.

7) open_problems
- Define unresolved mechanistic questions precisely.
- For each open problem, specify:
  - what is unknown
  - why current models fail
  - what decisive empirical test could resolve it

Return ONLY valid JSON.
""".strip()

SECTION_SYNTHESIS_SYSTEM_PROMPT = (
    "You are reconstructing the intellectual evolution of a scientific field. "
    "Do NOT summarize vaguely. Use concrete mechanisms, conflicts, and evidence anchors. "
    "Write analytically and avoid generic filler."
)

SECTION_SYNTHESIS_USER_TEMPLATE = """
Target section: {section_name}
Target key: {section_key}
Preferred language: English

Evidence bundle (JSON):
{evidence_json}

Writing requirements:
- Focus only on the target section.
- Use specific claims grounded in the evidence bundle.
- Include at least 2 explicit cause-effect chains.
- Mention concrete theory/model names and cite in `Author, Year` style only.
- Do NOT expose internal IDs such as `paper_XXX`.
- Do not output bullets unless needed for clarity.
- Target length: 500-900 words.

Return ONLY plain text for this section body (no markdown heading, no JSON).
""".strip()

REVIEW_WRITER_SYSTEM_PROMPT = (
    "You are an expert narrative review writer and historian of science. "
    "Transform structured synthesis into deeply analytical scholarly prose in Markdown. "
    "Do not output shallow summaries."
)

REVIEW_WRITER_USER_TEMPLATE = """
You will receive:
1) Structured section data (JSON)
2) Concept clusters (JSON)
3) A raw outline report in markdown

Your task:
- Write a human-readable review-style report in Korean.
- Maintain analytical rigor and conceptual clarity.
- Do not dump JSON or key-value lists.
- Use cohesive paragraphs and transitions.
- Keep section headings exactly:
  # Executive Overview
  # Concept Taxonomy
  # Major Theoretical Models
  # Methodological Landscape
  # Controversies
  # Research Trajectory
  # Open Problems

Writing requirements:
- Reconstruct theory genealogy (which model emerged, what limitation triggered revision, what replaced it).
- Explain relationships between concepts and paradigms using explicit causal statements.
- Compare competing models with concrete contrasts and adjudicating evidence.
- Discuss methodological tradeoffs and limitations as drivers of theoretical disagreement.
- Expand each section substantially (target 700-1200 words per section).
- End each section with 2-3 forward-looking insights.
- Avoid repeating identical phrases across sections.
- No code block, no raw JSON, no Python-style dict/list rendering.
- Generic, high-level summaries are unacceptable.

Input JSON (structured synthesis):
{synthesis_json}

Input JSON (concept clusters):
{clusters_json}

Raw report draft:
{raw_report}

Return ONLY markdown text for the final narrative report.
""".strip()

REVIEW_REWRITE_ONLY_USER_TEMPLATE = """
Rewrite the following raw markdown report into a polished Korean narrative review article.

Rules:
- Keep section headings exactly as-is.
- Convert list-like fragments into coherent prose paragraphs.
- Do not output JSON, dict/list literals, or bullet-heavy outlines.
- Preserve factual content; do not invent unsupported claims.
- In each section, explain implications and connect ideas across paragraphs.

Raw markdown:
{raw_report}

Return ONLY markdown text.
""".strip()

REVIEW_SECTION_REWRITE_USER_TEMPLATE = """
Rewrite one section of a raw review outline into polished {language} academic prose.

Rules:
- Keep the heading exactly unchanged.
- Turn bullet fragments and list-like content into coherent, publication-quality paragraphs.
- Do not output JSON, dict/list literals, or code blocks.
- Preserve factual claims from the source; do not fabricate.
- Reconstruct argument structure, not descriptive listing.
- Explain mechanisms, causal links, and theory-to-theory transitions where relevant.
- Include concrete contrasts between competing explanations.
- Each section must be substantially expanded (target: 700-1200 words).
- Generic statements (e.g., "many studies show...", "there were many changes") are unacceptable.
- Conclude with 2-3 forward-looking insight sentences grounded in the section's analysis.
- Citation format must be consistent: use only `(Author, Year)` style in-text.
- Never expose internal IDs such as `paper_XXX`.

Supplemental context for this section:
{supplemental_context}

Citation registry:
{citation_registry}

If the section contains dossier entries with `### <name>` items:
- You must explicitly explain every listed item by name at least once.
- Use dossier evidence (mechanism/evidence/limitations) to build detailed paragraphs.

Section markdown:
{section_markdown}

Return ONLY markdown for this section.
""".strip()
