# -*- coding: utf-8 -*-
"""녹십자웰빙 편입분을 index.html 에 주입(멱등) — 원격 최신 index.html 위에 다시 얹을 때 쓴다(CLAUDE.md '합치지 말고 다시 주입').
DATA 행 · MY_EST 한 줄 · <script src="js/gcwbmodel.js"> · GCWBMODEL 블록(gcwb_block.py)."""
import re, subprocess, sys
HTML = "public/index.html"
s = open(HTML, encoding="utf-8").read()
ROW = ('{"rank": 12.9, "pick2": "", "sector": "소비재", "sub": "미용", "name": "녹십자웰빙", "score": null, "fairMktcap": null, '
       '"rev27": null, "op27": null, "eps27": null, "thesis": "라이넥(태반주사제 점유율 80%) 9월 공급가 +20%·27년 IV 고용량 허가 vs 상품 매출 급증'
       '(이익률 약 17%)으로 매출총이익률 47→40%. 이니보 중국 허가(지분법 관계기업)는 주당 수백 원 수준(추적 전용)"}')
k = s.find("const DATA"); e = s.find("\n", k); line = s[k:e]
if '"name": "녹십자웰빙"' not in line:
    assert line.endswith("]};"); s = s[:k] + line[:-3] + ", " + ROW + "]};" + s[e:]
if '"녹십자웰빙": { "2026.12"' not in s:
    i = s.find('  "에이피알": { "2026.12"'); j = s.find("\n", i)
    s = s[:j + 1] + '  "녹십자웰빙": { "2026.12": {rev:57.4, op:3.9} },   // 2026-11-02 분기 손익 모델(gcwbmodel.js) 기본값 — 4Q 판관비 계절성·상품 저마진 반영 · 판가 3개월분 2.5\n' + s[j + 1:]
if 'js/gcwbmodel.js' not in s:
    s = s.replace('<script src="js/aprmodel.js"></script>', '<script src="js/aprmodel.js"></script>\n<script src="js/gcwbmodel.js"></script>', 1)
open(HTML, "w", encoding="utf-8").write(s)
subprocess.run([sys.executable, "gcwb_block.py"], check=True)
print("injected")
