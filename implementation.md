# 0. 전체 전략 요약

핵심 설계 원칙은 세 가지다:

1. **문서를 한 번에 LLM에 넣지 않는다**
   → section 단위로 분할
2. **요약 → 통합 → 상위 구조 생성의 3단계 추상화 유지**
3. **Vector DB는 clustering 보조 도구로만 사용**
   → graph DB처럼 쓰지 않는다

------

# 1. 기술 스택 확정

### Runtime

- Python 3.12+

### LLM

- Ollama local model (예: glm-5:cloud, ollama list에서 받아온 모델 중에서 선택 가능)
- Embedding: `qwen3-embedding` (Ollama)

### Libraries

- pdfplumber (텍스트 추출)
- langchain-text-splitters (선택, 더 좋은 것이 있나?)
- lancedb
- numpy
- scikit-learn (clustering 보조)
- networkx
- matplotlib
- tqdm

------

# 2. 디렉토리 구조

```
fieldmapper/
│
├── main.py
├── config.yaml
│
├── ingestion/
│   ├── pdf_loader.py
│   ├── section_parser.py
│
├── extraction/
│   ├── paper_extractor.py
│   ├── prompts.py
│
├── embedding/
│   ├── embedder.py
│   ├── vector_store.py
│
├── clustering/
│   ├── concept_cluster.py
│
├── synthesis/
│   ├── field_synthesizer.py
│
├── visualization/
│   ├── concept_map.py
│
└── output/
```

------

# 3. 단계별 구현 상세

------

## STEP 1: PDF Ingestion

### 1.1 pdf_loader.py

기능:

- 폴더 내 모든 PDF 로드
- 파일명 → metadata로 저장

출력 구조:

```
[
  {
    "file_name": "",
    "raw_text": ""
  },
  ...
]
```

------

### 1.2 section_parser.py

단순 rule-based 접근:

- "abstract"
- "introduction"
- "methods"
- "results"
- "discussion"

regex 기반 split.

출력:

```
{
  "abstract": "",
  "introduction": "",
  "methods": "",
  "results": "",
  "discussion": ""
}
```

주의:
원문이 완벽히 분리되지 않아도 된다.
우리는 introduction + discussion 중심으로 쓸 것.

------

# STEP 2: Paper-Level Structured Extraction

### 2.1 extraction/paper_extractor.py

입력:

- abstract
- introduction
- discussion

LLM prompt는 반드시 extraction-only mode.

------

### Prompt 구조 (핵심)

SYSTEM:

"You are an information extraction engine.
Do not summarize loosely.
Extract structured conceptual information only."

USER:

논문 텍스트 일부 + 아래 JSON 형식

반환 형식:

```
Return ONLY valid JSON.
Do not add commentary.
```

------

### Extraction 전략

LLM 입력은 다음만 포함:

- abstract
- introduction (최대 2000 tokens)
- discussion (최대 2000 tokens)

길면 chunking:

- intro를 2–3 chunk로 나눠
- 각각 key concept 추출 후 merge

------

### Output 저장

```
papers_structured.json
```

------

# STEP 3: Embedding + Vector DB

------

## 3.1 embedder.py

Ollama embedding endpoint 사용.

각 concept string에 대해:

```
embedding = ollama.embeddings(
    model="qwen3-embedding",
    prompt=concept
)
```

------

## 3.2 vector_store.py

Chroma 예시:

- collection = "concepts"
- metadata: paper_id, year

저장 대상:

- key_concepts
- theoretical_framework

core_problem은 제외해도 무방.

------

# STEP 4: Concept Clustering

목표:
개별 concept를 상위 cluster로 통합

------

## 4.1 clustering/concept_cluster.py

절차:

1. 모든 embedding 불러오기
2. numpy matrix 구성
3. cosine similarity matrix 계산

```
similarity = cosine_similarity(matrix)
```

1. threshold 기반 연결 (예: 0.82 이상)
2. graph connected components → cluster 생성

scikit-learn HDBSCAN도 가능하나
threshold + connected component 방식이 단순하고 안정적이다.

------

### 출력 구조

```
[
  {
    "cluster_id": 1,
    "representative_label": "",
    "concepts": [],
    "paper_count": n
  }
]
```

representative_label은 LLM에게 cluster concepts를 주고 한 줄 요약하게 하면 됨.

------

# STEP 5: Field-Level Synthesis

------

## 5.1 synthesis/field_synthesizer.py

입력:

- papers_structured.json
- concept_clusters.json

LLM에게 다음을 요청:

1. 핵심 개념 taxonomy 구성
2. 중심 패러다임 정의
3. 경쟁 패러다임 도출
4. 방법론 축 분류
5. 최근 확장 영역
6. unresolved question

중요:

cluster 기반으로 reasoning하도록 유도해야 한다.

프롬프트에:

"Use the following concept clusters as the structural backbone."

------

출력:

```
field_report_sections.json
```

------

# STEP 6: Report Generation

------

## report.md 생성

sections.json 기반으로 Markdown 조립.

자동 생성:

```
# Executive Overview

# Concept Taxonomy

# Theoretical Axes

# Methodological Landscape

# Controversies

# Research Trajectory

# Open Problems
```

------

# STEP 7: Concept Map Visualization

------

## visualization/concept_map.py

Graph 구성:

- node = cluster_id
- size = paper_count
- edge weight = cluster 간 co-occurrence

co-occurrence 계산:

- 동일 논문에서 두 cluster 등장하면 +1

networkx:

```
G = nx.Graph()
G.add_node(...)
G.add_edge(..., weight=...)
```

matplotlib layout:

- spring_layout
- node_size proportional to paper_count

출력:
`concept_map.png`

------

# STEP 8: CLI 설계

main.py:

```
python main.py --input ./papers --output ./output
```

Pipeline 순차 실행.

진행률 표시:
tqdm 사용.

------

# 9. 메모리 / 성능 전략

- extraction 단계에서 intermediate JSON 저장
- embedding은 concept 단위이므로 부담 낮음
- 50편 × 평균 concept 10개 → 500 vectors
  → 매우 가벼움

LLM 호출이 가장 느림.

------

# 10. 예상 개발 타임라인

Week 1:

- ingestion
- extraction 안정화

Week 2:

- embedding + clustering
- report generation

Week 3:

- concept map
- prompt refinement
- 결과 품질 개선

------

# 11. 가장 중요한 품질 결정 요인

성공 여부는 3가지에 달려 있다:

1. Extraction prompt 품질
2. Clustering threshold 튜닝
3. Synthesis prompt 설계

기술적 난이도는 낮다.
지적 품질은 prompt 설계에 달려 있다.

------

원한다면 다음 단계로:

- 실제 extraction prompt 초안 작성
- synthesis prompt 초안 작성
- clustering threshold 설계 기준
- hallucination 방지 전략

중 무엇을 먼저 구체화할지 결정하자.