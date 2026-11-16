# -*- coding: utf-8 -*-
"""다이소몰 누적 주문 수량 -> index.html 의  const DAISO = {...};   (2026-11-17 신설)

왜 다이소인가
  토니모리 '신채널'(다이소·올리브영·PX)이 분기 84억(매출 15%)으로 커졌는데 IS 에서 오차가 가장 큰 채널이다(검산 33%).
  다이소몰 검색 API 는 상품마다 **누적 주문 수량(totOrQy)** 을 준다 — 매일 찍어 상품별로 빼면 그날 온라인 주문 수다.
  커버리지 화장품 종목의 다이소 전용 브랜드도 같이 받는다(2026-11-17 실측 누적: VT 219만 · 본셉 119만 · 마데카21 64만 …).

무엇을 받나 — 검색어마다 요청 1건(100개씩 · 키·로그인 없음)
  https://www.daisomall.co.kr/ssn/search/Search?searchTerm=<검색어>&pageNum=N&cntPerPage=100
  항목: pdNo · pdNm · pdPrc(원) · brndNm('본셉 스킨케어>00049>…' — 앞부분만) · totOrQy(누적 주문) · revwCnt
  ⚠ pdNo 가 'B' 로 시작하는 건 박스 SKU 미러(같은 상품의 묶음 표시 · 주문 수가 본품과 거의 같다) — 빼야 두 번 센다.
  ⚠ 브랜드는 **brndNm 정확히** 로 거른다 — 검색어 'VDL'·'미샤' 는 남의 상품이 섞여 나온다(브랜드 칸이 빈 상품은 버린다).

무엇을 남기나
  DAISO.last   {pdNo: [누적 주문, 가격, 종목]}            오늘 스냅샷(내일 차분용)
  DAISO.s      {종목: {d:[날짜], o:[그날 주문 수], w:[그날 주문액(백만원)], n:[상품 수], c:[누적 주문 합]}}
               o·w = 어제·오늘 **둘 다 있는 상품만** 뺀 합(새 상품 첫날·단종은 빠진다 — 누적 합 c 를 빼면 단종이 음수로 튄다)
  DAISO.top    {종목: [[상품명, 가격, 누적 주문, 최근 차분]…]} 상위 8개
  하루 1회(이 PC · kr_collect — 러너 IP 에서 열리는지 아직 안 봤다). 같은 날 다시 돌면 그날 점을 덮는다.

  python fetch_daiso.py            # 수집·기록
  python fetch_daiso.py --dry-run  # 출력만
"""
import datetime, json, re, sys, time, urllib.parse, urllib.request

from collector_health import ua, nap, note_health

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
API = "https://www.daisomall.co.kr/ssn/search/Search"
DAYS = 400

# 종목 -> (검색어들, 브랜드 이름(brndNm 의 '>' 앞)들). 확실한 것만 — 회사 브랜드인지 확인한 것.
BRANDS = {
    "토니모리":     (["본셉"], ["본셉 메이크업", "본셉 스킨케어"]),          # 다이소 전용 브랜드 BONCEPT(토니모리)
    "브이티":       (["VT", "리들샷"], ["VT"]),
    "동국제약":     (["마데카"], ["마데카21", "동국제약"]),               # 센텔리안24 마데카21
    "에이블씨엔씨": (["어퓨"], ["어퓨_더퓨어"]),
    "네오팜":       (["리얼베리어"], ["바이 리얼베리어"]),
    "아모레퍼시픽": (["미모 바이 마몽드"], ["미모 바이 마몽드"]),
    "LG생활건강":   (["더페이스샵"], ["더페이스샵"]),
    "클리오":       (["트윙클팝"], ["트윙클팝"]),
}


def search(term):
    out, page = [], 1
    while page <= 5:
        u = f"{API}?searchTerm={urllib.parse.quote(term)}&pageNum={page}&cntPerPage=100"
        req = urllib.request.Request(u, headers={**ua(referer="https://www.daisomall.co.kr/"), "Accept": "application/json"})
        d = json.loads(urllib.request.urlopen(req, timeout=25).read().decode("utf-8"))
        r = (d.get("resultSet") or {}).get("result") or [{}]
        docs = r[0].get("resultDocuments") or []
        out += docs
        if len(out) >= int(r[0].get("totalSize") or 0) or not docs:
            break
        page += 1
        nap(0.4)
    return out


def main():
    dry = "--dry-run" in sys.argv
    now = datetime.datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    html = open(HTML, encoding="utf-8").read()
    m = re.search(r"^const DAISO = (\{.*?\});$", html, re.M | re.S)
    old = json.loads(m.group(1)) if m else {}
    prev = old.get("last") or {}
    prevDay = old.get("lastDay")

    snap, fails = {}, []
    for stock, (terms, brands) in BRANDS.items():
        for term in terms:
            try:
                docs = search(term)
            except Exception as e:
                fails.append(f"{stock}/{term}: {type(e).__name__}")
                continue
            for x in docs:
                pd = str(x.get("pdNo") or "")
                br = (x.get("brndNm") or "").split(">")[0].strip()
                if not pd or pd.startswith("B") or br not in brands:
                    continue
                try:
                    snap[pd] = [int(x.get("totOrQy") or 0), int(float(x.get("pdPrc") or 0)), stock, (x.get("pdNm") or "")[:40]]
                except ValueError:
                    continue
            nap(0.5)

    if not snap:
        note_health("다이소몰", ("수집 0건: " + "; ".join(fails))[:180] if fails else "수집 0건")
        print("[다이소] 0건"); sys.exit(1)

    S = old.get("s") or {}
    # 같은 날 다시 돌면 그날 점을 덮는다 — 그때도 차분 기준은 '어제' 스냅샷(prevBase)이어야 한다
    base = old.get("prevBase") if prevDay == today else prev
    base = base or {}
    top = {}
    for stock in BRANDS:
        mine = {k: v for k, v in snap.items() if v[2] == stock}
        if not mine:
            continue
        both = [k for k in mine if k in base]
        o = sum(max(0, mine[k][0] - base[k][0]) for k in both) if both else None
        w = round(sum(max(0, mine[k][0] - base[k][0]) * mine[k][1] for k in both) / 1e6, 2) if both else None
        s = S.setdefault(stock, {"d": [], "o": [], "w": [], "n": [], "c": []})
        if s["d"] and s["d"][-1] == today:
            for a in "dowcn":
                s[a].pop()
        s["d"].append(today); s["o"].append(o); s["w"].append(w)
        s["n"].append(len(mine)); s["c"].append(sum(v[0] for v in mine.values()))
        for a in "downc":
            s[a] = s[a][-DAYS:]
        rows = sorted(mine.items(), key=lambda kv: -kv[1][0])[:8]
        top[stock] = [[v[3], v[1], v[0], (v[0] - base[k][0]) if k in base else None] for k, v in rows]
        print(f"  {stock:8} 상품 {len(mine):3} · 누적 {s['c'][-1]:>10,} · 오늘 차분 {o if o is not None else '첫날'}")

    out = {"asOf": now.strftime("%Y-%m-%d %H:%M KST"), "lastDay": today,
           "prevBase": base if prevDay == today else prev, "last": snap, "s": S, "top": top}
    if fails:
        print("  일부 실패:", "; ".join(fails))
    note_health("다이소몰", ("; ".join(fails))[:180] if len(fails) > len(BRANDS) // 2 else None)
    if dry:
        print("[다이소] dry-run — 저장 안 함"); return
    block = "const DAISO = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";"
    if m:
        html = html[:m.start()] + block + html[m.end():]
    else:
        a = re.search(r"^const QOO10 = ", html, re.M)
        html = html[:a.start()] + block + "\n" + html[a.start():]
    open(HTML, "w", encoding="utf-8").write(html)
    print(f"[OK] DAISO 상품 {len(snap)}개 · {today}")


if __name__ == "__main__":
    main()
