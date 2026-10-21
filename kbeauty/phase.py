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
import datetime as dt
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
    out = {"asOf": d["asOf"], "src": d["src"], "months": d["months"], "partial": d.get("partial"), "b": d["b"]}
    tt = build_tt(set(d["b"]))
    if tt:
        out["tt"] = tt
    return out


# ── 틱톡샵(미국) — FastMoss 샵 상세 '최근 180일' 일별(kbeauty/fastmoss.js 덤프 · data/phase/fm/<받은 날>.txt) ──
# 덤프의 브랜드키(grab 셋째 인자) → 위 아마존 바구니의 브랜드 키. 미국 공식 샵을 못 찾은 브랜드: 설화수·페리페라·구달·메디필(2026-10-21 검색 · 클리오 3개는 'Clio Official USA' 한 샵에 섞여 못 가른다)
TT_MAP = {"anua": "anua", "skin1004": "skin1004", "boj": "beauty of joseon", "celimax": "celimax", "dralthea": "dr.althea",
          "torriden": "torriden", "numbuzin": "numbuzin", "roundlab": "round lab", "vt": "vt cosmetics", "centellian": "centellian 24",
          "abib": "abib", "mixsoon": "mixsoon", "somebymi": "some by mi", "haruharu": "haruharu", "manyo": "ma:nyo", "axisy": "axis-y",
          "isntree": "isntree", "tonymoly": "tonymoly", "innisfree": "innisfree", "romand": "rom&nd", "medicube": "medicube",
          "missha": "missha", "dalba": "d'alba piedmont", "cosrx": "cosrx", "laneige": "laneige", "belif": "belif", "rejuran": "rejuran",
          "biodance": "biodance"}
TT_WEEKS = 25          # 180일 = 25주 + 5일 — 앞 자투리는 버리고 끝에서부터 7일씩


def _b36(s):
    return int(s, 36) if s else 0


def build_tt(keys):
    files = sorted((SRC / "fm").glob("20??-??-??.txt"))
    if not files:
        return None
    path = files[-1]
    S, D, fh = {}, {}, None
    for l in path.read_text(encoding="utf-8").splitlines():
        f = l.split("|")
        if f[0] == "FH":
            fh = f[2]
        elif f[0] == "S":
            S[f[1]] = {"k": f[3], "name": f[5]}
        elif f[0] == "D":
            D[f[1]] = {"d0": f[2], "u": [_b36(x) for x in f[3].split(",")], "v": [_b36(x) for x in f[4].split(",")]}
    if not fh or not D:
        return None
    end = dt.date.fromisoformat(fh) - dt.timedelta(days=1)       # 받은 날(UTC)은 진행 중 — 그 전날까지
    first = end - dt.timedelta(days=7 * TT_WEEKS - 1)
    b, miss = {}, []
    for sid, d in D.items():
        k = TT_MAP.get(S[sid]["k"])
        if not k or k not in keys:
            miss.append(S[sid]["k"])
            continue
        d0 = dt.date.fromisoformat(d["d0"])
        U, V = d["u"], list(d["v"])
        # 판매액 단가 오류 고침 — ingest.build_block 과 같은 규칙(위로 튄 날만 · 직전 28일 중앙 단가의 2.5배 초과 → 판매량 × 중앙 단가)
        fixed = []
        for i in range(len(U)):
            if U[i] <= 0:
                continue
            past = sorted(V[j] / U[j] for j in range(max(0, i - 28), i) if U[j] > 0 and V[j] > 0 and j not in fixed)
            if len(past) < 10:
                continue
            med = past[len(past) // 2]
            if med > 0 and V[i] / U[i] > 2.5 * med:
                V[i] = round(U[i] * med)
                fixed.append(i)
        wu, wv = [0] * TT_WEEKS, [0] * TT_WEEKS
        for i in range(len(U)):
            day = d0 + dt.timedelta(days=i)
            if day < first or day > end:
                continue
            w = (day - first).days // 7
            wu[w] += U[i]
            wv[w] += V[i]
        o = b.setdefault(k, {"n": [], "u": [0] * TT_WEEKS, "v": [0] * TT_WEEKS, "fx": 0})
        o["n"].append(S[sid]["name"])
        o["u"] = [a + c for a, c in zip(o["u"], wu)]
        o["v"] = [a + c for a, c in zip(o["v"], wv)]
        o["fx"] += len(fixed)
    weeks = [(first + dt.timedelta(days=7 * w + 6)).isoformat() for w in range(TT_WEEKS)]   # 주 끝날
    return {"asOf": fh, "end": end.isoformat(), "weeks": weeks, "nShop": len(D), "miss": sorted(set(miss)),
            "src": f"FastMoss 틱톡샵 미국 공식 샵 {len(D)}곳 · 샵 상세 '최근 180일' 일별 판매량 ({path.name[:10]} 수집)", "b": b}


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
