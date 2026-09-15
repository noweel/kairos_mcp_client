@echo off
rem kairos-client 진입점 (Windows) — 옆의 kairos-client.py를 돌릴 파이썬을 고른다.
rem
rem Git Bash가 없는 Windows에서 Claude Code는 슬래시 명령을 PowerShell로 돌린다. 그때
rem sh 진입점(kairos-client)은 셔뱅이 읽히지 않아 열리지 않으므로, 같은 이름의 이 배치본이
rem 대신 열린다 — 명령줄이 `cd "<scripts>"; ./kairos-client ...`라 확장자는 PATHEXT가 고른다.
rem
rem 훅은 이 파일을 거치지 않는다: hooks.json이 exec 형식으로 파이썬을 직접 부른다(decisions.md 190).
py -3 -c "import sys" >nul 2>&1 && goto py3launcher
python -c "import sys" >nul 2>&1 && goto python
python3 -c "import sys" >nul 2>&1 && goto python3
echo kairos-client: no working Python found (tried: py -3, python, python3) 1>&2
exit /b 1
:py3launcher
py -3 "%~dp0kairos-client.py" %*
exit /b %errorlevel%
:python
python "%~dp0kairos-client.py" %*
exit /b %errorlevel%
:python3
python3 "%~dp0kairos-client.py" %*
exit /b %errorlevel%
