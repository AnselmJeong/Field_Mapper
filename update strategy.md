당신이 겪고 있는 문제는 기술적 문제가 아니라 **prompt abstraction level 문제**다.
현재 report가 “수박 겉핥기”가 되는 이유는 명확하다:

현재 synthesis prompt는
→ **field-level summary를 요구하고 있고**
→ **theory-level reconstruction을 요구하지 않고 있다.**

실제 당신이 원하는 것은 summary가 아니라:

> theory reconstruction
> conceptual genealogy
> intellectual conflict analysis

이다.

당신의 현재 report는 실제로 이런 수준에 머물러 있다:

> “The field is organized around recurring conceptual clusters…”

이 문장은 어떤 field에도 적용 가능한 generic 문장이다.

또한 현재 synthesis output도:

> “Competing paradigms are suggested by weakly connected clusters…”

같은 generic statement에 머물러 있다.

이것은 prompt가 “describe”를 요구하고 있기 때문이다.
당신은 “reconstruct”를 요구해야 한다.

------

# 핵심 해결 전략: 3-Layer Reconstruction Prompt Architecture

현재 구조:

paper → concept → summary

필요한 구조:

paper → theory unit → theory evolution → field narrative

즉, synthesis 단위를 concept cluster가 아니라 **theory lineage**로 바꿔야 한다.

------

# 새로운 Prompt Architecture (가장 중요한 부분)

다음 3단계로 synthesis prompt를 완전히 재설계해야 한다.

------

# STEP 1 — Theory Unit Reconstruction Prompt

목표: 개별 이론을 “완전한 intellectual object”로 복원

현재 cluster 예시:

cluster_id: 1
대표: DMN, triple network, functional connectivity 등

현재 시스템은 이것을 단순히:

"DMN is important"

수준으로 설명한다.

대신 아래 prompt를 사용해야 한다:

------

SYSTEM PROMPT:

You are reconstructing the intellectual structure of a scientific field.
Do NOT summarize.
Your task is to reconstruct each theoretical construct as a historical and mechanistic object.

For each theory, explain:

1. Origin problem — What specific empirical or theoretical problem led to this theory?
2. Core mechanism — What exactly does the theory claim happens mechanistically?
3. Novel insight — What did this theory explain that previous theories could not?
4. Key supporting evidence — What experimental findings made this theory credible?
5. Criticism — What objections were raised against it?
6. Evolution — How was this theory modified or replaced later?
7. Current status — Is it dominant, contested, or obsolete?

Write at least 800–1500 words per theory.

Use concrete mechanisms, not vague summaries.

------

USER INPUT:

cluster concepts
paper structured JSON
cluster papers

------

이 prompt는 완전히 다른 종류의 output을 만든다.

------

# STEP 2 — Theory Genealogy Reconstruction Prompt

이 단계는 가장 중요하다.

목표: 이론 간 인과 관계 재구성

현재 시스템은 단순히:

"Triple network model exists"

정도만 출력한다.

하지만 실제 중요한 질문은:

- 왜 triple network model이 등장했는가?
- 기존 DMN model의 어떤 문제를 해결하려 했는가?
- 어떤 empirical anomaly가 있었는가?

이를 위해 prompt는 다음처럼 바뀌어야 한다:

------

SYSTEM PROMPT:

Reconstruct the genealogy of theories in this field.

Do NOT summarize by topic.

Instead reconstruct:

- which theory came first
- what problem it failed to explain
- which theory emerged to solve that limitation
- how empirical findings forced theoretical revisions

Explain the causal chain between theories.

Use this format:

THEORY A → limitation → THEORY B → empirical conflict → THEORY C

Write at least 3000 words.

------

이 prompt는 summary가 아니라 intellectual history를 생성한다.

------

# STEP 3 — Mechanistic Integration Prompt

이 단계에서 narrative review 수준 output이 나온다.

------

SYSTEM PROMPT:

Integrate all reconstructed theories into a mechanistic explanation of the system.

Explain:

- how the brain network is hypothesized to operate mechanistically
- how dysfunction emerges mechanistically
- which competing models explain the same phenomenon differently
- what empirical results distinguish the models

Avoid generic statements.

Use explicit causal chains:

A causes B because X mechanism.

Write 4000–8000 words.

------

이 단계에서 진짜 narrative review 수준 output이 나온다.

------

# 가장 중요한 추가 변경: "Minimum Length Enforcement"

현재 LLM이 얕게 쓰는 이유는 length constraint가 없기 때문이다.

반드시 prompt에 포함:

Write at least 5000 words.
Short answers are unacceptable.

------

# Critical Change: Cluster → Theory decomposition

현재 cluster:

"Default mode network"
"Triple network model"
"Dynamic functional connectivity"

이것은 concept이지 theory가 아니다.

반드시 다음 단계 추가:

cluster → theory candidate extraction prompt

------

Prompt:

From the following concepts and papers, identify distinct theoretical models.

A theoretical model must:

- propose a mechanism
- explain a phenomenon
- be falsifiable

Return list of theories.

------

예:

- DMN self-referential theory
- Triple network model
- Dynamic functional connectivity model
- Graph theoretic modular brain model

이 단위로 reconstruction 해야 한다.

------

# 실제로 당신의 데이터에서 reconstruction 가능한 예

예: DMN theory

origin problem:

task-negative activity paradox

core claim:

brain has intrinsic activity supporting internal mentation

later conflict:

DMN hyperactivity in depression linked to rumination

later extension:

triple network model introduced salience network switching

이런 구조가 생성되어야 한다.

------

# Implementation change summary (핵심)

현재:

cluster → summary → report

새 구조:

cluster
→ theory extraction
→ theory reconstruction
→ genealogy reconstruction
→ mechanistic integration
→ report

------

# 가장 중요한 단일 prompt (추천)

이 prompt 하나만 바꿔도 품질이 극적으로 바뀐다:

------

SYSTEM:

You are reconstructing the intellectual evolution of a scientific field.

Do NOT summarize topics.

Instead reconstruct theories as causal explanatory systems.

Explain:

- why each theory was proposed
- what mechanism it proposed
- what empirical evidence supported it
- what criticisms it faced
- how later theories replaced or modified it

Write extremely detailed explanations.

Minimum length: 6000 words.

Generic summaries are unacceptable.

------

# 왜 이것이 효과적인가

현재 prompt는:

"Describe the field"

새 prompt는:

"Explain the intellectual evolution and mechanism"

LLM behavior가 완전히 달라진다.

------

# 결론

당신의 문제는 모델 문제가 아니라 prompt abstraction level 문제다.

현재 prompt: summary-level
필요한 prompt: theory reconstruction level

------

원한다면,
당신의 실제 cluster data를 기반으로

“완전히 새로운 synthesis prompt template (production-ready)”를
즉시 사용할 수 있는 형태로 작성해 줄 수 있다.