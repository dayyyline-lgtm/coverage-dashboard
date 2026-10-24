"""손익 모델(ISM)용 Keepa 브랜드 판매 — ism_keepa/<키>.json -> index.html 의  const ISMKP = {...};   (2026-10-25)

화장품 바깥 회사의 아마존 판매(첫 대상: 현대백화점 지누스 = 브랜드 zinus, 미국). K뷰티(KBPH·KBCH)와 같은 방식이지만 바구니가 달라 따로 둔다.
수집은 사람 크롬의 keepa.com Product Finder 탭(Pro 로그인)에서 — 절차는 CLAUDE.md '지누스' 절. 덤프 JSON 을 ism_keepa/<키>.json 으로 저장하고 이걸 돌린다.
월별 u = 그달 마지막 7일 '지난달 구매' 배지 중앙값(아랫값 · 하한) · v = u × 그달 가격(달러). 진행 중인 달 = 최근 30일 한 달치.

python ism_keepa.py
"""
import glob, json, os, re

HTML = "public/index.html"


def main():
    b = {}
    for f in sorted(glob.glob("ism_keepa/*.json")):
        k = os.path.splitext(os.path.basename(f))[0]
        o = json.load(open(f, encoding="utf-8"))
        b[k] = {"asOf": o["asOf"], "months": o["months"], "partial": o.get("partial"), "nsku": o.get("nsku"),
                "u": o["u"], "v": o["v"], "pc": o.get("pc")}
        print(f"[Keepa] {k} {o['asOf']} · {o.get('nsku')}개 · 마지막 완결 달 {o['months'][-2]} ${o['v'][-2] / 1e6:,.1f}M")
    html = open(HTML, encoding="utf-8").read()
    mm = re.search(r"^const ISMKP = (\{.*?\});$", html, re.M | re.S)
    old = json.loads(mm.group(1)) if mm else {}
    if old.get("b") == b:
        print("[Keepa] 변동 없음"); return
    asof = max(x["asOf"] for x in b.values()) if b else None
    out = {"asOf": asof, "b": b, "note": "Keepa 미국 브랜드 월 판매(배지 아랫값) · v 달러 — 손익 모델 지표(지누스)"}
    block = "const ISMKP = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";"
    if mm:
        html = html[:mm.start()] + block + html[mm.end():]
    else:
        a = re.search(r"^const TREND = ", html, re.M)
        html = html[:a.start()] + block + "\n" + html[a.start():]
    open(HTML, "w", encoding="utf-8").write(html)
    print(f"[Keepa] ISMKP 블록 갱신 {len(block) // 1024}KB")


if __name__ == "__main__":
    main()
