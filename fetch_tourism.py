# -*- coding: utf-8 -*-
"""
방한 외래관광객 월별 수집 — 호텔/면세/카지노 수요 신호(호텔신라·파라다이스·GKL·롯데관광개발 등).

한국관광공사 data.go.kr API 는 폐기됐고, 데이터랩은 공식 공개 API 가 없다. 대신 데이터랩
내부 시각화 엔드포인트가 키 없이 깨끗한 최신 JSON 을 준다(치지직과 같은 성격 — 비공식이라
구조가 바뀌면 조용히 멈출 수 있음. 실패 시 기존 데이터 보존).

  POST /visualize/getTempleteData.do  ·  BASE_YM1~BASE_YM2 기간
  · NAT_08_01_004    '방한 외래관광객 추이' — list[].PSON_NUM = 그 달 공식 총계(한국관광통계 · 2015-01~)
  · TS_01_16_004_NEW 입국 공항·항구별 — TOU_NUM1~13(인천공항·김해·김포·제주공항·기타공항 5개·부산항·인천항·제주항·기타항구)
  · NAT_08_01_021    '글로벌 방한관광객' — 기간 합 국적별(총계 줄 + 국적 205개 · 전년 같은 기간 대비 PER) → 한 달씩 부른다

⚠ 2026-10-29 전엔 TS_01_16_004_NEW 의 TOU_NUM1 을 '총계'로 읽었다 — 실제로는 **인천공항 입국분만**(총계의 61%)이었다.
  13칸을 다 더하면 공식 총계와 한 명까지 맞는다(2026-09 2,062,042). 그래서 total = 공식 총계, ports.icn = 옛 값.

  python fetch_tourism.py              # 수집·기록(국적은 빠진 달 + 최근 3개월)
  python fetch_tourism.py --backfill   # 국적을 START 부터 전부 다시
  python fetch_tourism.py --dry-run    # 출력만
"""
import re, json, sys, time, datetime, urllib.request, urllib.parse

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
URL = "https://datalab.visitkorea.or.kr/visualize/getTempleteData.do"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
START = "201901"                  # 2019 대비를 보려고 코로나 전부터
# 입국 공항·항구 — TS_01_16_004_NEW 의 TOU_NUM 번호(2026-09 NAT_08_01_007 공항·항구별 값으로 맞춰 봤다)
PORTS = [("icn", "인천공항", [1]), ("pus", "김해공항", [2]), ("gmp", "김포공항", [3]), ("cju", "제주공항", [4]),
         ("air", "기타공항", [5, 6, 7, 8, 9]), ("bsp", "부산항", [10]), ("icp", "인천항", [11]),
         ("cjp", "제주항", [12]), ("sea", "기타항구", [13])]
# 국적 — 2025-10~2026-09 방한객 상위 12개(나머지는 그 밖 = 총계 − 12개). 코드는 데이터랩 PTL_NAT_CD.
NATS = ["CN", "JP", "TW", "US", "HK", "PH", "VN", "SG", "ID", "TH", "MY", "CA"]


def _q(qid, a, b, **extra):
    p = {"qid": qid, "BASE_YM1": a, "BASE_YM2": b,
         "srchBgngYear": a[:4], "srchEndYear": b[:4], "srchBgngMm": a[4:], "srchEndMm": b[4:],
         "srchAreaDate": "1", "adminYn": "", "NAT_CD": ""}
    p.update(extra)
    req = urllib.request.Request(URL, data=urllib.parse.urlencode(p).encode(), headers={
        "User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8")).get("list") or []


def _now_ym():
    d = datetime.datetime.now(KST).date()
    return f"{d.year}{d.month:02d}"


def _months(a, b):
    out, y, m = [], int(a[:4]), int(a[4:])
    while f"{y}{m:02d}" <= b:
        out.append(f"{y}{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def _const(html, name):
    m = re.search(r"const %s\s*=\s*(\{.*?\});" % re.escape(name), html, re.S)
    return json.loads(m.group(1)) if m else None


def _put(html, name, obj):
    block = "const %s = %s;" % (name, json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
    pat = re.compile(r"const %s\s*=\s*\{.*?\};" % re.escape(name), re.S)
    if pat.search(html):
        return pat.sub(lambda m: block, html, count=1)
    liv = re.search(r"const LIVE\s*=\s*\{.*?\};", html, re.S)
    if not liv:
        raise RuntimeError("TOURISM 삽입 기준(const LIVE)을 못 찾음")
    return html[:liv.end()] + "\n" + block + html[liv.end():]


def main():
    html = open(HTML, encoding="utf-8").read()
    old = _const(html, "TOURISM") or {}
    end = _now_ym()
    try:
        rows = [x for x in _q("NAT_08_01_004", START, end) if x.get("PSON_NUM")]
        prow = [x for x in _q("TS_01_16_004_NEW", START, end) if x.get("TOU_NUM1")]
    except Exception as e:
        print(f"[관광] 실패: {str(e)[:120]} — 기존 데이터 보존"); return
    if not rows:
        print("[관광] 빈 응답 — 보존"); return
    rows.sort(key=lambda x: x["BASE_DATE"])
    months = [x["BASE_DATE"] for x in rows]
    total = [int(x["PSON_NUM"]) for x in rows]

    pby = {x["BASE_YM"]: x for x in prow}
    ports = {"keys": [k for k, _, _ in PORTS], "names": [n for _, n, _ in PORTS],
             "v": [[(sum(int(pby[m].get(f"TOU_NUM{i}") or 0) for i in ix) if m in pby else None) for m in months]
                   for _, _, ix in PORTS]}
    for m, t in zip(months, total):          # 13칸 합 = 공식 총계인지 검산(어긋나면 칸 번호가 바뀐 것)
        if m in pby:
            s = sum(int(pby[m].get(f"TOU_NUM{i}") or 0) for i in range(1, 14))
            if abs(s - t) > 2:
                print(f"  ⚠ {m} 공항·항구 합 {s:,} ≠ 총계 {t:,} — 칸 번호 확인")

    # 국적 — 이미 있는 달은 옮기고, 빠진 달 + 최근 3개월만 새로(수정 공표 반영) · --backfill 은 전부
    on = old.get("nat") or {}
    have = {m: {c: on["v"][c][i] for c in on.get("v", {})} for i, m in enumerate(on.get("months", []))
            if on.get("v")}
    names = dict(on.get("names") or {})
    need = months if "--backfill" in sys.argv else [m for m in months if m not in have or m in months[-3:]]
    for m in need:
        try:
            L = _q("NAT_08_01_021", m, m)
        except Exception as e:
            print(f"  국적 {m} 실패: {str(e)[:80]} — 그 달은 이전 값"); continue
        if not L:
            continue
        row = {}
        for x in L:
            c = x.get("PTL_NAT_CD") or ""
            if c in NATS:
                row[c] = int(x.get("TOU_NUM") or 0)
                names[c] = x.get("NAT_NM")
        have[m] = row
        time.sleep(0.4)
    nm = [m for m in months if m in have]
    nat = {"months": nm, "names": {c: names.get(c, c) for c in NATS},
           "v": {c: [have[m].get(c) for m in nm] for c in NATS}}

    tourism = {"asOf": old.get("asOf"), "src": "한국관광 데이터랩 · 한국관광통계(법무부 출입국)",
               "months": months, "total": total, "ports": ports, "nat": nat}
    for m, t in zip(months[-3:], total[-3:]):
        print(f"  {m[:4]}.{m[4:]}: {t:,}명")
    lm = months[-1]
    top = sorted(((nat["names"][c], have.get(lm, {}).get(c) or 0) for c in NATS), key=lambda x: -x[1])[:5]
    print("  " + lm + " 국적 상위: " + " · ".join(f"{n} {v:,}" for n, v in top))

    if "--dry-run" in sys.argv:
        print(f"(dry-run · {len(months)}개월 · 최근 {lm} · 국적 {len(nm)}개월)"); return
    same = {k: v for k, v in tourism.items() if k != "asOf"} == {k: v for k, v in old.items() if k != "asOf"}
    if same:
        print("[관광] 변동 없음 — SKIP"); return
    tourism["asOf"] = datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    open(HTML, "w", encoding="utf-8").write(_put(html, "TOURISM", tourism))
    print(f"[OK] TOURISM 갱신 · {len(months)}개월 · 국적 {len(nm)}개월")


if __name__ == "__main__":
    main()
