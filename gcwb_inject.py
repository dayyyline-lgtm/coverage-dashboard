# -*- coding: utf-8 -*-
"""녹십자웰빙 편입분을 index.html 에 주입(멱등) — 원격 최신 index.html 위에 다시 얹을 때 쓴다(CLAUDE.md '합치지 말고 다시 주입').
DATA 행 · MY_EST 한 줄 · <script src="js/gcwbmodel.js"> · GCWBMODEL 블록(gcwb_block.py)."""
import re, subprocess, sys
HTML = "public/index.html"
s = open(HTML, encoding="utf-8").read()
ROW = ('{"rank": 12.9, "pick2": "", "sector": "소비재", "sub": "미용", "name": "녹십자웰빙", "score": 5.5, "fairMktcap": 239.0, '
       '"rev27": null, "op27": null, "eps27": null, "thesis": "라이넥(태반주사, 매출총이익률 약 75%) 9월 공급가 +20%가 27년 이익을 끌지만 2Q·3Q 선매입이라 4Q·1H27 물량은 쉰다. 성장은 상품(마운자로 등 이익률 약 22%)이 끌어 매출총이익률 47→40%. 적정 시총 2,390억 = 27E 지분법·파생 제외 순이익 19.7십억 × 12배 + 이니바이오"}')
k = s.find("const DATA"); e = s.find("\n", k); line = s[k:e]
if '"name": "녹십자웰빙"' not in line:
    assert line.endswith("]};"); s = s[:k] + line[:-3] + ", " + ROW + "]};" + s[e:]
if '"녹십자웰빙": { "2026.12"' not in s:
    i = s.find('  "에이피알": { "2026.12"'); j = s.find("\n", i)
    s = s[:j + 1] + '  "녹십자웰빙": { "2026.12": {rev:55.8, op:6.3} },   // 2026-11-03 분기 손익 모델(gcwbmodel.js) 기본값 — 라이넥 75%·기타 61%·상품 22% · 판관비 고정비(3Q 수준 × 4Q 배수) + 변동비\n' + s[j + 1:]
if 'js/gcwbmodel.js' not in s:
    s = s.replace('<script src="js/aprmodel.js"></script>', '<script src="js/aprmodel.js"></script>\n<script src="js/gcwbmodel.js"></script>', 1)
open(HTML, "w", encoding="utf-8").write(s)
subprocess.run([sys.executable, "gcwb_block.py"], check=True)
print("injected")
