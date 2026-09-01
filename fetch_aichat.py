# -*- coding: utf-8 -*-
"""
AI 캐릭터 챗봇 앱 순위 수집 — 탑코미디어(탑툰챗)의 경쟁 지형을 '돈'으로 본다.

왜 검색 트렌드로는 부족한가
  ① '크랙'은 소프트웨어 크랙과 동음이의어라 네이버 검색량이 통째로 오염된다.
  ② 검색량은 관심이지 매출이 아니다. 이 시장은 이미 유료 구독으로 돈을 벌고 있어
     **앱스토어 매출순위**가 훨씬 직접적인 신호다(26.08 실측: 제타 엔터 매출 10위).

무엇을 받나 (Apple 마케팅 RSS, 키 불필요 · fetch_appstore.py 와 같은 소스)
  - 엔터테인먼트(6016) 매출/무료 Top100  → AI 캐릭터 채팅 앱들
  - 도서(6018)        매출/무료 Top100  → 웹툰·여성향 AI채팅 (탑툰 본체가 여기 있다)
  Top100 밖이면 그날은 값 없음(선이 끊긴다). 과거 시계열 무료 소스가 없어 매일 1점 누적.

⚠ 탑툰챗(탑코미디어)은 **앱이 없다** — 웹 전용이라 이 순위에 안 잡힌다.
  탑툰챗 자체 사용량은 fetch_toptoonchat.py(홈페이지 실측)가 담당하고,
  여기서는 '경쟁자가 어디까지 왔나'와 '탑툰 본체 앱 순위'를 본다.

  python fetch_aichat.py            # 수집·기록
  python fetch_aichat.py --dry-run  # 출력만
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

# 매칭 키워드는 **관측된 실제 타이틀에서 딴다**(소문자 부분일치).
#   '제타' 를 "zeta" 로 잡으면 무료 16위 'ZETA - 게임 에뮬레이터' 가 걸린다 → "제타(zeta)" 로 고정.
#   '크랙' 도 뒤의 " - " 까지 붙여 다른 앱과 섞이지 않게 한다.
# g = 장르(6016 엔터테인먼트 / 6018 도서). 앱마다 주 장르가 하나라 그 장르 안에서만 찾는다.
APPS = [
    {"n": "제타",       "co": "스캐터랩",   "kw": ["제타(zeta)"],   "g": 6016},
    {"n": "크랙",       "co": "뤼튼",       "kw": ["크랙 -"],       "g": 6016},
    {"n": "멜팅",       "co": "—",          "kw": ["멜팅 -"],       "g": 6016},
    {"n": "티키타",     "co": "—",          "kw": ["티키타 -"],     "g": 6016},
    {"n": "러비더비",   "co": "타인AI",     "kw": ["러비더비"],     "g": 6016},
    {"n": "프론티아",   "co": "—",          "kw": ["프론티아"],     "g": 6016},
    {"n": "리티",       "co": "—",          "kw": ["리티 -"],       "g": 6016},
    # 네오나 = 네오사피엔스(타입캐스트). 2026-09 코스닥 상장 예정이라 상장 후엔 종목이 된다.
    {"n": "네오나",     "co": "네오사피엔스", "kw": ["네오나"],     "g": 6016},
    # ── 도서(6018) — 웹툰/여성향 AI채팅. 탑툰 본체가 여기 있다.
    {"n": "탑툰",       "co": "탑코미디어", "kw": ["탑툰"],         "g": 6018},
    {"n": "플레이툰",   "co": "—",          "kw": ["플레이툰"],     "g": 6018},
    {"n": "채티",       "co": "—",          "kw": ["채티 -"],       "g": 6018},
    {"n": "돌로플래닛", "co": "—",          "kw": ["돌로플래닛"],   "g": 6018},
]


def chart(kind, genre):
    u = f"https://itunes.apple.com/kr/rss/{kind}/limit=100/genre={genre}/json"
    d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA),
                                          timeout=25).read().decode("utf-8"))
    return [e.get("im:name", {}).get("label", "") for e in d.get("feed", {}).get("entry", [])]


def best_rank(names, kws):
    kws = [k.lower() for k in kws]
    for i, nm in enumerate(names, 1):
        low = nm.lower()
        if any(k in low for k in kws):
            return i, nm[:36]
    return None, None


def _const(html, name):
    m = re.search(r"const %s\s*=\s*(\{.*?\});" % re.escape(name), html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _put(html, name, obj):
    block = "const %s = %s;" % (name, json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
    pat = re.compile(r"const %s\s*=\s*\{.*?\};" % re.escape(name), re.S)
    if pat.search(html):
        return pat.sub(lambda m: block, html, count=1)
    liv = re.search(r"const LIVE\s*=\s*\{.*?\};", html, re.S)
    if not liv:
        raise RuntimeError("AICHAT 삽입 기준(const LIVE)을 못 찾음")
    return html[:liv.end()] + "\n" + block + html[liv.end():]


def main():
    html = open(HTML, encoding="utf-8").read()
    today = datetime.datetime.now(KST).date().isoformat()
    prev = {a["n"]: a for a in (_const(html, "AICHAT") or {}).get("apps", [])}

    charts = {}
    for g in sorted({a["g"] for a in APPS}):
        try:
            charts[(g, "gross")] = chart("topgrossingapplications", g)
            charts[(g, "free")] = chart("topfreeapplications", g)
        except Exception as e:
            print(f"[aichat] 장르 {g} 차트 실패: {str(e)[:100]}")
    if not charts:
        print("[실패] 차트 0건 - index.html 그대로 둡니다"); sys.exit(1)

    apps = []
    for a in APPS:
        gr, gt = best_rank(charts.get((a["g"], "gross"), []), a["kw"])
        fr, ft = best_rank(charts.get((a["g"], "free"), []), a["kw"])
        old = prev.get(a["n"], {})
        hist = list(old.get("hist") or [])
        pt = {"d": today}
        if gr is not None: pt["gr"] = gr
        if fr is not None: pt["fr"] = fr
        if gt or ft:       pt["t"] = gt or ft
        if len(pt) > 1:
            by_d = {x["d"]: x for x in hist if x.get("d")}
            cur = by_d.get(today, {"d": today}); cur.update(pt); by_d[today] = cur
            hist = [by_d[d] for d in sorted(by_d)][-DAYS:]
        apps.append({"n": a["n"], "co": a["co"], "g": a["g"], "hist": hist})
        print(f"  {a['n']:>10}: 매출 {gr or '—'}위 · 무료 {fr or '—'}위"
              + (f"  ({gt or ft})" if (gt or ft) else "  (Top100 밖)"))

    out = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "apps": apps}
    if "--dry-run" in sys.argv:
        print(json.dumps(out, ensure_ascii=False)[:900]); return

    old_h = {a["n"]: a.get("hist") for a in (_const(html, "AICHAT") or {}).get("apps", [])}
    if old_h and all(old_h.get(a["n"]) == a["hist"] for a in apps):
        print("변동 없음 - index.html 그대로 둠"); return
    open(HTML, "w", encoding="utf-8").write(_put(html, "AICHAT", out))
    print(f"[OK] AICHAT 갱신 · 앱 {len(apps)}개")


if __name__ == "__main__":
    main()
