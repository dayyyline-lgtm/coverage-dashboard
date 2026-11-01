# -*- coding: utf-8 -*-
"""Keepa 주간 통합 수집(keepa_week.js) 덤프 → 회사 채널(KBCH) · 국면 미국 · 국면 유럽·일본·캐나다 (2026-11-01).

  python3 kbeauty/week_recv.py <덤프> [--compare] [--date D] [--dry] [--only KBCH]
    덤프 = __KW.bundle() 의 본문(@@KBCH@@ · @@US@@ · @@EU@@ 구획 · 끝 @@END@@).
    --compare  KBCH 를 저장하기 전에 지금 data/keepa_month.csv(직전 회차)와 같은 달끼리 견준다
               — 통합 수집은 '배지가 한 번도 없고 지금 30만 위 밖' 상품을 안 받는다. 그 몫이 옛 숫자에서 얼마였는지 본다.
    --dry      비교만 하고 아무것도 저장하지 않는다.
  저장은 기존 받는 쪽을 그대로 부른다: KBCH → ingest.py(이 덤프를 data/keepa/<날짜>.txt 로) · 미국 → phase_recv us · 유럽 → phase_recv eu.
  그 뒤에 python3 kbeauty/phase.py · python3 kbeauty/push.py --phase 는 따로.
"""
import argparse
import collections
import csv
import datetime as dt
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import phase_recv  # noqa: E402
import ingest  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

MK = {"1": "미국", "2": "영국", "3": "독일", "4": "프랑스", "5": "일본", "6": "캐나다", "8": "이탈리아", "9": "스페인"}


def split(t):
    if "@@END@@" not in t:
        sys.exit("@@END@@ 가 없다 — 덤프가 잘렸다")
    t = t[: t.rfind("@@END@@")].rstrip("\n")
    out, cur, buf = {}, None, []
    for l in t.split("\n"):
        if l in ("@@KBCH@@", "@@US@@", "@@EU@@"):
            if cur:
                out[cur] = "\n".join(buf)
            cur, buf = l.strip("@"), []
        else:
            buf.append(l)
    if cur:
        out[cur] = "\n".join(buf)
    return out


def ymstr(m):
    return f"{m // 12}-{m % 12 + 1:02d}"


def compare(kb):
    """새 A 줄(완결 월) vs keepa_month.csv — 나라·브랜드별 판매량 비 (새 ÷ 옛)."""
    H = next(l.split("|") for l in kb.splitlines() if l.startswith("H|"))
    MS, MC, mode = int(H[3]), int(H[4]), H[6]
    if mode != "full":
        print("[비교] recent 회차라 건너뛴다(완결 월이 두 개뿐)")
        return
    new = collections.defaultdict(float)
    for l in kb.splitlines():
        if not l.startswith("A|"):
            continue
        f = l.split("|")
        U = [ingest.b36(x) for x in f[5].split(",")]
        for j, u in enumerate(U[:-1]):
            new[(f[1], f[2], ymstr(MS + j))] += u
    old = collections.defaultdict(float)
    for r in csv.DictReader(open(HERE / "data" / "keepa_month.csv", encoding="utf-8")):
        old[(r["d"], r["k"], r["ym"])] += float(r["u"] or 0)
    common_m = sorted({k[2] for k in old} & {k[2] for k in new})
    last12 = common_m[-12:]
    first12 = common_m[:12]
    bd = collections.defaultdict(lambda: [0, 0, 0, 0])
    keys = {(d, k) for (d, k, m) in old} & {(d, k) for (d, k, m) in new}
    for d, k in keys:
        b = bd[d]
        b[0] += sum(new[(d, k, m)] for m in last12); b[1] += sum(old[(d, k, m)] for m in last12)
        b[2] += sum(new[(d, k, m)] for m in first12); b[3] += sum(old[(d, k, m)] for m in first12)
    print(f"[비교] 판매량 새 ÷ 옛 · 최근 12개월({last12[0]}~{last12[-1]}) · 처음 12개월({first12[0]}~{first12[-1]}) · 둘 다 있는 브랜드 {len(keys)}")
    for d in sorted(bd, key=int):
        b = bd[d]
        r1 = b[0] / b[1] if b[1] else float("nan")
        r2 = b[2] / b[3] if b[3] else float("nan")
        print(f"   {MK.get(d, d)}  최근 {r1:.3f} · 처음 {r2:.3f}")
    rows = []
    for d, k in keys:
        o = sum(old[(d, k, m)] for m in last12)
        n = sum(new[(d, k, m)] for m in last12)
        if o > 20000:
            rows.append((n / o if o else 0, d, k, o, n))
    rows.sort()
    print("   브랜드별 최근 12개월 비(옛 2만 개 넘는 것 · 낮은 순 8 · 높은 순 4):")
    for r in rows[:8] + rows[-4:]:
        print(f"     {MK.get(r[1], r[1])} {r[2]}: {r[0]:.3f} (옛 {r[3]:,.0f} → 새 {r[4]:,.0f})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--date", default=None)
    ap.add_argument("--only", default="KBCH,US,EU", help="저장할 구획(쉼표) — 예: KBCH 만")
    a = ap.parse_args()
    t = pathlib.Path(a.file).read_text(encoding="utf-8").replace("\r\n", "\n")
    print(f"받은 파일 {pathlib.Path(a.file).name} · len {len(t)} h {phase_recv.jhash(t)}")
    P = split(t)
    print("구획", {k: len(v) for k, v in P.items()})
    if "KBCH" in P and a.compare:
        compare(P["KBCH"])
    if a.dry:
        return
    date = a.date or phase_recv.kst_today()
    only = set(a.only.upper().split(","))
    P = {k: v for k, v in P.items() if k in only}
    if "KBCH" in P:
        tmp = HERE / "data" / "keepa" / f"_week_{date}.txt"
        tmp.write_text(P["KBCH"] + "\n", encoding="utf-8", newline="\n")
        rc = ingest.main([str(tmp)])
        tmp.unlink(missing_ok=True)
        print(f"[KBCH] ingest 종료코드 {rc}")
    if "US" in P:
        phase_recv.do_us(P["US"], 0)
    if "EU" in P:
        phase_recv.do_eu(P["EU"], date)


if __name__ == "__main__":
    main()
