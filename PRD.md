# PRD.md

## 1. Product Overview

**제품명 (가칭):** FieldMapper
**목적:**
연구자가 하나의 폴더(20–50편의 review + original article PDF)를 입력하면,
해당 field의 개념 구조, 이론적 축, 방법론적 분화, 연구 흐름을 정리한:

- 구조화된 보고서 (Markdown 또는 PDF)
- 개념도 (Concept Map 이미지)

를 자동 생성하는 개인용 로컬 도구.

이 시스템은 단순 요약기가 아니라:

> Field-level conceptual structure reconstruction tool

이다.

------

## 2. Target User

- 개인 연구자
- 특정 분야에 빠르게 진입하려는 학자
- Narrative review를 준비 중인 연구자

비목표:

- 다중 사용자 SaaS
- 대규모 citation 분석 플랫폼
- 실시간 collaborative 시스템

------

## 3. Core Problem

현재 literature reading workflow는:

- 논문을 많이 읽어야 함
- 구조화 비용이 큼
- narrative로 재조직하는 데 시간이 오래 걸림

해결 목표:

> 폴더 → 구조화된 지적 지도 + 보고서

------

## 4. Scope (V1)

### Input

- 로컬 폴더 경로
- PDF 파일 20–50편

### Output

1. `report.md`
2. `concept_map.png`
3. (optional) `structured_data.json`

------

## 5. Functional Requirements

### 5.1 Document Ingestion

- PDF → 텍스트 추출
- Section segmentation:
  - Abstract
  - Introduction
  - Methods
  - Results
  - Discussion
- Figure / Table caption extraction (optional)

------

### 5.2 Paper-Level Structured Extraction

각 논문에 대해 LLM(Ollama local model) 사용:

출력 구조(JSON):

```
{
  "title": "",
  "year": "",
  "paper_type": "review | original",
  "core_problem": "",
  "key_concepts": [],
  "theoretical_framework": [],
  "method_category": [],
  "main_claim": "",
  "limitations": "",
  "cited_foundational_concepts": []
}
```

주의:

- 긴 요약 금지
- 최대 400–600 tokens 제한

------

### 5.3 Vector Storage

Embedding model:

- Ollama qwen3-embedding

Vector DB:

- LanceDB 또는 Chroma (local only)

Index 대상:

- key_concepts
- theoretical_framework
- core_problem

목적:

- Concept clustering
- Similarity 기반 그룹화

------

### 5.4 Concept Clustering

절차:

1. 모든 key_concepts 수집
2. embedding 생성
3. cosine similarity 기반 clustering
4. threshold 기반 cluster merge

출력:

```
Cluster 1: Predictive coding / Bayesian inference / Hierarchical models
Cluster 2: Inflammation / Cytokines / Neuroimmune hypothesis
Cluster 3: ...
```

------

### 5.5 Field-Level Synthesis (LLM 단계 2)

입력:

- 모든 paper JSON
- concept clusters

LLM에게 다음을 생성하게 한다:

1. Core Concept Taxonomy
2. Major Theoretical Axes
3. Methodological Axes
4. Dominant Paradigm
5. Competing Paradigms
6. Emerging Branches
7. Unresolved Questions

이 단계는 field-level abstraction 단계이다.

------

### 5.6 Concept Map Generation

Graph 구성:

- Node = concept cluster
- Edge = co-occurrence strength
- Weight = cluster 간 공출현 빈도

Python:

- networkx
- matplotlib

출력:

- concept_map.png

그래프 요구사항:

- 중심 cluster 강조
- branch 구조 시각화
- label 가독성 확보

------

### 5.7 Final Report Generation

파일명: `report.md`

구조:

# Executive Overview

- Field 정의
- 핵심 질문

# Concept Taxonomy

- Cluster 기반 정리

# Major Theoretical Models

- 각 모델 설명
- 상호 관계

# Methodological Landscape

- 실험적 접근
- 계산적 접근
- 임상 연구

# Controversies

- competing claims

# Research Trajectory

- 시간 흐름
- 최근 확장 영역

# Open Problems

- empirical gap
- theoretical gap
- translational bottleneck

길이 목표:

- 5–10 pages equivalent

------

## 6. Non-Functional Requirements

- 100% 로컬 실행
- 인터넷 연결 불필요
- 50편 기준 30–60분 내 처리 완료
- 메모리 사용 < 16GB

------

## 7. Architecture Overview

```
/input_folder
        ↓
PDF parser
        ↓
Paper-level LLM extraction
        ↓
JSON aggregation
        ↓
Embedding (qwen3-embedding)
        ↓
Vector DB (LanceDB/Chroma)
        ↓
Clustering
        ↓
Field synthesis (LLM)
        ↓
Report + Concept Map
```

------

## 8. Risks

1. LLM hallucination
   - mitigation: extraction prompt 엄격화
2. Concept redundancy
   - mitigation: similarity threshold tuning
3. Over-compression
   - mitigation: cluster size 제한
4. 긴 문서 처리 시 context overflow
   - mitigation: section 단위 분할

------

## 9. Future Extensions (Out of Scope V1)

- Citation network 분석
- Temporal evolution graph
- Interactive UI
- Multi-field comparison
- 논쟁 자동 탐지기

------

## 10. Success Criteria

성공 판단 기준:

- 사용자가 report만 읽고 field 구조를 설명할 수 있음
- Narrative review outline 작성 시간이 50% 감소
- 핵심 이론 축이 명확히 구분됨
- Research frontier가 분명히 드러남

------

## 11. Prompt Philosophy

LLM은:

- 요약자가 아니다
- 구조 생성기다

Extraction prompt는 “정보 추출 모드”
Synthesis prompt는 “field theorist 모드”

------

## 12. MVP Boundary

V1에서는 다음만 구현:

- PDF ingestion
- Paper-level structured extraction
- Concept clustering
- Final structured report
- Static concept map

UI는 CLI로 충분하다.

------

원한다면 다음 단계로:

- 실제 파일 구조 설계
- CLI 인터페이스 설계
- Ollama prompt template 구체 작성
- Clustering 알고리즘 선택 기준

중 어느 것을 먼저 정교화할지 결정하자.