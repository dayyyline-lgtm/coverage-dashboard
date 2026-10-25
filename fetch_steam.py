# -*- coding: utf-8 -*-
"""
Steam 동접·리뷰 수집 — 게임 커버 종목의 '실측' 수요/평판 시계열.
검색 트렌드는 대리지표일 뿐이고, 출시된 Steam 게임은 동시접속·리뷰가 진짜 숫자다.

동접(시계열):
  SteamCharts chart-data.json 이 [ [ms, 동접], ... ] 로 과거 전체를 준다(호출마다 최신 포함).
  → UTC 날짜별 '최고 동접(daily peak)' 으로 리샘플. 과거가 통째로 들어오니 백필이 필요없다.
  SteamCharts 가 막히면 공식 API(GetNumberOfCurrentPlayers)로 오늘 1점만 보완(기존 시계열 보존).
리뷰(일별 · 2026-10-25 부터):
  store.steampowered.com/appreviewhistogram 의 recent(최근 30일 **일별** 신규 리뷰) + rollups(출시부터 주·월 합)
  → 날짜(UTC)마다 {"d", "t" 그날 끝 누적, "n" 그날 신규, "pos"}. 30일을 통째로 다시 받으니 빠진 날이 저절로 메워진다.
  ⚠ 옛 경로 appreviews(query_summary)는 10/23 부터 홈으로 302 를 준다(PC·러너 둘 다) — 동접만 들어와서
    블록 asOf 는 멀쩡했고 리뷰만 10/22 에 멈춰 있었다(watchdog 이 못 봤다 → 리뷰 날짜를 따로 본다).
  ⚠ 기준이 옛 total_reviews(purchase_type=all)와 다르다 — 유료작은 신규가 1.2~1.6배 적게 잡힌다(키 등록분이 빠지는 듯).
    10/22 까지의 옛 기록은 겹친 9/27~10/22 의 '옛 증분 ÷ 새 증분'(`rvk`)으로 나눠 새 기준에 이어 붙였다(`rvb`="hist").
    붉은사막 리뷰당 판매(GAMEEST box)도 같은 비율로 20.5 → 32.5. 무료 게임(배그·TL)은 옛 누적이 삭제로 줄어
    증분이 음수라 비율을 못 낸다 → 옛 기록을 버리고 30일부터 다시 쌓는다.

index.html 의 STEAM 상수(그 블록만) 를 교체/삽입한다. 시세·트렌드 블록은 안 건드린다.

  python fetch_steam.py            # 수집·기록
  python fetch_steam.py --dry-run  # 출력만
"""
import re, json, sys, datetime, urllib.request, urllib.parse

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
    ("NC",       "아이온2",        3393110),   # 글로벌판 2026-10-05 스팀 출시(첫날 동접 14만). 한국·대만판은 퍼플 런처라 스팀 밖
    ("NC",       "쓰론앤리버티",   2429640),   # 글로벌판(아마존게임즈 퍼블리싱 · NC 로열티). 한국판은 퍼플 런처라 스팀 밖
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


RVB = "hist"                       # 리뷰 기준 표시 — 이게 없는 옛 기록은 기준이 달라 이어 붙이지 않는다


def _reviews(appid):
    """(누적 리뷰수, 긍정%, [(UTC 날짜, 그날 신규 리뷰)] 최근 30일 · 진행 중인 오늘 포함)."""
    d = _get(f"https://store.steampowered.com/appreviewhistogram/{appid}"
             "?l=english&review_score_preference=0", browser=True)
    r = d.get("results") or {}
    roll, rec = r.get("rollups") or [], r.get("recent") or []
    if not roll or not rec:
        raise ValueError("빈 히스토그램")
    n = lambda x: (x.get("recommendations_up") or 0) + (x.get("recommendations_down") or 0)
    tot = sum(n(x) for x in roll)                     # rollups 는 진행 중인 주·달까지 들어 있다 = 지금까지 전부
    up = sum(x.get("recommendations_up") or 0 for x in roll)
    U = datetime.timezone.utc
    days = sorted((datetime.datetime.fromtimestamp(x["date"], U).date(), n(x)) for x in rec)
    return tot, (round(up / tot * 100, 1) if tot else None), days


def _pos_all(appids):
    """{appid: 긍정%} — 상점이 보여 주는 값(summary_filtered · 정수). 히스토그램 합으로 낸 긍정%는
    리뷰 폭탄 거른 것이 안 빠져 상점 표시보다 낮다(붉은사막 79.5 vs 83). 실패하면 빈 dict → 히스토그램 값."""
    q = json.dumps({"ids": [{"appid": a} for a in appids], "context": {"language": "english", "country_code": "US"},
                    "data_request": {"include_reviews": True}}, separators=(",", ":"))
    try:
        d = _get("https://api.steampowered.com/IStoreBrowseService/GetItems/v1/?input_json="
                 + urllib.parse.quote(q), browser=True)
        return {i["appid"]: ((i.get("reviews") or {}).get("summary_filtered") or {}).get("percent_positive")
                for i in (d.get("response") or {}).get("store_items") or [] if i.get("appid")}
    except Exception as e:
        print(f"  [상점 긍정% 실패] {str(e)[:60]} → 히스토그램 합으로")
        return {}


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
    shop_pos = _pos_all([a for _, _, a in GAMES])
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
                        players[-1] = max(players[-1] or 0, p)   # 하루 여러 번 돌면 그날 최댓값(peak)을 남긴다
                    else:
                        dates, players, avgs = dates + [lbl], players + [p], avgs + [None]
                    dates, players, avgs = dates[-DAYS:], players[-DAYS:], avgs[-DAYS:]
            except Exception as e2:
                print(f"    [현재동접도 실패] {str(e2)[:60]}")

        rvh = list(old.get("reviews") or [])                  # 날짜(UTC)별 누적·신규
        if rvh and old.get("rvb") != RVB:
            print(f"    [리뷰] {title}: 옛 기준 기록 {len(rvh)}일은 이어 붙이지 않는다(기준이 다르다)")
            rvh = []
        try:
            tot, pos, days = _reviews(appid)
            if shop_pos.get(appid) is not None:
                pos = float(shop_pos[appid])
            utc_today = datetime.datetime.now(datetime.timezone.utc).date()
            cum, later = {}, 0                                 # 그날 끝 누적 = 합계 − 그 뒤 날들의 신규
            for dd, c in reversed(days):
                cum[dd] = tot - later
                later += c
            keep = {x["d"]: x for x in rvh if x.get("d")}
            for dd, c in days:
                if dd >= utc_today:                            # 진행 중인 UTC 당일은 뺀다(동접과 같은 규칙)
                    continue
                k = dd.isoformat()
                keep[k] = {"d": k, "t": cum[dd], "n": c, "pos": (keep.get(k) or {}).get("pos", pos)}
            rvh = [keep[k] for k in sorted(keep)][-DAYS:]
            if rvh:
                rvh[-1]["pos"] = pos
            print(f"    리뷰 {tot:,} 긍정 {pos}% · 최근 {rvh[-1]['d'] if rvh else '—'} 신규 {rvh[-1]['n'] if rvh else '—'}")
        except Exception as e:
            print(f"    [리뷰 실패] {str(e)[:60]}")

        g = {"stock": stock, "title": title, "appid": appid,
             "dates": dates, "players": players, "avg": avgs, "reviews": rvh, "rvb": RVB}
        if old.get("rvk") is not None:
            g["rvk"] = old["rvk"]
        games.append(g)

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
