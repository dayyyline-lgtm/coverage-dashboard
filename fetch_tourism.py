# -*- coding: utf-8 -*-
"""
방한 외래관광객 월별 수집 — 호텔/면세/카지노 수요 신호(호텔신라·파라다이스·GKL·롯데관광개발 등).

한국관광공사 data.go.kr API 는 폐기됐고, 데이터랩은 공식 공개 API 가 없다. 대신 데이터랩
내부 시각화 엔드포인트가 키 없이 깨끗한 최신 JSON 을 준다(치지직과 같은 성격 — 비공식이라
구조가 바뀌면 조용히 멈출 수 있음. 실패 시 기존 데이터 보존).

  POST /visualize/getTempleteData.do  ·  qid=TS_01_16_004_NEW  ·  BASE_YM1~BASE_YM2 기간
  응답 list[].TOU_NUM1 = 그 달 방한 외래관광객 총계. 호출마다 전 기간을 주므로 전체 갱신.

  python fetch_tourism.py            # 수집·기록
  python fetch_tourism.py --dry-run  # 출력만
"""
import re, json, sys, datetime, urllib.request, urllib.parse

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
URL = "https://datalab.visitkorea.or.kr/visualize/getTempleteData.do"
QID = "TS_01_16_004_NEW"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
MONTHS = 24                       # 최근 N개월


def _fetch():
    now = datetime.datetime.now(KST).date().replace(day=1)
    idx = now.year * 12 + (now.month - 1)
    s = idx - MONTHS
    sy, sm = s // 12, s % 12 + 1
    body = urllib.parse.urlencode({
        "qid": QID,
        "BASE_YM1": f"{sy}{sm:02d}", "BASE_YM2": f"{now.year}{now.month:02d}",
        "srchBgngYear": str(sy), "srchEndYear": str(now.year),
        "srchBgngMm": f"{sm:02d}", "srchEndMm": f"{now.month:02d}",
        "srchAreaDate": "1", "adminYn": "",
    }).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
    with urllib.request.urlopen(req, timeout=25) as r:
        d = json.loads(r.read().decode("utf-8"))
    rows = [x for x in (d.get("list") or []) if x.get("TOU_NUM1")]
    rows.sort(key=lambda x: x.get("BASE_YM", ""))
    return rows


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
    try:
        rows = _fetch()
    except Exception as e:
        print(f"[관광] 실패: {str(e)[:120]} — 기존 데이터 보존"); return
    if not rows:
        print("[관광] 빈 응답 — 보존"); return

    months = [x["BASE_YM"] for x in rows]
    total = [int(x["TOU_NUM1"]) for x in rows]
    tourism = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
               "months": months, "total": total}
    for m, t in zip(months[-3:], total[-3:]):
        print(f"  {m[:4]}.{m[4:]}: {t:,}명")

    if "--dry-run" in sys.argv:
        print(f"(dry-run · {len(months)}개월 · 최근 {months[-1]})"); return
    open(HTML, "w", encoding="utf-8").write(_put(html, "TOURISM", tourism))
    print(f"[OK] TOURISM 갱신 · {len(months)}개월")


if __name__ == "__main__":
    main()
