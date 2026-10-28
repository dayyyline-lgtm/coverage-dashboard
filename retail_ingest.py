# -*- coding: utf-8 -*-
"""산업통상부 '주요 유통업체 매출 동향'(월간) -> index.html 의  const RETAIL = {...};   (2026-10-28)

유통 종목(신세계·롯데쇼핑·현대백화점·BGF리테일·GS리테일) 종목 페이지 손익 탭의 '산업부 유통업체 매출동향' 섹션 재료.
수집은 사용자 PC 크롬 예약 작업('유통업체 매출동향 월간 수집')이 한다 — 붙임(hwpx/pdf)이 크롬으로만 읽힌다.
그 작업이 붙임에서 읽은 원숫자(raw JSON)를 이 스크립트에 넘기면, 레벨·품목 실액을 계산해 블록에 한 달을 붙이고
트래커 DB(claude.ai 아티팩트)에 쓸 문서를 out 파일로 내놓는다. 계산 규칙은 여기 하나에만 둔다.

  python3 retail_ingest.py --raw raw_2610.json            # 한 달 추가(같은 달이 있으면 갈아 끼움)
  python3 retail_ingest.py --raw raw_2610.json --check    # 검증·계산만, 파일 안 씀
  python3 retail_ingest.py --seed DIR                     # DIR/*.json(월 문서)로 블록을 처음 만든다

raw JSON 모양(전부 대상 월 값, %):
  {"ym":"26.10", "release":"2026-11-25 11:00 (10월호)", "ev":"…"(없으면 생략),
   "head":{"전체":x,"오프라인":x,"온라인":x}, "chan":{"B":x,"M":x,"C":x,"S":x},      # 본문 업태별 표
   "yoy":{"M":[9],"B":[10],"C":[8],"S":[8],"O":[10],"F":[8]},                          # 붙임 행(소계·합계 포함) · O 는 아래 순서로 바꿔서
   "sh":{"M":[9],"B":[10],"C":[8],"S":[8]}, "sh_prev":{…같은 모양, 전월 행},             # 붙임 비중 행(소계·합계 열 포함 그대로)
   "kpi":{"M":{"구매건수":x,"구매단가":x,"점포당 매출":x}, "B":{…}, "C":{"구매건수","구매단가","점포 증가율","점포당 매출"}, "S":{…}},
   "comp":{"편의점":x,"온라인":x}, "stores":{"M":374,…}(선택)}
  yoy.O 순서 = [가전/전자, 도서/문구, 패션/의류, 화장품, 아동/유아, 스포츠, 식품, 생활/가구, 서비스/기타, 합계]
  (붙임 온라인 표는 [가전, 도서, 패션, 스포츠, 화장품, 아동, 식품, 생활, 서비스, 합계] 순이다.)
"""
import argparse, datetime, glob, json, os, re, sys

KST = datetime.timezone(datetime.timedelta(hours=9))
HTML = "public/index.html"
TRACKER = "https://claude.ai/artifact/5FBywc16SNyf6fzqZhEbJp"
NAMES = {"B": ["잡화", "여성정장", "여성캐주얼", "남성의류", "아동스포츠", "가정용품", "명품", "식품"],
         "C": ["생활용품", "잡화", "담배등", "가공식품", "즉석신선"],
         "M": ["가전문화", "의류", "가정생활", "스포츠", "잡화", "기타", "식품"],
         "S": ["일상용품", "생활잡화", "농수축산", "신선조리", "가공식품"]}
# 붙임 비중 행에서 품목 열 위치(소계·합계 열 제외) — NAMES 순서와 같다
SH_IDX = {"M": [0, 1, 2, 3, 4, 5, 7], "B": [0, 1, 2, 3, 4, 5, 6, 8], "C": [0, 1, 2, 4, 5], "S": [0, 1, 3, 4, 5]}
NCOL = {"M": 9, "B": 10, "C": 8, "S": 8, "O": 10, "F": 8}
TOT = {"M": 8, "B": 9, "C": 7, "S": 7}   # YoY 행의 합계 열
NOTE = ("산업통상부 주요 유통업체 매출 동향(월간 보도자료 붙임) · 레벨 조원(조사표본 기준) — '24.01~'26.07 은 점포당 매출×점포수 앵커"
        "(편의점·마트 '25.11 이전 4사 환산), '26.08~ 은 전년 같은 달 레벨×(1+공식 YoY) · 품목 = 레벨×원문 비중")


def ym_prev(ym, k=1):
    y, m = int(ym[:2]), int(ym[3:])
    m -= k
    while m < 1:
        y -= 1; m += 12
    return f"{y:02d}.{m:02d}"


def load_block(html):
    m = re.search(r"^const RETAIL = (\{.*?\});$", html, re.M | re.S)
    return (json.loads(m.group(1)) if m else None), m


def write_block(html, m, blk):
    line = "const RETAIL = " + json.dumps(blk, ensure_ascii=False, separators=(",", ":")) + ";"
    if m:
        return html[:m.start()] + line + html[m.end():]
    a = re.search(r"^const ECOS = \{.*?\};$", html, re.M | re.S)   # 처음엔 ECOS 바로 아래에 둔다
    if not a:
        sys.exit("ECOS 블록을 못 찾아 RETAIL 을 넣을 자리가 없다")
    return html[:a.end()] + "\n" + line + html[a.end():]


def items_from(sh_row, ch, level):
    vals = [sh_row[i] for i in SH_IDX[ch]]
    s = sum(vals)
    return {n: round(level * v / s, 3) for n, v in zip(NAMES[ch], vals)}, s


def check(raw):
    bad = []
    for ch, n in NCOL.items():
        if len(raw["yoy"].get(ch) or []) != n:
            bad.append(f"yoy.{ch} 열 수 {len(raw['yoy'].get(ch) or [])} ≠ {n}")
    for ch in "MBCS":
        if len(raw["sh"].get(ch) or []) != NCOL[ch]:
            bad.append(f"sh.{ch} 열 수 {len(raw['sh'].get(ch) or [])} ≠ {NCOL[ch]}")
            continue
        s = sum(raw["sh"][ch][i] for i in SH_IDX[ch])
        if abs(s - 100) > 0.35:
            bad.append(f"sh.{ch} 품목 비중 합 {s:.1f} ≠ 100")
        y = (raw["yoy"].get(ch) or [None] * NCOL[ch])[TOT[ch]]
        c = (raw.get("chan") or {}).get(ch)
        if y is not None and c is not None and abs(y - c) > 0.15:
            bad.append(f"{ch} 붙임 합계 {y} ≠ 본문 업태별 {c}")
    for k in ("전체", "오프라인", "온라인"):
        if (raw.get("head") or {}).get(k) is None:
            bad.append(f"head.{k} 없음")
    return bad


def ingest(blk, raw):
    by = {d["ym"]: d for d in blk["months"]}
    ym = raw["ym"]
    py = ym_prev(ym, 12)
    if py not in by:
        sys.exit(f"작년 같은 달 {py} 레벨이 블록에 없다")
    L = {ch: round(by[py]["L"][ch] * (1 + raw["yoy"][ch][TOT[ch]] / 100), 3) for ch in "BCMS"}
    I = {}
    for ch in "BCMS":
        I[ch], _ = items_from(raw["sh"][ch], ch, L[ch])
    doc = {"ym": ym, "L": L, "I": I,
           "yoy": {"head": raw["head"], **{ch: raw["yoy"][ch] for ch in "MBCSOF"}},
           "kpi": raw.get("kpi") or {}, "src": raw.get("release", "")}
    if raw.get("ev"):
        doc["ev"] = raw["ev"]
    comp = raw.get("comp") or {}
    if comp.get("편의점"):
        doc["T26"] = round(L["C"] / (comp["편의점"] / 100), 1)
        if comp.get("온라인"):
            doc["ON"] = round(doc["T26"] * comp["온라인"] / 100, 1)
    if raw.get("stores"):
        doc["stores"] = raw["stores"]
    # 전월 비중이 수정됐으면 전월 품목만 다시 나눈다(레벨은 그대로)
    revised = None
    pm = ym_prev(ym)
    if raw.get("sh_prev") and pm in by:
        p = by[pm]; changed = False; newI = {}
        for ch in "BCMS":
            row = raw["sh_prev"].get(ch)
            if not row or len(row) != NCOL[ch]:
                newI[ch] = p["I"][ch]; continue
            cand, _ = items_from(row, ch, p["L"][ch])
            old_sh = {n: p["I"][ch][n] / p["L"][ch] * 100 for n in NAMES[ch] if p["I"][ch].get(n) is not None}
            new_sh = {n: cand[n] / p["L"][ch] * 100 for n in NAMES[ch]}
            if any(abs(old_sh.get(n, 0) - new_sh[n]) > 0.2 for n in NAMES[ch]):
                changed = True; newI[ch] = cand
            else:
                newI[ch] = p["I"][ch]
        if changed:
            p = dict(p); p["I"] = newI; revised = p; by[pm] = p
    by[ym] = doc
    blk["months"] = [by[k] for k in sorted(by)]
    now = datetime.datetime.now(KST)
    blk["asOf"] = now.strftime("%Y-%m-%d %H:%M KST")
    blk["latest"] = blk["months"][-1]["ym"]
    blk["release"] = raw.get("release", blk.get("release", ""))
    return doc, revised


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw"); ap.add_argument("--seed"); ap.add_argument("--check", action="store_true")
    ap.add_argument("--out", default="retail_out.json")
    a = ap.parse_args()
    html = open(HTML, encoding="utf-8").read()
    blk, m = load_block(html)
    if a.seed:
        ms = [json.load(open(f, encoding="utf-8")) for f in sorted(glob.glob(os.path.join(a.seed, "*.json")))]
        blk = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "latest": ms[-1]["ym"],
               "release": "2026-10-28 11:00 (9월호)", "tracker": TRACKER, "note": NOTE, "months": ms}
        open(HTML, "w", encoding="utf-8").write(write_block(html, m, blk))
        print(f"[RETAIL] 시드 {len(ms)}개월 ({ms[0]['ym']}~{ms[-1]['ym']})")
        return
    if not a.raw:
        sys.exit("--raw 또는 --seed")
    if not blk:
        sys.exit("RETAIL 블록이 없다 — --seed 먼저")
    raw = json.load(open(a.raw, encoding="utf-8"))
    bad = check(raw)
    if bad:
        print("[RETAIL] 검증 실패: " + " / ".join(bad)); sys.exit(2)
    doc, revised = ingest(blk, raw)
    out = {"doc": doc, "revised_prev": revised}
    print(f"[RETAIL] {doc['ym']} 레벨 " + " ".join(f"{k}={v}" for k, v in doc["L"].items())
          + (f" · 전월 {revised['ym']} 품목 비중 수정 반영" if revised else ""))
    if a.check:
        print(json.dumps(out, ensure_ascii=False)[:1500]); return
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    open(HTML, "w", encoding="utf-8").write(write_block(html, m, blk))
    print(f"[RETAIL] 블록 갱신 · DB 용 문서 -> {a.out}")


if __name__ == "__main__":
    main()
