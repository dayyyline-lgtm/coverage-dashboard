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
    m = re.search(r"const %s\s*=\s*(\{.*?\});" % re.escape(name), html, re.S)
    return json.loads(m.group(1)) if m else None


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


def build(trade):
    months = trade.get("months") or []
    mon = months[-1] if months else ""
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


def main():
    html = open(HTML, encoding="utf-8").read()
    trade = _const(html, "TRADE")
    if not trade or not trade.get("items"):
        print("TRADE 데이터 없음"); return
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
