"""한국 IP 에서만 되는 수집기를 **이 PC 에서** 돌려 push 한다 (2026-09-09).

왜 이게 필요한가 — 러너 진단(diag_probe.py · diag/net_probe.json)으로 확정된 사실:
  GitHub 러너(Microsoft AS8075 · 미국)에서는 아이템매니아가 TCP 연결 자체를 안 받는다.
  DNS 는 되고 다른 한국 사이트는 다 열리는데 아이템매니아만 클라우드 대역을 드롭한다.
  헤더·재시도로는 절대 안 풀린다. 한국 가정용 IP(이 PC)에서는 0.1초에 200 이다.
  올리브영은 러너에서도 대체로 되지만(간헐 403) 여기서는 100% 라 같이 돌린다.

어떻게 push 하나 — CLAUDE.md 의 '합치지 말고 다시 주입' 규칙 그대로.
  수집기는 index.html 을 읽어 자기 블록만 바꿔 넣으므로, **원격 최신을 받은 뒤 수집하면 그게 곧 재주입**이다.
  push 가 밀리면(봇이 그 사이 커밋) 원격 최신을 다시 받고 재수집한다 — 수집이 4초라 재주입보다 단순하다.
  ⚠ 안전장치: 작업트리에 미커밋 변경이 있거나 push 안 된 로컬 커밋이 있으면 손대지 않고 끝낸다.
    (사람이 이 PC 에서 작업 중일 수 있다. `reset --hard` 는 그 둘이 없을 때만 실행된다.)

작업 스케줄러: kr_collect.bat 를 하루 1~2회(예: 08:30 · 13:30). 놓친 실행 보완 옵션을 켤 것.
  PC 가 꺼져 있던 날은 그날 데이터가 없다 — 러너 쪽 시도(events/refresh)는 그대로 두므로
  아이템매니아가 대역을 열어 주는 날엔 그쪽이 저절로 이어받는다.
"""
import datetime, os, subprocess, sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
KST = datetime.timezone(datetime.timedelta(hours=9))
COLLECTORS = [("게임머니", "fetch_gamemoney.py"), ("올리브영", "fetch_beauty.py")]


def git(*a):
    return subprocess.run(["git", *a], capture_output=True, text=True, encoding="utf-8", errors="replace")


def main():
    now = datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    print(f"===== kr_collect {now} KST")
    if git("status", "--porcelain", "--untracked-files=no").stdout.strip():
        print("작업트리에 미커밋 변경이 있어 건드리지 않는다 — 중단"); return 2
    f = git("fetch", "origin", "main")
    if f.returncode != 0:
        print("fetch 실패:", f.stderr.strip()[:200]); return 1
    ahead = git("log", "--format=%s", "origin/main..HEAD").stdout.strip()
    if ahead:
        print("push 안 된 로컬 커밋이 있어 중단:", ahead.splitlines()[0][:80]); return 2

    for attempt in (1, 2, 3):
        git("reset", "--hard", "origin/main")            # 원격 최신 = 재주입의 바탕
        for name, script in COLLECTORS:
            subprocess.run([sys.executable, "runstep.py", name, script],
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        git("add", "public/index.html", "health.json")
        c = git("commit", "-m", f"한국 IP 수집(게임머니·올리브영) {now} KST")
        if "nothing to commit" in (c.stdout + c.stderr):
            print("변동 없음 — push 생략"); return 0
        p = git("push", "origin", "main")
        if p.returncode == 0:
            print("push 완료"); return 0
        print(f"push 밀림 — 원격 최신 위에서 재수집 ({attempt}/3)")
        git("fetch", "origin", "main")
    print("push 3회 실패"); return 1


if __name__ == "__main__":
    sys.exit(main())
