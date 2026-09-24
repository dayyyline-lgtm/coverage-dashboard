# -*- coding: utf-8 -*-
"""Qoo10 JP 뷰티 베스트셀러 톱200 -> index.html 의  const QOO10 = {...};   (2026-09-24 신설 · 개편계획 Phase 3)

왜 Qoo10 인가
  일본 K뷰티의 주 채널은 아마존이 아니라 Qoo10(메가할인 'メガ割')이다. 사용자 지시: "일본은 Qoo10 같은 걸로".
  뷰티 카테고리 톱200 이 **판매 기반 순위**(사이트 안내: 販売数や売上高…)라 아마존 BSR 과 같은 성격의 신호다.

무엇을 받나 — 요청 1건
  https://www.qoo10.jp/gmkt.inc/Bestsellers/?g=2   (g=2 = ビューティ · 200개 서버 렌더)
  항목마다: 순위 · 상품번호 · 브랜드(txt_brand) · 제목 · 정가/할인가 · 리뷰 수 · 공식 여부 · **한국발**(GA 문자열 '#KR#').
  2026-09-24 실측: 200개 중 한국발 118개(59%) · 아누아 10 · 메디큐브 10 · SKIN1004 4 · 에이프릴스킨 4.

무엇을 남기나
  QOO10.kr[]      한국발 비중 시계열 {d, kr, n}            — 섹터 지표(실리콘투·콜마·코스맥스 프록시)
  QOO10.brands[]  브랜드별 {jp, brand, stock, hist:[{d, c(진입 수), best(최고 순위), rev(리뷰 합)}]}
  QOO10.top[]     오늘 톱200 전체(압축) — 화면 표용. 이력은 brands/kr 에만.
  값이 그대로면 파일을 건드리지 않는다(deepcopy 비교 — 탑툰챗 사고 재발 방지).

주의
  · 러너(GitHub Actions)에서 200·1MB·1초 (diag_probe 2026-09-24). urllib + ua(doc=True) 로 열린다.
  · 브랜드명은 일본 표기다. BRANDS 에 없는 한국발 브랜드는 '그 밖 한국발'로만 센다(개별 추적 안 함).
  · 가격은 엔. 할인가(strong) 가 있으면 그걸 p 로, 정가는 p0.
  · 검색 페이지(/s/키워드)는 리뷰·판매수가 없어 안 쓴다 — 상품 수만 보이는데 그건 신호가 약하다.

  python fetch_qoo10.py            # 수집·기록
  python fetch_qoo10.py --dry-run  # 출력만
"""
import re, json, sys, copy, datetime, urllib.request, html as htmlmod
from collector_health import ua, note_health

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
URL = "https://www.qoo10.jp/gmkt.inc/Bestsellers/?g=2"
DAYS = 180
N = 200

# 일본 표기(정규화 후) -> (정식 브랜드명, 종목 또는 운영사, 커버리지 종목명 or None)
# ⚠ 확실한 것만. 짐작으로 넣으면 조용히 틀린 종목에 붙는다.
BRANDS = {
    "メディキューブ": ("medicube", "에이피알", "에이피알"),
    "MEDICUBE": ("medicube", "에이피알", "에이피알"),
    "エイプリルスキン": ("April Skin", "에이피알", "에이피알"),
    "APRILSKIN": ("April Skin", "에이피알", "에이피알"),
    "ダルバ": ("d'Alba", "달바글로벌", "달바글로벌"),
    "D'ALBA": ("d'Alba", "달바글로벌", "달바글로벌"),
    "コスアールエックス": ("COSRX", "아모레퍼시픽", "아모레퍼시픽"),
    "COSRX": ("COSRX", "아모레퍼시픽", "아모레퍼시픽"),
    "ラネージュ": ("LANEIGE", "아모레퍼시픽", "아모레퍼시픽"),
    "LANEIGE": ("LANEIGE", "아모레퍼시픽", "아모레퍼시픽"),
    "イニスフリー": ("innisfree", "아모레퍼시픽", "아모레퍼시픽"),
    "INNISFREE": ("innisfree", "아모레퍼시픽", "아모레퍼시픽"),
    "エチュード": ("ETUDE", "아모레퍼시픽", "아모레퍼시픽"),
    "ETUDE": ("ETUDE", "아모레퍼시픽", "아모레퍼시픽"),
    "ヘラ": ("HERA", "아모레퍼시픽", "아모레퍼시픽"),
    "HERA": ("HERA", "아모레퍼시픽", "아모레퍼시픽"),
    "エスポア": ("espoir", "아모레퍼시픽", "아모레퍼시픽"),
    "ESPOIR": ("espoir", "아모레퍼시픽", "아모레퍼시픽"),
    "アロマティカ": ("Aromatica", "아로마티카", "아로마티카"),
    "AROMATICA": ("Aromatica", "아로마티카", "아로마티카"),
    "ビリーフ": ("belif", "LG생활건강", "LG생활건강"),
    "BELIF": ("belif", "LG생활건강", "LG생활건강"),
    "CNP": ("CNP", "LG생활건강", "LG생활건강"),
    "ザフェイスショップ": ("THE FACE SHOP", "LG생활건강", "LG생활건강"),
    "フィジオゲル": ("Physiogel", "LG생활건강", "LG생활건강"),
    # 커버리지 밖(상장·비상장) — 한국발 지형 파악용
    "アヌア": ("Anua", "더파운더즈", None),
    "ANUA": ("Anua", "더파운더즈", None),
    "SKIN1004": ("SKIN1004", "구다이글로벌", None),
    "ティルティル": ("TIRTIR", "구다이글로벌", None),
    "TIRTIR": ("TIRTIR", "구다이글로벌", None),
    "ビューティーオブジョソン": ("Beauty of Joseon", "구다이글로벌", None),
    "BEAUTYOFJOSEON": ("Beauty of Joseon", "구다이글로벌", None),
    "バイオダンス": ("BIODANCE", "바이오던스", None),
    "BIODANCE": ("BIODANCE", "바이오던스", None),
    "VT": ("VT Cosmetics", "브이티", None),
    "VTCOSMETICS": ("VT Cosmetics", "브이티", None),
    "魔女工場": ("Manyo", "마녀공장", None),
    "マニョ": ("Manyo", "마녀공장", None),
    "MANYO": ("Manyo", "마녀공장", None),
    "トリデン": ("Torriden", "토리든", None),
    "TORRIDEN": ("Torriden", "토리든", None),
    "ナンバーズイン": ("numbuzin", "넘버즈인", None),
    "NUMBUZIN": ("numbuzin", "넘버즈인", None),
    "ラウンドラボ": ("Round Lab", "라운드랩", None),
    "ROUNDLAB": ("Round Lab", "라운드랩", None),
    "アビブ": ("Abib", "아비브", None),
    "ABIB": ("Abib", "아비브", None),
    "クリオ": ("CLIO", "클리오", None),
    "CLIO": ("CLIO", "클리오", None),
    "ロムアンド": ("rom&nd", "아이패밀리에스씨", None),
    "ROM&ND": ("rom&nd", "아이패밀리에스씨", None),
    "ミシャ": ("MISSHA", "에이블씨엔씨", None),
    "MISSHA": ("MISSHA", "에이블씨엔씨", None),
    "メディヒール": ("Mediheal", "엘앤피코스메틱", None),
    "MEDIHEAL": ("Mediheal", "엘앤피코스메틱", None),
    "ドクターエルシア": ("Dr.Althea", "닥터엘시아", None),
    "DR.ALTHEA": ("Dr.Althea", "닥터엘시아", None),
    "トコボ": ("TOCOBO", "토코보", None),
    "TOCOBO": ("TOCOBO", "토코보", None),
    "イズントゥリー": ("Isntree", "이즈앤트리", None),
    "ISNTREE": ("Isntree", "이즈앤트리", None),
    "ミクスーン": ("mixsoon", "믹순", None),
    "MIXSOON": ("mixsoon", "믹순", None),
    "ピュリト": ("Purito", "퓨리토", None),
    "PURITO": ("Purito", "퓨리토", None),
    "セリマックス": ("Celimax", "셀리맥스", None),
    "CELIMAX": ("Celimax", "셀리맥스", None),
    "ドクタージャルト": ("Dr.Jart", "에스티로더", None),
    "DR.JART": ("Dr.Jart", "에스티로더", None),
    "サムバイミー": ("SOME BY MI", "썸바이미", None),
    "SOMEBYMI": ("SOME BY MI", "썸바이미", None),
    "ヒンス": ("hince", "아모레퍼시픽", "아모레퍼시픽"),
    "HINCE": ("hince", "아모레퍼시픽", "아모레퍼시픽"),
}


def _norm(s):
    s = htmlmod.unescape(s or "")
    s = re.sub(r"公式|\s+", "", s)
    return s.upper()


def match_brand(brand_txt, title):
    """브랜드 칸(정확일치) → 제목 안 별칭(포함) 순으로 찾는다."""
    key = _norm(brand_txt)
    if key in BRANDS:
        return key
    tn = _norm(title)
    for k in BRANDS:
        if len(k) >= 3 and k in tn:
            return k
    return None


def fetch():
    req = urllib.request.Request(URL, headers=ua(referer="https://www.qoo10.jp/", doc=True))
    with urllib.request.urlopen(req, timeout=40) as r:
        raw = r.read()
    t = raw.decode("utf-8", "replace")
    if "Bestsellers" not in t and "ランキング" not in t:
        raise RuntimeError(f"예상 밖 응답 {len(t)}B")
    return t


def parse(t):
    items = []
    for gno, blk in re.findall(r'<li id="g_(\d+)">(.*?)</li>', t, re.S):
        rk = re.search(r'class="rank">\s*(\d+)\s*<', blk)
        if not rk:
            continue
        brand = re.search(r'class="txt_brand"[^>]*title="([^"]*)"', blk)
        title = re.search(r'class="tt"[^>]*title="([^"]*)"', blk)
        prc = re.search(r'<div class="prc">(.*?)</div>', blk, re.S)
        p0 = p = None
        if prc:
            d = re.search(r"<del[^>]*>\s*([\d,]+)円", prc.group(1))
            s = re.search(r"<strong[^>]*>\s*([\d,]+)円", prc.group(1))
            nums = [int(x.replace(",", "")) for x in re.findall(r"([\d,]+)円", prc.group(1))]
            if d: p0 = int(d.group(1).replace(",", ""))
            if s: p = int(s.group(1).replace(",", ""))
            if p is None and nums: p = nums[-1]
            if p0 is None and nums: p0 = nums[0]
        rv = re.search(r'review_total_count[^>]*>\s*\(?([\d,]+)', blk)
        ga = re.search(r"GA_Front\.Click\('([^']*)'\)", blk)
        kr = bool(ga and "#KR#" in ga.group(1))
        off = 'class="official"' in blk
        bt = htmlmod.unescape(brand.group(1)) if brand else ""
        tt = htmlmod.unescape(title.group(1)) if title else ""
        key = match_brand(bt, tt)
        items.append({"r": int(rk.group(1)), "g": gno, "b": bt[:30], "t": tt[:70],
                      "p": p, "p0": p0, "rv": int(rv.group(1).replace(",", "")) if rv else None,
                      "kr": kr, "off": off, "key": key})
    items.sort(key=lambda x: x["r"])
    return items


def load_block(html):
    m = re.search(r"^const QOO10 = (\{.*?\});$", html, re.M | re.S)
    if not m:
        return None, None
    try:
        return json.loads(m.group(1)), m
    except json.JSONDecodeError:
        return None, m


def main():
    dry = "--dry-run" in sys.argv
    today = datetime.datetime.now(KST).strftime("%Y-%m-%d")
    html = open(HTML, encoding="utf-8").read()
    old, m = load_block(html)
    old = old or {"kr": [], "brands": []}
    out = copy.deepcopy(old)
    cutoff = (datetime.datetime.now(KST) - datetime.timedelta(days=DAYS)).strftime("%Y-%m-%d")

    try:
        t = fetch()
        items = parse(t)
    except Exception as e:
        note_health("Qoo10", f"수집 실패: {type(e).__name__}: {str(e)[:120]}")
        print("[Qoo10] 실패:", e); sys.exit(1)
    if len(items) < N * 0.5:
        note_health("Qoo10", f"항목 {len(items)}개뿐 — 페이지 구조 변경 의심")
        print(f"[Qoo10] 항목 {len(items)}개뿐"); sys.exit(1)
    note_health("Qoo10", None)

    krn = sum(1 for x in items if x["kr"])
    print(f"[Qoo10] 뷰티 톱{len(items)} · 한국발 {krn}({krn*100//len(items)}%) · {today}")
    # 한국발 비중 시계열
    out["kr"] = [x for x in (out.get("kr") or []) if x["d"] != today and x["d"] >= cutoff] + \
                [{"d": today, "kr": krn, "n": len(items)}]

    # 브랜드별 집계
    agg = {}
    for x in items:
        if not x["key"]:
            continue
        canon, owner, stock = BRANDS[x["key"]]
        a = agg.setdefault(canon, {"brand": canon, "owner": owner, "stock": stock, "jp": x["b"] or x["key"],
                                   "c": 0, "best": None, "rev": 0, "ranks": []})
        a["c"] += 1; a["ranks"].append(x["r"]); a["rev"] += (x["rv"] or 0)
        a["best"] = x["r"] if a["best"] is None else min(a["best"], x["r"])
    by = {b["brand"]: b for b in (out.get("brands") or [])}
    for canon, a in agg.items():
        b = by.setdefault(canon, {"brand": canon, "owner": a["owner"], "stock": a["stock"], "jp": a["jp"], "hist": []})
        b["owner"], b["stock"], b["jp"] = a["owner"], a["stock"], a["jp"]
        b["hist"] = [h for h in b["hist"] if h["d"] != today and h["d"] >= cutoff] + \
                    [{"d": today, "c": a["c"], "best": a["best"], "rev": a["rev"], "ranks": sorted(a["ranks"])[:8]}]
    # 오늘 안 보인 브랜드는 '0·권외' 점을 남겨 이탈이 보이게 (이미 이력이 있는 브랜드만)
    for canon, b in by.items():
        if canon not in agg and b.get("hist"):
            b["hist"] = [h for h in b["hist"] if h["d"] != today and h["d"] >= cutoff] + \
                        [{"d": today, "c": 0, "best": None, "rev": 0, "ranks": []}]
    out["brands"] = sorted(by.values(), key=lambda b: (b["stock"] is None, -(b["hist"][-1]["c"] if b["hist"] else 0)))
    for b in out["brands"]:
        h = b["hist"][-1] if b["hist"] else {}
        print(f"  {b['brand']:18} {b['owner']:10} 진입 {h.get('c',0):2} · 최고 {h.get('best') or '-':>3} · 리뷰합 {h.get('rev',0):,}")
    out["top"] = [{k: x[k] for k in ("r", "g", "b", "t", "p", "p0", "rv", "kr", "off")} |
                  ({"brand": BRANDS[x["key"]][0], "stock": BRANDS[x["key"]][2]} if x["key"] else {}) for x in items]
    out["n"] = len(items); out["url"] = URL; out["cat"] = "ビューティ"
    out["note"] = ("Qoo10 JP 뷰티 카테고리 베스트셀러 톱200(판매 기반 순위). 한국발 = 상품 원산/발송 KR 표시. "
                   "브랜드 매칭은 일본 표기 사전(BRANDS) 기준 — 사전 밖 한국 브랜드는 '한국발'에만 센다.")

    cmp_old = {k: v for k, v in old.items() if k not in ("asOf", "top")}
    cmp_new = {k: v for k, v in out.items() if k not in ("asOf", "top")}
    if dry:
        print("[dry-run] 저장 안 함"); return
    if cmp_old == cmp_new and m:
        print("[Qoo10] 변동 없음 — 파일 그대로"); return
    out["asOf"] = datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    block = "const QOO10 = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";"
    if m:
        html = html[:m.start()] + block + html[m.end():]
    else:
        anchor = re.search(r"^const TREND = ", html, re.M)
        if not anchor:
            print("삽입 위치(const TREND)를 못 찾았습니다"); sys.exit(1)
        html = html[:anchor.start()] + block + "\n" + html[anchor.start():]
    open(HTML, "w", encoding="utf-8").write(html)
    print(f"[Qoo10] QOO10 블록 갱신 ({len(block)//1024}KB · 브랜드 {len(out['brands'])})")


if __name__ == "__main__":
    main()
