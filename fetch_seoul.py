"""서울시 상권분석서비스 — 상권별·업종별 카드 추정매출(분기) -> index.html 의  const SEOULSALES = {...};   (2026-11-03)

서울 열린데이터광장 OA-15572 '서울시 상권분석서비스(추정매출-상권)' · 서비스 VwsmTrdarSelngQq · 제공 서울신용보증재단 · 원천 카드사 매출.
행 = (분기 STDR_YYQU_CD · 상권 TRDAR_CD · 업종 SVC_INDUTY_CD_NM) 하나. 분기에 약 2.1만 행 → 1,000행씩 받는다.
  · THSMON_SELNG_AMT = 그 분기 추정 매출(원) · THSMON_SELNG_CO = 건수 (이름은 '당월' 이지만 분기 집계다)
  · 상권 구분 TRDAR_SE_CD: A 골목 · D 발달 · R 전통시장 · U 관광특구(명동·이태원·동대문·종로청계·잠실·강남 마이스)
  · 서울 '상권' 안 매출만이다(상권 밖 가게는 없다) — 서울 전체 매출이 아니라 같은 표본의 추이로 읽을 것.
업종마다 분기 합계 · 관광특구 합계 · 여성 매출 · 20대 매출을 쌓는다. 화면은 app.js injectSeoulTrends(작년 같은 분기와 비교).

키: 서울 열린데이터광장 인증키(무료) → GitHub 시크릿 SEOUL_API_KEY. 없으면 건너뛴다.
분기 자료는 다음 분기 셋째 달쯤 올라온다(2026-09-11 에 2Q26). 이미 있는 분기는 다시 안 받는다 — 회차마다 '다음 분기가 생겼나' 1요청.

python fetch_seoul.py
"""
import datetime, json, os, re, time, urllib.request

from collector_health import note_health

KST = datetime.timezone(datetime.timedelta(hours=9))
HTML = "public/index.html"
KEY = os.environ.get("SEOUL_API_KEY", "")
SVC = "VwsmTrdarSelngQq"
FIRST = "20211"
PAGE = 1000
MAX_Q_PER_RUN = 6          # 첫 회차 백필은 여러 날에 나눈다(Actions 스텝 시간 보호)


def _get(a, b, q):
    u = f"http://openapi.seoul.go.kr:8088/{KEY}/json/{SVC}/{a}/{b}/{q}"
    d = json.loads(urllib.request.urlopen(u, timeout=60).read().decode("utf-8", "replace"))
    v = d.get(SVC) or {}
    code = (v.get("RESULT") or d.get("RESULT") or {}).get("CODE", "")
    if code == "INFO-200":           # 해당하는 데이터가 없습니다
        return 0, []
    if code and code != "INFO-000":
        raise RuntimeError(f"{code} {(v.get('RESULT') or d.get('RESULT') or {}).get('MESSAGE')}")
    return int(v.get("list_total_count") or 0), v.get("row") or []


def quarters(first, last):
    y, q = int(first[:4]), int(first[4])
    out = []
    while f"{y}{q}" <= last:
        out.append(f"{y}{q}")
        q += 1
        if q > 4:
            y, q = y + 1, 1
    return out


def fetch_quarter(q):
    total, rows = _get(1, PAGE, q)
    if not total:
        return None
    for a in range(PAGE + 1, total + 1, PAGE):
        time.sleep(0.25)
        _, r = _get(a, min(a + PAGE - 1, total), q)
        rows += r
    agg = {}
    for r in rows:
        nm = (r.get("SVC_INDUTY_CD_NM") or "").strip()
        if not nm:
            continue
        g = agg.setdefault(nm, [0.0, 0.0, 0.0, 0.0, 0.0])
        amt = float(r.get("THSMON_SELNG_AMT") or 0)
        g[0] += amt
        g[1] += float(r.get("THSMON_SELNG_CO") or 0)
        if r.get("TRDAR_SE_CD") == "U":
            g[2] += amt
        g[3] += float(r.get("FML_SELNG_AMT") or 0)
        g[4] += float(r.get("AGRDE_20_SELNG_AMT") or 0)
    # 원 → 억원(매출) · 건수는 그대로 · 소수 1자리
    return {k: [round(v[0] / 1e8, 1), round(v[1]), round(v[2] / 1e8, 1), round(v[3] / 1e8, 1), round(v[4] / 1e8, 1)]
            for k, v in agg.items()}, total, len(rows)


def main():
    if not KEY:
        print("[서울 상권] SEOUL_API_KEY 없음 — 건너뜀(키를 넣기 전엔 알림도 안 보낸다)"); return
    now = datetime.datetime.now(KST)
    html = open(HTML, encoding="utf-8").read()
    m = re.search(r"^const SEOULSALES = (\{.*?\});$", html, re.M | re.S)
    old = json.loads(m.group(1)) if m else {}
    have = dict(old.get("q") or {})
    cur = f"{now.year}{(now.month - 1) // 3 + 1}"
    want = [q for q in quarters(FIRST, cur) if q not in have]
    got, bad = 0, []
    for q in want:
        if got >= MAX_Q_PER_RUN:
            print(f"[서울 상권] 이번 회차 {MAX_Q_PER_RUN}분기까지 — 나머지는 다음 회차"); break
        try:
            r = fetch_quarter(q)
        except Exception as e:
            bad.append(f"{q} {type(e).__name__}"); print(f"[서울 상권] {q} 실패: {str(e)[:150]}"); break
        if r is None:
            print(f"[서울 상권] {q} 아직 없음"); continue
        agg, total, n = r
        if n < total * 0.98:
            bad.append(f"{q} 행 부족 {n}/{total}"); print(f"[서울 상권] {q} 행 부족 {n}/{total} — 버림"); continue
        have[q] = agg; got += 1
        print(f"[서울 상권] {q} {n:,}행 · 업종 {len(agg)} · 화장품 {agg.get('화장품', ['-'])[0]}억")
    note_health("서울 상권 추정매출", "; ".join(bad) if bad else None)
    if not got:
        print("[서울 상권] 새 분기 없음"); return
    out = {"asOf": now.strftime("%Y-%m-%d %H:%M KST"),
           "cols": ["매출(억원)", "건수", "관광특구 매출(억원)", "여성 매출(억원)", "20대 매출(억원)"],
           "q": dict(sorted(have.items())),
           "note": "서울시 상권분석서비스(추정매출-상권) OA-15572 · 서울신용보증재단 · 카드사 매출 기반 추정 · 서울 상권 안 가게만 · 분기"}
    block = "const SEOULSALES = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";"
    if m:
        html = html[:m.start()] + block + html[m.end():]
    else:
        a = re.search(r"^const TREND = ", html, re.M)
        html = html[:a.start()] + block + "\n" + html[a.start():]
    open(HTML, "w", encoding="utf-8").write(html)
    print(f"[서울 상권] 블록 갱신 {len(block) // 1024}KB · 분기 {len(have)}")


if __name__ == "__main__":
    main()
