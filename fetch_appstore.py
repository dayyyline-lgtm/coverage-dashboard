# -*- coding: utf-8 -*-
"""
Apple 앱스토어(한국) 게임 순위 수집 — 게임 커버 종목의 소비/수요 신호.

Apple 마케팅 RSS(무료·키 불필요). 게임 장르(6014)의:
  - 매출 순위(topgrossing)  = 매출 프록시 (핵심)
  - 무료 순위(topfree)      = 신규 유입/화제성
구글 플레이는 공식 무료 API 가 없어(유료 API 필요) 애플만 받는다. 애플은 한국에서
구글보다 점유가 작지만, 리니지·배그·니케·쿠키런 같은 대작은 매출 상위라 방향성 신호로 충분하다.

특정 게임을 지목 조회할 수 없어 Top100 을 훑어 종목별 대표작이 뜬 순위를 잡는다.
Top100 밖이면 그날은 값 없음(선이 끊긴다). 과거 시계열 무료 소스가 없어 매일 1점 누적.

  python fetch_appstore.py            # 수집·기록
  python fetch_appstore.py --dry-run  # 출력만
"""
import urllib.request, json, re, sys, datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
DAYS = 180
UA = {"User-Agent": "Mozilla/5.0"}

# 게임 커버 종목 → 대표작 타이틀 키워드(부분일치, 소문자 비교). 검증: 쿠키런·리니지·니케·배그 매칭 OK.
GAMES = {
    "데브시스터즈": ["쿠키런"],
    "크래프톤":   ["배틀그라운드", "pubg", "펍지", "뉴스테이트", "인조이", "inzoi"],
    "NC":        ["리니지", "아이온", "저니 오브 모나크", "저니오브모나크"],
    "펄어비스":   ["검은사막"],
    "시프트업":   ["니케", "nikke"],
}


def chart(kind):
    """게임 장르 Top100 앱 이름 리스트. kind: topgrossingapplications / topfreeapplications"""
    u = f"https://itunes.apple.com/kr/rss/{kind}/limit=100/genre=6014/json"
    d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA),
                                          timeout=25).read().decode("utf-8"))
    return [e.get("im:name", {}).get("label", "") for e in d.get("feed", {}).get("entry", [])]


def best_rank(names, kws):
    """차트에서 키워드에 맞는 가장 높은(작은) 순위와 타이틀. 없으면 (None, None)."""
    kws = [k.lower() for k in kws]
    for i, nm in enumerate(names, 1):
        low = nm.lower()
        if any(k in low for k in kws):
            return i, nm[:30]
    return None, None


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
        raise RuntimeError("APPRANK 삽입 기준(const LIVE)을 못 찾음")
    return html[:liv.end()] + "\n" + block + html[liv.end():]


def main():
    html = open(HTML, encoding="utf-8").read()
    today = datetime.datetime.now(KST).date().isoformat()
    prev = {g["stock"]: g for g in (_const(html, "APPRANK") or {}).get("games", [])}

    try:
        gross = chart("topgrossingapplications")
        free = chart("topfreeapplications")
    except Exception as e:
        print(f"[appstore] 차트 수집 실패: {str(e)[:100]}"); return

    games = []
    for stock, kws in GAMES.items():
        gr, gt = best_rank(gross, kws)
        fr, ft = best_rank(free, kws)
        old = prev.get(stock, {})
        hist = list(old.get("hist") or [])
        pt = {"d": today}
        if gr is not None:
            pt["gr"] = gr
        if fr is not None:
            pt["fr"] = fr
        if gt or ft:
            pt["t"] = gt or ft          # 매칭 타이틀(각주용)
        if len(pt) > 1:                 # 잡힌 게 있을 때만 점 추가
            by_d = {x["d"]: x for x in hist if x.get("d")}
            cur = by_d.get(today, {"d": today})
            cur.update(pt)
            by_d[today] = cur
            hist = [by_d[d] for d in sorted(by_d)][-DAYS:]
        games.append({"stock": stock, "hist": hist})
        print(f"  {stock}: 매출 {gr or '—'}위 · 무료 {fr or '—'}위"
              + (f" ({gt or ft})" if (gt or ft) else " (Top100 밖)"))

    out = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "games": games}
    if "--dry-run" in sys.argv:
        print(json.dumps(out, ensure_ascii=False, indent=1)[:800]); return

    # 값 변동 없으면(순위·히스토리 동일) asOf 만 바뀌므로 파일 안 건드림
    old_games = {g["stock"]: g.get("hist") for g in (_const(html, "APPRANK") or {}).get("games", [])}
    if all(old_games.get(g["stock"]) == g["hist"] for g in games) and old_games:
        print("변동 없음 — index.html 그대로 둠"); return
    open(HTML, "w", encoding="utf-8").write(_put(html, "APPRANK", out))
    print(f"[OK] APPRANK 갱신 · {len(games)}종목")


if __name__ == "__main__":
    main()
