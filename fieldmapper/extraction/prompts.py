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

# ---------------------------------------------------------------------------
# Theory Unit Extraction (Stage A)
# ---------------------------------------------------------------------------

THEORY_UNIT_EXTRACTION_SYSTEM_PROMPT = (
    "You are identifying discrete theoretical models within a scientific field. "
    "A theoretical model must: (1) propose a specific mechanism, "
    "(2) make predictions that are in principle falsifiable, "
    "(3) have a traceable intellectual origin — what problem it was created to address. "
    "Do NOT conflate measurement concepts with theories. "
    "'Functional connectivity' is a measurement concept. "
    "'Predictive coding hypothesis' is a theory. "
    "Return only valid JSON. No commentary, no markdown."
)

THEORY_UNIT_EXTRACTION_USER_TEMPLATE = """
Below are concept clusters, knowledge-base theory dossiers, and paper summaries
from a scientific corpus. Your task is to identify all discrete theoretical models
that appear across the corpus.

For each theory unit, extract:
- name: precise name of the theoretical model/framework/hypothesis
- origin_problem: the specific empirical or theoretical problem that motivated this theory
- core_mechanism: what exactly this theory claims happens, step by step
- predecessor_theories: list of theory names this one extended, replaced, or reacted to
- novel_explanatory_gain: what this theory explained that predecessors could not
- key_evidence: list of specific findings or experiments that support this theory
- main_criticisms: list of the most substantive objections raised against it
- successor_or_revision: how this theory was later modified, extended, or replaced
- current_status: one of "dominant", "contested", "synthesized", "declining", "foundational"
- paper_anchors: list of (Author, Year) citation strings from the corpus
- cluster_ids: list of cluster_id integers this theory relates to

Return a JSON array of theory unit objects.
Include 4 to 12 theory units — only genuine theoretical models, not concepts.

Concept clusters:
{clusters_json}

Knowledge base theory dossiers:
{kb_theories_json}

Paper summaries:
{papers_compact_json}

Return ONLY valid JSON array.
""".strip()

# ---------------------------------------------------------------------------
# Theory Genealogy (Stage B)
# ---------------------------------------------------------------------------

THEORY_GENEALOGY_SYSTEM_PROMPT = (
    "You are reconstructing the intellectual genealogy of a scientific field. "
    "Your task is NOT a chronological list — it is a CAUSAL NARRATIVE. "
    "Temporal direction is strict: only earlier theories can influence later ones. "
    "Every theoretical transition must be causally explained: "
    "WHY did the field move from Theory A to Theory B? "
    "What empirical anomaly, methodological advance, or theoretical contradiction forced it? "
    "Return only valid JSON. No commentary, no markdown."
)

THEORY_GENEALOGY_USER_TEMPLATE = """
Given the theory units and publication timeline below, reconstruct the causal
genealogy of theoretical development in this field.

Return a JSON object with exactly these keys:
- narrative: a continuous prose text of 2500-4000 words reconstructing the intellectual
  evolution. Use explicit causal language: "X failed to explain Y, which led researchers
  to propose Z because...". Use (Author, Year) citations throughout.
- causal_chains: a JSON array of objects, each with:
    - from_theory: name of predecessor theory
    - limitation: what specific gap or failure drove the transition
    - to_theory: name of successor theory
    - trigger_mechanism: what empirical finding or logical argument made the transition happen
    - approximate_period: e.g. "early 2000s", "post-2010"
- dominant_paradigm_shifts: a JSON array of strings, each describing one major
  field-level paradigm shift (2-5 items)

Theory units:
{theory_units_json}

Publication timeline:
{timeline_json}

Return ONLY valid JSON with keys: narrative, causal_chains, dominant_paradigm_shifts.
""".strip()

# ---------------------------------------------------------------------------
# Section Synthesis (field_synthesizer.py)
# ---------------------------------------------------------------------------

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

Return ONLY valid JSON.
""".strip()

SECTION_SYNTHESIS_SYSTEM_PROMPT = (
    "You are reconstructing the intellectual evolution of a scientific field. "
    "Do NOT summarize vaguely. Use concrete mechanisms, conflicts, and evidence anchors. "
    "Write analytically. Generic filler and section-to-section repetition are unacceptable."
)

SECTION_SYNTHESIS_USER_TEMPLATE = """
Target section: {section_name}
Target key: {section_key}

Previously written sections — DO NOT repeat the same claims, examples, or theory descriptions:
{context_so_far}

Theory units identified in this corpus:
{theory_units_json}

Theory genealogy data:
{genealogy_excerpt}

Evidence bundle (JSON):
{evidence_json}

Section-specific requirements:
{section_instructions}

General writing requirements:
- Write in English.
- Avoid bullet lists unless strictly necessary for parallel structure.
- Cite with (Author, Year) style only. Never wrap citations in backticks.
- Temporal direction is strict: newer work may refine or challenge older work, never the reverse.
- Do NOT expose internal IDs such as paper_XXX.
- Do NOT repeat content from the previously written sections shown above.
- Include at least 3 explicit cause-effect statements.
- Short, vague, or generic answers are unacceptable.
- Target word count: {word_target}

Return ONLY plain text for this section body (no markdown heading, no JSON wrapper).
""".strip()

# ---------------------------------------------------------------------------
# Review / Narrative Rewrite (review_writer.py)
# ---------------------------------------------------------------------------

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
- Write a human-readable review-style report.
- Maintain analytical rigor and conceptual clarity.
- Do not dump JSON or key-value lists.
- Use cohesive paragraphs and transitions.
- Keep section headings exactly:
  # Field Landscape
  # Conceptual Architecture
  # Theory Genealogy
  # Major Theoretical Models
  # Methodological Landscape
  # Theoretical Fault Lines
  # Research Trajectory
  # Open Problems

Writing requirements:
- Reconstruct theory genealogy (which model emerged, what limitation triggered revision, what replaced it).
- Explain relationships between concepts and paradigms using explicit causal statements.
- Compare competing models with concrete contrasts and adjudicating evidence.
- Discuss methodological tradeoffs and limitations as drivers of theoretical disagreement.
- Temporal order must be explicit and non-contradictory: older work can influence newer work only.
- Prohibit reversed chronology statements.
- Expand each section substantially (target 2000-3000 words per section).
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
Rewrite the following raw markdown report into a polished narrative review article.

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

Sections already written (avoid repeating the same theories, examples, or arguments):
{accumulated_context}

Rules:
- Keep the heading exactly unchanged.
- Turn bullet fragments and list-like content into coherent, publication-quality paragraphs.
- Do not output JSON, dict/list literals, or code blocks.
- Preserve factual claims from the source; do not fabricate.
- Reconstruct argument structure, not descriptive listing.
- Explain mechanisms, causal links, and theory-to-theory transitions where relevant.
- Keep chronology directionally valid: only newer studies can refine or revise older studies.
- Never claim that an earlier-year paper was refined/extended/updated by a later-year predecessor.
- If year ordering cannot be verified from section content, avoid directional evolution verbs.
- Include concrete contrasts between competing explanations.
- Each section must be substantially expanded (target: 2000-3000 words).
- Generic statements (e.g., "many studies show...", "there were many changes") are unacceptable.
- Conclude with 2-3 forward-looking insight sentences grounded in the section's analysis.
- Citation format must be consistent: use only (Author, Year) style in-text.
- Never wrap citations in backticks.
- Never expose internal IDs such as paper_XXX.

Supplemental context for this section:
{supplemental_context}

Citation registry:
{citation_registry}

If the section contains dossier entries with ### <name> items:
- You must explicitly explain every listed item by name at least once.
- Use dossier evidence (mechanism/evidence/limitations) to build detailed paragraphs.

Section markdown:
{section_markdown}

Return ONLY markdown for this section.
""".strip()
