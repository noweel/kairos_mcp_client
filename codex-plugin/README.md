# KAIROS Codex CLI 연결

OpenAI Codex CLI를 KAIROS 지식저장고에 붙이는 묶음입니다. Codex에는 Claude Code의 플러그인 같은 설치 단위가 없고 확장 지점 셋이 각자의 자리에 있으므로, 이 디렉터리의 설치기가 그 셋과 클라이언트 스크립트를 한 번에 놓습니다(`decisions.md` §127).

| 요소 | 놓이는 자리 | 하는 일 |
|---|---|---|
| MCP 서버 등록 | `~/.codex/config.toml`의 `[mcp_servers.kairos]` | 게이트웨이의 `/mcp`에 툴 11종을 연결합니다. `X-KAIROS-Client: codex` 헤더를 실어 노트에 인입 경로가 기록됩니다 |
| 훅 2종 | `~/.codex/hooks.json`의 `Stop`·`SessionEnd` | 턴 전송과 세션 마감. **등록만 되고 켜져 있지는 않습니다**(아래 「자동 보관」) |
| 스킬 3종 | `~/.codex/skills/{kairos,kairos-status,kairos-archive}/SKILL.md` | 사용 정책(`kairos`), 연결 상태(`$kairos-status`), 명시 보관(`$kairos-archive`). Codex는 슬래시 명령이 아니라 스킬로 부릅니다 |
| 클라이언트 스크립트 | `~/.codex/kairos/kairos-client` | 훅과 스킬이 부르는 본체. Claude Code 플러그인의 스크립트와 **같은 파일**이며(`scripts/kairos-client`는 그쪽을 가리키는 심볼릭 링크), 표준 라이브러리만 씁니다 |

## 요구 사항

- Codex CLI(훅과 스킬을 지원하는 판. 훅은 기본으로 켜져 있고, 꺼져 있으면 `config.toml`에 `[features]\nhooks = true`).
- Python 3.10 이상(스크립트용).
- 동작 중인 KAIROS 게이트웨이(`kairos serve` 또는 `kairos-gateway` 유닛).

## 설치

리포를 클론한 뒤 설치기 한 줄입니다. 같은 기계에서 게이트웨이가 돌면 인자가 필요 없습니다.

```bash
git clone https://github.com/noweel/kairos_mcp_client.git      # 이미 체크아웃이 있으면(코어의 deploy/) 그 경로를 씁니다
python3 kairos_mcp_client/codex-plugin/install.py install
```

**주소를 한 번 묻습니다.** 그냥 Enter면 건너뛰고 이미 등록된 값이나 `http://127.0.0.1:8080/mcp`를 씁니다. `--url`로 미리 줄 수도 있습니다. 토큰은 묻지 않습니다 — 값이 프로세스와 셸 이력을 지나가므로, LAN이면 셸 프로필의 `KAIROS_TOKEN`을 보라고 안내만 합니다.

훅에 적히는 인터프리터는 **설치기가 돌고 있는 파이썬의 절대 경로**입니다. `python3`라는 이름이 PATH에 없는 기계(Windows)에서도 훅이 돕니다.

게이트웨이가 다른 기계(LAN)에 있으면 주소를 줍니다. 이때 `config.toml`에는 토큰 값이 아니라 **변수 이름**(`bearer_token_env_var = "KAIROS_TOKEN"`)만 적히므로, 셸 프로필에 토큰을 두어야 합니다.

```bash
python3 kairos_mcp_client/codex-plugin/install.py install --url http://<서버>:8080/mcp
export KAIROS_TOKEN=$(cat ~/.config/kairos/token)   # 서버에서 `kairos token show`로 확인해 옮겨 온 값
```

클론하지 않고 이 디렉터리만 옮기려면 `scripts/kairos-client`가 심볼릭 링크(`../../claude-plugin/kairos/scripts/kairos-client`)이므로 **링크를 푼 채** 복사합니다(`cp -rL codex-plugin <대상>`). 무엇을 할지만 보려면 `--dry-run`을 붙이고, `~/.codex`가 아닌 곳을 쓰면 `--codex-home`을 줍니다.

설치기는 멱등입니다. 두 번 돌려도 같은 상태가 되고, `config.toml`과 `hooks.json`에서 자기 항목만 갈아 끼우며 다른 서버·훅은 바이트 그대로 둡니다. 설치가 끝나면 Codex를 다시 시작합니다.

## 확인

Codex 안에서 `$kairos-status`를 칩니다. 게이트웨이 주소, 토큰 출처, 툴 수, 자동 보관 여부, 이 프로젝트의 롤아웃과 보낸 턴 수가 나옵니다. 터미널에서 직접 보려면 다음을 칩니다.

```bash
python3 ~/.codex/kairos/kairos-client --client codex status --project "$PWD"
```

## 쓰는 법

**질문할 때는 할 일이 없습니다.** `kairos` 스킬이 정책을 주므로 "전에 어떻게 했지"류의 질문이나 노트 ID, `kairos://note/<id>` 링크에서 Codex가 먼저 `search_knowledge`를 부릅니다.

**대화를 보관하려면 `$kairos-archive`를 칩니다.** 이 프로젝트의 가장 최근 롤아웃(지금 이 세션)에서 아직 보내지 않은 턴만 보내고 세션을 마감합니다. 두 번 쳐도 같은 턴을 다시 보내지 않습니다. Codex는 프로젝트별 대화록 디렉터리가 없으므로, 스크립트가 `~/.codex/sessions/`의 롤아웃을 최근 것부터 열어 첫 줄의 작업 디렉터리(`session_meta.cwd`)가 지금 프로젝트인 것을 고릅니다.

**보내는 것과 보내지 않는 것.** 롤아웃의 `user_message`(사람이 친 글)와 최종 `agent_message`만 갑니다. Codex가 끼워 넣는 환경 문맥과 개발자 지시, 추론, 도구 호출과 그 출력, 중간 서술(`commentary`)은 **보내지 않습니다.** 허용 목록 방식이라 목록에 없는 종류는 새로 생겨도 나가지 않습니다. 답변 본문에 시크릿이 적히면 서버의 시크릿 스캔이 잡습니다.

**자동 보관은 기본이 아닙니다.** 훅은 등록되어 있지만 `KAIROS_AUTO_ARCHIVE=1`이 없으면 `Stop` 훅은 아무것도 보내지 않습니다. 켜면 턴이 끝날 때마다 새 턴이 전송되고, `SessionEnd`는 보낸 적 있는 세션만 마감합니다.

## 갱신과 제거

스크립트나 스킬을 고쳤으면 설치기를 다시 돌립니다. 자기 항목만 새 값으로 바뀝니다. 제거는 `uninstall`이며, 다른 서버·훅·스킬은 남깁니다.

```bash
python3 codex-plugin/install.py install
python3 codex-plugin/install.py uninstall
```

## 문제가 생기면

| 증상 | 확인할 것 |
|---|---|
| `$kairos-status`가 "연결 안 됨" | 게이트웨이가 떠 있는가, `config.toml`의 `url`이 그 주소인가 |
| LAN에서 401 | `KAIROS_TOKEN`이 셸 프로필에 있고 그 셸에서 Codex를 띄웠는가 |
| 툴이 목록에 없다 | 설치 뒤 Codex를 다시 시작했는가. `codex mcp list`에 `kairos`가 보이는가 |
| 훅이 돌지 않는다 | `config.toml`의 `[features] hooks`가 `false`가 아닌가 |
| 보관했는데 노트가 안 생긴다 | 서버 쪽 정규화가 대기 중일 수 있습니다. `kairos status`와 `kairos trace <queue_id>`가 사실을 보입니다 |

서버 쪽 설치와 운용 전체는 이 저장소 루트의 `README.md`에, Claude Code 쪽은 `claude-plugin/README.md`에 있습니다.
