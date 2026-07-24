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
MONTHS = 24          # 최근 N개월 (12개월씩 2회 조회, YoY 계산용)

try:
    from secrets_local import DATA_GO_KR_KEY
except ImportError:
    DATA_GO_KR_KEY = ""
DATA_GO_KR_KEY = os.environ.get("DATA_GO_KR_KEY", DATA_GO_KR_KEY)

# 커버리지와 직결되는 품목 (HS코드)
#   3304   화장품 전체
#   330499 기타 = 기초화장품(스킨케어·선크림)  <- K뷰티 수출의 대부분
#   330410 입술화장품 / 330420 눈화장품 / 330491 파우더  = 색조
#   3307   기타 조제향료·화장품 = 마스크팩류
#   3005   창상피복재(드레싱) — 300510 접착성 / 300590 기타
ITEMS = [
    {"hs": "3304",   "label": "화장품 전체",  "note": "에이피알·아모레·코스맥스·한국콜마·실리콘투"},
    {"hs": "330499", "label": "기초",        "note": "스킨케어·선크림 (330499)"},
    {"hs": "330410", "label": "색조-립",     "note": "입술화장품 (330410)"},
    {"hs": "330420", "label": "색조-아이",   "note": "눈화장품 (330420)"},
    {"hs": "330491", "label": "색조-파우더", "note": "파우더 (330491)"},
    {"hs": "3307",   "label": "마스크팩류",  "note": "기타 조제화장품 (3307)"},
    {"hs": "3005",   "label": "창상피복재",      "note": "파마리서치·엘앤씨바이오 등 (3005 전체)"},
    {"hs": "300510", "label": "창상피복재-접착성", "note": "접착성 피복재 (300510)"},
    {"hs": "300590", "label": "창상피복재-기타",   "note": "기타 피복재 (300590)"},
    {"hs": "190230", "label": "라면",        "note": "삼양식품·농심 (190230)"},
    {"hs": "190220", "label": "만두",        "note": "CJ제일제당 비비고 (190220 속을 채운 파스타)"},
]

# 유럽 주요 K-뷰티 수출국 9개국 (필요시 자유롭게 교체)
EUROPE = [
    ("GB", "영국"), ("FR", "프랑스"), ("DE", "독일"), ("NL", "네덜란드"),
    ("PL", "폴란드"), ("IT", "이탈리아"), ("ES", "스페인"),
    ("SE", "스웨덴"), ("BE", "벨기에"),
]

COUNTRIES = ([{"cd": "", "name": "전체"},
              {"cd": "US", "name": "미국"},
              {"cd": "JP", "name": "일본"},
              {"cd": "CN", "name": "중국"}]
             + [{"cd": c, "name": n, "eu": True} for c, n in EUROPE])


def yymm_range(n):
    today = datetime.date.today().replace(day=1)
    out = []
    for i in range(n, 0, -1):
        y, m = today.year, today.month - i
        while m <= 0:
            m += 12; y -= 1
        out.append(f"{y}{m:02d}")
    return out


def call_bulk(hs_prefix, start, end):
    """국가/세부HS 미지정으로 한 번에 받아온다 (국가 x 세부HS x 월 전체)"""
    p = {"serviceKey": DATA_GO_KR_KEY, "strtYymm": start, "endYymm": end, "hsSgn": hs_prefix}
    url = API + "?" + urllib.parse.urlencode(p, safe="")
    raw = urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
    root = ET.fromstring(raw)
    msg = root.findtext(".//resultMsg") or ""
    if msg and "정상" not in msg:
        raise RuntimeError(msg[:70])
    out = []
    for it in root.iter("item"):
        g = lambda t: (it.findtext(t) or "").strip()
        ym, hs, cd = g("year"), g("hsCd"), g("statCd")
        if not re.fullmatch(r"\d{4}\.\d{2}", ym):   # '총계' 행 제외
            continue
        if not hs.isdigit() or not re.fullmatch(r"[A-Z]{2}", cd):
            continue
        v = g("expDlr").replace(",", "")
        try: exp = float(v)
        except ValueError: continue
        out.append((ym.replace(".", ""), hs, cd, exp))
    return out


def windows(months):
    """API가 1년 이내만 허용 -> 12개월씩 쪼갠다"""
    return [months[i:i + 12] for i in range(0, len(months), 12)]


def main():
    if not DATA_GO_KR_KEY:
        print("DATA_GO_KR_KEY 가 없습니다."); sys.exit(1)

    months = yymm_range(MONTHS)
    prefixes = sorted({i["hs"][:4] if len(i["hs"]) > 4 else i["hs"] for i in ITEMS})
    print(f"조회 {months[0]} ~ {months[-1]} · HS {prefixes}")

    # (월, hs, 국가) -> 수출액
    raw = {}
    for pref in prefixes:
        for w in windows(months):
            try:
                rows = call_bulk(pref, w[0], w[-1])
                for ym, hs, cd, exp in rows:
                    raw[(ym, hs, cd)] = raw.get((ym, hs, cd), 0) + exp
                print(f"  HS {pref} {w[0]}~{w[-1]}: {len(rows):,}건")
            except Exception as e:
                print(f"  HS {pref} {w[0]}~{w[-1]} 실패: {str(e)[:60]}")
            time.sleep(0.4)

    if not raw:
        print("\n수집 실패. index.html 은 그대로 둡니다."); sys.exit(1)

    eu_codes = [c for c, _ in EUROPE]

    def series(hs_spec, country):
        out = []
        for m in months:
            tot = 0.0; hit = False
            for (ym, hs, cd), v in raw.items():
                if ym != m: continue
                if not hs.startswith(hs_spec): continue
                if country == "":                     pass
                elif country == "EU9":
                    if cd not in eu_codes: continue
                elif cd != country:                   continue
                tot += v; hit = True
            out.append(round(tot, 1) if hit else None)
        return out

    out = {"asOf": datetime.datetime.now(
               datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"),
           "months": months, "items": []}

    for item in ITEMS:
        entry = {"hs": item["hs"], "label": item["label"], "note": item["note"], "byCountry": []}
        for c in COUNTRIES:
            code = "EU9" if c.get("eu") else c["cd"]
            if c.get("eu"):
                continue                              # 개별 유럽국은 합계로만
            entry["byCountry"].append({"code": c["cd"], "name": c["name"],
                                       "exp": series(item["hs"], c["cd"])})
        entry["byCountry"].append({"code": "EU9", "name": "유럽 9개국",
                                   "exp": series(item["hs"], "EU9"),
                                   "members": [n for _, n in EUROPE]})
        for c, n in EUROPE:
            entry["byCountry"].append({"code": c, "name": n, "exp": series(item["hs"], c)})
        last = next((v for v in reversed(entry["byCountry"][0]["exp"]) if v), None)
        print(f"  {item['label']:<12} 전체 최근 {last/1e6 if last else 0:,.1f} 백만달러")
        out["items"].append(entry)

    block = "const TRADE = " + json.dumps(out, ensure_ascii=False) + ";"
    html = open(HTML_PATH, encoding="utf-8").read()
    html = re.sub(r"const TRADE = \{.*?\};", block, html, count=1, flags=re.S)
    open(HTML_PATH, "w", encoding="utf-8").write(html)
    print(f"\n[OK] 수출 데이터 반영 - {len(out['items'])}개 품목 x "
          f"{len(out['items'][0]['byCountry'])}개 국가")


if __name__ == "__main__":
    main()
