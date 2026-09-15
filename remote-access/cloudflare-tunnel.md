# 밖에서 KAIROS에 접속하기: Cloudflare Tunnel (도메인 준비 뒤)

도메인을 산 뒤에 쓰는 둘째 방법이다. Cloudflare Tunnel로 `https://kairos.<도메인>`을 인터넷에 열고, Cloudflare Access로 그 앞에 로그인 관문을 하나 더 둔다. 공유기 포트는 열지 않는다. 서버의 `cloudflared`가 Cloudflare 쪽으로 연결을 먼저 만들기 때문이다.

Tailscale 앱을 설치할 수 없는 기기(회사 노트북 등)에서도 쓸 수 있다는 점이 [`tailscale.md`](tailscale.md)와 가장 크게 다르다. 대신 **게이트웨이가 인터넷에 노출되므로** 이 가이드의 순서를 지켜야 한다. 두 방법은 함께 운용할 수 있다.

명령과 메뉴 이름은 Cloudflare 공식 문서에서 2026-09-15에 확인했다. 대시보드 문구는 자주 바뀌므로 화면과 다르면 같은 뜻의 메뉴를 찾는다.

---

## 0. 시작하기 전에 알아 둘 것

### 0.1 Tailscale과 무엇이 다른가

| | Tailscale | Cloudflare Tunnel |
|---|---|---|
| 닿는 범위 | 내 계정으로 로그인한 기기만 | 인터넷 전체. 그래서 Access를 앞에 둔다 |
| 도메인 | 필요 없다 | Cloudflare에 올린 도메인이 필요하다 |
| 기기 준비 | 기기마다 앱 설치 | 브라우저만 있으면 된다 |
| 암호화 | 기기 사이 종단 간 암호화(WireGuard) | **Cloudflare에서 TLS가 풀린다** |

**Cloudflare가 트래픽의 평문을 본다.** Cloudflare가 HTTPS를 종료하므로, 뷰어에 뜨는 노트 원문과 요청에 실린 토큰이 Cloudflare 구간에서는 평문으로 처리된다. 저장고는 여전히 서버에만 있어서 기획서 대전제 2(로컬 완결)의 문구는 지켜진다. 그래도 전송 경로에 제3자가 들어온다는 사실은 달라지지 않는다. decisions.md §119가 공개 DNS를 쓰지 않는 조건에서 이 방법을 제외했던 이유가 이것이다.

### 0.2 DuckDNS로는 할 수 없다

터널로 트래픽을 넘기려면 DNS 레코드가 터널과 **같은 Cloudflare 계정**에 있어야 한다. `xxx.duckdns.org`는 내 소유 도메인이 아니라서 Cloudflare 계정에 올릴 수 없다. 도메인 없이 되는 Quick Tunnel(`trycloudflare.com`)은 실행할 때마다 주소가 바뀌고 Access를 붙일 수 없는 테스트용 기능이라서, 실제 저장고를 여는 용도로는 쓰지 않는다.

### 0.3 경로(`도메인/kairos`)가 아니라 서브도메인(`kairos.도메인`)으로 연다

경로 방식은 쓰지 않는다. 이유는 셋이다.

1. **토큰이 같은 오리진에 노출된다.** 뷰어는 토큰을 브라우저의 `localStorage`에 둔다. 이 결정은 "같은 오리진에 다른 스크립트가 없다"는 전제에서 내린 것이다(decisions.md §79). `도메인/kairos`에 두면 같은 도메인의 다른 페이지가 모두 같은 오리진이 되어, 그 페이지의 스크립트가 토큰을 읽을 수 있다.
2. **cloudflared는 경로를 벗기지 않는다.** 경로로 규칙을 고르기만 하고 `/kairos/…`를 그대로 넘긴다. 게다가 뷰어가 `/assets`·`/mcp`·`/internal`을 절대 경로로 부르므로, 경로 방식을 쓰려면 코드를 고쳐야 한다.
3. **앱 쪽에서 접두 경로를 붙이는 방식은 인증을 우회시킨다.** 실제 게이트웨이를 `Mount('/kairos', app)`로 감싸 재현해 보니, 인증 미들웨어가 `/kairos/internal/status`를 보호 경로로 알아보지 못해 토큰 없이 200을 돌려주었다(2026-09-15).

서브도메인으로 열면 게이트웨이와 뷰어의 코드를 바꿀 필요가 없다.

---

## 1. KAIROS 쪽을 먼저 준비한다: 로컬호스트 면제 끄기

**이 단계를 마치기 전에는 터널을 연결하지 않는다.**

`cloudflared`는 서버 안에서 `localhost:8080`으로 요청을 넘기므로, 게이트웨이는 인터넷에서 온 요청도 루프백에서 온 것으로 본다. 게이트웨이는 루프백에서 온 요청이 `Host` 헤더까지 localhost일 때 토큰을 면제한다(A8). 실제 게이트웨이로 재현한 결과는 다음과 같다(2026-09-15).

| 게이트웨이가 받은 요청 | 토큰 없는 요청의 결과 |
|---|---|
| 루프백에서 왔고, `Host`가 공개 호스트명이다 (cloudflared 기본값) | 401로 거절된다 |
| 루프백에서 왔고, `Host`가 localhost이며, `X-Forwarded-For`가 없다 (터널의 `HTTP Host Header`를 localhost로 바꾼 경우) | **`/internal/status`와 MCP `tools/list`가 200으로 응답한다** |
| 위와 같은데 `X-Forwarded-For`가 붙어 있다 | 401로 거절된다 |

기본 설정에서는 막히지만, 설정 한 칸을 잘못 바꾸면 저장고 전체가 토큰 없이 열린다. 또 cloudflared가 원래 `Host` 헤더를 그대로 넘긴다는 문장은 Cloudflare 문서에 없다. 따라서 **면제 자체를 끈다.** 절차는 [`tailscale.md`](tailscale.md) 7.2·7.3과 같다.

**① 서버 자신의 클라이언트에 토큰을 준다.** 지금 서버의 Claude Code는 면제 덕분에 토큰 없이 MCP 툴을 쓰고 있다.

```bash
# 서버의 셸 프로필(~/.bashrc)에 추가하고, 그 셸에서 claude를 다시 실행한다
export KAIROS_TOKEN="$(cat ~/.config/kairos/token)"
```

서버에서 Codex도 쓴다면 `~/.codex/config.toml`의 `[mcp_servers.kairos]` 구획에 `bearer_token_env_var = "KAIROS_TOKEN"`을 추가한다. 설치기는 루프백 주소를 받으면 이 줄을 넣지 않기 때문이다.

**② 면제를 끄고 게이트웨이를 재기동한다.**

```toml
# ~/.config/kairos/config.toml
[gateway]
localhost_token_exempt = false
```

```bash
systemctl --user restart kairos-gateway
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: localhost' http://127.0.0.1:8080/healthz
# 401 이 나와야 한다
```

**③ 서버의 Claude Code에서 `/kairos:status`를 실행해 「연결: 됨」을 확인한다.**

---

## 2. 도메인을 Cloudflare에 올린다

**Cloudflare Registrar에서 도메인을 사면 이 단계가 거의 끝난다.** Registrar의 도메인은 처음부터 Cloudflare 네임서버를 쓰기 때문이다.

다른 등록기관에서 샀다면 다음 순서로 옮긴다.

1. Cloudflare 대시보드의 **Domains**에서 **Onboard a domain**을 고르고, 루트 도메인(`example.com`)을 입력한 뒤 Free 플랜을 고른다.
2. 등록기관의 관리 화면에서 **DNSSEC이 켜져 있으면 먼저 끈다.** DNSSEC을 켠 채로 네임서버를 바꾸면 도메인에 접속할 수 없게 될 수 있다.
3. 등록기관의 네임서버를 지우고, Cloudflare가 알려 준 네임서버 두 개를 **글자 그대로** 입력한다.
4. 변경이 반영될 때까지 기다린다. 최대 24시간이 걸린다.

---

## 3. Access 로그인 관문을 먼저 만든다

터널보다 Access를 먼저 만들면, 주소가 인터넷에 열리는 첫 순간부터 로그인 관문이 서 있다. 메뉴는 모두 Zero Trust(Cloudflare One) 대시보드에 있다.

### 3.1 로그인 방법: 이메일 일회용 코드

**Zero Trust → Integrations → Identity providers → Add new identity provider → One-time PIN**을 추가한다. 새로 만든 Zero Trust 조직에는 이 방법이 자동으로 추가되지 않으므로 직접 추가해야 한다. 이제 로그인할 때 이메일로 받은 코드를 입력하게 된다.

### 3.2 애플리케이션과 허용 정책

**Zero Trust → Access controls → Applications → Create new application → Self-hosted and private**를 고른다.

- **Add public hostname**: 서브도메인에 `kairos`, 도메인에 내 도메인을 입력한다. 경로 칸은 비워 두어 호스트 전체를 보호한다.
- **정책**: 동작(Action)을 **Allow**로 두고, 포함(Include) 규칙에 **내 이메일 주소 하나만** 넣는다. 이메일 도메인 전체(`@gmail.com`)를 넣으면 그 도메인의 모든 사람이 로그인할 수 있으므로 주소를 정확히 적는다.
- **로그인 방법**: 3.1에서 추가한 One-time PIN을 고른다.

브라우저의 로그인 세션은 기본적으로 24시간 유지된다. 이 값은 **Access controls → Access settings**의 전역 세션 기간에서 15분부터 1개월 사이로 바꿀 수 있다.

### 3.3 MCP 클라이언트 경로 (지금은 임시 방편)

**현재 KAIROS 플러그인은 Access의 서비스 토큰 헤더를 보내지 못한다.** 따라서 3.2만 적용하면 브라우저 뷰어는 동작하지만, Claude Code와 Codex의 MCP 연결, 보관 훅은 Access에서 막힌다. 선택지는 둘이다.

**(가) MCP 클라이언트는 Tailscale로 쓴다: 권장.** 브라우저 뷰어만 Cloudflare로 열고, Claude Code와 Codex는 [`tailscale.md`](tailscale.md)의 주소를 쓴다. 이 경우 3.3에서 할 일은 없다.

**(나) Tailscale을 쓸 수 없는 기기라면 `/mcp`만 Access에서 뺀다.** 애플리케이션을 하나 더 만들어 경로에 `mcp`를 적고, 정책의 동작을 **Bypass**로 둔다. 경로가 겹칠 때는 더 구체적인 경로의 규칙이 우선 적용되므로, `/mcp`에는 Bypass가 적용되고 나머지 경로는 3.2의 로그인 관문이 그대로 지킨다.

(나)를 고를 때 감수해야 할 대가는 다음과 같다.

- `/mcp`는 **토큰 한 겹으로만** 보호된다. 토큰이 새면 인터넷 어디서든 검색·조회와 인입(쓰기 3종)을 할 수 있다. 다만 MCP 응답은 시크릿 스팬을 가리고, 쓰기에는 속도 제한이 걸린다.
- Cloudflare 문서는 Bypass가 해당 트래픽의 **Access 보안 통제와 요청 기록을 모두 끈다**고 설명하며, 사용자나 서비스의 상시 접근 수단으로 쓰지 말라고 권고한다.
- 원문 열람(시크릿 무마스킹), 재처리, 삭제 승인이 있는 `/internal/*`은 여전히 Access 뒤에 있다.

플러그인이 서비스 토큰을 보내게 되면 (나)의 Bypass를 **Service Auth** 정책으로 바꾼다(9번). 그때까지 (나)는 임시 방편이다.

---

## 4. cloudflared를 설치하고 터널을 만든다

### 4.1 설치

```bash
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared noble main' | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt-get update && sudo apt-get install cloudflared
```

### 4.2 터널 만들기 (대시보드 관리형)

Cloudflare는 대부분의 경우 대시보드에서 관리하는 터널을 권장한다. `config.yml`로 관리하는 방식은 로컬 개발이나 테스트용이라고 설명한다.

1. **Zero Trust → Networking → Tunnels → Create a tunnel**을 고르고, 커넥터 유형은 **Cloudflared**, 이름은 `kairos`로 저장한다.
2. 대시보드가 토큰이 채워진 설치 명령을 보여 준다. **이 토큰은 비밀이다.** 토큰을 가진 사람은 누구든 내 터널의 커넥터를 띄울 수 있으므로, 저장소나 메모에 남기지 않는다. 이 서버의 bash는 공백으로 시작하는 명령을 기록에 남기지 않도록 설정되어 있으므로(`HISTCONTROL=ignoreboth`), **명령 앞에 공백을 하나 넣어** 실행한다.

   ```bash
    sudo cloudflared service install <대시보드가_보여준_토큰>
   ```

3. 설치가 끝나면 서비스 상태를 확인하고, 대시보드의 터널 목록에서 상태가 정상으로 바뀌었는지 본다.

   ```bash
   systemctl status cloudflared --no-pager
   ```

### 4.3 주소 연결 (Published application route)

터널 설정의 **Published application route**(예전 명칭은 Public hostname)에서 경로를 하나 추가한다.

| 칸 | 값 |
|---|---|
| Subdomain | `kairos` |
| Domain | 내 도메인 |
| Path | 비워 둔다 |
| Service Type | `HTTP` |
| URL | `localhost:8080` |

**추가 설정의 `HTTP Host Header`는 비워 둔다.** 1번 표의 둘째 줄이 바로 이 값을 localhost로 바꿨을 때 생기는 일이다. 면제를 껐더라도 이 칸을 건드릴 이유는 없다.

네임서버가 Cloudflare에 있는 일반적인 구성이면 DNS의 CNAME 레코드가 자동으로 생긴다.

---

## 5. 밖에서 확인한다

집 Wi-Fi를 끈 휴대폰이나 다른 네트워크에서 확인한다. 노트북이라면 Tailscale을 잠시 끄고 확인한다.

**브라우저.** `https://kairos.<도메인>/`을 열면 **Cloudflare Access 로그인 화면**이 먼저 떠야 한다. 곧바로 KAIROS 화면이 뜬다면 3.2의 애플리케이션이 이 호스트명을 덮고 있지 않은 것이므로, 주소를 닫고 설정을 다시 확인한다.

**명령줄.** 로그인 쿠키가 없는 `curl`로 데이터 경로를 부른다. **데이터가 나오지 않으면 성공이다.**

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://kairos.<도메인>/internal/status
# 200이 아니어야 한다(Access 로그인으로 넘기는 응답이 온다)
```

3.3 (나)를 적용했다면 `/mcp`는 Access를 건너뛰고 게이트웨이의 토큰 검사에 걸린다.

```bash
curl -s -w '  %{http_code}\n' -X POST https://kairos.<도메인>/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
# {"error":"unauthorized"}  401
```

---

## 6. 클라이언트를 붙인다

**주소에는 반드시 `https://`를 붙인다.** 클라이언트는 스킴이 빠진 주소에 `http://`를 붙이는데, 그러면 토큰이 평문으로 나가거나 요청이 리다이렉트에서 막힌다.

**브라우저 뷰어.** 먼저 `https://kairos.<도메인>/`에서 Access 로그인을 마친다. 그다음 KAIROS 로그인 화면에 토큰을 넣거나, 로그인을 마친 같은 탭에서 `https://kairos.<도메인>/#token=<토큰>`을 연다. Access 로그인이 리다이렉트를 여러 번 거치므로, 로그인하기 전에 `#token=` 주소를 열면 토큰 조각이 중간에 사라질 수 있다. https에서는 딥링크 복사도 동작한다.

**Claude Code와 Codex.** 3.3에서 (가)를 골랐다면 Tailscale 주소를 그대로 쓴다. (나)를 골랐다면 주소만 바꾸고 토큰은 LAN과 같은 방식으로 둔다([`tailscale.md`](tailscale.md) 6번).

```
/kairos:setup https://kairos.<도메인>/mcp
python3 codex-plugin/install.py install --url https://kairos.<도메인>/mcp
```

**claude.ai 웹과 모바일 Claude 앱의 커넥터.** 연결이 Anthropic 클라우드에서 시작되고, 고정 헤더 인증은 조직 관리자가 입력하는 베타 기능이다. 개인 플랜에서 쓸 수 있는지는 확인하지 못했다. 이 가이드의 범위 밖이다.

---

## 7. 한도

| 항목 | Cloudflare Free | KAIROS 쪽 값 |
|---|---|---|
| 요청 본문 | 100 MB | `add_knowledge`의 base64 실질 상한은 약 3 MiB, 산출물은 32 MB라서 걸리지 않는다 |
| 응답 시작까지 기다리는 시간 | 125초를 넘기면 524 오류가 난다. Free 플랜에서는 바꿀 수 없다 | MCP 응답은 스트림이 아니라 JSON 한 번이다. 서버 안에서 잰 검색 한 번은 0.5초였다(실측 2026-09-15) |

---

## 8. 운용

**토큰이 샜을 때.** 서버에서 KAIROS 토큰을 새로 발급한다. 이전 토큰은 즉시 무효가 된다. 그다음 클라이언트와 브라우저에 새 토큰을 넣는다.

```bash
kairos --root ~/kairos-data token rotate
```

**터널 토큰이 샜을 때.** 대시보드에서 그 터널을 지우고 새로 만든다. 새 토큰으로 설치하기 전에 기존 서비스를 먼저 제거한다.

```bash
sudo cloudflared service uninstall
```

**잠시 닫기.** `sudo systemctl stop cloudflared`로 터널을 멈추면 공개 주소가 곧바로 닫힌다. Tailscale과 LAN 접속은 영향을 받지 않는다. 다시 열 때는 `sudo systemctl start cloudflared`를 실행한다.

**완전히 걷어 내기.** 대시보드에서 Published application route와 터널을 지우고, 서버에서 `sudo cloudflared service uninstall`을 실행한다. 1번에서 끈 로컬호스트 면제는 그대로 두어도 된다.

---

## 9. 아직 되지 않는 것과 다음 작업

- **플러그인이 Access 서비스 토큰을 보내게 한다.** Claude Code는 MCP 서버 설정에서 `headersHelper`를 지원한다. 연결할 때마다 명령을 실행하고 그 출력(JSON)을 요청 헤더에 합치는 기능이다. 플러그인의 `.mcp.json`에서도 쓸 수 있다. 이 기능으로 토큰 파일과 서비스 토큰을 읽어 헤더로 보내게 하면 두 가지가 함께 해결된다. 첫째, PC 앱의 MCP 툴에도 토큰이 실린다. 둘째, 3.3 (나)의 Bypass를 없애고 **Service Auth** 정책(`CF-Access-Client-Id`·`CF-Access-Client-Secret` 헤더)으로 바꿀 수 있다. 서비스 토큰은 **Access controls → Service credentials → Service Tokens**에서 만들며, Client Secret은 만들 때 한 번만 보인다. 이 작업은 플러그인 설정이 참조하는 비밀 값의 범위를 넓히는 일이라서, 진행하기 전에 결정이 필요하다.
- **claude.ai·모바일 Claude 앱 커넥터.** 6번에 적었듯이 인증 방식을 따로 검토해야 한다.

---

## 10. 문제 해결

| 증상 | 확인할 것 |
|---|---|
| 도메인에 접속되지 않는다 | 네임서버 변경이 반영됐는지(최대 24시간), DNSSEC을 끄고 바꿨는지 |
| 대시보드에서 터널이 정상 상태가 아니다 | `systemctl status cloudflared`, `journalctl -u cloudflared -n 50` |
| Access 로그인 없이 KAIROS 화면이 뜬다 | 3.2 애플리케이션의 호스트명이 `kairos.<도메인>`과 정확히 같은지 확인한다. 고칠 때까지 `sudo systemctl stop cloudflared`로 닫아 둔다 |
| 로그인 코드 메일이 오지 않는다 | 3.1의 One-time PIN을 추가했는지, 3.2 정책의 이메일 주소가 정확한지 |
| 브라우저에서 KAIROS가 401을 낸다 | Access는 통과했고 KAIROS 토큰이 없는 상태다. 뷰어 로그인 화면에 토큰을 넣는다 |
| Claude Code의 MCP 연결이 실패한다 | 3.3을 확인한다. (가)라면 Tailscale 주소를 쓰는지, (나)라면 `/mcp` 경로의 Bypass 애플리케이션이 있는지 |
| 524 오류 | 게이트웨이가 125초 안에 응답을 시작하지 못했다. `journalctl --user -u kairos-gateway`를 확인한다 |
| 서버의 MCP 툴이 401을 낸다 | 1번 ①을 건너뛰었다. 서버 셸의 `KAIROS_TOKEN`을 확인한다 |

---

## 출처

- 도메인: [Full setup](https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/) · [Registrar FAQ](https://developers.cloudflare.com/registrar/faq/)
- 설치: [Cloudflare packages](https://pkg.cloudflare.com/) · [Downloads](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/)
- 터널: [Create a remotely-managed tunnel](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel) · [Tunnel tokens](https://developers.cloudflare.com/tunnel/reference/tunnel-tokens/) · [Locally-managed tunnels](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/) · [Origin parameters](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/origin-parameters/) · [Configuration file (경로를 벗기지 않음)](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/configuration-file/) · [DNS 라우팅](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/routing-to-tunnel/dns/) · [Quick Tunnels](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/)
- Access: [Self-hosted public app](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/) · [Application paths](https://developers.cloudflare.com/cloudflare-one/access-controls/policies/app-paths/) · [Common policies](https://developers.cloudflare.com/cloudflare-one/access-controls/policies/common-policies/) · [One-time PIN](https://developers.cloudflare.com/cloudflare-one/integrations/identity-providers/one-time-pin/) · [Service tokens](https://developers.cloudflare.com/cloudflare-one/access-controls/service-credentials/service-tokens/) · [Authorization cookie](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/) · [Session management](https://developers.cloudflare.com/cloudflare-one/access-controls/access-settings/session-management/)
- 한도: [Error 413](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/4xx-client-error/error-413) · [Error 524](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-524/)
- 헤더: [HTTP request headers](https://developers.cloudflare.com/fundamentals/reference/http-request-headers/)
- Claude: [MCP headersHelper](https://code.claude.com/docs/en/mcp) · [Connector authentication](https://claude.com/docs/connectors/building/authentication)
