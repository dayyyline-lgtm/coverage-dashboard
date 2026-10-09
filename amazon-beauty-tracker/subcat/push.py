# -*- coding: utf-8 -*-
"""ingest.py 가 바꾼 파일만 커밋해 올린다 (예약 작업 · 클라우드 세션에서 부른다).

  python amazon-beauty-tracker/subcat/push.py          # 저장소 루트 어디서 불러도 된다

- 잡는 파일은 셋뿐: amazon-beauty-tracker/data/subcat/ · amazon-beauty-tracker/subcat/config.json · public/index.html.
  pathspec 으로 커밋해 다른 작업이 인덱스에 올라와 있어도 휩쓸리지 않는다.
- 커밋 메시지에 항상 배포 생략 표시를 단다 — Cloudflare 빌드가 월 500건 한도 직전이라(2026-10 기준 30일 480건대),
  이 데이터는 봇의 다음 배포(평일 09~16시 매시간 · 주말 12·20시)가 같이 싣는다. 급하면 --deploy.
- push 가 거절되면 **합치지 않는다**(루트 CLAUDE.md 'index.html 에 쓰는 법'): 내 데이터 파일을 떼어 두고 →
  원격 최신으로 맞춘 뒤(reset --hard) → 데이터 파일을 되돌려 놓고 → ingest.py --inject 로 블록만 다시 주입 → 커밋.
  원격의 다른 상수는 원격 것이 그대로 남는다. 최대 4번.
"""
import argparse
import datetime
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
PATHS = ["amazon-beauty-tracker/data/subcat", "amazon-beauty-tracker/subcat/config.json", "public/index.html"]
KEEP = ["amazon-beauty-tracker/data/subcat", "amazon-beauty-tracker/subcat/config.json"]   # 재주입 때 떼어 둘 내 파일
SKIP = "[CI " + "Skip]"     # 글자를 쪼개 둔 이유: 이 파일을 고치는 커밋 메시지에 설명으로 붙여 넣다 배포가 빠진 적이 있다(CLAUDE.md)

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true", help="배포 생략 표시를 달지 않는다(지금 바로 사이트에 반영)")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    kst = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)
    try:
        days = (REPO / "amazon-beauty-tracker/data/subcat/days.csv").read_text(encoding="utf-8").strip().splitlines()
        last = days[-1].split(",")
        tag = f"{last[0]} · 카테고리 {last[2]}/{last[3]} · 한국 자리 {last[5]}" + (" · 부분" if last[8] == "1" else "")
    except Exception:
        tag = kst.strftime("%Y-%m-%d")
    msg = f"아마존 세부 카테고리 {tag} ({kst:%H:%M} KST)" + ("" if a.deploy else " " + SKIP)

    for attempt in range(4):
        git("add", "-A", "--", *PATHS)
        if not staged():
            print("변경 없음 — 커밋하지 않는다")
            return 0
        others = [p for p in staged() if not any(p == q or p.startswith(q.rstrip("/") + "/") for q in PATHS)]
        if others:
            print("내 것이 아닌 스테이징 파일이 있다 — 손대지 않고 멈춘다:", others)
            return 3
        if a.dry:
            print("[dry] 커밋할 파일:", staged(), "\n[dry] 메시지:", msg)
            return 0
        git("commit", "-q", "-m", msg, "--", *PATHS)
        r = git("push", "origin", "HEAD:main", check=False)
        if r.returncode == 0:
            print(f"push 완료 ({attempt + 1}번째) · {git('rev-parse', '--short', 'HEAD').stdout.strip()} · {msg}")
            return 0
        print(f"push 거절 ({attempt + 1}번째) — 원격 최신 위에 다시 주입한다\n{r.stderr.strip()[-400:]}")
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="amzsub_"))
        for k in KEEP:
            src = REPO / k
            if src.is_dir():
                shutil.copytree(src, tmp / k)
            elif src.exists():
                (tmp / k).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, tmp / k)
        git("fetch", "-q", "origin", "main")
        git("reset", "-q", "--hard", "origin/main")
        for k in KEEP:
            src, dst = tmp / k, REPO / k
            if src.is_dir():
                shutil.rmtree(dst, ignore_errors=True)
                shutil.copytree(src, dst)
            elif src.exists():
                shutil.copy2(src, dst)
        shutil.rmtree(tmp, ignore_errors=True)
        r = subprocess.run([sys.executable, str(HERE / "ingest.py"), "--inject"], cwd=REPO, capture_output=True, text=True)
        print(r.stdout.strip())
        if r.returncode:
            print(r.stderr.strip()[-600:])
            return 4
    print("4번 다 거절 — 다음 회차에 다시")
    return 5


if __name__ == "__main__":
    sys.exit(main())
