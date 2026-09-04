# -*- coding: utf-8 -*-
"""
Steam 동접·리뷰 수집 — 게임 커버 종목의 '실측' 수요/평판 시계열.
검색 트렌드는 대리지표일 뿐이고, 출시된 Steam 게임은 동시접속·리뷰가 진짜 숫자다.

동접(시계열):
  SteamCharts chart-data.json 이 [ [ms, 동접], ... ] 로 과거 전체를 준다(호출마다 최신 포함).
  → UTC 날짜별 '최고 동접(daily peak)' 으로 리샘플. 과거가 통째로 들어오니 백필이 필요없다.
  SteamCharts 가 막히면 공식 API(GetNumberOfCurrentPlayers)로 오늘 1점만 보완(기존 시계열 보존).
리뷰(스냅샷 누적):
  공식 store.steampowered.com/appreviews (query_summary) 로 현재 총리뷰·긍정%를 매일 1점씩 쌓는다.
  (리뷰는 과거 시계열 무료 소스가 없어 오늘부터 누적.)

index.html 의 STEAM 상수(그 블록만) 를 교체/삽입한다. 시세·트렌드 블록은 안 건드린다.

  python fetch_steam.py            # 수집·기록
  python fetch_steam.py --dry-run  # 출력만
"""
import re, json, sys, datetime, urllib.request

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
DAYS = 180                         # 최근 N일만 저장(단일플레이 신작은 전 생애, 라이브서비스는 최근 6개월)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# (종목, 표시명, Steam appid)
GAMES = [
    ("펄어비스", "붉은사막",       3321460),
    ("펄어비스", "검은사막",       582660),
    ("크래프톤", "배틀그라운드",   578080),
    ("시프트업", "스텔라블레이드", 3489700),
]


def _get(url, browser=False):
    ua = UA if browser else "coverage-dashboard/1.0"
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))


def _daily_peak(appid):
    """SteamCharts → UTC 날짜별 (최고동접, 평균동접). (dates['M/D'], players[int], avgs[int|None]).

    SteamCharts 해상도는 최근 ~1개월 시간별 · 그 전 일별 1점 · 더 전은 **월별 1점(그 달 최고)** 이다.
    월별 점을 일별 선에 이어 붙이면 '출시 직후 절벽' 모양이 생긴다 — 붉은사막 3/1·4/1·5/1·6/1 네 점이
    x축 네 칸을 차지해 넉 달이 나흘처럼 그려졌다(2026-09-04 외부 대조로 발견). 앞쪽의 성긴 점은 버린다.
    평균은 시간별 점이 20개 넘게 있는 날만 낸다(그 외 None). peak 만 뛰고 avg 가 안 오르면
    '특정 시간대에 잠깐 몰렸다 빠진' 유입이라 둘을 같이 봐야 한다."""
    raw = _get(f"https://steamcharts.com/app/{appid}/chart-data.json", browser=True)
    byday = {}
    for ms, cnt in raw:
        if cnt is None:
            continue
        day = datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).date()
        byday.setdefault(day, []).append(cnt)
    # 진행 중인 당일(UTC)은 아직 하루 peak 이 안 정해져 어제와 비교하면 급락처럼 보인다 → 제외.
    utc_today = datetime.datetime.now(datetime.timezone.utc).date()
    days = [d for d in sorted(byday) if d < utc_today]
    # 앞쪽 성긴(월별·주별 요약) 구간 제거: 다음 점까지 하루를 넘으면 그 점은 일별 값이 아니다
    while len(days) > 1 and (days[1] - days[0]).days > 1:
        days.pop(0)
    days = days[-DAYS:]
    if not days:
        raise ValueError("빈 시계열")
    peaks = [max(byday[d]) for d in days]
    avgs = [round(sum(byday[d]) / len(byday[d])) if len(byday[d]) >= 20 else None for d in days]
    return [f"{d.month}/{d.day}" for d in days], peaks, avgs


def _players_now(appid):
    d = _get("https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers"
             f"/v1/?appid={appid}")
    resp = d.get("response") or {}
    return resp.get("player_count") if resp.get("result") == 1 else None


def _reviews(appid):
    d = _get(f"https://store.steampowered.com/appreviews/{appid}"
             "?json=1&language=all&num_per_page=0&purchase_type=all", browser=True)
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
    today = datetime.datetime.now(KST).date()
    prev = {(g["stock"], g["title"]): g
            for g in (_const(html, "STEAM") or {}).get("games", [])}

    games = []
    for stock, title, appid in GAMES:
        old = prev.get((stock, title), {})
        dates, players = old.get("dates") or [], old.get("players") or []
        avgs = list(old.get("avg") or [None] * len(dates))
        try:
            dates, players, avgs = _daily_peak(appid)         # SteamCharts 시계열(과거 통째로)
            # 시간별 해상도가 지나가면(약 1개월) 그날 평균은 다시 못 구한다 → 예전에 구해 둔 값을 보존
            oldavg = dict(zip(old.get("dates") or [], old.get("avg") or []))
            avgs = [a if a is not None else oldavg.get(d) for d, a in zip(dates, avgs)]
            na = sum(1 for a in avgs if a is not None)
            print(f"  {title}: 동접 일별peak {len(players)}일(평균 {na}일) · 최근 peak {players[-1]:,}"
                  + (f" · avg {avgs[-1]:,}" if avgs[-1] is not None else ""))
        except Exception as e:
            print(f"  [SteamCharts 실패] {title}: {str(e)[:70]} → 공식 현재동접으로 오늘 1점 보완")
            try:
                p = _players_now(appid)
                if p is not None:
                    lbl = f"{today.month}/{today.day}"
                    if dates and dates[-1] == lbl:
                        players[-1] = p
                    else:
                        dates, players, avgs = dates + [lbl], players + [p], avgs + [None]
                    dates, players, avgs = dates[-DAYS:], players[-DAYS:], avgs[-DAYS:]
            except Exception as e2:
                print(f"    [현재동접도 실패] {str(e2)[:60]}")

        rvh = list(old.get("reviews") or [])                  # 리뷰 스냅샷 누적
        try:
            tot, pos = _reviews(appid)
            pt = {"d": today.isoformat(), "t": tot, "pos": pos}
            if rvh and rvh[-1].get("d") == today.isoformat():
                rvh[-1] = pt
            else:
                rvh.append(pt)
            rvh = rvh[-DAYS:]
            print(f"    리뷰 {tot:,} 긍정 {pos}%")
        except Exception as e:
            print(f"    [리뷰 실패] {str(e)[:60]}")

        games.append({"stock": stock, "title": title, "appid": appid,
                      "dates": dates, "players": players, "avg": avgs, "reviews": rvh})

    steam = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
             "games": games}

    if "--dry-run" in sys.argv:
        for g in games:
            r = g["reviews"][-1] if g["reviews"] else None
            print(f"{g['title']}: {len(g['players'])}일 · 최근 {g['players'][-1] if g['players'] else '—'} · 리뷰 {r}")
        return
    open(HTML, "w", encoding="utf-8").write(_put(html, "STEAM", steam))
    print(f"[OK] STEAM 갱신 · {len(games)}종")


if __name__ == "__main__":
    main()
