"""종목별 손익 모델(ISM)의 국내 부문 지표 — 네이버 데이터랩 월별 검색량 -> index.html 의  const ISMSRCH = {...};   (2026-10-25)

트렌드 탭(TREND)은 일별 90일·주별 52주라 분기 계수를 맞추기엔 짧다. 데이터랩은 2016년부터 월별을 주므로
2023-01 부터 받아 국내 부문(시술·화장품·완구)의 분기 매출과 견준다 — 검색어마다 따로 요청한다(각자 자기 최고 = 100).
화면 엔진(ism.js ISM_PX.srch)이 분기 합으로 쓴다. 쓸지 말지는 실전 검산(ismBacktest)으로 정했다(설계 ism_spec.js 에 적힌 것만 쓴다).
⚠ 검색은 '관심'이다 — 해외 매출·B2B 매출엔 쓰지 말 것. 새 최고가 나오면 전 구간이 다시 매겨진다(엔진이 계수를 매번 다시 맞추므로 괜찮다).

python fetch_ismsrch.py
"""
import datetime, json, os, re, sys, time

from collector_health import note_health

try:
    from secrets_local import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
except ImportError:
    NAVER_CLIENT_ID = NAVER_CLIENT_SECRET = ""
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", NAVER_CLIENT_ID)
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", NAVER_CLIENT_SECRET)

KST = datetime.timezone(datetime.timedelta(hours=9))
HTML = "public/index.html"
START = "2023-01-01"
# 키 = 화면에서 부를 이름 · 값 = 같은 그룹으로 묶을 검색어(데이터랩 keywords — 합쳐서 하나의 계열)
KW = {
    "리투오": ["리투오"],
    "리쥬란": ["리쥬란", "리쥬란힐러"],
    "리쥬란 화장품": ["리쥬란크림", "리쥬란 크림", "리쥬란앰플", "리쥬란 화장품"],
    "콘쥬란": ["콘쥬란"],
    "메디큐브": ["메디큐브", "에이지알"],
    "롬앤": ["롬앤"],
    "클리오": ["클리오", "페리페라", "구달"],
    "마녀공장": ["마녀공장"],
    "토니모리": ["토니모리"],
    "네오팜": ["아토팜", "제로이드", "리얼베리어"],
    "리들샷": ["리들샷", "VT코스메틱"],
    "아로마티카": ["아로마티카"],
    "TS샴푸": ["TS샴푸", "티에스샴푸"],
    "달바": ["달바", "달바 미스트"],
    "티니핑": ["티니핑"],
    "센텔리안24": ["센텔리안24", "마데카크림"],
    "에스트라": ["에스트라", "아토베리어"],
    "설화수": ["설화수"],
    "후": ["더후", "후 화장품"],
}


def month_list(a, b):
    y, m = int(a[:4]), int(a[5:7])
    out = []
    while f"{y}-{m:02d}" <= b:
        out.append(f"{y}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def fetch(words, end):
    import requests
    body = {"startDate": START, "endDate": end, "timeUnit": "month",
            "keywordGroups": [{"groupName": words[0], "keywords": words}]}
    r = requests.post("https://openapi.naver.com/v1/datalab/search",
                      headers={"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
                               "Content-Type": "application/json"}, data=json.dumps(body), timeout=20)
    r.raise_for_status()
    return {d["period"][:7]: d["ratio"] for d in r.json()["results"][0]["data"]}


def main():
    if not (NAVER_CLIENT_ID and NAVER_CLIENT_SECRET):
        note_health("검색 월별(ISM)", "네이버 키 없음"); print("네이버 키 없음"); sys.exit(1)
    now = datetime.datetime.now(KST).date()
    last = (now.replace(day=1) - datetime.timedelta(days=1))                 # 지난달 말 = 마지막 완결 달
    end = last.strftime("%Y-%m-%d")
    months = month_list(START[:7], end[:7])
    html = open(HTML, encoding="utf-8").read()
    mm = re.search(r"^const ISMSRCH = (\{.*?\});$", html, re.M | re.S)
    old = json.loads(mm.group(1)) if mm else {"s": {}}
    s, bad = {}, []
    for k, words in KW.items():
        try:
            d = fetch(words, end)
            s[k] = {"w": words, "v": [round(d.get(m, 0), 2) for m in months]}
            print(f"[검색] {k:10} 마지막 {months[-1]} {s[k]['v'][-1]} · 최고 {max(s[k]['v'])}")
        except Exception as e:
            bad.append(f"{k} {str(e)[:40]}")
            if k in (old.get("s") or {}) and old.get("months") == months:
                s[k] = old["s"][k]
        time.sleep(0.4)
    note_health("검색 월별(ISM)", "; ".join(bad[:3]) if len(bad) > 3 else None)
    if mm and old.get("s") == s and old.get("months") == months:
        print("[검색] 변동 없음"); return
    out = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "months": months, "s": s,
           "note": "네이버 데이터랩 월별 검색량(검색어 묶음마다 따로 · 자기 최고 = 100) — 손익 모델 국내 부문 지표"}
    block = "const ISMSRCH = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";"
    if mm:
        html = html[:mm.start()] + block + html[mm.end():]
    else:
        a = re.search(r"^const TREND = ", html, re.M)
        html = html[:a.start()] + block + "\n" + html[a.start():]
    open(HTML, "w", encoding="utf-8").write(html)
    print(f"[검색] ISMSRCH 블록 갱신 {len(block) // 1024}KB")


if __name__ == "__main__":
    main()
