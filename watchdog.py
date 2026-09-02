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
RENOTIFY_H = 24          # 같은 문제를 다시 알리기까지 (하루 한 번으로 묶는다)

# 문제가 이 시간 이상 이어져야 알린다.
#   네이버가 잠깐 흔들리는 건 늘 있는 일이라, 즉시 쏘면 하루 몇 통씩 오고
#   그러면 진짜 고장 났을 때 무시하게 된다. 다음 날 아침에도 여전히 깨져
#   있는 것만 알린다 — 그 사이 스스로 풀리면 아무 일도 없었던 게 된다.
PERSIST_H = 12
DASH = '<a href="https://coverage-dashboard.pages.dev">📊 대시보드 열기</a>'

# 블록별 허용 지연(시간). 주기가 느린 것은 넉넉하게 준다.
#   장이 안 열리는 주말엔 시세가 안 바뀌므로 LIVE 는 주말 보정을 따로 한다.
LIMITS = {
    "MOVIE_SCREENS": ("스크린·예매", 8),
    "MOVIE":         ("영화 예매·박스오피스", 10),
    "LIVE":          ("시세·컨센", 30),
    "NEWS":          ("종목 뉴스", 30),
    "TREND":         ("검색 트렌드", 200),      # 주 1회 전체수집
    "TRADE":         ("수출입(관세청)", 24 * 40),  # 월 1회 갱신
    # 아래는 감시 밖이었다 — 며칠 멈춰 있어도 아무도 몰랐다.
    "AMAZON":        ("아마존 뷰티", 24 * 3),   # 평일 리스트 수집, 주말은 건너뛴다
    "CIRCLE":        ("써클차트 앨범", 24 * 9),  # 주간 차트라 넉넉하게
    "SPOTIFY":       ("Spotify 아티스트", 48),
    "STEAM":         ("Steam 동접", 48),
    "TOURISM":       ("방한 관광객", 24 * 10),   # 월간 통계
    "SHOP":          ("해외 쇼핑 수요", 24 * 10),
    "CHZZK":         ("치지직 시청자", 30),
    "TOPTOON":       ("탑툰챗 대화수", 30),   # 아침 수집에서 하루 1회
    "AICHAT":        ("AI챗 앱순위", 30),     # 아침 수집에서 하루 1회
    "GAMEMONEY":     ("게임머니 시세", 30),    # 아침 수집에서 하루 1회 (아이템매니아)
    "GAMEBIT":       ("쌀먹 거래대금", 30),    # 아침 수집에서 하루 1회 (게임비트)
    "APPRANK":       ("앱스토어 게임순위", 30),
    "TWITCH":        ("트위치 시청자", 30),
}


def parse_ts(s):
    # 수집기마다 "2026-08-05 16:29" 과 "2026-08-04 06:25 KST" 가 섞여 있다.
    s = (s or "").replace("KST", "").strip()
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
        # 상수마다 `= {"asOf": "..."` 와 `={"asOf":"..."` 가 섞여 있어서
        # 예전 정규식은 AMAZON·SPOTIFY·STEAM 등을 통째로 놓치고 있었다.
        m = re.search(r'const %s\s*=\s*\{\s*"asOf"\s*:\s*"([^"]+)"' % key, html)
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


# 데일리 레터가 마지막으로 나간 뒤 이만큼 지나면 알린다.
#   레터는 매일 아침 06시경 나가므로, 보내기 직전(어제 것 기준 ~30시간)에도 안 울리게
#   여유를 둔다. 40시간이면 '이틀째 안 왔다' 만 잡힌다.
LETTER_LIMIT_H = 40
SENT_PATH = "digest_sent.json"


def letter_gap(now):
    """데일리 레터가 끊겼는가 — (지난 시간, 마지막 발송일) 또는 None.

    왜 여기서 보나
      alert.yml 은 워크플로가 '실패'해야 알린다. 그런데 2026-08-08~09 의 사고는
      **letter.yml 이 아예 한 번도 안 돈 것**이라 그 그물에 안 걸렸다(실행 0건).
      안 도는 것은 실패가 아니어서, 이틀 동안 아무도 몰랐다.
      watchdog 은 refresh.yml 에 얹혀 매시간 도니까 레터 경로가 통째로 죽어도 살아 있다.
      **'무엇이 실패했나'가 아니라 '와야 할 것이 왔나'를 보는 눈이 하나는 있어야 한다.**
    """
    if not os.path.exists(SENT_PATH):
        return None
    try:
        d = json.load(open(SENT_PATH, encoding="utf-8")) or {}
    except Exception:
        return None
    ts = parse_ts(d.get("date") or "")      # 날짜만 있다 → 그 날 자정(KST)
    if not ts:
        return None
    age = (now - ts).total_seconds() / 3600
    return (age, d.get("date")) if age > LETTER_LIMIT_H else None


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
    gap = letter_gap(now)
    if gap:
        age, last = gap
        # 키는 반드시 '접두어:이름' 꼴로 — 관찰중/복구 표시가 k.split(":",1)[1] 을 쓴다
        issues["letter:데일리 레터"] = (
                           f"📮 <b>데일리 레터</b>가 안 나가고 있습니다 — "
                            f"마지막 발송 <b>{last}</b> ({age / 24:.0f}일 전). "
                            f"수집은 돌아도 레터만 끊길 수 있습니다(트리거가 따로입니다)")

    try:
        st = json.load(open(STATE, encoding="utf-8"))
    except Exception:
        st = {}

    # 상태 파일에는 두 시각을 남긴다.
    #   first — 이 문제를 처음 본 때. 지속 여부 판정에 쓴다.
    #   t     — 마지막으로 알린 때. 하루 한 번으로 묶는 데 쓴다.
    #   알린 적 없으면 t 는 없다(관찰 중인 상태).
    lines, keep = [], {}
    watching = []
    for k, msg in issues.items():
        prev = st.get(k) or {}
        first = parse_ts(prev.get("first") or "") or now
        keep[k] = {"first": first.strftime("%Y-%m-%d %H:%M")}

        held = (now - first).total_seconds() / 3600
        if held < PERSIST_H:
            # 아직 일시적일 수 있다. 기록만 하고 조용히 지켜본다.
            watching.append(f"{k.split(':', 1)[1]}({held:.0f}h)")
            continue

        last = parse_ts(prev.get("t") or "")
        if last and (now - last).total_seconds() / 3600 < RENOTIFY_H:
            keep[k]["t"] = prev["t"]   # 오늘 이미 알렸다
            continue

        lines.append(f"{msg} <i>({held:.0f}시간째)</i>")
        keep[k]["t"] = now.strftime("%Y-%m-%d %H:%M")

    if watching:
        print(f"[watchdog] 관찰 중(아직 {PERSIST_H}시간 미만): " + ", ".join(watching))

    # 복구 알림은 '알린 적 있는 것'만 — 조용히 지켜보다 스스로 풀린 건
    # 사용자가 애초에 몰랐으므로 복구를 알릴 이유도 없다.
    fixed = [k for k in st if k not in issues and (st[k] or {}).get("t")]
    if fixed:
        names = ", ".join(k.split(":", 1)[1] for k in fixed)
        lines.append(f"✅ <b>복구됨</b> — {names} 수집이 다시 돌고 있습니다")

    if not lines:
        print("[watchdog] 이상 없음 — 발송 생략")
        # --dry-run 은 상태 파일을 건드리면 안 된다. 여기서 쓰면 '처음 본 때'가
        # 점검할 때마다 지금으로 밀려 지속시간이 리셋되고, 12시간을 영영 못 넘긴다.
        # (봇이 쓰는 파일이라 로컬에서 돌릴 때마다 커밋 대상이 되는 문제도 있었다.)
        if "--dry-run" not in sys.argv:
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
        # 발송이 실패해도 first(처음 본 때)는 남긴다. 이걸 잃으면 지속 시간이
        # 매번 0 으로 리셋돼 영영 PERSIST_H 를 못 넘긴다.
        for k in keep:
            keep[k].pop("t", None)
        json.dump(keep, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)
        print("[watchdog] 발송 실패 — 다음 실행에서 다시 시도합니다")


if __name__ == "__main__":
    main()
