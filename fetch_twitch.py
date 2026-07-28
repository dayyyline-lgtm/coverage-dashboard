# -*- coding: utf-8 -*-
"""
트위치(Twitch) 게임별 시청자 수집 — 글로벌/서구 시청 신호(치지직=국내와 짝).
트위치는 2024년 한국 철수라 국내는 치지직이 메인, 트위치는 해외 관객을 본다.

공식 Helix API. TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET 필요(없으면 스킵).
  - 앱 토큰: client_credentials 그랜트로 access_token
  - 게임ID: helix/games?name=  · 시청자: helix/streams?game_id= 의 viewer_count 합산(상위 페이지)

과거 시계열 무료 소스가 없어 매일 누적. refresh.yml(매시간)로 그날 최댓값(피크) 갱신.

  python fetch_twitch.py            # 수집·기록
  python fetch_twitch.py --dry-run  # 출력만
"""
import os, re, json, sys, datetime, urllib.request, urllib.parse

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
DAYS = 180
CID = os.environ.get("TWITCH_CLIENT_ID", "")
CSEC = os.environ.get("TWITCH_CLIENT_SECRET", "")

# (종목, 표시명, 트위치 게임명) — 글로벌 명칭
GAMES = [
    ("펄어비스", "붉은사막",       "Crimson Desert"),
    ("펄어비스", "검은사막",       "Black Desert"),
    ("크래프톤", "배틀그라운드",   "PUBG: BATTLEGROUNDS"),
    ("시프트업", "스텔라블레이드", "Stellar Blade"),
    ("시프트업", "니케",           "GODDESS OF VICTORY: NIKKE"),
    ("NC",       "아이온2",        "AION2"),
]


def available():
    return bool(CID and CSEC)


def _token():
    data = urllib.parse.urlencode({"client_id": CID, "client_secret": CSEC,
                                   "grant_type": "client_credentials"}).encode()
    with urllib.request.urlopen(urllib.request.Request("https://id.twitch.tv/oauth2/token",
                                                       data=data), timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))["access_token"]


def _helix(path, tok, **params):
    url = "https://api.twitch.tv/helix/" + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Client-Id": CID, "Authorization": "Bearer " + tok})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def _game_id(name, tok):
    its = (_helix("games", tok, name=name).get("data")) or []
    return its[0]["id"] if its else None


def _viewers(gid, tok):
    total, cursor = 0, None
    for _ in range(3):                       # 상위 300 스트림이면 게임별 총시청 대부분
        p = {"game_id": gid, "first": 100}
        if cursor:
            p["after"] = cursor
        d = _helix("streams", tok, **p)
        ss = d.get("data") or []
        total += sum(s.get("viewer_count", 0) for s in ss)
        cursor = (d.get("pagination") or {}).get("cursor")
        if not cursor or len(ss) < 100:
            break
    return total


def _const(html, name):
    m = re.search(r"const %s\s*=\s*(\{.*?\});" % re.escape(name), html, re.S)
    return json.loads(m.group(1)) if m else None


def _put(html, name, obj):
    block = "const %s = %s;" % (name, json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
    pat = re.compile(r"const %s\s*=\s*\{.*?\};" % re.escape(name), re.S)
    if pat.search(html):
        return pat.sub(lambda m: block, html, count=1)
    liv = re.search(r"const LIVE\s*=\s*\{.*?\};", html, re.S)
    if not liv:
        raise RuntimeError("TWITCH 삽입 기준(const LIVE)을 못 찾음")
    return html[:liv.end()] + "\n" + block + html[liv.end():]


def main():
    if not available():
        print("[twitch] 크레덴셜 없음 — 스킵"); return
    html = open(HTML, encoding="utf-8").read()
    today = datetime.datetime.now(KST).date().isoformat()
    prev = {(g["stock"], g["title"]): g.get("hist", [])
            for g in (_const(html, "TWITCH") or {}).get("games", [])}
    try:
        tok = _token()
    except Exception as e:
        print(f"[twitch] 토큰 실패: {str(e)[:100]}"); return

    games = []
    for stock, title, gname in GAMES:
        hist = list(prev.get((stock, title), []))
        try:
            gid = _game_id(gname, tok)
            v = _viewers(gid, tok) if gid else 0
            if hist and hist[-1].get("d") == today:
                hist[-1] = {"d": today, "v": max(hist[-1].get("v", 0), v)}
            else:
                hist.append({"d": today, "v": v})
            hist = hist[-DAYS:]
            print(f"  {title}: 시청자 {v:,}" + ("" if gid else f" (게임 '{gname}' 못 찾음)"))
        except Exception as e:
            print(f"  [{title}] 실패: {str(e)[:90]}")
        games.append({"stock": stock, "title": title, "hist": hist})

    tw = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "games": games}
    if "--dry-run" in sys.argv:
        print(json.dumps(tw, ensure_ascii=False, indent=1)[:600]); return
    open(HTML, "w", encoding="utf-8").write(_put(html, "TWITCH", tw))
    print(f"[OK] TWITCH 갱신 · {len(games)}종")


if __name__ == "__main__":
    main()
