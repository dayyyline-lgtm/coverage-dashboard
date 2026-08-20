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


_QLAST = {3: 31, 6: 30, 9: 30, 12: 31}
STALE_DAYS = 100          # 분기말로부터 이 기간을 넘긴 실적은 새 소식이 아니다


def qend(k):
    """분기 마지막 날. 형식이 어긋나면 None."""
    try:
        y, mo = int(k[:4]), int(k[4:6])
        return datetime.date(y, mo, _QLAST.get(mo, 28))
    except (ValueError, IndexError):
        return None


def main():
    if not (TOKEN and CHAT):
        print("텔레그램 시크릿 없음 - 건너뜀"); return

    # 실제 실적이 나올 때까지 기다렸다가 버그를 발견하면 늦다.
    # notify-test 워크플로로 언제든 연결 상태만 확인할 수 있게 해 둔다.
    if os.environ.get("NOTIFY_TEST"):
        r = send("🔔 <b>연결 테스트</b>\n커버리지 대시보드 알림이 정상 연결됐습니다.\n"
                 "실적 발표가 감지되면 컨센 대비 서프라이즈를 이 채널로 보냅니다.")
        print("테스트 발송:", "성공" if r.get("ok") else f"실패 {str(r)[:150]}")
        return

    html = open(HTML_PATH, encoding="utf-8").read()
    m = re.search(r"const LIVE = (\{.*?\});", html, re.S)
    if not m:
        print("LIVE 블록을 찾지 못했습니다"); return
    live = json.loads(m.group(1))
    snap = live.get("consSnap") or {}
    stocks = live.get("stocks") or {}
    # DART 잠정실적(PRELIM) — 발표를 '제때' 잡는 쪽은 이쪽이다.
    #   네이버 재무 API 는 정식 보고서(분기말+45일)가 올라와야 그 분기를 '실적'으로 바꾼다.
    #   그래서 네이버만 보면 회사가 발표한 지 한참 뒤에야 알림이 나갔다
    #   (2026-08-21 실측: 앞서 발표된 4건이 8/21 아침에 몰려서 발송).
    #   DART '영업(잠정)실적(공정공시)' 는 회사가 내는 즉시 뜨므로 fetch_prelim 이 받아 둔
    #   PRELIM 을 같이 본다. 단위는 series 와 같은 십억원이라 그대로 비교된다.
    prelim = {}
    mp = re.search(r"const PRELIM = (\{.*?\});", html, re.S)
    if mp:
        try:
            prelim = json.loads(mp.group(1))
        except json.JSONDecodeError:
            prelim = {}

    state = {}
    if os.path.exists(STATE_PATH):
        try:
            state = json.load(open(STATE_PATH, encoding="utf-8"))
        except json.JSONDecodeError:
            state = {}

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    today, td = now.strftime("%Y-%m-%d %H:%M"), now.date()
    sent = 0

    for name, per in snap.items():
        series = (((stocks.get(name) or {}).get("cons") or {}).get("quarter") or {}).get("series") or []
        for qk, cons in per.items():
            key = f"{name}|{qk}"
            if key in state:
                continue
            # 오래된 분기는 건너뛴다.
            # notified.json 이 사라지거나 초기화되면(실수로 지우거나 새로 받거나)
            # 이미 지나간 분기가 전부 '새 발표'로 보여 한꺼번에 쏟아진다.
            # 실적은 분기말 두 달 안에 나오므로 그 밖은 새 소식이 아니다.
            qe = qend(qk)
            if qe and (td - qe).days > STALE_DAYS:
                state[key] = "stale"          # 다시 검사하지 않도록 표시만 남긴다
                continue
            # 그 분기가 '실적'으로 확정됐는지 — e=False 면 발표된 것
            act = next((s for s in series if s.get("k") == qk and not s.get("e")), None)
            src = ""
            if not act:
                # 아직 정식 반영 전이면 DART 잠정실적으로 잡는다 — 발표 당일 알림이 나간다.
                pv = (prelim.get(name) or {}).get(qk)
                if pv and (pv.get("rev") is not None or pv.get("op") is not None):
                    act, src = pv, " (DART 잠정)"
            if not act:
                continue

            sr, so = pct(act.get("rev"), cons.get("rev")), pct(act.get("op"), cons.get("op"))
            # 영업이익 서프라이즈로 판정 (±5% 밖이면 어닝 서프라이즈/쇼크)
            # 컨센이 없으면 '부합'이 아니라 '판정 불가'다. In-line 로 적으면 거짓말이 된다.
            verdict = ("⚪ 컨센 없음(판정 보류)" if so is None
                       else "🟢 어닝 서프라이즈" if so > 5
                       else "🔴 어닝 쇼크" if so < -5
                       else "⚪ In-line")
            # 주가가 어떻게 받았는지까지 있어야 대응 판단이 된다.
            # 상회인데 주가가 빠지면 셀온, 하회인데 오르면 악재 선반영이다.
            chg = (stocks.get(name) or {}).get("chgPct")
            if chg is not None and so is not None:
                if so > 5 and chg < 0:
                    verdict += " · 주가 하락(셀온)"
                elif so < -5 and chg > 0:
                    verdict += " · 주가 상승(악재 선반영)"
                else:
                    verdict += f" · 주가 {chg:+.1f}%"
            arrow = lambda v: "—" if v is None else f"{'+' if v > 0 else ''}{v:.1f}%"
            msg = (f"<b>📊 {name} {qlab(qk)} 실적 발표{src}</b>\n"
                   f"<code>매출  {eok(act.get('rev')):>10}억  (컨센 {eok(cons.get('rev'))}억, {arrow(sr)})\n"
                   f"영익  {eok(act.get('op')):>10}억  (컨센 {eok(cons.get('op'))}억, {arrow(so)})</code>\n"
                   f"{verdict}\n"
                   f"<a href=\"https://coverage-dashboard.pages.dev\">📊 대시보드 열기</a>")
            try:
                r = send(msg)
                if not r.get("ok"):
                    print(f"  {key} 전송 실패: {str(r)[:120]}"); continue
            except Exception as e:
                print(f"  {key} 전송 오류: {type(e).__name__} {str(e)[:120]}"); continue
            state[key] = today
            sent += 1
            print(f"  발송: {key} · 영익 서프라이즈 {arrow(so)}")

    # 발송 없이 'stale' 로만 표시한 것도 남겨야 다음 실행이 또 훑지 않는다.
    before = json.load(open(STATE_PATH, encoding="utf-8")) if os.path.exists(STATE_PATH) else {}
    if state != before:
        json.dump(state, open(STATE_PATH, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print(f"\n[OK] {sent}건 발송" if sent else "새로 발표된 실적 없음")


if __name__ == "__main__":
    main()
