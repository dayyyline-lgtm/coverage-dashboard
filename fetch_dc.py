# -*- coding: utf-8 -*-
"""디시인사이드 갤러리 글 양 수집 -> index.html 의  const DCGALL = {...};

왜 이걸 보나 (2026-09-02 신설)
  커뮤니티 글 양은 '관심의 온도'다. 검색 트렌드보다 거칠지만 훨씬 빠르고, 특히 게임은
  런칭·업데이트·사건이 갤러리 글 양에 그날 바로 찍힌다. 쌀먹 거래대금(게임비트)·게임머니 시세
  (아이템매니아)와 나란히 놓으면 '관심 → 거래 → 가격' 순서가 보인다.

무엇을 받나 — 글번호 증분
  목록 페이지의 gall_num 은 갤러리 안에서 연속 증가한다(삭제돼도 번호는 소비). 그래서
  **하루 사이 최대 글번호의 차이 = 그날 작성된 글 수**다. 목록 페이지 1장(50글)이면 충분하다.
  날짜는 <td class="gall_date" title="YYYY-MM-DD HH:MM:SS"> 의 title 이 정확하다.

백필 — 페이지 샘플링
  과거를 다 걸으면 글이 많은 갤은 수천 페이지다. 대신 페이지 1·3·6·12·25·50·100·200·400 을
  찍어 (글번호, 날짜) 앵커를 얻고, 앵커 사이는 선형 보간한다. 정확한 일별치는 아니고
  '그 구간 평균'이지만 추세는 잡힌다. 앵커 없는 날이 늘어나지 않도록 매일 정확한 점을 쌓는다.
  hist 의 각 점은 {d, n(최대 글번호), x:true(앵커=샘플)} — 화면은 x 점 사이를 보간한 후 차분.

주의
  · 차단 없이 열리지만 간격은 0.5s 로 넉넉히(갤 10곳 × 페이지 1 = 하루 10요청, 첫 회 ~90).
  · 갤 id 가 틀리면 엉뚱한 갤을 센다(zeus = 최우제 갤이었다). 제목을 함께 저장해 검증한다.
  · 값이 그대로면 파일을 건드리지 않는다 — deepcopy 한 원본과 비교(탑툰챗 사고 재발 방지).

  python fetch_dc.py            # 수집·기록
  python fetch_dc.py --dry-run  # 출력만
  python fetch_dc.py --backfill # 앵커 다시 샘플링(페이지 범위를 늘렸을 때)
"""
import re, json, sys, gzip, copy, datetime, urllib.request

from collector_health import ua, nap, note_health, looks_blocked

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
DAYS = 400
SAMPLE_PAGES = [1, 3, 6, 12, 25, 50, 100, 200, 400, 800, 1600, 3200, 6400]   # 120일 넘으면 멈춤

# 종목 · 갤러리. kind: board(정식) / mgallery(마이너) / mini(미니). 확인된 제목을 note 에.
GALLS = [
    {"stock": "컴투스",   "name": "제우스",     "kind": "mgallery", "id": "zeusthegodofpride"},   # 제우스 오만의 신
    {"stock": "컴투스",   "name": "컴프야",     "kind": "mgallery", "id": "cpyv22"},            # 컴투스프로야구 V26(현역)
    {"stock": "NC",      "name": "아이온2",    "kind": "mgallery", "id": "aion2"},
    {"stock": "NC",      "name": "리니지클래식", "kind": "mgallery", "id": "lineage2classic"},   # 리니지 클래식(정식 리니지갤은 7월 말 이후 글 없음)
    {"stock": "탑코미디어", "name": "탑툰",      "kind": "mgallery", "id": "toptoon"},
    {"stock": "탑코미디어", "name": "탑툰챗",    "kind": "mgallery", "id": "toptoonchat"},
]


def url(g, page=1):
    base = "https://gall.dcinside.com/board/lists/" if g["kind"] == "board" \
        else f"https://gall.dcinside.com/{g['kind']}/board/lists/"
    return f"{base}?id={g['id']}&page={page}"


def fetch_page(g, page):
    """(제목, 최대 글번호, 그 페이지 최소 글번호 행의 날짜).
    목록 1페이지에도 오래된 개념글·공지가 섞여 있어(리니지갤 마지막 행이 2005년) 날짜는 반드시
    같은 행의 글번호와 짝지어 읽는다. 공지 행은 gall_num 이 숫자가 아니라 자연히 빠진다."""
    req = urllib.request.Request(url(g, page), headers=ua(referer="https://gall.dcinside.com/"))
    r = urllib.request.urlopen(req, timeout=30)
    raw = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        raw = gzip.decompress(raw)
    h = raw.decode("utf-8", "replace")
    title = (re.search(r"<title>([^<]+)</title>", h) or [None, ""])[1].split(" - ")[0].strip()
    rows = []
    for tr in h.split("<tr ")[1:]:
        n = re.search(r'<td class="gall_num">(\d+)</td>', tr)
        d = re.search(r'class="gall_date" title="(\d{4}-\d{2}-\d{2}) ', tr)
        if n and d:
            rows.append((int(n.group(1)), d.group(1)))
    if not rows:
        return title, None, None
    return title, max(rows)[0], min(rows)[1]


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
    today = now.strftime("%Y-%m-%d")
    html = open(HTML, encoding="utf-8").read()
    m = re.search(r"const DCGALL = (\{.*?\});", html, re.S)
    old = {}
    if m:
        try:
            old = json.loads(m.group(1))
        except json.JSONDecodeError:
            old = {}
    prev = {g["id"]: g for g in copy.deepcopy(old.get("galls") or [])}

    galls, fails, ok_any = [], [], False
    for g in GALLS:
        p = prev.get(g["id"]) or {}
        hist = {h["d"]: h for h in (p.get("hist") or [])}
        try:
            title, top, _ = fetch_page(g, 1)
        except Exception as e:
            fails.append(f"{g['name']} {type(e).__name__} {str(e)[:40]}")
            if looks_blocked(e):
                note_health("디시 글수", f"{g['name']} 차단 의심: {str(e)[:60]}")
            galls.append(p if p.get("hist") else {**g, "hist": []}); continue
        nap(0.5)
        if top is None:
            fails.append(f"{g['name']} 글 없음(id 확인)"); galls.append(p if p.get("hist") else {**g, "hist": []}); continue
        ok_any = True
        hist[today] = {"d": today, "n": top}
        # 첫 수집(또는 --backfill)이면 과거 페이지를 띄엄띄엄 찍어 앵커를 만든다.
        # 앵커는 '그날 어느 시점'의 번호라 ±하루 흐림이 있다. 오늘 점은 정확값(top)이므로 덮지 않고,
        # 매일 쌓이는 정확한 점(x 없음)도 앵커로 덮지 않는다.
        if not p.get("hist") or "--backfill" in sys.argv:
            for pg in SAMPLE_PAGES[1:]:
                try:
                    _, n2, d2 = fetch_page(g, pg)
                except Exception:
                    break
                nap(0.5)
                if not n2 or not d2:
                    break
                if d2 != today and (d2 not in hist or (hist[d2].get("x") and hist[d2]["n"] > n2)):
                    hist[d2] = {"d": d2, "n": n2, "x": True}
                if (now.date() - datetime.date.fromisoformat(d2)).days > 120:
                    break
        hs = [hist[k] for k in sorted(hist)][-DAYS:]
        galls.append({**g, "title": title, "hist": hs})
        print(f"  {g['name']:8s} {title[:18]:20s} 글번호 {top:>10,} · 점 {len(hs)}개")

    if not ok_any:
        note_health("디시 글수", "전부 실패: " + "; ".join(fails)[:120])
        print("[실패] 수집 0건"); sys.exit(1)
    if fails:
        print("  일부 실패:", "; ".join(fails))
    else:
        note_health("디시 글수", None)

    out = {"asOf": now.strftime("%Y-%m-%d %H:%M KST"), "src": "디시인사이드 갤러리 글번호", "galls": galls}
    if "--dry-run" in sys.argv:
        print(json.dumps(out, ensure_ascii=False)[:800]); return
    if m:
        a, b = dict(old), dict(out); a.pop("asOf", None); b.pop("asOf", None)
        if a == b:
            print("[SKIP] 변동 없음"); return
    open(HTML, "w", encoding="utf-8").write(_put(html, "DCGALL", out))
    print(f"[OK] DCGALL 갱신 · 갤러리 {len(galls)}곳")


if __name__ == "__main__":
    main()
