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
SIGUNGU_API = "https://apis.data.go.kr/1220000/sigunguperprlstperacrs/getSigunguPerPrlstPerAcrs"
MONTHS = 24          # 최근 N개월 (12개월씩 2회 조회, YoY 계산용)

# 지역(시군구) 프록시 품목 — 전용 HS가 없어 국가별 통계로는 안 잡히는 종목을 '제조지역'으로 포착.
#   수출은 「제조장소 우편번호」 기준이라, 파마리서치 강릉공장의 기타화장품(330499)=리쥬란·필러가
#   강릉시로 잡힌다. 도(강원) 단위는 원주 등 타 화장품 공장과 혼재하므로 반드시 시(강릉)로 좁힌다.
#   시군구 API 는 HS 6자리 필수. 여러 세부코드는 합산한다.
REGION_ITEMS = [
    {"label": "리쥬란(강릉 기타화장품)", "hs": ["330499"], "sidoCd": "51", "sgg": "강릉",
     "note": "파마리서치 강릉공장 · 기타화장품(330499) 제조지 기준 = 리쥬란·필러 프록시 (전용 HS 없음)"},
    {"label": "창상피복재(안성)", "hs": ["300510", "300590"], "sidoCd": "41", "sgg": "안성",
     "note": "티앤엘 안성공장 · 창상피복재(하이드로콜로이드 여드름패치, 300510+590) 제조지 기준 프록시. 안성이 경기 300590 압도적 1위"},
]

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
        # 금액만 쓰다가 중량도 같이 받는다 — 금액÷중량 = 수출단가(ASP).
        # 화장품은 물량보다 단가가 마진을 좌우해서, 금액이 빠질 때
        # '물량만 준 건지 단가까지 무너진 건지' 를 이걸로 가른다.
        try:
            exp = float(g("expDlr").replace(",", ""))
        except ValueError:
            continue
        try:
            wgt = float(g("expWgt").replace(",", ""))
        except ValueError:
            wgt = 0.0
        out.append((ym.replace(".", ""), hs, cd, exp, wgt))
    return out


def windows(months):
    """API가 1년 이내만 허용 -> 12개월씩 쪼갠다"""
    return [months[i:i + 12] for i in range(0, len(months), 12)]


def fetch_sigungu_series(hs_list, sido_cd, sgg, months):
    """시군구 월별 수출액(달러) 시계열을 months 축에 맞춰 반환. 시군구 API는 6자리 HS·월별(priodTitle) 응답.
       hs_list 의 여러 세부코드를 합산한다."""
    ym2v = {}
    for y in sorted({m[:4] for m in months}):          # 연 경계 누락 방지 — 연도별 조회
        for hs in hs_list:
            p = {"serviceKey": DATA_GO_KR_KEY, "strtYymm": f"{y}01", "endYymm": f"{y}12",
                 "hsSgn": hs, "sidoCd": sido_cd, "numOfRows": "2000"}
            url = SIGUNGU_API + "?" + urllib.parse.urlencode(p, safe="")
            try:
                raw = urllib.request.urlopen(
                    urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
            except Exception as e:
                print(f"  시군구 {sgg} {hs} {y} 실패: {str(e)[:50]}"); continue
            for it in ET.fromstring(raw).iter("item"):
                g = lambda t: (it.findtext(t) or "").strip()
                if sgg in g("sggNm") and g("hsSgn").startswith(hs):
                    ym = g("priodTitle").replace(".", "")   # 2024.05 -> 202405
                    if re.fullmatch(r"\d{6}", ym):
                        try:
                            ym2v[ym] = ym2v.get(ym, 0.0) + float(g("expUsdAmt").replace(",", "")) * 1000  # 천달러->달러
                        except ValueError:
                            pass
            time.sleep(0.35)
    return [round(ym2v[m], 1) if m in ym2v else None for m in months]


def main():
    if not DATA_GO_KR_KEY:
        print("DATA_GO_KR_KEY 가 없습니다."); sys.exit(1)

    # 직전 TRADE(변동 비교용) — 매일 돌려도 새 월/현행화가 없으면 파일을 안 건드리게.
    html0 = open(HTML_PATH, encoding="utf-8").read()
    old_trade = None
    _m = re.search(r"const TRADE = (\{.*?\});", html0, re.S)
    if _m:
        try:
            old_trade = json.loads(_m.group(1))
        except json.JSONDecodeError:
            old_trade = None

    months = yymm_range(MONTHS)
    prefixes = sorted({i["hs"][:4] if len(i["hs"]) > 4 else i["hs"] for i in ITEMS})
    print(f"조회 {months[0]} ~ {months[-1]} · HS {prefixes}")

    # (월, hs, 국가) -> [수출액, 수출중량]
    raw = {}
    for pref in prefixes:
        for w in windows(months):
            try:
                rows = call_bulk(pref, w[0], w[-1])
                for ym, hs, cd, exp, wgt in rows:
                    cur = raw.get((ym, hs, cd)) or [0.0, 0.0]
                    raw[(ym, hs, cd)] = [cur[0] + exp, cur[1] + wgt]
                print(f"  HS {pref} {w[0]}~{w[-1]}: {len(rows):,}건")
            except Exception as e:
                print(f"  HS {pref} {w[0]}~{w[-1]} 실패: {str(e)[:60]}")
            time.sleep(0.4)

    if not raw:
        print("\n수집 실패. index.html 은 그대로 둡니다."); sys.exit(1)

    eu_codes = [c for c, _ in EUROPE]

    def series(hs_spec, country, what="exp"):
        """what: exp=수출액(달러) · asp=수출단가(달러/kg)
           단가는 월별 합계끼리 나눈다 — 품목·국가를 합칠 때 가중평균이 되도록."""
        out = []
        for m in months:
            tot = 0.0; wt = 0.0; hit = False
            for (ym, hs, cd), v in raw.items():
                if ym != m: continue
                if not hs.startswith(hs_spec): continue
                if country == "":                     pass
                elif country == "EU9":
                    if cd not in eu_codes: continue
                elif cd != country:                   continue
                tot += v[0]; wt += v[1]; hit = True
            if not hit:
                out.append(None)
            elif what == "asp":
                out.append(round(tot / wt, 2) if wt > 0 else None)
            else:
                out.append(round(tot, 1))
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
                                       "exp": series(item["hs"], c["cd"]),
                                       "asp": series(item["hs"], c["cd"], "asp")})
        entry["byCountry"].append({"code": "EU9", "name": "유럽 9개국",
                                   "exp": series(item["hs"], "EU9"),
                                   "asp": series(item["hs"], "EU9", "asp"),
                                   "members": [n for _, n in EUROPE]})
        for c, n in EUROPE:
            entry["byCountry"].append({"code": c, "name": n, "exp": series(item["hs"], c),
                                       "asp": series(item["hs"], c, "asp")})
        last = next((v for v in reversed(entry["byCountry"][0]["exp"]) if v), None)
        print(f"  {item['label']:<12} 전체 최근 {last/1e6 if last else 0:,.1f} 백만달러")
        out["items"].append(entry)

    # 지역(시군구) 프록시 품목 — 단일 지역 시계열(국가 구분 없음)
    for ri in REGION_ITEMS:
        exp = fetch_sigungu_series(ri["hs"], ri["sidoCd"], ri["sgg"], months)
        last = next((v for v in reversed(exp) if v), None)
        print(f"  {ri['label']:<20} {ri['sgg']} 최근 {last/1e6 if last else 0:,.1f} 백만달러")
        out["items"].append({"hs": ri["hs"], "label": ri["label"], "note": ri["note"],
                             "region": True,
                             "byCountry": [{"code": "", "name": ri["sgg"], "exp": exp}]})

    # 값(월·품목) 변동이 없으면 asOf 만 바뀌므로 파일을 안 건드린다 —
    # 매일 돌려도 새 월이 뜨거나 기존 월이 현행화될 때만 커밋/배포된다.
    if old_trade and {k: v for k, v in old_trade.items() if k != "asOf"} == \
                     {k: v for k, v in out.items() if k != "asOf"}:
        newest = max((m for it in out["items"] for c in it.get("byCountry", [])
                      for m, v in zip(out["months"], c.get("exp") or []) if v is not None), default="?")
        print(f"[SKIP] 수출 변동 없음(최신월 {newest}) — index.html 그대로 둠"); return

    block = "const TRADE = " + json.dumps(out, ensure_ascii=False) + ";"
    html = open(HTML_PATH, encoding="utf-8").read()
    html = re.sub(r"const TRADE = \{.*?\};", block, html, count=1, flags=re.S)
    open(HTML_PATH, "w", encoding="utf-8").write(html)
    print(f"\n[OK] 수출 데이터 반영 - {len(out['items'])}개 품목 x "
          f"{len(out['items'][0]['byCountry'])}개 국가")


if __name__ == "__main__":
    main()
