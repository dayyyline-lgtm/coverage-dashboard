# -*- coding: utf-8 -*-
"""
시세 · 멀티플 · 증권사 리포트 · 지수 · 환율 갱신 스크립트
---------------------------------------------------------
index.html 안의  const LIVE = {...};  블록을 최신 데이터로 교체합니다.

사용법:
    python refresh_live.py

수집처 (전부 무료 · 키 불필요):
  - 네이버 금융 모바일 API : 현재가/등락률/시총/PER/PBR/EPS/배당수익률/52주/외국인/컨센목표가/리포트
  - open.er-api.com        : USD/JPY/CNY 대비 원화 환율

장중에 돌리면 실시간 시세, 장 마감 후엔 종가 기준입니다.
"""
import urllib.request, urllib.parse, json, time, re, datetime, sys

# Windows 콘솔(cp949)에서 한글/기호가 깨지지 않도록
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML_PATH = "public/index.html"
UA = {"User-Agent": "Mozilla/5.0"}

# 종목명 → 종목코드 (엑셀 표기와 다른 경우 여기서 교정)
NAME_FIX = {"앨엔씨바이오": "엘앤씨바이오", "와이지엔터": "와이지엔터테인먼트"}


def getj(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8"))


def num(s):
    if s is None:
        return None
    s = str(s).replace(",", "").replace("%", "").replace("배", "").replace("원", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def mktcap_eok(s):
    """'13조 6,836억' -> 억원 단위 숫자"""
    if not s:
        return None
    s = str(s).replace(",", "")
    jo = re.search(r"([\d.]+)조", s)
    eok = re.search(r"([\d.]+)억", s)
    tot = 0.0
    if jo:
        tot += float(jo.group(1)) * 10000
    if eok:
        tot += float(eok.group(1))
    return tot or None


def fetch_returns(code):
    """일봉으로 1W / 1M / 3M / 6M / 1Y / YTD 수익률 계산 (엑셀 고정값 대신 실시간)"""
    today = datetime.date.today()
    start = today - datetime.timedelta(days=400)   # 1년 수익률을 위해 13개월치 확보
    url = (f"https://api.stock.naver.com/chart/domestic/item/{code}/day"
           f"?startDateTime={start:%Y%m%d}0000&endDateTime={today:%Y%m%d}2359")
    rows = getj(url)
    pts = []
    for r in rows:
        d, c = r.get("localDate"), r.get("closePrice")
        if d and c:
            pts.append((d, float(c)))
    if len(pts) < 2:
        return {}
    pts.sort()
    last_d, last_c = pts[-1]

    def close_on_or_before(target):
        t = target.strftime("%Y%m%d")
        prev = [c for d, c in pts if d <= t]
        return prev[-1] if prev else None

    def pct(base):
        return round((last_c / base - 1) * 100, 2) if base else None

    ytd_base = next((c for d, c in pts if d >= f"{today.year}0101"), None)
    return {
        "ret1w": pct(close_on_or_before(today - datetime.timedelta(days=7))),
        "ret1m": pct(close_on_or_before(today - datetime.timedelta(days=30))),
        "ret3m": pct(close_on_or_before(today - datetime.timedelta(days=91))),
        "ret6m": pct(close_on_or_before(today - datetime.timedelta(days=182))),
        "ret1y": pct(close_on_or_before(today - datetime.timedelta(days=365))),
        "retYtd": pct(ytd_base),
    }


def fetch_consensus(code):
    """네이버 재무 API에서 컨센서스 추정치를 뽑는다.
       반환 단위는 십억원 (원본은 억원). EPS/비율은 원본 그대로."""
    out = {}
    ITEMS = {"매출액": "rev", "영업이익": "op", "당기순이익": "np",
             "영업이익률": "opm", "EPS": "eps", "BPS": "bps", "PBR": "pbr"}
    RATIO = ("opm", "eps", "bps", "pbr")   # 억→십억 변환 제외 (원/배 단위)

    def pull(period):
        d = getj(f"https://m.stock.naver.com/api/stock/{code}/finance/{period}")
        fi = d["financeInfo"]
        titles = {t["key"]: t for t in fi["trTitleList"]}
        rows = {r["title"]: r["columns"] for r in fi["rowList"]}
        cons_keys = sorted(k for k, t in titles.items() if t.get("isConsensus") == "Y")
        act_keys = sorted(k for k, t in titles.items() if t.get("isConsensus") != "Y")
        if not titles:
            return None

        def grab(key):
            vals = {}
            for kor, en in ITEMS.items():
                v = num((rows.get(kor) or {}).get(key, {}).get("value"))
                if v is None:
                    continue
                vals[en] = v if en in RATIO else round(v / 10, 2)  # 억 -> 십억
            return vals

        # ---- 전체 기간 시계열 ----
        # 예전엔 컨센 1개 기간만 뽑고 나머지를 버렸다. 그 탓에 실적표/분기차트가
        # 엑셀(FIN)에 의존했다. 이제 API가 주는 모든 기간을 그대로 담는다.
        #   annual  : 2023A · 2024A · 2025A · 2026E
        #   quarter : 1Q25 ~ 1Q26 실적 + 2Q26 컨센
        # e=True 면 컨센 추정치, False 면 확정 실적.
        series = []
        for k in sorted(titles):
            vals = grab(k)
            if not vals:
                continue
            series.append({"k": k, "t": titles[k]["title"],
                           "e": titles[k].get("isConsensus") == "Y", **vals})
        if not series:
            return None
        res = {"series": series}

        # ---- 하위호환: 기존 est/prev 유지 ----
        # 컨센이 아예 없는 종목(소형주)도 series 는 채워서 반환한다.
        # 예전 코드는 여기서 None 을 뱉어 실적까지 통째로 버렸다.
        if cons_keys:
            ck = cons_keys[0]                        # 가장 이른 컨센 기간
            res.update(key=ck, title=titles[ck]["title"], est=grab(ck))
            prev = str(int(ck[:4]) - 1) + ck[4:]     # 전년(동기)
            if prev in titles:
                res["prev"] = grab(prev)
            elif act_keys:
                res["prev"] = grab(act_keys[-1])
        return res

    for period, label in (("annual", "year"), ("quarter", "quarter")):
        try:
            r = pull(period)
            if r:
                out[label] = r
        except Exception:
            pass
    return out or None


TREND_DAYS = 130          # 약 6개월치 일봉


def fetch_daily(base_url, count=TREND_DAYS):
    """일봉 종가 {YYYYMMDD: 종가} — 지수·종목 공통(priceInfos 형식)"""
    d = getj(f"{base_url}?periodType=dayCandle&count={count}")
    infos = d.get("priceInfos") if isinstance(d, dict) else d
    out = {}
    for p in (infos or []):
        c = num(p.get("closePrice"))
        if c:
            out[str(p.get("localDate"))] = c
    return out


def collect_sector_trend(records, stocks):
    """소섹터별 등가중 지수를 '코스피 대비 초과수익률(%)'로 만든다.

       각 종목의 기준일 대비 수익률을 소섹터 안에서 평균낸 뒤 코스피 수익률을 뺀다.
       따라서 코스피가 0 인 수평선이 되고, 선이 위에 있으면 시장을 이긴 것이다.
       기준일 종가가 없는 종목(신규상장 등)은 지수에서 빼야 수익률이 왜곡되지 않는다."""
    try:
        kospi = fetch_daily("https://api.stock.naver.com/chart/domestic/index/KOSPI")
    except Exception as e:
        print(f"  섹터 추이 건너뜀(코스피 실패: {type(e).__name__})")
        return None
    if len(kospi) < 20:
        print(f"  섹터 추이 건너뜀(코스피 {len(kospi)}일치뿐)")
        return None

    dates = sorted(kospi)
    base = dates[0]
    by_sub, skipped = {}, []
    for r in records:
        code = (stocks.get(r["name"]) or {}).get("code")
        if not code:
            continue
        try:
            s = fetch_daily(f"https://api.stock.naver.com/chart/domestic/item/{code}")
        except Exception:
            skipped.append(r["name"]); continue
        if s.get(base):
            by_sub.setdefault(r["sub"], []).append(s)
        else:
            skipped.append(r["name"])       # 기준일 데이터 없음
        time.sleep(0.25)

    subs = {}
    for sub, arr in by_sub.items():
        line = []
        for d in dates:
            rets = [x[d] / x[base] - 1 for x in arr if x.get(d)]
            if rets:
                line.append(round((sum(rets) / len(rets) - (kospi[d] / kospi[base] - 1)) * 100, 2))
            else:
                line.append(None)
        subs[sub] = {"n": len(arr), "v": line}

    if not subs:
        return None
    print(f"  섹터 추이 {len(subs)}개 소섹터 / {len(dates)}일"
          + (f" (제외 {len(skipped)}: {', '.join(skipped[:4])})" if skipped else ""))
    return {"dates": dates, "base": base, "subs": subs}


def resolve_code(name):
    q = urllib.parse.quote(NAME_FIX.get(name, name))
    d = getj(f"https://m.stock.naver.com/front-api/search/autoComplete?query={q}&target=stock")
    items = [i for i in d["result"]["items"]
             if i.get("nationCode") == "KOR" and i.get("category") == "stock"]
    return (items[0]["code"], items[0]["typeCode"]) if items else (None, None)


def collect(names):
    stocks, researches, events, fails = {}, [], [], []
    for i, nm in enumerate(names, 1):
        try:
            code, mkt = resolve_code(nm)
            if not code:
                fails.append(nm); continue
            d = getj(f"https://m.stock.naver.com/api/stock/{code}/integration")
            b = getj(f"https://m.stock.naver.com/api/stock/{code}/basic")
            ti = {t["code"]: t.get("value") for t in d.get("totalInfos", [])}
            ci = d.get("consensusInfo") or {}
            stocks[nm] = {
                "code": code, "market": mkt,
                "price": num(b.get("closePrice")),
                "chg": num(b.get("compareToPreviousClosePrice")),
                "chgPct": num(b.get("fluctuationsRatio")),
                "mktcapEok": mktcap_eok(ti.get("marketValue")),
                "per": num(ti.get("per")), "pbr": num(ti.get("pbr")), "eps": num(ti.get("eps")),
                "cnsPer": num(ti.get("cnsPer")), "cnsEps": num(ti.get("cnsEps")),
                "divYield": num(ti.get("dividendYieldRatio")),
                "w52h": num(ti.get("highPriceOf52Weeks")), "w52l": num(ti.get("lowPriceOf52Weeks")),
                "foreign": num(ti.get("foreignRate")),
                "consTarget": num(ci.get("priceTargetMean")),
                "recommMean": num(ci.get("recommMean")),
                "cons": fetch_consensus(code),      # 컨센서스 실적 추정치
                **(fetch_returns(code) or {}),      # 1W/1M/3M/YTD 수익률
            }
            for r in (d.get("researches") or []):
                researches.append({"co": nm, "code": code, "broker": r.get("bnm"),
                                   "title": r.get("tit"), "date": r.get("wdt"),
                                   "views": num(r.get("rcnt"))})
            # IR 일정(실적발표 등) — 네이버가 제공하는 종목만 채워짐
            ir = d.get("irScheduleInfo") or {}
            if ir.get("irScheduleDate"):
                events.append({"co": nm, "code": code, "date": ir["irScheduleDate"],
                               "title": ir.get("title") or "IR 일정", "type": "earn"})
            sh = d.get("shareholdersMeetingInfo") or {}
            if sh.get("meetingDate"):
                events.append({"co": nm, "code": code, "date": sh["meetingDate"],
                               "title": sh.get("title") or "주주총회", "type": "corp"})
            print(f"  [{i}/{len(names)}] {nm} ({code}) OK")
        except Exception as e:
            fails.append(f"{nm}: {str(e)[:40]}")
        time.sleep(0.25)
    return stocks, researches, events, fails


# 커버리지 소섹터 -> 네이버 업종 번호 (커버리지 섹터 순서)
SECTOR_MAP = [
    ("화장품", 266), ("유통", 264), ("미용", 281), ("음식료", 268),
    ("엔터", 285), ("게임", 263), ("레져", 317),
]


def collect_sectors():
    """커버리지와 대응되는 네이버 업종 등락률"""
    groups = {}
    for pg in range(1, 6):
        try:
            d = getj(f"https://m.stock.naver.com/api/stocks/industry?page={pg}&pageSize=20")
        except Exception:
            break
        for g in d.get("groups", []):
            groups[g["no"]] = g
        if len(groups) >= d.get("totalCount", 0):
            break
    out = []
    for sub, no in SECTOR_MAP:
        g = groups.get(no)
        if not g:
            continue
        out.append({"sub": sub, "name": g["name"], "no": no, "chgPct": num(g.get("changeRate")),
                    "rise": g.get("riseCount"), "fall": g.get("fallCount"),
                    "n": g.get("totalCount")})
    return out


def collect_market():
    market = {}
    for idx in ["KOSPI", "KOSDAQ"]:
        try:
            d = getj(f"https://m.stock.naver.com/api/index/{idx}/basic")
            market[idx] = {"close": num(d.get("closePrice")),
                           "chg": num(d.get("compareToPreviousClosePrice")),
                           "chgPct": num(d.get("fluctuationsRatio"))}
        except Exception as e:
            print("  지수 실패:", idx, e)
    try:
        fx = getj("https://open.er-api.com/v6/latest/USD")["rates"]
        market["FX"] = {"USDKRW": round(fx["KRW"], 1),
                        "JPYKRW100": round(fx["KRW"] / fx["JPY"] * 100, 1),
                        "CNYKRW": round(fx["KRW"] / fx["CNY"], 1)}
    except Exception as e:
        print("  환율 실패:", e)
    try:
        market["sectors"] = collect_sectors()
    except Exception as e:
        print("  업종 실패:", e)
    return market


def main():
    html = open(HTML_PATH, encoding="utf-8").read()

    # index.html 에 이미 박혀 있는 커버리지 종목명을 그대로 사용
    m = re.search(r"const DATA = (\{.*?\});\n", html, re.S)
    if not m:
        print("index.html 에서 DATA 블록을 찾지 못했습니다."); sys.exit(1)
    records = json.loads(m.group(1))["records"]
    names = [r["name"] for r in records]
    print(f"커버리지 {len(names)}종목 수집 시작…")

    stocks, researches, events, fails = collect(names)
    market = collect_market()
    sector_trend = collect_sector_trend(records, stocks)
    researches.sort(key=lambda x: x["date"] or "", reverse=True)
    events.sort(key=lambda x: x["date"] or "")

    # GitHub Actions(UTC)에서 돌아도 한국시간으로 표기
    kst = datetime.timezone(datetime.timedelta(hours=9))
    live = {"asOf": datetime.datetime.now(kst).strftime("%Y-%m-%d %H:%M"),
            "market": market, "stocks": stocks, "researches": researches,
            "events": events}
    if sector_trend:
        live["sectorTrend"] = sector_trend

    # 수집 시각(asOf)만 바뀐 경우는 저장하지 않는다.
    # -> 장 마감 후·주말·공휴일에 불필요한 커밋/배포가 쌓이는 것을 막는다.
    old = None
    m_old = re.search(r"const LIVE = (\{.*?\});", html, re.S)
    if m_old:
        try:
            old = json.loads(m_old.group(1))
        except json.JSONDecodeError:
            old = None
    if old is not None:
        def strip(d):
            # asOf(수집시각)와 리포트 조회수는 계속 변하므로 비교에서 제외
            out = {k: v for k, v in d.items() if k != "asOf"}
            out["researches"] = [{k: v for k, v in r.items() if k != "views"}
                                 for r in d.get("researches", [])]
            return out
        if strip(old) == strip(live):
            print(f"\n[SKIP] 시세·리포트·일정 변동 없음 - index.html 그대로 둠 ({live['asOf']})")
            return

    new_block = "const LIVE = " + json.dumps(live, ensure_ascii=False) + ";"
    new_html, n = re.subn(r"const LIVE = \{.*?\};", new_block, html, count=1, flags=re.S)
    if not n:
        print("LIVE 블록을 찾지 못했습니다."); sys.exit(1)
    open(HTML_PATH, "w", encoding="utf-8").write(new_html)

    print(f"\n[OK] 갱신 완료 - 종목 {len(stocks)} / 리포트 {len(researches)}건 / 일정 {len(events)}건 / {live['asOf']}")
    if market.get("KOSPI"):
        print(f"   KOSPI {market['KOSPI']['close']:,} ({market['KOSPI']['chgPct']:+}%)")
    if fails:
        print("   실패:", fails)


if __name__ == "__main__":
    main()
