# -*- coding: utf-8 -*-
"""
치지직(CHZZK, 네이버) 게임별 시청자 수집 — 트위치가 한국을 떠난 뒤 국내 게임 시청의 메인 신호.

공식 개발자 API 는 없지만, 서비스 라이브 목록 엔드포인트가 키 없이 JSON 을 준다.
  https://api.chzzk.naver.com/service/v1/lives?sortType=POPULAR  (인기순, 커서 페이지네이션)
인기 라이브를 넉넉히 훑어 liveCategoryValue(게임명)별 concurrentUserCount 를 합산한다.
상위 방송이 시청자의 대부분이라 상위 N 합산이면 게임별 총시청과 거의 같다.

과거 시계열 무료 소스가 없어 '매일(가능하면 여러 번) 한 점씩' 쌓는다. 같은 날 재실행은
그날의 '최댓값(daily peak)'으로 갱신 → 저녁 피크가 잡히면 그 값이 남는다.
치지직이 막히면 기존 시계열을 보존하고 그날만 건너뛴다(fetch_trends 철학과 동일).

  python fetch_chzzk.py            # 수집·기록
  python fetch_chzzk.py --dry-run  # 출력만
"""
import re, json, sys, datetime, urllib.request

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
DAYS = 180
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
PAGES = 8          # 인기 라이브 페이지 수(page=50) — 상위 400개면 게임별 총시청 대부분 포착

# (종목, 표시명, 카테고리 매칭 키워드) — 치지직 카테고리명에 이 키워드가 들면 그 게임으로 합산
GAMES = [
    ("펄어비스", "붉은사막",       ["붉은사막"]),
    ("펄어비스", "검은사막",       ["검은사막"]),
    ("크래프톤", "배틀그라운드",   ["배틀그라운드", "PUBG"]),
    ("시프트업", "스텔라블레이드", ["스텔라블레이드"]),
    ("시프트업", "니케",           ["니케"]),
    ("NC",       "아이온2",        ["아이온2"]),
]


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def _agg_viewers():
    """치지직 인기 라이브를 커서로 넘기며 카테고리별 시청자 합산. {카테고리: 시청자합}."""
    agg = {}
    url = "https://api.chzzk.naver.com/service/v1/lives?size=50&sortType=POPULAR"
    for _ in range(PAGES):
        c = (_get(url).get("content") or {})
        ls = c.get("data") or []
        for x in ls:
            cat = x.get("liveCategoryValue") or ""
            if cat:
                agg[cat] = agg.get(cat, 0) + (x.get("concurrentUserCount") or 0)
        nxt = (c.get("page") or {}).get("next")
        if not ls or not nxt:
            break
        url = ("https://api.chzzk.naver.com/service/v1/lives?size=50&sortType=POPULAR"
               f"&concurrentUserCount={nxt.get('concurrentUserCount')}&liveId={nxt.get('liveId')}")
    return agg


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
        raise RuntimeError("CHZZK 삽입 기준(const LIVE)을 못 찾음")
    return html[:liv.end()] + "\n" + block + html[liv.end():]


def _merge_day(hist, today, v):
    """같은 날 여러 번 찍은 표본을 한 점으로. v=그날 최댓값, h=최댓값이 찍힌 KST 시각, n=표본 수, a=표본 평균.
    시청자는 '언제 찍었나'가 값만큼 중요하다(저녁 피크 vs 낮). 예전엔 최댓값만 남겨 그게 21시 값인지
    11시 값인지 알 수 없었다(2026-09-04). 저녁 표본은 viewers.yml(KST 21·22·23시)이 추가로 찍는다."""
    hour = datetime.datetime.now(KST).hour
    if hist and hist[-1].get("d") == today:
        e = hist[-1]; n = int(e.get("n") or 1); s = float(e.get("s") if e.get("s") is not None else e.get("v", 0)) + v
        peak = v > (e.get("v") or 0)
        hist[-1] = {"d": today, "v": max(e.get("v") or 0, v), "h": hour if peak else e.get("h", hour),
                    "n": n + 1, "s": round(s), "a": round(s / (n + 1))}
    else:
        hist.append({"d": today, "v": v, "h": hour, "n": 1, "s": v, "a": v})
    return hist


def main():
    html = open(HTML, encoding="utf-8").read()
    today = datetime.datetime.now(KST).date().isoformat()
    prev = {(g["stock"], g["title"]): g.get("hist", [])
            for g in (_const(html, "CHZZK") or {}).get("games", [])}

    try:
        agg = _agg_viewers()
    except Exception as e:
        print(f"[치지직 실패] {str(e)[:100]} — 기존 시계열 보존, 오늘 건너뜀")
        return

    games = []
    for stock, title, keys in GAMES:
        v = sum(val for cat, val in agg.items() if any(k in cat for k in keys))
        hist = list(prev.get((stock, title), []))
        hist = _merge_day(hist, today, v)
        hist = hist[-DAYS:]
        games.append({"stock": stock, "title": title, "hist": hist})
        print(f"  {title}: 시청자 {v:,}")

    chzzk = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "games": games}
    if "--dry-run" in sys.argv:
        print(json.dumps(chzzk, ensure_ascii=False, indent=1)[:600]); return
    open(HTML, "w", encoding="utf-8").write(_put(html, "CHZZK", chzzk))
    print(f"[OK] CHZZK 갱신 · {len(games)}종")


if __name__ == "__main__":
    main()
