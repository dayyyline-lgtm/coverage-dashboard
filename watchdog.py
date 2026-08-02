# -*- coding: utf-8 -*-
"""수집 건강검진 — 막히거나 굳으면 별도 텔레그램 메시지로 알린다.

왜 별도인가
  데일리 레터에 섞으면 '오늘도 왔네' 하고 지나친다. 장애는 레터와 무관하게,
  문제가 생겼을 때만, 눈에 띄게 따로 와야 한다. 정상일 땐 아무것도 안 보낸다.

무엇을 보나
  1) 신선도 — 각 데이터 블록의 asOf 가 기대 주기를 넘겼는가
  2) 차단   — 수집기가 남긴 health.json 의 403/429/캡차/타임아웃 기록
  둘 다 '문제 -> 알림 1회', '계속 문제 -> 6시간마다 재알림', '해결 -> 복구 알림 1회'.
  상태는 watchdog_state.json 에 남긴다(그게 없으면 매 실행마다 같은 걸 또 쏜다).

  python watchdog.py            # 점검 후 필요할 때만 발송
  python watchdog.py --dry-run  # 발송 없이 판정만
"""
import json, os, re, sys, datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import telegram_send

HTML = "public/index.html"
STATE = "watchdog_state.json"
HEALTH = "health.json"
KST = datetime.timezone(datetime.timedelta(hours=9))
RENOTIFY_H = 6           # 같은 문제를 다시 알리기까지
DASH = '<a href="https://coverage-dashboard.pages.dev">📊 대시보드 열기</a>'

# 블록별 허용 지연(시간). 주기가 느린 것은 넉넉하게 준다.
#   장이 안 열리는 주말엔 시세가 안 바뀌므로 LIVE 는 주말 보정을 따로 한다.
LIMITS = {
    "MOVIE_SCREENS": ("스크린·예매", 5),
    "MOVIE":         ("영화 예매·박스오피스", 8),
    "LIVE":          ("시세·컨센", 30),
    "NEWS":          ("종목 뉴스", 30),
    "TREND":         ("검색 트렌드", 200),      # 주 1회 전체수집
    "TRADE":         ("수출입(관세청)", 24 * 40),  # 월 1회 갱신
}


def parse_ts(s):
    for f in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s, f).replace(tzinfo=KST)
        except ValueError:
            pass
    return None


def freshness(html, now):
    """[(키, 라벨, 지연시간, 한도)] — 한도를 넘긴 것만."""
    bad = []
    for key, (label, limit_h) in LIMITS.items():
        m = re.search(r'const %s = \{"asOf": "([^"]+)"' % key, html)
        if not m:
            continue
        ts = parse_ts(m.group(1))
        if not ts:
            continue
        age = (now - ts).total_seconds() / 3600
        lim = limit_h
        # 주말엔 장이 안 서니 시세는 늦어도 정상 — 월요일 아침까지 봐준다
        if key == "LIVE" and now.weekday() >= 5:
            lim = max(lim, 72)
        if age > lim:
            bad.append((key, label, age, lim))
    return bad


def blocks():
    """수집기가 남긴 차단·오류 기록. {소스: {"msg":..., "t":...}}"""
    if not os.path.exists(HEALTH):
        return {}
    try:
        d = json.load(open(HEALTH, encoding="utf-8"))
    except Exception:
        return {}
    now = datetime.datetime.now(KST)
    out = {}
    for k, v in (d or {}).items():
        ts = parse_ts((v or {}).get("t") or "")
        if ts and (now - ts).total_seconds() / 3600 <= 12:   # 12시간 지난 건 흘려보낸다
            out[k] = v
    return out


def main():
    now = datetime.datetime.now(KST)
    html = open(HTML, encoding="utf-8").read()
    stale = freshness(html, now)
    blk = blocks()

    issues = {}
    for key, label, age, lim in stale:
        issues["stale:" + key] = (f"🕒 <b>{label}</b> 갱신이 멈췄습니다 — "
                                  f"마지막 수집 <b>{age:.0f}시간 전</b> (정상 {lim:.0f}시간 이내)")
    for src, v in blk.items():
        issues["block:" + src] = (f"🚫 <b>{src}</b> 수집이 막혔습니다 — "
                                  f"{(v.get('msg') or '')[:120]}")

    try:
        st = json.load(open(STATE, encoding="utf-8"))
    except Exception:
        st = {}

    lines, keep = [], {}
    for k, msg in issues.items():
        prev = st.get(k)
        last = parse_ts((prev or {}).get("t") or "")
        if prev and last and (now - last).total_seconds() / 3600 < RENOTIFY_H:
            keep[k] = prev            # 최근에 알렸으면 조용히 유지
            continue
        lines.append(msg)
        keep[k] = {"t": now.strftime("%Y-%m-%d %H:%M")}

    fixed = [k for k in st if k not in issues]
    if fixed:
        names = ", ".join(k.split(":", 1)[1] for k in fixed)
        lines.append(f"✅ <b>복구됨</b> — {names} 수집이 다시 돌고 있습니다")

    if not lines:
        print("[watchdog] 이상 없음 — 발송 생략")
        json.dump(keep, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)
        return

    head = "🛠 <b>대시보드 점검 알림</b>" if issues else "🛠 <b>대시보드 복구 알림</b>"
    body = "\n".join(f"• {x}" for x in lines)
    tail = ("\n\n<i>수집이 막히면 화면 숫자가 옛날 값에 멈춰 있습니다. "
            "차단이면 대개 하루 이틀 뒤 스스로 풀립니다.</i>" if issues else "")
    msg = f"{head}\n{now:%m/%d %H:%M} 기준\n\n{body}{tail}\n\n{DASH}"

    print(msg.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", ""))
    if "--dry-run" in sys.argv:
        return
    if telegram_send.send(msg):
        json.dump(keep, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"[watchdog] {len(lines)}건 발송")
    else:
        print("[watchdog] 발송 실패 — 상태 저장 생략(다음에 다시 시도)")


if __name__ == "__main__":
    main()
