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

HTML_PATH = "index.html"
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
    return market


def main():
    html = open(HTML_PATH, encoding="utf-8").read()

    # index.html 에 이미 박혀 있는 커버리지 종목명을 그대로 사용
    m = re.search(r"const DATA = (\{.*?\});\n", html, re.S)
    if not m:
        print("index.html 에서 DATA 블록을 찾지 못했습니다."); sys.exit(1)
    names = [r["name"] for r in json.loads(m.group(1))["records"]]
    print(f"커버리지 {len(names)}종목 수집 시작…")

    stocks, researches, events, fails = collect(names)
    market = collect_market()
    researches.sort(key=lambda x: x["date"] or "", reverse=True)
    events.sort(key=lambda x: x["date"] or "")

    # GitHub Actions(UTC)에서 돌아도 한국시간으로 표기
    kst = datetime.timezone(datetime.timedelta(hours=9))
    live = {"asOf": datetime.datetime.now(kst).strftime("%Y-%m-%d %H:%M"),
            "market": market, "stocks": stocks, "researches": researches,
            "events": events}

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
