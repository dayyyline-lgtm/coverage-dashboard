# -*- coding: utf-8 -*-
"""국면 주간 회차 — 이 PC 받기 서버(.claude/devserver.py)가 받은 덤프를 저장소 파일로 옮긴다 (2026-10-27).

크롬 탭이 덤프를 폼 POST 로 http://127.0.0.1:8766/recv 에 보내면 서버가 .claude/recv/<이름>.txt 에 그대로 쓴다.
옮겨 적기가 없어 틀릴 일이 없다 — 대신 페이지가 찍은 길이·검산값과 여기서 찍는 값이 같은지 본다.

  python kbeauty/phase_recv.py us <받은 파일> [--sku N]   # KBPH.dump() 본문(DUMPSTART…DUMPEND) → data/phase/<asOf>.json
                                                           #   ko·co·sup·src 는 직전 파일에서 옮긴다(덤프엔 없다) · --sku = 배지 SKU 수(설명 칸)
  python kbeauty/phase_recv.py eu <받은 파일> [--date D]   # 유럽 5개국 + '@@JPCA@@' + 일본·캐나다 → data/phase/eu/<날짜>.txt · <날짜>-jpca.txt
  python kbeauty/phase_recv.py fm <받은 파일> [--date D]   # FastMoss 덤프 → data/phase/fm/<날짜>.txt
  python kbeauty/phase_recv.py hash <받은 파일>            # 길이·검산값만

검산값 h = (h*31 + 글자 코드) mod 1e9+7 — 페이지 쪽 window.__send 와 같은 식(kbeauty/RUNBOOK.md 1-e).
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
PH = HERE / "data" / "phase"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def jhash(t):
    h = 0
    for ch in t:
        h = (h * 31 + ord(ch)) % 1000000007
    return h


def kst_today():
    return (dt.datetime.utcnow() + dt.timedelta(hours=9)).date().isoformat()


def do_us(t, sku):
    a, b = t.find("DUMPSTART"), t.rfind("DUMPEND")
    if a < 0 or b < 0:
        sys.exit("DUMPSTART…DUMPEND 가 없다 — KBPH.dump() 본문을 보냈는지 볼 것")
    d = json.loads(t[a + len("DUMPSTART"):b])
    prev = sorted(p for p in PH.glob("20??-??-??.json") if p.stem < d["asOf"])
    if not prev:
        sys.exit("직전 국면 파일이 없다")
    old = json.loads(prev[-1].read_text(encoding="utf-8"))
    miss = []
    for k, x in d["b"].items():
        o = old["b"].get(k)
        if not o:
            miss.append(k)
            continue
        for f in ("ko", "co", "sup"):
            if f in o:
                x[f] = o[f]
    src = old.get("src", "")
    nb = (d.get("fit") or {}).get("nbSku")
    if nb is not None:
        src = re.sub(r"배지 없는 세트·번들 \d+개", f"배지 없는 세트·번들 {nb}개", src)
    if sku:
        src = re.sub(r"SKU [\d,]+개", f"SKU {sku:,}개", src, count=1)
    d["src"] = src
    out = PH / f"{d['asOf']}.json"
    out.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"[US] {out.name} · 브랜드 {len(d['b'])} · 직전 {prev[-1].name} · 한글 이름 없는 브랜드 {miss or '없음'} · rw {'있음' if d.get('rws') else '없음'}")


def do_eu(t, date):
    if "\n@@JPCA@@\n" not in t:
        sys.exit("'@@JPCA@@' 구분이 없다 — 유럽 5개국 + 일본·캐나다를 한 번에 보냈는지 볼 것")
    eu, jc = t.split("\n@@JPCA@@\n", 1)
    (PH / "eu").mkdir(exist_ok=True)
    for name, body in ((f"{date}.txt", eu), (f"{date}-jpca.txt", jc)):
        (PH / "eu" / name).write_text(body.rstrip("\n") + "\n", encoding="utf-8", newline="\n")
    heads = [l for l in t.splitlines() if l.startswith("D|")]
    print(f"[EU] eu/{date}.txt · eu/{date}-jpca.txt · 나라 {len(heads)}")
    for l in heads:
        print("   ", l)


def do_fm(t, date):
    if not t.startswith("FH|") or "\nEND|" not in t:
        sys.exit("FH| 로 시작해 END| 로 끝나는 FastMoss 덤프가 아니다")
    (PH / "fm").mkdir(exist_ok=True)
    (PH / "fm" / f"{date}.txt").write_text(t.rstrip("\n") + "\n", encoding="utf-8", newline="\n")
    print(f"[FM] fm/{date}.txt · 샵 줄 {sum(1 for l in t.splitlines() if l.startswith('S|'))}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["us", "eu", "fm", "hash"])
    ap.add_argument("file")
    ap.add_argument("--date", default=None)
    ap.add_argument("--sku", type=int, default=0)
    a = ap.parse_args()
    t = pathlib.Path(a.file).read_text(encoding="utf-8")
    print(f"받은 파일 {pathlib.Path(a.file).name} · len {len(t)} h {jhash(t)}")
    date = a.date or kst_today()
    if a.kind == "us":
        do_us(t, a.sku)
    elif a.kind == "eu":
        do_eu(t, date)
    elif a.kind == "fm":
        do_fm(t, date)


if __name__ == "__main__":
    main()
