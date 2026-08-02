# -*- coding: utf-8 -*-
"""개봉 전 스크린 배정 추적 (CGV+롯데+메가박스 3사) -> const MOVIE_SCREENS = {...};

왜
  KOBIS 는 '지나간 날'의 스크린수만 준다. 개봉일에 몇 개 관이 잡혔는지는
  개봉 전엔 극장 체인 예매 스케줄에만 있다. 1편은 개봉일 스크린이 146 -> 1,065 로
  뛰며 흥행이 결정됐다 — 그 배정을 미리, 늘어나는 과정째로 본다.

3사 규격 (2026-08-02 브라우저에서 실측·캡처로 확정 · 전부 로그인 불필요)
  메가박스  POST /on/oh/ohc/Brch/schedulePage.do — 본문이 JSON(폼이면 404).
            brch(강남점)로 영화번호 탐색 -> movie × 지역 8곳.
  롯데      POST /LCWS/Ticketing/TicketingData.aspx — multipart 의 paramList 필드.
            GetTicketingPage 로 영화코드·영화관 237곳 -> GetPlaySequence × 영화관.
  CGV       GET /api/v1/booking/... (리뉴얼 후 신 API · 구 iframeTheater 는 404)
            searchAtktTopPostrList 로 movNo -> searchRegnList 로 '상영하는' 사이트만
            -> searchMovScnInfo?siteNo&scnYmd 로 관·회차·좌석(stcnt·frSeatCnt).

  요청량: CGV ~사이트수 + 롯데 237 + 메가 8지역 = 하루 한 번 몇 분. 간격을 둔다.
  어느 체인이 막혀도(해외 러너 차단 등) 나머지는 계속 — 체인별 독립 실패.

수집하는 값은 딱 두 개다 (2026-08-02 실측 검증)
  회차마다 '총좌석'과 '잔여좌석'만 받아서  판매 = 총 - 잔여  로 만든다.
  어느 API 도 '팔린 좌석'을 직접 주지 않는다. 나머지(판매율·예상관객·누적)는 전부 파생값.

  검증 1 — 유령 판매분(차단석)이 섞이나?
    CGV 8/10(일주일 뒤, 사실상 미판매) 25개 지점 28회차의 (총-잔여) 분포:
      0석 16회 · 1석 2 · 2석 5 · 3석 1 · 4석 3 · 8석 1
    0 이 최빈값 = 시스템적으로 빠지는 좌석이 없다. 짝수 편중은 가족영화라 2매씩 사는 것.
    (강변 008 관만 전 회차가 2 였는데 그건 우연이고, 넓히니 0 이 대부분이었다.)
  검증 2 — 롯데 BookingSeatCount 는 '예약'인가 '잔여'인가?
    8/5 101회차 중 33회차, 8/9 44회차 중 11회차가 BookingSeatCount == TotalSeatCount.
    '예약'이면 회차 3분의 1이 일주일 전에 매진이라는 뜻이라 말이 안 된다 -> 잔여가 맞다.
  검증 3 — 총량이 다른 출처와 맞나?
    3사 예매석 합 47,557 vs KOBIS 전국 예매관객 53,443 = 89.0%. 3사 점유율과 일치.

  한계: 온라인 예매만 잡힌다. 현장 구매는 안 잡히므로 '전국 보정'(natF)이
        KOBIS 실측 관객 ÷ 3사 예매석 으로 그 몫과 독립관을 함께 흡수한다.

  python fetch_screens.py            # 수집·기록
  python fetch_screens.py --dry-run  # 출력만
"""
import json, os, re, sys, time, uuid, datetime, urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
KEEP = 90
WATCH = ["하츄핑", "티니핑"]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def http_json(url, data=None, headers=None, timeout=40, tries=2):
    h = {"User-Agent": UA, "Accept": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def acc_new():
    return {"sites": set(), "screens": set(), "shows": 0, "seatTot": 0, "seatSold": 0}


def acc_fin(a):
    return {"sites": len(a["sites"]), "screens": len(a["screens"]), "shows": a["shows"],
            "seatTot": a["seatTot"], "seatSold": a["seatSold"]}


# ── 메가박스 ─────────────────────────────────────────────
MB_URL = "https://www.megabox.co.kr/on/oh/ohc/Brch/schedulePage.do"
MB_AREAS = ["10", "30", "35", "45", "55", "65", "70", "80"]


def mb_post(body):
    return http_json(MB_URL, data=json.dumps(body).encode(), headers={
        "Content-Type": "application/json; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.megabox.co.kr/booking/timetable"})


def megabox(play, crt):
    rows = (mb_post({"masterType": "brch", "brchNo": "1372", "firstAt": "N",
                     "brchNo1": "1372", "crtDe": crt, "playDe": play})
            .get("megaMap", {}).get("movieFormList")) or []
    targets = {x["rpstMovieNo"]: x.get("rpstMovieNm", "")
               for x in rows if any(w in (x.get("rpstMovieNm") or "") for w in WATCH)
               and x.get("rpstMovieNo")}
    out = {}
    for no, nm in targets.items():
        a = acc_new()
        for cd in MB_AREAS:
            d = mb_post({"masterType": "movie", "movieNo": no, "firstAt": "N",
                         "movieNo1": no, "areaCd": int(cd), "crtDe": crt, "playDe": play})
            for x in (d.get("megaMap", {}).get("movieFormList")) or []:
                a["sites"].add(x.get("brchNo"))
                a["screens"].add((x.get("brchNo"), x.get("theabNo")))
                a["shows"] += 1
                t, r = int(x.get("totSeatCnt") or 0), int(x.get("restSeatCnt") or 0)
                a["seatTot"] += t
                a["seatSold"] += max(0, t - r)
            time.sleep(0.25)
        out[nm] = acc_fin(a)
    return out


# ── 롯데시네마 ───────────────────────────────────────────
LC_URL = "https://www.lottecinema.co.kr/LCWS/Ticketing/TicketingData.aspx"


def lc_call(param):
    # multipart/form-data 의 paramList 한 필드 — 사이트가 이 형식만 받는다
    bnd = uuid.uuid4().hex
    body = (f"--{bnd}\r\nContent-Disposition: form-data; name=\"paramList\"\r\n\r\n"
            f"{json.dumps(param, ensure_ascii=False)}\r\n--{bnd}--\r\n").encode("utf-8")
    return http_json(LC_URL, data=body, headers={
        "Content-Type": f"multipart/form-data; boundary={bnd}",
        "Referer": "https://www.lottecinema.co.kr/NLCHS/Ticketing"})


def lotte(play_iso):
    base = {"channelType": "HO", "osType": "W", "osVersion": UA, "memberOnNo": ""}
    d = lc_call({"MethodName": "GetTicketingPage", **base})
    movies = ((d.get("Movies") or {}).get("Movies") or {}).get("Items") or []
    cins = ((d.get("Cinemas") or {}).get("Cinemas") or {}).get("Items") or []
    targets = {m["RepresentationMovieCode"]: m["MovieNameKR"]
               for m in movies if any(w in (m.get("MovieNameKR") or "") for w in WATCH)}
    out = {}
    for code, nm in targets.items():
        a = acc_new()
        for c in cins:
            cid = f"{c['DivisionCode']}|{c['DetailDivisionCode']}|{c['CinemaID']}"
            try:
                s = lc_call({"MethodName": "GetPlaySequence", **base,
                             "playDate": play_iso, "cinemaID": cid,
                             "representationMovieCode": code})
            except Exception:
                continue
            items = ((s.get("PlaySeqs") or {}).get("Items")) or []
            if not items:
                time.sleep(0.08)
                continue
            for x in items:
                a["sites"].add(cid)
                a["screens"].add((cid, x.get("ScreenNameKR")))
                a["shows"] += 1
                t = int(x.get("TotalSeatCount") or 0)
                r = int(x.get("BookingSeatCount") or 0)   # 이름과 달리 '잔여'다(실측 199/208)
                a["seatTot"] += t
                a["seatSold"] += max(0, t - r)
            time.sleep(0.08)
        out[nm] = acc_fin(a)
    return out


# ── CGV ─────────────────────────────────────────────────
CGV = "https://cgv.co.kr"


def cgv(play):
    lst = http_json(f"{CGV}/api/v1/booking/searchAtktTopPostrList?coCd=A420&movNm=&div=&attrCd=")
    targets = {x["movNo"]: x["movNm"] for x in (lst.get("data") or [])
               if any(w in (x.get("movNm") or "") for w in WATCH)}
    out = {}
    for no, nm in targets.items():
        reg = http_json(f"{CGV}/api/v1/booking/searchRegnList?movNo={no}&coCd=A420")
        sites = {s["siteNo"] for g in (reg.get("data") or [])
                 for s in (g.get("siteList") or []) if s.get("siteNo")}
        a = acc_new()
        for sn in sorted(sites):
            try:
                d = http_json(f"{CGV}/api/v1/booking/searchMovScnInfo"
                              f"?coCd=A420&siteNo={sn}&scnYmd={play}&rtctlScopCd=08")
            except Exception:
                continue
            rows = []
            def scan(o):
                if isinstance(o, list):
                    for v in o: scan(v)
                elif isinstance(o, dict):
                    if o.get("prodNm") and o.get("scnsNo"):
                        rows.append(o)
                    for v in o.values():
                        if isinstance(v, (list, dict)): scan(v)
            scan(d.get("data"))
            for x in rows:
                if not any(w in (x.get("prodNm") or "") for w in WATCH):
                    continue
                a["sites"].add(sn)
                a["screens"].add((sn, x.get("scnsNo")))
                a["shows"] += 1
                t = int(x.get("stcnt") or 0)
                r = int(x.get("frSeatCnt") or 0)
                a["seatTot"] += t
                a["seatSold"] += max(0, t - r)
            time.sleep(0.12)
        out[nm] = acc_fin(a)
    return out


# ── 편성 탐침 ────────────────────────────────────────────
# 날짜 하나를 전수 조사하면 CGV 147 + 롯데 237 = 384 요청이 든다.
# 그런데 편성이 안 된 날은 그게 통째로 헛수고다(오늘 기준 8/12 이후가 그렇다).
# 대형 멀티플렉스 몇 곳만 먼저 찔러 본다 — 와이드 릴리즈가 편성됐다면
# 강변·용산·영등포·왕십리 중 하나에는 반드시 걸린다.
PROBE_SITES = ["0001", "0013", "0059", "0074"]


def programmed(play):
    """그 상영일에 대상 영화가 편성됐는가 (값싼 확인)."""
    for sn in PROBE_SITES:
        try:
            d = http_json(f"{CGV}/api/v1/booking/searchMovScnInfo"
                          f"?coCd=A420&siteNo={sn}&scnYmd={play}&rtctlScopCd=08", tries=1)
        except Exception:
            continue
        hit = []
        def scan(o):
            if isinstance(o, list):
                for v in o: scan(v)
            elif isinstance(o, dict):
                if any(w in (o.get("prodNm") or "") for w in WATCH):
                    hit.append(1)
                for v in o.values():
                    if isinstance(v, (list, dict)): scan(v)
        scan(d.get("data"))
        if hit:
            return True
        time.sleep(0.1)
    return None          # None = CGV 기준 미편성(다른 체인 단독 편성은 드물다)


# ── 통합 ────────────────────────────────────────────────
def norm_title(nm):
    """체인마다 표기가 다르다(CGV '하츄핑-고래보석', 메가 '하츄핑: 고래보석').
       구분자만 다른 같은 제목을 한 키로 합친다."""
    return re.sub(r"[\s:\-·]+", "", nm)


def main():
    html = open(HTML, encoding="utf-8").read()
    now = datetime.datetime.now(KST)
    today = now.date()
    crt = today.strftime("%Y%m%d")

    # 예매 지평선 끝까지 본다. 개봉일에서 끊으면 안 되고(8/5 개봉인데 8/6·8/7 예매가
    # 이미 열려 있다), 고정 7일로 끊어도 안 된다 — CGV 는 8/18 까지 달력을 열어 둔다.
    # 다만 편성은 그보다 앞서 끝나므로(오늘 기준 8/10 이 마지막), 값싼 탐침으로
    # '이 날짜에 이 영화가 걸렸는가'만 먼저 보고 걸린 날만 전수 조사한다.
    dates = {today + datetime.timedelta(days=i) for i in range(15)}
    mb_blk = re.search(r"const MOVIE = (\{.*?\});\n", html, re.S)
    canon = {}                       # 정규화 제목 -> 대시보드 표기(예매 데이터 기준)
    if mb_blk:
        try:
            mv = json.loads(mb_blk.group(1))
            for t, pts in (mv.get("booking") or {}).items():
                canon[norm_title(t)] = t
                for p in pts[-1:]:
                    if p.get("open"):
                        try:
                            dates.add(datetime.date.fromisoformat(p["open"]))
                        except ValueError:
                            pass
        except json.JSONDecodeError:
            pass
    dates = sorted(d for d in dates if d >= today)[:16]

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
    horizon = None                     # 편성이 확인된 마지막 날짜
    for d in dates:
        play, play_iso = d.strftime("%Y%m%d"), d.isoformat()
        if not programmed(play):
            print(f"  {play} 미편성 — 전수 조사 생략")
            continue
        horizon = play
        # 체인별 독립 실행 — 하나가 막혀도 나머지는 간다
        chains = {}
        for tag, fn, arg in (("CGV", cgv, play), ("LC", lotte, play_iso), ("MB", megabox, None)):
            try:
                chains[tag] = fn(arg) if arg else megabox(play, crt)
            except Exception as e:
                print(f"  {play} {tag} 실패: {type(e).__name__} {str(e)[:70]}")
        # 제목 정규화로 3사 결과를 합친다
        merged = {}
        for tag, per in chains.items():
            for nm, v in per.items():
                k = norm_title(nm)
                merged.setdefault(k, {"nm": canon.get(k, nm), "by": {}})["by"][tag] = v
        for k, mv2 in merged.items():
            tot = {f: sum(v[f] for v in mv2["by"].values())
                   for f in ("sites", "screens", "shows", "seatTot", "seatSold")}
            key = f"{mv2['nm']}|{play}"
            pts = [p for p in (series.get(key) or []) if p.get("t") != stamp]
            pts.append({"t": stamp, **tot, "by": mv2["by"]})
            series[key] = pts[-KEEP:]
            # 영구 아카이브 — index.html 의 시계열은 KEEP 개로 잘리지만
            # 여기는 append 만 한다. 다음 극장판 때 이번 배정 이력이 기준선이 된다.
            os.makedirs("archive", exist_ok=True)
            with open("archive/screens.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": stamp, "title": mv2["nm"], "play": play,
                                    **tot, "by": mv2["by"]}, ensure_ascii=False) + "\n")
            got += 1
            bych = " · ".join(f"{t} {v['screens']}관" for t, v in mv2["by"].items())
            print(f"  [{play}] {mv2['nm']} · 지점 {tot['sites']} · 스크린 {tot['screens']} · "
                  f"회차 {tot['shows']} · 판매 {tot['seatSold']:,}/{tot['seatTot']:,}석  ({bych})")

    if not got:
        print("배정 스케줄 없음 — 기존 데이터 유지")
        return

    # horizon = 편성이 확인된 마지막 상영일. 이 근처 날짜는 스케줄이 아직 채워지는 중이라
    # 좌석·스크린이 실제보다 적게 잡힌다 — 화면에서 '축소'로 오독하지 않게 같이 넘긴다.
    out = {"asOf": stamp, "chain": "CGV+롯데+메가박스",
           "horizon": horizon or (old.get("horizon")), "series": series}
    block = "const MOVIE_SCREENS = " + json.dumps(out, ensure_ascii=False) + ";"
    if "--dry-run" in sys.argv:
        print(json.dumps(out, ensure_ascii=False)[:400]); return
    # 수집에 십수 분이 걸린다. 시작 시점에 읽어 둔 html 로 덮어쓰면 그 사이의
    # 다른 편집(화면 코드 수정 등)이 통째로 날아간다 — 실제로 한 번 날렸다.
    # 쓰기 직전에 파일을 다시 읽고, MOVIE_SCREENS 블록만 갈아 끼운다.
    html = open(HTML, encoding="utf-8").read()
    m = re.search(r"const MOVIE_SCREENS = \{.*?\};", html, re.S)
    if m:
        html = html[:m.start()] + block + html[m.end():]
    else:
        anchor = re.search(r"const MOVIE = \{", html)
        if not anchor:
            print("삽입 위치(const MOVIE)를 못 찾음"); sys.exit(1)
        html = html[:anchor.start()] + block + "\n" + html[anchor.start():]
    open(HTML, "w", encoding="utf-8").write(html)
    print(f"[OK] MOVIE_SCREENS 갱신 · {got}건 (3사 합산)")


if __name__ == "__main__":
    main()
