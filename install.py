#!/usr/bin/env python3
"""KAIROS 클라이언트 설치기 — 주소를 한 번 묻고 붙인다 (decisions.md §189).

Claude Code는 플러그인 한 번으로 붙지만(`claude plugin install`) 그 과정에 **주소를 물어볼
자리가 없다**. 플러그인의 `.mcp.json`은 `${KAIROS_URL}`을 참조만 하므로 값은 밖에서 와야
하는데, 셸 프로필의 `export`는 **PC 앱이 읽지 못한다** — 앱은 로그인 셸을 거치지 않는다.
그래서 이 설치기가 묻고, Claude Code의 설정 파일(`~/.claude/settings.json`의 `env`)에 적는다.
CLI와 PC 앱이 같이 읽고 Windows·리눅스가 같은 경로 규칙을 쓰는 유일한 자리다.

**묻는 것은 주소 하나뿐이고 건너뛸 수 있다.** 같은 기계에서 돌리면 적을 것이 없다 —
기본값 `http://127.0.0.1:8080/mcp`에 게이트웨이의 루프백 면제(A8)로 붙는다.

**토큰은 묻지 않는다.** 값을 받아 적으면 그 값이 이 프로세스와 로그를 지나간다. 있는지만
보고 없으면 무엇을 하라고 말한다 — 넣는 것은 사람이 한다.

**훅 인터프리터는 건드리지 않는다.** 플러그인의 `scripts/kairos-client`가 sh 진입점이라
`python3` · `python` · `py -3` 중 **실제로 실행되는 것**을 스스로 고른다(§189). 설치기는 그것이
이 기계에서 되는지만 보고(`status`의 「파이썬」 줄) 안 되면 무엇을 할지 말한다.

표준 라이브러리만 쓴다. `--dry-run`이면 아무것도 쓰지 않는다.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from contextlib import suppress
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLIENT = HERE / "claude-plugin" / "kairos" / "scripts" / "kairos-client.py"
CODEX_INSTALLER = HERE / "codex-plugin" / "install.py"
MARKETPLACE = HERE / "claude-plugin"          # 이 리포 자체가 마켓플레이스다
DEFAULT_URL = "http://127.0.0.1:8080/mcp"


def out(*parts: str) -> None:
    print(*parts, flush=True)


def ask_yes(question: str, default: bool, assume: bool) -> bool:
    """예/아니오. 터미널이 아니거나 `--yes`면 기본값을 그대로 쓴다."""
    if assume or not sys.stdin.isatty():
        return default
    hint = "Y/n" if default else "y/N"
    try:
        answer = input(f"  {question} [{hint}] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return default if not answer else answer.startswith(("y", "예", "ㅇ"))


def run_client(args: list[str]) -> int:
    """클라이언트 스크립트를 **이 인터프리터로** 부른다 — Windows에 `python3`가 없어도 된다."""
    return subprocess.call([sys.executable, str(CLIENT), *args])


def effective_url() -> str:
    """지금 쓰게 될 주소 — 설정 파일의 `env.KAIROS_URL`이 먼저다(방금 적었을 수 있다)."""
    import json

    path = Path(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude").expanduser() / "settings.json"
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        found = (obj.get("env") or {}).get("KAIROS_URL")
    except (OSError, ValueError, AttributeError):
        found = None
    return found or os.environ.get("KAIROS_URL") or DEFAULT_URL


def claude_cli() -> str | None:
    """`claude` 실행 파일. Windows에서는 `claude.cmd`도 여기서 찾힌다(PATHEXT)."""
    return shutil.which("claude")


def install_plugin(dry_run: bool) -> None:
    """마켓플레이스 등록 + 플러그인 설치. CLI가 없으면 칠 명령을 보인다.

    **경로로 등록한다** — 이 체크아웃이 이미 있으니 GitHub를 한 번 더 거칠 이유가 없고,
    고친 것이 바로 반영된다. GitHub에서 받고 싶으면 안내에 적힌 쪽을 쓴다.
    """
    cli = claude_cli()
    steps = [["plugin", "marketplace", "add", str(MARKETPLACE)],
             ["plugin", "install", "kairos@kairos"]]
    if cli is None:
        out("  claude 명령을 찾지 못했다 — Claude Code 안에서 또는 직접 다음을 친다:")
        for s in steps:
            out("    claude " + " ".join(s))
        return
    for s in steps:
        shown = "claude " + " ".join(s)
        if dry_run:
            out(f"  (dry-run) {shown}")
            continue
        out(f"  {shown}")
        # **Windows에서는 셸을 거친다.** `claude`는 npm이 놓은 `claude.cmd`인데, 배치 파일은
        # OS가 시스템 셸로 띄우면서 인자를 셸 규칙으로 다시 쪼갠다. `shell=False`면 파이썬이
        # 따옴표를 붙여 주지 않으므로 `C:\Users\John Doe\…` 같은 공백 있는 경로가 갈린다.
        # `shell=True`면 파이썬이 `list2cmdline`으로 감싼다(파이썬 문서의 권고).
        code = subprocess.call([cli, *s], shell=(os.name == "nt"))
        if code != 0:
            out(f"  ↳ 실패(종료 {code}) — 이미 등록돼 있으면 무해하다. 위 명령을 직접 확인한다.")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):      # Windows 콘솔의 cp949가 `—`에 죽는다
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="install.py", description=__doc__.split("\n")[0])
    ap.add_argument("--url", help="게이트웨이 MCP 주소. 없으면 묻고, 비우면 건너뛴다")
    ap.add_argument("--allow-reads", action="store_true",
                    help="조회 툴 8종을 permissions.allow에 더한다 (쓰기 3종은 넣지 않는다)")
    ap.add_argument("--claude", action="store_true", help="Claude Code만")
    ap.add_argument("--codex", action="store_true", help="Codex CLI만")
    ap.add_argument("--yes", action="store_true", help="묻지 않고 기본값을 쓴다")
    ap.add_argument("--dry-run", action="store_true", help="무엇을 할지만 보인다")
    args = ap.parse_args(argv)

    both = not (args.claude or args.codex)
    do_claude = args.claude or both
    do_codex = args.codex
    if both:
        # **Codex는 있을 때만 건드린다.** 없는 기계에 `~/.codex`를 만들어 두면 그 사람이
        # 쓰지도 않는 설정이 생긴다. `--codex`로 강제할 수 있다.
        codex_home = Path(os.environ.get("CODEX_HOME") or "~/.codex").expanduser()
        do_codex = codex_home.is_dir()
        if not do_codex:
            out(f"Codex는 건너뛴다 — {codex_home}가 없다 (`--codex`로 강제할 수 있다).")

    out("KAIROS 클라이언트 설치" + (" (dry-run)" if args.dry_run else ""))
    out("")

    # --- 1. 주소 — 묻고, 건너뛸 수 있다 ---------------------------------------------
    out("1) 게이트웨이 주소")
    setup = ["setup"]
    if args.url:
        setup += ["--set-url", args.url]
    if args.allow_reads:
        setup += ["--allow-reads"]
    if args.dry_run:
        setup += ["--dry-run"]
    if not args.url and not args.allow_reads and not sys.stdin.isatty():
        out("  터미널이 아니어서 묻지 않는다 — 지금 값을 그대로 쓴다.")
    if run_client(setup) != 0:
        return 1                                 # 설정 파일이 망가졌다 — 이유는 그쪽이 찍었다
    out("")

    # --- 2. Claude Code -------------------------------------------------------------
    if do_claude:
        out("2) Claude Code 플러그인 (CLI·PC 앱 공통)")
        if ask_yes("마켓플레이스를 등록하고 플러그인을 설치할까?", True, args.yes):
            install_plugin(args.dry_run)
        else:
            out("  건너뜀.")
        out("")

    # --- 4. Codex CLI ---------------------------------------------------------------
    if do_codex:
        out("3) Codex CLI")
        codex = [sys.executable, str(CODEX_INSTALLER), "install"]
        if args.url:
            codex += ["--url", args.url]
        if args.dry_run:
            codex += ["--dry-run"]
        subprocess.call(codex)
        out("")

    # --- 4. 확인 --------------------------------------------------------------------
    out("4) 확인")
    run_client(["status", "--url", effective_url()])   # 방금 적은 주소로 본다
    out("")
    out("Claude Code(와 Codex)를 다시 시작하면 적용된다. 확인은 /kairos:status 또는 $kairos-status.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
