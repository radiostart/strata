<!-- i18n: source=docs/en/cli.md sha=36f3ff08217a -->
# strata — 명령 참조

> strata 0.2(이정표 M1) 기준이다. 이 명령들 뒤의 설계는 [design.md](design.md) 에 있다.

명령줄은 Python 3.11 이상으로 돌린다.

```bash
python3 <플러그인>/scripts/strata <명령> [선택지]
```

Claude Code 안에서는 스킬 `/strata:init` · `/strata:validate` · `/strata:status` 가 대신 부른다.

모든 명령은 `--root DIR` 을 받는다(기본값: 작업 폴더와 그 위에서 `.strata/strata.toml` 을 가진 가장 가까운
폴더). 대부분은 `--format text|json` 도 받는다. 메시지는 프로젝트의 `project.language` 로 나온다.

| 종료 코드 | 뜻 |
| --- | --- |
| 0 | 성공 |
| 1 | 문제를 찾았거나(`validate`) 작업이 거절됐다(`record` · `register`) |
| 2 | 사용 오류, 프로젝트를 못 찾음, 또는 매니페스트가 올바르지 않음 |

## init

템플릿으로 프로젝트 뼈대를 만든다.

```bash
strata init [--lang en|ko] [--name ID] [--actor NAME]
```

- `--lang` 은 템플릿을 고른다. 기본 `en`. 템플릿은 `templates/<언어>/` 에 있다.
- `--name` 은 프로젝트 ID 다. 영문 소문자로 시작하고 소문자 · 숫자 · `-` 만 쓴다. 기본값은 폴더 이름에서
  만든다.
- `.strata/strata.toml`, 템플릿의 폴더와 결정 예시, 매니페스트가 선언한 모든 등록부 파일, 그리고 `init`
  기록을 만든다.
- **덮어쓰지 않는다.** 만들 파일 가운데 하나라도 이미 있으면 아무것도 쓰지 않고 종료 코드 2 로 끝난다.

## validate

문서를 매니페스트와 대조한다.

```bash
strata validate [PATH ...]
```

경로를 주지 않으면 프로젝트의 모든 `*.md` 를 보며, `.git` · `.strata` 같은 숨은 폴더는 건너뛴다. 경로는
파일이어도 폴더여도 된다.

파일은 프런트매터에 `type` 이 있을 때만 검사한다. 그다음은 이렇다.

| 검사 | 등급 |
| --- | --- |
| `type` 이 `[[documents.types]]` 에 선언돼 있다 | 아니면 경고 |
| 그 타입의 `frontmatter` 목록에 있는 키가 모두 있고 비어 있지 않다 | 오류 |
| 그 타입의 `sections` 목록에 있는 제목이 모두 2단계 제목(`## …`)으로 나온다. `1.` · `2.3` · `4)` 같은 앞 번호와 대소문자는 무시한다 | 오류 |
| `reference` 패턴을 가진 증거 태그 뒤에는 **같은 줄에** 그 패턴에 맞는 것이 있다 | 오류 |
| `---` 로 시작한 프런트매터가 닫혀 있다 | 오류 |

울타리 코드 블록 안의 글자는 제목과 태그 검사에서 무시한다. 경고는 종료 코드를 바꾸지 않는다.

## status

프로젝트를 요약한다: 트랙, 층마다 파일 수, 타입마다 문서 수, 등록부, 최근 기록. 읽기 전용이다.

```bash
strata status [--format json]
```

## record

추가 전용 실행 기록. 달마다 파일 하나다: `.strata/records/YYYY-MM.md`.

```bash
strata record add --kind KIND --target TARGET --result RESULT [--actor NAME] [--evidence PATH] [--note TEXT]
strata record list [--limit N]
```

- `kind` · `target` · `actor` · `result` 는 비워 둘 수 없다. `--actor` 가 없으면 환경 변수
  `STRATA_ACTOR`, 그것도 없으면 `-` 를 쓴다.
- 칸 하나는 300자까지다. 더 긴 내용은 파일에 두고 그 경로를 `--evidence` 로 준다.
- 한 행은 마크다운 표의 한 줄이다. `|` 는 이스케이프하고 줄바꿈은 빈칸이 된다.
- 가드는 매니페스트와 상관없이 모든 프로젝트에서 `.strata/records/` 를 추가 전용으로 본다. 행을 더할 수는
  있지만 바꾸거나 지울 수는 없다.

## register

등록부는 상향 보고나 쟁점의 추가 전용 목록이며, `[[registers]]` 에 선언한다.

```bash
strata register add --register ID --title TEXT [--source REF]
strata register close --id ENTRY-ID --resolution TEXT
strata register list [--register ID] [--open]
```

등록부 파일은 ID · 날짜 · 상태 · 제목 · 출처 · 처리 열을 가진 마크다운 표다.

- **ID.** 다음 ID 는 **첫 열**에 있는 가장 큰 `{접두}-{n}` 에 1 을 더한 것이다. 제목 속에 인용한 ID 는
  번호에 영향을 주지 않는다.
- **파일이 없을 때.** 등록부 파일이 없으면 `add` 는 실패한다. 새 파일을 만들지 않는다. 그러지 않으면 경로가
  틀렸을 때 번호가 1부터 다시 시작한다.
- **상태.** 상태 칸에는 고정 낱말 `open` 이나 `closed` 를 쓴다. 그래야 어느 언어에서든 도구가 같게 읽는다.
  `close` 는 그 항목의 줄만 바꾼다. 상태를 `closed` 로 바꾸고 처리 칸을 채운다.
