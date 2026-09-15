#!/usr/bin/env bash
# KAIROS Telegram 봇 유닛 등록 (README §8).
#
# 토큰과 허용 사용자는 **사람이 미리 넣어 둔다** — 이 스크립트는 그것을 만들지도, 읽어서
# 찍지도 않는다. 하는 일은 셋뿐이다: 전제 확인, 유닛 복사, 기동과 확인.
set -euo pipefail

CONF="${XDG_CONFIG_HOME:-$HOME/.config}/kairos"
UNITS="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/systemd/kairos-tg.service"

fail() { echo "✗ $1" >&2; exit 1; }

# --- 1. 전제 — 없는 채로 띄우면 유닛이 조용히 종료하고 원인이 로그에만 남는다
[ -f "$SRC" ] || fail "유닛 파일이 없다: $SRC (deploy 저장소를 받았는지 본다)"
[ -f "$CONF/kairos.env" ] || fail "$CONF/kairos.env 가 없다"
grep -q '^KAIROS_TG_TOKEN=.' "$CONF/kairos.env" \
  || fail "kairos.env 에 KAIROS_TG_TOKEN 이 비어 있다 (BotFather 토큰을 넣는다)"
grep -q '^\[telegram\]' "$CONF/config.toml" \
  || fail "config.toml 에 [telegram] 절이 없다"
grep -A5 '^\[telegram\]' "$CONF/config.toml" | grep -q '^allowed_user_id *= *[0-9]' \
  || fail "config.toml 의 [telegram].allowed_user_id 가 비었거나 숫자가 아니다"

# 토큰은 시크릿이다 — 값은 찍지 않고 권한만 본다
perm="$(stat -c '%a' "$CONF/kairos.env")"
[ "$perm" = "600" ] || echo "⚠ kairos.env 권한이 $perm 다 — 0600 을 권한다 (chmod 600)"
echo "✓ 전제 확인: 토큰 있음 · allowed_user_id 있음"

# --- 2. 유닛 등록
mkdir -p "$UNITS"
cp "$SRC" "$UNITS/"
systemctl --user daemon-reload
echo "✓ 유닛 복사: $UNITS/kairos-tg.service"

# --- 3. 기동 — 부팅 때도 뜨게 enable 을 함께 건다
systemctl --user enable --now kairos-tg
sleep 3

state="$(systemctl --user is-active kairos-tg || true)"
if [ "$state" != "active" ]; then
  echo "✗ 기동 실패 (상태: $state). 최근 로그:" >&2
  journalctl --user -u kairos-tg -n 20 --no-pager >&2
  exit 1
fi
echo "✓ kairos-tg 기동 (active)"
journalctl --user -u kairos-tg -n 10 --no-pager | sed 's/[0-9]\{8,\}:[A-Za-z0-9_-]\{20,\}/(토큰 가림)/g'
echo
echo "다음: 봇에게 아무 글이나 보내면 접수 회신이 온다. 회신이 없으면"
echo "  journalctl --user -u kairos-tg -f     # 봇이 받았는지"
echo "  kairos --root \$KAIROS_ROOT status     # 큐에 들어왔는지"
