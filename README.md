# KAIROS 설치·운용

빈 Ubuntu 기계에 KAIROS를 세우는 절차다. **주 서버는 Ubuntu이고**(기획서 §7.0 배포 환경), Windows에서는 브라우저로 게이트웨이에 붙는다.

프로세스는 다섯이고 **서로를 필수로 요구하지 않는다.** 이것이 편의가 아니라 설계다: §7.0이 "모델 서버가 없어도 기동은 성공한다 — 수집은 계속되고 정규화만 대기하다 복구 시 자동 재개한다"를 규정하므로, 유닛에 `Requires=`를 걸면 모델 장애가 인입 장애가 되어 그 규정이 뒤집힌다.

| 프로세스 | 유닛 | 없으면 |
|---|---|---|
| 수신기 | `kairos-worker` | 인입이 멈춘다 |
| 게이트웨이 | `kairos-gateway` | MCP·뷰어가 닫힌다 |
| 텍스트 모델 (vLLM) | `kairos-vllm` | 정규화만 **대기**한다. 인입·추출·판정·저장은 그대로 돈다 |
| 임베딩 (BGE-M3, CPU) | `kairos-embed` | 층2와 태그 후보가 공백. FTS 검색은 그대로 |
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

## 8. 대화 아카이브 훅 (선택)

에이전트 CLI의 대화를 저장고로 넣는 클라이언트 쪽 도구다. `deploy/hooks/kairos-archive` 한 파일이며 **표준 라이브러리만 쓴다** — KAIROS 체크아웃이 없는 다른 기계에 이 파일만 복사해도 돈다.

```bash
install -m 755 deploy/hooks/kairos-archive ~/bin/kairos-archive
export KAIROS_URL=http://<서버>:8080/mcp        # 원격이면 필수
export KAIROS_TOKEN_FILE=~/.config/kairos/token  # 또는 KAIROS_TOKEN
```

**먼저 무엇이 갈지 본다.** 아무것도 전송하지 않는다.

```bash
kairos-archive replay --transcript ~/.claude/projects/<슬러그>/<uuid>.jsonl --dry-run
```

괜찮으면 전송한다. 두 번째 실행은 이미 보낸 턴을 다시 보내지 않는다(상태 파일이 이어가는 자리를 안다).

```bash
kairos-archive replay --transcript <대화록> --max-turns 50
```

**보내는 것과 보내지 않는 것.** 사람이 실제로 친 프롬프트와 어시스턴트의 답변 텍스트만 간다. 도구 호출·도구 결과·사고 블록·슬래시 명령 출력·터미널 입출력·부수 대화(서브에이전트)는 **전부 보내지 않는다**. 허용 목록이라 새 레코드 종류가 생겨도 저절로 새지 않는다. 근거는 실측이다: 대화록의 터미널 입출력 자리에 GitHub 토큰과 평문 비밀번호가 그대로 있었다(2026-09-04). 답변 본문에 남은 자격 증명은 서버의 시크릿 스캔이 받아 `sensitive` 표시와 로컬 백엔드 강제로 처리한다.

**자동 실행은 기본이 아니다**(11-B-2 — 명시 요청만). 잡담 세션까지 전부 노트가 되면 §2.1이 막으려던 검색 노이즈가 세션 단위로 돌아온다. 그래도 자동으로 걸겠다면 `~/.claude/settings.json`에 둔다.

```json
{"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "~/bin/kairos-archive hook"}]}]}}
```

훅은 에이전트를 막지 않는다 — 대화록을 못 찾거나 입력이 깨져도 조용히 0을 돌려준다. 전송 속도는 분당 45회로 게이트웨이 상한(60) 아래에 잡혀 있고, 한도에 걸리면 기다렸다 다시 시도한다.

---

## 운용

### 재기동

```bash
systemctl --user restart kairos-gateway kairos-worker
```

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
