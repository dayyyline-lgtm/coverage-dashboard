# -*- coding: utf-8 -*-
"""
Steam 동접·리뷰 수집 — 게임 커버 종목의 '실측' 수요/평판 신호.
검색 트렌드는 대리지표일 뿐이고, 출시된 Steam 게임은 동시접속·리뷰가 진짜 숫자다.

공식 무료 API(키 불필요):
  - 동접: api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers
  - 리뷰: store.steampowered.com/appreviews (query_summary → total/positive)

index.html 의 STEAM 상수(그 블록만) 를 정규식으로 교체/삽입한다. 매일 1점씩 쌓는다.
같은 날 재실행이면 그날 값을 갱신(중복 append 안 함). 시세·트렌드 블록은 건드리지 않는다.

  python fetch_steam.py            # 수집·기록
  python fetch_steam.py --dry-run  # 출력만
"""
import re, json, sys, datetime, urllib.request

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
HISTMAX = 90

# (종목, 표시명, Steam appid) — 커버 게임사의 대표 타이틀.
#   붉은사막 2026-03-19 출시, 스텔라블레이드 PC판 — 단일플레이라 '동접 감소 곡선 + 리뷰'가 핵심.
#   검은사막·배그(PUBG)는 라이브서비스라 동접 절대수준이 매출 베이스.
GAMES = [
    ("펄어비스", "붉은사막",       3321460),
    ("펄어비스", "검은사막",       582660),
    ("크래프톤", "배틀그라운드",   578080),
    ("시프트업", "스텔라블레이드", 3489700),
]


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "coverage-dashboard/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def _players(appid):
    d = _get("https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers"
             f"/v1/?appid={appid}")
    resp = d.get("response") or {}
    return resp.get("player_count") if resp.get("result") == 1 else None


def _reviews(appid):
    d = _get(f"https://store.steampowered.com/appreviews/{appid}"
             "?json=1&language=all&num_per_page=0&purchase_type=all")
    q = d.get("query_summary") or {}
    tot, pos = q.get("total_reviews") or 0, q.get("total_positive") or 0
    return (tot, round(pos / tot * 100, 1)) if tot else (0, None)


def _const(html, name):
    m = re.search(r"const %s\s*=\s*(\{.*?\});" % re.escape(name), html, re.S)
    return json.loads(m.group(1)) if m else None


def _put(html, name, obj):
    """STEAM 블록만 교체. 없으면 LIVE 상수 뒤에 새로 삽입한다."""
    block = "const %s = %s;" % (name, json.dumps(obj, ensure_ascii=False,
                                                  separators=(",", ":")))
    pat = re.compile(r"const %s\s*=\s*\{.*?\};" % re.escape(name), re.S)
    if pat.search(html):
        return pat.sub(lambda m: block, html, count=1)
    liv = re.search(r"const LIVE\s*=\s*\{.*?\};", html, re.S)
    if not liv:
        raise RuntimeError("STEAM 삽입 기준(const LIVE)을 못 찾음")
    return html[:liv.end()] + "\n" + block + html[liv.end():]


def main():
    html = open(HTML, encoding="utf-8").read()
    today = datetime.datetime.now(KST).date().isoformat()
    old = {(g["stock"], g["title"]): g.get("hist", [])
           for g in (_const(html, "STEAM") or {}).get("games", [])}

    games = []
    for stock, title, appid in GAMES:
        hist = list(old.get((stock, title), []))
        try:
            p = _players(appid)
            rv, pos = _reviews(appid)
            pt = {"d": today, "p": p, "rv": rv, "pos": pos}
            if hist and hist[-1].get("d") == today:
                hist[-1] = pt                       # 같은 날 재실행 → 갱신
            else:
                hist.append(pt)
            hist = hist[-HISTMAX:]
            print(f"  {title}: 동접 {p:,} · 리뷰 {rv:,} 긍정 {pos}%")
        except Exception as e:
            print(f"  [실패] {title}: {str(e)[:100]} (기존 시계열 보존)")
        games.append({"stock": stock, "title": title, "appid": appid, "hist": hist})

    steam = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
             "games": games}

    if "--dry-run" in sys.argv:
        print(json.dumps(steam, ensure_ascii=False, indent=2)[:900]); return
    open(HTML, "w", encoding="utf-8").write(_put(html, "STEAM", steam))
    print(f"[OK] STEAM 갱신 · {len(games)}종")


if __name__ == "__main__":
    main()
