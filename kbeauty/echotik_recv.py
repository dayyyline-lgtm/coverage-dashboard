# -*- coding: utf-8 -*-
"""EchoTik 덤프(echotik.js) → 국면(KBPH)·회사 채널(KBCH)이 읽는 FastMoss 형식 덤프 (2026-11-23 · FastMoss 구독 끝 → EchoTik Pro).

  python3 kbeauty/echotik_recv.py <덤프 파일들> [--date D] [--check] [--compare]
  python3 kbeauty/echotik_recv.py --ids          # __ET.run 에 넘길 샵 ID 전부(fm_shops.csv)

하는 일
  1. 줄마다 CRC · END 검산 → 원문을 data/phase/et/<날짜>.txt 에 둔다.
  2. 샵마다 FastMoss 와 겹친 날(EchoTik 첫날 ~ FastMoss 마지막 날)로 '이어 붙이기 배수' k 를 낸다(판매량 · 판매액 · 영상 · 크리에이터 따로).
     k = FastMoss 합 ÷ EchoTik 합 — 처음 한 번만 정해 data/phase/et_k.json 에 남긴다(지우지 말 것 · 다음 주부터 같은 배수로 잇는다).
     두 곳의 정의가 달라서다: 판매량은 겹친 기간 합이 거의 같고(메디큐브 0.9~1.1배) 판매액은 EchoTik 이 2~5배 크다(단가가 날마다 출렁인다).
  3. FastMoss 가 끝난 다음 날부터만 EchoTik × k 를 FastMoss 형식(FH|E1 …)으로 data/phase/fm/<날짜>.txt 에 쓴다 —
     build_tt(phase.py)·ingest.py(KBCH)가 그대로 읽는다. FastMoss 이력(4/24~11/14)은 건드리지 않는다.
  --compare = 샵별 겹친 기간 비교표만 찍는다.
"""
import argparse
import csv
import datetime as dt
import json
import pathlib
import re
import sys
import zlib

HERE = pathlib.Path(__file__).resolve().parent
PH = HERE / "data" / "phase"
KF = PH / "et_k.json"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def crc36(s):
    n = zlib.crc32(s.encode("utf-8")) & 0xFFFFFFFF
    d, out = "0123456789abcdefghijklmnopqrstuvwxyz", ""
    while n:
        n, r = divmod(n, 36)
        out = d[r] + out
    return out or "0"


def b36(n):
    n = max(0, int(round(n)))
    d, out = "0123456789abcdefghijklmnopqrstuvwxyz", ""
    while n:
        n, r = divmod(n, 36)
        out = d[r] + out
    return out or "0"


def ub36(s):
    return int(s, 36) if s else 0


REC = re.compile(r"^(EH|T|E|END)\|")


def read(files):
    body, end, bad = [], None, []
    for f in files:
        for raw in pathlib.Path(f).read_text(encoding="utf-8").splitlines():
            l = raw.strip()
            if not REC.match(l):
                continue
            if l.startswith("END|"):
                end = l
                continue
            head, _, c = l.rpartition("|")
            if crc36(head) != c:
                bad.append(l[:40])
                continue
            if l not in body:
                body.append(l)
    return body, end, bad


def parse(body):
    res = {"date": None, "T": {}, "E": {}}
    for l in body:
        f = l.split("|")[:-1]
        if f[0] == "EH":
            res["date"] = f[2]
        elif f[0] == "T":
            d0 = dt.date.fromisoformat(f[2])
            cols = [[ub36(x) for x in s.split(",")] for s in f[3:9]]
            res["T"][f[1]] = {"d0": d0, "u": cols[0], "v": cols[1], "a": cols[2], "vi": cols[3], "l": cols[4], "li": cols[5]}
        elif f[0] == "E":
            res["E"][f[1]] = f[2]
    return res


def fm_days():
    """FastMoss 덤프(FH 가 E 로 시작하지 않는 것)만 이어 붙인 샵별 일별 {날: (u, v, a, c, l)}"""
    day = {}
    # 바탕 = KBCH 일별(fm_daily · fm_social) — 국면 덤프에 없는 샵(에이프릴스킨·MEDICUBE USA 등)도 겹친 날을 갖게
    soc0 = {}
    sp = HERE / "data" / "fm_social.csv"
    if sp.exists():
        for r in csv.DictReader(open(sp, encoding="utf-8")):
            soc0[(r["s"], r["date"])] = (int(r["a"]), int(r["c"]), int(r["l"]))
    dp = HERE / "data" / "fm_daily.csv"
    if dp.exists():
        for r in csv.DictReader(open(dp, encoding="utf-8")):
            a, c, lv = soc0.get((r["s"], r["date"]), (None, None, None))
            day.setdefault(r["s"], {})[dt.date.fromisoformat(r["date"])] = (int(r["u"]), int(float(r["v"])), a, c, lv)
    for path in sorted((PH / "fm").glob("20??-??-??.txt")):
        fh = ver = None
        D, V = {}, {}
        for l in path.read_text(encoding="utf-8").splitlines():
            f = l.split("|")
            if f[0] == "FH":
                ver, fh = f[1], dt.date.fromisoformat(f[2])
            elif f[0] == "D":
                D[f[1]] = (dt.date.fromisoformat(f[2]), [ub36(x) for x in f[3].split(",")], [ub36(x) for x in f[4].split(",")])
            elif f[0] == "V":
                V[f[1]] = [[ub36(x) for x in f[k].split(",")] for k in (3, 4, 5)]
        if not fh or str(ver).startswith("E"):
            continue
        for s, (d0, U, Vv) in D.items():
            dd = day.setdefault(s, {})
            soc = V.get(s)
            for i, (u, v) in enumerate(zip(U, Vv)):
                t = d0 + dt.timedelta(days=i)
                if t < fh:
                    a = c = lv = None
                    if soc and i < len(soc[0]):
                        a, c, lv = soc[0][i], soc[1][i], soc[2][i]
                    dd[t] = (u, v, a, c, lv)
    return day


def et_daily(x):
    d0 = x["d0"]
    vi, li = x["vi"], x["li"]
    out = {}
    for i in range(len(x["u"])):
        t = d0 + dt.timedelta(days=i)
        nc = None
        if i > 0 and vi[i] and vi[i - 1]:
            nc = max(0, vi[i] - vi[i - 1]) + max(0, (li[i] or 0) - (li[i - 1] or 0))
        out[t] = (x["u"][i], x["v"][i], x["a"][i], nc, x["l"][i])
    return out


def _fix_price(fm):
    """FastMoss 단가 튐(판매량은 평소인데 단가가 몇 배 — 10/13~19 메디큐브 · 10/17~29 바이오던스)을 빼고 배수를 낸다.
    ingest.build_block·phase.build_tt 와 같은 규칙(직전 28일 중앙 단가의 2.5배 초과 → 판매량 × 중앙 단가). 안 빼면 바이오던스 판매액 배수가 5.9배로 나왔다(2026-11-24)."""
    ds = sorted(fm)
    out = {}
    for i, t in enumerate(ds):
        u, v = fm[t][0], fm[t][1]
        past = sorted(out[x][1] / out[x][0] for x in ds[max(0, i - 28):i] if out[x][0] and out[x][1])   # 고친 값으로 — 튐이 2주 넘게 이어지면 원값 중앙이 튐 쪽으로 간다
        if u and v and len(past) >= 10 and v / u > 2.5 * past[len(past) // 2]:
            v = round(u * past[len(past) // 2])
        out[t] = (u, v) + tuple(fm[t][2:])
    return out


def ratios(fm, et):
    fm, et = _fix_price(fm), _fix_price(et)          # 양쪽 다 — EchoTik 도 하루씩 튄다(바이오던스 11/4 단가 $189)
    ov = sorted(set(fm) & set(et))
    ov28 = ov[-28:]                       # 이어 붙이는 자리 바로 앞 4주 — 배수는 여기서 낸다(겹친 기간 앞쪽은 FastMoss 자체 튐이 섞인다)
    r28 = {}
    for j, k in enumerate(("u", "v", "a", "c")):
        sf = sum(fm[t][j] or 0 for t in ov28 if fm[t][j] is not None and et[t][j] is not None)
        se = sum(et[t][j] or 0 for t in ov28 if fm[t][j] is not None and et[t][j] is not None)
        r28[k] = round(sf / se, 4) if se > 0 and sf > 0 else None
    r = {"k28": r28, "n": len(ov), "from": ov[0].isoformat() if ov else "", "to": ov[-1].isoformat() if ov else ""}
    for j, k in enumerate(("u", "v", "a", "c")):
        sf = sum(fm[t][j] or 0 for t in ov if fm[t][j] is not None and et[t][j] is not None)
        se = sum(et[t][j] or 0 for t in ov if fm[t][j] is not None and et[t][j] is not None)
        r[k] = round(sf / se, 4) if se > 0 and sf > 0 else None
    # 단가(판매액 ÷ 판매량) — 두 곳의 겹친 기간 중앙값과 흔들림(사분위 폭 ÷ 중앙)
    def med(v):
        v = sorted(v)
        return v[len(v) // 2] if v else None

    for j, nm in ((fm, "pf"), (et, "pe")):
        pr = [j[t][1] / j[t][0] for t in ov if j[t][0] > 0 and j[t][1] > 0]
        m = med(pr)
        r[nm] = round(m, 2) if m else None
        if pr and m:
            q = sorted(pr)
            r[nm + "w"] = round((q[3 * len(q) // 4] - q[len(q) // 4]) / m, 2)
    # 판매량 일별 상관(모양이 같은가)
    xs = [fm[t][0] for t in ov]
    ys = [et[t][0] for t in ov]
    if len(xs) > 5:
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
        sxx = sum((a - mx) ** 2 for a in xs) ** .5
        syy = sum((b - my) ** 2 for b in ys) ** .5
        r["cor"] = round(sxy / (sxx * syy), 3) if sxx and syy else None
    return r


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--ids", action="store_true", help="__ET.run 에 넘길 샵 ID 목록(fm_shops.csv 전부)")
    ap.add_argument("--date")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--compare", action="store_true")
    a = ap.parse_args(argv)
    if a.ids:
        ids = sorted({r["s"] for r in csv.DictReader(open(HERE / "data" / "fm_shops.csv", encoding="utf-8"))})
        print(" ".join(ids))
        print(f"[{len(ids)}곳]", file=sys.stderr)
        return 0
    if not a.files:
        ap.error("덤프 파일을 주거나 --ids")
    body, end, bad = read(a.files)
    if bad:
        print(f"CRC 불일치 {len(bad)}줄: {bad[:5]}")
        return 2
    if not end or int(end.split("|")[1]) != len(body) + 1 or end.split("|")[2] != crc36("\n".join(body)):
        print(f"END 불일치 — 덩어리가 빠졌거나 순서가 틀렸다 · 몸통 {len(body)}줄 · {end}")
        return 3
    res = parse(body)
    date = a.date or res["date"]
    print(f"[EchoTik] {date} · 샵 {len(res['T'])} · 실패 {len(res['E'])} {list(res['E'].items())[:5]}")
    if a.check:
        return 0
    shops = {r["s"]: r for r in csv.DictReader(open(HERE / "data" / "fm_shops.csv", encoding="utf-8"))}
    fm = fm_days()
    kall = json.loads(KF.read_text(encoding="utf-8")) if KF.exists() else {}
    rows = []
    for s, x in sorted(res["T"].items()):
        et = et_daily(x)
        r = ratios(fm.get(s, {}), et)
        rows.append((shops.get(s, {}).get("k", s), s, r))
        if s not in kall and r["n"] >= 21:
            q = r["k28"]
            kall[s] = {"k": shops.get(s, {}).get("k", ""), "u": q["u"], "v": q["v"], "a": q["a"], "c": q["c"], "n": r["n"], "from": r["from"], "to": r["to"],
                       "full": {x: r[x] for x in ("u", "v", "a", "c")}, "cor": r.get("cor"), "pf": r.get("pf"), "pe": r.get("pe")}
    print("샵 | 겹친 날 | 판매량 FM÷ET | 판매액 FM÷ET | 영상 | 크리에이터 | 판매량 상관")
    for k, s, r in sorted(rows):
        print(f"{k:12s} {r['n']:3d}  u {r['u']}  v {r['v']}  a {r['a']}  c {r['c']}  cor {r.get('cor')}  4주 u {r['k28']['u']} v {r['k28']['v']}  단가 FM {r.get('pf')}({r.get('pfw')}) ET {r.get('pe')}({r.get('pew')})")
    if a.compare:
        return 0
    (PH / "et").mkdir(exist_ok=True)
    (PH / "et" / f"{date}.txt").write_text("\n".join(body + [end]) + "\n", encoding="utf-8", newline="\n")
    KF.write_text(json.dumps(kall, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    # FastMoss 형식으로 — 샵마다 FastMoss 마지막 날 다음부터
    L = []

    def push(f):
        s = "|".join(str(x) for x in f)
        L.append(s + "|" + crc36(s))

    ids = [s for s in sorted(res["T"]) if s in shops]
    push(["FH", "E1", date, len(ids)])
    for s in ids:
        o = shops[s]
        push(["S", s, o["r"], o["k"], o["cur"], o["name"], o["first"]])
    D, V = [], []
    for s in ids:
        et = et_daily(res["T"][s])
        kk = kall.get(s, {})
        ku = kk.get("u") or 1
        kv = kk.get("v") or 1
        ka = kk.get("a") or 1
        kc = kk.get("c") or 1
        last_fm = max(fm[s]) if fm.get(s) else None
        ds = sorted(t for t in et if (last_fm is None or t > last_fm))
        if not ds:
            continue
        d0 = ds[0]
        span = [d0 + dt.timedelta(days=i) for i in range((ds[-1] - d0).days + 1)]
        D.append(["D", s, d0.isoformat(), ",".join(b36(et[t][0] * ku) for t in span), ",".join(b36(et[t][1] * kv) for t in span)])
        V.append(["V", s, d0.isoformat(), ",".join(b36((et[t][2] or 0) * ka) for t in span),
                  ",".join(b36((et[t][3] or 0) * kc) for t in span), ",".join(b36(et[t][4] or 0) for t in span)])
    for f in D + V:
        push(f)
    for f in D:                                            # 이어 붙인 단가 ÷ FastMoss 중앙 단가 — 배수가 틀렸으면 여기서 보인다
        kk = kall.get(f[1], {})
        uu = [ub36(x) for x in f[3].split(",")]
        vv = [ub36(x) for x in f[4].split(",")]
        if sum(uu) and kk.get("pf"):
            r = sum(vv) / sum(uu) / kk["pf"]
            if r > 1.8 or r < 0.55:
                print(f"[EchoTik 경고] {kk.get('k')} 이어 붙인 단가 ${sum(vv) / sum(uu):.1f} = FastMoss 중앙 ${kk['pf']} 의 {r:.1f}배 — et_k.json 판매액 배수 확인")
    L.append("|".join(["END", str(len(L) + 1), crc36("\n".join(L))]))
    out = PH / "fm" / f"{date}.txt"
    out.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print(f"→ {out.relative_to(HERE.parent)} · 샵 {len(ids)} · 일별 {len(D)}줄(FastMoss 다음 날부터 · × 이어 붙이기 배수)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
