"""history.csv → public/index.html 의 `const AMAZON` 블록만 교체.

루트 CLAUDE.md 의 데이터 파이프라인 규약을 그대로 따른다:
  - 자기 상수 블록만 정규식으로 갈아끼운다 (다른 상수는 절대 안 건드림)
  - 변동이 없으면 파일을 안 건드린다 (Cloudflare 무료 빌드 500회/월 절약)
  - 구조는 APPRANK 와 같은 관용구: {asOf, brands:[{brand, stock, hist:[...]}]}

매출은 **USD 로 저장**한다. 원화 환산은 페이지에서 `LIVE.market.FX.USDKRW`
(라이브 값)로 하면 되고, 그래야 환율이 굳지 않는다.
"""
import re
import csv
import json
import datetime
from pathlib import Path

BASE = Path(__file__).parent
INDEX = BASE.parent / "public" / "index.html"
HISTORY = BASE / "data" / "history.csv"

KEEP_DAYS = 180          # 시계열 보관 기간 (파일 비대화 방지)
TOP_N = 10               # 브랜드당 상세 제품 수

# 브랜드 → 운영사. 상장사면 stock 에 커버리지 종목명을 적는다.
# 비상장 브랜드를 '어느 종목 수혜'로 잇지 않는다 — 유통 관계를 확인하지 않은 추측이고,
# 그건 데이터가 아니라 판단이라 애널리스트 몫이다.
BRAND_STOCK = {
    "medicube":         {"stock": "에이피알",     "owner": "에이피알"},
    "COSRX":            {"stock": "아모레퍼시픽", "owner": "아모레퍼시픽"},
    "d'Alba":           {"stock": "달바글로벌",   "owner": "달바글로벌"},
    "Coreana":          {"stock": None,           "owner": "코리아나"},
    "Anua":             {"stock": None, "owner": "더파운더즈"},
    "BIODANCE":         {"stock": None, "owner": "바이오던스"},
    "Beauty of Joseon": {"stock": None, "owner": "구다이글로벌"},
    "Melaxin":          {"stock": None, "owner": "닥터멜락신"},
    "Purito":           {"stock": None, "owner": "퓨리토"},
}
# EUR·GBP → USD 교차환율. 원/달러만큼 안 움직여서 상수로 둔다.
FX_TO_USD = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27}


def _n(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def build():
    rows = list(csv.DictReader(open(HISTORY, encoding="utf-8")))
    if not rows:
        return None
    cutoff = (datetime.date.today() - datetime.timedelta(days=KEEP_DAYS)).isoformat()
    rows = [r for r in rows if r["date"] >= cutoff]

    # (브랜드, 날짜) 단위 집계
    agg = {}
    for r in rows:
        b, d, mk = r["brand"], r["date"], r["market"]
        u, p, bsr = _n(r.get("bought")), _n(r.get("price")), _n(r.get("bsr_main"))
        e = agg.setdefault((b, d), {"u": 0, "rev": 0.0, "n": 0, "bsr": None, "mk": {}})
        m = e["mk"].setdefault(mk, {"u": 0, "rev": 0.0, "n": 0, "bsr": None})
        e["n"] += 1
        m["n"] += 1
        if u:
            e["u"] += u
            m["u"] += u
            if p:
                usd = u * p * FX_TO_USD.get(r.get("currency"), 0)
                e["rev"] += usd
                m["rev"] += usd
        if bsr:
            for tgt in (e, m):
                if tgt["bsr"] is None or bsr < tgt["bsr"]:
                    tgt["bsr"] = int(bsr)

    latest = max(r["date"] for r in rows)
    brands = []
    for b in sorted({r["brand"] for r in rows}):
        hist = []
        for (bb, d), e in sorted(agg.items(), key=lambda kv: kv[0][1]):
            if bb != b:
                continue
            hist.append({"d": d, "u": e["u"], "rev": round(e["rev"]), "n": e["n"],
                         "bsr": e["bsr"],
                         "mk": {k: [v["u"], round(v["rev"]), v["n"], v["bsr"]]
                                for k, v in sorted(e["mk"].items())}})
        # 최신일 상위 제품
        today_rows = [r for r in rows if r["brand"] == b and r["date"] == latest]
        today_rows.sort(key=lambda r: -(_n(r.get("bought")) or 0))
        top = [{"mk": r["market"], "asin": r["asin"], "name": r["title"][:70],
                "bsr": int(_n(r["bsr_main"])) if _n(r.get("bsr_main")) else None,
                "sub": r.get("bsr_sub_cat") or None,
                "subR": int(_n(r["bsr_sub"])) if _n(r.get("bsr_sub")) else None,
                "u": int(_n(r["bought"])) if _n(r.get("bought")) else None,
                "p": _n(r.get("price")), "cur": r.get("currency")}
               for r in today_rows[:TOP_N]]
        brands.append({"brand": b, **BRAND_STOCK.get(b, {}), "hist": hist, "top": top})

    brands.sort(key=lambda x: -(x["hist"][-1]["rev"] if x["hist"] else 0))
    return {
        "asOf": datetime.datetime.now().strftime("%Y-%m-%d %H:%M KST"),
        "latest": latest,
        "markets": ["US", "UK", "DE", "FR", "IT", "ES"],
        "fxToUsd": FX_TO_USD,
        "note": ("아마존 6개국(US·UK·DE·FR·IT·ES) Beauty 기준. 판매량은 아마존이 상품페이지에 "
                 "공개하는 구간값의 하한이라 실제는 이보다 큽니다. 매출은 USD 기준."),
        "brands": brands,
    }


def main():
    data = build()
    if not data:
        print("[amazon] history.csv 가 비어 있어 주입 생략")
        return 0
    html = INDEX.read_text(encoding="utf-8")
    block = "const AMAZON = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";"
    pat = re.compile(r"const AMAZON\s*=\s*\{.*?\};", re.S)
    if pat.search(html):
        new = pat.sub(lambda _: block, html, count=1)
    else:
        # 최초 1회: LIVE 상수 앞에 새로 심는다
        anchor = html.index("const LIVE = ")
        new = html[:anchor] + block + "\n" + html[anchor:]
    if new == html:
        print("[amazon] 변동 없음 — 파일 안 건드림")
        return 0
    INDEX.write_text(new, encoding="utf-8")
    kb = len(block) / 1024
    print(f"[amazon] AMAZON 블록 갱신 ({kb:,.0f}KB, 브랜드 {len(data['brands'])}개, "
          f"기준일 {data['latest']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
