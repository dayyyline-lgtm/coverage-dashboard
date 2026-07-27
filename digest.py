# -*- coding: utf-8 -*-
"""
텔레그램 데일리 다이제스트 — 대시보드 데이터를 하루 한 번 요약해 폰으로 쏜다.
(실적 서프라이즈 즉시알림은 notify.py 가 따로 담당한다. 이건 '요약' 담당.)

  python digest.py            # 전송 (토큰 있으면)
  python digest.py --dry-run  # 전송 없이 메시지만 출력(검증용)
  python digest.py --alerts   # 임박 일정·시세 급변·예매만(짧은 알림)

데이터는 public/index.html 의 상수(TREND/MOVIE/DART_EVENTS/LIVE)에서 읽는다 — API 재조회 없음.
"""
import re, json, sys, datetime
import telegram_send

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
CHG_ALERT = 5.0        # 시세 급변 임계(%)
EVENT_DAYS = 7         # 임박 일정 범위(일)


def _const(html, name, br="{"):
    cl = "}" if br == "{" else "]"
    m = re.search(r"const %s\s*=\s*(\%s.*?\%s);" % (re.escape(name), br, cl), html, re.S)
    return json.loads(m.group(1)) if m else None


def _wow(series):
    s = [v for v in series if v is not None]
    if len(s) < 2 or not s[-2]:
        return None
    return (s[-1] / s[-2] - 1) * 100


def build(html, alerts_only=False):
    today = datetime.datetime.now(KST).date()
    out = []

    # ── 임박 일정(실적발표/IR, 7일) ──
    evs = _const(html, "DART_EVENTS", "[") or []
    end = (today + datetime.timedelta(days=EVENT_DAYS)).isoformat()
    soon = [e for e in evs if e.get("type") in ("earn", "ir")
            and today.isoformat() <= e.get("date", "") <= end]
    soon.sort(key=lambda e: e["date"])
    if soon:
        lines = []
        for e in soon[:10]:
            dd = (datetime.date.fromisoformat(e["date"]) - today).days
            tag = "📊실적발표" if e["type"] == "earn" else "🎤IR"
            lines.append(f"· {e['date'][5:]} ({'오늘' if not dd else 'D-'+str(dd)}) {tag} <b>{e['co']}</b>")
        out.append("<b>📅 임박 일정 (7일)</b>\n" + "\n".join(lines))

    # ── 시세 급변 ──
    live = _const(html, "LIVE") or {}
    movers = [(s.get("chgPct"), nm) for nm, s in (live.get("stocks") or {}).items()
              if s.get("chgPct") is not None and abs(s["chgPct"]) >= CHG_ALERT]
    movers.sort(key=lambda x: -abs(x[0]))
    if movers:
        out.append("<b>📈 시세 급변 (±%.0f%%+)</b>\n" % CHG_ALERT
                   + "\n".join(f"· {'🔴' if c > 0 else '🔵'} <b>{nm}</b> {c:+.1f}%" for c, nm in movers[:12]))

    # ── 하츄핑2 예매(개봉 전 선행지표) ──
    mv = _const(html, "MOVIE") or {}
    for nm, pts in (mv.get("booking") or {}).items():
        if not pts:
            continue
        p, prev = pts[-1], (pts[-2] if len(pts) > 1 else None)
        drate = f" ({p['rate']-prev['rate']:+.1f}%p)" if prev else ""
        out.append(f"<b>🎬 {nm}</b>\n· 예매율 <b>{p['rate']}%</b>{drate} · 예매 {p['book']:,}명")

    if alerts_only:
        head = f"⏰ <b>커버리지 알림</b> · {today.strftime('%m/%d')}"
        return (head + "\n\n" + "\n\n".join(out)) if out else ""

    # ── 검색 트렌드 요약(전체 다이제스트에만) ──
    tr = _const(html, "TREND")
    if tr and tr.get("groups"):
        blocks = []
        for gname, g in tr["groups"].items():
            series = g.get("naver") or g.get("google") or []
            prods = g.get("products") or []
            rows = []
            for i, pr in enumerate(prods):
                if i >= len(series):
                    continue
                last = next((v for v in reversed(series[i]) if v is not None), None)
                if last is not None:
                    rows.append((last, pr, _wow(series[i])))
            rows.sort(key=lambda x: -x[0])
            if rows:
                inner = " · ".join(f"{pr} {last}{'' if w is None else f'({w:+.0f}%)'}"
                                   for last, pr, w in rows[:4])
                blocks.append(f"· <b>{gname}</b>: {inner}")
        if blocks:
            out.insert(0, "<b>📊 검색 트렌드</b> <i>(최근값·전주비)</i>\n" + "\n".join(blocks))

    head = f"🗞 <b>커버리지 데일리</b> · {today.strftime('%Y-%m-%d')}"
    body = "\n\n".join(out) if out else "특이사항 없음."
    return head + "\n\n" + body + "\n\n<i>coverage-dashboard.pages.dev</i>"


def main():
    html = open(HTML, encoding="utf-8").read()
    msg = build(html, alerts_only=("--alerts" in sys.argv))
    if not msg:
        print("보낼 내용 없음."); return
    if "--dry-run" in sys.argv:
        print("─" * 54); print(re.sub(r"<[^>]+>", "", msg)); print("─" * 54)
        print(f"(dry-run · {len(msg)}자 · 전송 안 함)")
    else:
        telegram_send.send(msg)


if __name__ == "__main__":
    main()
