# KAIROS 설치·운용

빈 Ubuntu 기계에 KAIROS를 세우는 절차다. **주 서버는 Ubuntu이고**(기획서 §7.0 배포 환경), Windows에서는 브라우저로 게이트웨이에 붙는다.

프로세스는 여섯이고(봇은 선택) **서로를 필수로 요구하지 않는다.** 이것이 편의가 아니라 설계다: §7.0이 "모델 서버가 없어도 기동은 성공한다 — 수집은 계속되고 정규화만 대기하다 복구 시 자동 재개한다"를 규정하므로, 유닛에 `Requires=`를 걸면 모델 장애가 인입 장애가 되어 그 규정이 뒤집힌다.

| 프로세스 | 유닛 | 없으면 |
|---|---|---|
| 수신기 | `kairos-worker` | 인입이 멈춘다 |
| 게이트웨이 | `kairos-gateway` | MCP·뷰어가 닫힌다 |
| 텍스트 모델 (vLLM) | `kairos-vllm` | 정규화만 **대기**한다. 인입·추출·판정·저장은 그대로 돈다 |
| 임베딩 (BGE-M3, CPU) | `kairos-embed` | 층2와 태그 후보가 공백. FTS 검색은 그대로 |
| Telegram 봇 (선택) | `kairos-tg` | 모바일 인입만 멈춘다. 코어는 무관 |
| 온디맨드 VLM | `kairos-vllm-vlm` | 이미지가 raw로 보존되고 재처리 큐에 남는다 |

---

## 1. 설치

```bash
git clone <저장소> ~/Workspace/kairos && cd ~/Workspace/kairos
pip install -e '.[embed]'          # 임베딩을 이 기계에서 돌릴 때만 [embed]
```

**`[embed]`는 선택이다.** torch·transformers가 여기에만 걸려 있으므로, 임베딩을 다른 기계나 다른 구현에 두는 구성에서는 `pip install -e .`만 하면 된다(decisions.md §89).

SQLite는 **3.43 이상**이어야 한다(11-A A1 — `RETURNING`과 `contentless_delete`). 미달이면 기동이 명확히 실패한다.

```bash
python3 -c "import sqlite3; print(sqlite3.sqlite_version)"
```

## 2. 저장고 만들기

```bash
kairos --root ~/kairos-data init
```

vault 레이아웃과 `queue.db`·`index.db`를 만들고, **저장고를 git 저장소로 두고 bare 사본을 붙인다**(`~/kairos-data/vault.git`). 기획서 §5.4가 자동 삭제를 "vault가 git이므로 복구 가능"으로 정당화하므로 그 전제가 여기서 선다(decisions.md §83).

## 3. 설정

```bash
mkdir -p ~/.config/kairos
cp deploy/systemd/kairos.env.example ~/.config/kairos/kairos.env
$EDITOR ~/.config/kairos/kairos.env          # 경로 넷을 자기 환경으로
```

KAIROS 자체 설정은 `~/.config/kairos/config.toml`이고 **전 키가 11-A A9에 있다.** 없으면 전부 기본값으로 돈다. 최소 예시:

```toml
schema_version = 1

[gateway]
bind = "0.0.0.0"        # LAN 개방 — 데이터 경로는 토큰 필수, SPA 셸만 공개
port = 8080
spa_dir = "/home/YOU/Workspace/kairos/viewer/dist"

[normalizer]
timeout_base_s = 180    # 32GB 티어 실측값(decisions.md §41)
```

## 4. 뷰어 빌드

```bash
cd viewer && npm ci && npm run build
```

**별도 서버 프로세스가 없다** — 게이트웨이가 `spa_dir`를 정적 서빙하고 SPA는 같은 오리진의 `/mcp`·`/internal/*`을 부른다(decisions.md §54). npm은 전부 빌드 타임이라 런타임 신규 의존성은 0이다.

## 5. 유닛 등록

```bash
mkdir -p ~/.config/systemd/user
cp deploy/systemd/*.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now kairos-vllm kairos-embed kairos-worker kairos-gateway
systemctl --user enable --now kairos-tg        # Telegram 봇을 쓸 때만 (§9)
```

**서빙 옵션은 유닛이 아니라 `kairos.env`에 있다.** 기획서 §7.1이 "모델과 서빙 옵션을 한 쌍으로 기록한다"고 정한 대로, 티어로 정해지는 값(모델 경로·컨텍스트 길이·GPU 점유·KV dtype·`compilation-config`·사고 모드·구조화 출력 백엔드)이 전부 모델 경로와 **같은 파일**에 모여 있다. 모델을 바꾸면 그 묶음을 함께 본다.

JSON 값은 반드시 큰따옴표로 감싸 넘긴다(`"$KAIROS_TEXT_COMPILE"`). 값에 공백이 있어 감싸지 않으면 `sh`가 쪼개고, vLLM은 알 수 없는 인자로 죽는다. **systemd의 `EnvironmentFile`은 따옴표와 공백을 그대로 보존한다** — `sh`로 직접 `source` 했을 때와 다르므로 그것으로 확인하면 안 된다. 확인은 이렇게 한다.

```bash
systemd-run --user --wait --pipe --collect \
  -p EnvironmentFile=%h/.config/kairos/kairos.env \
  /bin/sh -c 'printf "%s\n" "$KAIROS_TEXT_COMPILE"'
```

**`kairos-vllm-vlm`은 enable하지 않는다.** 수신기가 필요할 때 `systemctl --user start`로 올리고 유휴 TTL에 내린다(§7.1 — 판단 태스크 여덟 중 비전은 하나뿐이라 상시 상주가 비용 대비 이득이 없다). 메인 모델이 비전을 겸하는 티어에서는 이 유닛을 아예 쓰지 않고 config에 `[llm.backend] vlm_describe = "local"`을 둔다(스왑 0).

로그아웃 뒤에도 유닛이 살아 있으려면 lingering이 필요하다.

```bash
loginctl enable-linger $USER
```

## 6. 확인

```bash
systemctl --user status kairos-worker kairos-gateway --no-pager
curl -s http://127.0.0.1:8002/health                      # 임베딩
curl -s http://127.0.0.1:8000/v1/models | head -c 200     # 텍스트 모델
kairos --root ~/kairos-data status
```

기동 로그에 **어느 코드로 도는지**가 찍힌다. 재기동을 잊었을 때 이것이 유일한 단서다(decisions.md §84 이전 기록).

```
INFO kairos.cli kairos-gateway 기동 — 코드 0.1.0+<커밋>
```

## 7. 접속

LAN에서 열려면 토큰이 필요하다(A8 — **LAN 요청은 설정과 무관하게 토큰 필수**).

```bash
kairos --root ~/kairos-data token show
```

뷰어는 `http://<서버>:8080`이다. 토큰을 넣는 대신 **비밀번호를 설정해 두면** 이후 재접속은 비밀번호로 연다. Windows·모바일에서는 이 주소를 브라우저로 열면 되고, **KAIROS를 그쪽에 설치하지 않는다.**

---

## 8. Claude Code 연결 — 플러그인

Claude Code와의 연결은 **플러그인 하나**로 끝난다(`deploy/claude-plugin/`, decisions.md §102). 설치하면 MCP 서버 등록·대화 보관 훅·사용 정책 스킬·`/kairos:status`·`/kairos:archive`가 한 번에 붙는다. 손으로 `claude mcp add`를 치거나 `settings.json`을 편집할 일이 없다.

```bash
claude plugin marketplace add ./deploy/claude-plugin     # 이 리포를 마켓플레이스로
claude plugin install kairos@kairos                       # 사용자 스코프 — 모든 프로젝트
```

다른 기계에서는 `deploy/claude-plugin/` 디렉토리만 복사해 같은 두 줄을 친다. 플러그인 안의 스크립트는 표준 라이브러리만 쓰므로 KAIROS 체크아웃이 필요 없다.

**갱신.** 설치본은 리포의 **복사본**이다(`~/.claude/plugins/cache/kairos/kairos/<버전>/`). `deploy/claude-plugin/`을 고쳐도 설치본은 그대로이므로, 바꾼 뒤에는 `plugin.json`의 `version`을 올리고 `claude plugin update kairos@kairos`를 친다. 게이트웨이·워커를 함께 재기동해야 하는 것과 같은 성격의 어긋남이다 — 고친 코드가 어디서 돌고 있는지가 다르다. 손보기 전 `claude plugin validate ./deploy/claude-plugin/kairos`로 규격을 확인한다.

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

**Codex·Antigravity.** 플러그인 체계가 없으므로 `deploy/claude-plugin/kairos/scripts/kairos-client`를 복사해 `replay --transcript <대화록>`으로 명시 보관한다. MCP 등록은 각 클라이언트의 설정에 `url`(Codex) / `serverUrl`(Antigravity)로 한다. 대화록 어댑터는 Claude Code 것만 있다 — 두 클라이언트의 형식은 실측 뒤 붙인다.

---

## 9. Telegram 봇 — 모바일 인푸터 (선택)

기획서 §6.2의 인입 전용 봇이다(decisions.md §111). 검색은 하지 않는다 — 모바일 검색·열람은 LAN 뷰어가 맡는다.

**준비.** BotFather에서 봇을 만들어 토큰을 받고, 자기 Telegram `user_id`(숫자)를 확인한다(`@userinfobot` 같은 봇이 알려 준다). 토큰은 **env 파일**에, user_id는 **config**에 둔다 — 토큰은 시크릿이라 설정 파일에 두지 않는다.

```bash
# ~/.config/kairos/kairos.env (0600)
KAIROS_TG_TOKEN=123456789:AA...

# ~/.config/kairos/config.toml
[telegram]
allowed_user_id = 123456789      # 본인 하나. 그 밖의 발신자에게는 무응답이다
```

`systemctl --user enable --now kairos-tg`로 띄운다. 토큰이 없으면 유닛은 기동하지 않고 종료한다(`journalctl --user -u kairos-tg`).

**보내는 법.** 텍스트·링크·사진·파일을 봇에게 보내면 접수 회신이 오고, 정규화가 끝나면 제목·요약·노트 ID·딥링크가 회신된다(기본 15분까지 기다리고, 넘으면 "아직 처리 중"). 캡션의 `#태그`는 태그가 되고 나머지는 인입 메모가 된다. 화면 캡처 사진은 `#capture`를 붙이면 OCR 우선으로 읽는다. 앨범으로 보낸 여러 장은 한 묶음(`batch`)이 된다. Bot API 상한(20 MB)을 넘는 파일은 받을 수 없으니 vault-inbox에 넣는다. 음성·영상은 원본만 보관된다(raw).

**상태.** `kairos status`의 큐 항목과 `kairos trace <queue_id>`가 봇이 보는 것과 같은 사실을 보인다 — 회신이 안 오면 거기서 본다. 오프셋·대기 목록은 `<root>/telegram/`에 있다.

## 운용

### 재기동

```bash
systemctl --user restart kairos-gateway kairos-worker kairos-tg
```

**DDL(`kairos/db/*.sql`)이 바뀌었으면 `kairos --root $KAIROS_ROOT rebuild-index`를 돌린다.** 마이그레이션 기구는 따로 없다 — 인덱스는 파생물이라 재생성이 곧 마이그레이션이고 `events`는 보존된다. 안 돌리면 쓰기가 전부 조용히 실패한다: 워커는 기동을 거부하고 `kairos status`가 `SCHEMA DRIFT`를 찍는다(decisions.md §112).

**코드를 고쳤으면 반드시 재기동한다.** 돌고 있는 프로세스는 옛 코드를 계속 서빙하고, 증상은 원인과 동떨어진 형태(새 엔드포인트가 404 등)로만 보인다.

**스키마를 고쳤으면 둘을 함께 재기동한다.** 게이트웨이와 워커는 별개 프로세스라 한쪽만 올리면 **버전이 어긋난 채로 계속 돈다**. 실측(2026-09-04, `origin.part` 추가): 게이트웨이만 올렸더니 턴 인입은 전부 성공하는데 워커가 새 IR을 읽지 못해 `정의되지 않은 키: part` 경고를 30초마다 남기며 세션 통합만 조용히 건너뛰었다. 큐도 로그도 "정상"으로 보이므로 눈치채기 어렵다.

```bash
journalctl --user -u kairos-worker -n 30 --no-pager   # 어긋남은 여기서만 보인다
```

### 백업

- **`notes/`·`meta/`는 git이 맡는다** — 감쇠 배치가 하루 한 번 커밋하고 `~/kairos-data/vault.git`에 밀어 넣는다(Store §8).
- **`assets/`는 git 밖이다**(대용량 바이너리). 외장 rsync 대상이며, 자동 삭제는 노트만 지우고 원본은 남긴다(§5.4 — 정규화는 손실 압축이라 원본이 최후의 비가역 지점).

### 전체 초기화

```bash
kairos --root ~/kairos-data reset --confirm '/home/YOU/kairos-data'
```

**되돌릴 수 없다.** 지우기 전에 커밋하고 복구 지점을 출력하며, 이력이 없으면 거절한다. `.git`과 bare 사본은 남긴다. 확인 문구가 고정 문구가 아니라 루트 경로 자체인 이유는, 고정 문구가 손에 익어 무의미해지기 때문이다.

### 인덱스 재생성

```bash
kairos --root ~/kairos-data rebuild-index
```

인덱스는 전부 파생물이므로 지워도 vault에서 완전히 재생성된다(절대 원칙 1). 유일한 예외는 `events`(감사 이력)이고, 그것은 재생성되지 않는다.
