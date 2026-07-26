# -*- coding: utf-8 -*-
"""
실적 발표 감지 -> 텔레그램 알림

분기 실적이 발표되면 네이버 재무 API 에서 그 분기가 '컨센'에서 '실적'으로 바뀐다.
발표 전에 저장해 둔 컨센(LIVE.consSnap)과 대조하면 서프라이즈가 바로 나온다.
같은 건을 두 번 쏘지 않도록 보낸 목록을 notified.json 에 남긴다.

토큰이 없으면 조용히 종료한다(수집 워크플로를 깨지 않는다).
  TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
"""
import json, re, os, sys, urllib.request, urllib.parse, datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML_PATH = "public/index.html"
STATE_PATH = "notified.json"
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")


def send(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": CHAT, "text": text,
        "parse_mode": "HTML", "disable_web_page_preview": "true"}).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def eok(v):
    """십억원 -> 억원 표기"""
    return "—" if v is None else f"{round(v * 10):,}"


def pct(a, b):
    return None if (a is None or not b) else (a / b - 1) * 100


def qlab(k):
    return f"{(int(k[4:6]) - 1) // 3 + 1}Q{k[2:4]}"


def main():
    if not (TOKEN and CHAT):
        print("텔레그램 시크릿 없음 - 건너뜀"); return

    html = open(HTML_PATH, encoding="utf-8").read()
    m = re.search(r"const LIVE = (\{.*?\});", html, re.S)
    if not m:
        print("LIVE 블록을 찾지 못했습니다"); return
    live = json.loads(m.group(1))
    snap = live.get("consSnap") or {}
    stocks = live.get("stocks") or {}

    state = {}
    if os.path.exists(STATE_PATH):
        try:
            state = json.load(open(STATE_PATH, encoding="utf-8"))
        except json.JSONDecodeError:
            state = {}

    today = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
    sent = 0

    for name, per in snap.items():
        series = (((stocks.get(name) or {}).get("cons") or {}).get("quarter") or {}).get("series") or []
        for qk, cons in per.items():
            key = f"{name}|{qk}"
            if key in state:
                continue
            # 그 분기가 '실적'으로 확정됐는지 — e=False 면 발표된 것
            act = next((s for s in series if s.get("k") == qk and not s.get("e")), None)
            if not act:
                continue

            sr, so = pct(act.get("rev"), cons.get("rev")), pct(act.get("op"), cons.get("op"))
            # 영업이익 서프라이즈로 판정 (±5% 밖이면 어닝 서프라이즈/쇼크)
            verdict = ("🟢 어닝 서프라이즈" if (so is not None and so > 5)
                       else "🔴 어닝 쇼크" if (so is not None and so < -5)
                       else "⚪ In-line")
            arrow = lambda v: "—" if v is None else f"{'+' if v > 0 else ''}{v:.1f}%"
            msg = (f"<b>📊 {name} {qlab(qk)} 실적 발표</b>\n"
                   f"<code>매출  {eok(act.get('rev')):>10}억  (컨센 {eok(cons.get('rev'))}억, {arrow(sr)})\n"
                   f"영익  {eok(act.get('op')):>10}억  (컨센 {eok(cons.get('op'))}억, {arrow(so)})</code>\n"
                   f"{verdict}")
            try:
                r = send(msg)
                if not r.get("ok"):
                    print(f"  {key} 전송 실패: {str(r)[:120]}"); continue
            except Exception as e:
                print(f"  {key} 전송 오류: {type(e).__name__} {str(e)[:120]}"); continue
            state[key] = today
            sent += 1
            print(f"  발송: {key} · 영익 서프라이즈 {arrow(so)}")

    if sent:
        json.dump(state, open(STATE_PATH, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"\n[OK] {sent}건 발송")
    else:
        print("새로 발표된 실적 없음")


if __name__ == "__main__":
    main()
