"""호텔 ADR 추적 -> public/index.html 의  const ADR = {...};   (2026-10-29)

재료(hotel_adr/data/, 전부 손으로 넣거나 수집기가 쌓는다):
  reit_monthly.json  리츠 IR 차트·표 — 호텔 4곳 월별 ADR(천원)·OCC(%) (그랜드 머큐어 용산 · 나인트리 동대문 · 신라스테이 광화문 · 마포)
  ir_quarterly.json  회사 IR 분기 — 신라 사업장별 매출·투숙률(2011~) · GS피앤엘 사업장별 매출·OCC(2025~) · 서부T&D 객실·식음 매출
  broker.json        증권사 ADR·OCC 언급(원문 표현)
  market.json        시장 참고값(한국호텔업협회 연간 · STR 월 · 문체부)
  ota.csv            Google 호텔 최저가 관측(관측일 × 호텔 × 숙박일) — hotel_adr/ota.js(크롬)가 쌓는다
  kayak.csv          KAYAK 호텔 월별 평균 요금(수집일 × 호텔 · 달러 12달 + 요일 7개) — hotel_adr/kayak.js(크롬)가 주 1회 쌓는다

쓰는 법(아침 수집 절차는 hotel_adr/RUNBOOK.md):
  python3 hotel_adr/build.py                 블록만 다시 만든다(데이터가 같으면 파일을 안 건드린다)
  python3 hotel_adr/build.py --today         종료코드 0 = 오늘 관측이 이미 있다(아침 수집 건너뛰기)
  python3 hotel_adr/build.py --ota dump.txt  수집기 덤프(O| 줄)를 ota.csv 에 더한 뒤 블록을 만든다
  python3 hotel_adr/build.py --check dump.txt  덤프만 검사(줄 수 · 상태)
  python3 hotel_adr/build.py --kayak-done    종료코드 0 = 이번 달 KAYAK 수집이 6일 안쪽에 있다(건너뛰기)
  python3 hotel_adr/build.py --kayak-check dump.txt  KAYAK 덤프(K| 줄) 검사 — 줄마다 CRC · END 줄 수
  python3 hotel_adr/build.py --kayak dump.txt        KAYAK 덤프를 kayak.csv 에 더한 뒤 블록을 만든다
  python3 hotel_adr/push.py                  hotel_adr/data · index.html 만 커밋해 올린다(배포 생략 표시)

화면: app.js renderAdr — 호텔신라 · GS피앤엘 · 서부T&D 종목 페이지 손익 탭 '호텔 ADR 추적'.
"""
import calendar, csv, io, json, os, re, sys
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "hotel_adr", "data")
HTML = os.path.join(ROOT, "public", "index.html")
KST = timezone(timedelta(hours=9))
VAT = 1.1

HOTELS = {   # 키: [표시 이름, 회사, 등급, 지역]
    "gic": ["그랜드 인터컨티넨탈 파르나스", "GS피앤엘", 5, "서울 삼성"],
    "westin": ["웨스틴 서울 파르나스", "GS피앤엘", 5, "서울 삼성"],
    "pjeju": ["파르나스 호텔 제주", "GS피앤엘", 5, "제주"],
    "nt_md2": ["나인트리 명동II", "GS피앤엘", 4, "서울 명동"],
    "nt_ddm": ["나인트리 동대문", "GS피앤엘", 4, "서울 동대문"],
    "gm_ys": ["그랜드 머큐어 용산", "서부T&D", 5, "서울 용산"],
    "ns_ys": ["노보텔 스위트 용산", "서부T&D", 5, "서울 용산"],
    "nv_ys": ["노보텔 용산", "서부T&D", 5, "서울 용산"],
    "is_ys": ["이비스 스타일 용산", "서부T&D", 4, "서울 용산"],
    "shilla_seoul": ["서울신라호텔", "호텔신라", 5, "서울 장충"],
    "shilla_jeju": ["제주신라호텔", "호텔신라", 5, "제주"],
    "stay_ghm": ["신라스테이 광화문", "호텔신라", 4, "서울 광화문"],
    "stay_mapo": ["신라스테이 마포", "호텔신라", 4, "서울 마포"],
}
# 드래곤시티 4개 브랜드 객실 수(가중 평균용 · 이투데이 2017 개장 기사)
DC_ROOMS = {"gm_ys": 202, "ns_ys": 286, "nv_ys": 621, "is_ys": 591}
OTA_COLS = ["obs", "key", "stay", "price", "lo", "hi", "label", "deal", "alt", "st"]

# KAYAK 월별 평균 요금(hotel_adr/kayak.js 가 쌓는다 · 2026-10-29~) — 키: [KAYAK id, 표시 이름, 회사]
KAYAK_H = {
    "gic": [82365, "그랜드 인터컨티넨탈", "GS피앤엘"], "westin": [1072878518, "웨스틴 서울 파르나스", "GS피앤엘"],
    "pjeju": [1070436092, "파르나스 호텔 제주", "GS피앤엘"],
    "nt_md1": [496105, "나인트리 명동Ⅰ", "GS피앤엘"], "nt_md2": [2731798, "나인트리 명동Ⅱ", "GS피앤엘"],
    "nt_ins": [5554595, "나인트리 인사동", "GS피앤엘"], "nt_ddm": [6019223, "나인트리 동대문", "GS피앤엘"],
    "nt_pg": [7536808, "나인트리 판교", "GS피앤엘"], "nt_ys": [1070670581, "나인트리 용산(위탁)", "GS피앤엘"],
    "shilla_seoul": [76540, "서울신라호텔", "호텔신라"], "shilla_jeju": [86274, "제주신라호텔", "호텔신라"],
    "stay_ghm": [2450802, "신라스테이 광화문", "호텔신라"], "stay_mapo": [2330447, "신라스테이 마포", "호텔신라"],
    "stay_yeoksam": [2154992, "신라스테이 역삼", "호텔신라"], "stay_seocho": [2757891, "신라스테이 서초", "호텔신라"],
    "stay_samsung": [6080159, "신라스테이 삼성", "호텔신라"], "stay_sdm": [806452, "신라스테이 서대문", "호텔신라"],
    "stay_guro": [2450800, "신라스테이 구로", "호텔신라"], "stay_dongtan": [728662, "신라스테이 동탄", "호텔신라"],
    "stay_hud": [2757890, "신라스테이 해운대", "호텔신라"], "stay_jeju": [2259231, "신라스테이 제주", "호텔신라"],
    "stay_iho": [10357751, "신라스테이 플러스 이호테우", "호텔신라"],
    "gm_ys": [2992812, "그랜드 머큐어 용산", "서부T&D"], "ns_ys": [2992813, "노보텔 스위트 용산", "서부T&D"],
    "nv_ys": [2991340, "노보텔 용산", "서부T&D"], "is_ys": [2991349, "이비스 스타일 용산", "서부T&D"],
}
# 묶음(가중 평균) — 나인트리 5곳 = 객실 수 × 2026 상반기 투숙률(GS피앤엘 반기보고서 · 용산은 위탁이라 매출이 수수료뿐이어서 뺀다)
KAYAK_AGG = {
    "nt5": ["나인트리 5곳", "GS피앤엘", {"nt_md1": 144 * .887, "nt_md2": 408 * .906, "nt_ins": 301 * .876, "nt_ddm": 219 * .864, "nt_pg": 315 * .768}],
    "dragoncity": ["드래곤시티 4곳", "서부T&D", dict(DC_ROOMS)],
    "stay_all": ["신라스테이 11곳", "호텔신라", {k: 1 for k in KAYAK_H if k.startswith("stay_")}],
}
KAYAK_COLS = ["snap", "key", "id", "cur"] + [f"m{i}" for i in range(1, 13)] + [f"w{i}" for i in range(1, 8)]


def jload(n):
    with open(os.path.join(D, n), encoding="utf-8") as f:
        return json.load(f)


def qkey(y, m):
    return f"{y}Q{(m - 1) // 3 + 1}"


def qprev(q, k):
    y, n = int(q[:4]), int(q[-1])
    n -= k
    while n < 1:
        n += 4; y -= 1
    return f"{y}Q{n}"


# ---------------- 월별(리츠) → 분기 ----------------
def monthly_block(R):
    out = {}
    for h, mm in R["m"].items():
        ks = sorted(mm)
        rows = []
        for ym in ks:
            adr, occ, src = mm[ym]
            y, m = int(ym[:4]), int(ym[5:])
            prev = mm.get(f"{y - 1}-{m:02d}")
            yoy = round((adr / prev[0] - 1) * 100, 1) if prev and prev[0] else None
            oyy = round(occ - prev[1], 1) if prev else None
            rows.append([ym, adr, occ, round(adr * occ / 100, 1), yoy, oyy, src])
        # 분기: 객실 판매 가중(ADR = Σ ADR×OCC×일수 / Σ OCC×일수) · 세 달이 다 있어야 완결
        qd = {}
        for ym in ks:
            y, m = int(ym[:4]), int(ym[5:])
            qd.setdefault(qkey(y, m), []).append((ym, mm[ym]))
        qrows = []
        for q in sorted(qd, key=lambda s: (int(s[:4]), int(s[-1]))):
            arr = qd[q]
            sold = sum(v[1] * calendar.monthrange(int(ym[:4]), int(ym[5:]))[1] for ym, v in arr)
            days = sum(calendar.monthrange(int(ym[:4]), int(ym[5:]))[1] for ym, v in arr)
            rev = sum(v[0] * v[1] * calendar.monthrange(int(ym[:4]), int(ym[5:]))[1] for ym, v in arr)
            adr = rev / sold if sold else None
            occ = sold / days if days else None
            qrows.append([q, round(adr, 1), round(occ, 1), round(adr * occ / 100, 1), len(arr)])
        qmap = {r[0]: r for r in qrows}
        for r in qrows:
            p = qmap.get(qprev(r[0], 4))
            r.append(round((r[1] / p[1] - 1) * 100, 1) if p and p[4] == 3 and r[4] == 3 else None)
            p1 = qmap.get(qprev(r[0], 1))
            r.append(round((r[1] / p1[1] - 1) * 100, 1) if p1 and p1[4] == 3 and r[4] == 3 else None)
        out[h] = {"m": rows, "q": qrows}
    return out


# ---------------- 회사 IR 분기 ----------------
def ir_block(IR):
    out = {}
    for co, blk in IR.items():
        skip = blk.get("skip", {})   # 공사 등으로 비교가 안 되는 분기 — 그 분기를 기준으로 한 전년비는 안 낸다
        c = {"src": blk.get("src"), "note": blk.get("rev_note", {}), "skip": skip, "h": {}}
        rooms = blk.get("rooms", {})
        keys = set(blk.get("occ", {})) | set(blk.get("rev", {}))
        for h in sorted(keys):
            occ = blk.get("occ", {}).get(h, {})
            rev = blk.get("rev", {}).get(h, {})
            qs = sorted(set(occ) | set(rev), key=lambda s: (int(s[:4]), int(s[-1])))
            rows = []
            for q in qs:
                o, r = occ.get(q), rev.get(q)
                y, n = int(q[:4]), int(q[-1])
                days = sum(calendar.monthrange(y, m)[1] for m in range(3 * n - 2, 3 * n + 1))
                px = None   # 투숙 1실당 사업장 매출(천원) — 식음·연회가 섞인 대용치
                if rooms.get(h) and o and r:
                    px = round(r * 1e8 / (rooms[h] * days * o / 100) / 1e3, 1)
                rp = round(r * 1e8 / (rooms[h] * days) / 1e3, 1) if rooms.get(h) and r else None   # 가용 객실당 매출(천원)
                rows.append([q, o, r, px, rp])
            m = {x[0]: x for x in rows}
            for x in rows:
                p = None if qprev(x[0], 4) in skip.get(h, []) or x[0] in skip.get(h, []) else m.get(qprev(x[0], 4))
                x.append(round((x[2] / p[2] - 1) * 100, 1) if p and p[2] and x[2] else None)   # 매출 YoY
                x.append(round((x[3] / p[3] - 1) * 100, 1) if p and p[3] and x[3] else None)   # 대용치 YoY
                x.append(round(x[1] - p[1], 1) if p and p[1] is not None and x[1] is not None else None)  # OCC %p
            c["h"][h] = rows
        out[co] = c
    return out


# ---------------- OTA ----------------
def ota_load():
    p = os.path.join(D, "ota.csv")
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def ota_save(rows):
    seen, out = {}, []
    for r in rows:                               # 같은 (관측일·호텔·숙박일)은 나중 것
        seen[(r["obs"], r["key"], r["stay"])] = r
    out = sorted(seen.values(), key=lambda r: (r["obs"], r["key"], r["stay"]))
    with open(os.path.join(D, "ota.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OTA_COLS); w.writeheader()
        for r in out:
            w.writerow({k: r.get(k, "") for k in OTA_COLS})
    return out


def parse_dump(text):
    rows, end = [], None
    for ln in text.splitlines():
        ln = ln.strip()
        if ln.startswith("O|"):
            p = ln.split("|")[1:]
            if len(p) < 10:
                continue
            r = dict(zip(OTA_COLS, p[:10]))
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", r["obs"]) or r["key"] not in HOTELS:
                continue
            rows.append(r)
        elif ln.startswith("END|"):
            end = ln.split("|")
    return rows, end


def pos_label(p, lo, hi):
    if not (p and lo and hi):
        return ""
    return "높음" if p > hi else "낮음" if p < lo else "보통"


def rule_dates(obs):
    """수집기(ota.js stayDates)와 같은 규칙 — 관측일 +14일 뒤 첫 수·토, +45일 뒤 첫 수·토."""
    o = date.fromisoformat(obs)
    def nxt(d, wd):
        while d.weekday() != wd:
            d += timedelta(days=1)
        return d
    a, b = o + timedelta(days=14), o + timedelta(days=45)
    return {nxt(a, 2).isoformat(): "wd", nxt(a, 5).isoformat(): "we", nxt(b, 2).isoformat(): "wd", nxt(b, 5).isoformat(): "we"}


def ota_block(rows):
    """관측일마다 호텔별 '선행 판매가' = 규칙 숙박일 4개(2주 뒤 · 6주 반 뒤의 수·토) 최저가(세금 포함) ÷ 1.1 의 평균(천원).
       평일(수)·주말(토)를 따로 + 둘의 평균. 규칙 밖 숙박일(손으로 고른 날짜)은 표에만 보이고 지수엔 안 들어간다."""
    by = {}
    # 이상치(일반 객실이 매진돼 스위트값만 잡힌 날 등)는 지수에서 뺀다 — 구글 보통 범위 상단의 1.5배 넘게, 또는
    # 같은 관측일·같은 호텔 다른 숙박일 중앙값의 2배 넘게. 표에는 그대로 두고 판정 칸에 '이상치'로 적는다.
    med = {}
    for r in rows:
        if r["st"] == "ok" and r["price"]:
            med.setdefault((r["obs"], r["key"]), []).append(float(r["price"]))
    def odd(r):
        p = float(r["price"]); m = sorted(med.get((r["obs"], r["key"]), []))
        mid = m[len(m) // 2] if len(m) >= 3 else None
        return bool((r["hi"] and p > 1.5 * float(r["hi"])) or (mid and p > 2.0 * mid))
    for r in rows:
        if r["st"] != "ok" or not r["price"]:
            continue
        k = rule_dates(r["obs"]).get(r["stay"])
        if not k or odd(r):
            continue
        p = float(r["price"]) / VAT / 1e3
        by.setdefault(r["obs"], {}).setdefault(r["key"], {"wd": [], "we": []})[k].append(p)
    obs = sorted(by)
    idx = {}
    for h in HOTELS:
        wd, we, al = [], [], []
        for o in obs:
            d = by[o].get(h)
            a = round(sum(d["wd"]) / len(d["wd"]), 1) if d and d["wd"] else None
            b = round(sum(d["we"]) / len(d["we"]), 1) if d and d["we"] else None
            wd.append(a); we.append(b)
            al.append(round((a + b) / 2, 1) if a is not None and b is not None else None)
        if any(v is not None for v in al + wd + we):
            idx[h] = {"wd": wd, "we": we, "al": al}
    # 드래곤시티 4개 브랜드 객실 가중
    dc = []
    for i, o in enumerate(obs):
        vs = [(idx[k]["al"][i], n) for k, n in DC_ROOMS.items() if k in idx and idx[k]["al"][i] is not None]
        dc.append(round(sum(v * n for v, n in vs) / sum(n for _, n in vs), 1) if len(vs) == len(DC_ROOMS) else None)
    if any(v is not None for v in dc):
        idx["dragoncity"] = {"al": dc}
    last = obs[-1] if obs else (max(r["obs"] for r in rows) if rows else None)
    lrows = []
    for r in rows:
        if r["obs"] != last:
            continue
        p = int(r["price"]) if r["price"] else None
        lo = int(r["lo"]) if r["lo"] else None
        hi = int(r["hi"]) if r["hi"] else None
        lab = "이상치" if r["st"] == "ok" and p and odd(r) else (r["label"] or pos_label(p, lo, hi))
        lrows.append([r["key"], r["stay"], p, lo, hi, lab, r["deal"], r["alt"], r["st"]])
    lrows.sort(key=lambda x: (list(HOTELS).index(x[0]), x[1]))
    return {"obs": obs, "idx": idx, "last": last, "rows": lrows, "n": len(rows),
            "days": sorted({r["obs"] for r in rows})}


# ---------------- KAYAK 월별 평균 요금 ----------------
# 무엇: 호텔 페이지의 monthlyStayPrice(1~12월) — 'KAYAK 사용자들이 지난 12개월 동안 검색한 요금' 의 달별 평균(달러 · 전 객실 타입 · 세금 포함).
# 달 번호 → 실제 연월: 수집일이 속한 달보다 앞 달 = 올해 끝난 달 · 같은 달 = 진행 중 · 뒤 달 = 작년 같은 달과 내년 미리 검색이 섞여 버린다.
# 끝난 달은 그 달이 끝난 뒤 첫 수집 값을 쓴다(그 뒤로는 내년 같은 달 미리 검색이 조금씩 섞여 들어온다).
# 첫 수집(2026-10-29)의 1~9월은 끝나고 한참 뒤 값이라 'late' 표시.
# 환율: KAYAK 은 달러로 쌓아 두고 화면 통화로는 오늘 환율 하나를 곱해 보여 준다 → 원화 값 = 달러 × 그달 평균 원/달러(ECB · kbeauty/data/fx_month.csv).
# 검증(2026-10-29): 리츠가 실제 ADR 을 내는 3곳의 3Q26/2Q26 — 그랜드 머큐어 실측 −2.0% vs +0.9% · 신라스테이 광화문 −8.8% vs −9.9% ·
# 마포 −6.7% vs −7.3% (보정 안 하면 +6.7 · −4.4 · −2.0 으로 원화 강세만큼 높게 나온다). 월별 수준 상관 0.83~0.98.
def kayak_load():
    p = os.path.join(D, "kayak.csv")
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def kayak_save(rows):
    seen = {}
    for r in rows:
        seen[(r["snap"], r["key"])] = r
    out = sorted(seen.values(), key=lambda r: (r["snap"], list(KAYAK_H).index(r["key"]) if r["key"] in KAYAK_H else 99))
    with open(os.path.join(D, "kayak.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=KAYAK_COLS); w.writeheader()
        for r in out:
            w.writerow({k: r.get(k, "") for k in KAYAK_COLS})
    return out


def _crc36(s):
    import zlib
    n = zlib.crc32(s.encode("utf-8")) & 0xFFFFFFFF
    a = "0123456789abcdefghijklmnopqrstuvwxyz"; o = ""
    while True:
        n, r = divmod(n, 36); o = a[r] + o
        if not n:
            return o


def kayak_parse(text):
    rows, bad, end = [], [], None
    for ln in text.splitlines():
        ln = ln.strip()
        if ln.startswith("K|"):
            p = ln.split("|")
            if len(p) != 8:
                bad.append(ln[:40]); continue
            body, c = "|".join(p[:7]), p[7]
            mv, wv = p[5].split(";"), (p[6].split(";") if p[6] else [])
            if _crc36(body) != c or len(mv) != 12 or p[2] not in KAYAK_H or not re.match(r"^\d{4}-\d{2}-\d{2}$", p[1]):
                bad.append(p[2] if len(p) > 2 else ln[:40]); continue
            r = {"snap": p[1], "key": p[2], "id": p[3], "cur": p[4]}
            r.update({f"m{i + 1}": mv[i] for i in range(12)})
            r.update({f"w{i + 1}": (wv[i] if i < len(wv) else "") for i in range(7)})
            rows.append(r)
        elif ln.startswith("END|"):
            end = ln.split("|")
    return rows, bad, end


def fx_month():
    p = os.path.join(ROOT, "kbeauty", "data", "fx_month.csv")
    out = {}
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    out[r["ym"]] = float(r["USD"])
                except (KeyError, ValueError):
                    pass
    return out


def _mi(y, m):
    return y * 12 + m - 1


def _ym(i):
    return f"{i // 12}-{i % 12 + 1:02d}"


def kayak_block(rows):
    if not rows:
        return None
    FX = fx_month()
    snaps = sorted({r["snap"] for r in rows})
    last = snaps[-1]
    lm = _mi(int(last[:4]), int(last[5:7]))
    H = {}
    for k, (kid, nm, co) in KAYAK_H.items():
        rs = sorted((r for r in rows if r["key"] == k and r.get("cur", "USD") in ("USD", "")), key=lambda r: r["snap"])
        if not rs:
            continue
        done = {}      # 실제 연월 번호 → [달러, 수집일] — 그 달이 끝난 뒤 첫 수집
        cur = None
        for r in rs:
            s = r["snap"]; si = _mi(int(s[:4]), int(s[5:7]))
            for m in range(1, 13):
                v = r.get(f"m{m}")
                if not v:
                    continue
                v = float(v)
                if v <= 0:
                    continue
                if m < int(s[5:7]):
                    i = _mi(int(s[:4]), m)
                    if i not in done:
                        done[i] = [v, s]
                elif m == int(s[5:7]) and s == rs[-1]["snap"] and si == lm:
                    cur = [si, v, s]
        mrows = []
        for i in sorted(done):
            usd, s = done[i]
            ym = _ym(i); fx = FX.get(ym)
            si = _mi(int(s[:4]), int(s[5:7]))
            mrows.append([ym, round(usd, 2), round(usd * fx / 1e3, 1) if fx else None, "l" if si - i > 1 else "d", s])
        if cur and (cur[0] not in done):
            ym = _ym(cur[0]); fx = FX.get(ym)
            mrows.append([ym, round(cur[1], 2), round(cur[1] * fx / 1e3, 1) if fx else None, "c", cur[2]])
        wk = rs[-1]
        wv = [float(wk[f"w{i}"]) for i in range(1, 8) if wk.get(f"w{i}")]
        wa = sum(wv) / len(wv) if wv else None
        H[k] = {"n": nm, "co": co, "id": kid, "m": mrows, "w": [round(x / wa * 100, 1) for x in wv] if wa else []}
    # 묶음 — 끝난 달(d·l)은 구성 호텔이 다 있을 때만, 진행 중(c)도 다 있을 때만
    for ak, (nm, co, wts) in KAYAK_AGG.items():
        mem = [k for k in wts if k in H]
        if len(mem) < max(2, len(wts) - (len(wts) // 4)):    # 4곳 중 1곳까지는 빠져도 된다(단순 평균 묶음)
            continue
        by = {}
        for k in mem:
            for ym, usd, krw, st, s in H[k]["m"]:
                by.setdefault(ym, {})[k] = (usd, krw, st)
        mrows = []
        for ym in sorted(by):
            d = by[ym]
            if set(d) != set(mem) or any(v[1] is None for v in d.values()):
                continue
            sts = {v[2] for v in d.values()}
            st = "c" if "c" in sts else ("l" if "l" in sts else "d")
            W = sum(wts[k] for k in mem)
            usd = sum(d[k][0] * wts[k] for k in mem) / W
            krw = sum(d[k][1] * wts[k] for k in mem) / W
            mrows.append([ym, round(usd, 2), round(krw, 1), st, ""])
        if mrows:
            H[ak] = {"n": nm, "co": co, "agg": mem, "m": mrows, "w": []}
    # 분기 — 일수 가중 평균 · 세 달이 다 끝났을 때만 완결 · 전분기비·전년비는 완결끼리
    for k, h in H.items():
        qd = {}
        for ym, usd, krw, st, s in h["m"]:
            if krw is None:
                continue
            y, m = int(ym[:4]), int(ym[5:])
            qd.setdefault(qkey(y, m), []).append((calendar.monthrange(y, m)[1], krw, st))
        qrows = []
        for q in sorted(qd, key=lambda s: (int(s[:4]), int(s[-1]))):
            arr = qd[q]
            v = sum(dd * x for dd, x, st in arr) / sum(dd for dd, x, st in arr)
            nd = sum(1 for dd, x, st in arr if st != "c")
            qrows.append([q, round(v, 1), nd])
        qm = {r[0]: r for r in qrows}
        for r in qrows:
            p1, p4 = qm.get(qprev(r[0], 1)), qm.get(qprev(r[0], 4))
            r.append(round((r[1] / p1[1] - 1) * 100, 1) if p1 and p1[2] == 3 and r[2] == 3 else None)
            r.append(round((r[1] / p4[1] - 1) * 100, 1) if p4 and p4[2] == 3 and r[2] == 3 else None)
        h["q"] = qrows
    fx = {ym: round(v, 1) for ym, v in FX.items() if ym >= "2025-01"}
    return {"asOf": last, "snaps": snaps, "fx": fx, "h": H}


# ---------------- 블록 ----------------
def build():
    R = jload("reit_monthly.json")
    IR = jload("ir_quarterly.json")
    B = jload("broker.json")
    M = jload("market.json")
    ota = ota_load()
    O = ota_block(ota)
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    blk = {
        "asOf": now, "hotels": HOTELS, "dcRooms": DC_ROOMS,
        "reit": {"src": R["src"], "h": monthly_block(R)},
        "ir": ir_block(IR), "br": B["rows"], "mkt": M, "ota": O,
    }
    K = kayak_block(kayak_load())
    if K:
        blk["kayak"] = K
    return blk


def inject(blk):
    with open(HTML, encoding="utf-8") as f:
        html = f.read()
    m = re.search(r"^const ADR = (\{.*?\});$", html, re.M | re.S)
    if m:
        old = json.loads(m.group(1))
        a = dict(old); b = dict(blk); a.pop("asOf", None); b.pop("asOf", None)
        if a == b:
            print("[ADR] 변동 없음 — 파일을 안 건드린다")
            return False
    line = "const ADR = " + json.dumps(blk, ensure_ascii=False, separators=(",", ":")) + ";"
    if m:
        html = html[:m.start()] + line + html[m.end():]
    else:
        a = re.search(r"^const RETAIL = \{.*?\};$", html, re.M | re.S)     # 처음엔 RETAIL 바로 아래
        if not a:
            sys.exit("RETAIL 블록을 못 찾아 ADR 을 넣을 자리가 없다")
        html = html[:a.end()] + "\n" + line + html[a.end():]
    with open(HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[ADR] 블록 {len(line)/1024:.1f}KB 갱신")
    return True


def main():
    a = sys.argv[1:]
    if a and a[0] == "--today":      # 종료코드 0 = 오늘(KST) 관측이 이미 있다 → 아침 수집을 건너뛴다
        today = datetime.now(KST).strftime("%Y-%m-%d")
        n = sum(1 for r in ota_load() if r["obs"] == today and r["st"] == "ok")
        print(f"[ADR-OTA] {today} 관측 ok {n}줄")
        sys.exit(0 if n >= 26 else 1)
    if a and a[0] == "--check":
        text = "".join(open(p, encoding="utf-8").read() for p in a[1:])
        rows, end = parse_dump(text)
        st = {}
        for r in rows:
            st[r["st"]] = st.get(r["st"], 0) + 1
        ok_end = end and len(end) >= 3 and end[2].isdigit() and int(end[2]) == len(rows)
        print(f"[ADR-OTA] 줄 {len(rows)} · 상태 {st} · END {'일치' if ok_end else '없음/불일치'}")
        sys.exit(0 if rows and ok_end else 2)
    if a and a[0] == "--kayak-done":   # 종료코드 0 = 이번 달 수집이 있고 6일 안쪽이다 → KAYAK 단계를 건너뛴다
        today = datetime.now(KST).date()
        snaps = sorted({r["snap"] for r in kayak_load()})
        ok = bool(snaps) and snaps[-1][:7] == today.isoformat()[:7] and (today - date.fromisoformat(snaps[-1])).days <= 6
        print(f"[ADR-KAYAK] 마지막 수집 {snaps[-1] if snaps else '없음'} → {'건너뜀' if ok else '수집할 차례'}")
        sys.exit(0 if ok else 1)
    if a and a[0] in ("--kayak-check", "--kayak"):
        text = "".join(open(p, encoding="utf-8").read() for p in a[1:])
        new, bad, end = kayak_parse(text)
        ok_end = end and len(end) >= 3 and end[2].isdigit() and int(end[2]) == len(new) + len(bad)
        miss = [k for k in KAYAK_H if k not in {r["key"] for r in new}]
        print(f"[ADR-KAYAK] 줄 {len(new)} · 틀린 줄 {len(bad)}{' ' + ','.join(bad) if bad else ''} · 빠진 호텔 {len(miss)}{' ' + ','.join(miss) if miss else ''} · END {'일치' if ok_end else '없음/불일치'}")
        if a[0] == "--kayak-check":
            sys.exit(0 if new and not bad and ok_end else 2)
        if not new:
            sys.exit("[ADR-KAYAK] 덤프에 맞는 K| 줄이 없다")
        rows = kayak_save(kayak_load() + new)
        print(f"[ADR-KAYAK] {new[0]['snap']} 호텔 {len(new)}곳 더함 · 누적 {len(rows)}줄")
    if a and a[0] == "--ota":
        text = "".join(open(p, encoding="utf-8").read() for p in a[1:])
        new, end = parse_dump(text)
        if not new:
            sys.exit("[ADR-OTA] 덤프에 O| 줄이 없다")
        rows = ota_save(ota_load() + new)
        ok = sum(1 for r in new if r["st"] == "ok")
        print(f"[ADR-OTA] {new[0]['obs']} 관측 {len(new)}줄(ok {ok}) 더함 · 누적 {len(rows)}줄")
    blk = build()
    inject(blk)
    O = blk["ota"]
    if O["obs"]:
        last = O["obs"][-1]
        top = []
        for h in ["gic", "westin", "dragoncity", "shilla_seoul", "stay_ghm", "nt_ddm"]:
            v = O["idx"].get(h, {}).get("al", [None])[-1]
            if v is not None:
                top.append(f"{(HOTELS.get(h) or ['드래곤시티'])[0]} {v:.0f}")
        print(f"[ADR] OTA {last} 선행 판매가(천원·VAT 제외) " + " · ".join(top))
    K = blk.get("kayak")
    if K:
        top = []
        for h in ["gic", "westin", "pjeju", "nt5", "shilla_seoul", "stay_all", "dragoncity"]:
            q = [r for r in K["h"].get(h, {}).get("q", []) if r[2] == 3 and r[3] is not None]
            if q:
                top.append(f"{K['h'][h]['n']} {q[-1][0][-1]}Q{q[-1][0][2:4]} 전분기비 {q[-1][3]:+.1f}%")
        print(f"[ADR] KAYAK {K['asOf']} 수집 {len(K['snaps'])}회 · " + " · ".join(top))


if __name__ == "__main__":
    main()
