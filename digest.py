# -*- coding: utf-8 -*-
"""
텔레그램 데일리 레터 — 대시보드 데이터를 하루 한 번, 간결하게 요약+해석.
(실적 서프라이즈=notify.py, 월간 수출=trade_digest.py 가 따로 담당. 여긴 매일 요약.)

원칙: 내 커버 종목 신호만. 경쟁사 키워드·피어그룹·수출(월데이터)은 넣지 않는다.
추이는 스파크라인(▁▂▃▅▇)으로 한눈에.

  python digest.py            # 전송
  python digest.py --dry-run  # 출력만
  python digest.py --alerts   # 일정·시세·예매만(짧게)
"""
import re, json, sys, datetime
import telegram_send

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
CHG_ALERT = 5.0
EVENT_DAYS = 7
SPIKE = 25
STREAK_MIN = 3
FLOOR = 5
BLK = "▁▂▃▄▅▆▇█"
WD = ["월", "화", "수", "목", "금", "토", "일"]

# 커버 종목이 '자기 키워드'로 있는 트렌드 그룹만 (경쟁사·피어 제외). kw=None → 국가별(대표국가 자동).
TRACK = [
    ("파마리서치", "스킨부스터", "리쥬란"),
    ("에이피알", "K-뷰티 브랜드", "메디큐브"),
    ("달바글로벌", "K-뷰티 브랜드", "달바"),
    ("리센스메디컬", "쿨로아600", "쿨로아600"),
    ("크래프톤", "배틀그라운드(크래프톤)", "배틀그라운드"),
    ("펄어비스", "펄어비스 IP", "붉은사막"),
    ("시프트업", "시프트업 IP", "니케"),
    ("NC", "아이온2 국가별", None),
    ("SAMG엔터", "티니핑 국가별", None),
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


def _tags(w, st):
    t = []
    if w is not None and abs(w) >= SPIKE:
        t.append("🔥급등" if w > 0 else "❄️급락")
    if abs(st) >= STREAK_MIN:
        t.append(f"{'↗' if st > 0 else '↘'}{abs(st)}주")
    return "·".join(t)


def _series(gobj, kw):
    prods = gobj.get("products") or []
    ser = gobj.get("naver") or gobj.get("google") or []
    if kw in prods and prods.index(kw) < len(ser):
        return ser[prods.index(kw)]
    return None


def _country_head(gobj):
    prods = gobj.get("products") or []
    ser = gobj.get("naver") or gobj.get("google") or []
    best = None
    for i, p in enumerate(prods):
        if i >= len(ser):
            continue
        last = _last(ser[i])
        if last is None or last < FLOOR:
            continue
        w = _wow(ser[i])
        key = (abs(w) if w is not None else 0, last)
        if best is None or key > best[0]:
            best = (key, (p, ser[i]))
    return best[1] if best else None


def _track_rows(tr):
    """(종목, 표시라벨, 시계열) 리스트. 신호 없는 건 제외, 전주비 큰 순."""
    groups = tr.get("groups") or {}
    rows = []
    for stock, gname, kw in TRACK:
        g = groups.get(gname)
        if not g:
            continue
        if kw is None:
            h = _country_head(g)
            if not h:
                continue
            lab, s = f"{gname.replace(' 국가별', '')} {h[0]}", h[1]
        else:
            s = _series(g, kw)
            if not s or (_last(s) or 0) < FLOOR:
                continue
            lab = kw
        rows.append((stock, lab, s))
    rows.sort(key=lambda r: abs(_wow(r[2]) or 0), reverse=True)
    return rows


def build(html, alerts_only=False):
    today = datetime.datetime.now(KST).date()
    tr = _const(html, "TREND") or {"groups": {}}
    live = _const(html, "LIVE") or {}
    evs = _const(html, "DART_EVENTS", "[") or []
    mv = _const(html, "MOVIE") or {}
    data = _const(html, "DATA") or {"records": []}
    sub = {r["name"]: r.get("sub", "") for r in data.get("records", [])}

    end = (today + datetime.timedelta(days=EVENT_DAYS)).isoformat()
    soon = sorted([e for e in evs if e.get("type") in ("earn", "ir")
                   and today.isoformat() <= e.get("date", "") <= end], key=lambda e: e["date"])
    movers = sorted([(s.get("chgPct"), nm) for nm, s in (live.get("stocks") or {}).items()
                     if s.get("chgPct") is not None and abs(s["chgPct"]) >= CHG_ALERT],
                    key=lambda x: -abs(x[0]))
    trows = _track_rows(tr)

    # 오늘의 포인트
    pts = []
    for e in [x for x in soon if x["type"] == "earn"
              and (datetime.date.fromisoformat(x["date"]) - today).days <= 1][:2]:
        dd = (datetime.date.fromisoformat(e["date"]) - today).days
        pts.append(f"📊 {'오늘' if not dd else '내일'} <b>{e['co']}</b> 실적발표")
    for st, lab, s in trows:
        w = _wow(s)
        if w is not None and abs(w) >= SPIKE:
            pts.append(f"{'🔥' if w > 0 else '❄️'} 검색 {'급등' if w > 0 else '급락'}: <b>{st}</b> {lab} {w:+.0f}%")
            break
    if movers:
        c, nm = movers[0]
        pts.append(f"{'📈' if c > 0 else '📉'} 시세: <b>{nm}</b> {c:+.1f}%"
                   + (f" 외 {len(movers)-1}" if len(movers) > 1 else ""))

    out = []
    if pts:
        out.append("<b>〈오늘의 포인트〉</b>\n" + "\n".join("• " + p for p in pts))

    # 검색 트렌드 (내 종목 키워드 · 스파크라인 · 전주비)
    if not alerts_only and trows:
        lines = []
        for st, lab, s in trows:
            w, tg = _wow(s), _tags(_wow(s) or 0, _streak(s))
            wtxt = "" if w is None else f" {w:+.0f}%"
            tgt = f" {tg}" if tg else ""
            lines.append(f"· <b>{st}</b> {lab} <code>{_spark(s)}</code>{wtxt}{tgt}")
        out.append("<b>📊 검색 트렌드</b> <i>(내 종목 키워드, 최근 10주)</i>\n" + "\n".join(lines))

    # 임박 일정
    if soon:
        lines = []
        for e in soon[:6]:
            dd = (datetime.date.fromisoformat(e["date"]) - today).days
            tag = "📊실적" if e["type"] == "earn" else "🎤IR"
            lines.append(f"· {e['date'][5:]} {'오늘' if not dd else 'D-'+str(dd)} {tag} <b>{e['co']}</b>")
        out.append("<b>📅 임박 일정</b>\n" + "\n".join(lines))

    # 시세 급변 (섹터 태그, 한 줄씩, 상위 6)
    if movers:
        lines = [f"· {'🔴' if c > 0 else '🔵'} <b>{nm}</b> {c:+.1f}%"
                 + (f" <i>{sub[nm]}</i>" if sub.get(nm) else "") for c, nm in movers[:6]]
        extra = f"\n<i>…외 {len(movers)-6}종목</i>" if len(movers) > 6 else ""
        out.append(f"<b>📈 시세 급변 (±{CHG_ALERT:.0f}%+)</b>\n" + "\n".join(lines) + extra)

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
        telegram_send.send(msg)


if __name__ == "__main__":
    main()
