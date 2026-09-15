---
description: KAIROS 연결 상태 — 게이트웨이·토큰·자동 보관·이 프로젝트의 대화록
allowed-tools: Bash(cd:*), Bash(./kairos-client:*), PowerShell(cd:*), PowerShell(./kairos-client:*)
---

아래는 방금 실행한 `kairos-client status`의 출력이다.

```
!`cd "${CLAUDE_PLUGIN_ROOT}/scripts"; ./kairos-client status --project "${CLAUDE_PROJECT_DIR}"`
```

이 출력을 그대로 보여 주고, **실패 줄이 있으면 그 줄이 말하는 다음 조치**(토큰 설정, 서버 기동)를 한 문장으로 덧붙인다. 출력에 없는 것을 추측해 말하지 않는다.
