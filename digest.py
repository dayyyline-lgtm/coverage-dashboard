# -*- coding: utf-8 -*-
"""
텔레그램 데일리 레터 — 대시보드 데이터를 하루 한 번 요약+해석해 폰으로 쏜다.
(실적 서프라이즈 즉시알림은 notify.py 가 담당. 이건 '요약' 담당.)

원칙: 내 커버 종목에 대한 신호만. 경쟁사 키워드(또봇 등)나 피어비교 그룹은 넣지 않는다.

  python digest.py            # 전송
  python digest.py --dry-run  # 전송 없이 출력(검증)
  python digest.py --alerts   # 임박 일정·시세·예매만(짧게)
"""
import re, json, sys, datetime
import telegram_send

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
CHG_ALERT = 5.0
EVENT_DAYS = 7
SPIKE = 25
STREAK_MIN = 3
FLOOR = 5           # 검색량 사실상 없는 계열 컷
WD = ["월", "화", "수", "목", "금", "토", "일"]

# 커버 종목이 '자기 키워드'로 어느 트렌드 그룹에 있나 (경쟁사·피어 그룹은 제외).
# kw=None 은 국가별 그룹 → 대표 국가를 자동으로 뽑는다.
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
# 수출 디제스트에 넣을 품목(내 커버 관련) — 갱신된 날에만 노출
TRADE_ITEMS = ["화장품 전체", "라면", "만두", "리쥬란(강릉 기타화장품)", "창상피복재(안성)"]


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


def _tags(w, st):
    t = []
    if w is not None and abs(w) >= SPIKE:
        t.append("🔥급등" if w > 0 else "❄️급락")
    if abs(st) >= STREAK_MIN:
        t.append(f"{'↗' if st > 0 else '↘'}{abs(st)}주")
    return (", " + "·".join(t)) if t else ""


def _series(gobj, kw):
    prods = gobj.get("products") or []
    ser = gobj.get("naver") or gobj.get("google") or []
    if kw in prods and prods.index(kw) < len(ser):
        return ser[prods.index(kw)]
    return None


def _country_head(gobj):
    """국가별 그룹에서 가장 크게 움직인 국가 (라벨, 최근값, wow, streak)."""
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
            best = (key, (p, last, w, _streak(ser[i])))
    return best[1] if best else None


def _track_rows(tr):
    """TRACK 을 돌며 (종목, 표시라벨, 최근값, wow, streak) 리스트. 신호 없는 건 뺀다."""
    groups = tr.get("groups") or {}
    rows = []
    for stock, gname, kw in TRACK:
        g = groups.get(gname)
        if not g:
            continue
        if kw is None:                     # 국가별 → 대표 국가
            h = _country_head(g)
            if not h:
                continue
            ip = gname.replace(" 국가별", "")
            lab, last, w, st = h
            rows.append((stock, f"{ip} {lab}", last, w, st))
        else:
            s = _series(g, kw)
            last = _last(s) if s else None
            if last is None or last < FLOOR:
                continue
            rows.append((stock, kw, last, _wow(s), _streak(s)))
    rows.sort(key=lambda r: abs(r[3]) if r[3] is not None else 0, reverse=True)
    return rows


def build(html, alerts_only=False):
    today = datetime.datetime.now(KST).date()
    tr = _const(html, "TREND") or {"groups": {}}
    live = _const(html, "LIVE") or {}
    evs = _const(html, "DART_EVENTS", "[") or []
    mv = _const(html, "MOVIE") or {}
    data = _const(html, "DATA") or {"records": []}
    trade = _const(html, "TRADE") or {}
    sub = {r["name"]: r.get("sub", "") for r in data.get("records", [])}

    end = (today + datetime.timedelta(days=EVENT_DAYS)).isoformat()
    soon = sorted([e for e in evs if e.get("type") in ("earn", "ir")
                   and today.isoformat() <= e.get("date", "") <= end], key=lambda e: e["date"])
    movers = sorted([(s.get("chgPct"), nm) for nm, s in (live.get("stocks") or {}).items()
                     if s.get("chgPct") is not None and abs(s["chgPct"]) >= CHG_ALERT],
                    key=lambda x: -abs(x[0]))
    trows = _track_rows(tr)

    # ── 오늘의 포인트 ──
    pts = []
    for e in [x for x in soon if x["type"] == "earn"
              and (datetime.date.fromisoformat(x["date"]) - today).days <= 1][:3]:
        dd = (datetime.date.fromisoformat(e["date"]) - today).days
        pts.append(f"📊 {'오늘' if not dd else '내일'} <b>{e['co']}</b> 실적발표")
    spike = next((r for r in trows if r[3] is not None and abs(r[3]) >= SPIKE), None)
    if spike:
        st, lab, last, w, _s = spike
        pts.append(f"{'🔥' if w > 0 else '❄️'} 검색 {'급등' if w > 0 else '급락'}: <b>{st}</b> {lab} {w:+.0f}%")
    if movers:
        c, nm = movers[0]
        pts.append(f"{'📈' if c > 0 else '📉'} 시세: <b>{nm}</b> {c:+.1f}%"
                   + (f" 외 {len(movers)-1}종목" if len(movers) > 1 else ""))

    out = []
    if pts:
        out.append("<b>〈오늘의 포인트〉</b>\n" + "\n".join("• " + p for p in pts))

    # ── 검색 트렌드(내 종목 키워드만, 중복 없이) ──
    if not alerts_only and trows:
        lines = []
        for st, lab, last, w, s in trows:
            wtag = "" if w is None else f" ({w:+.0f}%{_tags(w, s)})"
            lines.append(f"· <b>{st}</b>: {lab} {last}{wtag}")
        out.append("<b>📊 검색 트렌드</b> <i>(내 종목 키워드·전주비)</i>\n" + "\n".join(lines))

    # ── 임박 일정 ──
    if soon:
        lines = []
        for e in soon[:8]:
            dd = (datetime.date.fromisoformat(e["date"]) - today).days
            tag = "📊실적발표" if e["type"] == "earn" else "🎤IR"
            lines.append(f"· {e['date'][5:]} {'오늘' if not dd else 'D-'+str(dd)} {tag} <b>{e['co']}</b>")
        out.append("<b>📅 임박 일정</b>\n" + "\n".join(lines))

    # ── 시세 급변(섹터 붙여 한 줄씩) ──
    if movers:
        lines = []
        for c, nm in movers[:10]:
            tg = f" <i>{sub[nm]}</i>" if sub.get(nm) else ""
            lines.append(f"· {'🔴' if c > 0 else '🔵'} <b>{nm}</b> {c:+.1f}%{tg}")
        out.append(f"<b>📈 시세 급변 (±{CHG_ALERT:.0f}%+)</b>\n" + "\n".join(lines))

    # ── 수출(관세청 월 데이터 → 월요일 주간 요약으로만. 매일 반복 방지) ──
    weekly = today.weekday() == 0
    if not alerts_only and weekly and trade.get("items"):
        by = {it["label"]: it for it in trade["items"]}
        mon = (trade.get("months") or [""])[-1]
        mlab = f"{mon[:4]}.{mon[4:]}" if len(mon) == 6 else mon
        lines = []
        for lbl in TRADE_ITEMS:
            it = by.get(lbl)
            if not it:
                continue
            exp = (it.get("byCountry") or [{}])[0].get("exp") or []
            idx = [i for i, v in enumerate(exp) if v]
            if not idx:
                continue
            li = idx[-1]
            last = exp[li]
            yoy = ((last / exp[li - 12] - 1) * 100) if (li >= 12 and exp[li - 12]) else None
            lines.append(f"· {lbl}: <b>${last/1e6:,.0f}M</b>" + ("" if yoy is None else f" ({yoy:+.0f}% YoY)"))
        if lines:
            out.append(f"<b>📦 수출 갱신</b> <i>({mlab} 확정)</i>\n" + "\n".join(lines))

    # ── 예매 ──
    for nm, ptsB in (mv.get("booking") or {}).items():
        if not ptsB:
            continue
        p, prev = ptsB[-1], (ptsB[-2] if len(ptsB) > 1 else None)
        dr = f" ({p['rate']-prev['rate']:+.1f}%p)" if prev else " (수집 시작)"
        out.append(f"<b>🎬 {nm}</b>\n· 예매율 <b>{p['rate']}%</b>{dr} · 예매 {p['book']:,}명")

    if alerts_only:
        head = f"⏰ <b>커버리지 알림</b> · {today:%m/%d}({WD[today.weekday()]})"
        # 알림 모드는 일정·시세·예매만
        keep = [b for b in out if not b.startswith("<b>📊 검색")]
        return (head + "\n\n" + "\n\n".join(keep)) if keep else ""

    head = f"🗞 <b>커버리지 데일리</b> · {today:%Y-%m-%d}({WD[today.weekday()]})"
    body = "\n\n".join(out) if out else "특이사항 없음."
    return head + "\n\n" + body + "\n\n<i>coverage-dashboard.pages.dev · 리서치 참고용</i>"


def main():
    html = open(HTML, encoding="utf-8").read()
    msg = build(html, alerts_only=("--alerts" in sys.argv))
    if not msg:
        print("보낼 내용 없음."); return
    if "--dry-run" in sys.argv:
        print("─" * 56); print(re.sub(r"<[^>]+>", "", msg)); print("─" * 56)
        print(f"(dry-run · {len(msg)}자)")
    else:
        telegram_send.send(msg)


if __name__ == "__main__":
    main()
