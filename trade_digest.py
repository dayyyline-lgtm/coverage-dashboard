# -*- coding: utf-8 -*-
"""
텔레그램 수출 월간 레터 — 관세청 품목별·시군구 통관이 갱신되면(월 1회) 정리해 보낸다.

관세청 확정 품목별 데이터는 매월 15일경 '전월까지' 현행화된다.
그래서 새 '최근월'이 TRADE 에 잡히면 그때 1번만 발송한다(상태파일로 중복 방지).

  python trade_digest.py             # 새 월이면 전송
  python trade_digest.py --dry-run   # 출력만
  python trade_digest.py --force     # 상태 무시하고 전송
"""
import re, json, os, sys
import telegram_send

HTML = "public/index.html"
STATE = "trade_sent.json"
BLK = "▁▂▃▄▅▆▇█"

# 국가 전체 기준으로 보여줄 품목 (라벨, 설명/커버종목)
ITEMS = [
    ("화장품 전체", "화장품 ODM·브랜드"),
    ("기초", "스킨케어(330499)"),
    ("색조-립", "색조"),
    ("마스크팩류", "마스크팩"),
    ("라면", "삼양·농심"),
    ("만두", "CJ제일제당"),
]
# 시군구 프록시(커버 종목 직결)
REGION = [
    ("리쥬란(강릉 기타화장품)", "파마리서치"),
    ("창상피복재(안성)", "티앤엘"),
]


def _const(html, name):
    """index.html 의 상수 블록을 읽는다.

       TRADE 처럼 스크립트가 쓰는 블록은 순수 JSON 이지만,
       TRADE_FLASH 처럼 손으로 적는 블록에는 주석과 끝 쉼표가 들어간다.
       자바스크립트는 받아 주고 JSON 은 거부하므로 여기서 떼어 낸다."""
    m = re.search(r"const %s\s*=\s*(\{.*?\n\});" % re.escape(name), html, re.S) \
        or re.search(r"const %s\s*=\s*(\{.*?\});" % re.escape(name), html, re.S)
    if not m:
        return None
    s = m.group(1)
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)      # 블록 주석
    s = re.sub(r"(?m)//.*$", "", s)                  # 줄 주석
    s = re.sub(r",(\s*[}\]])", r"\1", s)             # 끝 쉼표
    return json.loads(s)


def _spark(vals, n=12):
    c = [v for v in vals if v][-n:]
    if len(c) < 2:
        return ""
    lo, hi = min(c), max(c)
    if hi == lo:
        return BLK[3] * len(c)
    return "".join(BLK[min(7, int((v - lo) / (hi - lo) * 7 + 0.5))] for v in c)


def _stats(exp):
    """최근월값, MoM, YoY (달러 기준). exp 는 월별(None 포함)."""
    idx = [i for i, v in enumerate(exp) if v]
    if not idx:
        return None
    li = idx[-1]
    last = exp[li]
    prev = exp[li - 1] if li >= 1 and exp[li - 1] else None
    yoy_b = exp[li - 12] if li >= 12 and exp[li - 12] else None
    mom = (last / prev - 1) * 100 if prev else None
    yoy = (last / yoy_b - 1) * 100 if yoy_b else None
    return last, mom, yoy, li


def _line(label, note, exp):
    s = _stats(exp)
    if not s:
        return None
    last, mom, yoy, li = s
    mm = "" if mom is None else f" MoM {mom:+.0f}%"
    yy = "" if yoy is None else f" · YoY {yoy:+.0f}%"
    spk = _spark(exp)
    return f"· <b>{label}</b> ${last/1e6:,.0f}M{mm}{yy}\n  <code>{spk}</code> <i>{note}</i>"


def _last_filled(trade):
    """값이 실제로 있는 마지막 달.

       months[-1] 을 그대로 쓰면 안 된다. 관세청 API 는 아직 집계 안 된 달도
       빈 값으로 돌려줘서, 헤더만 '202607 확정'이라 적고 본문 숫자는 202606 인
       레터가 나갔던 적이 있다."""
    months = trade.get("months") or []
    filled = set()
    for it in (trade.get("items") or []):
        exp = (it.get("byCountry") or [{}])[0].get("exp") or []
        for i, v in enumerate(exp):
            if v and i < len(months):
                filled.add(months[i])
    return max(filled) if filled else (months[-1] if months else "")


def build(trade):
    mon = _last_filled(trade)
    mlab = f"{mon[:4]}.{mon[4:]}" if len(mon) == 6 else mon
    by = {it["label"]: it for it in (trade.get("items") or [])}

    def block(items):
        out = []
        for lbl, note in items:
            it = by.get(lbl)
            if not it:
                continue
            exp = (it.get("byCountry") or [{}])[0].get("exp") or []
            ln = _line(lbl, note, exp)
            if ln:
                out.append(ln)
        return out

    parts = [f"📦 <b>수출 월간 리포트</b> · {mlab} 확정",
             "<i>관세청 품목별·시군구 통관 · 전월비(MoM)·전년동월비(YoY)·최근 12개월</i>"]
    b1 = block(ITEMS)
    if b1:
        parts.append("<b>품목(전국)</b>\n" + "\n".join(b1))
    b2 = block(REGION)
    if b2:
        parts.append("<b>커버 종목 프록시(제조지 기준)</b>\n" + "\n".join(b2))
    parts.append(f"<i>수집 {trade.get('asOf','')}</i>")
    return mon, "\n\n".join(parts)


def _w(s):
    """표시 폭 — 한글은 두 칸. 고정폭 칸을 맞출 때 글자 수로 세면 어긋난다."""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _vspark(vals):
    """세로 블록 스파크라인 — 트렌드 레터와 같은 표기법.
       가로 막대로 '크기'를 그려 봤지만, 이 레터에서 알고 싶은 건 크기가 아니라
       '어느 쪽으로 가고 있나'다. 시간순으로 세워야 그게 보인다.
       속보 출처가 주는 시점은 전년동월·전월·당월 셋이라 그 셋을 세운다."""
    c = [v for v in vals if v is not None]
    if len(c) < 2:
        return "   "
    lo, hi = min(c), max(c)
    if hi == lo:
        return BLK[3] * len(c)
    return "".join(BLK[min(7, int((v - lo) / (hi - lo) * 7 + 0.5))] for v in c)


def _three(v, mm, yy):
    """당월 값과 전월비·전년비로부터 (전년동월, 전월, 당월) 세 점을 복원한다."""
    prev = v / (1 + mm / 100) if mm is not None and mm != -100 else None
    ago = v / (1 + yy / 100) if yy is not None and yy != -100 else None
    return [ago, prev, v]


def _yr_line(r):
    """연간 추이 스파크라인 — 2022~2025 연간 + 올해 누계.
       월 3점짜리보다 이쪽이 '몇 년째 어느 쪽인가'를 보여 준다.
       다만 마지막 점은 연간이 아니라 누계(7개월치)라 그대로 이으면 급락처럼 보인다.
       올해를 연율로 환산해서(누계 ÷ 경과월 × 12) 같은 잣대로 맞춘다."""
    yr = r.get("yr") or []
    if len(yr) < 2:
        return None
    pts = list(yr)
    if r.get("ytd") and r.get("months_elapsed"):
        pts.append(r["ytd"] / r["months_elapsed"] * 12)
    return _vspark(pts)


def build_flash(fl, trade):
    """실시간 집계 속보 레터. 원문 수치를 그대로 옮기고 전월비를 앞세운다.

       확정치보다 2주 빠른 게 존재 이유라, 확정치와 섞지 않고 따로 낸다.
       금액은 오른쪽, 전월비·전년비는 그 뒤 — 훑을 때 '이번 달에 뭐가 꺾였나'가
       먼저 보여야 한다."""
    mon = fl.get("month", "")
    mlab = f"{mon[:4]}.{mon[4:]}" if len(mon) == 6 else mon
    out = [f"⚡ <b>화장품 수출 속보</b> · {mlab} 잠정",
           f"<i>{fl.get('source','')} · 확정치보다 약 2주 빠름</i>"]

    # 영업일수 보정 — 총액만 보면 방향을 오독한다.
    # 이번 달이 그 예다: 총액 전월비 0% 인데 영업일이 21->22 라 일평균은 -5% 다.
    wd = fl.get("workdays") or {}
    adj = None
    if wd.get("cur") and wd.get("prev") and wd.get("ago"):
        adj = lambda pct, base: ((1 + pct / 100) * base / wd["cur"] - 1) * 100

    tot0 = next((r for r in (fl.get("items") or []) if r["k"] == "화장품 총계"), None)
    if tot0:
        line = (f"<b>화장품 총계</b>  ${tot0['v']:,}M\n"
                f"전월 <b>{tot0['mm']:+.1f}%</b> · 전년 <b>{tot0['yy']:+.1f}%</b>")
        if adj:
            line += (f"\n일평균 전월 <b>{adj(tot0['mm'], wd['prev']):+.1f}%</b>"
                     f" · 전년 <b>{adj(tot0['yy'], wd['ago']):+.1f}%</b>")
        if tot0.get("ytd"):
            line += f"\n누계 ${tot0['ytd']:,}M · 전년비 {tot0['ytdYy']:+.1f}%"
        out.append(line)
        if adj:
            out.append(f"<i>영업일 {wd['cur']}일 (전월 {wd['prev']}일 · 전년 {wd['ago']}일). "
                       f"총액은 일수에 흔들리므로 일평균을 같이 봅니다.</i>")

    # 품목별 — 막대로 크기를, 숫자로 변화를. 이 레터의 존재 이유가
    # '이번 달에 뭐가 꺾였나'라서 막대(수준)만으론 부족하고 전월비가 같이 있어야 한다.
    items = fl.get("items") or []
    if items:
        rows = [r for r in items if r["k"] != "화장품 총계"]
        lw = max(_w(r["k"]) for r in rows)
        vw = max(len(f"{r['v']:,}") for r in rows)
        lines = []
        elapsed = int(mon[4:6]) if len(mon) == 6 else None
        for r in rows:
            pad = " " * max(0, lw - _w(r["k"]))
            if elapsed:
                r = {**r, "months_elapsed": elapsed}
            spk = _yr_line(r) or _vspark(_three(r["v"], r["mm"], r["yy"]))
            amt = f"{r['v']:,}".rjust(vw)
            row = f"{r['k']}{pad} {spk} {amt}M {r['mm']:+5.1f}% {r['yy']:+4.0f}%"
            lines.append(f"<code>{row}</code>")
        src = fl.get("itemsSource") or ""
        out.append("<b>품목별</b> <i>(막대=연간 22~25+올해 연율 · 금액 · 전월비 · 전년비)</i>\n"
                   + "\n".join(lines)
                   + (f"\n<i>{src}</i>" if src else ""))

    for g in fl.get("groups") or []:
        rows = g.get("rows") or []
        if not rows:
            continue
        # 전체 줄은 머리로 올리고 지역은 아래에 붙인다
        head = next((r for r in rows if r["k"] == "전체"), None)
        rest = [r for r in rows if r["k"] != "전체"]
        note = f" <i>({g['note']})</i>" if g.get("note") else ""
        if head:
            out.append(f"<b>{g['label']} · 지역별</b>{note}  전체 ${head['v']:,.1f}M"
                       f"  전월 {head['mm']:+d}% · 전년 {head['yy']:+d}%")
        if not rest:
            continue          # 담배처럼 전체 한 줄뿐인 품목은 머리줄로 끝난다
        # 금액 큰 순으로 — 어디가 주력인지 먼저 보이고, 변화는 숫자로 읽는다
        rest.sort(key=lambda r: -r["v"])
        lw = max(_w(r["k"]) for r in rest)
        vw = max(len(f"{r['v']:,.0f}") for r in rest)
        lines = []
        for r in rest:
            pad = " " * max(0, lw - _w(r["k"]))
            spk = _vspark(_three(r["v"], r["mm"], r["yy"]))
            amt = f"{r['v']:,.0f}".rjust(vw)
            lines.append(f"<code>{r['k']}{pad} {spk} {amt}M "
                         f"{r['mm']:+4d}% {r['yy']:+5d}%</code>")
        out.append("\n".join(lines))

    gsrc = fl.get("groupsSource") or ""
    if gsrc and (fl.get("groups") or []):
        out.append(f"<i>지역별 출처 — {gsrc}</i>")

    # 두 표는 출처가 달라 총계가 다르다. 섞어 읽지 않도록 못을 박아 둔다.
    last = _last_filled(trade)
    it_tot = next((r["v"] for r in (fl.get("items") or []) if r["k"] == "화장품 총계"), None)
    gp_tot = next((r["v"] for g in (fl.get("groups") or []) if g["label"] == "화장품"
                   for r in g["rows"] if r["k"] == "전체"), None)
    out.append(f"<i>품목표 총계({it_tot:,})는 향수·헤어까지 포함, "
               f"지역표 전체({gp_tot:,.0f})는 화장품(HS3304) 계열 — 총계끼리 비교 금지.\n"
               f"관세청 확정치는 {last[:4]}.{last[4:]} 까지. 대시보드는 HS 6단위라 "
               f"'기초'의 범위가 이 표와 다릅니다.</i>")
    return mon, "\n\n".join(out)


def main():
    html = open(HTML, encoding="utf-8").read()
    trade = _const(html, "TRADE")
    if not trade or not trade.get("items"):
        print("TRADE 데이터 없음"); return

    # 속보 모드 — 실시간 집계가 확정치보다 앞서 있으면 그걸 보낸다.
    if "--flash" in sys.argv:
        fl = _const(html, "TRADE_FLASH")
        if not fl or not fl.get("groups"):
            print("TRADE_FLASH 없음"); return
        mon, msg = build_flash(fl, trade)
        mon += "F"                       # 확정 레터(202607)와 상태 키를 구분한다
    else:
        mon, msg = build(trade)

    force = "--force" in sys.argv
    dry = "--dry-run" in sys.argv
    prev = ""
    if os.path.exists(STATE):
        try:
            prev = json.load(open(STATE, encoding="utf-8")).get("month", "")
        except Exception:
            prev = ""

    if dry:
        print("─" * 52); print(re.sub(r"<[^>]+>", "", msg)); print("─" * 52)
        print(f"(dry-run · 최근월 {mon} · 직전발송 {prev or '없음'})")
        return
    if not force and mon == prev:
        print(f"이미 {mon} 발송함 — 생략"); return
    if telegram_send.send(msg):
        json.dump({"month": mon}, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"[OK] {mon} 수출 레터 발송")


if __name__ == "__main__":
    main()
