<!-- i18n: source=README.md sha=c99bd2e7f840 -->
# strata

**AI 에이전트가 층을 이루고 승인을 거치는 문서를 만드는 저장소를 위한 운영 층.**

[English](README.md)

strata 는 [Claude Code](https://claude.com/claude-code) 플러그인이다. 문서가 서로 위에 쌓이는
프로젝트를 위한 것이다 — 사업 기획이 제품 명세를 제약하고, 제품 명세가 개발 기획을 제약하며, 그 문서들을
여러 AI 대화가 쓴다.

> **상태: 초기(0.1).** 층 · 트랙 가드는 동작하고 시험을 거쳤다. 사이클 · 기록 · 에이전트 · 스킬은
> 설계만 있고 아직 만들지 않았다. [로드맵](docs/ko/design.md#12-로드맵)을 보라.

## 하는 일

- **층을 경로로 지킨다.** 문서마다 쓰기 모드를 가진 층에 속한다: `immutable`(불변) · `frozen`(시점
  고정) · `append-only`(추가 전용) · `living`(살아있는) · `scratch`(작업장). 모드를 깨는 쓰기를 훅이
  막는다. 예를 들어 결정 기록을 통째로 덮어쓰거나, 이미 쓴 조사 문서를 고치는 것이다.
- **닫힌 트랙은 닫힌 채로 둔다.** 작업 단계(「트랙」)는 사람이 매니페스트에서 연다. 열기 전에는 그
  트랙에 아무것도 쓰지 않는다.
- **도메인을 모른다.** 트랙 이름 · 폴더 · 문서 타입 · 절 제목은 모두 프로젝트 매니페스트에서 온다. 코드는
  그중 어느 것도 담지 않으며, 시험이 그것을 강제한다.
- **사용자의 언어로 말한다.** 메시지는 영어와 한국어로 나온다. 문서는 영어로 쓰고 번역하며, 번역이
  원본보다 뒤처지면 검사가 실패한다.

다음 계획: 제목 · 경로 · 프런트매터 · 층으로 문서의 절에 점수를 매겨 에이전트가 필요한 것만 읽게 하는
문맥 선택, 기계가 상한을 세는 다중 에이전트 사이클, 사람의 원문 답이 뒷받침하는 승인 게이트, 추가 전용
기록과 상향 보고 등록부.

## 설치

```bash
claude plugin marketplace add radiostart/strata
claude plugin install strata@strata
```

필요한 것: `PATH` 에 Python 3.11 이상. 다른 의존성은 없다.

## 사용

프로젝트에 매니페스트 `.strata/strata.toml` 이 생기기 전까지 strata 는 아무것도 하지 않는다.

```toml
[project]
name = "acme"
language = "ko"   # 또는 "en"
schema = 1

[[tracks]]
id = "business"
path = "tracks/business"
open = true

[[layers]]
id = "decisions"
mode = "append-only"
paths = ["tracks/*/decisions/**"]

[[layers]]
id = "research"
mode = "frozen"
paths = ["tracks/*/research/**"]
```

전체 스키마는 [설계 문서](docs/ko/design.md#6-매니페스트)에 있다.

막힌 쓰기가 의도했고 승인된 것이면, `STRATA_GUARD_BYPASS=1` 을 환경에 넣고 Claude Code 를 다시 띄운다.
가드는 사고를 막는 장치이지 보안 경계가 아니다.

## 개발

```bash
python3 -m unittest discover -s tests
python3 tools/i18n_check.py
```

기여자와 AI 에이전트를 위한 저장소 규약은 [CLAUDE.md](CLAUDE.md) 에 있다.

## 출발점

strata 는 문서가 먼저인 앞선 제품 프로젝트를 위해 처음 만든 운영 층을 백지에서 다시 쓴 것이다. 원리는
옮겼고, 어떤 프로젝트의 구조도 박히지 않도록 코드는 새로 썼다. [설계 § 2](docs/ko/design.md#2-출발점과-바뀐-것)
를 보라.

## 라이선스

[MIT](LICENSE)
