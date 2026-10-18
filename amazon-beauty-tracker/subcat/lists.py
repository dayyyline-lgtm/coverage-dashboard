# -*- coding: utf-8 -*-
"""아마존 7개국 뷰티 Top100 덤프(AMZL · lists.js) → data/lists/ + public/index.html 의 `const AMZL` · KMJAMZ.trk.
(2026-10-18 · PC 트래커를 대신한다 — 사용자 "고치지 말고 예약 작업으로")

  python lists.py --check /tmp/amzl/*.txt     검증만 — 틀린 나라를 알려 준다(그 나라 탭에서 window.__AMZL.again() 로 다시 띄운다)
  python lists.py /tmp/amzl/*.txt             검증 → 저장 → 블록 주입(AMZL · KMJAMZ.trk)
  python lists.py --inject                    저장된 데이터로 블록만 다시 만든다(push 거절 뒤 재주입용)
  python lists.py --today                     오늘(KST) 7개국이 다 ok 면 종료코드 0, 아니면 1 — 빠진 나라를 찍는다
  python lists.py --seed                      마스터(data/lists/skus.json)가 없을 때 미국 세부 카테고리 마스터로 시작한다

덤프 형식은 lists.js 맨 위 주석. 여기서 하는 일:
  1. 덤프마다(AMZL 머리줄 ~ END) 줄 CRC · END 의 줄 수와 전체 CRC · K 줄의 번호가 마스터 안인지 · 새 ASIN 의 T 줄이 있는지 본다.
     한 나라라도 틀리면 아무것도 안 쓰고 종료코드 2. 같은 나라 덤프가 여럿이면(1차 block → 2차 ok) 상태가 좋은 것, 같으면 늦은 것.
  2. data/lists/skus.json   한국 브랜드 ASIN 마스터 [asin, 브랜드 번호(config.brands), 제목 64자, 처음 본 날] — **맨 뒤에만 붙인다**
                            (번호 = 위치 = 다음 덤프의 짧은 번호). 7개국 공용 — 같은 ASIN 은 나라가 달라도 같은 상품이다.
  3. data/lists/YYYY-MM.csv 그날 한국 브랜드 자리 date,market,rank,asin,brand — (날짜, 나라)마다 갈아 끼운다(ok·part 만)
  4. data/lists/days.csv    나라별 회차 date,market,ts,status,read,titled,maxr,kpos — block·norecs 도 적는다(시도했는데 못 받음).
                            같은 (날짜, 나라)에 이미 더 좋은 상태가 있으면 낮추지 않는다.
  5. data/lists/unknown.csv 새 브랜드 후보 date,market,asin,rank,title — (나라, ASIN)마다 처음 본 날 한 줄
  6. public/index.html      `const AMZL = …;`(브랜드별 개수 — app.js amztBuild 가 트래커 대신 쓴다) + KMJAMZ.trk(fetch_kmj.py --trk-only 와 같은 일)
"""
import argparse
import csv
import datetime
import io
import json
import pathlib
import re
import sys
import zlib

HERE = pathlib.Path(__file__).resolve().parent          # amazon-beauty-tracker/subcat
TRACKER = HERE.parent
REPO = TRACKER.parent
DATA = TRACKER / "data" / "lists"
CFG = HERE / "config.json"
MASTER = DATA / "skus.json"
DAYS = DATA / "days.csv"
UNK = DATA / "unknown.csv"
INDEX = REPO / "public" / "index.html"
SUB_MASTER = TRACKER / "data" / "subcat" / "skus.json"

MK = ["US", "UK", "DE", "FR", "IT", "ES", "JP"]
RANK = {"ok": 3, "part": 2, "norecs": 1, "block": 0}
BLOCK_DAYS = 120          # AMZL 블록에 싣는 회차
# 화면(amztBuild · AMZT_ORDER · AMAZON 블록)이 쓰는 브랜드 이름 — 트래커 시절 이름으로 맞춰야 선이 이어진다.
# 대소문자만 다른 것(Laneige·LANEIGE · Innisfree·innisfree · Laka·LAKA)은 TRACKER_NAMES 로, 철자가 다른 것만 KEY_ALIAS 로.
TRACKER_NAMES = ["medicube", "LANEIGE", "BIODANCE", "Anua", "Melaxin", "COSRX", "SKIN1004", "Beauty of Joseon", "VT Cosmetics",
                 "Cellimax", "d'Alba", "Abib", "innisfree", "Purito", "TIRTIR", "Coreana", "Aromatica", "rom&nd", "LAKA", "TS"]
KEY_ALIAS = {"VT": "VT Cosmetics", "celimax": "Cellimax"}


def screen_key(name):
    if name in KEY_ALIAS:
        return KEY_ALIAS[name]
    return next((t for t in TRACKER_NAMES if t.lower() == name.lower()), name)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def b36(n):
    s = "0123456789abcdefghijklmnopqrstuvwxyz"
    if n == 0:
        return "0"
    o = ""
    while n:
        n, r = divmod(n, 36)
        o = s[r] + o
    return o


def crc(s):
    return b36(zlib.crc32(s.encode("utf-8")) & 0xFFFFFFFF)


def kst_now():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)


def load_json(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_if_changed(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        if p.read_text(encoding="utf-8") == text:
            return False
    except FileNotFoundError:
        pass
    p.write_text(text, encoding="utf-8", newline="\n")
    return True


def csv_text(header_row, rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header_row)
    w.writerows(rows)
    return buf.getvalue()


def read_csv(p):
    try:
        with p.open(encoding="utf-8", newline="") as f:
            return list(csv.reader(f))
    except FileNotFoundError:
        return []


def master_text(L):
    txt = ('{"v":1,"note":"아마존 7개국 뷰티 Top100 의 한국 브랜드 ASIN 마스터(lists.js) — [asin, 브랜드 번호(subcat/config.json brands), '
           '제목 64자, 처음 본 날]. 번호=위치. 맨 뒤에만 붙인다.","n":%d,"list":[\n' % len(L))
    return txt + ",\n".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in L) + "\n]}\n"


# ───────────────────────── 덤프 읽기 ─────────────────────────

REC = re.compile(r"^(AMZL|K|T|U|END)\|")


def parse(paths):
    """파일들 → 덤프 목록. 덤프 = AMZL 머리줄부터 END 까지(get_page_text 머리 같은 덤프 밖 줄은 버린다)."""
    dumps, cur = [], None
    for p in paths:
        for raw in pathlib.Path(p).read_text(encoding="utf-8").split("\n"):
            line = raw.rstrip("\r")
            if not REC.match(line):
                continue
            if line.startswith("AMZL|"):
                cur = {"file": str(p), "lines": [line], "end": None}
                dumps.append(cur)
            elif cur is None:
                continue
            elif line.startswith("END|"):
                cur["end"] = line
                cur = None
            else:
                cur["lines"].append(line)
    return [read_dump(d) for d in dumps]


def read_dump(d):
    errs, hdr = [], None
    body = d["lines"]
    for l in body:
        b, _, c = l.rpartition("|")
        if not b or crc(b) != c:
            errs.append("CRC 불일치: " + l[:70])
    p = body[0].rpartition("|")[0].split("|")
    try:
        hdr = {"date": p[2], "ts": p[3], "mk": p[4], "status": p[5], "read": int(p[6]), "titled": int(p[7]),
               "maxr": int(p[8]), "cfg_v": p[9], "masterN": int(p[10])}
    except (IndexError, ValueError):
        errs.append("머리줄 형식 오류: " + body[0][:70])
    if not d["end"]:
        errs.append("END 줄이 없다 — 덤프 끝을 빠뜨렸다")
    else:
        e = d["end"].split("|")
        if int(e[1]) != len(body) + 1:
            errs.append(f"줄 수가 다르다 — END 는 {e[1]}줄, 받은 것은 {len(body) + 1}줄")
        elif crc("\n".join(body)) != e[2]:
            errs.append("END 의 전체 CRC 가 다르다")
    K, T, U = None, {}, []
    for l in body[1:]:
        q = l.rpartition("|")[0].split("|")
        try:
            if q[0] == "K":
                K = q[2]
            elif q[0] == "T":
                T[q[1]] = (int(q[2], 36), q[3])
            elif q[0] == "U":
                U.append((q[2], int(q[3]), q[4]))
        except (IndexError, ValueError):
            errs.append("줄 형식 오류: " + l[:70])
    if hdr and hdr["status"] in ("ok", "part") and K is None:
        errs.append("K 줄이 없다")
    return {"file": d["file"], "hdr": hdr, "K": K, "T": T, "U": U, "errs": errs}


def verify(dumps, master_n):
    """(나라별로 고른 덤프, 틀린 점 목록)"""
    errs, best = [], {}
    for d in dumps:
        h = d["hdr"]
        tag = f"{(h or {}).get('mk', '?')} ({pathlib.Path(d['file']).name})"
        if d["errs"]:
            errs += [f"{tag}: {e}" for e in d["errs"]]
            continue
        if h["mk"] not in MK:
            errs.append(f"{tag}: 모르는 나라 {h['mk']}")
            continue
        if h["masterN"] > master_n:
            errs.append(f"{tag}: 덤프는 마스터 {h['masterN']}개를 보고 만들었는데 지금 마스터는 {master_n}개 — 저장소를 최신으로 받고 다시")
            continue
        bad = False
        if d["K"] and d["K"] != "-":
            for t in d["K"].split(","):
                p = t.split(".")
                if len(p) == 2:
                    if int(p[1], 36) >= h["masterN"]:
                        errs.append(f"{tag}: 짧은 번호 {p[1]} 가 마스터({h['masterN']}개) 밖"); bad = True
                elif len(p) == 3:
                    if p[2] not in d["T"]:
                        errs.append(f"{tag}: 새 ASIN {p[2]} 의 T 줄이 없다"); bad = True
                else:
                    errs.append(f"{tag}: 자리 형식 오류 {t}"); bad = True
        if bad:
            continue
        k = (h["date"], h["mk"])
        o = best.get(k)
        if o is None or (RANK.get(h["status"], -1), h["ts"]) > (RANK.get(o["hdr"]["status"], -1), o["hdr"]["ts"]):
            best[k] = d
    # 같은 나라의 다른 덤프가 맞으면 틀린 덤프는 경고로 낮춘다(다시 받은 것으로 갈음)
    fixed = []
    for e in errs:
        mk = e.split(" ", 1)[0]
        if any(k[1] == mk for k in best):
            print("경고(맞는 덤프로 갈음):", e)
        else:
            fixed.append(e)
    return best, fixed


# ───────────────────────── 저장 ─────────────────────────

def store(best, cfg, master):
    L = master["list"]
    idx = {row[0]: k for k, row in enumerate(L)}
    brands = cfg["brands"]
    changed, new_rows, summary = [], [], []
    by_month = {}
    day_rows = []
    unk_add = []
    for (date, mk), d in sorted(best.items()):
        h = d["hdr"]
        pos = []
        if h["status"] in ("ok", "part") and d["K"] and d["K"] != "-":
            for t in d["K"].split(","):
                p = t.split(".")
                r = int(p[0])
                if len(p) == 2:
                    k = int(p[1], 36)
                else:
                    a = p[2]
                    if a in idx:
                        k = idx[a]
                    else:
                        b, title = d["T"][a]
                        L.append([a, b, title, date])
                        k = idx[a] = len(L) - 1
                        new_rows.append(k)
                pos.append((r, k))
        if h["status"] in ("ok", "part"):
            by_month.setdefault(date[:7], {})[(date, mk)] = [[date, mk, r, L[k][0], brands[L[k][1]][0]] for r, k in sorted(pos)]
        day_rows.append([date, mk, h["ts"], h["status"], h["read"], h["titled"], h["maxr"], len(pos)])
        for a, r, t in d["U"]:
            unk_add.append([date, mk, a, r, t])
        summary.append((mk, h, len(pos)))

    if new_rows or not MASTER.exists():
        master["n"] = len(L)
        if write_if_changed(MASTER, master_text(L)):
            changed.append(MASTER)

    for ym, add in by_month.items():
        mp = DATA / f"{ym}.csv"
        old = read_csv(mp)
        keep = [r for r in old[1:] if r and (r[0], r[1]) not in add]
        for rows in add.values():
            keep += rows
        keep.sort(key=lambda r: (r[0], MK.index(r[1]) if r[1] in MK else 99, int(r[2])))
        if write_if_changed(mp, csv_text(["date", "market", "rank", "asin", "brand"], keep)):
            changed.append(mp)

    old = read_csv(DAYS)
    cur = {(r[0], r[1]): r for r in old[1:] if len(r) >= 8}
    for r in day_rows:
        o = cur.get((r[0], r[1]))
        if o and RANK.get(o[3], -1) > RANK.get(r[3], -1):
            continue                                   # 더 좋은 상태가 이미 있다 — 낮추지 않는다
        cur[(r[0], r[1])] = [str(x) for x in r]
    rows = sorted(cur.values(), key=lambda r: (r[0], MK.index(r[1]) if r[1] in MK else 99))
    if write_if_changed(DAYS, csv_text(["date", "market", "ts", "status", "read", "titled", "maxr", "kpos"], rows)):
        changed.append(DAYS)

    if unk_add:
        old = read_csv(UNK)
        have = {(r[1], r[2]) for r in old[1:] if len(r) > 2}
        keep = old[1:] + [u for u in sorted(unk_add, key=lambda u: (u[0], u[1], u[3])) if (u[1], u[2]) not in have]
        if write_if_changed(UNK, csv_text(["date", "market", "asin", "rank", "title"], keep)):
            changed.append(UNK)
    return {"changed": changed, "new": new_rows, "summary": summary}


# ───────────────────────── 블록 ─────────────────────────

def load_days():
    """{(날짜, 나라): {status, maxr, ts}}"""
    out = {}
    for r in read_csv(DAYS)[1:]:
        if len(r) >= 8:
            out[(r[0], r[1])] = {"ts": r[2], "status": r[3], "maxr": int(r[6] or 0), "kpos": int(r[7] or 0)}
    return out


def load_positions():
    """{(날짜, 나라): [(순위, asin, 브랜드)]}"""
    out = {}
    for p in sorted(DATA.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9].csv")):
        for r in read_csv(p)[1:]:
            if len(r) >= 5:
                out.setdefault((r[0], r[1]), []).append((int(r[2]), r[3], r[4]))
    return out


def build_block(cfg):
    """const AMZL — 날짜 × 나라 × 브랜드의 Top100 개수(t100) · Top50 개수(t50) · 최고 순위. app.js amztBuild 가 읽는다.
      days [날짜] · st [날짜마다 나라 7글자: o ok · p part · b block · n norecs · - 시도 안 함] · mx [날짜마다 나라별 끝 순위]
      br [[화면 키, 회사, 상태 L/P/F/N]] · c [[날짜 번호, 나라 번호, 브랜드 번호, t100, t50, 최고 순위]]"""
    dm = load_days()
    pos = load_positions()
    dates = sorted({d for d, _ in dm})[-BLOCK_DAYS:]
    if not dates:
        return None
    comps = cfg.get("companies", {})
    by_name = {b[0]: b for b in cfg["brands"]}
    br, br_i, c = [], {}, []
    st, mx = [], []
    for di, dt in enumerate(dates):
        s, m = "", []
        for mi, mk in enumerate(MK):
            x = dm.get((dt, mk))
            s += {"ok": "o", "part": "p", "block": "b", "norecs": "n"}.get(x["status"], "-") if x else "-"
            m.append(x["maxr"] if x else 0)
            if not x or x["status"] not in ("ok", "part"):
                continue
            agg = {}
            for r, a, b in pos.get((dt, mk), []):
                g = agg.setdefault(b, [0, 0, 999])
                g[0] += 1
                g[1] += r <= 50
                g[2] = min(g[2], r)
            for b, g in sorted(agg.items()):
                if b not in br_i:
                    row = by_name.get(b)
                    co = row[2] if row else ""
                    stt = (row[3] if row else "") or comps.get(co, {}).get("st", "")
                    br_i[b] = len(br)
                    br.append([screen_key(b), co, stt])
                c.append([di, mi, br_i[b], g[0], g[1], g[2]])
        st.append(s)
        mx.append(m)
    last = max((x["ts"] for (d, _), x in dm.items() if d == dates[-1]), default="")
    return {"asOf": f"{dates[-1]} {last}".strip(), "v": 1, "mk": MK, "days": dates, "st": st, "mx": mx, "br": br, "c": c,
            "note": "아마존 7개국 Best Sellers in Beauty Top100 — 아침 예약 작업(크롬 · lists.js). PC 트래커를 대신한다(2026-10-18)."}


def inject_amzl(block):
    html = INDEX.read_text(encoding="utf-8")
    line = "const AMZL = " + json.dumps(block, ensure_ascii=False, separators=(",", ":")) + ";"
    pat = re.compile(r"^const AMZL = .*$", re.M)
    if pat.search(html):
        new = pat.sub(lambda _m: line, html, count=1)
    else:
        mk = re.search(r"^const AMZSUB = .*$", html, re.M) or re.search(r"^const KMJAMZ = .*$", html, re.M)
        if not mk:
            raise SystemExit("삽입 위치(const AMZSUB · KMJAMZ)를 못 찾았다")
        new = html[:mk.end()] + "\n" + line + html[mk.end():]
    if new == html:
        return False
    INDEX.write_text(new, encoding="utf-8", newline="\n")
    return True


def inject_trk():
    """KMJAMZ.trk 다시 만들기 — fetch_kmj.py --trk-only 와 같다(네트워크 없음)."""
    sys.path.insert(0, str(REPO))
    import os
    cwd = os.getcwd()
    os.chdir(REPO)
    try:
        import fetch_kmj
        return fetch_kmj.trk_only()
    finally:
        os.chdir(cwd)


def inject_all(cfg):
    changed = []
    block = build_block(cfg)
    if block and inject_amzl(block):
        changed.append(INDEX)
    if inject_trk() and INDEX not in changed:
        changed.append(INDEX)
    return block, changed


# ───────────────────────── 실행 ─────────────────────────

def seed():
    """미국 세부 카테고리 마스터(같은 브랜드 번호 체계)로 시작한다 — 첫날 T 줄(제목)을 크게 줄인다."""
    if MASTER.exists():
        print("마스터가 이미 있다 — 그대로 둔다:", MASTER.relative_to(REPO))
        return 0
    sub = load_json(SUB_MASTER, {"list": []})["list"]
    L = [[x[0], x[1], x[2], x[3] if len(x) > 3 else ""] for x in sub]
    write_if_changed(MASTER, master_text(L))
    print(f"마스터 시작: 미국 세부 카테고리 마스터에서 {len(L)}개 →", MASTER.relative_to(REPO))
    return 0


def today_status():
    today = kst_now().strftime("%Y-%m-%d")
    dm = load_days()
    have = {mk: dm[(today, mk)]["status"] for mk in MK if (today, mk) in dm}
    miss = [mk for mk in MK if have.get(mk) != "ok"]
    print(f"오늘({today}) " + (" · ".join(f"{mk} {have.get(mk, '없음')}" for mk in MK)))
    return 0 if not miss else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--inject", action="store_true")
    ap.add_argument("--today", action="store_true")
    ap.add_argument("--seed", action="store_true")
    ap.add_argument("--no-inject", action="store_true")
    a = ap.parse_args()
    if a.today:
        return today_status()
    if a.seed:
        return seed()
    cfg = load_json(CFG, None)
    if a.inject and not a.files:
        block, changed = inject_all(cfg)
        print("블록 재주입:", "바뀜" if changed else "변화 없음")
        return 0
    if not a.files:
        ap.error("덤프 파일을 주거나 --inject")
    master = load_json(MASTER, {"v": 1, "list": []})
    dumps = parse(a.files)
    if not dumps:
        print("덤프(AMZL 머리줄)가 하나도 없다")
        return 2
    best, errs = verify(dumps, len(master["list"]))
    if errs:
        print("검증 실패 — 아무것도 쓰지 않았다")
        for e in errs[:40]:
            print("  ", e)
        bad = sorted({e.split(" ", 1)[0] for e in errs})
        print("  → 그 나라 탭(robots.txt)에서 lists.js 를 다시 불러 window.__AMZL.again() → get_page_text → 새 파일로 같이 넘길 것:", ", ".join(bad))
        return 2
    print("검증 통과 · " + " · ".join(f"{mk} {d['hdr']['status']}" for (_, mk), d in sorted(best.items(), key=lambda x: MK.index(x[0][1]))))
    if a.check:
        return 0
    res = store(best, cfg, master)
    changed = res["changed"]
    if not a.no_inject:
        block, ch = inject_all(cfg)
        changed += [p for p in ch if p not in changed]
    for mk, h, n in sorted(res["summary"], key=lambda x: MK.index(x[0])):
        print(f"[AMZL] {h['date']} {h['ts']} {mk} {h['status']} · 읽은 자리 {h['read']} · 제목 {h['titled']} · 끝 {h['maxr']}위 · 한국 자리 {n}")
    print(f"  마스터 +{len(res['new'])} (지금 {len(master['list'])}개)")
    print("  바뀐 파일:", ", ".join(str(p.relative_to(REPO)) for p in changed) or "(없음)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
