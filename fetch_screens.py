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

# 차단 대응(브라우저 헤더·흔들린 간격·health.json 기록)은 collector_health 로 합쳤다.
# 예전엔 이 파일에만 사본이 있어서 정작 요청이 제일 많은 네이버 금융은 무방비였다.
from collector_health import ua as _ua, nap as _nap, note_health, looks_blocked

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
KEEP = 90
WATCH = ["하츄핑", "티니핑"]
# 비교군 — 같은 시기 흥행작만. '예매율 12% 가 낮은 건가'를 가르는 기준선이다.
# 전 영화를 담으면 소규모 재개봉·예술영화까지 섞여 오히려 안 읽힌다.
PEER_TITLES = ["스파이더맨", "오디세이", "호프"]
UA = _ua()["User-Agent"]


def peer_key(nm):
    """비교군 이름을 대표 제목으로 접는다.

    체인들이 상영 포맷을 별개 영화처럼 준다 — '오디세이(IMAX 2D)', '(S)스파이더맨…',
    '호프(무대인사)'. 그대로 두면 비교군이 24개로 불어나고 한 영화의 좌석이
    여러 줄로 쪼개져 총량이 안 맞는다. 키워드로 묶어 3편으로 되돌린다.
    """
    for p in PEER_TITLES:
        if p in (nm or ""):
            return p
    return None


def is_peer(nm):
    return peer_key(nm) is not None


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


def megabox(play, crt, peer_names=()):
    """(대상, 비교군). 메가는 영화별 x 지역8 이라 비교군은 요청한 제목만 훑는다."""
    rows = (mb_post({"masterType": "brch", "brchNo": "1372", "firstAt": "N",
                     "brchNo1": "1372", "crtDe": crt, "playDe": play})
            .get("megaMap", {}).get("movieFormList")) or []
    allm = {x["rpstMovieNo"]: (x.get("rpstMovieNm") or "").strip()
            for x in rows if x.get("rpstMovieNo")}
    targets = {no: nm for no, nm in allm.items() if any(w in nm for w in WATCH)}
    want_peer = {norm_title(p) for p in peer_names}
    peers_sel = {no: nm for no, nm in allm.items()
                 if no not in targets and norm_title(nm) in want_peer}

    def sweep(no):
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
            _nap(0.25)
        return acc_fin(a)

    out = {nm: sweep(no) for no, nm in targets.items()}
    peers = {}
    for no, nm in peers_sel.items():
        k = peer_key(nm) or nm
        v = sweep(no)
        if k in peers:            # 같은 영화의 다른 포맷 — 합친다
            for f in ("sites", "screens", "shows", "seatTot", "seatSold"):
                peers[k][f] += v[f]
        else:
            peers[k] = v
    return out, peers


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
    """(대상, 비교군).

    representationMovieCode 를 '비워서' 부르면 그 영화관의 전 영화가 한 번에 온다.
    (건대입구 8/5: 53회차 6편) 예전엔 영화별로 237개관을 따로 돌아서 요청이 2배였다 —
    비우면 절반으로 줄면서 비교군까지 공짜로 딸려온다. IP 부담도 그만큼 준다.
    """
    base = {"channelType": "HO", "osType": "W", "osVersion": UA, "memberOnNo": ""}
    d = lc_call({"MethodName": "GetTicketingPage", **base})
    cins = ((d.get("Cinemas") or {}).get("Cinemas") or {}).get("Items") or []
    out, peers = {}, {}
    for c in cins:
        cid = f"{c['DivisionCode']}|{c['DetailDivisionCode']}|{c['CinemaID']}"
        try:
            s = lc_call({"MethodName": "GetPlaySequence", **base,
                         "playDate": play_iso, "cinemaID": cid,
                         "representationMovieCode": ""})
        except Exception:
            _nap(0.12)
            continue
        for x in ((s.get("PlaySeqs") or {}).get("Items")) or []:
            nm = (x.get("MovieNameKR") or "").strip()
            if not nm:
                continue
            t = int(x.get("TotalSeatCount") or 0)
            r = int(x.get("BookingSeatCount") or 0)   # 이름과 달리 '잔여'다(실측 199/208)
            tgt = any(w in nm for w in WATCH)
            for bucket, key in ((out, nm) if tgt else (None, None), (peers, peer_key(nm)) if is_peer(nm) else (None, None)):
                if bucket is None:
                    continue
                a = bucket.setdefault(key, acc_new())
                a["sites"].add(cid)
                a["screens"].add((cid, x.get("ScreenNameKR")))
                a["shows"] += 1
                a["seatTot"] += t
                a["seatSold"] += max(0, t - r)
        _nap(0.12)
    return ({k: acc_fin(v) for k, v in out.items()},
            {k: acc_fin(v) for k, v in peers.items()})


# ── CGV ─────────────────────────────────────────────────
CGV = "https://cgv.co.kr"


def cgv(play):
    lst = http_json(f"{CGV}/api/v1/booking/searchAtktTopPostrList?coCd=A420&movNm=&div=&attrCd=")
    targets = {x["movNo"]: x["movNm"] for x in (lst.get("data") or [])
               if any(w in (x.get("movNm") or "") for w in WATCH)}
    out, peers = {}, {}          # peers = 같은 지점·같은 날의 다른 영화들(비교군)
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
                t = int(x.get("stcnt") or 0)
                r = int(x.get("frSeatCnt") or 0)
                pn = (x.get("prodNm") or "").strip()
                # 같은 요청이 그 지점의 '전 영화'를 준다. 우리 영화만 걸러 버리면
                # 비교군(스파이더맨·오디세이…)을 공짜로 얻을 수 있는 걸 버리는 셈이다.
                # 예매율이 원래 저조한 건지 이 영화만 저조한 건지는 옆 영화를 봐야 안다.
                pk = peer_key(pn)
                if pk:
                    b = peers.setdefault(pk, acc_new())
                    b["sites"].add(sn); b["screens"].add((sn, x.get("scnsNo")))
                    b["shows"] += 1; b["seatTot"] += t; b["seatSold"] += max(0, t - r)
                if not any(w in pn for w in WATCH):
                    continue
                a["sites"].add(sn)
                a["screens"].add((sn, x.get("scnsNo")))
                a["shows"] += 1
                a["seatTot"] += t
                a["seatSold"] += max(0, t - r)
            _nap(0.15)
        out[nm] = acc_fin(a)
    return out, {k: acc_fin(v) for k, v in peers.items()}


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
        _nap(0.12)
    return None          # None = CGV 기준 미편성(다른 체인 단독 편성은 드물다)


# ── 통합 ────────────────────────────────────────────────
def norm_title(nm):
    """체인마다 표기가 다르다(CGV '하츄핑-고래보석', 메가 '하츄핑: 고래보석').
       구분자만 다른 같은 제목을 한 키로 합친다."""
    return re.sub(r"[\s:\-·]+", "", nm)


def _parse_stamp(s):
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=KST)
    except Exception:
        return None


def main():
    html = open(HTML, encoding="utf-8").read()
    now = datetime.datetime.now(KST)
    today = now.date()
    crt = today.strftime("%Y%m%d")
    hot_only = "--hot" in sys.argv

    # 예매 지평선 끝까지 본다. 개봉일에서 끊으면 안 되고(8/5 개봉인데 8/6·8/7 예매가
    # 이미 열려 있다), 고정 7일로 끊어도 안 된다 — CGV 는 8/18 까지 달력을 열어 둔다.
    # 다만 편성은 그보다 앞서 끝나므로(오늘 기준 8/10 이 마지막), 값싼 탐침으로
    # '이 날짜에 이 영화가 걸렸는가'만 먼저 보고 걸린 날만 전수 조사한다.
    dates = {today + datetime.timedelta(days=i) for i in range(15)}
    mb_blk = re.search(r"const MOVIE = (\{.*?\});\n", html, re.S)
    canon = {}                       # 정규화 제목 -> 대시보드 표기(예매 데이터 기준)
    opens = []                       # 추적 대상들의 개봉일
    if mb_blk:
        try:
            mv = json.loads(mb_blk.group(1))
            for t, pts in (mv.get("booking") or {}).items():
                canon[norm_title(t)] = t
                for p in pts[-1:]:
                    if p.get("open"):
                        try:
                            od = datetime.date.fromisoformat(p["open"])
                            dates.add(od); opens.append(od)
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

    # 주기 — 개봉 후 한 달은 매시간, 그 뒤로는 4시간마다.
    # 워크플로가 여러 개(refresh·screens)라 같은 시간에 겹쳐 뜰 수 있으므로
    # '직전 수집이 얼마나 됐나'로 스스로 걸러 낸다. --force 면 무시.
    newest_open = max(opens) if opens else None
    aged = newest_open is not None and (today - newest_open).days > 30
    min_gap = datetime.timedelta(hours=3, minutes=30) if aged else datetime.timedelta(minutes=45)
    prev = _parse_stamp(old.get("asOf") or "")
    if prev and now - prev < min_gap and "--force" not in sys.argv:
        print(f"[skip] 직전 수집 {old.get('asOf')} · {int((now-prev).total_seconds()//60)}분 전 "
              f"(주기 {int(min_gap.total_seconds()//60)}분{' · 개봉 30일 경과' if aged else ''})")
        return

    # 전수 조사는 하루 한 번이면 충분하다 — 배정(좌석)은 천천히 바뀐다.
    # 시간마다 필요한 건 '예매가 얼마나 찼나'뿐이라, 가까운 날짜만 다시 잰다.
    last_full = old.get("lastFull")
    want_full = (not hot_only) or (last_full != today.isoformat())
    if not want_full:
        known = sorted({k.split("|")[1] for k in series})
        keep = set([p for p in known if p >= crt][:3])
        if newest_open and newest_open >= today:
            keep.add(newest_open.strftime("%Y%m%d"))
        dates = [d for d in dates if d.strftime("%Y%m%d") in keep]
        print(f"[hot] 가까운 날짜만 갱신: {', '.join(sorted(keep))}")

    stamp = now.strftime("%Y-%m-%d %H:%M")
    got = 0
    horizon = None                     # 편성이 확인된 마지막 날짜
    # 비교군은 CGV 만 쓴다 — 롯데·메가는 영화별 루프라 편당 수백 요청이 더 든다.
    # 어차피 '같은 체인·같은 지점·같은 날' 끼리 견주는 게 비교로도 더 깨끗하다.
    # 예전 수집의 잔재(전 영화 담던 시절)를 걷어낸다
    peer_series = {k: v for k, v in (old.get("peers") or {}).items() if k in PEER_TITLES}
    for d in dates:
        play, play_iso = d.strftime("%Y%m%d"), d.isoformat()
        if not programmed(play):
            print(f"  {play} 미편성 — 전수 조사 생략")
            continue
        horizon = play
        # 체인별 독립 실행 — 하나가 막혀도 나머지는 간다
        chains, peer_by = {}, {}
        # 매시간 도는 hot 은 CGV 만 본다. 롯데는 237개관, 메가는 지역8 순회라
        # 시간마다 돌리면 Actions 분과 상대 서버 부담이 같이 커진다.
        # CGV 는 지점 요청 하나가 전 영화를 주므로 비교군까지 한 번에 온다 —
        # 시간 단위로 알고 싶은 '예매가 얼마나 찼나'는 이걸로 충분하다.
        # 3사 전수와 비교군 합산은 하루 한 번 전수 조사 때 맞춘다.
        for tag in (("CGV",) if not want_full else ("CGV", "LC", "MB")):
            try:
                if tag == "CGV":
                    o, p = cgv(play)
                elif tag == "LC":
                    o, p = lotte(play_iso)
                else:
                    o, p = megabox(play, crt, PEER_TITLES)
                chains[tag] = o
                for pn, pv in p.items():
                    peer_by.setdefault(norm_title(pn), {"nm": pn, "by": {}})["by"][tag] = pv
                note_health(tag, None)                    # 성공 — 기록 해제
            except Exception as e:
                print(f"  {play} {tag} 실패: {type(e).__name__} {str(e)[:70]}")
                if looks_blocked(e):
                    note_health(tag, f"{type(e).__name__}: {e}")
        # 비교군도 3사 합산. 어느 체인이 빠졌는지 같이 남겨 화면에서 구분한다.
        for pk, pv in peer_by.items():
            prev = (peer_series.get(pv["nm"]) or {}).get(play) or {}
            for t2, v2 in (prev.get("by") or {}).items():
                pv["by"].setdefault(t2, v2)          # 대상과 같은 이유로 이어받는다
            tot = {f: sum(v[f] for v in pv["by"].values())
                   for f in ("sites", "screens", "shows", "seatTot", "seatSold")}
            if tot["seatTot"] <= 0:
                continue
            peer_series.setdefault(pv["nm"], {})[play] = {
                **tot, "t": stamp, "by": pv["by"]}
        # 제목 정규화로 3사 결과를 합친다
        merged = {}
        for tag, per in chains.items():
            for nm, v in per.items():
                k = norm_title(nm)
                merged.setdefault(k, {"nm": canon.get(k, nm), "by": {}})["by"][tag] = v
        for k, mv2 in merged.items():
            key = f"{mv2['nm']}|{play}"
            # hot 은 CGV 만 새로 재므로, 안 잰 체인은 직전 스냅샷 값을 이어받는다.
            # 안 그러면 3사 합산이던 숫자가 갑자기 CGV 몫으로 뚝 떨어져
            # '배정이 반토막 났다'는 가짜 신호가 된다.
            prev_pts = series.get(key) or []
            if prev_pts:
                for t2, v2 in (prev_pts[-1].get("by") or {}).items():
                    mv2["by"].setdefault(t2, v2)
            tot = {f: sum(v[f] for v in mv2["by"].values())
                   for f in ("sites", "screens", "shows", "seatTot", "seatSold")}
            pts = [p for p in prev_pts if p.get("t") != stamp]
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
    #
    # ⚠ hot 회차의 horizon 은 쓰지 않는다.
    #   horizon 은 '이번에 조사한 날짜 중 마지막'이라, 가까운 3일+개봉일만 보는 hot 이
    #   덮어쓰면 지평선이 그 앞으로 쪼그라든다(실측: 전수 직후 20260817 -> hot 뒤 20260805).
    #   화면은 play > horizon 이면 '편성 중' 표시를 빼므로, 그렇게 되면 뒤쪽 날짜 전부가
    #   '편성 중'이 아니게 되어 스크린 감소가 축소로 읽힌다 — 이 값이 막으려던 바로 그 오독이다.
    #   지평선은 전 날짜를 훑는 전수 회차만 알 수 있다.
    out = {"asOf": stamp, "chain": "CGV+롯데+메가박스",
           "horizon": (horizon if want_full else None) or old.get("horizon"),
           "lastFull": today.isoformat() if want_full else last_full,
           "series": series, "peers": peer_series}
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
