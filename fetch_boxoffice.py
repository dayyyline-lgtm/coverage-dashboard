# -*- coding: utf-8 -*-
"""
극장가 흥행 — 대원미디어 '극장판 치이카와' + 같은 시기 흥행작 3편 (2026-09-26 · → const BOXOFFICE)

하츄핑(SAMG) 수집기(fetch_movie·fetch_screens → MOVIE·MOVIE_SCREENS)는 1편 앵커·비교군이
그 영화에 맞춰 짜여 있어 건드리지 않는다(보관 기록). 여기는 **영화 목록만 바꿔 끼우는** 범용판이다.

  대상(FILMS) — KOBIS 영화코드로 고정한다. 제목 키워드는 극장 체인 매칭용.
    극장판 치이카와: 인어 섬의 비밀  9/30 개봉 · 수입 대원미디어(048910) · 배급 CJ ENM   ← 주인공
    암살자(들)                      9/23 · 하이브미디어코프(⚠ 하이브 HYBE 와 무관한 영화사)
    타짜: 벨제붑의 노래              9/23 · 배급 CJ ENM · 제작 싸이더스
    오디세이                        8/5  · 유니버설 — 누적 1,155만(9/25)의 기준선

소스 셋 — 전부 키·로그인 없음
  ① KOBIS 일별 박스오피스(웹 통계 findDailyBoxOfficeList.do)
     OpenAPI(키 필요)는 Top10 만 주지만 **웹 페이지는 그날 상영된 전 영화**(9/25 실측 98편)를 준다.
     그래서 순위 밖으로 밀려도 끊기지 않고, 전 영화 관객 합(=시장 총량)까지 같이 얻는다.
  ② KOBIS 실시간 예매(findRealTicketList.do) — 개봉 전 유일한 실시간 수요 지표.
     ⚠ '남은 상영분' 기준이라 하루 중에도 줄어든다(fetch_movie 주석 · 05:38 14.5만 → 12:54 9.1만).
        같은 시각끼리만 견줄 것 — 화면은 날마다 10시에 가장 가까운 스냅샷을 쓴다.
  ③ 3사 좌석(--seats) — CGV·롯데·메가 예매 API 의 회차별 총좌석·잔여 → 판매 = 총 − 잔여.
     규격·검증은 fetch_screens.py 머리 주석이 원본이다(요청 함수도 거기서 가져온다).
     ⚠ CGV 는 GitHub 러너에서 403 이다(2026-09-13~). 그래서 --seats 는 **이 PC(한국 IP)에서만** 돌린다.
        러너(refresh.yml)는 ①② 만 — 요청 2~3건이라 가볍다.

추적 기한(UNTIL) 이 지나면 아무것도 안 하고 끝난다 — 하츄핑 때처럼 끝난 영화를 계속 긁지 않게.

  python fetch_boxoffice.py                                  # ①② (러너 · 매 회차)
  python fetch_boxoffice.py --seats                          # ①②③ 한 번에 (이 PC · 20~30분)
  python fetch_boxoffice.py --seats --cache=.cache/seats.json  # ③ 받기만 (kr_boxoffice.py 1단계)
  python fetch_boxoffice.py --merge=.cache/seats.json          # ①② + 캐시의 ③ 병합 (2단계)
  python fetch_boxoffice.py --dry-run
"""
import datetime, html as htmlmod, http.cookiejar, json, re, sys, time, urllib.parse, urllib.request

from collector_health import ua, nap, note_health

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
UNTIL = "2026-11-15"          # 치이카와 개봉 +6주 — 지나면 수집 중단(블록은 보관)
SCAN_FROM = "20260805"        # 가장 이른 개봉(오디세이) — 일별 백필의 시작
BOOK_KEEP = 400

FILMS = [
    {"title": "극장판 치이카와: 인어 섬의 비밀", "short": "치이카와", "kobis": "20261807",
     "open": "2026-09-30", "kw": ["치이카와"], "dist": "CJ ENM", "imp": "대원미디어",
     "stock": "대원미디어", "listed": [["대원미디어", "048910"], ["CJ ENM", "035760"]]},
    {"title": "암살자(들)", "short": "암살자(들)", "kobis": "20255033",
     "open": "2026-09-23", "kw": ["암살자들"], "dist": "하이브미디어코프",
     "note": "하이브(HYBE)와 무관한 영화사"},
    {"title": "타짜: 벨제붑의 노래", "short": "타짜", "kobis": "20256161",
     "open": "2026-09-23", "kw": ["벨제붑"], "dist": "CJ ENM", "prod": "싸이더스",
     "listed": [["CJ ENM", "035760"]]},
    {"title": "오디세이", "short": "오디세이", "kobis": "20250654",
     "open": "2026-08-05", "kw": ["오디세이"], "not": ["스페이스"], "dist": "유니버설"},
]
BY_CODE = {f["kobis"]: f["title"] for f in FILMS}


def norm(s):
    return re.sub(r"[^0-9A-Za-z가-힣]", "", htmlmod.unescape(s or ""))


def film_of(name):
    n = norm(name)
    for f in FILMS:
        if any(k in n for k in f["kw"]) and not any(x in n for x in f.get("not", [])):
            return f["title"]
    return None


# ── KOBIS (웹 통계 · 키 불필요) ───────────────────────────
KOBIS = "https://www.kobis.or.kr/kobis/business/stat/boxs/"
_TAG = re.compile(r"<[^>]*>")


def kobis_post(page, form, tries=3):
    """세션 쿠키를 먼저 받아야 표가 채워져 온다(없으면 껍데기). 러너에선 KOBIS 가 느리다 — 90초."""
    url = KOBIS + page
    last = None
    for i in range(tries):
        try:
            op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            h = ua(referer=url, doc=True)
            op.addheaders = list(h.items())
            op.open(url, timeout=90).read()
            req = urllib.request.Request(url, data=urllib.parse.urlencode(form).encode(),
                                         headers={"X-Requested-With": "XMLHttpRequest", "Referer": url})
            return op.open(req, timeout=90).read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            time.sleep(5 * (i + 1))
    raise last


def _rows(page_html):
    """<tr> 마다 (영화코드, 칸 텍스트 목록). 영화명 칸의 '동일·1상승' 같은 꼬리는 버리고 코드로 식별한다."""
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page_html, re.S):
        m = re.search(r"mstView\('movie','(\d+)'\)", tr)
        if not m:
            continue
        cells = [re.sub(r"\s+", " ", _TAG.sub(" ", c)).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        out.append((m.group(1), cells))
    return out


def _n(s):
    s = (s or "").split("(")[0]
    v = re.sub(r"[^\d-]", "", s)
    return int(v) if v not in ("", "-") else 0


def daily(ymd):
    """그날 상영된 전 영화. 칸: 순위·영화명·개봉일·매출액·점유율·매출증감·누적매출·관객수·관객증감·누적관객·스크린·상영횟수."""
    d = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"
    rows = _rows(kobis_post("findDailyBoxOfficeList.do",
                            {"loadEnd": 0, "searchType": "search", "sSearchFrom": d, "sSearchTo": d,
                             "sMultiMovieYn": "", "sRepNationCd": "", "sWideAreaCd": ""}))
    got, tot = {}, 0
    for code, c in rows:
        if len(c) < 12:
            continue
        audi = _n(c[7])
        tot += audi
        t = BY_CODE.get(code)
        if t:
            got[t] = {"d": ymd, "rank": _n(c[0]) or None, "audi": audi, "acc": _n(c[9]),
                      "scrn": _n(c[10]), "show": _n(c[11]), "sales": _n(c[3])}
    return got, tot, len(rows)


def booking():
    """실시간 예매. 칸: 순위·영화명·개봉일·예매율·예매매출·누적매출·예매관객·누적관객."""
    rows = _rows(kobis_post("findRealTicketList.do", {"loadEnd": 0, "searchType": "real"}))
    got = {}
    for code, c in rows:
        t = BY_CODE.get(code)
        if t and len(c) >= 8:
            got[t] = {"rank": _n(c[0]) or None, "rate": float(re.sub(r"[^\d.]", "", c[3]) or 0),
                      "book": _n(c[6]), "acc": _n(c[7])}
    return got, len(rows)


# ── 3사 좌석 (요청 함수는 fetch_screens 것을 그대로 쓴다) ─────
#   2026-09-26 개편 — "예전처럼 열려 있는 날짜 전부, 일별로". 하츄핑 때와 같은 뼈대다:
#     ① 탐침: 오늘~SEAT_DAYS 일 뒤까지, 날짜마다 체인별로 대형 지점 몇 곳만 찔러 '대상 영화가 걸렸나'를 본다.
#        걸린 (날짜, 체인)만 ② 전수 조사한다 — 안 열린 먼 날짜에 수천 요청을 버리지 않게.
#     ② 전수: 체인 셋을 **동시에**(스레드 3개) 돈다. 호스트가 달라 서로 기다릴 이유가 없다. 체인 안에서는 순차 + 간격.
#     ③ 한 체인이 통째로 실패하면(서버에선 CGV 가 403) 그 체인 없이 저장한다. 이어받지 않는다 —
#        대신 점마다 체인별 수치를 남기고, 화면이 '두 수집에 다 있는 체인'끼리만 비교해 가짜 급증·급감을 막는다.
#   ⚠ 서버(boxseats.yml)는 2026-09-26 기준 CGV 403 · 메가 간헐 시간초과 → 대개 롯데(+메가) 기준이다.
#     탐침이 이틀 연속 전부 실패한 체인은 그 회차에서 바로 포기한다(막힌 체인에 20분씩 헛돌지 않게).
#   ⚠ 탐침은 대형 지점만 본다. 그 지점에 안 걸리고 소형관에만 먼저 걸린 날짜는 놓칠 수 있다(와이드 개봉작은 드묾).
SEAT_DAYS = 14
SEAT_BUDGET = 38 * 60     # 전수 시간 예산(초). 넘기면 먼 날짜부터 생략 — 워크플로 시간 제한(75분) 안에서 끝나게
PROBE = {"CGV": ["0001", "0013", "0059", "0074"],          # 강변·용산·영등포·왕십리 (fetch_screens.PROBE_SITES)
         "LC": ["월드타워", "건대입구", "김포공항", "수원"],   # 이름으로 ID 를 찾는다
         "MB": ["1372", "1351"]}                             # 강남·코엑스


def _cgv_rows(d):
    rows, stack = [], [d.get("data")]
    while stack:
        o = stack.pop()
        if isinstance(o, list):
            stack.extend(o)
        elif isinstance(o, dict):
            if o.get("prodNm") and o.get("scnsNo"):
                rows.append(o)
            stack.extend(v for v in o.values() if isinstance(v, (list, dict)))
    return rows


def seat_plan(fs, dates, crt):
    """{play: set(체인)} — 그 날짜에 대상 영화가 걸린 체인. 탐침이 통째로 실패한 체인은 가까운 7일만 편성으로 본다."""
    base = {"channelType": "HO", "osType": "W", "osVersion": fs.UA, "memberOnNo": ""}
    tp = fs.lc_call({"MethodName": "GetTicketingPage", **base})
    cins = ((tp.get("Cinemas") or {}).get("Cinemas") or {}).get("Items") or []
    lc_ids = []
    for nm in PROBE["LC"]:
        c = next((c for c in cins if nm in (c.get("CinemaNameKR") or "")), None)
        if c:
            lc_ids.append(f"{c['DivisionCode']}|{c['DetailDivisionCode']}|{c['CinemaID']}")
    plan, today = {}, datetime.datetime.strptime(crt, "%Y%m%d").date()
    cnt = {"CGV": len(PROBE["CGV"]), "LC": len(lc_ids), "MB": len(PROBE["MB"])}
    dead, streak = set(), {"CGV": 0, "LC": 0, "MB": 0}   # 탐침이 이틀 연속 전부 실패하면 그 체인은 이번 회차 포기
    mb_h = {"Content-Type": "application/json; charset=UTF-8", "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.megabox.co.kr/booking/timetable"}
    for d in dates:
        play, iso = d.strftime("%Y%m%d"), d.isoformat()
        got, err = set(), {"CGV": 0, "LC": 0, "MB": 0}
        for sn in ([] if "CGV" in dead else PROBE["CGV"]):
            try:
                r = fs.http_json(f"{fs.CGV}/api/v1/booking/searchMovScnInfo?coCd=A420&siteNo={sn}&scnYmd={play}&rtctlScopCd=08", tries=1)
                if any(film_of(x.get("prodNm")) for x in _cgv_rows(r)):
                    got.add("CGV"); break
            except Exception:
                err["CGV"] += 1
            nap(0.1)
        for cid in ([] if "LC" in dead else lc_ids):
            try:
                s = fs.lc_call({"MethodName": "GetPlaySequence", **base, "playDate": iso, "cinemaID": cid, "representationMovieCode": ""})
                if any(film_of(x.get("MovieNameKR")) for x in ((s.get("PlaySeqs") or {}).get("Items")) or []):
                    got.add("LC"); break
            except Exception:
                err["LC"] += 1
            nap(0.1)
        for bn in ([] if "MB" in dead else PROBE["MB"]):
            try:   # 탐침은 1회·20초 — mb_post(3회·40초)로 찌르면 막힌 날 탐침만 수십 분이 된다
                body = json.dumps({"masterType": "brch", "brchNo": bn, "firstAt": "N", "brchNo1": bn,
                                   "crtDe": crt, "playDe": play}).encode()
                rows = (fs.http_json(fs.MB_URL, data=body, headers=mb_h, timeout=20, tries=1)
                        .get("megaMap", {}).get("movieFormList")) or []
                if any(film_of(x.get("rpstMovieNm")) for x in rows):
                    got.add("MB"); break
            except Exception:
                err["MB"] += 1
            nap(0.1)
        near = (d - today).days <= 7
        for ch, n in err.items():
            if ch in dead or not cnt[ch]:
                continue
            if n >= cnt[ch]:                            # 전부 실패 = 편성 여부를 모름
                streak[ch] += 1
                if streak[ch] >= 2:
                    dead.add(ch); print(f"  {ch} 탐침 이틀 연속 전부 실패 — 이번 회차 제외(차단 추정)")
                elif near and ch not in got:
                    got.add(ch)                         # 가까운 날짜는 편성된 것으로 보고 전수에서 한 번 더 확인
            else:
                streak[ch] = 0
        for ch in dead:
            got.discard(ch)
        if got:
            plan[play] = got
    for p in plan:                                       # 뒤늦게 죽은 체인은 앞 날짜 계획에서도 뺀다
        plan[p] -= dead
    plan = {p: c for p, c in plan.items() if c}
    return plan, cins, dead


def seats(plan, cins, crt):
    """plan = {play: set(체인)} → ({(title, play): {체인: 집계}}, 실패한 체인 집합)"""
    import concurrent.futures as cf
    import fetch_screens as fs

    def acc():
        return {"sites": set(), "screens": set(), "shows": 0, "seatTot": 0, "seatSold": 0}

    def add(res, title, play, site, screen, t, r):
        a = res.setdefault((title, play), acc())
        a["sites"].add(site); a["screens"].add((site, screen)); a["shows"] += 1
        a["seatTot"] += t; a["seatSold"] += max(0, t - r)

    plays_of = lambda ch: [p for p in sorted(plan) if ch in plan[p]]     # 가까운 날짜부터 — 시간이 모자라면 먼 날이 잘린다
    deadline = time.time() + SEAT_BUDGET
    cut = {}                                                               # 체인 -> 시간 예산에 걸려 못 본 상영일
    # 동시 요청 수는 체인마다 다르다 — 롯데는 4개 병렬도 멀쩡했지만(510 vs 순차 527스크린, 차이는 지난 회차)
    #   **CGV 는 병렬로 부르면 절반 넘게 거절한다**(2026-09-26 실측: 암살자 CGV 583→185스크린, 이튿날은 0).
    #   CGV 는 Cloudflare 뒤라 순간 요청이 몰리면 막힌다. 순차 + 0.12초 간격을 지킨다.
    POOL = {"CGV": 1, "LC": 4}

    def sweep(ch, plays, items, fetch):
        """상영일마다 items(지점)를 POOL 개씩 병렬로 부르고 결과 행을 모은다. 예산을 넘기면 남은 날짜는 cut."""
        rows = []
        for i, play in enumerate(plays):
            if time.time() > deadline:
                cut[ch] = set(plays[i:]); print(f"  {ch} 시간 예산 초과 — {len(plays) - i}일 생략(먼 날짜부터)"); break
            with cf.ThreadPoolExecutor(POOL.get(ch, 1)) as ex:
                for got in ex.map(lambda it: fetch(play, it), items):
                    rows.extend(got or [])
        return rows

    def run_cgv():
        res, plays = {}, plays_of("CGV")
        if not plays:
            return res
        lst = fs.http_json(f"{fs.CGV}/api/v1/booking/searchAtktTopPostrList?coCd=A420&movNm=&div=&attrCd=")
        nos = [x["movNo"] for x in (lst.get("data") or []) if film_of(x.get("movNm"))]
        sites = set()
        for no in nos:
            reg = fs.http_json(f"{fs.CGV}/api/v1/booking/searchRegnList?movNo={no}&coCd=A420")
            sites |= {s["siteNo"] for g in (reg.get("data") or []) for s in (g.get("siteList") or []) if s.get("siteNo")}
            nap(0.2)
        print(f"  CGV 대상 {len(nos)}편 · 지점 {len(sites)}곳 × 상영일 {len(plays)}")

        def one(play, sn):
            try:
                d = fs.http_json(f"{fs.CGV}/api/v1/booking/searchMovScnInfo?coCd=A420&siteNo={sn}&scnYmd={play}&rtctlScopCd=08")
            except Exception:
                return []
            nap(0.12)
            return [(t, play, sn, o.get("scnsNo"), int(o.get("stcnt") or 0), int(o.get("frSeatCnt") or 0))
                    for o in _cgv_rows(d) for t in [film_of(o["prodNm"])] if t]
        for r in sweep("CGV", plays, sorted(sites), one):
            add(res, *r)
        return res

    def run_lc():
        res, plays = {}, plays_of("LC")
        if not plays:
            return res
        base = {"channelType": "HO", "osType": "W", "osVersion": fs.UA, "memberOnNo": ""}
        print(f"  롯데 영화관 {len(cins)}곳 × 상영일 {len(plays)}")

        def one(play, c):
            cid = f"{c['DivisionCode']}|{c['DetailDivisionCode']}|{c['CinemaID']}"
            try:
                s2 = fs.lc_call({"MethodName": "GetPlaySequence", **base, "playDate": f"{play[:4]}-{play[4:6]}-{play[6:]}",
                                 "cinemaID": cid, "representationMovieCode": ""})
            except Exception:
                return []
            nap(0.1)
            # BookingSeatCount 는 이름과 달리 '잔여'다(fetch_screens 검증 2)
            return [(t, play, cid, x.get("ScreenNameKR"), int(x.get("TotalSeatCount") or 0), int(x.get("BookingSeatCount") or 0))
                    for x in ((s2.get("PlaySeqs") or {}).get("Items")) or [] for t in [film_of(x.get("MovieNameKR"))] if t]
        for r in sweep("LC", plays, cins, one):
            add(res, *r)
        return res

    def run_mb():
        res, plays = {}, plays_of("MB")
        if not plays:
            return res
        # 메가는 러너에서 간헐 시간초과다. fetch_screens.mb_post(3회×40초)로 부르면 한 번 막힐 때 2분씩 묶여
        # 전체가 한 시간을 넘긴다(2026-09-26 서버 첫 실행). 여기선 2회×20초 + 연속 6번 실패면 체인을 접는다.
        mb_h = {"Content-Type": "application/json; charset=UTF-8", "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://www.megabox.co.kr/booking/timetable"}
        fails = [0]

        def mb(body):
            try:
                r = fs.http_json(fs.MB_URL, data=json.dumps(body).encode(), headers=mb_h, timeout=20, tries=2)
                fails[0] = 0
                return r
            except Exception:
                fails[0] += 1
                if fails[0] >= 6:
                    raise RuntimeError("메가박스 연속 6회 실패 — 이번 회차 제외")
                return {}
        nos = {}
        for play in plays:                       # 날짜마다 걸린 영화가 달라 합집합
            for bn in PROBE["MB"]:
                rows = (mb({"masterType": "brch", "brchNo": bn, "firstAt": "N", "brchNo1": bn,
                            "crtDe": crt, "playDe": play}).get("megaMap", {}).get("movieFormList")) or []
                for x in rows:
                    t = film_of(x.get("rpstMovieNm"))
                    if t and x.get("rpstMovieNo"):
                        nos[x["rpstMovieNo"]] = t
        print(f"  메가 대상 {len(set(nos.values()))}편 × 지역 8 × 상영일 {len(plays)}")
        for i, play in enumerate(plays):
            if time.time() > deadline:
                cut["MB"] = set(plays[i:]); print(f"  MB 시간 예산 초과 — {len(plays) - i}일 생략"); break
            for no, t in nos.items():
                for cd in fs.MB_AREAS:
                    dd = mb({"masterType": "movie", "movieNo": no, "firstAt": "N", "movieNo1": no,
                             "areaCd": int(cd), "crtDe": crt, "playDe": play})
                    for x in (dd.get("megaMap", {}).get("movieFormList")) or []:
                        add(res, t, play, x.get("brchNo"), x.get("theabNo"),
                            int(x.get("totSeatCnt") or 0), int(x.get("restSeatCnt") or 0))
                    nap(0.2)
        return res

    out, failed = {}, set()
    with cf.ThreadPoolExecutor(3) as ex:
        futs = {ex.submit(fn): ch for ch, fn in (("CGV", run_cgv), ("LC", run_lc), ("MB", run_mb))}
        for f in cf.as_completed(futs):
            ch = futs[f]
            try:
                for k, a in f.result().items():
                    out.setdefault(k, {})[ch] = {"sites": len(a["sites"]), "screens": len(a["screens"]),
                                                 "shows": a["shows"], "seatTot": a["seatTot"], "seatSold": a["seatSold"]}
                note_health(ch, None)
            except Exception as e:
                failed.add(ch)
                print(f"  {ch} 실패: {type(e).__name__} {str(e)[:80]}")
    return out, failed, cut


def collect_seats(crt):
    """탐침 → 전수. 결과는 JSON 으로 옮길 수 있는 꼴(캐시 파일·병합 공용)."""
    import fetch_screens as fs
    t0 = time.time()
    today = datetime.datetime.strptime(crt, "%Y%m%d").date()
    dates = [today + datetime.timedelta(days=i) for i in range(SEAT_DAYS + 1)]
    plan, cins, dead = seat_plan(fs, dates, crt)
    desc = ", ".join(p[4:6] + "/" + p[6:] + ":" + "".join(sorted(c)) for p, c in sorted(plan.items()))
    print(f"  편성 탐침 · {desc}")
    res, failed, cut = seats(plan, cins, crt)
    failed |= dead
    for ch, ps in cut.items():                           # 시간 예산으로 못 본 (날짜, 체인)은 '연 체인'에서도 뺀다
        for p in ps:
            if p in plan:
                plan[p].discard(ch)
    plan = {p: c for p, c in plan.items() if c}
    print(f"  3사 전수 {time.time() - t0:.0f}초 · (영화×상영일) {len(res)}건" + (f" · 실패 {sorted(failed)}" if failed else ""))
    return {"t": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
            "plan": {p: sorted(c) for p, c in plan.items()}, "failed": sorted(failed),
            "res": [{"title": t, "play": p, "by": by} for (t, p), by in sorted(res.items())]}


SEAT_SNAPS = 30          # (영화, 상영일)마다 수집일 스냅샷 보관 수(하루 1점 기준 한 달)
SEAT_PAST = 10           # 지난 상영일은 이만큼(일)까지 화면 블록에 둔다 — 그 뒤는 archive 에만


def merge_seats(out, cache, today):
    """캐시(collect_seats 결과)를 BOXOFFICE.seats 에 합친다.
       · 수집일마다 1점 — 같은 날 여러 번 받으면 마지막 것으로 바꿔 낀다(일별 추적).
       · 체인별 내역(by)은 지난 점에도 판매·총좌석·스크린만 남긴다 — 서버는 CGV 가 막혀(403) 날마다
         잡히는 체인이 다를 수 있어, 화면이 '두 수집에 다 있는 체인'끼리만 비교하게 하려는 것이다.
         (예전 fetch_screens 처럼 빠진 체인을 직전 값으로 이어받으면, 한국 IP 에서 받은 CGV 값이
          서버 회차마다 끝없이 복사돼 굳은 숫자가 된다.)"""
    stamp, failed = cache["t"], set(cache.get("failed") or [])
    ser = out.setdefault("seats", {})
    lines = []
    slim = lambda by: {c: {k: v[k] for k in ("seatSold", "seatTot", "screens")} for c, v in (by or {}).items()}
    newest = max([p["t"] for v in ser.values() for p in v] or [""])
    for r in cache["res"]:
        key = f"{r['title']}|{r['play']}"
        by, t = dict(r["by"]), stamp
        # 같은 날 두 번째 수집이면 **체인별로 합친다** — 한국 IP 에서 받은 3사(CGV 포함) 뒤에 서버가 롯데·메가만
        # 받아 오면, 통째로 바꿔 끼울 때 그날 CGV 가 사라졌다(2026-09-26 치이카와 개봉일 10.1만→7.1만석).
        # 겹치는 체인은 더 최근 값, 한쪽에만 있는 체인은 그 값. 날짜가 다르면 섞지 않는다(굳은 숫자 방지).
        same = next((p for p in ser.get(key, []) if p.get("t", "")[:10] == stamp[:10]), None)
        if same:
            old = same.get("by") or {}
            by = {**old, **by} if stamp >= same.get("t", "") else {**by, **old}
            t = max(stamp, same.get("t", ""))
        tot = {k: sum(v.get(k, 0) for v in by.values()) for k in ("sites", "screens", "shows", "seatTot", "seatSold")}
        pts = [{**{k: v for k, v in p.items() if k != "by"}, "by": slim(p.get("by"))}
               for p in ser.get(key, []) if p.get("t", "")[:10] != stamp[:10]]
        pts.append({"t": t, **tot, "by": by})
        ser[key] = pts[-SEAT_SNAPS:]
        lines.append({"t": stamp, "title": r["title"], "play": r["play"], **tot, "by": dict(r["by"])})
    cut = (today - datetime.timedelta(days=SEAT_PAST)).strftime("%Y%m%d")
    for k in [k for k in ser if k.split("|")[1] < cut]:
        del ser[k]
    older = stamp < newest                  # 지난 캐시를 다시 끼우는 경우(예: 같은 날 한국 IP 수집분 복원)
    if not older:
        out["seatsAt"] = stamp
        out["seatPlan"] = cache.get("plan") or {}
        out["seatFailed"] = sorted(failed)
    else:                                   # 계획·실패 목록은 최신 수집 것을 두고, 연 체인만 합집합
        pl = out.setdefault("seatPlan", {})
        for p, c in (cache.get("plan") or {}).items():
            pl[p] = sorted(set(pl.get(p, [])) | set(c))
        got = {c for cs in (cache.get("plan") or {}).values() for c in cs}
        out["seatFailed"] = sorted(set(out.get("seatFailed") or []) - got)
    out.pop("plays", None)
    # 영구 아카이브 — 화면 블록은 잘리지만 여기는 append 만 한다(다음 극장판의 기준선).
    import os
    os.makedirs("archive", exist_ok=True)
    with open("archive/boxoffice_seats.jsonl", "a", encoding="utf-8") as f:
        for ln in ([] if older else lines):     # 지난 캐시 재주입은 이미 archive 에 있다 — 두 번 쓰지 않는다
            f.write(json.dumps(ln, ensure_ascii=False) + "\n")
    for ln in sorted(lines, key=lambda x: (x["play"], -x["seatSold"])):
        rate = ln["seatSold"] / ln["seatTot"] * 100 if ln["seatTot"] else 0
        print(f"  [{ln['play']}] {ln['title'][:14]} · 스크린 {ln['screens']} · 판매 {ln['seatSold']:,}/{ln['seatTot']:,} ({rate:.1f}%)")


# ── 기준선: 하츄핑2(SAMG) 개봉 전 예매·좌석 — archive/*.jsonl ────────
#   같은 애니메이션 극장판이라 치이카와의 '개봉 N일 전' 수요를 견줄 유일한 실측 잣대다.
#   KOBIS 는 예매 이력을 안 남겨서 우리가 쌓은 아카이브가 원본이다(fetch_movie·fetch_screens 가 append).
#   ⚠ 개봉 당일(D+0) 좌석은 지난 회차가 빠지고 CGV 는 hot 수집만 돼 작게 잡힌다 — 개봉 전(D-N)만 싣는다.
REF = {"title": "사랑의 하츄핑: 고래보석의 전설", "short": "하츄핑2", "open": "2026-08-05"}


def ref_baseline():
    import os
    od = datetime.date.fromisoformat(REF["open"])
    lo, hi = od - datetime.timedelta(days=10), od + datetime.timedelta(days=7)
    out = {**REF, "book": [], "seats": []}
    if os.path.exists("archive/booking.jsonl"):
        for line in open("archive/booking.jsonl", encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("title") != REF["title"] or len(r.get("t") or "") < 16:
                continue
            d = datetime.date.fromisoformat(r["t"][:10])
            if lo <= d <= hi:
                out["book"].append({k: r.get(k) for k in ("t", "rank", "rate", "book", "acc")})
    if os.path.exists("archive/screens.jsonl"):
        play = REF["open"].replace("-", "")
        last = {}
        for line in open("archive/screens.jsonl", encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("play") != play or "하츄핑" not in (r.get("title") or ""):
                continue
            if len(r.get("by") or {}) < 3 or r["t"][:10] >= REF["open"]:
                continue                                  # 3사가 다 잡힌 개봉 전 스냅샷만
            last[r["t"][:10]] = {k: r.get(k) for k in ("t", "screens", "shows", "seatSold", "seatTot")}
        out["seats"] = [last[k] for k in sorted(last)]
    return out


# ── index.html ────────────────────────────────────────────
def _block(h):
    m = re.search(r"const BOXOFFICE = (\{.*?\});\n", h, re.S)
    return (json.loads(m.group(1)), m) if m else ({}, None)


def main():
    now = datetime.datetime.now(KST)
    today = now.date()
    if today.isoformat() > UNTIL:
        print(f"[극장가] 추적 기한({UNTIL}) 경과 — 수집 안 함"); return
    stamp = now.strftime("%Y-%m-%d %H:%M")
    # 3사 전수는 20~30분 걸린다. 그 사이 원격이 움직이므로 PC 자동 실행(kr_boxoffice.py)은
    #   ① --seats --cache=파일 로 받기만 하고  ② 원격 최신으로 맞춘 뒤 --merge=파일 로 끼워 넣는다(재주입 규칙).
    seat_cache = None
    cache_out = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--cache=")), None)
    merge_in = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--merge=")), None)
    if "--seats" in sys.argv:
        seat_cache = collect_seats(today.strftime("%Y%m%d"))
        if cache_out:
            import os
            os.makedirs(os.path.dirname(cache_out) or ".", exist_ok=True)
            json.dump(seat_cache, open(cache_out, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"[캐시] {cache_out} · (영화×상영일) {len(seat_cache['res'])}건"); return
    elif merge_in:
        seat_cache = json.load(open(merge_in, encoding="utf-8"))
        print(f"[병합] {merge_in} · {seat_cache['t']} 수집분 {len(seat_cache['res'])}건")
    h = open(HTML, encoding="utf-8").read()
    old, _ = _block(h)
    out = json.loads(json.dumps(old)) if old else {}      # 깊은 복사 — 변동 비교를 위해 old 는 그대로 둔다
    days = out.setdefault("daily", {})
    mkt = out.setdefault("market", {})
    scanned = set(out.get("scanned") or [])
    fails = []

    # ② 예매 먼저 — 매번 바뀌는 값이라 백필보다 우선
    try:
        bk, n = booking()
        for t, v in bk.items():
            pts = [p for p in out.setdefault("book", {}).get(t, []) if p.get("t") != stamp]
            pts.append({"t": stamp, **v})
            out["book"][t] = pts[-BOOK_KEEP:]
            print(f"  [예매] {t} · {v['rank']}위 · {v['rate']}% · 예매 {v['book']:,} · 누적 {v['acc']:,}")
        if not n:
            fails.append("예매 표 0행")
    except Exception as e:
        fails.append(f"예매 {type(e).__name__}")
        print(f"  예매 실패: {e}")

    # ① 일별 — 어제까지가 확정치. 최근 2일은 늦게 확정되는 일이 있어 다시 본다.
    y = today - datetime.timedelta(days=1)
    want, d = [], datetime.datetime.strptime(SCAN_FROM, "%Y%m%d").date()
    while d <= y:
        want.append(d.strftime("%Y%m%d")); d += datetime.timedelta(days=1)
    recheck = {(y - datetime.timedelta(days=i)).strftime("%Y%m%d") for i in range(2)}
    todo = [x for x in want if x not in scanned or x in recheck][:60]
    for ymd in todo:
        try:
            got, tot, n = daily(ymd)
        except Exception as e:
            print(f"  {ymd} 일별 실패: {str(e)[:60]}"); fails.append(f"일별 {ymd}"); continue
        if not n:
            print(f"  {ymd} 빈 표 — 다음에 재시도"); continue
        scanned.add(ymd)
        mkt[ymd] = tot
        for t, v in got.items():
            pts = [p for p in days.get(t, []) if p["d"] != ymd]
            pts.append(v)
            days[t] = sorted(pts, key=lambda p: p["d"])
        nap(0.3)
    print(f"  일별 {len(todo)}일 훑음({todo[0] if todo else '-'}~{todo[-1] if todo else '-'})")
    out["scanned"] = sorted(scanned)

    # ③ 3사 좌석 — 방금 받았거나(--seats) 캐시에서 읽은(--merge) 결과를 합친다
    if seat_cache:
        merge_seats(out, seat_cache, today)

    out["films"] = FILMS
    out["until"] = UNTIL
    try:
        out["ref"] = ref_baseline()
    except Exception as e:
        print(f"  기준선(하츄핑2) 실패: {e}")
    if fails and len(fails) >= 2:
        note_health("극장가(KOBIS)", " · ".join(fails[:4]))
    elif not fails:
        note_health("극장가(KOBIS)", None)

    cmp_old = {k: v for k, v in old.items() if k != "asOf"}
    cmp_new = {k: v for k, v in out.items() if k != "asOf"}
    if old and cmp_old == cmp_new:
        print("[극장가] 변동 없음 — 파일 유지"); return
    res = {"asOf": stamp, "until": UNTIL, **{k: v for k, v in out.items() if k not in ("asOf", "until")}}
    if "--dry-run" in sys.argv:
        print(f"(dry-run · {len(json.dumps(res, ensure_ascii=False)):,}자)"); return
    # 3사 수집이 십수 분 걸리므로 쓰기 직전에 다시 읽어 이 블록만 갈아 끼운다(fetch_screens 와 같은 이유).
    h = open(HTML, encoding="utf-8").read()
    _, m = _block(h)
    block = "const BOXOFFICE = " + json.dumps(res, ensure_ascii=False, separators=(",", ":")) + ";\n"
    if m:
        h = h[:m.start()] + block + h[m.end():]
    else:
        a = re.search(r"const MOVIE = \{", h)
        if not a:
            print("삽입 위치(const MOVIE)를 못 찾음"); sys.exit(1)
        h = h[:a.start()] + block + h[a.start():]
    open(HTML, "w", encoding="utf-8").write(h)
    print(f"[OK] BOXOFFICE 갱신 · 일별 {sum(len(v) for v in days.values())}점 · 예매 {len(out.get('book', {}))}편")


if __name__ == "__main__":
    main()
