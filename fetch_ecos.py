"""한국은행 ECOS 소매업태별 판매액지수(901Y098 · 경상지수 · 2020=100) -> index.html 의  const ECOS = {...};   (2026-10-24 · ISM)

유통 종목(신세계·롯데쇼핑·현대백화점·BGF리테일·GS리테일)·면세(호텔신라·신세계·현대)의 분기 매출 동인.
2026-10-24 조사: 백화점 총매출 ÷ 백화점 지수 CV 1.9~4.0% · 전년비 상관 0.98~0.99 · 편의점 ÷ 편의점 지수 CV 0.9~2.2%.
면세는 지수로 안 맞는다(점포 개폐가 지배 — 신세계 CV 13%) — 방향 참고만.
키 없이 'sample' 키로 요청당 10행 → 업태마다 10개월씩 끊어 받는다(익월 말 공표).

+ 소비자물가지수(901Y009 · 2020=100) 숙박 품목 — 호텔숙박료(K02101 · 1975~) · 여관숙박료 · 콘도이용료 · 숙박 서비스(2026-10-29 · 호텔 ADR 추적).
  호텔 3종목 손익 탭 '호텔 ADR 추적'의 '전국 호텔 물가' 줄·차트. 2010-01 부터 싣고, 이미 있으면 마지막 달 6개월 앞부터만 다시 받아 붙인다(요청 수 절약).

python fetch_ecos.py
"""
import datetime, json, re, time, urllib.request

from collector_health import note_health

KST = datetime.timezone(datetime.timedelta(hours=9))
HTML = "public/index.html"
START = "202301"
ITEMS = {"I74B": "백화점", "I74C": "대형마트", "I74F": "면세점", "I74I": "슈퍼마켓·잡화점", "I74IA": "체인 슈퍼마켓",
         "I74J": "편의점", "I74R": "가전·통신기기", "I74VA": "인터넷 쇼핑", "I74VB": "홈쇼핑"}
START_CPI = "201001"
CPI = {"K02101": "호텔숙박료", "K02102": "여관숙박료", "K02103": "콘도이용료", "K021": "숙박 서비스"}


def months(a, b):
    y, m = int(a[:4]), int(a[4:])
    out = []
    while f"{y}{m:02d}" <= b:
        out.append(f"{y}{m:02d}")
        m += 1
        if m > 12:
            y += 1; m = 1
    return out


def series(code, ms, tbl="901Y098/M/{a}/{b}/{code}/I74A"):
    out = {}
    for i in range(0, len(ms), 10):
        a, b = ms[i], ms[min(i + 9, len(ms) - 1)]
        u = "https://ecos.bok.or.kr/api/StatisticSearch/sample/json/kr/1/10/" + tbl.format(a=a, b=b, code=code)
        d = json.loads(urllib.request.urlopen(u, timeout=30).read().decode())
        for r in (d.get("StatisticSearch") or {}).get("row", []):
            try:
                out[f"{r['TIME'][:4]}-{r['TIME'][4:]}"] = float(r["DATA_VALUE"])
            except (TypeError, ValueError):
                pass
        time.sleep(0.4)
    return out


def main():
    now = datetime.datetime.now(KST)
    ms = months(START, now.strftime("%Y%m"))
    html = open(HTML, encoding="utf-8").read()
    m = re.search(r"^const ECOS = (\{.*?\});$", html, re.M | re.S)
    old = json.loads(m.group(1)) if m else {}
    s, bad = {}, []
    for code, nm in ITEMS.items():
        try:
            v = series(code, ms)
        except Exception as e:
            bad.append(f"{nm} {type(e).__name__}"); v = (old.get("s") or {}).get(code, {}).get("v", {})
        if v:
            s[code] = {"nm": nm, "v": dict(sorted(v.items()))}
            print(f"[ECOS] {nm:10} {len(v)}개월 · 마지막 {max(v)} {v[max(v)]}")
    # 소비자물가 숙박 품목 — 있으면 마지막 달 6개월 앞부터만 다시 받아 옛 값 위에 붙인다
    for code, nm in CPI.items():
        ov = (old.get("s") or {}).get(code, {}).get("v", {})
        st = START_CPI
        if len(ov) >= 24:
            ly, lm = int(max(ov)[:4]), int(max(ov)[5:]) - 6
            while lm < 1:
                lm += 12; ly -= 1
            st = f"{ly}{lm:02d}"
        try:
            v = dict(ov); v.update(series(code, months(st, now.strftime("%Y%m")), "901Y009/M/{a}/{b}/{code}"))
        except Exception as e:
            bad.append(f"{nm} {type(e).__name__}"); v = ov
        if v:
            s[code] = {"nm": nm, "v": dict(sorted(v.items())), "t": "cpi"}
            print(f"[ECOS] {nm:10} {len(v)}개월 · 마지막 {max(v)} {v[max(v)]}")
    note_health("ECOS 소매판매", "; ".join(bad) if len(bad) > 2 else None)
    if m and old.get("s") == s:
        print("[ECOS] 변동 없음"); return
    out = {"asOf": now.strftime("%Y-%m-%d %H:%M KST"), "s": s,
           "note": "한국은행 ECOS 901Y098 소매업태별 판매액지수 · 경상지수(2020=100) · 월 · 익월 말 공표 / 901Y009 소비자물가 숙박 품목(2020=100 · t=cpi) · 익월 초 공표"}
    block = "const ECOS = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";"
    if m:
        html = html[:m.start()] + block + html[m.end():]
    else:
        a = re.search(r"^const TREND = ", html, re.M)
        html = html[:a.start()] + block + "\n" + html[a.start():]
    open(HTML, "w", encoding="utf-8").write(html)
    print(f"[ECOS] 블록 갱신 {len(block) // 1024}KB")


if __name__ == "__main__":
    main()
