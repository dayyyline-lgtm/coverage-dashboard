# -*- coding: utf-8 -*-
"""K뷰티 브랜드 국면 지도(아마존 미국 · 32개 브랜드) → public/index.html 의 `const KBPH` 한 줄 (2026-10-21).

KBCH(회사 채널 모델)는 상장사 브랜드만 본다. 국면 지도는 '피어 안에서 몫이 늘고 있나'를 보려는 것이라
비상장 경쟁사(아누아·스킨1004·조선미녀·셀리맥스·닥터엘시아(Dr.Althea)·토리든 …)까지 같은 바구니에 넣는다.

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
# 덤프의 브랜드키(grab 셋째 인자) → 위 아마존 바구니의 브랜드 키. 미국 공식 샵을 못 찾은 브랜드: 설화수·메디필 · 페리페라·구달은 'Clio Official USA' 한 샵에 클리오와 섞여 있어 'clio' 로 통째로 넣는다(2026-10-21)
TT_MAP = {"anua": "anua", "skin1004": "skin1004", "boj": "beauty of joseon", "celimax": "celimax", "dralthea": "dr.althea",
          "torriden": "torriden", "numbuzin": "numbuzin", "roundlab": "round lab", "vt": "vt cosmetics", "centellian": "centellian 24",
          "abib": "abib", "mixsoon": "mixsoon", "somebymi": "some by mi", "haruharu": "haruharu", "manyo": "ma:nyo", "axisy": "axis-y",
          "isntree": "isntree", "tonymoly": "tonymoly", "innisfree": "innisfree", "romand": "rom&nd", "medicube": "medicube",
          "missha": "missha", "dalba": "d'alba piedmont", "cosrx": "cosrx", "laneige": "laneige", "belif": "belif", "rejuran": "rejuran",
          "biodance": "biodance", "equalberry": "eqqualberry",
          "clio": "clio"}   # Clio Official USA(Stride Leader Corporation) — 클리오·페리페라·구달이 한 샵에 섞여 있어 'clio' 칸에 통째로 넣는다(2026-10-21)
TT_MAXW = 52          # 주별 칸 최대 — '평소'를 아마존처럼 1년까지(덤프가 쌓이면 늘어난다)


def _b36(s):
    return int(s, 36) if s else 0


def build_tt(keys):
    """FastMoss 덤프를 **전부** 이어 붙인다(같은 샵·같은 날은 나중 덤프가 이긴다 · 덤프마다 받은 날과 그 뒤는 진행 중이라 버린다).
    FastMoss 는 180일만 주므로 매주 받은 덤프를 버리지 않고 이어야 '평소'·꼬리가 길어진다(2026-10-21)."""
    files = sorted((SRC / "fm").glob("20??-??-??.txt"))
    if not files:
        return None
    S, day, fhs = {}, {}, []
    for path in files:
        fh = None
        for l in path.read_text(encoding="utf-8").splitlines():
            f = l.split("|")
            if f[0] == "FH":
                fh = f[2]
            elif f[0] == "S":
                S[f[1]] = {"k": f[3], "name": f[5]}
            elif f[0] == "D" and fh:
                d0 = dt.date.fromisoformat(f[2])
                U, V = [_b36(x) for x in f[3].split(",")], [_b36(x) for x in f[4].split(",")]
                cut = dt.date.fromisoformat(fh)
                dd = day.setdefault(f[1], {})
                for i, (u, v) in enumerate(zip(U, V)):
                    t = d0 + dt.timedelta(days=i)
                    if t < cut:
                        dd[t] = (u, v)
        if fh:
            fhs.append(fh)
    if not day:
        return None
    end = max(max(dd) for dd in day.values() if dd)
    start = min(min(dd) for dd in day.values() if dd)
    nw = min(TT_MAXW, ((end - start).days + 1) // 7)
    first = end - dt.timedelta(days=7 * nw - 1)
    # 달 — 처음부터 끝까지 받은 달만 완결(첫 달은 1일부터 있어야) · 끝 달이 말일까지 안 찼으면 partial
    # 첫 달이 1일부터가 아니면(4/24~) 그 달 앞부분은 샵마다 '관측 첫 14일 평균 × 빠진 날수'로 채우고 mest 에 적는다(2026-10-21 · 잣대 통일 —
    # 3개월 비교(7~9월 ÷ 4~6월)에 4월이 필요하다. KBCH 의 kbShopQ 와 같은 채움). 그 달이 3개월 창에서 빠지면(11월~) 추정도 사라진다.
    m0 = dt.date(start.year, start.month, 1)
    gap = (start - m0).days
    mest = [m0.isoformat()[:7]] if gap > 0 else []
    months, m = [], m0
    while m <= end:
        months.append(m.isoformat()[:7])
        m = dt.date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    nxt = end + dt.timedelta(days=1)
    partial = months[-1] if months and nxt.month == end.month else None
    b, miss = {}, []
    for sid, dd in day.items():
        k = TT_MAP.get(S.get(sid, {}).get("k"))
        if not k or k not in keys:
            miss.append(S.get(sid, {}).get("k", sid))
            continue
        ds = sorted(dd)
        U = [dd[t][0] for t in ds]
        V = [dd[t][1] for t in ds]
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
        wu, wv = [0] * nw, [0] * nw
        mu, mv = [0] * len(months), [0] * len(months)
        if gap > 0 and ds and ds[0] == start:
            n14 = min(14, len(U))
            mu0, mv0 = sum(U[:n14]) / n14 * gap, sum(V[:n14]) / n14 * gap
        else:
            mu0 = mv0 = 0
        for t, u, v in zip(ds, U, V):
            if first <= t <= end:
                w = (t - first).days // 7
                wu[w] += u
                wv[w] += v
            ym = t.isoformat()[:7]
            if ym in months:
                j = months.index(ym)
                mu[j] += u
                mv[j] += v
        mu[0] += round(mu0)
        mv[0] += round(mv0)
        o = b.setdefault(k, {"n": [], "u": [0] * nw, "v": [0] * nw, "mu": [0] * len(months), "mv": [0] * len(months), "fx": 0})
        o["n"].append(S[sid]["name"])
        o["u"] = [a + c for a, c in zip(o["u"], wu)]
        o["v"] = [a + c for a, c in zip(o["v"], wv)]
        o["mu"] = [a + c for a, c in zip(o["mu"], mu)]
        o["mv"] = [a + c for a, c in zip(o["mv"], mv)]
        o["fx"] += len(fixed)
    weeks = [(first + dt.timedelta(days=7 * w + 6)).isoformat() for w in range(nw)]   # 주 끝날
    return {"asOf": fhs[-1], "end": end.isoformat(), "start": start.isoformat(), "weeks": weeks, "months": months, "partial": partial, "mest": mest,
            "nShop": len(day), "nDump": len(files), "miss": sorted(set(miss)),
            "src": f"FastMoss 틱톡샵 미국 공식 샵 {len(day)}곳 · 샵 상세 일별 판매량({start.isoformat()}~{end.isoformat()} · 덤프 {len(files)}개 이어 붙임)", "b": b}


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
