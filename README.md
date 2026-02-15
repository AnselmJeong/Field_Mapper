# FieldMapper

`PRD.md`와 `implementation.md`를 기반으로 구현한 로컬 Python CLI 앱입니다.

## Features
- PDF 폴더 ingestion 및 section 분리 (abstract/introduction/methods/results/discussion)
- Ollama 기반 paper-level structured extraction
- concept embedding + similarity clustering
- field-level synthesis
- `raw_report.md`(구조형) + `report.md`(review-style 서술형) + `concept_map.png` 자동 생성

## Run
1. Ollama 실행 및 모델 준비
   - LLM 예: `mistral-large-3:675b-cloud`
   - Embedding: `qwen3-embedding:latest` (고정)
   - CLI에서 `ollama list` 기반으로 LLM 모델 선택 가능
   - 서술형 `report.md` 언어(Korean/English) 선택 가능
2. 프로젝트 루트에서 실행

```bash
uv run main.py
```

또는 설치형 엔트리포인트:

```bash
uv run fieldmapper
```

## Output
지정한 output 디렉토리에 생성:
- `papers_structured.json`
- `citation_registry.json` (paper_id -> 통일 citation 매핑)
- `concept_method_kb.json` (개념/이론/방법 설명 지식베이스)
- `concept_vectors.json`
- `concept_clusters.json`
- `cluster_edges.json`
- `field_report_sections.json`
- `raw_report.md`
- `report.md`
- `concept_map.png`
- `concept_map.html` (sigma.js interactive graph)
