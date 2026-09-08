# -*- coding: utf-8 -*-
"""
SOOP(아프리카TV) 게임별 시청자 수집 — 국내 스트리밍 3대 플랫폼의 마지막 한 조각 (2026-09-08 신설).

치지직·트위치는 이미 받고 있었는데 **SOOP 이 빠져 있었다.** 국내에서는 SOOP 이 여전히
치지직과 양강이라, 빼 놓으면 '국내 시청'이라고 부르면서 절반만 보고 있는 셈이었다.

카테고리 목록 API 가 키·로그인 없이 열린다:

```
sch.sooplive.co.kr/api.php?m=categoryList&szKeyword=&nPageNo=N   20개씩 · is_more 로 페이징
```

**치지직보다 이쪽이 구조적으로 낫다.** 치지직은 인기 라이브 상위 400개를 훑어 카테고리별로
합산하는 방식이라 작은 게임이 잘리는데(상위 밖 방송은 안 세어진다), SOOP 은 카테고리 자체가
`view_cnt` 를 들고 있어 **그 카테고리 전체**가 잡힌다. 13요청이면 240개 카테고리 전부다.

실측(2026-09-08 오후): PUBG 5,484 · 아이온 2 360 · 리니지 클래식 180 · **제우스: 오만의 신 178** ·
리니지 47 · 서머너즈 워 19. 컴투스 신작 둘이 여기서 잡힌다 — 치지직 목록엔 없던 것이라 같이 넣었다.

⚠ 카테고리명 띄어쓰기가 플랫폼마다 다르다 — SOOP 은 "아이온 2"(공백), 치지직은 "아이온2".
  그래서 매칭 전에 **공백을 지우고 비교한다.** 안 그러면 조용히 0 이 찍힌다.

⚠ 세 플랫폼의 절대값을 더하지 말 것. 집계 방식이 다르다(SOOP=카테고리 전체, 치지직=상위 400 합산,
  트위치=글로벌). 같은 게임의 **추이**를 나란히 보는 용도다.

과거 시계열 무료 소스가 없어 '매일 여러 번 한 점씩' 쌓는다. 같은 날 재실행은 그날 최댓값으로
갱신하고, 언제 찍힌 값인지(`h`)·표본 수(`n`)·표본 평균(`a`)을 같이 남긴다 —
저녁 피크(21시)와 낮(11시)은 다른 숫자다(치지직·트위치와 동일한 규칙).

  python fetch_soop.py            # 수집·기록
  python fetch_soop.py --dry-run  # 출력만
"""
import re, json, sys, datetime, urllib.request
from collector_health import ua, nap, note_health

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
DAYS = 180
PAGES = 15          # 20개씩 · 실측 240개(13페이지)라 여유를 둔다
API = "https://sch.sooplive.co.kr/api.php?m=categoryList&szKeyword=&nPageNo=%d"

# (종목, 표시명, 카테고리 매칭 키워드) — 비교 대상은 fetch_chzzk.py 의 GAMES 다.
# 키워드는 **공백을 지운 상태**로 비교한다("아이온 2" → "아이온2").
GAMES = [
    ("펄어비스", "붉은사막",       ["붉은사막"]),
    ("펄어비스", "검은사막",       ["검은사막"]),
    ("크래프톤", "배틀그라운드",   ["배틀그라운드", "PUBG"]),
    ("시프트업", "스텔라블레이드", ["스텔라블레이드"]),
    ("시프트업", "니케",           ["니케"]),
    ("NC",       "아이온2",        ["아이온2"]),
    ("NC",       "리니지클래식",   ["리니지클래식"]),
    ("컴투스",   "제우스",         ["제우스:오만의신", "제우스오만"]),
    ("컴투스",   "서머너즈워",     ["서머너즈워"]),
]
UA = ua(referer="https://www.sooplive.co.kr/")


def _norm(s):
    return re.sub(r"\s+", "", s or "")


def _get(url):
    req = urllib.request.Request(url, headers=dict(UA))
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _categories():
    """{카테고리명: 시청자수}. is_more 가 꺼질 때까지 넘긴다."""
    out = {}
    for p in range(1, PAGES + 1):
        d = (_get(API % p).get("data") or {})
        lst = d.get("list") or []
        for c in lst:
            nm = c.get("category_name") or ""
            if nm:
                out[nm] = out.get(nm, 0) + int(c.get("view_cnt") or 0)
        if not lst or not d.get("is_more"):
            break
        nap(0.25)
    if len(out) < 30:
        raise RuntimeError(f"카테고리 {len(out)}개뿐(구조 변경?)")
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
        raise RuntimeError("SOOP 삽입 기준(const LIVE)을 못 찾음")
    return html[:liv.end()] + "\n" + block + html[liv.end():]


def _merge_day(hist, today, v):
    """같은 날 여러 번 찍은 표본을 한 점으로 — 치지직·트위치와 **같은 규칙**이어야 나란히 읽힌다.
    v=그날 최댓값 · h=최댓값이 찍힌 KST 시 · n=표본 수 · a=표본 평균."""
    hour = datetime.datetime.now(KST).hour
    if hist and hist[-1].get("d") == today:
        e = hist[-1]
        n = int(e.get("n") or 1)
        s = float(e.get("s") if e.get("s") is not None else e.get("v", 0)) + v
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
            for g in (_const(html, "SOOP") or {}).get("games", [])}

    try:
        cats = _categories()
    except Exception as e:
        # 기존 시계열은 보존하고 그날만 건너뛴다(fetch_chzzk 와 같은 철학).
        note_health("SOOP", f"{type(e).__name__} {str(e)[:80]}")
        print(f"[SOOP 실패] {str(e)[:100]} — 기존 시계열 보존, 오늘 건너뜀")
        sys.exit(1)
    note_health("SOOP", None)

    norm = {_norm(k): v for k, v in cats.items()}
    games = []
    for stock, title, keys in GAMES:
        v = sum(val for cat, val in norm.items() if any(_norm(k) in cat for k in keys))
        hist = _merge_day(list(prev.get((stock, title), [])), today, v)
        games.append({"stock": stock, "title": title, "hist": hist[-DAYS:]})
        print(f"  {title:12s} 시청자 {v:,}")

    soop = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
            "src": "SOOP(아프리카TV) 카테고리별 시청자", "cats": len(cats), "games": games}
    if "--dry-run" in sys.argv:
        print(json.dumps(soop, ensure_ascii=False)[:700]); return
    open(HTML, "w", encoding="utf-8").write(_put(html, "SOOP", soop))
    print(f"[OK] SOOP 갱신 · {len(games)}종 · 카테고리 {len(cats)}개")


if __name__ == "__main__":
    main()
