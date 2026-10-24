"""미국 해상 수입 B/L(선하증권) 월별 선적량 -> index.html 의  const BL = {...};   (2026-10-24 신설)

왜 — 관세청 수출(TRADE)은 다음 달 15일에야 나오고 품목·지역 단위다. B/L 은 **회사 단위**이고 미국 도착 며칠 뒤면 잡힌다.
  사용자 2026-10-24 "트렌드에 수출 B/L 같은 선적 데이터도 추가".

소스 — ImportYeti(importyeti.com). 미국 세관(CBP) AMS 해상 적하목록을 회사별로 묶어 무료로 보여 준다.
  회사 페이지(Next.js flight)에 '월별 해상 선적(Total Sea Shipments Over Time)'이 2015년부터 실려 있다:
    "data":{"01/10/2026":{"shipments":441,"weight":4533180,"teu":879,...}}   ← 키는 일/월/연(일은 늘 01)
  `databaseUpdated` 가 자료 기준일이다(그 달은 그날까지만 — 진행 중인 달).

어느 쪽 페이지를 쓰나 — **미국 법인(수입자 · company/…)이 있으면 그쪽이 먼저다.**
  ⚠ 수출자 이름은 가려질 수 있다(미국 세관 '적하목록 비공개' 신청 · 2년마다 갱신). 삼양식품 수출자 페이지는
    2024-10 ~ 2026-08 이 거의 0 인데 같은 기간 미국 법인(Samyang America) 수입은 월 400~700건이 그대로 있다 —
    수출자 칸이 'Missing in source document' 로 바뀐 것이다. 0 이 '안 보냈다'가 아닐 수 있다.
  ⚠ 해상만이다(항공 화물 없음). 화장품은 항공 비중이 커서 회사 전체 물량이 아니다 — **추이**를 보는 지표.
  ⚠ 미국 공장 생산분은 안 잡힌다(농심 랜초쿠카몽가 · 코스맥스 뉴저지 · CJ 슈완스).

차단 — 로그인 없이 한 IP 에서 페이지를 20여 장 넘게 열면 데이터 없는 빈 화면(56KB)을 준다(2026-10-24 실측).
  그래서 한 번에 MAX_PAGES 장만, **가장 오래전에 받은 소스부터** 돌아가며 받는다(월별 자료라 2~3일 간격이면 충분).
  빈 화면이 나오면 그 회차는 바로 멈춘다(더 열면 막힘만 길어진다). 검색 API(/api/search)는 더 빡빡하다(40회쯤 429).

새 소스 찾는 법 — 브라우저에서 https://www.importyeti.com/search?q=<영문 회사명> → 미국 법인(Company) · 한국 수출자(Supplier) 주소.
  페이지의 HS 구성(Product Breakdown)이 그 회사 물건인지 꼭 볼 것 — 같은 이름의 딴 회사가 섞인다
  (Samyang America 에 삼양사 화학 · 'Samyang' 수출자는 삼양사).

python fetch_bl.py            # 오래된 순으로 MAX_PAGES 장
python fetch_bl.py --all      # 전부(첫 수집 · 막히면 거기서 멈춘다)
python fetch_bl.py --if-due   # 오늘 이미 받았으면 끝(kr_collect 용)
"""
import copy, datetime, json, re, sys, time, urllib.request

from collector_health import ua, nap, note_health

KST = datetime.timezone(datetime.timedelta(hours=9))
HTML = "public/index.html"
BASE = "https://www.importyeti.com/"
START = "2019-01"            # 화면에 싣는 첫 달 — 전년비·계절을 보려고 7년
MAX_PAGES = 7

# (종목, 페이지, 화면 이름, 메모) — 순서 = 화면 순서
SOURCES = [
    ("삼양식품", "company/samyang-america", "미국 법인 수입", "Samyang America(브레아) · 라면(1902)이 B/L 의 80% · 수출자 이름은 2024-10~2026-08 가려짐"),
    ("농심", "company/nongshim-america", "미국 법인 수입", "Nongshim America · 라면(1902)·스낵(1905) · 미국 공장 생산분은 안 잡힘"),
    ("농심", "supplier/nongshim", "한국 출하", "농심 한국 수출자 → 미국(대부분 미국 법인)"),
    ("빙그레", "supplier/binggrae", "한국 출하", "빙과(2105)·가공유(0402) · 미국 법인 이름이 따로 안 잡혀 수출자 쪽"),
    ("CJ제일제당", "supplier/cj-cheiljedang", "한국 출하", "식품(1904 즉석밥·2103 소스·1902)에 소재가 섞인다 — 추이만"),
    ("아모레퍼시픽", "company/us-amorepacific-warehouse", "미국 창고 수입", "US Amorepacific Warehouse · 화장품(3304)"),
    ("아모레퍼시픽", "supplier/cosrx", "코스알엑스 한국 출하", "COSRX 수출자 → 미국"),
    ("LG생활건강", "supplier/lg-h-h", "한국 출하", "LG H&H 수출자 · 화장품(3304)·세제(3402) 혼재 · 2025-05 전 이름(LG Household)은 따로라 그 전은 얇다"),
    ("코스맥스", "supplier/cosmax", "한국 출하", "한국 공장 → 미국 고객사(브랜드) · 미국 공장(뉴저지) 생산분은 안 잡힘"),
    ("실리콘투", "supplier/silicon2", "한국 출하", "Silicon2 수출자 → 미국(자사 창고·리테일러)"),
    ("토니모리", "company/tonymoly-usa", "미국 법인 수입", "Tonymoly USA"),
    ("에이블씨엔씨", "supplier/able-c-c", "한국 출하", "Able C&C(미샤) 수출자"),
]


def get(path):
    q = urllib.request.Request(BASE + path, headers=ua(referer=BASE, doc=True))
    return urllib.request.urlopen(q, timeout=40).read().decode("utf-8", "replace")


def flight_of(html):
    parts = re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', html)
    return "".join(json.loads('"' + x + '"') for x in parts)


def grab_obj(fl, key):
    """'"key":{' 다음 JSON 객체를 괄호 짝으로 잘라 낸다."""
    i = fl.find('"' + key + '":{')
    if i < 0:
        return None
    i = fl.index("{", i)
    d = 0; ins = False; esc = False
    for j in range(i, len(fl)):
        c = fl[j]
        if ins:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == '"': ins = False
        elif c == '"': ins = True
        elif c == "{": d += 1
        elif c == "}":
            d -= 1
            if d == 0:
                return json.loads(fl[i:j + 1])
    return None


def parse(html):
    """월별 {YYYY-MM: (건수, 톤, TEU)} · 자료 기준일. 빈 화면(차단)이면 None."""
    fl = flight_of(html)
    upd = re.search(r'"databaseUpdated":"(\d\d)/(\d\d)/(\d{4})"', fl)
    data = grab_obj(fl, "data") if upd else None
    if not upd or not data:
        return None, None
    out = {}
    for k, v in data.items():
        m = re.match(r"\d\d/(\d\d)/(\d{4})$", k)
        if m:
            out[f"{m.group(2)}-{m.group(1)}"] = (v.get("shipments") or 0, round((v.get("weight") or 0) / 1000, 1), v.get("teu") or 0)
    return out, f"{upd.group(3)}-{upd.group(1)}-{upd.group(2)}"


def months_until(last):
    y, m = map(int, START.split("-"))
    ly, lm = map(int, last.split("-"))
    out = []
    while (y, m) <= (ly, lm):
        out.append(f"{y}-{m:02d}")
        m += 1
        if m > 12: y += 1; m = 1
    return out


def load_block(html):
    m = re.search(r"^const BL = (\{.*?\});$", html, re.M | re.S)
    if not m:
        return None, None
    try:
        return json.loads(m.group(1)), m
    except json.JSONDecodeError:
        return None, m


def main():
    now = datetime.datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    html = open(HTML, encoding="utf-8").read()
    old, m = load_block(html)
    if "--if-due" in sys.argv and old and (old.get("asOf") or "")[:10] == today:
        print("[B/L] 오늘 이미 받음 — 건너뜀"); return
    old = old or {}
    prev = {s["id"]: s for s in (old.get("s") or [])}

    # 받을 순서: 처음 보는 소스 → 오래전에 받은 소스
    order = sorted(SOURCES, key=lambda s: (prev.get(s[1], {}).get("got") or "0000"))
    limit = len(order) if "--all" in sys.argv else MAX_PAGES
    got, blocked, fails = {}, False, []
    for st, path, label, memo in order[:limit]:
        try:
            mon, upd = parse(get(path))
        except Exception as e:
            fails.append(f"{path}: {type(e).__name__} {str(e)[:60]}")
            nap(6); continue
        if mon is None:
            blocked = True
            print(f"[B/L] {path} — 데이터 없는 빈 화면(조회 한도) · 이번 회차는 여기서 멈춘다")
            break
        got[path] = (mon, upd)
        last = max(mon) if mon else "-"
        print(f"[B/L] {st:8} {path:36} 기준 {upd} · {len(mon)}개월 · 마지막 {last} {mon.get(last, ('', '', ''))}")
        nap(6)

    if not got and (blocked or fails):
        note_health("B/L 선적", ("조회 한도(빈 화면)" if blocked else "") + (" · " + "; ".join(fails[:3]) if fails else ""))
        print("[B/L] 하나도 못 받음"); sys.exit(1)
    note_health("B/L 선적", (f"일부만({len(got)}곳) — 조회 한도" if blocked and len(got) < 3 else None))

    # 모든 소스의 마지막 달까지 공통 달 축
    lasts = [max(v[0]) for v in got.values() if v[0]] + [old["months"][-1]] if old.get("months") else [max(v[0]) for v in got.values() if v[0]]
    months = months_until(max(lasts))
    out = {"asOf": now.strftime("%Y-%m-%d %H:%M KST"), "months": months, "s": []}
    for st, path, label, memo in SOURCES:
        if path in got:
            mon, upd = got[path]
            first = min(mon) if mon else START
            ser = lambda i: [(mon.get(k, (0, 0, 0))[i] if k >= first else None) for k in months]   # 첫 선적 뒤 빈 달 = 0건
            s = {"st": st, "id": path, "label": label, "memo": memo, "got": today, "upd": upd,
                 "n": ser(0), "w": ser(1), "teu": ser(2)}
        elif path in prev:
            s = copy.deepcopy(prev[path])
            pm = old["months"]
            for k in ("n", "w", "teu"):                     # 옛 달 축 → 새 달 축(뒤에 붙은 달은 비움)
                mp = dict(zip(pm, s[k]))
                s[k] = [mp.get(x) for x in months]
            s.update(st=st, label=label, memo=memo)
        else:
            continue
        out["s"].append(s)
    ups = [s["upd"] for s in out["s"] if s.get("upd")]
    out["upd"] = max(ups) if ups else None
    out["src"] = "ImportYeti · 미국 세관(CBP) 해상 수입 적하목록(B/L)"
    out["note"] = ("미국으로 들어온 **해상** 선적만(항공 제외) · 월 = 미국 도착 달 · 중량은 B/L 신고 총중량(t). "
                   "미국 법인(수입자) 페이지를 먼저 쓴다 — 수출자 이름은 세관 비공개 신청으로 가려질 수 있다. "
                   "마지막 달은 자료 기준일까지만(진행 중).")

    if old and {k: v for k, v in old.items() if k != "asOf"} == {k: v for k, v in out.items() if k != "asOf"}:
        print("[B/L] 변동 없음")
    block = "const BL = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";"
    if m:
        html = html[:m.start()] + block + html[m.end():]
    else:
        anchor = re.search(r"^const TREND = ", html, re.M)
        if not anchor:
            print("삽입 위치(const TREND)를 못 찾았습니다"); sys.exit(1)
        html = html[:anchor.start()] + block + "\n" + html[anchor.start():]
    open(HTML, "w", encoding="utf-8").write(html)
    print(f"[B/L] BL 블록 갱신 ({len(block) // 1024}KB · 소스 {len(out['s'])} · 이번에 받은 것 {len(got)})")


if __name__ == "__main__":
    main()
