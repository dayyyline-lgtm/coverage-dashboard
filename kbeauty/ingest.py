# -*- coding: utf-8 -*-
"""K뷰티 채널 데이터(Keepa · FastMoss 크롬 덤프) → kbeauty/data/ 파일 + public/index.html 의 `const KBCH` 한 줄 (2026-10-20).

  python3 kbeauty/ingest.py --check  /tmp/kbk/*.txt /tmp/kfm/*.txt    # CRC 만 본다(틀린 줄은 redo 키를 알려 준다)
  python3 kbeauty/ingest.py          /tmp/kbk/*.txt /tmp/kfm/*.txt    # 저장 + 블록
  python3 kbeauty/ingest.py --inject                                  # 저장된 파일로 블록만 다시(재주입)
  python3 kbeauty/ingest.py --tasks                                   # config.json → keepa_tasks.json
  python3 kbeauty/ingest.py --due                                     # 마지막 Keepa 회차가 6일 넘었으면 종료코드 0

덤프 형식은 keepa.js · fastmoss.js 맨 위 주석. 머리 4줄(Title: · URL: · Source element: · ---)은 버린다.

데이터 파일
  data/keepa_month.csv   ym,d,k,u,v         — 완결 월의 판매량(개)·판매액(현지 통화). 회차마다 그 (d,k) 를 통째로 갈아 끼운다(곡선이 바뀌면 옛 달도 바뀐다).
  data/keepa_recent.csv  asof,d,k,u,v       — '최근 30일'(배지 = 지난 30일 · 순위 = 30일 평균). 회차마다 한 줄씩 쌓는다.
  data/keepa_top.csv     asof,d,k,i,g,n,t,p,u13,v13 — 판매액 상위 묶음(마지막 회차만)
  data/keepa_curves.csv  asof,d,n,bins,a,b1,b2,tag
  data/fm_daily.csv      date,r,s,u,v       — 틱톡샵 샵별 일별 판매량·판매액(USD 등 샵 통화). 같은 날은 갈아 끼운다.
  data/fm_shops.csv      s,r,k,name,cur,first — 샵 사전(FastMoss seller_id · 지역 · 브랜드 키)
  data/keepa/<날짜>.txt · data/fastmoss/<날짜>.txt — 덤프 원문(검산용)
"""
import csv
import datetime as dt
import json
import re
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DATA = HERE / "data"
INDEX = REPO / "public" / "index.html"
CFG = HERE / "config.json"
IR = HERE / "ir.json"

REC = re.compile(r"^(H|F|A|T|X|FH|S|D|E|END)\|")


def b36(s):
    return int(s, 36) if s else 0


def _crc36(s):
    n = zlib.crc32(s.encode("utf-8")) & 0xFFFFFFFF
    if n == 0:
        return "0"
    d, out = "0123456789abcdefghijklmnopqrstuvwxyz", ""
    while n:
        n, r = divmod(n, 36)
        out = d[r] + out
    return out


def read_lines(files):
    """파일들에서 덤프 줄만. 같은 키(줄의 앞 칸들)가 여럿이면 CRC 가 맞는 것."""
    good, bad = {}, {}
    order = []
    for f in files:
        for raw in Path(f).read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not REC.match(line):
                continue
            key = _key(line)
            if key not in good and key not in bad:
                order.append(key)
            if line.startswith("END|"):
                good.setdefault(key, []).append(line)
                continue
            if _crc36(line.rpartition("|")[0]) == line.rpartition("|")[2]:
                good[key] = [line]
                bad.pop(key, None)
            elif key not in good:
                bad[key] = line
    return order, good, bad


def _key(line):
    f = line.split("|")
    t = f[0]
    if t in ("A", "X"):
        return "|".join(f[:3]) + "|"
    if t == "T":
        return "|".join(f[:4]) + "|"
    if t in ("F",):
        return "|".join(f[:2]) + "|"
    if t in ("S",):
        return "|".join(f[:2]) + "|"
    if t == "D":
        return "|".join(f[:3]) + "|"
    if t == "END":
        return "END|" + f[1] + "|"
    return t + "|"


# ───────────────────────── Keepa ─────────────────────────

def ym_str(M):
    return f"{M // 12:04d}-{M % 12 + 1:02d}"


def parse_keepa(lines):
    H = next((l for l in lines if l.startswith("H|")), None)
    if not H:
        return None
    h = H.split("|")
    res = {"v": h[1], "date": h[2], "MS": int(h[3]), "MC": int(h[4]), "tasks": int(h[5]), "mode": h[6],
           "F": [], "A": [], "T": [], "X": []}
    for l in lines:
        f = l.split("|")
        if f[0] == "F":
            res["F"].append({"d": int(f[1]), "n": int(f[2] or 0), "bins": int(f[3] or 0), "a": f[4], "b1": f[5], "b2": f[6], "tag": f[7]})
        elif f[0] == "A":
            U = [b36(x) for x in f[5].split(",")]
            V = [b36(x) for x in f[6].split(",")]
            res["A"].append({"d": int(f[1]), "k": f[2], "n": int(f[3]), "g": int(f[4]), "U": U, "V": V, "rank": int(f[7] or 0)})
        elif f[0] == "T":
            res["T"].append({"d": int(f[1]), "k": f[2], "i": int(f[3]), "g": f[4], "n": int(f[5]), "t": f[6], "p": b36(f[7]),
                             "u": [b36(x) for x in f[8].split(",")], "v": [b36(x) for x in f[9].split(",")]})
        elif f[0] == "X":
            res["X"].append({"d": int(f[1]), "k": f[2], "why": f[3]})
    return res


def save_keepa(res, raw_text):
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "keepa").mkdir(exist_ok=True)
    (DATA / "keepa" / f"{res['date']}.txt").write_text(raw_text, encoding="utf-8", newline="\n")
    MS, MC = res["MS"], res["MC"]
    full = res["mode"] == "full"
    first = MS if full else MC - 2
    # 완결 월
    path = DATA / "keepa_month.csv"
    old = []
    if path.exists():
        with open(path, encoding="utf-8", newline="") as f:
            old = list(csv.DictReader(f))
    got = {(a["d"], a["k"]) for a in res["A"]}
    months = {ym_str(M) for M in range(first, MC)}
    keep = [r for r in old if not ((int(r["d"]), r["k"]) in got and r["ym"] in months)]
    new = []
    for a in res["A"]:
        for j, M in enumerate(range(first, MC + 1)):
            if M == MC:
                continue
            u, v = a["U"][j] if j < len(a["U"]) else 0, a["V"][j] if j < len(a["V"]) else 0
            if u or v:
                new.append({"ym": ym_str(M), "d": a["d"], "k": a["k"], "u": u, "v": v})
    rows = keep + new
    rows.sort(key=lambda r: (r["k"], int(r["d"]), r["ym"]))
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ym", "d", "k", "u", "v"])
        w.writeheader()
        w.writerows(rows)
    # 최근 30일
    rp = DATA / "keepa_recent.csv"
    rec = []
    if rp.exists():
        with open(rp, encoding="utf-8", newline="") as f:
            rec = [r for r in csv.DictReader(f) if r["asof"] != res["date"]]
    for a in res["A"]:
        u, v = a["U"][-1] if a["U"] else 0, a["V"][-1] if a["V"] else 0
        rec.append({"asof": res["date"], "d": a["d"], "k": a["k"], "u": u, "v": v})
    rec.sort(key=lambda r: (r["asof"], r["k"], int(r["d"])))
    with open(rp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["asof", "d", "k", "u", "v"])
        w.writeheader()
        w.writerows(rec)
    # 상위 묶음 · 곡선
    with open(DATA / "keepa_top.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["asof", "d", "k", "i", "g", "n", "t", "p", "u13", "v13"])
        for t in res["T"]:
            w.writerow([res["date"], t["d"], t["k"], t["i"], t["g"], t["n"], t["t"], t["p"], " ".join(map(str, t["u"])), " ".join(map(str, t["v"]))])
    cp = DATA / "keepa_curves.csv"
    cur = []
    if cp.exists():
        with open(cp, encoding="utf-8", newline="") as f:
            cur = [r for r in csv.DictReader(f) if r["asof"] != res["date"]]
    for c in res["F"]:
        cur.append({"asof": res["date"], "d": c["d"], "n": c["n"], "bins": c["bins"], "a": c["a"], "b1": c["b1"], "b2": c["b2"], "tag": c["tag"]})
    with open(cp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["asof", "d", "n", "bins", "a", "b1", "b2", "tag"])
        w.writeheader()
        w.writerows(cur)
    mp = DATA / "keepa_meta.json"
    om = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
    # full = 마지막 전체(36개월) 회차 · sig = 그때 과제 목록 — --due 가 다음 모드를 정한다
    meta = {"date": res["date"], "MS": MS, "MC": MC, "mode": res["mode"], "tasks": res["tasks"],
            "full": res["date"] if full else om.get("full", ""), "sig": tasks_sig() if full else om.get("sig", ""),
            "fail": [f"{x['d']}:{x['k']}:{x['why']}" for x in res["X"]]}
    mp.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(new)


# ───────────────────────── FastMoss ─────────────────────────

def parse_fm(lines):
    """FH|v|날짜|샵 수 · S|샵ID|지역|브랜드키|통화|이름|첫날 · D|샵ID|첫날|u…|v… (일별 36진수, v 는 통화 단위 정수) · E|샵ID|사유"""
    H = next((l for l in lines if l.startswith("FH|")), None)
    if not H:
        return None
    h = H.split("|")
    res = {"date": h[2], "S": {}, "D": {}, "E": []}
    for l in lines:
        f = l.split("|")
        if f[0] == "S":
            res["S"][f[1]] = {"s": f[1], "r": f[2], "k": f[3], "cur": f[4], "name": f[5], "first": f[6]}
        elif f[0] == "D":
            res["D"][f[1]] = {"first": f[2], "u": [b36(x) for x in f[3].split(",")], "v": [b36(x) for x in f[4].split(",")]}
        elif f[0] == "E":
            res["E"].append({"s": f[1], "why": f[2]})
    return res


def save_fm(res, raw_text):
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "fastmoss").mkdir(exist_ok=True)
    (DATA / "fastmoss" / f"{res['date']}.txt").write_text(raw_text, encoding="utf-8", newline="\n")
    sp = DATA / "fm_shops.csv"
    shops = {}
    if sp.exists():
        with open(sp, encoding="utf-8", newline="") as f:
            shops = {r["s"]: r for r in csv.DictReader(f)}
    for s, x in res["S"].items():
        shops[s] = {"s": s, "r": x["r"], "k": x["k"], "name": x["name"], "cur": x["cur"], "first": min(x["first"], shops.get(s, {}).get("first", x["first"]) or x["first"])}
    with open(sp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["s", "r", "k", "name", "cur", "first"])
        w.writeheader()
        w.writerows(sorted(shops.values(), key=lambda r: (r["k"], r["r"], r["s"])))
    dp = DATA / "fm_daily.csv"
    rows = {}
    if dp.exists():
        with open(dp, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                rows[(r["s"], r["date"])] = r
    n = 0
    for s, x in res["D"].items():
        d0 = dt.date.fromisoformat(x["first"])
        for i, (u, v) in enumerate(zip(x["u"], x["v"])):
            day = (d0 + dt.timedelta(days=i)).isoformat()
            rows[(s, day)] = {"date": day, "r": res["S"].get(s, {}).get("r", ""), "s": s, "u": u, "v": v}
            n += 1
    with open(dp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "r", "s", "u", "v"])
        w.writeheader()
        w.writerows(sorted(rows.values(), key=lambda r: (r["s"], r["date"])))
    return n


# ───────────────────────── 블록 ─────────────────────────

def load_csv(p):
    if not p.exists():
        return []
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def build_block():
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    meta = json.loads((DATA / "keepa_meta.json").read_text(encoding="utf-8")) if (DATA / "keepa_meta.json").exists() else {}
    km = load_csv(DATA / "keepa_month.csv")
    yms = sorted({r["ym"] for r in km})
    kp = {}
    for r in km:
        e = kp.setdefault(r["k"], {}).setdefault(r["d"], {"u": {}, "v": {}})
        e["u"][r["ym"]] = int(r["u"])
        e["v"][r["ym"]] = int(r["v"])
    kpb = {}
    for k, ds in kp.items():
        for d, e in ds.items():
            if not any(e["v"].values()):
                continue
            kpb.setdefault(k, {})[d] = [[e["u"].get(m, 0) for m in yms], [e["v"].get(m, 0) for m in yms]]
    rec = load_csv(DATA / "keepa_recent.csv")
    last = max((r["asof"] for r in rec), default="")
    k30 = {}
    for r in rec:
        if r["asof"] == last and (int(r["u"]) or int(r["v"])):
            k30.setdefault(r["k"], {})[r["d"]] = [int(r["u"]), int(r["v"])]
    hist30 = {}
    for r in rec:
        if int(r["v"]):
            hist30.setdefault(r["k"], {}).setdefault(r["d"], []).append([r["asof"], int(r["v"])])
    # 상위 묶음 — 회사마다 최근 3개월 판매액(원화 환산) 상위 16개만 싣는다(화면은 14개 · 블록 크기)
    fxr0 = load_csv(DATA / "fx_month.csv")
    fx_last = {c: float(fxr0[-1][c]) for c in ("USD", "GBP", "EUR", "JPY", "CAD") if fxr0 and fxr0[-1].get(c)} if fxr0 else {}
    cur_of = {int(d): v[1] for d, v in cfg["domains"].items()}
    co_of = {b["k"]: b["co"] for b in cfg["brands"]}
    cand = {}
    for r in load_csv(DATA / "keepa_top.csv"):
        v13 = [int(x) for x in r["v13"].split()]
        d = int(r["d"])
        krw = sum(v13[-4:-1]) * fx_last.get(cur_of.get(d, "USD"), 1)
        cand.setdefault(co_of.get(r["k"], ""), []).append((krw, r["k"], [d, int(r["i"]), r["t"], int(r["p"] or 0), int(r["n"]), v13, r["g"]]))
    top = {}
    for co, rs in cand.items():
        for _, k, row in sorted(rs, key=lambda x: -x[0])[:16]:
            top.setdefault(k, []).append(row)
    curves = {}
    for r in load_csv(DATA / "keepa_curves.csv"):
        if r["asof"] == meta.get("date"):
            curves[r["d"]] = [float(r["a"] or 0), float(r["b1"] or 0), float(r["b2"] or 0), int(r["n"] or 0), r["tag"]]
    # 틱톡샵
    shops = {r["s"]: r for r in load_csv(DATA / "fm_shops.csv")}
    daily = {}
    for r in load_csv(DATA / "fm_daily.csv"):
        daily.setdefault(r["s"], []).append(r)
    tt = {}
    fm_last = ""
    for s, rs in daily.items():
        rs.sort(key=lambda r: r["date"])
        d0 = dt.date.fromisoformat(rs[0]["date"])
        d1 = dt.date.fromisoformat(rs[-1]["date"])
        n = (d1 - d0).days + 1
        U, V = [0] * n, [0] * n
        for r in rs:
            i = (dt.date.fromisoformat(r["date"]) - d0).days
            U[i], V[i] = int(r["u"]), int(r["v"])
        sh = shops.get(s, {})
        tt[s] = {"k": sh.get("k", ""), "r": sh.get("r", ""), "n": sh.get("name", ""), "c": sh.get("cur", "USD"), "d0": d0.isoformat(), "u": U, "v": V}
        fm_last = max(fm_last, d1.isoformat())
    fx = {}
    fxr = load_csv(DATA / "fx_month.csv")
    for r in fxr:
        fx[r["ym"]] = [float(r[c]) if r.get(c) else None for c in ("USD", "GBP", "EUR", "JPY", "CAD")]
    ir = json.loads(IR.read_text(encoding="utf-8")) if IR.exists() else {}
    brands = {b["k"]: {"co": b["co"], "ko": b["ko"]} for b in cfg["brands"]}
    block = {
        "asOf": max(meta.get("date", ""), fm_last),
        "kp": {"asOf": meta.get("date", ""), "months": yms, "b": kpb, "r30": k30, "h30": hist30, "top": top, "curves": curves,
               "fail": meta.get("fail", [])},
        "tt": {"asOf": fm_last, "s": tt},
        "fx": {"cols": ["USD", "GBP", "EUR", "JPY", "CAD"], "m": fx},
        "dom": {k: v[:2] for k, v in cfg["domains"].items()},
        "co": cfg["companies"],
        "brands": brands,
        "ir": ir,
    }
    return block


def inject(block):
    html = INDEX.read_text(encoding="utf-8")
    line = "const KBCH = " + json.dumps(block, ensure_ascii=False, separators=(",", ":")) + ";"
    pat = re.compile(r"^const KBCH = .*$", re.M)
    if pat.search(html):
        new = pat.sub(lambda _m: line, html, count=1)
    else:
        mk = re.search(r"^const AMZL = .*$", html, re.M) or re.search(r"^const AMZSUB = .*$", html, re.M)
        if mk:
            new = html[:mk.end()] + "\n" + line + html[mk.end():]
        else:
            at = html.index("const LIVE = ")
            new = html[:at] + line + "\n" + html[at:]
    if new == html:
        return False
    INDEX.write_text(new, encoding="utf-8", newline="\n")
    return True


def make_tasks():
    """config.json → keepa_tasks.json (브랜드 × 나라 · d = "all"/"few"/[도메인] · tf = 제목 조건)"""
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    out = []
    for b in cfg["brands"]:
        ds = cfg[b["d"]] if isinstance(b["d"], str) else b["d"]
        for d in ds:
            t = {"d": int(d), "k": b["k"], "b": b["kp"]}
            if b.get("tf"):
                t["tf"] = b["tf"]
            out.append(t)
    (HERE / "keepa_tasks.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"keepa_tasks.json · {len(out)}개 과제 · 브랜드 {len(cfg['brands'])}")
    return 0


def tasks_sig():
    p = HERE / "keepa_tasks.json"
    return format(zlib.crc32(p.read_bytes()) & 0xFFFFFFFF, "x") if p.exists() else ""


def due():
    """마지막 Keepa 회차가 6일 넘게 지났으면 0(돌 차례) · 아니면 1. 모드도 알려 준다 —
    full(36개월 전부) = 전체 회차가 없거나 84일 넘었거나 과제 목록(새 브랜드 등)이 그때와 다를 때 · 아니면 recent(최근 3개월만 · 덤프가 절반)"""
    meta = json.loads((DATA / "keepa_meta.json").read_text(encoding="utf-8")) if (DATA / "keepa_meta.json").exists() else {}
    last, fl = meta.get("date", ""), meta.get("full", "")
    today = (dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(hours=9)).date()
    age = (today - dt.date.fromisoformat(last)).days if last else 999
    fage = (today - dt.date.fromisoformat(fl)).days if fl else 999
    mode = "full" if (fage >= 84 or meta.get("sig") != tasks_sig()) else "recent"
    print(f"마지막 Keepa 회차 {last or '없음'} · {age}일 전 · {'돌 차례' if age >= 6 else '아직'} · 모드 {mode}"
          + ("" if mode == "recent" else f" (전체 회차 {fl or '없음'} · 과제 {'같음' if meta.get('sig') == tasks_sig() else '바뀜'})"))
    return 0 if age >= 6 else 1


def main(argv):
    if "--tasks" in argv:
        return make_tasks()
    if "--due" in argv:
        return due()
    check = "--check" in argv
    only_inject = "--inject" in argv
    files = [a for a in argv if not a.startswith("--")]
    if not only_inject:
        order, good, bad = read_lines(files)
        if bad:
            keys = ",".join(sorted(bad))
            print(f"CRC 불일치 {len(bad)}줄 → redo('{keys}')")
            return 2
        lines = [good[k][0] for k in order if k in good]
        # END = 앞 줄 전체의 CRC — 덩어리가 빠지거나 순서가 틀리면 여기서 잡힌다
        for kind, pre in (("KEEPA", ("H|", "F|", "A|", "T|", "X|")), ("FASTMOSS", ("FH|", "S|", "D|", "E|"))):
            body = [l for l in lines if l.startswith(pre) and not l.startswith("END|")]
            ends = [l for l in lines if l.startswith("END|")]
            if not body:
                continue
            ok = any(int(e.split("|")[1]) == len(body) + 1 and e.split("|")[2] == _crc36("\n".join(body)) for e in ends)
            print(f"[{kind}] END {'일치' if ok else '불일치 — 덩어리가 빠졌거나 순서가 틀렸다'} · {len(body)}줄")
            if not ok and not check:
                return 3
        kl = [l for l in lines if l[:2] in ("H|", "F|", "A|", "T|", "X|") or (l.startswith("END|") and False)]
        fl = [l for l in lines if l[:3] == "FH|" or l[:2] in ("S|", "D|", "E|")]
        res_k = parse_keepa(kl) if kl else None
        res_f = parse_fm(fl) if fl else None
        if check:
            if res_k:
                print(f"[KEEPA] {res_k['date']} · 과제 {res_k['tasks']} · 브랜드·나라 {len(res_k['A'])} · 실패 {len(res_k['X'])} · 곡선 {len(res_k['F'])}")
            if res_f:
                print(f"[FASTMOSS] {res_f['date']} · 샵 {len(res_f['S'])} · 일별 {len(res_f['D'])} · 실패 {len(res_f['E'])}")
            return 0
        if res_k:
            raw = "\n".join(kl) + "\n"
            n = save_keepa(res_k, raw)
            print(f"[KEEPA] 저장 {n}줄 · 실패 {len(res_k['X'])}")
        if res_f:
            raw = "\n".join(fl) + "\n"
            n = save_fm(res_f, raw)
            print(f"[FASTMOSS] 일별 {n}줄")
    block = build_block()
    ch = inject(block)
    size = len(json.dumps(block, ensure_ascii=False, separators=(",", ":")))
    print(f"[KBCH] {'갱신' if ch else '변동 없음'} · {size // 1024}KB · keepa {block['kp']['asOf']} · tiktok {block['tt']['asOf']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
