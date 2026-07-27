# -*- coding: utf-8 -*-
"""
텔레그램 데일리 레터 — 중요한 신호만 간결하게.
(실적 서프라이즈=notify.py, 월간 수출=trade_digest.py 가 담당. 여긴 매일 요약.)

원칙:
  - 트렌드 데이터: TRACK 이 정한 계열만. 고정(pin) 은 매일, 나머지는 의미있게 움직였을 때만.
    같은 (종목, 그룹) 은 한 블록으로 묶어 서로 비교되게 찍는다.
  - 시세 급변(전일)엔 '왜 움직였나'를 준다. 근거가 센 순서로:
    실적발표(실제치 vs consSnap 컨센 → 상회/하회 × 주가방향으로 호실적반영/부진/셀온/
    악재선반영 판정, _surprise) > 그 밖의 공시 > 뉴스 헤드라인 > 트렌드 동반 > 섹터 전반.
    외부 API 는 쓰지 않는다. 근거가 하나도 없으면 아무 말도 붙이지 않는다(지어내지 않는다).
  - 카테고리: 소비재는 세부(화장품/미용/음식료/유통), 엔터·게임·호텔은 섹터.
  - 방향은 색 하나로만 (🔴상승·🔵하락, 한국식). 부호가 이미 방향을 말하므로 기호를 겹치지 않는다.
  - 줄이 넘치면 텔레그램이 다음 줄을 왼쪽 끝에 붙여 들여쓰기가 깨진다.
    그래서 폭(REASON_W·LABEL_W)을 정해 놓고 애초에 안 넘치게 자른다.
    자리 맞춤이 필요한 줄은 <code> 로 감싼다 — 밖은 가변폭이라 칸이 안 맞는다.

  python digest.py            # 전송
  python digest.py --dry-run  # 출력만
  python digest.py --alerts   # 일정·시세만(짧게)
"""
import re, json, sys, datetime, unicodedata
import telegram_send


HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
CHG_ALERT = 5.0
EVENT_DAYS = 7
NOTABLE_WOW = 15      # 트렌드 '의미있는' 전주비(%)
NOTABLE_BASE = 15     # 트렌드 기저(이 미만은 노이즈)
SPIKE = 30            # 급등/급락 태그
STREAK_MIN = 4        # 연속추세 태그(주)
# 폭(표시 칸 수). 텔레그램은 줄이 넘치면 다음 줄을 왼쪽 끝에 붙여 버려서
# 들여쓴 이유 줄이 두 줄이 되는 순간 모양이 무너진다. 애초에 안 넘치게 자른다.
REASON_W = 32         # 급변 이유 한 줄(들여쓰기 4칸 + 32 = 모바일 한 줄에 들어감)
LABEL_W = 12          # 트렌드 계열 이름 칸 (넘치면 자른다)
BLK = "▁▂▃▄▅▆▇█"
WD = ["월", "화", "수", "목", "금", "토", "일"]

# 레터에 올릴 계열 — (종목, 트렌드 그룹, 계열, 고정)
#   고정=True  : 움직임과 무관하게 매일 싣는다(매일 보고 싶다고 지정한 것)
#   고정=False : '의미있게 움직였을 때'만 (NOTABLE_WOW / STREAK_MIN)
# 연속으로 같은 (종목, 그룹) 이면 한 블록으로 묶여 서로 비교되게 찍힌다.
#
# 뺀 것: 배틀그라운드(크래프톤)·니케(시프트업).
#   둘 다 수년째 서비스 중이라 검색이 평탄하고, 움직여도 업데이트/이벤트라
#   실적 방향과 이어지지 않는다. 매일 볼 값이 아니다.
TRACK = [
    # 스킨부스터 3파전 — 리쥬란 단독으로 보면 '리쥬란이 빠진 건지 카테고리가
    # 빠진 건지'를 못 가른다. 경쟁 IP 와 나란히 놔야 점유 변화가 읽힌다.
    ("파마리서치", "스킨부스터", "리쥬란",   True),
    ("파마리서치", "스킨부스터", "리투오",   True),
    ("파마리서치", "스킨부스터", "셀르디엠", True),
    ("에이피알",   "K-뷰티 브랜드", "메디큐브", False),
    ("달바글로벌", "K-뷰티 브랜드", "달바",     False),
    ("리센스메디컬", "쿨로아600", "쿨로아600",  False),
    # 티니핑 국내(네이버) — 극장판 2편 개봉(8/5) 앞이라 홈마켓 관심이 곧 예매로 이어진다
    ("SAMG엔터", "티니핑 국가별", "한국", True),
    # 메탈카드봇 러시아(얀덱스) — 얀덱스는 절대 검색수를 줘서 크기 비교가 되는 유일한 소스
    ("SAMG엔터", "변신로봇 IP 러시아", "메탈카드봇", True),
    ("펄어비스", "펄어비스 IP", "붉은사막", False),
    # NC 신작 — 미출시라 평소엔 0 근처, 코믹마켓·테스터 모집 같은 이벤트에만 튄다.
    # 그 스파이크가 곧 신호라 조건부로 둔다(고정하면 매일 빈 줄만 나간다).
    ("NC", "아스트라에 오라티오", "아스트라에 오라티오", False),
]


def _const(html, name, br="{"):
    cl = "}" if br == "{" else "]"
    m = re.search(r"const %s\s*=\s*(\%s.*?\%s);" % (re.escape(name), br, cl), html, re.S)
    return json.loads(m.group(1)) if m else None


def _clean(s):
    return [v for v in s if v is not None]


def _wow(s):
    c = _clean(s)
    return None if len(c) < 2 or not c[-2] else (c[-1] / c[-2] - 1) * 100


def _streak(s):
    c = _clean(s)
    if len(c) < 2:
        return 0
    up, n = c[-1] > c[-2], 0
    for i in range(len(c) - 1, 0, -1):
        if c[i] != c[i - 1] and (c[i] > c[i - 1]) == up:
            n += 1
        else:
            break
    return n if up else -n


def _last(s):
    c = _clean(s)
    return c[-1] if c else None


def _w(s):
    """표시 폭 — 한글·전각은 두 칸을 먹는다.
       텔레그램 고정폭 글꼴에서 자리를 맞추려면 글자 수가 아니라 이 폭으로 세야 한다
       ('리쥬란' 3글자와 '셀르디엠' 4글자는 폭이 6 vs 8 이라 글자 수로 맞추면 어긋난다)."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _pad(s, n, right=False):
    sp = " " * max(0, n - _w(s))
    return (sp + s) if right else (s + sp)


def _cut(s, n):
    """표시 폭 n 칸으로 자른다. 글자 수로 자르면 한글이 섞였을 때 두 배로 길어져
       텔레그램에서 줄이 넘치고, 넘친 줄은 들여쓰기를 잃고 왼쪽 끝으로 붙는다."""
    if not s or _w(s) <= n:
        return s
    out = ""
    for c in s:
        if _w(out + c) > n - 1:
            break
        out += c
    return out + "…"


def _spark(s, n=10):
    c = _clean(s)[-n:]
    if len(c) < 2:
        return ""
    lo, hi = min(c), max(c)
    if hi == lo:
        return BLK[3] * len(c)
    return "".join(BLK[min(7, int((v - lo) / (hi - lo) * 7 + 0.5))] for v in c)


def _series(gobj, kw):
    prods = gobj.get("products") or []
    ser = gobj.get("naver") or gobj.get("google") or []
    if kw in prods and prods.index(kw) < len(ser):
        return ser[prods.index(kw)]
    return None


def _notable(tr):
    """레터에 실을 계열. dict 리스트로 돌려준다.
       고정(pin)은 무조건, 나머지는 의미있게 움직였을 때만.
       순서는 TRACK 순서를 유지한다 — 같은 그룹끼리 붙어 있어야 비교로 읽힌다."""
    groups = tr.get("groups") or {}
    rows = []
    for stock, gname, kw, pin in TRACK:
        g = groups.get(gname)
        s = _series(g, kw) if g else None
        if not s:
            continue
        last, w, st = _last(s), _wow(s), _streak(s)
        if last is None:
            continue
        if not pin:
            if last < NOTABLE_BASE:
                continue
            if not ((w is not None and abs(w) >= NOTABLE_WOW) or abs(st) >= STREAK_MIN):
                continue
        rows.append({"stock": stock, "group": gname, "kw": kw, "s": s,
                     "w": w, "streak": st, "pin": pin, "last": last,
                     # 얀덱스 그룹만 절대 검색수를 준다(peak=100 에 해당하는 실제 건수).
                     # 0~100 상대값끼리 크기를 비교하면 거짓말이 되므로 이때만 실수치를 쓴다.
                     "peak": (g or {}).get("peak"),
                     "src": ((g or {}).get("srcOf") or [None] * 99)[
                         ((g or {}).get("products") or []).index(kw)
                         if kw in ((g or {}).get("products") or []) else 0]})
    return rows


def _arw(c):
    """등락 방향 — 한국식 색(상승 빨강·하락 파랑).
       텔레그램은 이모지로만 색을 낼 수 있다. 예전엔 네모+삼각형을 겹쳐 썼는데
       기호가 둘이라 지저분했다. 부호(+/-)가 이미 방향을 말하므로 색 하나면 충분하다."""
    return "🔴" if c > 0 else "🔵"


def _cat(rec, name):
    r = rec.get(name)
    if not r:
        return ""
    return r.get("sub", "") if r.get("sector") == "소비재" else r.get("sector", "")


def _prev_bday(d):
    """직전 영업일 — 등락(직전 세션 결과)에 인과가 될 수 있는 뉴스 창의 시작점.
       화~금: 전 영업일=어제. 월: 전 영업일=금요일(주말 갭 포함)."""
    x = d - datetime.timedelta(days=1)
    while x.weekday() >= 5:
        x -= datetime.timedelta(days=1)
    return x


def _match(item, name):
    """뉴스 1건이 이 종목 건인지 — co 리스트 우선, 없으면 제목 매칭."""
    return name in (item.get("co") or []) or name in (item.get("t") or "")


def _news(items, name, cut):
    """종목 관련, 날짜가 cut(직전 영업일) 이후인 최신 기사 제목. 없으면 None.
       cut 밖(오래된) 기사는 이번 등락과 인과가 없으므로 붙이지 않는다."""
    cand = [x for x in items if _match(x, name) and x.get("d", "")[:10] >= cut]
    if not cand:
        return None
    cand.sort(key=lambda x: x.get("d", ""), reverse=True)
    t = cand[0]["t"]
    return _cut(t, REASON_W)


_QLAST = {3: 31, 6: 30, 9: 30, 12: 31}


def _qn(k):
    return {"03": "1Q", "06": "2Q", "09": "3Q", "12": "4Q"}.get(k[4:6], k) if len(k) >= 6 else k


def _surprise(live, nm, chg, today):
    """발표된 최근 분기의 '실제 vs consSnap 컨센' → 서프라이즈 × 주가방향 해석 한 줄. 없으면 None.
       컨센(consSnap)이 보존돼 있고 시계열이 실제(e=False)로 바뀐, 분기말 80일 내 분기만 본다
       (오래된 분기를 이번 급변에 오귀속하지 않도록)."""
    r = (live.get("stocks") or {}).get(nm) or {}
    snap = (live.get("consSnap") or {}).get(nm) or {}
    qser = ((r.get("cons") or {}).get("quarter") or {}).get("series") or []
    hit = None
    for x in reversed(qser):
        k = x.get("k", "")
        if x.get("e") or k not in snap or len(k) < 6:   # 아직 컨센(추정)이거나 스냅샷 없음
            continue
        try:
            qe = datetime.date(int(k[:4]), int(k[4:6]), _QLAST.get(int(k[4:6]), 28))
        except ValueError:
            continue
        if (today - qe).days > 80:      # 오래된 분기 → 이번 급변과 무관
            break
        hit = x
        break
    if not hit:
        return None
    c = snap[hit["k"]]
    qn = _qn(hit["k"])
    co, ao, cr, ar = c.get("op"), hit.get("op"), c.get("rev"), hit.get("rev")
    up = chg > 0
    beat = miss = False
    if co is not None and ao is not None:
        if co < 0 <= ao:
            vs, beat = f"{qn} 영업 흑자전환(컨센 상회)", True
        elif ao < 0 <= co:
            vs, miss = f"{qn} 영업 적자전환(컨센 하회)", True
        elif co < 0 and ao < 0:                          # 둘 다 적자 → 축소/확대
            better = ao > co
            vs = f"{qn} 영업적자 {'축소' if better else '확대'}(컨센 {'상회' if better else '하회'})"
            beat, miss = better, not better
        else:
            base = abs(co) or abs(ao) or 1
            pct = (ao - co) / base * 100
            if pct >= 5:
                vs, beat = f"{qn} 영업익 컨센 {pct:+.0f}% 상회", True
            elif pct <= -5:
                vs, miss = f"{qn} 영업익 컨센 {pct:.0f}% 하회", True
            else:
                vs = f"{qn} 영업익 컨센 부합"
    elif cr and ar:                                      # 영업익 없으면 매출로
        pct = (ar / cr - 1) * 100
        if pct >= 5:
            vs, beat = f"{qn} 매출 컨센 {pct:+.0f}% 상회", True
        elif pct <= -5:
            vs, miss = f"{qn} 매출 컨센 {pct:.0f}% 하회", True
        else:
            vs = f"{qn} 매출 컨센 부합"
    else:
        return None
    if beat and up:
        return f"{vs}, 호실적 반영"
    if beat and not up:
        return f"{vs}에도 하락 → 셀온"
    if miss and not up:
        return f"{vs}, 실적 부진 반영"
    if miss and up:
        return f"{vs}에도 상승 → 악재 선반영/저점매수"
    return vs                                            # 컨센 부합


def build(html, alerts_only=False):
    today = datetime.datetime.now(KST).date()
    tr = _const(html, "TREND") or {"groups": {}}
    live = _const(html, "LIVE") or {}
    evs = _const(html, "DART_EVENTS", "[") or []
    mv = _const(html, "MOVIE") or {}
    data = _const(html, "DATA") or {"records": []}
    news = _const(html, "NEWS") or {"items": []}
    rec = {r["name"]: r for r in data.get("records", [])}
    nitems = news.get("items") or []
    news_cut = _prev_bday(today).isoformat()   # 이 등락과 인과 가능한 뉴스 창 시작(직전 영업일)

    end = (today + datetime.timedelta(days=EVENT_DAYS)).isoformat()
    soon = sorted([e for e in evs if e.get("type") in ("earn", "ir")
                   and today.isoformat() <= e.get("date", "") <= end], key=lambda e: e["date"])
    movers = sorted([(s.get("chgPct"), nm) for nm, s in (live.get("stocks") or {}).items()
                     if s.get("chgPct") is not None and abs(s["chgPct"]) >= CHG_ALERT],
                    key=lambda x: -abs(x[0]))
    notable = _notable(tr)

    chg_of = {nm: c for c, nm in movers}

    # 같은 카테고리가 통째로 움직였는지 — 개별 재료가 없을 때의 기본 설명.
    # 종목 뉴스가 없다고 '이유 없음'으로 두면, 실은 섹터 전반이 움직인 날을 놓친다.
    def _sector_move(nm):
        cat = _cat(rec, nm)
        if not cat:
            return None
        peers = [n for n, r in rec.items() if _cat(rec, n) == cat and n != nm]
        chgs = [(live.get("stocks") or {}).get(n, {}).get("chgPct") for n in peers]
        chgs = [c for c in chgs if c is not None]
        if len(chgs) < 3:
            return None
        me = chg_of.get(nm, 0)
        same = [c for c in chgs if (c > 0) == (me > 0) and abs(c) >= 1.5]
        if len(same) < len(chgs) * 0.6:
            return None
        return f"{cat} 섹터 전반 {'강세' if me > 0 else '약세'}(동반 {len(same)}/{len(chgs)}종목)"

    # 그 종목의 트렌드가 같은 방향으로 튀었는지 — 수요 쪽 근거가 되는 유일한 자체 데이터
    def _trend_move(nm):
        for r in notable:
            if r["stock"] != nm or r["w"] is None or abs(r["w"]) < SPIKE:
                continue
            if (r["w"] > 0) == (chg_of.get(nm, 0) > 0):
                return f"{r['kw']} 트렌드 전주비 {r['w']:+.0f}% 동반"
        return None

    def _why(nm):
        """키 없이 도는 규칙기반 이유. 근거가 센 순서로 본다.
           실적 > 그 밖의 공시 > 뉴스 헤드라인 > 트렌드 동반 > 섹터 전반.
           (예전엔 Claude API 로 추론했으나 키를 쓰지 않기로 해서 규칙만 남겼다.
            지어내지 않는 게 원칙이라, 아무 근거도 없으면 아무 말도 붙이지 않는다.)"""
        disc = [e for e in evs if e.get("co") == nm
                and news_cut <= e.get("date", "") <= today.isoformat()]
        head = _news(nitems, nm, news_cut)
        # 한 줄에 하나만 담는다. 예전엔 '공시: … · 뉴스헤드라인…' 처럼 둘을 이어 붙여
        # 줄이 넘쳤고, 넘친 줄은 들여쓰기를 잃고 왼쪽 끝에 붙어 모양이 깨졌다.
        if any(e.get("type") == "earn" for e in disc):
            sur = _surprise(live, nm, chg_of.get(nm, 0), today)
            if sur:
                return _cut(sur, REASON_W)                   # 실제치 vs 컨센이 잡히면 그 해석이 이유
            return "실적발표" if not head else _cut(f"실적발표 · {head}", REASON_W)
        if disc:                                             # 실적 외 공시(IR·계약 등)
            kinds = [e.get("title") or e.get("type") for e in disc]
            return _cut(f"공시: {kinds[0]}", REASON_W)
        return head or _trend_move(nm) or _cut(_sector_move(nm) or "", REASON_W) or None

    # 오늘의 포인트
    pts = []
    for e in [x for x in soon if x["type"] == "earn"
              and (datetime.date.fromisoformat(x["date"]) - today).days <= 1][:2]:
        dd = (datetime.date.fromisoformat(e["date"]) - today).days
        pts.append(f"{'오늘' if not dd else '내일'} <b>{e['co']}</b> 실적발표")
    sp = next((r for r in notable
               if r["w"] is not None and abs(r["w"]) >= SPIKE and r["last"] >= NOTABLE_BASE), None)
    if sp:
        pts.append(f"<b>{sp['stock']}</b> {sp['kw']} 트렌드 {sp['w']:+.0f}%")
    # 급변 1위는 여기 안 적는다 — 바로 아래 '전일 급변' 첫 줄과 똑같은 내용이라
    # 같은 문장이 두 번 나오고, 이유까지 달면 줄이 넘쳐 줄바꿈이 깨진다.

    # ── 본문 ───────────────────────────────────────────────
    # 이모지는 섹션 머리에 1개씩만. 본문 줄에는 색(등락)만 쓴다.
    # 예전엔 줄마다 🟥▲ / 🔥급등 / ↗4주 가 겹쳐 붙어 읽는 데 방해가 됐다.
    # 부호와 숫자가 이미 방향·세기를 말하므로 기호를 더 얹지 않는다.
    out = []
    if pts:
        out.append("<b>오늘의 포인트</b>\n" + "\n".join("• " + p for p in pts))

    # 전일 시세 급변 — 가장 먼저. 오늘 당장 대응할 게 있다면 여기다.
    if movers:
        lines = []
        for c, nm in movers[:6]:
            cat = _cat(rec, nm)
            rs = _why(nm)
            lines.append(f"{_arw(c)} <b>{nm}</b> {c:+.1f}%" + (f"  <i>{cat}</i>" if cat else "")
                         + (f"\n    {rs}" if rs else ""))
        extra = f"\n<i>외 {len(movers)-6}종목</i>" if len(movers) > 6 else ""
        out.append(f"<b>📈 전일 급변</b> <i>(±{CHG_ALERT:.0f}%)</i>\n" + "\n".join(lines) + extra)

    # 트렌드 데이터 — 고정 계열은 매일, 나머지는 의미있게 움직였을 때만. 최근 10주 추이.
    # (종목, 그룹)이 같으면 한 블록으로 묶는다 — 리쥬란/리투오/셀르디엠처럼
    #  나란히 놓여야 '누가 뺏겼나'가 보이는 것들이 있다.
    if not alerts_only and notable:
        # 먼저 그룹별로 모은다. 자리(폭)는 그룹 안에서만 맞추면 된다 —
        # 비교는 같은 그룹 안에서 일어나고, 그룹마다 단위가 다르다(0~100 vs 주당 건수).
        # 종목 단위로 묶는다. 그룹명은 그 그룹이 두 계열 이상을 낼 때만 붙인다 —
        # 계열이 하나뿐이면 '변신로봇 IP 러시아 / 메탈카드봇' 처럼 같은 말을 두 번 하는 셈이다.
        # 출처(네이버·얀덱스)는 아예 뺐다. 단위가 이미 성격을 말한다
        # (0~100 = 상대지수 / N건 = 얀덱스 절대 검색수).
        gcount = {}
        for r in notable:
            gcount[(r["stock"], r["group"])] = gcount.get((r["stock"], r["group"]), 0) + 1

        blocks = []
        for r in notable:
            if not blocks or blocks[-1]["stock"] != r["stock"]:
                blocks.append({"stock": r["stock"], "groups": [], "rows": []})
            b = blocks[-1]
            if gcount[(r["stock"], r["group"])] > 1 and r["group"] not in b["groups"]:
                b["groups"].append(r["group"])
            b["rows"].append({
                "label": _cut(r["kw"], LABEL_W),
                "spark": _spark(r["s"]),
                # 얀덱스는 절대 검색수라 실제 건수를 그대로 쓴다. 나머지는 0~100 상대값.
                "lvl": (f"{round(r['last'] / 100 * r['peak']):,}건"
                        if r["peak"] else f"{r['last']:.0f}/100"),
                "wow": "" if r["w"] is None else f"{r['w']:+.0f}%",
                "tail": f"  {abs(r['streak'])}주" if abs(r["streak"]) >= STREAK_MIN else ""})

        # 자리는 레터 전체에서 한 번만 잡는다.
        # 블록마다 따로 맞추면 블록이 바뀔 때마다 막대 시작점이 밀려서,
        # 겹쳐 보라고 넣은 스파크라인이 오히려 들쭉날쭉해 보인다.
        rows = [x for b in blocks for x in b["rows"]]
        lw = max(_w(x["label"]) for x in rows)
        vw = max(_w(x["lvl"]) for x in rows)
        ww = max(_w(x["wow"]) for x in rows)

        lines = []
        for b in blocks:
            if lines:
                lines.append("")                       # 종목 사이 한 줄 띄움
            lines.append(f"<b>{b['stock']}</b>"
                         + (" · " + " · ".join(b["groups"]) if b["groups"] else ""))
            for x in b["rows"]:
                lines.append("<code>" + _pad(x["label"], lw) + " " + x["spark"]
                             + " " + _pad(x["lvl"], vw, True)
                             + (" " + _pad(x["wow"], ww, True) if ww else "")
                             + x["tail"] + "</code>")
        out.append("<b>📊 트렌드 데이터</b> <i>(최근 10주 · 전주비)</i>\n" + "\n".join(lines))

    # 임박 일정
    if soon:
        lines = []
        # 자리를 맞추는 칸은 날짜 하나뿐이다. 날짜는 순수 ASCII 라 고정폭에서 정확히 맞는다.
        # 예전엔 D-day·종류까지 칸을 잡았는데, '오늘' vs 'D-1' 과 '실적' vs 'IR' 처럼
        # 한글과 영문이 섞이면 텔레그램 고정폭 글꼴에서 한글이 정확히 두 배가 아니라
        # 칸 수를 맞춰도 실제 폭이 어긋난다. 그래서 뒤쪽은 자연스럽게 흘려보낸다.
        for e in soon[:6]:
            dd = (datetime.date.fromisoformat(e["date"]) - today).days
            lines.append(f"<code>{e['date'][5:].replace('-', '/')}</code>  <b>{e['co']}</b> "
                         + ("실적" if e["type"] == "earn" else "IR")
                         + " · " + ("오늘" if not dd else f"D-{dd}"))
        out.append("<b>📅 임박 일정</b>\n" + "\n".join(lines))

    # 예매 — 개봉 전 유일한 실시간 지표. 여러 편이면 한 섹션에 묶는다.
    bk = [(nm, p) for nm, p in (mv.get("booking") or {}).items() if p]
    if bk:
        lines = []
        for nm, ptsB in bk:
            p, prv = ptsB[-1], (ptsB[-2] if len(ptsB) > 1 else None)
            dr = f" ({p['rate']-prv['rate']:+.1f}%p)" if prv else " (수집 시작)"
            lines.append(f"<b>{nm.split(':')[0]}</b>  예매율 {p['rate']}%{dr} · "
                         f"예매 {p['book']:,}명")
        out.append("<b>🎬 예매</b>\n" + "\n".join(lines))

    if alerts_only:
        keep = [b for b in out if not b.startswith("<b>📊")]
        head = f"<b>커버리지 알림</b> · {today:%m/%d}({WD[today.weekday()]})"
        return (head + "\n\n" + "\n\n".join(keep)) if keep else ""

    head = f"<b>커버리지 데일리</b> · {today:%m/%d}({WD[today.weekday()]})"
    return (head + "\n\n" + ("\n\n".join(out) if out else "특이사항 없음.")
            + "\n\n<i>coverage-dashboard.pages.dev</i>")


def main():
    html = open(HTML, encoding="utf-8").read()
    msg = build(html, alerts_only=("--alerts" in sys.argv))
    if not msg:
        print("보낼 내용 없음."); return
    if "--dry-run" in sys.argv:
        print("─" * 52); print(re.sub(r"<[^>]+>", "", msg)); print("─" * 52)
        print(f"(dry-run · {len(msg)}자)")
    else:
        if not telegram_send.send(msg):
            sys.exit(1)


if __name__ == "__main__":
    main()
