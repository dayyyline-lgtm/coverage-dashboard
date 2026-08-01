# -*- coding: utf-8 -*-
"""개봉 전 스크린 배정 추적 (메가박스) -> index.html 의  const MOVIE_SCREENS = {...};

왜
  KOBIS 는 '지나간 날'의 스크린수만 준다. 개봉일에 몇 개 관이 잡혔는지는
  개봉 전엔 극장 체인 예매 스케줄에만 있다. 1편은 개봉일 스크린이 146 -> 1,065 로
  뛰며 흥행이 결정됐다 — 그 배정을 미리, 그리고 늘어나는 과정째로 보려는 것.

어떻게 (실측으로 확인한 규격 · 2026-08-02)
  메가박스 스케줄 API. 요청은 JSON 본문(POST)이다 — 폼 인코딩이면 404 가 난다.
    /on/oh/ohc/Brch/schedulePage.do
    1) masterType:"brch" + brchNo(강남 1372) 로 그날 전 영화 목록 -> rpstMovieNo 탐색
    2) masterType:"movie" + movieNo × 지역 8곳 -> 전국 지점·스크린·회차·좌석
  지역코드: 10 서울 · 30 경기 · 35 인천 · 45 대전/충청/세종 · 55 부산/대구/경상
           · 65 광주/전라 · 70 강원 · 80 제주
  전국 점유 ~20% 체인 하나지만 '배정이 늘고 있는가'의 방향은 전 체인이 같다.
  같은 상영일을 매일 다시 재면 배정 확대 과정 자체가 시계열이 된다.

  python fetch_screens.py            # 수집·기록
  python fetch_screens.py --dry-run  # 출력만
"""
import json, re, sys, time, datetime, urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
KEEP = 90                      # 스냅샷 보존(작품·상영일별)
WATCH = ["하츄핑", "티니핑"]    # fetch_movie 의 WATCH 와 같은 규칙
URL = "https://www.megabox.co.kr/on/oh/ohc/Brch/schedulePage.do"
AREAS = [("10", "서울"), ("30", "경기"), ("35", "인천"), ("45", "대전충청"),
         ("55", "부산경상"), ("65", "광주전라"), ("70", "강원"), ("80", "제주")]
DISCOVER_BRCH = "1372"         # 강남점 — 전 영화가 걸리는 대형점이라 목록 탐색용


def post(body, tries=3):
    req = urllib.request.Request(URL, data=json.dumps(body).encode("utf-8"), headers={
        "User-Agent": "Mozilla/5.0", "Content-Type": "application/json; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.megabox.co.kr/booking/timetable"})
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            time.sleep(2 * (i + 1))
    raise last


def rows_of(d):
    return ((d.get("megaMap") or {}).get("movieFormList")) or []


def discover(crt, play):
    """그 상영일에 걸린 대상 영화들의 (rpstMovieNo, 이름)."""
    d = post({"masterType": "brch", "brchNo": DISCOVER_BRCH, "firstAt": "N",
              "brchNo1": DISCOVER_BRCH, "crtDe": crt, "playDe": play})
    out = {}
    for x in rows_of(d):
        nm = (x.get("rpstMovieNm") or x.get("movieNm") or "").strip()
        if any(w in nm for w in WATCH) and x.get("rpstMovieNo"):
            out[x["rpstMovieNo"]] = nm
    return out


def nationwide(movie_no, crt, play):
    """지역 8곳 합산 — 지점·스크린·회차·좌석(총/판매)."""
    sites, screens, shows, seat_tot, seat_rest = set(), set(), 0, 0, 0
    for cd, _ in AREAS:
        d = post({"masterType": "movie", "movieNo": movie_no, "firstAt": "N",
                  "movieNo1": movie_no, "areaCd": int(cd), "crtDe": crt, "playDe": play})
        for x in rows_of(d):
            sites.add(x.get("brchNo"))
            screens.add((x.get("brchNo"), x.get("theabNo")))
            shows += 1
            try:
                seat_tot += int(x.get("totSeatCnt") or 0)
                seat_rest += int(x.get("restSeatCnt") or 0)
            except (TypeError, ValueError):
                pass
        time.sleep(0.3)
    return {"sites": len(sites), "screens": len(screens), "shows": shows,
            "seatTot": seat_tot, "seatSold": max(0, seat_tot - seat_rest)}


def main():
    html = open(HTML, encoding="utf-8").read()
    now = datetime.datetime.now(KST)
    today = now.date()
    crt = today.strftime("%Y%m%d")

    # 잴 상영일: 오늘·내일 + booking 에 적힌 개봉일(개봉 전 핵심)
    dates = {today, today + datetime.timedelta(days=1)}
    mb = re.search(r"const MOVIE = (\{.*?\});\n", html, re.S)
    if mb:
        try:
            for pts in (json.loads(mb.group(1)).get("booking") or {}).values():
                for p in pts[-1:]:
                    if p.get("open"):
                        try:
                            dates.add(datetime.date.fromisoformat(p["open"]))
                        except ValueError:
                            pass
        except json.JSONDecodeError:
            pass
    dates = sorted(d for d in dates if d >= today)[:3]

    m = re.search(r"const MOVIE_SCREENS = (\{.*?\});", html, re.S)
    old = {}
    if m:
        try:
            old = json.loads(m.group(1))
        except json.JSONDecodeError:
            old = {}
    series = old.get("series") or {}

    stamp = now.strftime("%Y-%m-%d %H:%M")
    got = 0
    for d in dates:
        play = d.strftime("%Y%m%d")
        try:
            movies = discover(crt, play)
        except Exception as e:
            print(f"  {play} 목록 실패: {type(e).__name__} {str(e)[:70]}")
            continue
        if not movies:
            print(f"  {play} 대상 영화 없음(강남점 기준)")
            continue
        for no, nm in movies.items():
            try:
                v = nationwide(no, crt, play)
            except Exception as e:
                print(f"  {play} {nm} 전국 실패: {str(e)[:70]}")
                continue
            key = f"{nm}|{play}"
            pts = [p for p in (series.get(key) or []) if p.get("t") != stamp]
            pts.append({"t": stamp, **v})
            series[key] = pts[-KEEP:]
            got += 1
            print(f"  [{play}] {nm} · 지점 {v['sites']} · 스크린 {v['screens']} · "
                  f"회차 {v['shows']} · 판매 {v['seatSold']:,}/{v['seatTot']:,}석")

    if not got:
        print("배정 스케줄 없음 — 기존 데이터 유지")
        return

    out = {"asOf": stamp, "chain": "메가박스", "series": series}
    block = "const MOVIE_SCREENS = " + json.dumps(out, ensure_ascii=False) + ";"
    if "--dry-run" in sys.argv:
        print(json.dumps(out, ensure_ascii=False)[:400]); return
    if m:
        html = html[:m.start()] + block + html[m.end():]
    else:
        anchor = re.search(r"const MOVIE = \{", html)
        if not anchor:
            print("삽입 위치(const MOVIE)를 못 찾음"); sys.exit(1)
        html = html[:anchor.start()] + block + "\n" + html[anchor.start():]
    open(HTML, "w", encoding="utf-8").write(html)
    print(f"[OK] MOVIE_SCREENS 갱신 · {got}건 (메가박스 기준 프록시)")


if __name__ == "__main__":
    main()
