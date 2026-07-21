# -*- coding: utf-8 -*-
"""
관세청 수출입무역통계 -> 대체데이터(수출 동향) 수집
---------------------------------------------------
index.html 의  const TRADE = {...};  블록을 갱신합니다.

필요 API (공공데이터포털에서 '활용신청', 무료·자동승인)
  관세청_품목별 국가별 수출입실적(GW)
  https://www.data.go.kr/data/15100475/openapi.do

키는 secrets_local.py 의 DATA_GO_KR_KEY (일반 인증키 Decoding)
또는 환경변수 DATA_GO_KR_KEY.

사용법:  python fetch_trade.py
"""
import urllib.request, urllib.parse, json, re, sys, os, time, datetime
import xml.etree.ElementTree as ET

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML_PATH = "public/index.html"
API = "https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"
MONTHS = 13          # 최근 N개월 (YoY 비교 위해 13개월)

try:
    from secrets_local import DATA_GO_KR_KEY
except ImportError:
    DATA_GO_KR_KEY = ""
DATA_GO_KR_KEY = os.environ.get("DATA_GO_KR_KEY", DATA_GO_KR_KEY)

# 커버리지와 직결되는 품목 (HS코드) x 국가
ITEMS = [
    {"hs": "3304",   "label": "화장품",        "note": "기초·색조 (에이피알·아모레·코스맥스·한국콜마·실리콘투)"},
    {"hs": "3307",   "label": "기타 미용제품",  "note": "화장품 밸류체인"},
    {"hs": "190230", "label": "라면",          "note": "삼양식품·농심"},
]
COUNTRIES = [
    {"cd": "",   "name": "전체"},
    {"cd": "US", "name": "미국"},
    {"cd": "JP", "name": "일본"},
    {"cd": "CN", "name": "중국"},
]


def yymm_range(n):
    today = datetime.date.today().replace(day=1)
    out = []
    for i in range(n, 0, -1):
        y, m = today.year, today.month - i
        while m <= 0:
            m += 12; y -= 1
        out.append(f"{y}{m:02d}")
    return out


def call(hs, cnty, start, end):
    p = {"serviceKey": DATA_GO_KR_KEY, "strtYymm": start, "endYymm": end, "hsSgn": hs}
    if cnty:
        p["cntyCd"] = cnty
    url = API + "?" + urllib.parse.urlencode(p, safe="")
    raw = urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read()
    root = ET.fromstring(raw)
    # 오류 응답 확인
    msg = root.findtext(".//errMsg") or root.findtext(".//resultMsg") or ""
    if msg and "정상" not in msg and "NORMAL" not in msg.upper():
        raise RuntimeError(msg[:80])
    rows = []
    for it in root.iter("item"):
        g = lambda t: (it.findtext(t) or "").strip()
        def num(t):
            v = g(t).replace(",", "")
            try: return float(v)
            except ValueError: return None
        rows.append({"ym": g("year"), "expDlr": num("expDlr"), "impDlr": num("impDlr"),
                     "expWgt": num("expWgt"), "balPayments": num("balPayments")})
    return [r for r in rows if r["ym"] and re.fullmatch(r"\d{6}", r["ym"])]


def main():
    if not DATA_GO_KR_KEY:
        print("DATA_GO_KR_KEY 가 없습니다. secrets_local.py 에 넣어주세요."); sys.exit(1)

    months = yymm_range(MONTHS)
    start, end = months[0], months[-1]
    print(f"조회 기간 {start} ~ {end}")

    out = {"asOf": datetime.datetime.now(
               datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"),
           "months": months, "items": []}

    for item in ITEMS:
        entry = {"hs": item["hs"], "label": item["label"], "note": item["note"], "byCountry": []}
        for c in COUNTRIES:
            try:
                rows = call(item["hs"], c["cd"], start, end)
                by = {r["ym"]: r["expDlr"] for r in rows}
                series = [by.get(m) for m in months]
                entry["byCountry"].append({"code": c["cd"], "name": c["name"], "exp": series})
                last = next((v for v in reversed(series) if v), None)
                print(f"  {item['label']:<12} {c['name']:<4} 최근 {last if last else '-'} 천달러")
            except Exception as e:
                print(f"  {item['label']:<12} {c['name']:<4} 실패: {str(e)[:60]}")
            time.sleep(0.3)
        out["items"].append(entry)

    if not any(c.get("exp") for i in out["items"] for c in i["byCountry"]):
        print("\n수집된 데이터가 없습니다. index.html 은 그대로 둡니다."); sys.exit(1)

    block = "const TRADE = " + json.dumps(out, ensure_ascii=False) + ";"
    html = open(HTML_PATH, encoding="utf-8").read()
    if "const TRADE =" in html:
        html = re.sub(r"const TRADE = \{.*?\};", block, html, count=1, flags=re.S)
    else:
        html = html.replace("/* ==== helpers ==== */", block + "\n\n/* ==== helpers ==== */", 1)
    open(HTML_PATH, "w", encoding="utf-8").write(html)
    print(f"\n[OK] 수출 데이터 반영 완료 ({len(out['items'])}개 품목)")


if __name__ == "__main__":
    main()
