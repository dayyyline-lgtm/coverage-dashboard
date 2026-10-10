# -*- coding: utf-8 -*-
"""아마존 US 뷰티 세부 카테고리 Top100 덤프(AMZSUB) → 데이터 파일 + public/index.html 의 `const AMZSUB` 한 줄.

  python ingest.py 덤프.txt [덤프2.txt …]       검증 → 저장 → 블록 주입 (덩어리 파일은 순서대로 주면 된다)
  python ingest.py --check 덤프.txt …           검증만 — 틀린 줄을 알려 준다(브라우저에서 __AMZSUB.line(n) 으로 다시 받는다)
  python ingest.py --inject                     저장된 데이터로 블록만 다시 만든다(push 거절 뒤 재주입용)
  python ingest.py 덤프.txt --names 이름.txt     비어 있는 카테고리 이름 채우기(줄마다 '번호|이름')

덤프 형식은 collector.js 맨 위 주석에 있다. 여기서 하는 일:
  1. 줄마다 CRC · 성공 카테고리 수 · 새 ASIN 의 제목 줄을 확인한다. 하나라도 어긋나면 아무것도 안 쓰고 종료코드 2.
  2. data/subcat/skus.json   — 한국 브랜드 ASIN 마스터 [asin, 브랜드 번호, 제목, 처음 본 날].
                               **맨 뒤에만 붙인다** — 번호(=위치)가 다음 덤프의 짧은 번호다. 순서를 바꾸면 과거 덤프가 틀어진다.
  3. data/subcat/YYYY-MM.csv — 그날 한국 브랜드 자리(date,cat,rank,asin,brand). 같은 날 다시 넣으면 그날 행을 갈아 끼운다.
  4. data/subcat/days.csv    — 회차 요약(성공 카테고리 · 자리 수 · 부분 여부).
  5. data/subcat/unknown.csv — 사전에 없는데 제목에 Korean·K-beauty 가 들어간 상품(새 브랜드 후보). ASIN 당 한 줄.
  6. config.json             — 비어 있는 카테고리 이름만 채운다(구분용으로 고쳐 둔 이름은 안 건드린다).
  7. data/subcat/prices.csv  — 한국 SKU 카드 가격(asin,date,price USD). 값이 바뀐 날만 적는다(2026-10-11 ~ · 덤프의 P 줄).
  8. public/index.html       — `const AMZSUB = …;` 한 줄만 교체(없으면 KMJAMZ 줄 뒤에 넣는다). 바뀐 게 없으면 안 쓴다.
     추정 매출(model.py — 세부 순위 → 전체 순위 → 월 판매량 → × 가격)은 블록을 만들 때마다 트래커 history.csv 로 다시 보정한다.

부분 회차: 성공 카테고리가 97% 밑이면 그날은 part=1 — 화면이 완전한 날과 같은 선에 잇지 않는다.
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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import model  # noqa: E402  (같은 폴더 — 추정 매출)

HERE = pathlib.Path(__file__).resolve().parent          # amazon-beauty-tracker/subcat
TRACKER = HERE.parent
REPO = TRACKER.parent
DATA = TRACKER / "data" / "subcat"
CFG = HERE / "config.json"
MASTER = DATA / "skus.json"
DAYS = DATA / "days.csv"
UNK = DATA / "unknown.csv"
PRICES = DATA / "prices.csv"
INDEX = REPO / "public" / "index.html"

PART_CUT = 0.97     # 성공 카테고리 비율이 이 밑이면 부분 회차
SKU_H = 30          # 블록의 SKU 별 일별 최고순위 이력 — 최근 30회차(긴 이력은 월별 CSV 에 다 있다)
CO_DAYS = 120       # 블록의 회사별 일별 집계 — 최근 120회차
TITLE_N = 56        # 블록에 싣는 제목 길이(마스터는 64자 그대로)
SHOW_ST = ("L", "P")  # 블록에 SKU·회사 줄을 싣는 상태 — 상장(L) · 상장 준비(P)

# 블록 모양 (app.js renderAmzSub 가 읽는다 — 바꾸면 거기도 같이)
#   asOf 마지막 회차가 끝난 시각(KST) · latest 그 날짜 · date 기준 회차(마지막 완전한 회차 — 표·카드·SKU 의 r 이 이 날) · days/ok/tot/part 회차별(최근 CO_DAYS)
#   cats [[cat_id, 이름]] (번호 = 카테고리 번호) · bl [브랜드 이름] (SKU 의 브랜드 번호)
#   cos [{n 회사, st L/P, chk 확인 필요, memo, br [[브랜드, 마지막 회차 SKU 수]], s SKU 수, a 노출 자리, t Top10 자리, q Top30 자리, w 1위 자리,
#         b 뷰티 전체 Top100 안 SKU, o 뷰티 전체 최고 순위(0 = 밖)}]  ← 배열은 days 와 같은 길이
#   k {s,a,t,q,w,b,r} 한국 브랜드 전체 · hd SKU 이력의 날짜(최근 SKU_H)
#   skus [[asin, 브랜드 번호, 회사 번호(cos), 제목, 처음 본 회차(days 번호 · -1 = 창 밖), [[카테고리 번호, 순위]](마지막 회차), h]]
#        h = hd 날마다 최고 순위를 36진수 두 자리로 이은 문자열('00' = 그날 없음) — 배열보다 1/3 작다
#   unk [[asin, 카테고리 번호, 순위, 제목]] 마지막 회차의 새 브랜드 후보
#   추정 매출(2026-10-11 · model.py): cos[].r · k.r = 회차별 하루 추정 매출(USD 정수, 부분 회차는 null)
#        skus[i][7..10] = 기준 회차의 가격(센트) · 추정 월 판매량 · 하루 추정 매출(USD) · 가격 출처(c 카드 · t 트래커 · m 카테고리 중앙값 · g 전체 중앙값)
#        rm = 보정 요약 {a,b1,b2 판매량 곡선 · nu 배지 수 · beta · direct/linked/ncat 카테고리 · npairs · val 맞춤 · px 가격 출처 수 · gmed}

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


def unfw(s):
    """collector 가 '&' 를 전각으로 바꿔 내보낸다(크롬 도구가 '&' 를 쿼리 문자열로 보고 가린다)."""
    return s.replace("＆", "&")


# ───────────────────────── 덤프 읽기 ─────────────────────────

def read_lines(paths):
    out = []
    for p in paths:
        for raw in pathlib.Path(p).read_text(encoding="utf-8").split("\n"):
            line = raw.rstrip("\r")
            if line.strip():
                out.append(line)          # 줄 끝 공백은 그대로 — 제목이 64자에서 잘리며 공백으로 끝나는 일이 많다
    return out


REC = re.compile(r"^(AMZSUB|C|F|N|T|U|P|END)\|")


def _key(l):
    p = l.split("|")
    if p[0] in ("AMZSUB", "END"):
        return p[0]
    return p[0] + "|" + (p[1] if len(p) > 1 else "")


def _valid(l):
    if l.startswith(("AMZSUB|", "END|", "F|")):
        return True
    body, _, c = l.rpartition("|")
    return bool(body) and crc(body) == c


def parse_dump(paths):
    """덩어리 파일들을 순서대로 읽는다. 같은 줄이 두 번이면 한 번만, 틀린 줄은 같은 키(C|번호 · T|ASIN …)의 맞는 줄이
    다른 파일(다시 받은 redo 덩어리)에 있으면 그 자리에 갈아 끼운다 — 그래서 고칠 땐 틀린 줄만 다시 받아 파일을 하나 더 주면 된다."""
    lines = read_lines(paths)
    ent = []
    for l in lines:
        if not REC.match(l):               # get_page_text 머리(Title:·URL:·Source element:·---) 같은 덤프 밖 줄은 버린다
            continue
        ent.append((_key(l), l, _valid(l)))
    good = {}
    for k, l, v in ent:
        if v and k not in good:
            good[k] = l
    d = {"hdr": None, "C": {}, "F": {}, "N": {}, "T": {}, "U": {}, "P": {}, "bad": [], "warn": [], "end": None, "lines": lines}
    emitted = set()
    body_lines = []
    for k, l, v in ent:
        if k in emitted:
            if v and l != good.get(k):
                d["warn"].append(f"같은 키에 다른 내용의 줄이 둘 — 앞의 것을 쓴다: {k}")
            continue
        if not v:
            if k in good:
                l = good[k]
            else:
                d["bad"].append(k)
                emitted.add(k)
                continue
        emitted.add(k)
        if k == "END":
            d["end"] = l
            continue
        body_lines.append(l)
        if k == "AMZSUB":
            d["hdr"] = l
            continue
        if l.startswith("F|"):
            p = l.split("|")
            d["F"][int(p[1])] = p[2] if len(p) > 2 else ""
            continue
        p = l.rpartition("|")[0].split("|")
        try:
            if p[0] == "C":
                d["C"][int(p[1])] = (int(p[2]), int(p[3]), p[4])
            elif p[0] == "N":
                d["N"][int(p[1])] = unfw(p[2])
            elif p[0] == "T":
                d["T"][p[1]] = (int(p[2], 36), p[3])
            elif p[0] == "U":
                d["U"][p[1]] = (int(p[2]), int(p[3]), p[4])
            elif p[0] == "P":
                d["P"][int(p[1])] = p[2]
        except (ValueError, IndexError):
            d["bad"].append(k)
    d["body_lines"] = body_lines
    return d


def header(d):
    p = d["hdr"].split("|")
    return {"ver": int(p[1]), "date": p[2], "ts": p[3], "ok": int(p[4]), "total": int(p[5]), "items": int(p[6]),
            "notitle": int(p[7]), "src": p[8], "cfg_v": p[9], "masterN": int(p[10])}


def verify(d, master_n):
    """틀린 점 목록(비면 통과)."""
    errs = []
    if not d["hdr"]:
        return ["머리줄(AMZSUB|…)이 없다 — 첫 덩어리(0번 줄부터)를 빠뜨렸다"]
    h = header(d)
    if d["bad"]:
        keys = [k + "|" for k in d["bad"]]
        errs.append(f"CRC 불일치 {len(keys)}줄: {', '.join(d['bad'][:30])}")
        errs.append("  → 브라우저에서 window.__AMZSUB.redo('" + ",".join(keys[:40]) + "') → get_page_text → 새 파일로 저장해 같이 넘길 것")
    if len(d["C"]) != h["ok"]:
        miss = [i for i in range(h["total"]) if i not in d["C"] and i not in d["F"]]
        errs.append(f"C 줄 {len(d['C'])}개 · 머리줄은 성공 {h['ok']}개 — 빠진 카테고리 번호 {miss[:20]}")
    if h["masterN"] > master_n:
        errs.append(f"덤프는 마스터 {h['masterN']}개를 보고 만들었는데 지금 마스터는 {master_n}개 — 저장소를 최신으로 받고 다시")
    for ci, (_, _, tok) in d["C"].items():
        if tok == "-":
            continue
        for t in tok.split(","):
            p = t.split(".")
            if len(p) == 2:
                if int(p[1], 36) >= h["masterN"]:
                    errs.append(f"C {ci}: 짧은 번호 {p[1]} 가 마스터({h['masterN']}개) 밖")
            elif len(p) == 3:
                if p[2] not in d["T"]:
                    errs.append(f"C {ci}: 새 ASIN {p[2]} 의 T 줄이 없다")
            else:
                errs.append(f"C {ci}: 자리 형식 오류 {t}")
    for pk, tok in d["P"].items():
        for t in tok.split(","):
            a, _, c = t.rpartition(".")
            try:
                int(c, 36)
                if len(a) < 10 and int(a, 36) >= h["masterN"]:
                    errs.append(f"P {pk}: 짧은 번호 {a} 가 마스터({h['masterN']}개) 밖")
            except ValueError:
                errs.append(f"P {pk}: 가격 형식 오류 {t}")
    # END — 줄 수와 전체 CRC. 덩어리를 순서대로 줬다면 맞는다(아니면 경고만: 줄마다 CRC 가 이미 맞았다).
    if d["end"]:
        p = d["end"].split("|")
        if int(p[1]) != len(d["body_lines"]) + 1:
            errs.append(f"줄 수가 다르다 — END 는 {p[1]}줄, 받은 것은 {len(d['body_lines']) + 1}줄 (빠진 줄이 있다)")
        elif crc("\n".join(d["body_lines"])) != p[2]:
            d["warn"].append("END 의 전체 CRC 가 다르다 — 덩어리 순서가 바뀌었거나 머리줄이 다른 호출의 것(줄마다 CRC 는 통과)")
    else:
        d["warn"].append("END 줄이 없다 — 마지막 덩어리를 빠뜨렸을 수 있다")
    return errs


# ───────────────────────── 저장 ─────────────────────────

def load_json(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def dump_config(cfg):
    """사람이 브랜드를 맨 뒤에 덧붙이기 쉽게 항목마다 한 줄."""
    j = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
    out = ["{"]
    keys = list(cfg.keys())
    for n, k in enumerate(keys):
        v = cfg[k]
        tail = "," if n < len(keys) - 1 else ""
        if k in ("cats", "brands") and isinstance(v, list):
            out.append(f"{j(k)}:[")
            out += [j(x) + ("," if i < len(v) - 1 else "") for i, x in enumerate(v)]
            out.append("]" + tail)
        elif k == "companies" and isinstance(v, dict):
            out.append(f"{j(k)}:{{")
            items = list(v.items())
            out += [f"{j(a)}:{j(b)}" + ("," if i < len(items) - 1 else "") for i, (a, b) in enumerate(items)]
            out.append("}" + tail)
        else:
            out.append(f"{j(k)}:{j(v)}{tail}")
    out.append("}")
    return "\n".join(out) + "\n"


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


def store(d, cfg, master, names_file=None):
    h = header(d)
    date = h["date"]
    L = master["list"]
    idx = {row[0]: k for k, row in enumerate(L)}
    brands = cfg["brands"]
    cats = cfg["cats"]
    new_rows = []                                   # 이번에 마스터에 붙인 것
    rows = []                                       # (cat 번호, 순위, 마스터 번호)
    for ci in sorted(d["C"]):
        tok = d["C"][ci][2]
        if tok == "-":
            continue
        for t in tok.split(","):
            p = t.split(".")
            r = int(p[0])
            if len(p) == 2:
                k = int(p[1], 36)
            else:
                b, a = int(p[1], 36), p[2]
                if a in idx:
                    k = idx[a]
                else:
                    L.append([a, b, d["T"][a][1], date])
                    k = idx[a] = len(L) - 1
                    new_rows.append(k)
            rows.append((ci, r, k))

    changed = []
    if new_rows or not MASTER.exists():
        master["n"] = len(L)
        txt = '{"v":1,"note":"한국 브랜드 ASIN 마스터 — [asin, 브랜드 번호(config.brands), 제목 64자, 처음 본 날]. 번호=위치. 맨 뒤에만 붙인다.","n":%d,"list":[\n' % len(L)
        txt += ",\n".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in L) + "\n]}\n"
        if write_if_changed(MASTER, txt):
            changed.append(MASTER)

    # 월별 CSV — 그날 행을 갈아 끼운다
    mp = DATA / f"{date[:7]}.csv"
    old = read_csv(mp)
    keep = [r for r in old[1:] if r and r[0] != date]
    add = [[date, cats[ci][0], r, L[k][0], brands[L[k][1]][0]] for ci, r, k in sorted(rows, key=lambda x: (x[0], x[1]))]
    keep += add
    keep.sort(key=lambda r: (r[0], int(_cat_order(cats).get(r[1], 9999)), int(r[2])))
    if write_if_changed(mp, csv_text(["date", "cat", "rank", "asin", "brand"], keep)):
        changed.append(mp)

    # 회차 요약
    part = 1 if h["total"] and h["ok"] / h["total"] < PART_CUT else 0
    old = read_csv(DAYS)
    keep = [r for r in old[1:] if r and r[0] != date]
    keep.append([date, h["ts"].replace("T", " ")[:16], h["ok"], h["total"], h["items"], len(rows), h["notitle"],
                 len(d["F"]), part, h["cfg_v"], len(new_rows)])
    keep.sort(key=lambda r: r[0])
    if write_if_changed(DAYS, csv_text(["date", "ts", "cats_ok", "cats_total", "items", "kpos", "notitle", "fails",
                                        "partial", "cfg_v", "new_skus"], keep)):
        changed.append(DAYS)

    # 새 브랜드 후보 — ASIN 당 처음 본 날 한 줄
    if d["U"]:
        old = read_csv(UNK)
        have = {r[1] for r in old[1:] if len(r) > 1}
        keep = old[1:] + [[date, a, cats[u[0]][0], u[1], u[2]] for a, u in sorted(d["U"].items(), key=lambda x: x[1][1]) if a not in have]
        if write_if_changed(UNK, csv_text(["date", "asin", "cat", "rank", "title"], keep)):
            changed.append(UNK)

    # 카테고리 이름 — 비어 있는 것만
    names = dict(d["N"])
    if names_file:
        for line in pathlib.Path(names_file).read_text(encoding="utf-8").splitlines():
            if "|" in line:
                i, n = line.split("|", 1)
                names[int(i)] = unfw(n.strip())
    cfg_changed = False
    for i, n in names.items():
        if 0 <= i < len(cats) and not cats[i][1] and n and n != "Amazon Best Sellers":
            cats[i][1] = n
            cfg_changed = True
    if cfg_changed and write_if_changed(CFG, dump_config(cfg)):
        changed.append(CFG)

    if store_prices(d, date, L):
        changed.append(PRICES)

    return {"date": date, "rows": rows, "new": new_rows, "part": part, "changed": changed, "h": h}


def store_prices(d, date, L):
    """P 줄 → prices.csv (asin,date,price). 직전에 적힌 값과 달라진 ASIN 만 그날 날짜로 적는다(같은 날 다시 넣으면 그날 줄을 갈아 끼운다)."""
    if not d["P"]:
        return False
    got = {}
    for tok in d["P"].values():
        for t in tok.split(","):
            a, _, c = t.rpartition(".")
            asin = a if len(a) >= 10 else L[int(a, 36)][0]
            got[asin] = int(c, 36) / 100.0
    old = read_csv(PRICES)[1:]
    keep = [r for r in old if len(r) >= 3 and r[1] != date]
    last = {}
    for r in sorted(keep, key=lambda r: r[1]):
        if r[1] < date:
            last[r[0]] = float(r[2])
    add = [[a, date, f"{p:.2f}"] for a, p in sorted(got.items()) if a not in last or abs(last[a] - p) > 0.004]
    rows = sorted(keep + add, key=lambda r: (r[0], r[1]))
    return write_if_changed(PRICES, csv_text(["asin", "date", "price"], rows))


def load_prices():
    """{asin: [(date, usd)]} 날짜순"""
    out = {}
    for r in read_csv(PRICES)[1:]:
        if len(r) >= 3:
            try:
                out.setdefault(r[0], []).append((r[1], float(r[2])))
            except ValueError:
                pass
    for v in out.values():
        v.sort()
    return out


_CO = {}


def _cat_order(cats):
    key = id(cats)
    if key not in _CO:
        _CO[key] = {c[0]: i for i, c in enumerate(cats)}
    return _CO[key]


# ───────────────────────── 블록 ─────────────────────────

def history():
    """{날짜: [(cat_id, rank, asin), …]} — 월별 CSV 전부."""
    out = {}
    for p in sorted(DATA.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9].csv")):
        for r in read_csv(p)[1:]:
            if len(r) >= 4:
                out.setdefault(r[0], []).append((r[1], int(r[2]), r[3]))
    return out


def build_block(cfg, master):
    hist = history()
    dmeta = {r[0]: r for r in read_csv(DAYS)[1:] if r}
    dates = sorted(hist)[-CO_DAYS:]
    if not dates:
        return None
    cats = cfg["cats"]
    corder = _cat_order(cats)
    brands = cfg["brands"]
    comps = cfg.get("companies", {})
    m = {row[0]: row for row in master["list"]}

    def co_of(asin):
        row = m.get(asin)
        if not row:
            return None, None, None
        b = brands[row[1]]
        st = b[3] or comps.get(b[2], {}).get("st", "")
        return b[0], b[2], st

    # 추정 매출 — 날마다 다시 보정한다(트래커 자료가 쌓이면 곡선이 조금씩 움직인다 · 지난 날도 같은 곡선으로 다시 계산)
    try:
        est, rmeta = model.estimate(cats, hist, model.load_tracker(TRACKER / "data" / "history.csv", dates[-1]), load_prices(), dates[-1])
    except Exception as e:                     # 매출 추정이 깨져도 순위 블록은 그대로 낸다
        print("경고: 추정 매출 계산 실패 —", repr(e)[:200])
        est, rmeta = {}, None

    # 회사 목록 — 상장(L)·상장 준비(P)
    names = []
    for b in brands:
        st = b[3] or comps.get(b[2], {}).get("st", "")
        if st in SHOW_ST and b[2] and b[2] not in names:
            names.append(b[2])
    ser = {n: {"s": [], "a": [], "t": [], "q": [], "w": [], "b": [], "o": [], "r": []} for n in names}
    ksr = {"s": [], "a": [], "t": [], "q": [], "w": [], "b": [], "r": []}
    ok, tot, part, kpos = [], [], [], []
    for dt in dates:
        mt = dmeta.get(dt)
        ok.append(int(mt[2]) if mt else 0)
        tot.append(int(mt[3]) if mt else 0)
        part.append(int(mt[8]) if mt else 0)
        agg = {n: [set(), 0, 0, 0, set(), 0, 0] for n in names}
        kk = [set(), 0, 0, 0, set(), 0, 0]
        for cat, r, a in hist[dt]:
            br, co, st = co_of(a)
            if br is None:
                continue
            kk[0].add(a); kk[1] += 1; kk[2] += r <= 10; kk[3] += r == 1; kk[6] += r <= 30
            if cat == "beauty":
                kk[4].add(a)
            if co in agg:
                g = agg[co]
                g[0].add(a); g[1] += 1; g[2] += r <= 10; g[3] += r == 1; g[6] += r <= 30
                if cat == "beauty":
                    g[4].add(a)
                    g[5] = r if not g[5] else min(g[5], r)
        for n in names:
            g = agg[n]
            for key, v in zip("satwboq", (len(g[0]), g[1], g[2], g[3], len(g[4]), g[5], g[6])):
                ser[n][key].append(v)
        for key, v in zip("satwbq", (len(kk[0]), kk[1], kk[2], kk[3], len(kk[4]), kk[6])):
            ksr[key].append(v)
        # 하루 추정 매출(USD) — 부분 회차는 null(자리가 빠져 매출도 빠진다 — 선·누적은 완전한 날로만)
        ed = est.get(dt)
        rv = {n: 0.0 for n in names}
        kr = 0.0
        if ed and not part[-1]:
            for a, x in ed.items():
                br, co, st = co_of(a)
                if br is None:
                    continue
                kr += x[2]
                if co in rv:
                    rv[co] += x[2]
        for n in names:
            ser[n]["r"].append(round(rv[n]) if ed and not part[-1] else None)
        ksr["r"].append(round(kr) if ed and not part[-1] else None)

    # 기준 회차 = 마지막 '완전한' 회차(부분 회차의 숫자를 표·카드에 쓰면 가짜 하락이 된다). 완전한 회차가 없으면 마지막 회차.
    full = [dt for i, dt in enumerate(dates) if not part[i]]
    last = full[-1] if full else dates[-1]
    # 회사 줄 — 기준 회차 노출 수 순
    br_last = {}
    for cat, r, a in hist[last]:
        br, co, st = co_of(a)
        if co in ser:
            br_last.setdefault(co, {}).setdefault(br, set()).add(a)
    cos = []
    for n in names:
        s = ser[n]
        if not any(s["a"]):
            continue
        meta = comps.get(n, {})
        cos.append({"n": n, "st": meta.get("st", ""), "chk": meta.get("chk", 0), "memo": meta.get("memo", ""),
                    "br": sorted(([b, len(v)] for b, v in br_last.get(n, {}).items()), key=lambda x: -x[1]), **s})
    li = dates.index(last)
    cos.sort(key=lambda c: (-c["a"][li], -c["s"][li], c["n"]))
    co_i = {c["n"]: i for i, c in enumerate(cos)}

    # SKU 줄 — 최근 SKU_H 회차에 한 번이라도 나온 상장·상장 준비 브랜드 SKU
    hd = dates[-SKU_H:]
    day_i = {dt: i for i, dt in enumerate(dates)}
    best = {}                                   # asin → {날짜: 최고 순위}
    pos_last = {}                               # asin → [[cat 번호, 순위], …]
    for dt in hd:
        for cat, r, a in hist[dt]:
            br, co, st = co_of(a)
            if st not in SHOW_ST or co not in co_i:
                continue
            bd = best.setdefault(a, {})
            bd[dt] = min(bd.get(dt, 999), r)
            if dt == last:
                pos_last.setdefault(a, []).append([corder.get(cat, -1), r])
    bl, bl_i = [], {}
    skus = []
    for a, bd in best.items():
        row = m[a]
        br, co, st = co_of(a)
        if br not in bl_i:
            bl_i[br] = len(bl)
            bl.append(br)
        r = sorted(pos_last.get(a, []), key=lambda x: x[1])
        first = row[3] if len(row) > 3 else ""
        h = "".join(b36(bd[dt]).rjust(2, "0") if dt in bd else "00" for dt in hd)
        x = est.get(last, {}).get(a)
        ex = [round(x[1] * 100), round(x[0]), round(x[2]), x[3]] if x else [0, 0, 0, ""]
        skus.append([a, bl_i[br], co_i[co], row[2][:TITLE_N].rstrip(), day_i.get(first, -1), r, h] + ex)
    skus.sort(key=lambda s: (s[5][0][1] if s[5] else 999, -len(s[5]), s[0]))

    mt = dmeta.get(dates[-1])                   # asOf 는 마지막 회차(부분이어도) — 신선도 판정은 '돌았는가'를 본다
    unk = []
    for r in read_csv(UNK)[1:]:
        if len(r) >= 5 and r[0] == dates[-1]:
            unk.append([r[1], corder.get(r[2], -1), int(r[3]), r[4]])
    unk.sort(key=lambda x: x[2])
    return {
        "asOf": (mt[1] if mt else dates[-1]), "v": 1, "date": last, "latest": dates[-1],
        "days": dates, "ok": ok, "tot": tot, "part": part,
        "cats": [[c[0], c[1]] for c in cats], "bl": bl,
        "cos": cos, "k": ksr, "hd": hd, "skus": skus, "unk": unk[:30],
        **({"rm": rmeta} if rmeta else {}),
    }


def inject(block):
    html = INDEX.read_text(encoding="utf-8")
    line = "const AMZSUB = " + json.dumps(block, ensure_ascii=False, separators=(",", ":")) + ";"
    pat = re.compile(r"^const AMZSUB = .*$", re.M)
    if pat.search(html):
        new = pat.sub(lambda _m: line, html, count=1)
    else:
        mk = re.search(r"^const KMJAMZ = .*$", html, re.M)
        if mk:
            new = html[:mk.end()] + "\n" + line + html[mk.end():]
        else:
            at = html.index("const LIVE = ")
            new = html[:at] + line + "\n" + html[at:]
    if new == html:
        return False
    INDEX.write_text(new, encoding="utf-8", newline="\n")
    return True


# ───────────────────────── 실행 ─────────────────────────

def summary(res, cfg, master, block):
    h = res["h"]
    brands = cfg["brands"]
    comps = cfg.get("companies", {})
    L = master["list"]
    print(f"[AMZSUB] {h['date']} {h['ts'][11:16]} · 카테고리 {h['ok']}/{h['total']}"
          f"{' (부분)' if res['part'] else ''} · 읽은 자리 {h['items']} · 제목 없음 {h['notitle']} · 한국 자리 {len(res['rows'])}")
    listed_new = []
    for k in res["new"]:
        b = brands[L[k][1]]
        st = b[3] or comps.get(b[2], {}).get("st", "")
        if st in SHOW_ST:
            listed_new.append(f"{b[2]} · {b[0]} · {L[k][0]} · {L[k][2][:50]}")
    print(f"  마스터 +{len(res['new'])} (상장·상장준비 브랜드 +{len(listed_new)})")
    if master["list"] and len(res["new"]) < len(master["list"]):      # 첫날은 전부 새것이라 목록을 생략
        for s in listed_new[:30]:
            print("   NEW", s)
    if block:
        top = ", ".join(f"{c['n']} {c['s'][-1]}개/{c['a'][-1]}자리" for c in block["cos"][:6])
        print(f"  상장사 상위: {top}")
        li = block["days"].index(block["date"])
        rv = sorted(((c["r"][li] or 0, c["n"]) for c in block["cos"] if c.get("r")), reverse=True)
        if rv and rv[0][0]:
            kr = block["k"]["r"][li] or 0
            print(f"  추정 매출(하루, {block['date']}): 한국 전체 ${kr / 1e6:.2f}M · " + ", ".join(f"{n} ${v / 1e6:.2f}M" for v, n in rv[:5]))
        if block["unk"]:
            print(f"  새 브랜드 후보 {len(block['unk'])}개 (unknown.csv)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--inject", action="store_true")
    ap.add_argument("--names")
    ap.add_argument("--no-inject", action="store_true")
    ap.add_argument("--today", action="store_true", help="오늘(KST) 완전한 회차가 이미 있으면 종료코드 0, 없으면 1")
    a = ap.parse_args()

    if a.today:
        today = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)).strftime("%Y-%m-%d")
        row = next((r for r in read_csv(DAYS)[1:] if r and r[0] == today), None)
        if row and row[8] == "0":
            print(f"오늘({today}) 완전한 회차 있음 — {row[1]} · 카테고리 {row[2]}/{row[3]}")
            return 0
        print(f"오늘({today}) " + ("부분 회차만 있음" if row else "회차 없음"))
        return 1

    cfg = load_json(CFG, None)
    master = load_json(MASTER, {"v": 1, "list": []})

    if a.inject and not a.files:
        block = build_block(cfg, master)
        print("블록 재주입:", "바뀜" if block and inject(block) else "변화 없음")
        return 0
    if not a.files:
        ap.error("덤프 파일을 주거나 --inject")

    d = parse_dump(a.files)
    errs = verify(d, len(master["list"]))
    for w in d["warn"]:
        print("경고:", w)
    if errs:
        print("검증 실패 — 아무것도 쓰지 않았다")
        for e in errs[:60]:
            print("  ", e)
        return 2
    h = header(d)
    print(f"검증 통과 · {h['date']} · C {len(d['C'])} · T {len(d['T'])} · F {len(d['F'])} · U {len(d['U'])}")
    if a.check:
        return 0

    res = store(d, cfg, master, a.names)
    block = build_block(cfg, master)
    if block and not a.no_inject and inject(block):
        res["changed"].append(INDEX)
    summary(res, cfg, master, block)
    print("  바뀐 파일:", ", ".join(str(p.relative_to(REPO)) for p in res["changed"]) or "(없음)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
