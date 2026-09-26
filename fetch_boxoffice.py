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

  python fetch_boxoffice.py              # ①② (러너)
  python fetch_boxoffice.py --seats      # ①②③ (이 PC · 15분 안팎)
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
SEAT_KEEP = 60

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
def seats(plays, crt):
    import fetch_screens as fs

    def acc():
        return {"sites": set(), "screens": set(), "shows": 0, "seatTot": 0, "seatSold": 0}

    def add(a, site, screen, t, r):
        a["sites"].add(site); a["screens"].add((site, screen)); a["shows"] += 1
        a["seatTot"] += t; a["seatSold"] += max(0, t - r)

    res = {}                                    # (title, play) -> chain -> acc
    def bucket(title, play, chain):
        return res.setdefault((title, play), {}).setdefault(chain, acc())

    # CGV — 지점 하나가 그날 전 영화를 준다. 대상 영화를 거는 지점의 합집합만 훑는다.
    try:
        lst = fs.http_json(f"{fs.CGV}/api/v1/booking/searchAtktTopPostrList?coCd=A420&movNm=&div=&attrCd=")
        nos = [x["movNo"] for x in (lst.get("data") or []) if film_of(x.get("movNm"))]
        sites = set()
        for no in nos:
            reg = fs.http_json(f"{fs.CGV}/api/v1/booking/searchRegnList?movNo={no}&coCd=A420")
            sites |= {s["siteNo"] for g in (reg.get("data") or []) for s in (g.get("siteList") or []) if s.get("siteNo")}
            nap(0.2)
        print(f"  CGV 대상 {len(nos)}편 · 지점 {len(sites)}곳")
        for play in plays:
            for sn in sorted(sites):
                try:
                    d = fs.http_json(f"{fs.CGV}/api/v1/booking/searchMovScnInfo?coCd=A420&siteNo={sn}&scnYmd={play}&rtctlScopCd=08")
                except Exception:
                    continue
                stack = [d.get("data")]
                while stack:
                    o = stack.pop()
                    if isinstance(o, list):
                        stack.extend(o)
                    elif isinstance(o, dict):
                        if o.get("prodNm") and o.get("scnsNo"):
                            t = film_of(o["prodNm"])
                            if t:
                                add(bucket(t, play, "CGV"), sn, o.get("scnsNo"),
                                    int(o.get("stcnt") or 0), int(o.get("frSeatCnt") or 0))
                        stack.extend(v for v in o.values() if isinstance(v, (list, dict)))
                nap(0.15)
        note_health("CGV", None)
    except Exception as e:
        print(f"  CGV 실패: {type(e).__name__} {str(e)[:80]}")

    # 롯데 — representationMovieCode 를 비우면 그 영화관의 전 영화가 온다.
    try:
        base = {"channelType": "HO", "osType": "W", "osVersion": fs.UA, "memberOnNo": ""}
        d = fs.lc_call({"MethodName": "GetTicketingPage", **base})
        cins = ((d.get("Cinemas") or {}).get("Cinemas") or {}).get("Items") or []
        print(f"  롯데 영화관 {len(cins)}곳")
        for play in plays:
            iso = f"{play[:4]}-{play[4:6]}-{play[6:]}"
            for c in cins:
                cid = f"{c['DivisionCode']}|{c['DetailDivisionCode']}|{c['CinemaID']}"
                try:
                    s = fs.lc_call({"MethodName": "GetPlaySequence", **base, "playDate": iso,
                                    "cinemaID": cid, "representationMovieCode": ""})
                except Exception:
                    nap(0.12); continue
                for x in ((s.get("PlaySeqs") or {}).get("Items")) or []:
                    t = film_of(x.get("MovieNameKR"))
                    if t:   # BookingSeatCount 는 이름과 달리 '잔여'다(fetch_screens 검증 2)
                        add(bucket(t, play, "LC"), cid, x.get("ScreenNameKR"),
                            int(x.get("TotalSeatCount") or 0), int(x.get("BookingSeatCount") or 0))
                nap(0.12)
    except Exception as e:
        print(f"  롯데 실패: {type(e).__name__} {str(e)[:80]}")

    # 메가 — 강남점 목록으로 영화번호를 얻고(날짜마다 걸린 영화가 달라 합집합) 영화 × 지역 8곳.
    try:
        nos = {}
        for play in plays:
            rows = (fs.mb_post({"masterType": "brch", "brchNo": "1372", "firstAt": "N", "brchNo1": "1372",
                                "crtDe": crt, "playDe": play}).get("megaMap", {}).get("movieFormList")) or []
            for x in rows:
                t = film_of(x.get("rpstMovieNm"))
                if t and x.get("rpstMovieNo"):
                    nos[x["rpstMovieNo"]] = t
        print(f"  메가 대상 {len(set(nos.values()))}편")
        for play in plays:
            for no, t in nos.items():
                for cd in fs.MB_AREAS:
                    dd = fs.mb_post({"masterType": "movie", "movieNo": no, "firstAt": "N", "movieNo1": no,
                                     "areaCd": int(cd), "crtDe": crt, "playDe": play})
                    for x in (dd.get("megaMap", {}).get("movieFormList")) or []:
                        add(bucket(t, play, "MB"), x.get("brchNo"), x.get("theabNo"),
                            int(x.get("totSeatCnt") or 0), int(x.get("restSeatCnt") or 0))
                    nap(0.25)
    except Exception as e:
        print(f"  메가 실패: {type(e).__name__} {str(e)[:80]}")

    fin = lambda a: {"sites": len(a["sites"]), "screens": len(a["screens"]), "shows": a["shows"],
                     "seatTot": a["seatTot"], "seatSold": a["seatSold"]}
    return {k: {ch: fin(a) for ch, a in v.items()} for k, v in res.items()}


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

    # ③ 3사 좌석
    if "--seats" in sys.argv:
        plays = {today, today + datetime.timedelta(days=1)}
        for f in FILMS:                                   # 개봉일과 그 주말 첫 토요일
            od = datetime.date.fromisoformat(f["open"])
            if od >= today:
                plays.add(od)
                plays.add(od + datetime.timedelta(days=(5 - od.weekday()) % 7))
        plays = sorted(p.strftime("%Y%m%d") for p in plays)
        print(f"  3사 좌석 · 상영일 {', '.join(plays)}")
        res = seats(plays, today.strftime("%Y%m%d"))
        ser = out.setdefault("seats", {})
        for (t, play), by in res.items():
            tot = {k: sum(v[k] for v in by.values()) for k in ("sites", "screens", "shows", "seatTot", "seatSold")}
            key = f"{t}|{play}"
            pts = [p for p in ser.get(key, []) if p.get("t") != stamp]
            pts.append({"t": stamp, **tot, "by": by})
            ser[key] = pts[-SEAT_KEEP:]
            rate = tot["seatSold"] / tot["seatTot"] * 100 if tot["seatTot"] else 0
            print(f"  [{play}] {t} · 스크린 {tot['screens']} · 회차 {tot['shows']} · "
                  f"판매 {tot['seatSold']:,}/{tot['seatTot']:,} ({rate:.1f}%) · "
                  + " ".join(f"{c} {v['screens']}관" for c, v in by.items()))
        out["seatsAt"] = stamp
        out["plays"] = plays

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
