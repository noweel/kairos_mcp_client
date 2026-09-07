---
name: kairos-status
description: KAIROS 연결 상태를 본다 — 게이트웨이·토큰·자동 보관·이 프로젝트의 대화록과 보낸 턴 수. 사용자가 "kairos 상태", "저장고 연결됐어?"를 물을 때 쓴다.
---

# KAIROS 연결 상태

다음 명령을 그대로 실행하고 출력을 그대로 보여 준다.

```bash
python3 "{KAIROS_CLIENT}" --client codex status --project "$PWD"
```

출력에 실패 줄이 있으면 그 줄이 말하는 다음 조치(토큰 설정, 서버 기동)를 한 문장으로 덧붙인다. 출력에 없는 것을 추측해 말하지 않는다.
