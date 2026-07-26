# -*- coding: utf-8 -*-
"""
쇼핑몰 수요 지표 수집 -> index.html 의  const SHOP = {...};

검색 트렌드가 '관심'이라면 이쪽은 '실제로 팔리고 있나'에 가깝다.
리뷰 수는 구매자만 남기므로, 주간 증가분이 판매 대리지표가 된다.

  러시아 — 와일드베리즈 (인증 불필요)
  일본  — 라쿠텐 이치바   (RAKUTEN_APP_ID + RAKUTEN_ACCESS_KEY)

중요: 두 API 모두 '현재 스냅샷'만 준다. 과거 시계열을 주지 않는다.
그래서 실행할 때마다 한 점씩 찍어 SHOP.series 에 누적한다.
기존 값을 읽어 이어붙이므로 이 블록을 지우면 과거가 사라진다.

생산지가 어디든 '그 나라에서 팔린 것'만 잡히므로,
중국에서 만들어 러시아로 직접 나가는 물량도 러시아 쪽에 반영된다.
"""
import urllib.request, urllib.parse, json, re, sys, os, datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML_PATH = "public/index.html"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}

RAKUTEN_APP_ID     = os.environ.get("RAKUTEN_APP_ID", "")
RAKUTEN_ACCESS_KEY = os.environ.get("RAKUTEN_ACCESS_KEY", "")

WB_URL = "https://search.wb.ru/exactmatch/ru/common/v4/search"
RK_URL = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"

# 추적 대상 — 종목별로 그 나라에서 쓰는 현지 표기를 넣는다.
# 검색어가 틀리면 0 이 찍히므로 트렌드 때와 같은 원칙: 현지 정식명을 쓴다.
TARGETS = [
    {"stock": "SAMG엔터",   "label": "메탈카드봇",
     "wb": "Метал Кард Бот", "rk": "メタルカードボット"},
    {"stock": "SAMG엔터",   "label": "티니핑",
     "wb": "Тинипин",        "rk": "ティニピン"},
    {"stock": "에이피알",   "label": "메디큐브",  "rk": "メディキューブ"},
    {"stock": "달바글로벌", "label": "달바",      "rk": "d'Alba"},
    {"stock": "파마리서치", "label": "리쥬란",    "rk": "リジュラン"},
]


def getj(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8"))


def fetch_wb(query):
    """와일드베리즈 — 상품 수 · 리뷰 합계 · 평균 평점.
       dest 는 배송지 코드(모스크바). 없으면 빈 결과가 오는 경우가 있다."""
    q = urllib.parse.quote(query)
    d = getj(f"{WB_URL}?query={q}&resultset=catalog&limit=100&dest=-1257786")
    items = ((d.get("data") or {}).get("products")
             or (d.get("products") if isinstance(d.get("products"), list) else []) or [])
    if not items:
        return None
    revs = [int(p.get("nmFeedbacks") or p.get("feedbacks") or 0) for p in items]
    rats = [float(p.get("reviewRating") or p.get("rating") or 0) for p in items]
    rats = [r for r in rats if r > 0]
    return {"n": len(items), "rev": sum(revs),
            "rating": round(sum(rats) / len(rats), 2) if rats else None}


def fetch_rakuten(query):
    """라쿠텐 이치바 — 상품 수 · 리뷰 합계 · 평균 평점.
       Referer 를 앱 등록 도메인으로 맞춘다(Allowed websites 검사 대비)."""
    if not (RAKUTEN_APP_ID and RAKUTEN_ACCESS_KEY):
        return None
    p = urllib.parse.urlencode({
        "applicationId": RAKUTEN_APP_ID, "accessKey": RAKUTEN_ACCESS_KEY,
        "keyword": query, "hits": 30, "sort": "-reviewCount"})
    req = urllib.request.Request(f"{RK_URL}?{p}",
                                 headers={**UA, "Referer": "https://coverage-dashboard.pages.dev/"})
    d = json.loads(urllib.request.urlopen(req, timeout=25).read().decode("utf-8"))
    items = [x.get("Item", x) for x in (d.get("Items") or [])]
    if not items:
        return None
    revs = [int(x.get("reviewCount") or 0) for x in items]
    rats = [float(x.get("reviewAverage") or 0) for x in items]
    rats = [r for r in rats if r > 0]
    return {"n": len(items), "rev": sum(revs),
            "rating": round(sum(rats) / len(rats), 2) if rats else None}


def main():
    html = open(HTML_PATH, encoding="utf-8").read()

    # 기존 SHOP 을 읽어 시계열을 이어붙인다 — 이 API 들은 과거를 안 주므로 지우면 복구 불가
    old = {}
    m = re.search(r"const SHOP = (\{.*?\});\n", html, re.S)
    if m:
        try:
            old = json.loads(m.group(1))
        except json.JSONDecodeError:
            old = {}
    series = dict(old.get("series") or {})

    kst = datetime.timezone(datetime.timedelta(hours=9))
    today = datetime.datetime.now(kst).strftime("%Y-%m-%d")
    meta, ok, fail = [], 0, []

    for t in TARGETS:
        meta.append({k: t[k] for k in ("stock", "label") if k in t})
        for src, key, fn in (("wb", "wb", fetch_wb), ("rk", "rk", fetch_rakuten)):
            if not t.get(key):
                continue
            sid = f"{t['label']}|{src}"
            try:
                r = fn(t[key])
            except Exception as e:
                fail.append(f"{sid}({type(e).__name__})"); continue
            if not r:
                fail.append(f"{sid}(빈결과)"); continue
            pts = [p for p in (series.get(sid) or []) if p.get("d") != today]  # 같은 날 재실행 시 덮어씀
            pts.append({"d": today, **r})
            series[sid] = pts[-120:]                                          # 최대 120점 보관
            ok += 1
            print(f"  {sid:<22} 상품 {r['n']:>3} · 리뷰 {r['rev']:>7} · 평점 {r['rating']}")

    if not ok:
        print("수집 0건 - index.html 그대로 둠"); return

    shop = {"asOf": today, "targets": TARGETS, "series": series}
    block = "const SHOP = " + json.dumps(shop, ensure_ascii=False) + ";\n"
    if m:
        html = html[:m.start()] + block + html[m.end():]
    else:
        # 최초 1회 — TREND 상수 앞에 끼워 넣는다
        anchor = re.search(r"^const TREND=", html, re.M)
        if not anchor:
            print("삽입 위치를 찾지 못했습니다(const TREND=)"); sys.exit(1)
        html = html[:anchor.start()] + block + html[anchor.start():]
    open(HTML_PATH, "w", encoding="utf-8").write(html)
    print(f"\n[OK] {ok}건 기록 ({today})" + (f" · 실패 {len(fail)}: {', '.join(fail)}" if fail else ""))


if __name__ == "__main__":
    main()
