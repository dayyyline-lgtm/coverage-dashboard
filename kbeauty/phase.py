# -*- coding: utf-8 -*-
"""K뷰티 브랜드 국면 지도(아마존 미국 · 32개 브랜드) → public/index.html 의 `const KBPH` 한 줄 (2026-10-21).

KBCH(회사 채널 모델)는 상장사 브랜드만 본다. 국면 지도는 '피어 안에서 몫이 늘고 있나'를 보려는 것이라
비상장 경쟁사(아누아·스킨1004·조선미녀·셀리맥스·닥터알떼아·토리든 …)까지 같은 바구니에 넣는다.

원재료: kbeauty/data/phase/<날짜>.json — Keepa Product Finder(웹 · 미국) 결과 표의 상품 객체를 브랜드 × 월로 합친 것.
  u   = 월 판매량(배지 'Bought in past month' 계단 이력의 그달 일수 가중 평균 · 구간 아랫값 → 하한)
  n1k = 그달 1천 개 이상 팔린 SKU 수
  nw  = 배지 첫 등장 12개월 이내 SKU 의 판매량(2024-08 부터 유효)
  pi  = 현재 바이박스가 ÷ 1년 평균가(판매량 가중)
  top1 = 7~9월 판매 1위 SKU 와 직전 완결 월 판매량
  마지막 달(partial)은 진행 중 — 화면에서 완결 월과 섞지 않는다.

점유율·두 축·칸·질 체크는 전부 화면(app.js renderKbPhase)에서 계산한다(파생값은 페이지에서 — CLAUDE.md).

  python3 kbeauty/phase.py            # 가장 최근 원재료로 블록 넣기
  python3 kbeauty/phase.py --dry      # 블록 크기만
"""
import argparse
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
INDEX = HERE.parent / "public" / "index.html"
SRC = HERE / "data" / "phase"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def latest():
    files = sorted(SRC.glob("20??-??-??.json"))
    if not files:
        raise SystemExit("kbeauty/data/phase 에 원재료가 없다")
    return files[-1]


def build(path):
    d = json.loads(path.read_text(encoding="utf-8"))
    n = len(d["months"])
    for k, b in d["b"].items():
        for f in ("u", "n1k", "nw"):
            if len(b[f]) != n:
                raise SystemExit(f"{k}.{f} 길이 {len(b[f])} ≠ 월 수 {n}")
    return {"asOf": d["asOf"], "src": d["src"], "months": d["months"], "partial": d.get("partial"), "b": d["b"]}


def inject(block):
    html = INDEX.read_text(encoding="utf-8")
    line = "const KBPH = " + json.dumps(block, ensure_ascii=False, separators=(",", ":")) + ";"
    pat = re.compile(r"^const KBPH = .*$", re.M)
    if pat.search(html):
        new = pat.sub(lambda _m: line, html, count=1)
    else:
        mk = re.search(r"^const KBCH = .*$", html, re.M) or re.search(r"^const AMZL = .*$", html, re.M)
        if mk:
            new = html[:mk.end()] + "\n" + line + html[mk.end():]
        else:
            at = html.index("const LIVE = ")
            new = html[:at] + line + "\n" + html[at:]
    if new == html:
        return False, len(line)
    INDEX.write_text(new, encoding="utf-8", newline="\n")
    return True, len(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    p = latest()
    block = build(p)
    if a.dry:
        print(f"[KBPH] {p.name} · 브랜드 {len(block['b'])} · {len(json.dumps(block, ensure_ascii=False)) // 1024}KB")
        return
    ch, size = inject(block)
    print(f"[KBPH] {'갱신' if ch else '변동 없음'} · {size // 1024}KB · {block['asOf']} · 브랜드 {len(block['b'])}")


if __name__ == "__main__":
    main()
