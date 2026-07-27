# -*- coding: utf-8 -*-
"""
텔레그램 데일리 레터 — 중요한 신호만 간결하게.
(실적 서프라이즈=notify.py, 월간 수출=trade_digest.py 가 담당. 여긴 매일 요약.)

원칙:
  - 검색 트렌드: 소비재 브랜드/제품처럼 '검색=수요 선행'인 것 위주. 게임 국가별 자가정규화(0~100)
    노이즈는 뺀다. '의미있게 움직인' 것만(전주비 기준 명시).
  - 시세 급변(전일)엔 '왜 움직였나'를 준다. 실적발표면 실제치 vs consSnap 컨센을 계산해
    상회/하회 × 주가방향으로 호실적반영/부진/셀온/악재선반영까지 판정(_surprise).
    발표 전이면 관련 뉴스 헤드라인. ANTHROPIC_API_KEY 를 넣으면 Claude(웹서치)로 추론
    (analyze.py)하지만, 안 넣어도 규칙기반으로 조용히 돈다.
  - 카테고리: 소비재는 세부(화장품/미용/음식료/유통), 엔터·게임·호텔은 섹터.
  - 방향은 ▲(상승, 한국식 빨강)·▼(하락) 로.

  python digest.py            # 전송
  python digest.py --dry-run  # 출력만
  python digest.py --alerts   # 일정·시세만(짧게)
"""
import re, json, sys, datetime
import telegram_send
import analyze

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
CHG_ALERT = 5.0
EVENT_DAYS = 7
NOTABLE_WOW = 15      # 트렌드 '의미있는' 전주비(%)
NOTABLE_BASE = 15     # 검색량 기저(이 미만은 노이즈)
SPIKE = 30            # 급등/급락 태그
STREAK_MIN = 4        # 연속추세 태그(주)
BLK = "▁▂▃▄▅▆▇█"
WD = ["월", "화", "수", "목", "금", "토", "일"]

# 검색이 실적 선행지표인 '내 종목 단일 키워드'만. (아이온2·티니핑 국가별은 노이즈라 데일리 제외)
TRACK = [
    ("파마리서치", "스킨부스터", "리쥬란"),
    ("에이피알", "K-뷰티 브랜드", "메디큐브"),
    ("달바글로벌", "K-뷰티 브랜드", "달바"),
    ("리센스메디컬", "쿨로아600", "쿨로아600"),
    ("크래프톤", "배틀그라운드(크래프톤)", "배틀그라운드"),
    ("펄어비스", "펄어비스 IP", "붉은사막"),
    ("시프트업", "시프트업 IP", "니케"),
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
    """의미있게 움직인 트렌드만 (전주비 큰/연속추세). (종목, 키워드, 시계열, wow, streak)."""
    groups = tr.get("groups") or {}
    rows = []
    for stock, gname, kw in TRACK:
        g = groups.get(gname)
        s = _series(g, kw) if g else None
        if not s:
            continue
        last, w, st = _last(s), _wow(s), _streak(s)
        if last is None or last < NOTABLE_BASE:
            continue
        if (w is not None and abs(w) >= NOTABLE_WOW) or abs(st) >= STREAK_MIN:
            rows.append((stock, kw, s, w, st))
    rows.sort(key=lambda r: abs(r[3] or 0), reverse=True)
    return rows


def _arw(c):
    """등락 방향 — 한국식 색(상승 빨강·하락 파랑). 텔레그램은 이모지로만 색이 되므로 네모+삼각형."""
    return "🟥▲" if c > 0 else "🟦▼"


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
    return t[:36] + "…" if len(t) > 37 else t


def _news_all(items, name, cut, k=4):
    """LLM 근거용 — 창 내 관련 헤드라인 여러 개(최신순)."""
    cand = [x for x in items if _match(x, name) and x.get("d", "")[:10] >= cut]
    cand.sort(key=lambda x: x.get("d", ""), reverse=True)
    return " / ".join(f"({x['d'][5:10]}) {x['t']}" for x in cand[:k]) if cand else ""


def _disc(evs, name, cut, today):
    """LLM 근거용 — 창 내(직전 영업일~오늘) 이 종목 공시/실적 일정."""
    lo, hi = cut, today.isoformat()
    ds = [e for e in evs if e.get("co") == name and lo <= e.get("date", "") <= hi]
    ds.sort(key=lambda e: e.get("date", ""), reverse=True)
    out = [f"{e['date']} [{'실적' if e.get('type') == 'earn' else 'IR/공시'}] {e.get('title', '')}"
           for e in ds[:4]]
    return " / ".join(out)


def _cons(live, name):
    """LLM 근거용 — 컨센 스냅샷(당분기 매출·영익)과 밸류에이션. 실적 재료 해석에 쓴다."""
    s = (live.get("stocks") or {}).get(name) or {}
    snap = (live.get("consSnap") or {}).get(name) or {}
    parts = []
    if snap:
        q, v = sorted(snap.items())[-1]
        parts.append(f"{q[:4]}.{q[4:]} 컨센 매출 {v.get('rev')}십억·영익 {v.get('op')}십억")
    if s.get("price") and s.get("consTarget"):
        up = (s["consTarget"] / s["price"] - 1) * 100
        parts.append(f"현재가 {s['price']:,.0f}·컨센목표 {s['consTarget']:,.0f}({up:+.0f}%)")
    if s.get("cnsPer"):
        parts.append(f"12MF PER {s['cnsPer']:.1f}배")
    return " · ".join(parts)


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

    # 급변 종목 '왜' 추론 — 공시·컨센·뉴스를 근거로 Claude(웹서치)가 한 줄. 상위 6종목만.
    # API 미설정/실패면 reasons 는 비고, _why() 가 뉴스 헤드라인으로 폴백한다.
    reasons = {}
    if not alerts_only and analyze.available():
        for c, nm in movers[:6]:
            reasons[nm] = analyze.reason(
                nm, c, _cat(rec, nm), today.isoformat(),
                _disc(evs, nm, news_cut, today), _cons(live, nm),
                _news_all(nitems, nm, news_cut))

    chg_of = {nm: c for c, nm in movers}

    def _rule_why(nm):
        """키 없이 도는 규칙기반 이유. 실적발표면 '컨센 대비 상회/하회 × 주가방향'으로
           호실적반영/부진/셀온/악재선반영까지 판정(_surprise). 발표 전이면 헤드라인."""
        head = _news(nitems, nm, news_cut)
        disc = [e for e in evs if e.get("co") == nm and news_cut <= e.get("date", "") <= today.isoformat()]
        if any(e.get("type") == "earn" for e in disc):
            sur = _surprise(live, nm, chg_of.get(nm, 0), today)
            if sur:
                return sur                                   # 실제치 vs 컨센이 잡히면 그 해석이 이유
            return f"실적발표 · {head}" if head else "실적발표"  # 발표됐지만 실제치 아직(데이터 랙)
        return head

    def _why(nm):
        return reasons.get(nm) or _rule_why(nm)

    # 오늘의 포인트
    pts = []
    for e in [x for x in soon if x["type"] == "earn"
              and (datetime.date.fromisoformat(x["date"]) - today).days <= 1][:2]:
        dd = (datetime.date.fromisoformat(e["date"]) - today).days
        pts.append(f"📊 {'오늘' if not dd else '내일'} <b>{e['co']}</b> 실적발표")
    sp = next((r for r in notable if r[3] is not None and abs(r[3]) >= SPIKE), None)
    if sp:
        st, kw, s, w, _s = sp
        pts.append(f"{'🔥' if w > 0 else '❄️'} 검색 {'급등' if w > 0 else '급락'}: <b>{st}</b> {kw} 전주비 {w:+.0f}%")
    if movers:
        c, nm = movers[0]
        rs = _why(nm)
        pts.append(f"{_arw(c)} <b>{nm}</b> {c:+.1f}%" + (f" — {rs}" if rs else ""))

    out = []
    if pts:
        out.append("<b>〈오늘의 포인트〉</b>\n" + "\n".join("• " + p for p in pts))

    # 검색 트렌드 — 의미있게 움직인 것만(전주비), 최근 10주 추이
    if not alerts_only and notable:
        lines = []
        for st, kw, s, w, streak in notable[:5]:
            tag = []
            if w is not None and abs(w) >= SPIKE:
                tag.append("🔥급등" if w > 0 else "❄️급락")
            if abs(streak) >= STREAK_MIN:
                tag.append(f"{'↗' if streak > 0 else '↘'}{abs(streak)}주")
            tg = (" " + "·".join(tag)) if tag else ""
            wtxt = "" if w is None else f" 전주비 {w:+.0f}%"
            lines.append(f"· <b>{st}</b> {kw} <code>{_spark(s)}</code>{wtxt}{tg}")
        out.append("<b>📊 검색 트렌드</b> <i>(수요 선행 · 전주비, 최근 10주)</i>\n" + "\n".join(lines))

    # 임박 일정
    if soon:
        lines = []
        for e in soon[:6]:
            dd = (datetime.date.fromisoformat(e["date"]) - today).days
            tag = "📊실적" if e["type"] == "earn" else "🎤IR"
            lines.append(f"· {e['date'][5:]} {'오늘' if not dd else 'D-'+str(dd)} {tag} <b>{e['co']}</b>")
        out.append("<b>📅 임박 일정</b>\n" + "\n".join(lines))

    # 전일 시세 급변 — 카테고리 + 관련 뉴스(이유)
    if movers:
        lines = []
        for c, nm in movers[:6]:
            cat = _cat(rec, nm)
            rs = _why(nm)
            base = f"{_arw(c)} <b>{nm}</b> {c:+.1f}%" + (f" <i>{cat}</i>" if cat else "")
            lines.append(base + (f"\n   └ {rs}" if rs else ""))
        extra = f"\n<i>…외 {len(movers)-6}종목</i>" if len(movers) > 6 else ""
        out.append(f"<b>📈 전일 시세 급변 (±{CHG_ALERT:.0f}%+)</b>\n" + "\n".join(lines) + extra)

    # 예매
    for nm, ptsB in (mv.get("booking") or {}).items():
        if not ptsB:
            continue
        p, prev = ptsB[-1], (ptsB[-2] if len(ptsB) > 1 else None)
        dr = f" ({p['rate']-prev['rate']:+.1f}%p)" if prev else " (수집 시작)"
        out.append(f"<b>🎬 {nm.split(':')[0]}</b> · 예매율 <b>{p['rate']}%</b>{dr} · 예매 {p['book']:,}명")

    if alerts_only:
        keep = [b for b in out if not b.startswith("<b>📊 검색")]
        head = f"⏰ <b>커버리지 알림</b> · {today:%m/%d}({WD[today.weekday()]})"
        return (head + "\n\n" + "\n\n".join(keep)) if keep else ""

    head = f"🗞 <b>커버리지 데일리</b> · {today:%m/%d}({WD[today.weekday()]})"
    return head + "\n\n" + ("\n\n".join(out) if out else "특이사항 없음.") + "\n\n<i>coverage-dashboard.pages.dev</i>"


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
