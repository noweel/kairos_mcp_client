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

**Windows에서는 훅 인터프리터도 본다.** 플러그인의 훅은 exec 형식이라 PATH에서 `python3`를
찾는데, PEP 394가 보증하는 그 이름은 Windows를 제외한다 — python.org 설치본은 `python.exe`와
`py.exe`만 놓는다. 그래서 `python3`가 없고 다른 이름이 있으면, 물어본 뒤 작은 심을 만들고 그
디렉터리를 **사용자** PATH에 더한다. 되돌리는 것은 `install.py remove-shim`이다.

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
CLIENT = HERE / "claude-plugin" / "kairos" / "scripts" / "kairos-client"
CODEX_INSTALLER = HERE / "codex-plugin" / "install.py"
MARKETPLACE = HERE / "claude-plugin"          # 이 리포 자체가 마켓플레이스다
DEFAULT_URL = "http://127.0.0.1:8080/mcp"


# --- Windows 훅 인터프리터 심 (decisions.md §189) --------------------------------------
#
# 플러그인의 `hooks.json`은 정적으로 실려 나가므로 기계마다 다른 인터프리터 경로를 담을 수
# 없고, exec 형식은 PATH의 이름을 쓴다. PEP 394가 보증하는 이름은 `python3`뿐인데 그 PEP는
# **Windows를 명시적으로 제외한다** — python.org 설치본은 `python.exe`와 `py.exe`만 놓는다.
# 그래서 Windows에서만, `python3`가 없고 `python`이나 `py`가 있을 때 그 이름을 만들어 준다.
SHIM_NAME = "python3.cmd"


def shim_dir() -> Path:
    """심을 둘 자리. 우리가 만든 디렉터리라 지울 때 통째로 지워도 남의 것이 섞이지 않는다."""
    base = os.environ.get("LOCALAPPDATA") or "~\\AppData\\Local"
    return Path(base).expanduser() / "KAIROS" / "bin"


def find_interpreter() -> tuple[str, str, list[str]] | None:
    """`(이름, 실행 파일, 앞에 붙일 인자)` — 이 기계에서 파이썬을 부를 방법.

    `python3`가 이미 있으면 그것이고(심이 필요 없다), 없으면 `python`, 그다음 `py -3`이다.
    셋 다 없으면 None — 파이썬 자체가 없는 기계다.
    """
    for name, prefix in (("python3", []), ("python", []), ("py", ["-3"])):
        exe = shutil.which(name)
        if exe:
            return name, exe, prefix
    return None


def shim_text(exe: str, prefix: list[str]) -> str:
    """`python3`로 불리면 실제 인터프리터에 그대로 넘기는 배치 파일.

    경로를 절대로 적는 이유는 심 자신이 PATH에 기대지 않게 하려는 것이다. 줄 끝은 CRLF다 —
    cmd.exe는 LF만 있는 배치 파일에서 마지막 줄을 잘못 읽는 일이 있다.
    """
    args = (" " + " ".join(prefix)) if prefix else ""
    return f'@echo off\r\n"{exe}"{args} %*\r\n'


def _path_key(entry: str) -> str:
    """Windows PATH 항목의 동일성 — 대소문자를 가리지 않고 `\\`와 `/`가 같으며 끝 구분자는 무시한다.

    `os.path.normcase`에 맡기지 않는다. 그것은 **도는 기계의** 규칙을 쓰는데(리눅스에서는
    아무것도 하지 않는다), 여기서 다루는 값은 언제나 Windows의 PATH 문자열이다. 시험도
    리눅스에서 도므로 규칙을 여기 적어 두어야 둘이 같은 것을 본다.
    """
    return entry.strip().strip('"').replace("\\", "/").rstrip("/").lower()


def path_with(current: str, directory: str) -> str | None:
    """PATH 문자열에 디렉터리를 더한 결과. **이미 있으면 None**(두 번 넣지 않는다)."""
    parts = [p for p in current.split(";") if p.strip()]
    if any(_path_key(p) == _path_key(directory) for p in parts):
        return None
    return ";".join([*parts, directory])


def path_without(current: str, directory: str) -> str | None:
    """PATH 문자열에서 디렉터리를 뺀 결과. 없으면 None — 없는데 쓰지 않는다."""
    parts = [p for p in current.split(";") if p.strip()]
    kept = [p for p in parts if _path_key(p) != _path_key(directory)]
    return ";".join(kept) if len(kept) != len(parts) else None


def _user_path(write: str | None = None) -> str:
    """사용자 PATH를 레지스트리에서 읽고, 주면 쓴다. Windows 전용.

    **`%PATH%`를 되쓰지 않는다** — 그 값은 시스템 것과 합쳐진 결과라 그대로 사용자
    스코프에 쓰면 시스템 항목이 복사된다. **`setx`도 쓰지 않는다** — 값이 1024자를
    넘으면 잘라 버리는 것으로 알려져 있어 남의 PATH를 망가뜨릴 수 있다.
    """
    import winreg

    access = winreg.KEY_READ | (winreg.KEY_WRITE if write is not None else 0)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, access) as key:
        try:
            current, kind = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current, kind = "", winreg.REG_EXPAND_SZ
        if write is not None:
            winreg.SetValueEx(key, "Path", 0, kind or winreg.REG_EXPAND_SZ, write)
    return str(current)


def _broadcast_env() -> None:
    """새로 뜨는 프로세스가 바뀐 PATH를 보게 알린다. 실패해도 무해하다(다시 로그인하면 된다)."""
    try:
        import ctypes

        ctypes.windll.user32.SendMessageTimeoutW(
            0xFFFF, 0x001A, 0, ctypes.c_wchar_p("Environment"), 0x0002, 5000, None)
    except Exception:
        pass


def install_shim(assume: bool, dry_run: bool) -> None:
    """Windows에서 `python3`라는 이름을 만들어 준다 — 물어보고 한다."""
    if os.name != "nt":
        return
    found = find_interpreter()
    if found is None:
        out("  파이썬을 찾지 못했다 — `winget install Python.Python.3.12` 뒤에 다시 돌린다.")
        return
    name, exe, prefix = found
    if name == "python3":
        out(f"  python3 이 이미 있다: {exe}")
        return
    target = shim_dir()
    out(f"  python3 이 PATH에 없다. {name} 을 찾았다: {exe}")
    out(f"  훅이 돌게 하려면 {target / SHIM_NAME} 를 만들고 그 디렉터리를 사용자 PATH에 더한다.")
    if not ask_yes("만들까? (사용자 PATH를 고친다)", True, assume):
        out("  건너뜀 — MCP 조회는 되고 훅만 돌지 않는다.")
        return
    if dry_run:
        out(f"  (dry-run) {target / SHIM_NAME} 작성 · 사용자 PATH에 {target} 추가")
        return
    target.mkdir(parents=True, exist_ok=True)
    (target / SHIM_NAME).write_text(shim_text(exe, prefix), encoding="utf-8", newline="")
    out(f"  만듦: {target / SHIM_NAME}")
    updated = path_with(_user_path(), str(target))
    if updated is None:
        out("  사용자 PATH에 이미 있다")
    else:
        _user_path(updated)
        _broadcast_env()
        out(f"  사용자 PATH에 더함: {target}")
    out("  새로 뜨는 프로세스만 이것을 본다 — Claude Code를 다시 시작한다.")


def remove_shim(dry_run: bool) -> None:
    """심과 PATH 항목을 되돌린다. 우리가 만든 디렉터리만 지운다."""
    if os.name != "nt":
        out("  Windows 전용이라 할 일이 없다.")
        return
    target = shim_dir()
    shim = target / SHIM_NAME
    if shim.exists():
        out(f"  {'(dry-run) ' if dry_run else ''}지움: {shim}")
        if not dry_run:
            shim.unlink()
            with suppress(OSError):
                target.rmdir()                     # 비었을 때만 지워진다
    updated = path_without(_user_path(), str(target))
    if updated is None:
        out("  사용자 PATH에 없다")
    elif dry_run:
        out(f"  (dry-run) 사용자 PATH에서 뺌: {target}")
    else:
        _user_path(updated)
        _broadcast_env()
        out(f"  사용자 PATH에서 뺌: {target}")


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
        code = subprocess.call([cli, *s])
        if code != 0:
            out(f"  ↳ 실패(종료 {code}) — 이미 등록돼 있으면 무해하다. 위 명령을 직접 확인한다.")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):      # Windows 콘솔의 cp949가 `—`에 죽는다
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="install.py", description=__doc__.split("\n")[0])
    ap.add_argument("action", nargs="?", default="install", choices=["install", "remove-shim"],
                    help="remove-shim: Windows의 python3 심과 PATH 항목을 되돌린다 "
                         "(플러그인 제거는 `claude plugin uninstall kairos@kairos`)")
    ap.add_argument("--url", help="게이트웨이 MCP 주소. 없으면 묻고, 비우면 건너뛴다")
    ap.add_argument("--allow-reads", action="store_true",
                    help="조회 툴 8종을 permissions.allow에 더한다 (쓰기 3종은 넣지 않는다)")
    ap.add_argument("--claude", action="store_true", help="Claude Code만")
    ap.add_argument("--codex", action="store_true", help="Codex CLI만")
    ap.add_argument("--yes", action="store_true", help="묻지 않고 기본값을 쓴다")
    ap.add_argument("--dry-run", action="store_true", help="무엇을 할지만 보인다")
    args = ap.parse_args(argv)

    if args.action == "remove-shim":
        out("Windows python3 심 되돌리기" + (" (dry-run)" if args.dry_run else ""))
        remove_shim(args.dry_run)
        return 0

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

    # --- 2. 훅 인터프리터 (Windows에서만 할 일이 있다) --------------------------------
    if os.name == "nt":
        out("2) 훅 인터프리터")
        install_shim(args.yes, args.dry_run)
        out("")

    # --- 3. Claude Code -------------------------------------------------------------
    if do_claude:
        out("3) Claude Code 플러그인 (CLI·PC 앱 공통)")
        if ask_yes("마켓플레이스를 등록하고 플러그인을 설치할까?", True, args.yes):
            install_plugin(args.dry_run)
        else:
            out("  건너뜀.")
        out("")

    # --- 4. Codex CLI ---------------------------------------------------------------
    if do_codex:
        out("4) Codex CLI")
        codex = [sys.executable, str(CODEX_INSTALLER), "install"]
        if args.url:
            codex += ["--url", args.url]
        if args.dry_run:
            codex += ["--dry-run"]
        subprocess.call(codex)
        out("")

    # --- 4. 확인 --------------------------------------------------------------------
    out("5) 확인")
    run_client(["status", "--url", effective_url()])   # 방금 적은 주소로 본다
    out("")
    out("Claude Code(와 Codex)를 다시 시작하면 적용된다. 확인은 /kairos:status 또는 $kairos-status.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
