# KAIROS Claude Code 플러그인

Claude Code를 KAIROS 지식저장고에 붙이는 플러그인입니다. 설치 한 번으로 아래 다섯이 함께 붙습니다(`decisions.md` §102).

| 요소 | 파일 | 하는 일 |
|---|---|---|
| MCP 서버 등록 | `kairos/.mcp.json` | 게이트웨이의 `/mcp`에 툴 11종(조회 8·인입 3)을 연결합니다. 요청마다 `X-KAIROS-Client: claude-code` 헤더를 보내 노트에 인입 경로가 기록됩니다 |
| 훅 2종 | `kairos/hooks/hooks.json` | `Stop`(턴 전송)·`SessionEnd`(세션 마감). **등록만 되고 켜져 있지는 않습니다**(아래 「자동 보관」) |
| 사용 정책 스킬 | `kairos/skills/kairos/SKILL.md` | "언제 저장고를 먼저 보는가"를 Claude에게 줍니다. 툴이 있어도 이것이 없으면 거의 부르지 않습니다 |
| 슬래시 명령 | `kairos/commands/setup.md`·`status.md`·`archive.md` | `/kairos:setup`(주소 적기 — 건너뛸 수 있습니다), `/kairos:status`(연결 상태), `/kairos:archive`(이 대화를 명시 보관) |
| 클라이언트 스크립트 | `kairos/scripts/kairos-client` | 훅과 명령이 부르는 본체. 표준 라이브러리만 쓰므로 KAIROS 체크아웃 없이 이 디렉터리만 있으면 동작합니다 |

## 요구 사항

- Claude Code(플러그인 지원 버전), Python 3.10 이상이 **`python3`라는 이름으로 `PATH`에** 있어야 합니다(훅과 슬래시 명령이 셸을 거치지 않고 그 이름을 직접 띄웁니다). 없으면 MCP 조회는 되고 훅만 돌지 않으며, `/kairos:status`가 그 사실을 말합니다.
- 동작 중인 KAIROS 게이트웨이(`kairos serve` 또는 `kairos-gateway` 유닛). 게이트웨이가 없어도 설치는 되고, `/kairos:status`가 "연결 안 됨"을 말해 줍니다.

## 설치

체크아웃이 있으면 **설치기 한 줄**이 가장 짧습니다. 게이트웨이 주소를 한 번 묻고(Enter로 건너뛸 수 있습니다) 마켓플레이스 등록과 플러그인 설치까지 합니다. Windows·리눅스·macOS가 같은 명령입니다.

```bash
python3 deploy/install.py            # 코어 작업 트리에서. 클론만 있으면 kairos_mcp_client/install.py
```

물어보는 것은 주소 하나뿐입니다. **토큰은 묻지 않습니다** — 값을 받아 적으면 그 값이 프로세스와 셸 이력을 지나가므로, 있는지만 보고 없으면 무엇을 할지 말합니다.

손으로 하려면 아래와 같습니다. 리포(`noweel/kairos_mcp_client`) 자체가 마켓플레이스입니다(루트의 `.claude-plugin/marketplace.json`). GitHub 경로로 등록하고 플러그인을 사용자 스코프로 설치합니다 — 클론이 필요 없습니다.

```bash
claude plugin marketplace add noweel/kairos_mcp_client   # 비공개 리포면 git 인증(SSH 키나 자격 증명 도우미)이 있어야 합니다
claude plugin install kairos@kairos
```

체크아웃이 있는 기계에서는 그 경로로 등록합니다.

```bash
claude plugin marketplace add /path/to/kairos_mcp_client   # 코어 작업 트리에서는 ./deploy
claude plugin install kairos@kairos
```

리포가 없고 인증도 없는 기계에서는 리포 전체를 복사해 가되, 마켓플레이스 매니페스트가 루트에 있으므로 `claude-plugin/`만 떼어 가면 등록되지 않습니다. 설치 전에 규격을 확인하려면 체크아웃에서 다음을 칩니다.

```bash
claude plugin validate ./claude-plugin/kairos
```

설치가 끝나면 Claude Code를 다시 시작합니다. 플러그인은 세션이 시작될 때 읽힙니다.

## 연결 설정

같은 기계에서 게이트웨이가 돌면 **아무것도 설정하지 않아도 됩니다.** `.mcp.json`의 기본 주소가 `http://127.0.0.1:8080/mcp`이고, 게이트웨이가 루프백 요청을 토큰 없이 받아들입니다(A8).

게이트웨이가 다른 기계(LAN)에 있으면 주소와 토큰을 줍니다.

**주소는 Claude Code의 설정 파일에 적는 편이 낫습니다.** 셸 프로필의 `export`는 **PC 앱이 읽지 못합니다** — 앱은 로그인 셸을 거치지 않으므로 `.bashrc`·`.zshrc`가 실행되지 않습니다. `/kairos:setup`이나 설치기가 `~/.claude/settings.json`의 `env`에 적어 주며, 그 자리는 CLI와 PC 앱이 같이 읽고 Windows에서는 `%USERPROFILE%\.claude`로 풀립니다.

```
/kairos:setup http://<서버>:8080/mcp
```

**토큰은 셸 프로필에 둡니다.** `.mcp.json`은 이 변수를 **참조만** 하므로 값이 설정 파일에 남지 않습니다. PC 앱에서 LAN 저장고를 쓸 때는 토큰 파일(`~/.config/kairos/token`)을 두는 편이 확실합니다 — 스크립트가 그것을 읽습니다.

```bash
export KAIROS_TOKEN=$(cat ~/.config/kairos/token)   # 서버에서 `kairos token show`로 확인해 옮겨 온 값
```

스크립트가 읽는 변수 전체는 다음과 같습니다.

| 변수 | 기본값 | 뜻 |
|---|---|---|
| `KAIROS_URL` | `http://127.0.0.1:8080/mcp` | 게이트웨이 주소. `/kairos:setup`이 `settings.json`의 `env`에 적습니다 |
| `KAIROS_TOKEN` | (없음) | A8 토큰. 없으면 `KAIROS_TOKEN_FILE`을 봅니다 |
| `KAIROS_TOKEN_FILE` | `~/.config/kairos/token` | 토큰 파일 경로 |
| `KAIROS_AUTO_ARCHIVE` | (꺼짐) | `1`이면 턴마다 자동 보관 |
| `KAIROS_ARCHIVE_STATE` | `$XDG_STATE_HOME/kairos/archive` | 어디까지 보냈는지 기억하는 상태 디렉터리 |

## 확인

Claude Code 안에서 `/kairos:status`를 칩니다. 게이트웨이 주소, 토큰 출처, 툴 수, 자동 보관 여부, 이 프로젝트의 대화록과 보낸 턴 수가 한 화면에 나옵니다. 실패 줄이 있으면 다음 조치(토큰 설정, 서버 기동)를 문장으로 말합니다.

터미널에서 직접 보려면 스크립트를 바로 부릅니다.

```bash
~/.claude/plugins/cache/kairos/kairos/<버전>/scripts/kairos-client status --project "$PWD"
```

## 쓰는 법

**질문할 때는 할 일이 없습니다.** 스킬이 정책을 주므로 "전에 어떻게 했지"류의 질문, 노트 ID나 `kairos://note/<id>` 링크, 이전 작업의 연장으로 보이는 요청에서 Claude가 먼저 `search_knowledge`를 부릅니다.

**대화를 보관하려면 `/kairos:archive`를 칩니다.** 이 프로젝트의 지금 대화록에서 아직 보내지 않은 턴만 보내고 세션을 마감합니다. 두 번 쳐도 같은 턴을 다시 보내지 않습니다. 지금 치고 있는 턴은 대화록에 아직 다 쓰이지 않았을 수 있어 다음 보관 때 이어서 들어갑니다.

**보내는 것과 보내지 않는 것.** 사람이 실제로 친 프롬프트와 어시스턴트의 답변 텍스트만 갑니다. 도구 호출, 도구 결과, 사고 블록, 슬래시 명령 출력, 터미널 입출력, 서브에이전트 대화는 **보내지 않습니다.** 허용 목록 방식이라 목록에 없는 종류는 새로 생겨도 나가지 않습니다. 실측에서 터미널 출력 자리에 토큰과 평문 비밀번호가 있었기 때문입니다(`decisions.md` §97). 그래도 답변 본문에 시크릿이 적히면 서버의 시크릿 스캔이 잡아 `sensitive` 표시와 마스킹으로 처리합니다.

**자동 보관은 기본이 아닙니다.** 훅은 등록되어 있지만 `KAIROS_AUTO_ARCHIVE=1`이 없으면 `Stop` 훅은 아무것도 보내지 않습니다(11-B-2, "명시 요청만"). 켜면 턴이 끝날 때마다 새 턴이 전송되고, `SessionEnd`는 보낸 적 있는 세션만 마감합니다.

**다른 대화록을 보관하려면** 스크립트의 `replay`를 직접 부릅니다. `--dry-run`은 보낼 턴만 세고 아무것도 보내거나 기억하지 않습니다.

```bash
kairos-client replay --transcript <대화록.jsonl> --dry-run
kairos-client replay --project <프로젝트 경로>          # /kairos:archive가 하는 일
```

## 권한 프롬프트 줄이기

플러그인이 붙인 툴의 권한 식별자는 `mcp__plugin_kairos_kairos__<툴>`입니다(서버 이름 앞에 `plugin_kairos_`가 붙습니다). 조회 8종을 묻지 않게 하려면 `~/.claude/settings.json`에 적습니다. 인입 3종(`add_knowledge`·`archive_turn`·`finalize_session`)은 넣지 않는 편이 맞습니다. 매번 확인받는 것이 보관의 뜻에 맞기 때문입니다.

```json
{ "permissions": { "allow": [
  "mcp__plugin_kairos_kairos__search_knowledge", "mcp__plugin_kairos_kairos__get_note",
  "mcp__plugin_kairos_kairos__get_source",       "mcp__plugin_kairos_kairos__get_related",
  "mcp__plugin_kairos_kairos__list_by_filter",   "mcp__plugin_kairos_kairos__list_vocabulary",
  "mcp__plugin_kairos_kairos__trace_ingest",     "mcp__plugin_kairos_kairos__export_graph"
] } }
```

## 갱신과 제거

설치본은 이 디렉터리의 **복사본**입니다(`~/.claude/plugins/cache/kairos/kairos/<버전>/`). 여기를 고쳐도 설치본은 그대로이므로, 바꾼 뒤에는 `kairos/.claude-plugin/plugin.json`의 `version`을 올리고 갱신합니다. 갱신 뒤에는 Claude Code를 다시 시작해야 적용됩니다.

```bash
claude plugin validate ./claude-plugin/kairos
claude plugin update kairos@kairos
```

제거는 플러그인과 마켓플레이스를 차례로 뺍니다.

```bash
claude plugin uninstall kairos@kairos
claude plugin marketplace remove kairos              # GitHub 경로로 등록했든 로컬 경로로 등록했든 이름은 kairos다
```

## 문제가 생기면

| 증상 | 확인할 것 |
|---|---|
| `/kairos:status`가 "연결 안 됨" | 게이트웨이가 떠 있는가(`systemctl --user status kairos-gateway`), `KAIROS_URL`이 그 주소인가 |
| LAN에서 401 | `KAIROS_TOKEN`이 셸 프로필에 있고 그 셸에서 Claude Code를 띄웠는가. 토큰은 서버의 `kairos token show`가 정본 |
| 툴이 목록에 없다 | 설치 뒤 Claude Code를 다시 시작했는가. `claude plugin list`에서 `enabled`인가 |
| 보관했는데 노트가 안 생긴다 | 서버 쪽 정규화가 대기 중일 수 있습니다(모델 서버 부재). `kairos status`와 `kairos trace <queue_id>`가 사실을 보입니다 |
| 노트가 「미상」 경로로 잡힌다 | 플러그인 0.2.0 이전에 시작한 세션입니다. 서버에서 `kairos migrate-client --apply`가 근거 있는 것만 채웁니다 |
| 훅만 돌지 않는다 (MCP 조회는 된다) | `/kairos:status`의 `python3` 줄을 봅니다. 훅은 셸을 거치지 않고 `PATH`에서 `python3`를 찾으므로 그 이름이 없으면 훅만 조용히 실패합니다. Windows는 python.org 설치본에서 「Add python.exe to PATH」를 켜거나 `winget install Python.Python.3.12` |
| PC 앱에서만 주소가 다르다 | 앱은 로그인 셸을 거치지 않아 `.bashrc`의 `export KAIROS_URL`을 읽지 못합니다. `/kairos:setup <주소>`로 설정 파일에 적습니다 |

Codex CLI는 `codex-plugin/`의 설치기가 같은 스크립트를 `--client codex`로 놓습니다. Antigravity는 아직 어댑터가 없습니다. 서버 쪽 설치와 운용 전체는 이 저장소 루트의 `README.md`에 있습니다.
