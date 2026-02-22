# FieldMapper Monograph-Quality Upgrade Plan

## 진단: 왜 현재 결과물이 "수박 겉핥기"인가

코드와 실제 output(`report.md`)을 대조 분석한 결과, 문제는 모델 품질이 아니라 **구조적 설계 결함** 세 가지다.

### 결함 1: 7개 섹션이 동일한 evidence에서 독립 생성된다
`synthesize_field_report()`는 모든 섹션에 동일한 `evidence` 딕셔너리(top_theories, top_methods, papers 리스트)를 라우팅한다. Executive Overview가 "attractor network theory"를 소개하면 Concept Taxonomy, Major Theoretical Models, Research Trajectory도 같은 출발점에서 같은 내용을 독립적으로 재도출한다. **섹션 간 narrative continuity가 없다.**

### 결함 2: synthesis 단계에서 가장 풍부한 데이터가 누락된다
`concept_method_kb`의 theory dossier (메커니즘, 증거, 비판, 인용 논문 목록) 는 `generate_report_markdown()`의 raw_report 조립에만 쓰인다. **synthesis LLM은 이 데이터를 전혀 받지 않는다.** LLM은 compact paper 리스트와 top_theories 카운트만 보고 글을 쓴다.

### 결함 3: 분량 상한이 monograph 수준을 원천 봉쇄한다
- Synthesis: 500–900 words/section × 7 = 최대 6,300 단어
- Review rewrite: 700–1,200 words/section × 7 = 최대 8,400 단어
- Monograph 한 챕터: 통상 5,000–15,000 단어

결국 전체 report가 아무리 잘 써도 학술지 리뷰 논문 수준(8,000–10,000 단어)을 넘지 못한다. 현재 `update strategy.md`가 진단한 "prompt abstraction level 문제"는 부분적으로 맞지만, 더 근본적으로는 **아키텍처 문제**다.

---

## 새로운 아키텍처: 5-Stage Synthesis Pipeline

현재 구조:
```
clusters + papers → [7개 섹션 독립 생성] → raw_report → [7개 섹션 독립 rewrite] → report.md
```

새 구조:
```
clusters + papers + concept_method_kb
  → [A] Theory Unit Extraction      → theory_units.json
  → [B] Theory Genealogy            → theory_genealogy.json
  → [C] Deep Section Synthesis      → field_report_sections_v2.json  (sequential, cross-aware)
  → [D] Monograph Assembly          → raw_report_v2.md
  → [E] Sequential Narrative Rewrite → report.md
```

단계 A, B가 신규다. C, D, E는 기존 모듈을 확장·수정한다.

---

## 변경 범위 (기존 코드 최대 재활용)

| 위치 | 변경 유형 | 핵심 내용 |
|---|---|---|
| `fieldmapper/synthesis/theory_extractor.py` | **신규** | Stage A, B 구현 |
| `fieldmapper/synthesis/field_synthesizer.py` | **수정** | Stage C: sequential 생성 + theory_units/genealogy 주입 |
| `fieldmapper/reporting/report_generator.py` | **수정** | Stage D: 8섹션 구조, theory_genealogy 포함 |
| `fieldmapper/reporting/review_writer.py` | **수정** | Stage E: accumulated_context 전달, 분량 상향 |
| `fieldmapper/extraction/prompts.py` | **수정** | 신규 프롬프트 4개 추가, 기존 target 길이 상향 |
| `fieldmapper/pipeline.py` | **수정** | Stage A, B 호출 + 다운스트림 데이터 패스 |

`ingestion/`, `embedding/`, `clustering/`, `reporting/citations.py`, `reporting/openalex.py`, `visualization/`, `config.py`, `cli.py`는 **변경 없음**.

---

## Stage A: Theory Unit Extraction

### 목적
클러스터와 논문 데이터에서 "이론 단위(theory unit)"를 식별하고 각각을 완전한 intellectual object로 재구성한다. concept cluster ≠ theory unit. "Default mode network"는 개념이지만 "DMN self-referential processing hypothesis"는 이론이다.

### 신규 파일: `fieldmapper/synthesis/theory_extractor.py`

```python
def extract_theory_units(
    papers: list[dict],
    clusters: list[dict],
    concept_method_kb: dict,
    client: OllamaClient,
    llm_model: str,
) -> list[dict]:
    """
    Output schema per theory unit:
    {
      "theory_id": str,
      "name": str,
      "origin_problem": str,          # 어떤 empirical/theoretical 문제에서 등장했나
      "core_mechanism": str,          # 무엇을 mechanistically 주장하는가
      "predecessor_theories": [str],  # 무엇을 대체/확장했나
      "novel_explanatory_gain": str,  # 선행 이론 대비 무엇을 새로 설명했나
      "key_evidence": [str],          # 어떤 실험적 근거가 있나
      "main_criticisms": [str],       # 어떤 비판을 받았나
      "successor_or_revision": str,   # 어떻게 수정되거나 대체됐나
      "current_status": str,          # dominant / contested / synthesized / obsolete
      "paper_anchors": [str],         # (Author, Year) 스타일
      "cluster_ids": [int],           # 연관 cluster IDs
    }
    """
```

### 프롬프트 설계 (THEORY_UNIT_EXTRACTION_SYSTEM_PROMPT)

```
You are identifying discrete theoretical models within a scientific field.

A theoretical model must:
1. Propose a specific mechanism explaining a phenomenon
2. Make predictions that are in principle falsifiable
3. Have a traceable intellectual origin (what problem it addressed)

Do NOT conflate theoretical labels with theories:
- "functional connectivity" = measurement concept, NOT a theory
- "Default Mode Network" = anatomical concept, NOT a theory
- "DMN suppression failure hypothesis of depression" = a theory

From the provided cluster concepts, paper summaries, and knowledge base dossiers,
identify the distinct theoretical models in this field.

Return a JSON array of theory unit objects.
```

### 입력 구성
- `clusters` (상위 20개)
- `concept_method_kb["theories"]` (dossier 전체)
- `papers` compact (상위 30개, title/year/core_problem/main_claim/theoretical_framework)

### 출력
`theory_units.json` — 보통 4–12개 theory unit

---

## Stage B: Theory Genealogy

### 목적
theory unit들 간의 인과 관계를 재구성한다. 어떤 이론이 어떤 한계 때문에 어떤 이론을 낳았는가. 시간 축의 intellectual history.

### 함수: `build_theory_genealogy(theory_units, papers, client, llm_model) -> dict`

```python
"""
Output schema:
{
  "narrative": str,           # 3000–5000 단어의 genealogy narrative (plain text)
  "causal_chains": [          # 구조화된 인과 체인 목록
    {
      "from_theory": str,
      "limitation": str,
      "to_theory": str,
      "trigger_mechanism": str,   # 어떤 empirical finding이 전환을 촉발했나
      "approximate_period": str,
    }
  ],
  "dominant_paradigm_shifts": [str],  # 필드 전체 패러다임 전환 목록
}
"""
```

### 프롬프트 설계 (THEORY_GENEALOGY_SYSTEM_PROMPT)

```
You are reconstructing the intellectual genealogy of a scientific field.

Rules:
- Temporal direction is strict: only earlier theories can influence later ones.
- Each theoretical transition must be causally explained:
  WHY did the field move from Theory A to Theory B?
  What empirical anomaly, methodological advance, or theoretical limitation forced this?
- Do NOT produce a chronological list. Produce a CAUSAL CHAIN narrative.
- Format: THEORY A [limitation X] → THEORY B [empirical conflict Y] → THEORY C ...
- Write at least 3000 words.
- Use (Author, Year) citations anchored in the provided theory units.
```

### 출력
`theory_genealogy.json`

---

## Stage C: Deep Section Synthesis (기존 field_synthesizer.py 수정)

### 핵심 변경: Sequential Generation with Accumulated Context

현재 `synthesize_field_report()`는 7개 섹션을 독립 생성한다. 수정 후:

```python
def synthesize_field_report(
    papers, clusters, concept_method_kb,
    theory_units, theory_genealogy,   # NEW
    llm_model, client,
) -> dict:
    evidence = _build_evidence_index(papers, clusters, concept_method_kb, theory_units, theory_genealogy)
    payload = {}
    context_so_far = ""   # NEW: accumulated narrative context

    for key, name in SECTION_SPECS:
        section_text = _generate_section(
            section_key=key,
            section_name=name,
            evidence=evidence,
            context_so_far=context_so_far,   # NEW
            llm_model=llm_model,
            client=client,
        )
        payload[key] = section_text
        context_so_far += f"\n\n--- {name} (already written) ---\n{section_text[:1500]}"

    return payload
```

### `_build_evidence_index()` 수정
- `concept_method_kb["theories"]` (dossier 전체) 포함
- `theory_units` 포함
- `theory_genealogy["causal_chains"]` + `theory_genealogy["dominant_paradigm_shifts"]` 포함

### `_section_evidence()` 수정
각 섹션에 맞는 theory_units 하위집합과 genealogy 발췌를 라우팅:
- `major_theoretical_models`: theory_units 전체 + method dossiers
- `controversies`: theory_units의 competing 쌍 + criticisms
- `research_trajectory`: genealogy causal_chains + timeline
- `executive_overview`: genealogy narrative 요약 + dominant_paradigm_shifts

### 새 Section Specs (8개, 기존 7개에서 확장)

```python
SECTION_SPECS = [
    ("field_landscape",         "Field Landscape"),           # 기존 executive_overview 대체
    ("conceptual_architecture", "Conceptual Architecture"),   # 기존 concept_taxonomy 강화
    ("theory_genealogy_section","Theory Genealogy"),          # 신규 전용 섹션
    ("major_theoretical_models","Major Theoretical Models"),
    ("methodological_landscape","Methodological Landscape"),
    ("theoretical_fault_lines", "Theoretical Fault Lines"),   # 기존 controversies 대체
    ("research_trajectory",     "Research Trajectory"),
    ("open_problems",           "Open Problems"),
]
```

### 분량 목표 상향

기존 `SECTION_SYNTHESIS_USER_TEMPLATE`의 "Target length: 500-900 words"를:
- 주요 섹션 (Major Theoretical Models, Theory Genealogy, Methodological Landscape): **2000–3500 words**
- 나머지 섹션: **1200–2000 words**
- 전체 합계 목표: **12,000–20,000 words**

---

## Stage D: Monograph Assembly (기존 report_generator.py 수정)

### `generate_report_markdown()` 수정

현재: synthesis output을 단순 조립
수정: theory_units dossier를 "심층 이론 프로파일" 섹션으로 포함, theory_genealogy narrative를 Theory Genealogy 섹션 아래 삽입

```python
def generate_report_markdown(synthesis, clusters, concept_method_kb, theory_units, theory_genealogy):
    # ... 기존 taxonomy_lines ...

    # Theory Genealogy 섹션에 causal chains를 구조화하여 삽입
    genealogy_chains = _render_causal_chains(theory_genealogy.get("causal_chains", []))

    # Major Theoretical Models 섹션에 theory_units 각각의 deep dossier 삽입
    theory_profiles = _render_theory_profiles(theory_units)
```

### 출력 파일명: `raw_report_v2.md`
(기존 `raw_report.md` 유지하여 "Report only" 재생성 모드 호환 보장)

---

## Stage E: Sequential Narrative Rewrite (기존 review_writer.py 수정)

### `generate_review_report_markdown()` 수정

핵심 변경: **accumulated_context를 각 섹션 rewrite에 전달**

```python
def generate_review_report_markdown(...):
    # ...
    accumulated_context = ""

    for heading, body in sections:
        supplemental_context = _build_supplemental(heading, theory_dossiers, method_dossiers, accumulated_context)

        rewritten = _rewrite_one_section(
            heading=heading,
            body=body,
            supplemental_context=supplemental_context,
            ...
        )
        rewritten_sections.append(rewritten)
        # 다음 섹션에 이 섹션의 핵심 내용을 전달
        accumulated_context += f"\n\n=== {heading} 핵심 요약 ===\n{rewritten[:2000]}"
```

### `REVIEW_SECTION_REWRITE_USER_TEMPLATE` 수정
- `accumulated_context` 파라미터 추가
- 지시: "이전 섹션에서 이미 다룬 내용과 겹치지 않도록 새로운 관점과 세부 내용으로 확장하라"
- target 분량: **2000–3000 words** (현재 700-1200에서 상향)

### theory_dossiers를 Major Theoretical Models에만 한정하지 않기
현재 `generate_review_report_markdown()`에서:
```python
if heading == "# Major Theoretical Models":
    supplemental_context = theory_context  # 현재: 이 섹션만 dossier 받음
```
수정: 섹션별로 관련 theory_units 하위집합을 supplemental로 전달

---

## 새 프롬프트 목록 (prompts.py 추가/수정)

### 신규 프롬프트 (4개)

**1. `THEORY_UNIT_EXTRACTION_SYSTEM_PROMPT`**
위 Stage A 참조

**2. `THEORY_UNIT_EXTRACTION_USER_TEMPLATE`**
```
Concept clusters (JSON):
{clusters_json}

Knowledge base theory dossiers (JSON):
{kb_theories_json}

Paper summaries (JSON):
{papers_compact_json}

Identify discrete theoretical models. Return JSON array.
```

**3. `THEORY_GENEALOGY_SYSTEM_PROMPT`**
위 Stage B 참조

**4. `THEORY_GENEALOGY_USER_TEMPLATE`**
```
Theory units (JSON):
{theory_units_json}

Paper timeline (JSON):
{timeline_json}

Reconstruct the causal genealogy. Return JSON with keys: narrative, causal_chains, dominant_paradigm_shifts.
```

### 기존 프롬프트 수정 (2개)

**`SECTION_SYNTHESIS_USER_TEMPLATE`** — 신규 파라미터 추가:
- `context_so_far`: 이전 섹션 요약 (1500자 이내)
- `theory_units_json`: 섹션 관련 theory unit 하위집합
- `genealogy_excerpt`: 관련 genealogy 발췌
- Target length 상향: 주요 섹션 2000–3500 words
- 지시에 "이전 섹션 context를 보고 중복 피하라" 추가

**`REVIEW_SECTION_REWRITE_USER_TEMPLATE`** — 파라미터 추가:
- `accumulated_context`: 이전 섹션 핵심 요약 (2000자 이내)
- Target length 상향: 2000–3000 words
- 지시에 cross-reference 요구 추가

---

## pipeline.py 변경

```python
from fieldmapper.synthesis.theory_extractor import extract_theory_units, build_theory_genealogy

def run_pipeline(config):
    # ... 기존 단계 A-F (ingestion ~ clustering) ...

    # NEW: Theory Unit Extraction
    theory_units = extract_theory_units(
        papers=structured,
        clusters=clusters,
        concept_method_kb=concept_method_kb,
        client=client,
        llm_model=config.llm_model,
    )
    theory_units_path = out_dir / "theory_units.json"
    write_json(theory_units_path, theory_units)

    # NEW: Theory Genealogy
    theory_genealogy = build_theory_genealogy(
        theory_units=theory_units,
        papers=structured,
        client=client,
        llm_model=config.llm_model,
    )
    theory_genealogy_path = out_dir / "theory_genealogy.json"
    write_json(theory_genealogy_path, theory_genealogy)

    # MODIFIED: synthesis receives theory_units + genealogy
    synthesis = synthesize_field_report(
        papers=structured,
        clusters=clusters,
        concept_method_kb=concept_method_kb,
        theory_units=theory_units,
        theory_genealogy=theory_genealogy,
        llm_model=config.llm_model,
        client=client,
    )
    # ... 이하 동일 ...
```

### `regenerate_report_from_output()` 호환성
- `theory_units.json`, `theory_genealogy.json`이 있으면 로드
- 없으면 기존 방식으로 fallback (backwards compatible)

---

## 새 섹션 구조와 각 섹션의 역할

각 섹션이 **이전 섹션과 명확히 다른 역할**을 갖도록 mandate를 재설계한다.

### 1. Field Landscape (기존 Executive Overview)
- **역할**: 이 field의 존재 이유. 어떤 현상이 기존 이론으로 설명되지 않아 이 분야가 생겼나.
- **금지**: 이론 이름 나열, 결론 요약
- **요구**: 핵심 explanatory problem 1개를 800단어로 깊이 설명

### 2. Conceptual Architecture (기존 Concept Taxonomy)
- **역할**: 개념의 위계와 역할. 어떤 개념이 explanatory primitive이고 어떤 것이 operational proxy인가.
- **금지**: 개념 glossary, 사전식 나열
- **요구**: 개념 간 인과 관계 명시, 측정 개념과 이론 개념의 구분

### 3. Theory Genealogy (신규)
- **역할**: 이론 간 인과 계보. 어떤 한계가 다음 이론을 낳았나.
- **내용**: `theory_genealogy["narrative"]`를 기반으로 서술
- **형식**: THEORY A → [limitation] → THEORY B → [anomaly] → THEORY C 구조가 prose에 녹아 있어야 함

### 4. Major Theoretical Models (유지, 깊이 강화)
- **역할**: 각 theory unit의 완전한 intellectual object 재구성
- **이전 섹션과의 차이**: Genealogy가 "흐름"을 다뤘다면, 이 섹션은 각 이론을 "정지해서 해부"
- **요구**: theory_units 각각에 대해 origin → mechanism → evidence → criticism → current status 구조

### 5. Methodological Landscape (유지, 강화)
- **역할**: 방법론이 이론 논쟁을 어떻게 형성하고 제약하는가
- **이전 섹션과의 차이**: 이론 이름 반복 금지, 방법론-이론 연결에 집중
- **요구**: "방법 X가 이론 Y의 검증을 불가능하게 만들었다" 수준의 분석

### 6. Theoretical Fault Lines (기존 Controversies)
- **역할**: 현재 진행 중인 실질적 논쟁의 구조 분석
- **이전 섹션과의 차이**: Genealogy가 "해소된 긴장"을 다뤘다면, 이 섹션은 "현재 미해소 긴장"
- **형식**: Claim A vs Claim B, 각 측의 data, 무엇이 adjudicate할 수 있나

### 7. Research Trajectory (유지, 강화)
- **역할**: 시간 축 변화 + 현재 확장 frontier
- **이전 섹션과의 차이**: Genealogy가 "왜" 변했나를 다뤘다면, 이 섹션은 "어디로" 가는가
- **요구**: 현재 진행 중인 연구 방향 3–5개 명시

### 8. Open Problems (유지, 강화)
- **역할**: 미해결 mechanistic 문제 정밀 정의
- **요구**: 각 open problem에 대해 (a) 무엇이 모르는가, (b) 왜 현재 모델이 실패하는가, (c) 어떤 decisive empirical test가 해결할 수 있나

---

## 예상 출력 품질 변화

| 지표 | 현재 | 목표 |
|---|---|---|
| 총 단어 수 | ~8,000–10,000 | ~20,000–30,000 |
| 섹션 간 개념 반복률 | 높음 (같은 이론 3–4회) | 낮음 (각 섹션이 다른 각도) |
| Theory reconstruction depth | 이론 이름 + 1–2문장 | origin/mechanism/evidence/criticism 완전 재구성 |
| Causal chain 명시 | 부분적 | 전 섹션에 걸쳐 explicit |
| Cross-section coherence | 없음 | 각 섹션이 이전 섹션 위에 구축 |

---

## 구현 순서 (의존성 기준)

### Phase 1: 프롬프트 + 신규 모듈 (의존성 없음)
1. `prompts.py`에 `THEORY_UNIT_EXTRACTION_*`, `THEORY_GENEALOGY_*` 추가
2. `fieldmapper/synthesis/theory_extractor.py` 신규 작성

### Phase 2: Synthesis 수정 (Phase 1 완료 후)
3. `field_synthesizer.py`: accumulated context, theory_units/genealogy 주입, 분량 상향
4. `report_generator.py`: 8섹션 구조, theory_profiles 렌더링

### Phase 3: Review writer 수정 (Phase 2 완료 후)
5. `review_writer.py`: sequential accumulated_context, 분량 상향

### Phase 4: Pipeline 통합 (Phase 1–3 완료 후)
6. `pipeline.py`: Stage A, B 추가, 다운스트림 데이터 패스
7. `regenerate_report_from_output()`: theory_units/genealogy fallback

### Phase 5: 검증
8. 기존 output 폴더(`output/20260216_222917/`)를 "Report only" 모드로 재실행하여 비교

---

## 재활용되는 기존 코드 (변경 없음)

- `ingestion/` 전체 (pdf_loader, section_parser)
- `embedding/` 전체 (embedder, vector_store)
- `clustering/concept_cluster.py`
- `reporting/citations.py`
- `reporting/openalex.py`
- `reporting/knowledge_base.py`
- `visualization/concept_map.py`
- `config.py`, `cli.py`, `io_utils.py`
- `extraction/ollama_client.py`
- `extraction/paper_extractor.py`
- 기존 `EXTRACTION_SYSTEM_PROMPT`, `EXTRACTION_USER_TEMPLATE`

---

## 핵심 설계 원칙 (변경하지 말 것)

- **100% local**: OpenAlex가 optional internet인 것 외 모든 LLM 호출은 Ollama
- **intermediate JSON 보존**: 각 신규 단계도 JSON 파일로 persist
- **backwards compatible**: "Report only" 모드에서 theory_units/genealogy 없으면 기존 경로로 fallback
- **단일 LLM 호출로 처리 불가한 것은 분리**: theory_units 추출과 genealogy 구축은 각각 별도 LLM 호출
