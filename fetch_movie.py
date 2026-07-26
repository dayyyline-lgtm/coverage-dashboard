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
MAX_BACKFILL = 60      # 한 번에 훑을 최대 날짜 수
LOOKBACK_DAYS = 400    # 처음 시작할 때 거슬러 올라갈 한도


def getj(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8"))


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
    dates = [(today - datetime.timedelta(days=i)).strftime("%Y%m%d")
             for i in range(1, LOOKBACK_DAYS + 1)]
    todo = [d for d in dates if d not in scanned][:MAX_BACKFILL]
    if not todo:
        print("새로 훑을 날짜 없음"); return

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

    out = {"asOf": today.strftime("%Y-%m-%d"),
           "movies": movies,
           "scanned": sorted(scanned)[-500:]}     # 날짜 목록이 무한정 커지지 않게
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
