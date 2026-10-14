<!-- i18n: source=docs/en/development.md sha=8ecb0a3228e5 -->
# strata — 개발 안내

> 다음 이정표를 이어받는 사람이나 AI 에이전트를 위한 문서다. 저장소 규칙은 [CLAUDE.md](../../CLAUDE.md),
> strata 가 무엇인지는 [design.md](design.md) 에 있다. 이 안내는 일이 어디까지 왔고 어떻게 이어 가는지를
> 적는다.

## 1. 상태

| 이정표 | 상태 | 비고 |
| --- | --- | --- |
| M0 — 기반 | 끝 | 매니페스트 로더, 층 · 트랙 가드, 메시지 카탈로그, 번역 검사 |
| M1 — 기록과 검증 | 끝 | `strata init · validate · status · record · register`, 템플릿 `en` · `ko`, 스킬 `/strata:init · validate · status` |
| **M2 — 문맥 선택** | **다음** | 작업 목록은 § 6 |
| M3 — 사이클 엔진 | 시작 전 | 설계 § 7.2(변경 파일과 반영) |
| M4 — 사이클 스킬과 에이전트 | 시작 전 | M2 와 M3 를 기다린다 |
| M5 — 역할과 게이트 | 시작 전 | |
| M6 — 조율 | 시작 전 | 실제 둘째 프로젝트가 M0~M5 를 쓴 뒤에만 |

이정표마다의 커밋은 `git log` 에 있다.

## 2. 시작하기

```bash
git clone https://github.com/radiostart/strata.git
cd strata
python3 --version                      # 3.11 이상
python3 -m unittest discover -s tests  # 시험이 모두 통과해야 한다
python3 tools/i18n_check.py            # 번역이 최신이어야 한다
claude plugin validate .               # CLAUDE.md 경고 하나는 예상된 것이다(설계 § 9)
```

작업 사본으로 프로젝트에서 플러그인을 써 보려면:

```bash
claude plugin marketplace add /path/to/strata
claude plugin install strata@strata
```

플러그인 없이 명령줄만 써 보려면:

```bash
python3 scripts/strata init --lang en --root /tmp/demo
python3 scripts/strata status --root /tmp/demo
```

## 3. 코드 지도

| 경로 | 맡은 일 |
| --- | --- |
| `strata/manifest.py` | `.strata/strata.toml` 의 스키마와 로더. 모든 키를 여기서 선언한다 |
| `strata/paths.py` | 글롭 맞춤, 대소문자 처리, 프로젝트 루트 찾기 |
| `strata/guard.py` | 도구 호출 하나에 대한 층 · 트랙 판정 |
| `strata/bashwrites.py` | Bash 명령의 쓰기 대상을 보수적으로 뽑기 |
| `strata/hook.py`, `hooks/run.sh`, `scripts/hook.py` | 훅 입구: Python 을 찾고, 입력을 읽고, 0 이나 2 로 끝낸다 |
| `strata/validate.py` | 글자에 대한 문서 검사. 쓰기 전의 제안도 검증할 수 있다 |
| `strata/records.py` | 월별 추가 전용 실행 기록 |
| `strata/registers.py` | 등록부 파일: ID · 추가 · 닫기 · 목록 |
| `strata/scaffold.py`, `templates/<언어>/` | `strata init` |
| `strata/status.py` | 읽기 전용 프로젝트 요약 |
| `strata/cli.py`, `scripts/strata` | 명령줄 |
| `strata/messages.py`, `strata/i18n/*.toml` | 메시지 카탈로그 |
| `skills/*/SKILL.md` | 명령 하나씩을 감싸는 얇은 스킬 |
| `tests/` | 단위 시험. 동작 시험은 `tests/fixtures/` 의 모든 고정물에서 돈다 |
| `tools/i18n_check.py` | 번역 최신 여부 |

## 4. 걸려 넘어지기 쉬운 규칙

전체 목록은 [CLAUDE.md](../../CLAUDE.md) 에 있다. 아래는 M0 · M1 에서 실제로 실패했던 것이다.

- **코드에 프로젝트 어휘가 없다.** 고정물 낱말이 동작에 영향을 주는 문자열에 나오면
  `tests/test_conventions.py` 가 실패한다. 한 고정물이 `done` 을 상태로 쓰기 때문에 `init.done` 이라는 메시지
  키가 걸렸다. 식별자 이름을 바꾸고, 시험은 절대 약하게 만들지 않는다.
- **메시지에 `{lang}` 자리표시자를 쓰지 않는다.** `text(key, lang, **params)` 가 이미 `lang` 을 받는다.
- **사용자에게 보이는 문자열은 모두 카탈로그를 거친다.** `en.toml` 과 `ko.toml` 에 같은 키와 같은
  자리표시자로 둔다.
- **템플릿에 `.strata/` 폴더를 두지 않는다.** 템플릿 매니페스트는 `templates/<언어>/manifest.toml` 이다. 진짜
  `.strata/` 가 있으면 템플릿 폴더가 가드가 판정하는 프로젝트가 된다.
- **가드는 Claude 의 도구 호출만 본다.** strata 자신의 명령은 파일을 직접 쓰므로, 층에 쓰는 명령은 층 규칙을
  스스로 확인해야 한다. M3 의 `apply` 에서 중요하다.
- **영어 원본이 먼저다.** `docs/en/*.md` 나 `README.md` 가 바뀌면 같은 변경 안에서 한국어 번역을 고치고
  `python3 tools/i18n_check.py --stamp <번역 파일>` 을 돌린다.

## 5. 이정표를 맡는 법

1. [설계 § 12](design.md#12-로드맵)의 그 이정표 행과, 그 행이 가리키는 절을 읽는다.
2. 설계가 열어 둔 결정이 있으면 정하고, 그것을 코드와 **같은 변경 안에서** `docs/en/design.md` 와 한국어
   번역에 적는다. 이유는 짧게 쓴다.
3. 실패하는 시험을 먼저 쓴다. 동작 시험은 `per_fixture` 데코레이터를 쓴다.
4. 만든다. 모듈은 표준 라이브러리만 쓴다.
5. 명령이 바뀌면 `docs/en/cli.md` 를, 사용자에게 달라 보이는 것이 있으면 `README.md` 를, 그리고 이 안내의
   § 1 을 고친다. 번역하고 다시 찍는다.
6. 전체 시험, 번역 검사, `claude plugin validate .` 를 돌린다.
7. 브랜치(`feat/m2-…`)에 커밋하고, 파일은 이름으로 담고, 관리자가 말하면 `main` 에 합친다.

## 6. M2 — 문맥 선택: 작업 목록

설계: [§ 8](design.md#8-문맥-선택) 과 [§ 7.3](design.md#73-시작-안내-대화가-길을-찾는-법). 항목 하나가
검토할 수 있는 변경 하나다.

| # | 일 | 끝 조건 |
| --- | --- | --- |
| M2.1 | **스키마.** § 8.3 의 계획 키와 § 7.4 의 M2 키를 받는다: `[[layers]] weight`, `[documents] status_weights`, `[context]`(`section_levels` · `chunk_bytes` · `budget_bytes` · `limit` · `exclude` · `start` · `brief_chars`), `[[cycles.access]]`(`step` · `reads` · `excludes` · `writes`). 모르는 자리표시자와 `{cycle}` 밖의 `writes` 는 거절한다. § 8.3 과 § 7.4 의 키에서 「계획」 표시를 걷는다 | 스키마 시험이 키마다, 거절마다 있다 · 두 고정물이 로드된다 |
| M2.2 | `strata/context/` 의 **절 색인.** 마크다운을 설정된 제목 수준으로 나누고, 머리말도 절로 두고, 큰 절은 빈 줄이나 표 행에서 조각내고, 경로 · 제목 · 수준 · 프런트매터 `description` · `status` · `sources` · 인용 경로를 기록한다 | 조각난 표를 포함한 색인 시험이 두 고정물에서 통과 |
| M2.3 | `project.language` 별 **토큰화.** 영어: 소문자 낱말 나누기. 한국어: 붙어 있는 낱말이 이어 쓴 꼴과도 맞고(`접수 상태` ↔ `접수상태`), 긴 한글 토큰은 띄어 쓰든 붙여 쓰든 맞는다 | 언어별 토큰화 시험 |
| M2.4 | **검색.** § 8.2 의 신호와 기본 가중치, 층 · 상태 배수, 중복 접기, 기본 제외(`.strata/records/**` · `[context] exclude`), 결정적 동점 처리, 「제외가 가린 것」 알림, 질의 형식 셋 | 골든 질의가 두 고정물에서 통과 · 현행 층의 절이 같은 글의 아카이브 사본보다 위에 온다 |
| M2.5 | **명령.** `strata context QUERY [--limit N] [--format text|json|manifest] [--inject] [--max-bytes N]`. `strata load --cycle-type T --step S --cycle DIR` 는 `files_to_read` · `writable_paths` · `excluded` 를 JSON 으로 돌려주고, 접근 항목이 없는 단계는 거절한다 | 명령 시험 · 거절 시험 |
| M2.6 | **시작 안내.** `SessionStart` 훅이 프로젝트, 열린 트랙, `[context] start` 문서, strata 스킬을 `brief_chars` 안에서 프로젝트 언어로 찍는다. 매니페스트가 없으면 아무것도 찍지 않는다 | 두 고정물과 매니페스트 없는 폴더에서 훅 시험 |
| M2.7 | `strata context` 를 감싸는 **스킬** `/strata:context`. 목록 → 고르기 → 주입 흐름 | 스킬이 `${CLAUDE_PLUGIN_ROOT}` 경로로 명령을 부른다 |

**M2 에는 고정물에 문서가 필요하다.** 고정물마다 그 언어로 작은 문서 묶음을 더한다. 현행 문서, 그중 하나의
아카이브 사본, superseded 문서, 아주 큰 표가 들어간다. 골든 질의를 그 옆에 둔다. 예:
`tests/fixtures/<이름>/golden.toml`.

```toml
[[queries]]
query = "pricing small shops"
expect = ["<경로>#<제목>"]   # 상위 결과에 반드시 나와야 한다
top = 3
```

**지연 시간.** 시험 안에서 문서 500개 묶음을 만들고, 색인과 질의 한 번이 예산 안에 드는지 확인한다. 색인은
호출마다 메모리에서 만든다(§ 8.2).

## 7. 나중에 정할 알려진 문제

- **고정물 낱말 `decisions` 와 M3.** 설계 § 7.1 은 결정 초안을 `{cycle}/decisions/` 에 둔다. 그런데 고정물
  `alpha` 가 `decisions` 를 폴더 이름으로 쓴다. M3 코드에 그 낱말이 들어가면 어휘 시험이 실패한다. M3 에서
  정한다: 초안 폴더를 매니페스트 키로 만들거나, 고정물의 폴더 이름을 바꾼다. 시험을 약하게 만들지 않는다.
- **기록의 주체.** `--actor` 가 없으면 `STRATA_ACTOR`, 그다음 `-` 를 쓴다. 주체가 무엇인지는 역할(M5)이
  정한다.
- **Windows.** 훅은 `sh` 로 돈다. Windows 에서는 Git Bash 다. 아직 시험하지 않았다.
- **권한 정책이 거절하는 명령.** 어떤 환경은 `rm -rf` 나 `chmod` 같은 셸 명령을 거절한다. 시험은
  `tempfile` 을 쓰므로 그런 명령이 필요 없다. 그대로 유지한다.
