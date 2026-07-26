# -*- coding: utf-8 -*-
"""
영화 흥행 수집 (KOBIS 영화관입장권통합전산망) -> index.html 의  const MOVIE = {...};

SAMG엔터는 극장판 흥행이 실적에 직결된다(「사랑의 하츄핑」 100만 돌파, 2편 개봉 예정).
관객수는 검색 트렌드와 달리 확정 수치라 추정이 필요 없다.

수집 구조상 주의:
  일별 박스오피스 API 는 '그날의 Top 10' 만 준다. 특정 영화를 지목해 조회할 수 없다.
  따라서 날짜별로 훑어 대상 영화가 순위에 뜬 날만 기록한다.
  개봉 초기에는 확실히 잡히고, 10위 밖으로 밀리면 그날부터 끊긴다
  (누적 관객수는 마지막으로 잡힌 값이 남는다).

  과거는 날짜마다 1회씩 호출해야 해서 첫 실행이 무겁다.
  MAX_BACKFILL 로 한 번에 훑는 날짜 수를 제한하고, 남은 구간은 다음 실행이 이어받는다.
"""
import urllib.request, urllib.parse, json, re, sys, os, time, datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML_PATH = "public/index.html"
KEY = os.environ.get("KOBIS_KEY", "")
BASE = "http://www.kobis.or.kr/kobisopenapi/webservice/rest"
UA = {"User-Agent": "Mozilla/5.0"}

# 커버리지와 엮인 영화만 잡는다. 제목에 이 말이 들어가면 대상.
WATCH = [
    {"stock": "SAMG엔터", "match": ["하츄핑", "티니핑"]},
]
# 훑을 구간 — 개봉 전후만 본다. 그 밖은 호출 낭비다.
#   1편 사랑의 하츄핑           2024-08 개봉 · 누적 124만  <- 2편 비교 기준선
#   2편 사랑의 하츄핑2(고래보석) 2026-08-05 개봉
# 1편 구간을 채워 둬야 2편을 '개봉 N일차' 기준으로 겹쳐 볼 수 있다.
WINDOWS = [
    ("20240801", "20241110"),   # 1편 (개봉~장기상영)
    ("20260801", None),         # 2편 (None = 어제까지)
]
MAX_BACKFILL = 40      # 한 번에 훑을 최대 날짜 수 (남은 구간은 다음 실행이 이어받음)


def getj(url, timeout=60, tries=3):
    """KOBIS 는 깃허브 러너에서 응답이 느려 20초로는 절반이 타임아웃난다.
       넉넉히 잡고 재시도한다."""
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8"))
        except Exception as e:
            last = e
            if i < tries - 1:
                time.sleep(3 * (i + 1))
    raise last


def daily(dt):
    """그날 Top10. 반환: [{movieCd, movieNm, audiCnt, audiAcc, scrnCnt, showCnt, salesAmt}]"""
    d = getj(f"{BASE}/boxoffice/searchDailyBoxOfficeList.json?key={KEY}&targetDt={dt}")
    if "faultInfo" in d:
        raise RuntimeError(d["faultInfo"].get("message", "")[:80])
    return (d.get("boxOfficeResult") or {}).get("dailyBoxOfficeList") or []


def matched(name):
    for w in WATCH:
        if any(m in name for m in w["match"]):
            return w["stock"]
    return None


def fetch_booking():
    """실시간 예매율 (KOFIC 통계 페이지).

       OpenAPI 는 예매 정보를 주지 않는다. 개봉 전 관객은 예매에서만 보이므로
       공개 통계 페이지를 파싱한다. 세션 쿠키를 먼저 받아야 표가 채워져 온다
       (쿠키 없이 POST 하면 껍데기만 온다).

       표 구조: <tr> 안에 td 8개
         순위 · 영화명 · 개봉일 · 예매율 · 예매매출 · 누적매출 · 예매관객 · 누적관객
       화면 구조가 바뀌면 조용히 빈 결과가 되므로 실패해도 본 수집은 계속한다."""
    import http.cookiejar
    base = "https://www.kobis.or.kr/kobis/business/stat/boxs/findRealTicketList.do"
    body = urllib.parse.urlencode({"loadEnd": 0, "searchType": "real"}).encode()
    # 깃허브 러너에서 KOBIS 응답이 아주 느리다(30초로는 타임아웃). 넉넉히 잡고 재시도한다.
    last = None
    html = None
    for attempt in range(3):
        try:
            cj = http.cookiejar.CookieJar()
            op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
            op.addheaders = [("User-Agent", UA["User-Agent"]), ("Referer", base),
                             ("X-Requested-With", "XMLHttpRequest")]
            op.open(base, timeout=90).read()               # 세션 발급
            html = op.open(urllib.request.Request(base, data=body),
                           timeout=90).read().decode("utf-8", "replace")
            break
        except Exception as e:
            last = e
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
    if html is None:
        raise last

    strip = re.compile(r"<[^>]*>")
    out = []
    for chunk in html.split("<tr ")[1:]:
        cells = [strip.sub("", c).strip() for c in chunk.split("</td>")]
        cells = [c for c in cells if c]
        if len(cells) < 8:
            continue
        name = cells[1]
        if not matched(name):
            continue
        num = lambda s: int(re.sub(r"[^\d]", "", s) or 0)
        out.append({"nm": name, "openDt": cells[2],
                    "rate": float(re.sub(r"[^\d.]", "", cells[3]) or 0),
                    "bookAmt": num(cells[4]), "accAmt": num(cells[5]),
                    "book": num(cells[6]), "acc": num(cells[7])})
    return out


def main():
    if not KEY:
        print("KOBIS_KEY 가 없습니다."); sys.exit(1)

    html = open(HTML_PATH, encoding="utf-8").read()
    old = {}
    m = re.search(r"const MOVIE = (\{.*?\});\n", html, re.S)
    if m:
        try:
            old = json.loads(m.group(1))
        except json.JSONDecodeError:
            old = {}
    movies = dict(old.get("movies") or {})
    scanned = set(old.get("scanned") or [])      # 이미 훑은 날짜 — 재조회를 막는다

    kst = datetime.timezone(datetime.timedelta(hours=9))
    today = datetime.datetime.now(kst).date()
    # 어제까지가 확정치다. 오늘 자료는 아직 안 나온다.
    yesterday = today - datetime.timedelta(days=1)
    dates = []
    for a, b in WINDOWS:
        s = datetime.datetime.strptime(a, "%Y%m%d").date()
        e = yesterday if b is None else datetime.datetime.strptime(b, "%Y%m%d").date()
        e = min(e, yesterday)                     # 미래 날짜는 자료가 없다
        d = s
        while d <= e:
            dates.append(d.strftime("%Y%m%d"))
            d += datetime.timedelta(days=1)
    todo = [x for x in dates if x not in scanned][:MAX_BACKFILL]
    # 훑을 박스오피스 날짜가 없어도 여기서 끝내면 안 된다 —
    # 예매율은 개봉 전에도 매일 바뀌므로 아래에서 따로 받아야 한다.
    if not todo:
        print(f"새로 훑을 박스오피스 날짜 없음 (누적 {len(scanned)}일 완료)")
    else:
        print(f"훑을 날짜 {len(todo)}일 ({todo[0]}~{todo[-1]}) · 남은 구간 "
              f"{max(0, len([x for x in dates if x not in scanned]) - len(todo))}일")

    hit = 0
    for dt in todo:
        try:
            rows = daily(dt)
        except Exception as e:
            print(f"  {dt} 실패: {str(e)[:70]}")
            continue
        scanned.add(dt)
        for r in rows:
            stock = matched(r.get("movieNm", ""))
            if not stock:
                continue
            nm = r["movieNm"]
            mv = movies.setdefault(nm, {"stock": stock, "code": r.get("movieCd"),
                                        "openDt": r.get("openDt"), "days": []})
            if any(p["d"] == dt for p in mv["days"]):
                continue
            mv["days"].append({
                "d": dt,
                "audi": int(r.get("audiCnt") or 0),        # 그날 관객수
                "acc": int(r.get("audiAcc") or 0),         # 누적 관객수
                "scrn": int(r.get("scrnCnt") or 0),        # 스크린수
                "sales": int(r.get("salesAmt") or 0),      # 그날 매출액
                "rank": int(r.get("rank") or 0)})
            hit += 1
        time.sleep(0.2)

    for mv in movies.values():
        mv["days"].sort(key=lambda x: x["d"])

    if not movies:
        print(f"{len(todo)}일 훑음 · 대상 영화 없음 (미개봉이거나 Top10 밖)")

    # 실시간 예매 — 개봉 전 관객은 여기서만 보인다. 매 실행마다 한 점씩 쌓는다.
    booking = dict(old.get("booking") or {})
    try:
        for b in fetch_booking():
            pts = [p for p in (booking.get(b["nm"]) or []) if p["d"] != today.strftime("%Y-%m-%d")]
            pts.append({"d": today.strftime("%Y-%m-%d"), "rate": b["rate"],
                        "book": b["book"], "acc": b["acc"]})
            booking[b["nm"]] = pts[-180:]
            print(f"  [예매] {b['nm']} · 예매율 {b['rate']}% · 예매 {b['book']:,}명 · 누적 {b['acc']:,}명")
    except Exception as e:
        print(f"  예매율 수집 실패(본 수집은 계속): {type(e).__name__} {str(e)[:90]}")

    out = {"asOf": today.strftime("%Y-%m-%d"),
           "movies": movies, "booking": booking,
           # 자르면 잘린 날짜를 다음 실행이 또 훑어 백필이 끝나지 않는다.
           # 구간이 유한(WINDOWS)이라 무한정 커지지 않으므로 전부 남긴다.
           "scanned": sorted(scanned)}
    block = "const MOVIE = " + json.dumps(out, ensure_ascii=False) + ";\n"
    if m:
        html = html[:m.start()] + block + html[m.end():]
    else:
        anchor = re.search(r"^const TREND=", html, re.M)
        if not anchor:
            print("삽입 위치를 찾지 못했습니다(const TREND=)"); sys.exit(1)
        html = html[:anchor.start()] + block + html[anchor.start():]
    open(HTML_PATH, "w", encoding="utf-8").write(html)

    for nm, mv in movies.items():
        last = mv["days"][-1] if mv["days"] else None
        print(f"  {nm} · 개봉 {mv.get('openDt')} · {len(mv['days'])}일 기록"
              + (f" · 누적 {last['acc']:,}명" if last else ""))
    print(f"\n[OK] {len(todo)}일 훑음 · {hit}건 추가 · 누적 스캔 {len(scanned)}일")


if __name__ == "__main__":
    main()
