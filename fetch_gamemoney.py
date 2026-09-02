# -*- coding: utf-8 -*-
"""아이템매니아 게임머니 시세 수집 -> index.html 의  const GAMEMONEY = {...};

왜 이걸 보나 (2026-09-02 신설)
  MMORPG 의 게임머니 시세는 '게임 경제의 온도계'다. 게임머니 원화 가격이 오르면
  사려는 사람(신규·복귀 유저)이 파는 사람보다 많다는 뜻이고, 내리면 반대다.
  아이온2 실측: 7/4 890원 → 9/1 390원(-56%) — 검색은 해외에서 뛰는데 국내 경제는 식는 중.
  컴투스 신작 '제우스: 오만의 신'(8/26 출시)이 이 방식의 첫 실전 대상이다.

무엇을 받나
  /_xml/gamemoney_avg.xml.php?gamecode=G&servercode=S&count=N
    → <data date="2026/09/01" price="7790" amount="160" .../>  일별, N일치 (백필 60일 확인)
  price = 게임머니 multiple(100·1,000·10,000)당 원.
  ⚠ amount 는 거래량이 아니다 — **전일 대비 가격 변동액**이다(2026-09-02 확인). 시세 페이지 JS 가
    amount_type(up/down/none)에 따라 ▲▼ 아이콘 옆에 찍는 값이고, 7,630→7,790 일 때 amount=160 이었다.
    저장 필드 a 는 그래서 '등락'이지 '거래량'이 아니다. 거래량은 다른 페이지(순위정보)를 봐야 한다.

어디를 보나
  '서버전체' 옵션이 없어서 게임마다 대표 서버 몇 개를 정해 평균낸다. 리니지M 은 232서버라
  전부 받을 수 없다 — 1번 서버(데포로쥬)로 대표. 아이온2 는 '월드거래소' 가 사실상 전체 시장.
  게임코드는 /game_info/js/gamelist.js 에 박혀 있다(제우스 6027 · 아이온2 5799 · 리니지M 3449 ·
  리니지W 4763 · TL 5092). 서버가 바뀌면 그 파일에서 다시 찾는다.

주의
  · _ajax/ 경로는 봇 게이트가 있지만 _xml/ 는 urllib 로 열린다(Actions 에서 확인).
    막히면 note_health 로 남긴다.
  · 값이 그대로면 파일을 건드리지 않는다 — 비교는 deepcopy 한 원본과 한다(탑툰챗 사고 재발 방지).

  python fetch_gamemoney.py            # 수집·기록
  python fetch_gamemoney.py --dry-run  # 출력만
"""
import re, json, sys, gzip, copy, datetime, urllib.request

from collector_health import ua, nap, note_health, looks_blocked

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
BASE = "https://www.itemmania.com"
XML = BASE + "/_xml/gamemoney_avg.xml.php?gamecode={g}&servercode={s}&count={n}"
DAYS = 400
BACKFILL = 60              # 첫 수집 때 과거 N일 (사이트가 주는 최대치 확인: 60일 OK)

# 종목 · 게임 · 대표 서버. 시세는 서버별 평균, a(등락)는 합.
# 거래량은 시세 XML 에 없다 → 아래 fetch_rank() 의 거래순위 TOP30 이 그 대용이다.
GAMES = [
    {"stock": "컴투스", "game": "제우스:오만의신", "code": 6027,
     "servers": [(24868, "아테나1"), (24869, "아테나2"), (24870, "아테나3"), (24871, "아레스1")],
     "note": "8/26 출시 MMORPG · 초기 4서버 평균"},
    {"stock": "NC", "game": "아이온2", "code": 5799,
     "servers": [(24084, "월드거래소(천족)"), (24085, "월드거래소(마족)")],
     "note": "월드거래소 = 사실상 전체 시장"},
    {"stock": "NC", "game": "리니지M", "code": 3449,
     "servers": [(14060, "데포로쥬")], "note": "232서버 중 1번 서버로 대표"},
    {"stock": "NC", "game": "리니지W", "code": 4763,
     "servers": [(18506, "군터")], "note": "196서버 중 1번 서버로 대표"},
    {"stock": "NC", "game": "TL", "code": 5092,
     "servers": [(21535, "베니")], "note": ""},
]


def fetch_xml(code, server, n):
    req = urllib.request.Request(XML.format(g=code, s=server, n=n),
                                 headers=ua(referer=BASE + "/game_info/money/"))
    r = urllib.request.urlopen(req, timeout=30)
    raw = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        raw = gzip.decompress(raw)
    x = raw.decode("utf-8", "replace")
    if "<quotation" not in x:
        raise RuntimeError("XML 아님(봇 게이트 의심)")
    mult = int((re.search(r'multiple="(\d+)"', x) or [None, "1000"])[1])
    rows = []
    for d, p, a in re.findall(r'<data date="([\d/]+)" price="(\d+)" amount="(\d+)"', x):
        rows.append((d.replace("/", "-"), int(p), int(a)))
    return rows, mult


RANK_URL = BASE + "/game_info/rank_game/"


def fetch_rank():
    """거래순위 TOP30 (오늘). 절대 거래 건수는 안 주고 순위만 준다 — 거래량의 대용.
    페이지가 서버 렌더링이라 urllib 로 열린다(_ajax 봇 게이트와 무관). 반환: (날짜, [(순위, 게임명)…])"""
    req = urllib.request.Request(RANK_URL, headers=ua(referer=BASE + "/"))
    r = urllib.request.urlopen(req, timeout=30)
    raw = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        raw = gzip.decompress(raw)
    h = raw.decode("utf-8", "replace")
    if "59.18.34.179" in h:
        raise RuntimeError("봇 게이트")
    m = re.search(r'id="today_rank".*?</table>', h, re.S)
    if not m:
        raise RuntimeError("today_rank 표 없음(구조 변경?)")
    tb = m.group(0)
    dm = re.search(r'class="top_label">(\d{4})\.\s*(\d{2})\.\s*(\d{2})', tb)
    d = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}" if dm else datetime.datetime.now(KST).strftime("%Y-%m-%d")
    rows = re.findall(r'<td class="rank[^"]*">(\d+)</td>\s*<td class="game_name">\s*<span[^>]*>\s*([^<]+?)\s*<', tb)
    top = [(int(rk), nm.strip()) for rk, nm in rows]
    if len(top) < 10:
        raise RuntimeError(f"순위 {len(top)}개뿐(파싱 실패?)")
    return d, top


def _put(html, name, obj):
    block = "const %s = %s;" % (name, json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
    pat = re.compile(r"const %s\s*=\s*\{.*?\};" % re.escape(name), re.S)
    if pat.search(html):
        return pat.sub(lambda m: block, html, count=1)
    liv = re.search(r"const LIVE\s*=\s*\{.*?\};", html, re.S)
    if not liv:
        raise RuntimeError("삽입 기준(const LIVE)을 못 찾음")
    return html[:liv.end()] + "\n" + block + html[liv.end():]


def main():
    now = datetime.datetime.now(KST)
    html = open(HTML, encoding="utf-8").read()
    m = re.search(r"const GAMEMONEY = (\{.*?\});", html, re.S)
    old = {}
    if m:
        try:
            old = json.loads(m.group(1))
        except json.JSONDecodeError:
            old = {}
    # ⚠ 제자리 수정 전에 복사 — 안 그러면 끝의 '변동 없음' 비교가 자기 자신과 비교가 된다.
    prev = {it["code"]: it for it in copy.deepcopy(old.get("items") or [])}

    items, fails, ok_any = [], [], False
    for g in GAMES:
        p = prev.get(g["code"]) or {"hist": []}
        hist = {h["d"]: h for h in (p.get("hist") or [])}
        n = 3 if hist else BACKFILL              # 처음엔 백필, 이후엔 최근 며칠만
        per_day = {}                              # d -> [prices], [amounts]
        mult = 1000
        for sc, sname in g["servers"]:
            try:
                rows, mult = fetch_xml(g["code"], sc, n)
            except Exception as e:
                fails.append(f"{g['game']}/{sname} {type(e).__name__} {str(e)[:40]}")
                if looks_blocked(e):
                    note_health("게임머니", f"{g['game']} 차단 의심: {str(e)[:60]}")
                continue
            for d, price, amt in rows:
                if price <= 0:
                    continue
                per_day.setdefault(d, [[], []])
                per_day[d][0].append(price); per_day[d][1].append(amt)
            nap(0.3)
        if not per_day:
            items.append(p if p.get("hist") else {**g, "hist": []}); continue
        ok_any = True
        for d, (ps, as_) in per_day.items():
            hist[d] = {"d": d, "p": round(sum(ps) / len(ps)), "a": sum(as_), "n": len(ps)}
        hs = [hist[k] for k in sorted(hist)][-DAYS:]
        items.append({"stock": g["stock"], "game": g["game"], "code": g["code"],
                      "servers": [s for _, s in g["servers"]], "mult": mult,
                      "note": g["note"], "hist": hs})
        last = hs[-1]
        print(f"  {g['game']:12s} {last['d']} {last['p']:,}원/{mult}머니 · 등락 {last['a']:+} · {len(hs)}일치")

    if not ok_any:
        note_health("게임머니", "전부 실패: " + "; ".join(fails)[:120])
        print("[실패] 수집 0건"); sys.exit(1)
    if fails:
        print("  일부 실패:", "; ".join(fails))
    else:
        note_health("게임머니", None)

    ranks = [x for x in copy.deepcopy(old.get("ranks") or [])]
    try:
        d, top = fetch_rank()
        ranks = [x for x in ranks if x.get("d") != d] + [{"d": d, "top": [[r, n] for r, n in top]}]
        ranks = sorted(ranks, key=lambda x: x["d"])[-DAYS:]
        mine = {n: r for r, n in top if n in ("제우스:오만의신", "아이온2", "리니지M", "리니지W", "리니지클래식", "TL쓰론앤리버티")}
        print(f"  거래순위 {d}: " + " · ".join(f"{n} {r}위" for n, r in mine.items()))
    except Exception as e:
        fails.append(f"거래순위 {type(e).__name__} {str(e)[:40]}")

    out = {"asOf": now.strftime("%Y-%m-%d %H:%M KST"), "src": "아이템매니아 게임머니 시세",
           "items": items, "ranks": ranks}
    if "--dry-run" in sys.argv:
        print(json.dumps(out, ensure_ascii=False)[:800]); return
    if m:
        a, b = dict(old), dict(out); a.pop("asOf", None); b.pop("asOf", None)
        if a == b:
            print("[SKIP] 변동 없음"); return
    open(HTML, "w", encoding="utf-8").write(_put(html, "GAMEMONEY", out))
    print(f"[OK] GAMEMONEY 갱신 · 게임 {len(items)}개")


if __name__ == "__main__":
    main()
