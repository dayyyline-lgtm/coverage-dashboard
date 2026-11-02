# -*- coding: utf-8 -*-
"""GC녹십자웰빙 분기 손익 모델의 재료 → index.html 의  const GCWBMODEL = {...};   (2026-11-02 신설 · 수기 갱신)

화면 = 종목 페이지 손익 탭 '분기 손익 — 라이넥·상품·판관비'(js/gcwbmodel.js 의 renderGcwbModel).
원자료 = gcwb/dart_raw.json — DART 정기보고서를 크롬으로 읽어 옮긴 값(백만원 · 판관비는 십억원 소수 첫째).
  is        연결 손익 3개월(4Q = 연간 − 3Q 누적 · 전기 = 다음 해 보고서의 재작성 비교치)
  laennec   'II.2 주요 제품 등에 관한 사항' 라이넥주 매출(누적 차분)
  sep_sales 'II.4 매출실적'(별도) 제품 전문의약품·제품 기타·상품 전문의약품·상품 건기식·상품 기타·합계 → 연결 − 별도 = 자회사·조정
  sga       연결 주석 '판매비와 관리비'(묶음은 renderGcwbModel 의 SGL 참고)
  util·prod 'II.3 생산 및 설비' 혁신공장 충전 가동시간·생산수량(누적 → 분기)
  bs·cb     연결 재무상태표·사채 주석
다음 보고서(3분기보고서 11월 중순)가 나오면 dart_raw.json 에 한 분기를 더 적고  python gcwb_block.py  — 블록만 바꾼다.
"""
import json, re, datetime, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
D = json.load(open("gcwb/dart_raw.json", encoding="utf-8"))
K = D["is_keys"]
q = {}
for k, v in D["is"].items():
    o = {kk: round(x / 1000, 3) for kk, x in zip(K, v)}
    if k in D["laennec"]: o["L"] = round(D["laennec"][k] / 1000, 3)
    s = D["sep_sales"].get(k)
    if s: o.update(prod=round((s[0] + s[1]) / 1000, 3), goods=round((s[2] + s[3] + s[4]) / 1000, 3), sep=round(s[5] / 1000, 3),
                     gq=[round(s[2] / 1000, 3), round(s[3] / 1000, 3), round(s[4] / 1000, 3)])   # 상품 전문의약품·건기식·기타
    if k in D["sga"]: o["sg"] = {kk: vv for kk, vv in D["sga"][k].items()}
    u = D["util"].get(k)
    if u: o["ut"] = {"amp": round(u["amp"][1] / u["amp"][0], 4), "vial": round(u["vial"][1] / u["vial"][0], 4)}
    inv = D["bs"]["재고자산"].get(k)
    if inv is not None: o["inv"] = round(inv / 10, 1)
    q[k] = o
p = D["prelim_2026Q3"]
blk = dict(asOf=datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), code="234690", q=q,
           p={"2026Q3": {"rev": p["rev"] / 1000, "op": p["op"] / 1000, "np": p["np"] / 1000, "src": p["src"]}},
           cb={"face": 20.0, "conv": 2.0, "left": 18.0, "px": 9478, "shares": 17.96, "note": D["cb"]["매도청구권"]},
           debt={"st": 44.2, "lt": 20.0}, rcp=D["rcp"])
line = "const GCWBMODEL = " + json.dumps(blk, ensure_ascii=False, separators=(",", ":")) + ";"
html = open(HTML, encoding="utf-8").read()
pat = re.compile(r"^const GCWBMODEL = .*?;$", re.M)
if pat.search(html):
    html = pat.sub(lambda m: line, html, count=1)
else:
    anchor = re.search(r"^const APRMODEL = .*?;$", html, re.M)
    html = html[:anchor.end()] + "\n" + line + html[anchor.end():]
open(HTML, "w", encoding="utf-8").write(html)
print("GCWBMODEL", len(line), "bytes ·", ", ".join(sorted(q)))
