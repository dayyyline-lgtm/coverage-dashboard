"""통계청(국가데이터처) 온라인쇼핑동향 — 상품군별 온라인쇼핑 거래액(월) -> index.html 의  const KOSIS = {...};   (2026-11-03)

KOSIS 공유서비스(OpenAPI) 통계표 DT_1KE10051 '온라인쇼핑몰 운영형태별/상품군별거래액'(orgId 101 · 백만원 · 월 · 익월 초 공표).
운영형태 '계' 만 쓴다(종합몰·전문몰 갈래는 버린다). 화장품·음식료품·의복·여행·아동유아용품·음반 같은 상품군을
그 업종 종목들의 트렌드 탭에 '온라인쇼핑 거래액' 으로 붙인다(app.js injectKosisTrends · 작년 같은 달과 비교).

키: KOSIS 공유서비스 회원가입 → 활용신청 → 인증키(무료) → GitHub 시크릿 KOSIS_API_KEY.
   키가 없으면 아무것도 안 하고 끝낸다(기존 블록 그대로).
⚠ 이 PC/클라우드 작업 공간에서는 kosis.kr 에 못 닿는다 — 첫 확인은 Actions 회차 로그로 한다.
   항목·분류 코드를 몰라도 되게 itmId·objL1·objL2 를 ALL 로 받고 이름(C1_NM·C2_NM·ITM_NM)으로 고른다.

python fetch_kosis.py
"""
import datetime, json, os, re, time, urllib.parse, urllib.request

from collector_health import note_health

KST = datetime.timezone(datetime.timedelta(hours=9))
HTML = "public/index.html"
KEY = os.environ.get("KOSIS_API_KEY", "")
TABLES = {"online": {"orgId": "101", "tblId": "DT_1KE10051", "nm": "온라인쇼핑몰 운영형태별/상품군별 거래액"}}
START = "201801"


def _get(params):
    q = {"method": "getList", "apiKey": KEY, "format": "json", "jsonVD": "Y", "prdSe": "M"}
    q.update(params)
    u = "https://kosis.kr/openapi/Param/statisticsParameterData.do?" + urllib.parse.urlencode(q)
    raw = urllib.request.urlopen(u, timeout=60).read().decode("utf-8", "replace")
    d = json.loads(raw)
    if isinstance(d, dict):          # 오류는 {"err":"20","errMsg":"..."} 로 온다
        raise RuntimeError(f"KOSIS {d.get('err')} {d.get('errMsg')}")
    return d


def fetch_online(start, end):
    t = TABLES["online"]
    base = {"orgId": t["orgId"], "tblId": t["tblId"], "itmId": "ALL", "objL1": "ALL", "objL2": "ALL",
            "startPrdDe": start, "endPrdDe": end}
    try:
        rows = _get(base)
    except RuntimeError as e:
        # 셀 한도(4만)에 걸리면 연도별로 쪼갠다
        if "31" not in str(e) and "한도" not in str(e):
            raise
        rows = []
        for y in range(int(start[:4]), int(end[:4]) + 1):
            p = dict(base); p["startPrdDe"] = max(start, f"{y}01"); p["endPrdDe"] = min(end, f"{y}12")
            rows += _get(p); time.sleep(0.5)
    s, unit = {}, None
    for r in rows:
        c1, c2 = (r.get("C1_NM") or "").strip(), (r.get("C2_NM") or "").strip()
        itm = (r.get("ITM_NM") or "").strip()
        if c1 not in ("계", "합계", "전체"):
            continue
        if itm and "거래액" not in itm:
            continue
        try:
            v = float(str(r.get("DT", "")).replace(",", ""))
        except ValueError:
            continue
        p = str(r.get("PRD_DE", ""))
        if len(p) != 6:
            continue
        s.setdefault(c2 or "합계", {})[f"{p[:4]}-{p[4:]}"] = v
        unit = unit or r.get("UNIT_NM")
    return s, unit


def main():
    if not KEY:
        print("[KOSIS] KOSIS_API_KEY 없음 — 건너뜀(GitHub Settings > Secrets 에 등록)")
        return
    now = datetime.datetime.now(KST)
    html = open(HTML, encoding="utf-8").read()
    m = re.search(r"^const KOSIS = (\{.*?\});$", html, re.M | re.S)
    old = json.loads(m.group(1)) if m else {}
    end = now.strftime("%Y%m")
    # 있으면 마지막 달 12개월 앞부터만 다시 받아 붙인다(잠정치 수정 반영)
    ov = (old.get("online") or {}).get("s") or {}
    st = START
    if ov:
        last = max(max(v) for v in ov.values() if v)
        y, mo = int(last[:4]), int(last[5:]) - 12
        while mo < 1:
            mo += 12; y -= 1
        st = max(START, f"{y}{mo:02d}")
    try:
        new, unit = fetch_online(st, end)
    except Exception as e:
        print("[KOSIS] 실패:", str(e)[:200]); note_health("KOSIS 온라인쇼핑", f"{type(e).__name__}: {str(e)[:150]}")
        return
    if not new:
        print("[KOSIS] 받은 행 없음 — 운영형태 '계' 이름이 바뀌었는지 확인"); note_health("KOSIS 온라인쇼핑", "받은 행 없음"); return
    s = {k: dict(v) for k, v in ov.items()}
    for k, v in new.items():
        s.setdefault(k, {}).update(v)
    s = {k: dict(sorted(v.items())) for k, v in s.items()}
    for k, v in sorted(s.items()):
        print(f"[KOSIS] {k:16} {len(v)}개월 · 마지막 {max(v)} {v[max(v)]:,.0f}")
    note_health("KOSIS 온라인쇼핑", None)
    if m and (old.get("online") or {}).get("s") == s:
        print("[KOSIS] 변동 없음"); return
    out = {"asOf": now.strftime("%Y-%m-%d %H:%M KST"),
           "online": {"tbl": TABLES["online"]["tblId"], "nm": TABLES["online"]["nm"], "unit": unit or "백만원", "s": s},
           "note": "통계청 온라인쇼핑동향 · KOSIS DT_1KE10051 · 운영형태 계 · 상품군별 거래액(백만원) · 월 · 익월 초 공표(최근 달은 잠정)"}
    block = "const KOSIS = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";"
    if m:
        html = html[:m.start()] + block + html[m.end():]
    else:
        a = re.search(r"^const TREND = ", html, re.M)
        html = html[:a.start()] + block + "\n" + html[a.start():]
    open(HTML, "w", encoding="utf-8").write(html)
    print(f"[KOSIS] 블록 갱신 {len(block) // 1024}KB · 상품군 {len(s)}")


if __name__ == "__main__":
    main()
