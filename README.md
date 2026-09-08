# KAIROS 클라이언트 연결 (kairos_mcp_client)

> 이 저장소는 KAIROS의 **클라이언트·배포 묶음**이다. Claude Code 플러그인(`claude-plugin/`), Codex CLI 설치기(`codex-plugin/`), systemd 유닛(`systemd/`)이 있다. 코어(`noweel/kairos`)의 작업 트리에서는 `deploy/`로 체크아웃한다(`decisions.md` §128). **서버 쪽 설치와 운용**(유닛 등록·설정·접속·Telegram·재기동·백업)은 코어 저장소 루트의 `README.md`에 있다. 이 문서는 게이트웨이가 이미 떠 있다는 전제에서 **클라이언트를 붙이는 방법**만 다룬다.

| 클라이언트 | 붙이는 방법 | 자세히 |
|---|---|---|
| Claude Code | `claude plugin marketplace add noweel/kairos_mcp_client` + `claude plugin install kairos@kairos` | 아래 §1, `claude-plugin/README.md` |
| Codex CLI | 클론 뒤 `codex-plugin/install.py install` | 아래 §2, `codex-plugin/README.md` |
| Antigravity 등 | MCP 등록만(설정의 `serverUrl`), 대화록 어댑터는 아직 없다 | 아래 §2 |

---

## 1. Claude Code — 플러그인

Claude Code와의 연결은 **플러그인 하나**로 끝난다(`claude-plugin/`, decisions.md §102). 플러그인 자체의 설치·설정·사용법은 `claude-plugin/README.md`에 따로 있다 — 리포 없이 디렉터리만 복사해 간 기계에서도 읽을 수 있게 그쪽에 두었다. 설치하면 MCP 서버 등록·대화 보관 훅·사용 정책 스킬·`/kairos:status`·`/kairos:archive`가 한 번에 붙는다. 손으로 `claude mcp add`를 치거나 `settings.json`을 편집할 일이 없다.

**이 리포 자체가 마켓플레이스다**(루트의 `.claude-plugin/marketplace.json`). GitHub 경로로 바로 등록한다 — 클론이 필요 없다.

```bash
claude plugin marketplace add noweel/kairos_mcp_client   # GitHub에서 마켓플레이스로 (비공개 리포면 git 인증이 있어야 한다)
claude plugin install kairos@kairos                       # 사용자 스코프 — 모든 프로젝트
```

체크아웃이 있는 기계에서는 그 경로를 준다: `claude plugin marketplace add /path/to/kairos_mcp_client`(코어 작업 트리에서는 `./deploy`). 플러그인 안의 스크립트는 표준 라이브러리만 쓰므로 KAIROS 체크아웃이 필요 없다.

**갱신.** 설치본은 리포의 **복사본**이다(`~/.claude/plugins/cache/kairos/kairos/<버전>/`, Windows는 `%USERPROFILE%\.claude\plugins\cache\…`). 리포를 고쳐도 설치본은 그대로이므로, 바꾼 뒤에는 `plugin.json`의 `version`을 올리고 푸시한 다음 `claude plugin marketplace update kairos && claude plugin update kairos@kairos`를 친다(경로로 등록했으면 마켓플레이스 갱신은 필요 없다). 게이트웨이·워커를 함께 재기동해야 하는 것과 같은 성격의 어긋남이다 — 고친 코드가 어디서 돌고 있는지가 다르다. 손보기 전 `claude plugin validate ./claude-plugin/kairos`로 규격을 확인한다.

**경로 표식.** 플러그인의 `.mcp.json`과 훅 스크립트는 요청마다 `X-KAIROS-Client: claude-code` 헤더를 보낸다(0.2.0, decisions.md §106). 게이트웨이가 이 값을 노트의 `source.client`로 적어 뷰어가 **인입 경로별로** 그래프를 가른다. 인증이 아니라 분류다 — 토큰과 무관하고, 없으면 그 노트는 「미상」이다. Codex·Gemini도 각자의 MCP 설정에서 같은 헤더를 보내면 갈라진다.

**토큰.** 같은 호스트면 아무것도 설정하지 않아도 된다 — 게이트웨이의 루프백 면제(A8)로 붙는다. LAN이면 셸 프로필에 둘을 둔다. 플러그인의 `.mcp.json`은 `${KAIROS_TOKEN}`을 **참조만** 하므로 값이 설정 파일에 남지 않는다.

```bash
export KAIROS_URL=http://<서버>:8080/mcp
export KAIROS_TOKEN=$(cat ~/.config/kairos/token)   # 서버에서 복사해 온 값
```

**권한.** 플러그인이 붙인 MCP 툴의 권한 식별자는 `mcp__plugin_kairos_kairos__<툴>`이다(실측 2026-09-04 — 플러그인 경유라 서버 이름 앞에 `plugin_kairos_`가 붙는다). Claude Code는 `readOnlyHint`로 자동 승인하지 않으므로 조회 6종을 묻지 않게 하려면 `~/.claude/settings.json`의 `permissions.allow`에 이름을 적는다. 쓰기 3종(`archive_turn`·`finalize_session`·`add_knowledge`)은 넣지 않는다 — 매번 확인받는 편이 맞다.

```json
{ "permissions": { "allow": [
  "mcp__plugin_kairos_kairos__search_knowledge", "mcp__plugin_kairos_kairos__get_note",
  "mcp__plugin_kairos_kairos__get_source",       "mcp__plugin_kairos_kairos__get_related",
  "mcp__plugin_kairos_kairos__list_by_filter",   "mcp__plugin_kairos_kairos__export_graph"
] } }
```

**확인.** Claude Code 안에서 `/kairos:status`. 게이트웨이·토큰 출처·툴 수·자동 보관 여부·이 프로젝트의 대화록과 보낸 턴 수를 한 화면에 보인다. 실패 줄은 다음 조치를 문장으로 말한다.

**보관.** 기본은 **명시 보관**이다(11-B-2). 대화를 넣고 싶을 때 `/kairos:archive`를 치면 이 프로젝트의 지금 대화록에서 아직 보내지 않은 턴만 보내고 세션을 마감한다. 두 번 쳐도 같은 턴을 다시 보내지 않는다. 턴마다 자동으로 보내려면 `export KAIROS_AUTO_ARCHIVE=1` — 훅은 이미 등록돼 있고 이 변수가 그것을 켠다. 잡담 세션까지 전부 노트가 되면 §2.1이 막으려던 검색 노이즈가 세션 단위로 돌아오므로, 실사용에서 노이즈 비율을 본 뒤 정한다.

**보내는 것과 보내지 않는 것.** 사람이 실제로 친 프롬프트와 어시스턴트의 답변 텍스트만 간다. 도구 호출·도구 결과·사고 블록·슬래시 명령 출력·터미널 입출력·부수 대화(서브에이전트)는 **전부 보내지 않는다**. 허용 목록이라 새 레코드 종류가 생겨도 저절로 새지 않는다. 근거는 실측이다: 대화록의 터미널 입출력 자리에 GitHub 토큰과 평문 비밀번호가 그대로 있었다(2026-09-04). 답변 본문에 남은 자격 증명은 서버의 시크릿 스캔이 받아 `sensitive` 표시와 로컬 백엔드 강제로 처리한다.

**사용 정책.** 플러그인의 스킬(`skills/kairos/SKILL.md`)이 "언제 저장고를 먼저 보는가"를 Claude에게 준다 — 툴이 등록돼도 이것이 없으면 거의 부르지 않는다. 같은 정책의 요약이 MCP 서버의 `instructions`에도 있어 스킬을 못 읽는 클라이언트(Codex·Antigravity)도 받는다.

---

## 2. Codex CLI와 그 밖의 클라이언트

**Codex.** 플러그인 체계가 없으므로 리포를 클론한 뒤 `codex-plugin/install.py install`이 MCP 등록·훅·스킬 3종·클라이언트를 `~/.codex`에 놓는다(decisions.md §127).

```bash
git clone https://github.com/noweel/kairos_mcp_client.git
python3 kairos_mcp_client/codex-plugin/install.py install
```
 스킬 `$kairos-status`·`$kairos-archive`가 슬래시 명령의 자리다. 자세한 것은 `codex-plugin/README.md`. **Antigravity**는 아직 어댑터가 없다 — MCP 등록은 설정의 `serverUrl`로 하고, 대화록 보관은 형식을 실측한 뒤 붙인다.
