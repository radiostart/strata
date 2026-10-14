---
type: decision
id: D-001
title: "{{project}} 에 strata 를 쓴다"
date: {{date}}
status: accepted
---

# D-001 — {{project}} 에 strata 를 쓴다

## 배경

이 프로젝트의 문서는 서로 위에 쌓이고, 여러 AI 대화가 그 문서를 쓴다. 가드가 없으면 결정이 덮어써지거나
조사 문서가 나중에 고쳐질 수 있다. [가정]

## 결정

strata 를 쓴다. 결정은 `work/decisions/` 에 두고 추가 전용이다. 조사는 `work/evidence/` 에 두고 쓰는 순간
시점 고정이다. 살아있는 문서는 `work/current/` 에 둔다.

## 영향

- 결정을 바꾸려면 새 결정을 쓰고 옛 결정을 `superseded` 로 표시한다.
- 결정이 필요한 쟁점은 `issues` 등록부에 올린다(`strata register add`).

## 재검토 조건

층 규칙이 막는 실수보다 막는 정당한 작업이 더 많아지면 다시 본다.
