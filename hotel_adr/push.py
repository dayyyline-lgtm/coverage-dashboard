# -*- coding: utf-8 -*-
"""hotel_adr/build.py 가 바꾼 파일만 커밋해 올린다 (아침 크롬 수집 세션에서 부른다 · 2026-10-29).

  python3 hotel_adr/push.py            # 배포 생략 표시 — 봇의 다음 배포(평일 장중 매시)가 같이 싣는다
  python3 hotel_adr/push.py --deploy   # 지금 바로 배포

- 잡는 파일: hotel_adr/data/ · public/index.html (pathspec 커밋 — 인덱스에 남의 작업이 올라와 있어도 안 휩쓸린다)
- 선행 판매가는 급한 숫자가 아니라 기본은 배포 생략(Cloudflare 빌드 월 500건 한도).
- push 가 거절되면 합치지 않는다(루트 CLAUDE.md 'index.html 에 쓰는 법'): 내 데이터 파일을 떼어 두고 → 원격 최신으로 맞춘 뒤 →
  데이터 파일을 되돌리고 → build.py 로 ADR 블록만 다시 넣는다. 최대 4번.
  작업 트리에 이 둘 밖의 미커밋 변경이 있으면 원격으로 맞추지 않고 멈춘다(남의 작업을 지우지 않게).
"""
import argparse
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
PATHS = ["hotel_adr/data", "public/index.html"]
KEEP = ["hotel_adr/data"]
SKIP = "[CI " + "Skip]"     # 쪼개 둔 이유: 이 글자가 커밋 메시지 어디에든 있으면 배포가 빠진다(CLAUDE.md)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def git(*a, check=True):
    r = subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(a)} → {r.returncode}\n{r.stdout}{r.stderr}")
    return r


def staged():
    return [l for l in git("diff", "--cached", "--name-only").stdout.splitlines() if l.strip()]


def mine(p):
    return any(p == q or p.startswith(q.rstrip("/") + "/") for q in PATHS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    try:
        rows = (HERE / "data" / "ota.csv").read_text(encoding="utf-8").strip().splitlines()[1:]
        last = max(r.split(",")[0] for r in rows)
        n = sum(1 for r in rows if r.startswith(last + ",") and r.rstrip().endswith(",ok"))
        tag = f"Google 호텔 {last} · ok {n}"
    except Exception:
        tag = "호텔 ADR"
    for attempt in range(4):
        msg = f"호텔 ADR {tag}" + ("" if a.deploy else " " + SKIP)
        git("add", "-A", "--", *PATHS)
        if not staged():
            print("변경 없음 — 커밋하지 않는다")
            return 0
        others = [p for p in staged() if not mine(p)]
        if others:
            print("내 것이 아닌 스테이징 파일이 있다 — 손대지 않고 멈춘다:", others)
            return 3
        if a.dry:
            print("[dry]", staged(), msg)
            return 0
        git("commit", "-q", "-m", msg, "--", *PATHS)
        r = git("push", "origin", "HEAD:main", check=False)
        if r.returncode == 0:
            print(f"push 완료 ({attempt + 1}번째) · {git('rev-parse', '--short', 'HEAD').stdout.strip()} · {msg}")
            return 0
        print(f"push 거절 ({attempt + 1}번째) — 원격 최신 위에 다시 주입\n{r.stderr.strip()[-300:]}")
        dirty = [l[3:] for l in git("status", "--porcelain").stdout.splitlines() if l.strip() and not mine(l[3:].strip('"'))]
        if dirty:
            print("작업 트리에 내 것이 아닌 변경이 있다 — 원격으로 맞추지 않고 멈춘다:", dirty[:8])
            return 3
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="adr_"))
        for k in KEEP:
            src = REPO / k
            if src.is_dir():
                shutil.copytree(src, tmp / k)
        git("fetch", "-q", "origin", "main")
        git("reset", "-q", "--hard", "origin/main")
        for k in KEEP:
            src, dst = tmp / k, REPO / k
            if src.is_dir():
                shutil.rmtree(dst, ignore_errors=True)
                shutil.copytree(src, dst)
        shutil.rmtree(tmp, ignore_errors=True)
        r = subprocess.run([sys.executable, str(HERE / "build.py")], cwd=REPO, capture_output=True, text=True)
        print(r.stdout.strip())
        if r.returncode:
            print(r.stderr.strip()[-600:])
            return 4
    print("4번 다 거절 — 다음 회차에 다시")
    return 5


if __name__ == "__main__":
    sys.exit(main())
