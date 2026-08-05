# -*- coding: utf-8 -*-
"""수집기 한 개를 돌리고, 성패를 health.json 에 남긴다.

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

쓰는 법
    python runstep.py 영화 fetch_movie.py
    python runstep.py 시세 refresh_live.py --deep

  첫 인자가 알림에 뜰 이름, 나머지가 실제로 돌릴 명령이다.
  종료 코드는 항상 0 이다 — 워크플로를 멈추지 않는 것이 이 파일의 목적이다.
"""
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from collector_health import note_health


def main():
    if len(sys.argv) < 3:
        print("사용법: python runstep.py <이름> <스크립트.py> [인자...]")
        return 0

    label, cmd = sys.argv[1], sys.argv[2:]
    r = subprocess.run([sys.executable] + cmd)

    if r.returncode == 0:
        # 정상 복귀도 기록해야 한다. 안 지우면 한 번 실패한 소스가
        # 영영 '고장'으로 남아 watchdog 이 계속 같은 걸 쏜다.
        note_health(label, None)
        return 0

    # 종료 코드만으로는 '왜' 를 알 수 없지만, 최소한 '무엇이 언제부터'는 남는다.
    # 자세한 원인은 수집기 자신이 note_health 로 따로 적는다(차단·캡차 등).
    msg = f"{' '.join(cmd)} 실패 (종료코드 {r.returncode})"
    print(f"  ! {label}: {msg} — 기록만 남기고 계속 진행합니다")
    note_health(label, msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
