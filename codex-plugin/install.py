#!/usr/bin/env python3
"""KAIROS ↔ Codex CLI 연결 설치기 (decisions.md §127).

Codex에는 Claude Code의 플러그인 같은 묶음 단위가 없다. 대신 확장 지점 셋이 각자의 자리에
있다 — MCP 서버는 `~/.codex/config.toml`의 `[mcp_servers.<이름>]`, 훅은 `~/.codex/hooks.json`,
스킬은 `~/.codex/skills/<이름>/SKILL.md`. 이 설치기가 그 셋과 클라이언트 스크립트를 한 번에
놓고, 되돌리는 길(`uninstall`)도 함께 둔다. 표준 라이브러리만 쓴다.

**멱등이다.** 두 번 돌려도 같은 상태가 되고, 이미 있는 KAIROS 항목은 새 값으로 바뀐다.
config.toml은 읽기(tomllib)만 표준에 있으므로 쓰기는 `[mcp_servers.kairos]` 구획을 문자열로
갈아 끼운다 — 다른 구획은 바이트 그대로 둔다.

**토큰은 값이 아니라 변수 이름으로 둔다.** `bearer_token_env_var = "KAIROS_TOKEN"`은 URL이
루프백이 아닐 때만 적는다 — 같은 호스트는 게이트웨이의 루프백 면제(A8)로 붙고, 변수가 없는
채로 적어 두면 Codex가 기동 때 그 서버를 실패로 표시할 수 있다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
DEFAULT_URL = "http://127.0.0.1:8080/mcp"
SKILLS = ("kairos", "kairos-status", "kairos-archive")
MARK = "kairos-client"                       # 훅 항목을 우리 것으로 알아보는 표식
# 머리줄 뒤의 주석(`[mcp_servers.kairos]   # …`)까지 삼킨다 — 우리가 쓰는 블록이 그 꼴이다
SECTION_RE = re.compile(r"^\[mcp_servers\.kairos(?:\.[^\]]*)?\][^\n]*\n(?:(?!^\[).*\n?)*", re.M)


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or "~/.codex").expanduser()


def is_loopback(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in ("127.0.0.1", "localhost", "::1")


def config_block(url: str) -> str:
    lines = ["[mcp_servers.kairos]              # KAIROS 지식저장고 — deploy/codex-plugin/install.py가 관리한다",
             f'url = "{url}"']
    if not is_loopback(url):
        lines.append('bearer_token_env_var = "KAIROS_TOKEN"   # 값이 아니라 변수 이름 — 셸 프로필에 둔다')
    lines.append('http_headers = { "X-KAIROS-Client" = "codex" }   # 인입 경로 표식 — 인증이 아니다')
    return "\n".join(lines) + "\n"


def merge_config(text: str, block: str) -> str:
    """`[mcp_servers.kairos]` 구획만 갈아 끼운다. 없으면 끝에 붙인다."""
    stripped = SECTION_RE.sub("", text)
    if stripped and not stripped.endswith("\n"):
        stripped += "\n"
    if stripped.strip():
        stripped = stripped.rstrip("\n") + "\n\n"
    return stripped + block


def strip_config(text: str) -> str:
    return SECTION_RE.sub("", text).rstrip("\n") + ("\n" if text.strip() else "")


def hook_entries(client: Path) -> dict[str, list]:
    tmpl = json.loads((HERE / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    out = {}
    for event, groups in tmpl.items():
        for g in groups:
            for h in g["hooks"]:
                h["command"] = h["command"].replace("{KAIROS_CLIENT}", str(client))
        out[event] = groups
    return out


def _ours(group: dict) -> bool:
    return any(MARK in str(h.get("command", "")) for h in group.get("hooks", []))


def merge_hooks(obj: dict, entries: dict[str, list]) -> dict:
    """우리 항목만 빼고 다시 넣는다 — 다른 훅은 순서까지 그대로다."""
    hooks = dict(obj.get("hooks") or {})
    for event, groups in entries.items():
        kept = [g for g in hooks.get(event, []) if not _ours(g)]
        hooks[event] = kept + groups
    return {**obj, "hooks": hooks}


def strip_hooks(obj: dict) -> dict:
    hooks = {}
    for event, groups in (obj.get("hooks") or {}).items():
        kept = [g for g in groups if not _ours(g)]
        if kept:
            hooks[event] = kept
    return {**obj, "hooks": hooks}


def install(home: Path, url: str, dry_run: bool) -> list[str]:
    done: list[str] = []
    client = home / "kairos" / "kairos-client"
    src = (HERE / "scripts" / "kairos-client").resolve()   # 심볼릭 링크는 여기서 풀린다

    def put(path: Path, content: str | bytes, what: str) -> None:
        done.append(f"{'(dry-run) ' if dry_run else ''}{what}: {path}")
        if dry_run:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

    put(client, src.read_bytes(), "클라이언트")
    if not dry_run:
        client.chmod(client.stat().st_mode | stat.S_IXUSR)
    for name in SKILLS:
        body = (HERE / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        put(home / "skills" / name / "SKILL.md", body.replace("{KAIROS_CLIENT}", str(client)), f"스킬 {name}")

    cfg = home / "config.toml"
    text = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
    put(cfg, merge_config(text, config_block(url)), "MCP 등록 [mcp_servers.kairos]")

    hooks_path = home / "hooks.json"
    try:
        obj = json.loads(hooks_path.read_text(encoding="utf-8")) if hooks_path.exists() else {}
    except ValueError:
        obj = {}
    put(hooks_path, json.dumps(merge_hooks(obj, hook_entries(client)), ensure_ascii=False, indent=2) + "\n",
        "훅 Stop·SessionEnd (KAIROS_AUTO_ARCHIVE 없이는 보내지 않는다)")
    return done


def uninstall(home: Path, dry_run: bool) -> list[str]:
    done: list[str] = []

    def rm(path: Path, what: str) -> None:
        if not path.exists():
            return
        done.append(f"{'(dry-run) ' if dry_run else ''}{what} 제거: {path}")
        if dry_run:
            return
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

    rm(home / "kairos", "클라이언트")
    for name in SKILLS:
        rm(home / "skills" / name, f"스킬 {name}")
    cfg = home / "config.toml"
    if cfg.exists():
        text = cfg.read_text(encoding="utf-8")
        if SECTION_RE.search(text):
            done.append(f"{'(dry-run) ' if dry_run else ''}MCP 등록 제거: {cfg}")
            if not dry_run:
                cfg.write_text(strip_config(text), encoding="utf-8")
    hooks_path = home / "hooks.json"
    if hooks_path.exists():
        try:
            obj = json.loads(hooks_path.read_text(encoding="utf-8"))
        except ValueError:
            obj = None
        if obj is not None:
            done.append(f"{'(dry-run) ' if dry_run else ''}훅 제거: {hooks_path}")
            if not dry_run:
                hooks_path.write_text(json.dumps(strip_hooks(obj), ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")
    return done


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="install.py", description=__doc__.split("\n")[0])
    parser.add_argument("action", choices=["install", "uninstall"])
    parser.add_argument("--url", default=os.environ.get("KAIROS_URL", DEFAULT_URL),
                        help=f"게이트웨이 MCP 주소 (기본 {DEFAULT_URL}, KAIROS_URL 환경 변수를 따른다)")
    parser.add_argument("--codex-home", type=Path, default=None, help="기본 ~/.codex (CODEX_HOME)")
    parser.add_argument("--dry-run", action="store_true", help="무엇을 할지만 보인다")
    args = parser.parse_args(argv)
    home = args.codex_home or codex_home()
    done = install(home, args.url, args.dry_run) if args.action == "install" else uninstall(home, args.dry_run)
    print("\n".join(done) if done else "할 일 없음")
    if args.action == "install" and not args.dry_run:
        print("\nCodex를 다시 시작하면 적용된다. 확인은 Codex 안에서 `$kairos-status`.")
        if not is_loopback(args.url):
            print("LAN 주소이므로 셸 프로필에 `export KAIROS_TOKEN=<토큰>`이 있어야 한다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
