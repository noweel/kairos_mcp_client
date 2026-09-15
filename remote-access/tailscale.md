# 밖에서 KAIROS에 접속하기: Tailscale

집 서버의 KAIROS를 밖에서 쓰기 위한 첫째 방법이다(decisions.md §119 ①). Tailscale로 내 기기끼리만 닿는 사설망을 만들고, 밖에 있는 노트북과 폰을 그 망에 넣는다. 게이트웨이는 인터넷에 노출되지 않으며, **KAIROS의 코드와 설정은 바꾸지 않는다.**

도메인을 사서 인터넷에 공개하는 방법은 [`cloudflare-tunnel.md`](cloudflare-tunnel.md)에 따로 정리했다. 공유기 포트포워딩과 DuckDNS는 이 두 방법 어디에도 필요하지 않다.

모든 명령과 메뉴 이름은 Tailscale 공식 문서에서 2026-09-15에 확인했다. 콘솔 화면의 문구는 이후에 바뀔 수 있다.

---

## 0. 무엇이 되고 무엇이 안 되나

**동작 방식.** 로그인한 기기마다 `100.x.y.z` 주소가 붙고, 기기끼리 WireGuard로 암호화해 연결한다. 방화벽 때문에 직접 연결이 막히면 Tailscale의 중계 서버(DERP)를 거쳐 우회한다. 공유기 설정과 공인 IP는 필요하지 않다.

**인터넷 속도에는 영향을 주지 않는다.** 공식 문서에 따르면 Tailscale은 기본적으로 Tailscale 기기 사이의 트래픽만 전달하고, 일반 인터넷 트래픽은 건드리지 않는다. 모든 트래픽이 집을 거치게 되는 경우는 exit node를 따로 켰을 때뿐이며, 이 가이드에서는 exit node를 쓰지 않는다. KAIROS 통신량도 작다. 실측해 보니 검색 한 번이 37 KB, 그래프 전체가 1.1 MB, 뷰어의 첫 로딩이 3.7 MB였다(2026-09-15).

**KAIROS 입장에서는 LAN이 넓어지는 것과 같다.** 게이트웨이는 이미 `0.0.0.0:8080`에서 토큰 인증으로 LAN 요청을 받고 있다. Tailscale 기기는 `100.x` 주소로 접속하는데 이 주소는 루프백이 아니므로, 지금과 똑같이 토큰이 있어야만 데이터가 나간다.

**이 방법으로 되지 않는 것.**

- **Tailscale 앱을 설치할 수 없는 기기에서는 쓸 수 없다.** 회사 노트북에 VPN 클라이언트를 설치할 수 없다면 Cloudflare 방식으로 가야 한다.
- **claude.ai 웹과 모바일 Claude 앱의 커넥터로는 붙을 수 없다.** 커넥터 연결은 Anthropic 클라우드에서 시작되므로 내 사설망에 닿지 않는다. 휴대폰의 **브라우저 뷰어**는 폰에 Tailscale 앱을 설치하면 쓸 수 있다.

---

## 1. 서버에 설치하고 로그인한다

Ubuntu 24.04 기준이다. 공식 설치 스크립트를 쓰는 방법이 가장 짧다.

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

스크립트를 파이프로 실행하고 싶지 않다면 apt 저장소를 직접 등록한다.

```bash
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.noarmor.gpg | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.tailscale-keyring.list | sudo tee /etc/apt/sources.list.d/tailscale.list
sudo apt-get update && sudo apt-get install tailscale
```

설치가 끝나면 로그인한다. 명령이 인증 URL을 출력하므로, 그 URL을 브라우저에서 열어 쓸 계정으로 로그인한다.

```bash
sudo tailscale up
tailscale status          # 서버가 목록에 보이면 된다
tailscale ip -4           # 서버의 100.x 주소
systemctl status tailscaled --no-pager
```

---

## 2. 관리 콘솔에서 서버 기기를 정리한다

관리 콘솔(`login.tailscale.com/admin`)의 **Machines** 페이지에서 두 가지를 정리한다.

**이름을 짧게 바꾼다.** 기기 이름은 기본적으로 OS 호스트명에서 만들어지므로, 서버처럼 호스트명이 길면 주소도 길어진다. 서버 행의 메뉴에서 **Edit machine name**을 골라 `kairos`처럼 짧은 이름으로 바꾼다. 이 가이드의 이후 예시는 서버 이름을 `kairos`로 가정한다. MagicDNS는 2022-10-20 이후에 만든 tailnet에서 기본으로 켜져 있으므로, 이름을 바꾸면 곧바로 `kairos` 또는 `kairos.<tailnet이름>.ts.net`으로 접속할 수 있다.

**서버의 키 만료를 끈다.** 노드 키는 기본적으로 180일이 지나면 만료되고, 만료된 기기는 다시 로그인하기 전까지 tailnet에서 빠진다. 서버는 사람이 매번 로그인해 줄 수 없으므로, 서버 행의 오른쪽 끝 메뉴에서 **Disable Key Expiry**를 고른다. 노트북과 폰은 기본값(만료 켜짐)으로 두어도 된다.

---

## 3. 서버 방화벽을 연다

이 서버에서는 `ufw`가 켜져 있다(2026-09-15 확인). `ufw`에 `tailscale0` 인터페이스를 허용하는 규칙이 없으면 밖의 기기에서 보낸 요청이 게이트웨이에 닿지 않는다. 먼저 현재 규칙을 확인한다.

```bash
sudo ufw status
```

게이트웨이 포트만 여는 규칙을 권한다. 사설망 안에서도 필요한 포트만 열어 두는 편이 안전하다.

```bash
sudo ufw allow in on tailscale0 to any port 8080 proto tcp
```

SSH처럼 다른 서비스도 Tailscale로 쓰려면 Tailscale 공식 문서가 안내하는 대로 인터페이스 전체를 연다.

```bash
sudo ufw allow in on tailscale0
```

---

## 4. 쓸 기기에 앱을 설치한다

노트북과 폰에 앱을 설치하고, **서버와 같은 계정으로** 로그인한다.

| 기기 | 받는 곳 |
|---|---|
| Windows | https://tailscale.com/download/windows |
| macOS | https://tailscale.com/download/mac |
| iPhone | https://tailscale.com/download/ios |
| Android | https://tailscale.com/download/android |

같은 계정으로 로그인한 기기끼리는 기본 정책에서 서로 접속할 수 있으므로, 접근 정책(ACL)을 따로 편집하지 않아도 된다.

로그인한 뒤 노트북에서 연결 상태를 확인한다.

```bash
tailscale ping kairos
```

출력에 `via <IP>:<포트>`가 나오면 직접 연결이고, `via DERP(<지역>)`이 나오면 중계를 거치고 있다는 뜻이다. 중계를 거쳐도 기능은 모두 동작하지만 조금 느려질 수 있다. 직접 연결이 되지 않는 원인을 찾을 때는 `tailscale netcheck`로 지금 네트워크 상태를 진단한다.

---

## 5. 게이트웨이까지 닿는지 확인한다

노트북에서 토큰 없이 `/healthz`를 부른다. **401이 나오면 성공이다.** 게이트웨이까지 도달했고, 토큰이 없어서 거절당했다는 뜻이다.

```bash
curl -s -w '  %{http_code}\n' http://kairos:8080/healthz
# {"error":"unauthorized"}  401
```

시간 초과가 나면 3번의 방화벽 규칙을 확인하고, 이름을 찾지 못한다는 오류가 나면 전체 이름인 `kairos.<tailnet이름>.ts.net`을 쓴다. 클라이언트에 따라 짧은 이름이 풀리지 않을 수도 있기 때문이다.

토큰을 넣고 다시 부르면 게이트웨이가 정상 응답을 준다.

```bash
curl -s -H "Authorization: Bearer $KAIROS_TOKEN" http://kairos:8080/healthz
# {"ok":true,"mcp":"/mcp"}
```

---

## 6. KAIROS 클라이언트를 붙인다

**Tailscale 주소는 집에서도 그대로 동작한다.** 같은 LAN에 있으면 Tailscale이 직접 연결을 잡기 때문에, 집과 밖에서 주소를 바꿔 쓸 필요가 없다. 따라서 LAN 주소(`192.168.x.x`) 대신 `http://kairos:8080`을 모든 클라이언트에 적어 두는 편이 편하다.

**토큰은 서버에서 확인한다.** 이 명령은 토큰 값을 화면에 출력하므로, 옆에 다른 사람이 없을 때 실행한다. 토큰을 메신저나 메모 앱에 붙여 두지 않는다.

```bash
kairos --root ~/kairos-data token show
```

### Claude Code

주소는 설치기나 `/kairos:setup`으로 적는다. 그러면 Claude Code의 설정 파일(`~/.claude/settings.json`의 `env`)에 주소가 저장된다.

```
/kairos:setup http://kairos:8080/mcp
```

토큰은 두 자리에서 읽는다. 이 차이를 알아야 401의 원인을 찾을 수 있다.

| 쓰는 곳 | 토큰을 읽는 자리 |
|---|---|
| MCP 툴(검색·조회·인입) | 환경 변수 `KAIROS_TOKEN`만 읽는다. 플러그인의 `.mcp.json`이 `${KAIROS_TOKEN}`을 참조한다 |
| 훅과 슬래시 명령(보관·상태) | `KAIROS_TOKEN`을 먼저 보고, 없으면 토큰 파일 `~/.config/kairos/token`을 읽는다 |

터미널에서 쓰는 CLI라면 셸 프로필에 토큰을 두고 그 셸에서 `claude`를 실행한다.

```bash
# ~/.bashrc 또는 ~/.zshrc
export KAIROS_TOKEN="<서버에서 확인한 토큰>"
```

**Windows에서는 CLI와 PC 앱 모두 사용자 환경 변수에 토큰을 둔다.** PC 앱은 셸 프로필과 PowerShell 프로필을 읽지 않지만, 사용자 환경 변수는 물려받는다. PowerShell에서 아래 명령을 실행하면 토큰 파일의 값이 화면에 출력되지 않고 옮겨진다. 그다음 PowerShell 창을 새로 열고, PC 앱은 트레이까지 완전히 종료했다가 다시 실행한다. 이 방법으로 `claude mcp list`의 `√ Connected`와 PC 앱의 검색이 동작하는 것을 확인했다(2026-09-15).

```powershell
$t = (Get-Content "$env:USERPROFILE\.config\kairos\token" -Raw).Trim()
[Environment]::SetEnvironmentVariable("KAIROS_TOKEN", $t, "User")
Remove-Variable t
```

토큰 파일이 없다면 `Win + R`에 `rundll32 sysdm.cpl,EditEnvironmentVariables`를 입력하고, 사용자 변수에 `KAIROS_TOKEN`을 새로 만들어 값을 붙여 넣는다. `setx KAIROS_TOKEN <값>`처럼 값을 명령줄에 쓰면 PowerShell 기록 파일에 토큰이 남으므로 쓰지 않는다.

**PC 앱에서는 `/mcp`로 연결을 확인할 수 없다.** 새 **Local** 세션을 열고 저장고 검색을 시켜 확인한다. 플러그인을 설치하거나 업데이트한 뒤에는 `/reload-plugins`로 MCP 서버가 연결되지 않으므로 새 세션을 연다.

**macOS PC 앱은 실측하지 않았다.** 공식 문서에 따르면 Dock이나 Finder에서 실행한 앱은 셸 프로필에서 `PATH`와 정해진 Claude Code 변수만 가져오므로, `export KAIROS_TOKEN`이 앱에 전달되지 않을 수 있다.

설치와 문제 해결의 자세한 절차는 [`../README.md`](../README.md) §1과 [`../claude-plugin/README.md`](../claude-plugin/README.md)에 있다.

### Codex CLI

```bash
python3 codex-plugin/install.py install --url http://kairos:8080/mcp
export KAIROS_TOKEN="<서버에서 확인한 토큰>"     # 셸 프로필에 둔다
```

설치기는 루프백이 아닌 주소를 받으면 `~/.codex/config.toml`에 `bearer_token_env_var = "KAIROS_TOKEN"`을 적는다. 값이 아니라 변수 이름만 적힌다.

### 브라우저 뷰어 (노트북·폰)

`http://kairos:8080/`을 열고 로그인 화면에 토큰을 넣는다. 폰에서는 `http://kairos:8080/#token=<토큰>`을 열면 토큰을 손으로 옮겨 적지 않아도 된다. 토큰 값은 주소창에서 곧바로 지워지고 브라우저 저장소에 남는다.

http로 열면 **딥링크 복사가 동작하지 않는다.** 브라우저의 클립보드 API가 https나 localhost에서만 열리기 때문이다(decisions.md §125). 이 기능이 필요하면 7번의 HTTPS 설정을 추가로 진행한다.

---

## 7. (선택) HTTPS로 열기: `tailscale serve`

`tailscale serve`를 쓰면 `https://kairos.<tailnet이름>.ts.net`이라는 주소가 생긴다. 인증서는 Tailscale이 발급해 준다. 이 주소도 **tailnet 안에서만** 접속된다. 인터넷에 공개하는 `tailscale funnel`은 이 가이드에서 쓰지 않는다. 공개가 필요하다면 접근 제어를 한 겹 더 두는 Cloudflare 방식이 적합하다.

### 7.1 먼저 알아 둘 것

**기기 이름이 공개 기록에 남는다.** HTTPS 인증서를 켜면 기기 이름과 tailnet 이름이 인증서 투명성(Certificate Transparency) 공개 기록에 올라간다. Tailscale 문서는 기기 이름에 민감한 정보가 들어 있으면 HTTPS를 켜지 말라고 안내한다. `kairos`라는 이름 자체는 민감하지 않지만, 호스트명에 실명이나 조직명이 들어 있다면 2번에서 먼저 이름을 바꾼다.

**serve를 켜기 전에 로컬호스트 면제를 꺼야 한다.** 이 절에서 가장 중요한 단계다. `tailscale serve`는 받은 요청을 서버 안에서 `localhost:8080`으로 넘기므로, 게이트웨이는 모든 요청을 루프백에서 온 것으로 본다. 게이트웨이는 루프백에서 온 요청이 `Host` 헤더까지 localhost일 때 토큰을 면제한다(A8). 그런데 serve가 원래 `Host` 헤더와 `X-Forwarded-For`를 그대로 전달하는지는 Tailscale 문서에 적혀 있지 않다. 실제 게이트웨이로 재현한 결과는 다음과 같다(2026-09-15).

| 게이트웨이가 받은 요청 | 토큰 없는 요청의 결과 |
|---|---|
| 루프백에서 왔고, `Host`가 공개 이름이다 | 401로 거절된다 |
| 루프백에서 왔고, `Host`가 localhost이며, `X-Forwarded-For`가 없다 | **`/internal/status`와 MCP `tools/list`가 200으로 응답한다** |

프록시의 헤더 처리 방식에 기대지 않으려면 면제 자체를 끄면 된다. 면제를 끄면 루프백에서 온 요청에도 토큰이 필요해지므로, **서버 자신의 클라이언트에 먼저 토큰을 준다.**

### 7.2 서버 자신의 클라이언트에 토큰을 준다

지금 서버의 Claude Code는 로컬호스트 면제 덕분에 토큰 없이 MCP 툴을 쓰고 있다. 면제를 끄기 전에 아래 항목을 먼저 처리하지 않으면 서버의 MCP 툴이 401로 멈춘다.

- **Claude Code(서버)**: 서버의 셸 프로필에 다음 줄을 넣고, 그 셸에서 `claude`를 다시 실행한다. 토큰 파일을 읽어 변수에 담으므로 값이 화면에 나오지 않는다.

  ```bash
  export KAIROS_TOKEN="$(cat ~/.config/kairos/token)"
  ```

- **Codex(서버)**: 설치기는 루프백 주소를 받으면 `bearer_token_env_var` 줄을 넣지 않는다. `~/.codex/config.toml`의 `[mcp_servers.kairos]` 구획에 `bearer_token_env_var = "KAIROS_TOKEN"`을 직접 추가한다. 설치기를 다시 실행하면 이 줄이 사라지므로, 그때는 줄을 다시 추가한다.
- **훅과 슬래시 명령**: 토큰 파일을 읽으므로 따로 할 일이 없다.
- **서버에서 localhost로 연 뷰어**: 로그인 화면에 토큰을 한 번 넣는다.

### 7.3 면제를 끄고 확인한다

`~/.config/kairos/config.toml`의 `[gateway]` 구획에 한 줄을 추가하고 게이트웨이를 재기동한다.

```toml
[gateway]
localhost_token_exempt = false
```

```bash
systemctl --user restart kairos-gateway
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: localhost' http://127.0.0.1:8080/healthz
# 401 이 나와야 한다. 200이면 설정이 반영되지 않은 것이다
```

그다음 서버의 Claude Code에서 `/kairos:status`를 실행해 「연결: 됨」이 나오는지 확인한다.

### 7.4 serve를 켠다

먼저 관리 콘솔의 **DNS** 페이지를 열고, **HTTPS Certificates** 항목에서 **Enable HTTPS**를 고른다. 그다음 서버에서 serve를 켠다.

```bash
sudo tailscale serve --bg --https=443 localhost:8080
tailscale serve status
```

이제 주소는 다음과 같다. 접두 경로를 쓰지 않고 주소 전체를 게이트웨이로 넘기므로 KAIROS 쪽에서 바꿀 것은 없다.

| 용도 | 주소 |
|---|---|
| 뷰어 | `https://kairos.<tailnet이름>.ts.net/` |
| MCP (`/kairos:setup`, Codex `--url`) | `https://kairos.<tailnet이름>.ts.net/mcp` |

주소를 적을 때는 **`https://`를 반드시 붙인다.** 클라이언트는 스킴이 빠진 주소에 `http://`를 붙이기 때문이다.

serve를 끄려면 다음 중 하나를 실행한다.

```bash
sudo tailscale serve --https=443 localhost:8080 off   # 이 설정만 끈다
sudo tailscale serve reset                            # serve 설정 전체를 지운다
```

serve를 꺼도 7.3의 면제 해제는 그대로 두어도 된다. 토큰을 받은 클라이언트는 면제가 없어도 동작하기 때문이다.

---

## 8. 운용

**기기를 잃어버렸을 때.** 두 가지를 순서대로 한다.

1. 관리 콘솔 **Machines** 페이지에서 해당 기기의 메뉴를 열고 **Remove**를 고른 다음, 확인 창에서 **Remove machine**을 고른다. 이제 그 기기는 tailnet에 들어올 수 없다.
2. 잃어버린 기기의 브라우저 저장소에도 토큰이 남아 있으므로, 서버에서 토큰을 새로 발급한다. 이전 토큰은 즉시 무효가 된다. 남은 기기에는 새 토큰을 다시 넣는다.

   ```bash
   kairos --root ~/kairos-data token rotate
   ```

**서버를 공유하지 않는다.** Tailscale의 기기 공유 기능을 쓰면 공유받은 사람도 그 기기에 접속할 수 있게 된다. 게이트웨이는 여전히 토큰을 요구하지만, 3번에서 인터페이스 전체를 열었다면 SSH처럼 `tailscale0`에 열어 둔 다른 서비스에도 그 사람이 닿을 수 있다.

**잠시 끄기.** 서버에서 `sudo tailscale down`을 실행하면 tailnet에서 빠지고, `sudo tailscale up`을 실행하면 다시 들어온다. LAN 접속은 영향을 받지 않는다.

---

## 9. 문제 해결

| 증상 | 확인할 것 |
|---|---|
| `curl`이 시간 초과로 끝난다 | 서버에서 `sudo ufw status`로 `tailscale0` 규칙이 있는지(3번), 노트북의 `tailscale status`에 서버가 보이는지 |
| 이름을 찾지 못한다 | 전체 이름 `kairos.<tailnet이름>.ts.net`으로 시도한다. 관리 콘솔 **DNS** 페이지에서 MagicDNS가 켜져 있는지 확인한다 |
| 잘 되다가 서버만 목록에서 사라졌다 | 서버의 키가 만료됐다. 서버에서 `sudo tailscale up`으로 다시 로그인하고, 2번의 **Disable Key Expiry**를 확인한다 |
| 느리다 | `tailscale ping kairos`의 출력에 `via DERP`가 있는지, `tailscale netcheck`의 진단 결과 |
| 401 (CLI) | 그 셸에 `KAIROS_TOKEN`이 있는지, 서버에서 토큰을 새로 발급한 뒤 옛 값을 쓰고 있지 않은지 |
| 401 (MCP 툴만, 보관과 상태는 된다) | 토큰이 파일에만 있고 환경 변수 `KAIROS_TOKEN`에는 없다. Windows는 사용자 환경 변수에 넣고 PC 앱을 재실행한다(6번) |
| serve를 켠 뒤 서버의 MCP 툴이 401을 낸다 | 7.2를 건너뛰었다. 서버 셸의 `KAIROS_TOKEN`을 확인한다 |
| `/kairos:status`가 http 주소를 보인다 | 주소를 적을 때 `https://`를 빠뜨렸다. `/kairos:setup https://…/mcp`로 다시 적는다 |

---

## 출처

- [Install Tailscale on Linux](https://tailscale.com/docs/install/linux) · [Tailscale packages](https://pkgs.tailscale.com/stable/)
- [MagicDNS](https://tailscale.com/docs/features/magicdns) · [Machine names](https://tailscale.com/kb/1098/machine-names)
- [Key expiry](https://tailscale.com/docs/features/access-control/key-expiry)
- [Connection types](https://tailscale.com/kb/1257/connection-types) · [Tailscale CLI](https://tailscale.com/docs/reference/tailscale-cli)
- [tailscale serve](https://tailscale.com/kb/1242/tailscale-serve) · [Enabling HTTPS](https://tailscale.com/kb/1153/enabling-https)
- [ACLs](https://tailscale.com/kb/1018/acls) · [Sharing](https://tailscale.com/kb/1084/sharing) · [Remove a device](https://tailscale.com/docs/features/access-control/device-management/how-to/remove)
- [Use ufw to lock down an Ubuntu server](https://tailscale.com/kb/1077/secure-server-ubuntu)
- [Exit nodes](https://tailscale.com/docs/features/exit-nodes)
