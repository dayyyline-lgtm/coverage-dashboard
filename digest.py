# -*- coding: utf-8 -*-
"""
텔레그램 데일리 레터 — 대시보드 데이터를 하루 한 번 요약+해석해 폰으로 쏜다.
(실적 서프라이즈 즉시알림은 notify.py 가 따로 담당한다. 이건 '요약' 담당.)

  python digest.py            # 전송 (토큰 있으면)
  python digest.py --dry-run  # 전송 없이 메시지만 출력(검증용)
  python digest.py --alerts   # 임박 일정·시세 급변·예매만(짧은 알림)

데이터는 public/index.html 의 상수(TREND/MOVIE/DART_EVENTS/LIVE)에서 읽는다 — API 재조회 없음.
숫자만 나열하지 않고, '오늘의 포인트'(자동 하이라이트) + 트렌드 급등/급락·연속추세 해석을 붙인다.
"""
import re, json, sys, datetime
import telegram_send

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
CHG_ALERT = 5.0        # 시세 급변 임계(%)
EVENT_DAYS = 7         # 임박 일정 범위(일)
SPIKE = 25             # 검색 트렌드 '급등/급락' 임계(전주비 %)
STREAK_MIN = 3         # 연속추세로 볼 최소 주 수
WD = ["월", "화", "수", "목", "금", "토", "일"]

# 트렌드 그룹 -> 커버 종목. index.html 의 TREND_STOCK 을 그룹 기준으로 뒤집은 것(그게 원본).
GROUP_STOCK = {
    "K-뷰티 브랜드": "에이피알·달바글로벌", "스킨부스터": "파마리서치",
    "쿨로아600": "리센스메디컬", "티니핑 국가별": "SAMG엔터",
    "변신로봇 IP": "SAMG엔터", "변신로봇 IP 러시아": "SAMG엔터",
    "아이온2 국가별": "NC", "배틀그라운드(크래프톤)": "크래프톤",
    "펄어비스 IP": "펄어비스", "시프트업 IP": "시프트업",
}
def _stock(g):
    return GROUP_STOCK.get(g, "커버외")


def _const(html, name, br="{"):
    cl = "}" if br == "{" else "]"
    m = re.search(r"const %s\s*=\s*(\%s.*?\%s);" % (re.escape(name), br, cl), html, re.S)
    return json.loads(m.group(1)) if m else None


def _clean(series):
    return [v for v in series if v is not None]


def _wow(series):
    s = _clean(series)
    if len(s) < 2 or not s[-2]:
        return None
    return (s[-1] / s[-2] - 1) * 100


def _streak(series):
    """끝에서부터 같은 방향(증/감) 연속 주 수. +면 상승연속, -면 하락연속."""
    s = _clean(series)
    if len(s) < 2:
        return 0
    up = s[-1] > s[-2]
    n = 0
    for i in range(len(s) - 1, 0, -1):
        if (s[i] > s[i - 1]) == up and s[i] != s[i - 1]:
            n += 1
        else:
            break
    return n if up else -n


HEAD_MIN = 12          # 헤드라인 후보 최소 최근값(작은 기저의 ±50% 잡음 배제)


def _headline(g):
    """그룹 대표 계열을 뽑아 (라벨, 최근값, wow, streak) 반환.
       최근값이 어느 정도 있는(기저가 큰) 계열 중 가장 크게 움직인 것을 우선.
       그런 계열이 없으면 최근값 최대 계열로 대체."""
    series = g.get("naver") or g.get("google") or []
    prods = g.get("products") or []
    cand = []
    for i, pr in enumerate(prods):
        if i >= len(series):
            continue
        s = series[i]
        last = next((v for v in reversed(s) if v is not None), None)
        if last is None:
            continue
        cand.append((pr, last, _wow(s), _streak(s)))
    if not cand:
        return None
    big = [c for c in cand if c[1] >= HEAD_MIN]
    if big:
        return max(big, key=lambda c: (abs(c[2]) if c[2] is not None else 0, c[1]))
    return max(cand, key=lambda c: c[1])          # 다 작으면 최근값 최대


def build(html, alerts_only=False):
    today = datetime.datetime.now(KST).date()
    tr = _const(html, "TREND") or {"groups": {}}
    live = _const(html, "LIVE") or {}
    evs = _const(html, "DART_EVENTS", "[") or []
    mv = _const(html, "MOVIE") or {}

    # ── 재료 계산 ──
    end = (today + datetime.timedelta(days=EVENT_DAYS)).isoformat()
    soon = sorted([e for e in evs if e.get("type") in ("earn", "ir")
                   and today.isoformat() <= e.get("date", "") <= end], key=lambda e: e["date"])
    movers = sorted([(s.get("chgPct"), nm) for nm, s in (live.get("stocks") or {}).items()
                     if s.get("chgPct") is not None and abs(s["chgPct"]) >= CHG_ALERT],
                    key=lambda x: -abs(x[0]))
    # 그룹별 헤드라인
    heads = {g: _headline(obj) for g, obj in (tr.get("groups") or {}).items()}
    heads = {g: h for g, h in heads.items() if h}

    # ── 오늘의 포인트(자동 하이라이트) ──
    pts = []
    imminent = [e for e in soon if (datetime.date.fromisoformat(e["date"]) - today).days <= 1 and e["type"] == "earn"]
    for e in imminent[:3]:
        dd = (datetime.date.fromisoformat(e["date"]) - today).days
        pts.append(f"📊 {'오늘' if not dd else '내일'} <b>{e['co']}</b> 실적발표")
    spike = max(heads.items(), key=lambda kv: abs(kv[1][2]) if kv[1][2] is not None else 0, default=None)
    if spike and spike[1][2] is not None and abs(spike[1][2]) >= SPIKE:
        g, (lab, last, w, st) = spike
        pts.append(f"{'🔥' if w > 0 else '❄️'} 검색 {'급등' if w > 0 else '급락'}: <b>{_stock(g)}</b> · {g} {lab} {w:+.0f}%")
    if movers:
        c, nm = movers[0]
        pts.append(f"{'📈' if c > 0 else '📉'} 시세: <b>{nm}</b> {c:+.1f}%" + (f" 외 {len(movers)-1}종목" if len(movers) > 1 else ""))

    out = []
    if pts:
        out.append("<b>〈오늘의 포인트〉</b>\n" + "\n".join("• " + p for p in pts))

    # ── 임박 일정 ──
    if soon:
        lines = []
        for e in soon[:8]:
            dd = (datetime.date.fromisoformat(e["date"]) - today).days
            tag = "📊실적발표" if e["type"] == "earn" else "🎤IR"
            lines.append(f"· {e['date'][5:]} {'오늘' if not dd else 'D-'+str(dd)} {tag} <b>{e['co']}</b>")
        out.append("<b>📅 임박 일정</b>\n" + "\n".join(lines))

    # ── 시세 급변 ──
    if movers:
        up = [f"🔴{nm} +{c:.1f}%" for c, nm in movers if c > 0][:8]
        dn = [f"🔵{nm} {c:.1f}%" for c, nm in movers if c < 0][:6]
        seg = []
        if up:
            seg.append("상승 " + " · ".join(up))
        if dn:
            seg.append("하락 " + " · ".join(dn))
        out.append(f"<b>📈 시세 급변 (±{CHG_ALERT:.0f}%+)</b>\n" + "\n".join(seg))

    # ── 예매(개봉 전 선행지표) ──
    for nm, ptsB in (mv.get("booking") or {}).items():
        if not ptsB:
            continue
        p, prev = ptsB[-1], (ptsB[-2] if len(ptsB) > 1 else None)
        dr = f" ({p['rate']-prev['rate']:+.1f}%p)" if prev else " (수집 시작)"
        out.append(f"<b>🎬 {nm}</b>\n· 예매율 <b>{p['rate']}%</b>{dr} · 예매 {p['book']:,}명")

    if alerts_only:
        head = f"⏰ <b>커버리지 알림</b> · {today:%m/%d}({WD[today.weekday()]})"
        return (head + "\n\n" + "\n\n".join(out)) if out else ""

    # ── 검색 트렌드(해석 붙여, 많이 움직인 순) ──
    def interp(w, st):
        t = []
        if w is not None and abs(w) >= SPIKE:
            t.append("🔥급등" if w > 0 else "❄️급락")
        if abs(st) >= STREAK_MIN:
            t.append(f"{'↗' if st > 0 else '↘'}{abs(st)}주")
        return (" " + "·".join(t)) if t else ""
    rows = sorted(heads.items(),
                  key=lambda kv: abs(kv[1][2]) if kv[1][2] is not None else 0, reverse=True)
    tl = []
    for g, (lab, last, w, st) in rows:
        if last < 5:                              # 검색량 사실상 없는 그룹은 생략
            continue
        wtxt = "" if w is None else f" {w:+.0f}%"
        tl.append(f"· <b>{_stock(g)}</b> · {g}: {lab} {last}{wtxt}{interp(w, st)}")
    if tl:
        out.insert(0 if not pts else 1, "<b>📊 검색 트렌드</b> <i>(대표 계열·전주비, 움직인 순)</i>\n" + "\n".join(tl))

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
        print(f"(dry-run · {len(msg)}자 · 전송 안 함)")
    else:
        telegram_send.send(msg)


if __name__ == "__main__":
    main()
