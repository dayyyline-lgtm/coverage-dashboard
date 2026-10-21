# -*- coding: utf-8 -*-
"""kbeauty/ingest.py 가 바꾼 파일만 커밋해 올린다 (크롬 수집 세션에서 부른다 · 2026-10-20).

  python3 kbeauty/push.py            # 배포 생략 표시 — 봇의 다음 배포(평일 장중 매시)가 같이 싣는다
  python3 kbeauty/push.py --deploy   # 지금 바로 배포

- 잡는 파일: kbeauty/data/ · kbeauty/config.json · public/index.html (pathspec 커밋 — 인덱스에 남의 작업이 올라와 있어도 안 휩쓸린다)
- push 가 거절되면 합치지 않는다(루트 CLAUDE.md 'index.html 에 쓰는 법'): 내 데이터 파일을 떼어 두고 → 원격 최신으로 맞춘 뒤 →
  데이터 파일을 되돌리고 → ingest.py --inject 로 KBCH 블록만 다시 넣는다. 최대 4번.
"""
import argparse
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
PATHS = ["kbeauty/data", "kbeauty/config.json", "public/index.html"]
KEEP = ["kbeauty/data", "kbeauty/config.json"]
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--phase", action="store_true", help="국면 주간 회차(KBPH) — 바로 배포하고 주간 브리핑 워크플로를 깨운다")
    a = ap.parse_args()
    if a.phase:
        a.deploy = True
    try:
        import json
        meta = json.loads((HERE / "data" / "keepa_meta.json").read_text(encoding="utf-8"))
        tag = f"Keepa {meta.get('date', '')}"
    except Exception:
        tag = "K뷰티 채널"
    for attempt in range(4):
        if a.phase:
            try:
                import re as _re
                asof = _re.search(r'^const KBPH = \{"asOf":"([0-9-]+)"', (REPO / "public" / "index.html").read_text(encoding="utf-8"), _re.M).group(1)
            except Exception:
                asof = ""
            msg = f"K뷰티 국면 주간 {asof}"
        else:
            msg = f"K뷰티 채널 모델 {tag}" + ("" if a.deploy else " " + SKIP)
        git("add", "-A", "--", *PATHS)
        if not staged():
            print("변경 없음 — 커밋하지 않는다")
            return 0
        others = [p for p in staged() if not any(p == q or p.startswith(q.rstrip("/") + "/") for q in PATHS)]
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
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="kbch_"))
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
        for sc in (["ingest.py", "--inject"], ["phase.py"]):   # KBCH · KBPH 둘 다 원격 최신 위에 다시 넣는다
            r = subprocess.run([sys.executable, str(HERE / sc[0]), *sc[1:]], cwd=REPO, capture_output=True, text=True)
            print(r.stdout.strip())
            if r.returncode:
                print(r.stderr.strip()[-600:])
                return 4
    print("4번 다 거절 — 다음 회차에 다시")
    return 5


if __name__ == "__main__":
    sys.exit(main())
