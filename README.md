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

## 운용

### 재기동

```bash
systemctl --user restart kairos-gateway
```

**코드를 고쳤으면 반드시 재기동한다.** 돌고 있는 프로세스는 옛 코드를 계속 서빙하고, 증상은 원인과 동떨어진 형태(새 엔드포인트가 404 등)로만 보인다.

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
