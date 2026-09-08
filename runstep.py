# -*- coding: utf-8 -*-
"""수집기 한 개를 돌리고, 성패와 **실패 사유**를 health.json 에 남긴다.

왜 필요한가
  워크플로가 전부 이렇게 생겨 있었다:

      python fetch_movie.py || echo "영화 수집 건너뜀"

  `|| echo` 는 실패를 삼킨다. 스텝은 초록불이고 잡도 초록불이라, 화면에서는
  Actions 실패율이 0% 로 보인다. 실제로는 2026-08-05 로그를 뒤져 보니
  예매율 수집이 timeout 으로 조용히 넘어가고 있었다. 데이터는 옛날 값에
  멈춰 있는데 아무도 모르는 상태가 며칠씩 간다.

  그렇다고 `|| echo` 를 떼면 수집기 하나가 죽을 때 워크플로 전체가 멈춘다.
  아침 레터가 그것 때문에 안 나간 전례가 있다(events.yml 주석 참고).

  그래서 '실패해도 계속 가되, 실패했다는 사실은 남긴다'로 바꾼다.
  watchdog.py 가 health.json 을 읽어 하루 한 번 요약으로 알린다.

### 2026-09-08 — '무엇이' 는 남았는데 '왜' 가 사라지고 있었다

  옛 판은 실패하면 무조건 `note_health(label, "… 실패 (종료코드 1)")` 를 썼다.
  그런데 수집기들은 죽기 직전에 **자기 사유를 같은 키로 이미 적어 둔다**
  (`note_health("게임머니", "전부 실패: 봇 게이트")` → 곧바로 `sys.exit(1)`).
  같은 키라 runstep 의 일반 메시지가 그걸 **덮어썼다.** 남는 건 종료코드뿐이고,
  Actions 로그를 열어 보지 않는 한 원인을 영영 알 수 없었다.

  실제 피해: `GAMEMONEY`(아이템매니아)가 도입일부터 **엿새 내리 Actions 에서 실패**했는데,
  기록에는 "종료코드 1" 뿐이라 아무도 원인을 좁히지 못했다(로컬에서는 4초 만에 성공).

  지금은 이렇게 한다.
    ① 자식의 출력을 **잡아 두되 그대로 다시 찍는다**(Actions 로그는 예전과 똑같이 보인다).
    ② 수집기가 이번 실행 중에 자기 사유를 적었으면 **그걸 살린다** — 종료코드만 덧붙인다.
    ③ 안 적었으면 **stderr 마지막 줄**(대개 예외 한 줄)을 사유로 쓴다.

쓰는 법
    python runstep.py 영화 fetch_movie.py
    python runstep.py 시세 refresh_live.py --deep

  첫 인자가 알림에 뜰 이름, 나머지가 실제로 돌릴 명령이다.
  종료 코드는 항상 0 이다 — 워크플로를 멈추지 않는 것이 이 파일의 목적이다.
"""
import json
import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from collector_health import note_health, HEALTH


def _note_of(label):
    """health.json 에 이 라벨로 적힌 기록(있으면). 수집기가 스스로 남긴 사유를 읽으려는 것."""
    try:
        d = json.load(open(HEALTH, encoding="utf-8"))
        v = d.get(label)
        return v if isinstance(v, dict) else None
    except Exception:
        return None


def _tail(text, n=3, cap=150):
    """마지막 의미 있는 줄 n 개 — 파이썬 예외는 맨 끝 줄이 사유다."""
    lines = [x.strip() for x in (text or "").splitlines() if x.strip()]
    return " / ".join(lines[-n:])[:cap]


def main():
    if len(sys.argv) < 3:
        print("사용법: python runstep.py <이름> <스크립트.py> [인자...]")
        return 0

    label, cmd = sys.argv[1], sys.argv[2:]
    before = _note_of(label)

    # 출력을 잡되 그대로 다시 찍는다 — Actions 로그는 예전과 같아야 한다.
    # ⚠ capture 라 자식이 끝난 뒤에 한꺼번에 찍힌다. 실시간 진행이 필요한 단계는
    #   runstep 을 쓰지 말고 직접 부를 것(지금은 전부 몇 분 안쪽이라 문제없다).
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")     # 러너 기본 인코딩에서 한글 print 가 죽는 일이 있다
    r = subprocess.run([sys.executable] + cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    if r.stdout:
        sys.stdout.write(r.stdout)
    if r.stderr:
        sys.stderr.write(r.stderr)

    if r.returncode == 0:
        # 정상 복귀도 기록해야 한다. 안 지우면 한 번 실패한 소스가
        # 영영 '고장'으로 남아 watchdog 이 계속 같은 걸 쏜다.
        # 단, 수집기가 이번에 스스로 경고를 남겼으면(부분 차단 등) 그건 지우지 않는다.
        after = _note_of(label)
        if not after or (before and after == before):
            note_health(label, None)
        return 0

    # 실패 — '왜' 를 최대한 살린다.
    after = _note_of(label)
    own = after["msg"] if (after and after != before) else None      # 이번 실행 중 수집기가 적은 사유
    why = own or _tail(r.stderr) or _tail(r.stdout) or "출력 없음"
    msg = f"{why} (종료코드 {r.returncode})"
    print(f"  ! {label}: {msg} — 기록만 남기고 계속 진행합니다")
    note_health(label, msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
