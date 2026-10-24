"""종목별 분기 손익 모델의 재료 -> index.html 의  const ISM = {...};   (2026-10-24 신설)

사용자 "종목마다 다 IS 모델링 — 컴투스·대원처럼 열심히 된 애들을 참고해서". 컴투스(C2MODEL)·대원(DWMODEL)·카카오게임즈(KGMODEL)·
디어유(DYMODEL)는 전용 수집기가 있고, 나머지 종목은 **이 수집기 하나**가 실적 칸을 채운다. 추정(동인·식)은 public/js/ism.js.

무엇을 받나
  q    {"2025Q1": {rev, opex, op, pbt, np, npp}, ...}   연결 분기 손익(십억원) — fetch_c2model.dart_quarters 그대로
                                                           (4Q = 사업보고서 연간 − 3Q 누적 · 다음 해 보고서의 재작성 비교치 우선)
  seg  {"2025Q1": {"부문명": [매출, 영업이익|null], ...}}  종목마다 다른 표(영업부문 · 매출실적 · 지역) — SEG 의 파서 함수가 읽는다
  src  {"2026-06": 접수번호, ...}                          처리한 정기보고서 — 새 보고서가 나왔을 때만 다시 받는다(평소 종목당 목록 1요청)

부문 표는 회사마다 모양이 달라 **종목마다 파서를 단다**(SEG). 표는 보고서 원문(document.xml)에서 앵커 문구로 찾고,
누적(1Q·반기·3Q·연간)이면 차분해서 분기로 바꾼다(fetch_dwmodel.py 와 같은 방식). 파서가 없는 종목은 q 만 싣는다.

python fetch_ism.py                 # 새 보고서가 나온 종목만
python fetch_ism.py --all           # 전 종목 다시(파서를 고쳤을 때)
python fetch_ism.py --only=삼양식품  # 한 종목만(쉼표로 여럿)
"""
import datetime, html as _html, io, json, re, sys, time, urllib.request, zipfile

import fetch_c2model as C2
from collector_health import note_health

KST = datetime.timezone(datetime.timedelta(hours=9))
HTML = "public/index.html"
Y0 = 2023                       # 실적 칸 첫 해(2024 전년비 계산용)
PERIOD = {"03": 1, "06": 2, "09": 3, "12": 4}
RC = {1: "11013", 2: "11012", 3: "11014", 4: "11011"}
SEG_FROM = "2025-03"            # 부문 원문은 이 보고서부터(파서는 2025~2026 양식으로 검산 · 그 앞 분기는 ism_seed)

# 전용 모델이 있는 종목은 받지 않는다(그쪽 수집기가 원본)
SKIP = {"컴투스", "대원미디어", "카카오게임즈", "디어유"}
# corpcode_cache.json 에 없는 종목(신규 상장 등) — DART company.json 으로 확인한 고유번호
CORP_EXTRA = {"아로마티카": "01381805",       # 2025-11 상장 — 캐시에 없음
              "탑코미디어": "00608699"}       # 134580 · 2026-10-08 사명 '엔키AX' 로 바뀜(이름으로 찾으면 안 나온다)


import glob, importlib, os
from ism_lib import *  # noqa: F401,F403  — 원문 도구·SEG
for _m in ("ism_seg_cos", "ism_seg_odm", "ism_seg_food", "ism_seg_game", "ism_seg_ent"):
    if os.path.exists(_m + ".py"):
        importlib.import_module(_m)

# ── 수집 ─────────────────────────────────────────────────────────────────────
def corps(html):
    cc = json.load(open("corpcode_cache.json", encoding="utf-8"))
    dec = json.JSONDecoder()
    D = dec.raw_decode(html, re.search(r"const DATA\s*=\s*", html).end())[0]
    L = dec.raw_decode(html, re.search(r"const LIVE\s*=\s*", html).end())[0]
    out = {}
    for r in D["records"]:
        nm = r["name"]
        if nm in SKIP:
            continue
        code = ((L.get("stocks") or {}).get(nm) or {}).get("code")
        corp = CORP_EXTRA.get(nm) or (cc.get(code) if code else None)
        if corp:
            out[nm] = corp
    return out


def reports(corp):
    u = (f"https://opendart.fss.or.kr/api/list.json?crtfc_key={C2.DART_KEY}&corp_code={corp}"
         f"&bgn_de={Y0}0101&pblntf_ty=A&page_count=100")
    d = json.loads(urllib.request.urlopen(u, timeout=25).read().decode())
    out = {}
    for r in sorted(d.get("list", []), key=lambda r: r["rcept_no"]):
        m = re.search(r"\((\d{4})\.(\d{2})\)", r["report_nm"])
        if m and m.group(2) in PERIOD:
            out[f"{m.group(1)}-{m.group(2)}"] = r["rcept_no"]
    return out


def segs_of(nm, rep, getdoc=None):
    """정기보고서마다 부문 표 → 분기 부문 손익.
       파서가 "_prev"(같은 표의 전년 같은 기간 = 재작성 비교치)를 주면 그 기준끼리 따로 차분해서 원래 값 위에 덮는다
       (LG생활건강 2026 부문 재분류처럼 — 기준이 다른 누적끼리 빼면 안 된다)."""
    fn = SEG.get(nm)
    if not fn:
        return {}, None, set()
    cum, rest, three = {}, {}, {}
    for ym, rc in sorted(rep.items()):
        if ym < SEG_FROM:
            continue
        q = f"{ym[:4]}Q{PERIOD[ym[5:]]}"
        try:
            d, kind = fn((getdoc or doc)(rc), q)
        except Exception as e:
            print(f"   [{nm}] {ym} 부문 파싱 실패: {type(e).__name__} {str(e)[:80]}")
            continue
        if not d:
            continue
        pv = d.pop("_prev", None)
        if pv:
            rest[qadd(q, -4)] = pv
        (cum if kind == "cum" else three)[q] = d
    out = cum_to_q(cum) if cum else {}
    restq = set()
    if rest:
        for k, v in cum_to_q(rest).items():
            out.setdefault(k, {}).update(v)
            restq.add(k)
    for k, v in three.items():
        out.setdefault(k, {}).update(v)
    return {k: out[k] for k in sorted(out)}, (fn.__doc__ or "").strip().splitlines()[0], restq


def seed_of(nm):
    """ism_seed/*.json — 조사 때 원문에서 뽑은 과거 분기 부문 값(파서가 못 읽는 옛 양식 분기). 파서 값이 있으면 그게 이긴다."""
    out = {}
    for f in sorted(glob.glob("ism_seed/*.json")):
        try:
            d = json.load(open(f, encoding="utf-8")).get(nm) or {}
        except Exception as e:
            print(f"   시드 {f} 읽기 실패: {e}")
            continue
        for q, v in d.items():
            if re.fullmatch(r"\d{4}Q[1-4]", q) and isinstance(v, dict):
                out.setdefault(q, {}).update(v)
            elif q == "_q" and isinstance(v, dict):          # 종목 단위로 둔 연결 손익 보정(CJ제일제당 F&C 재분류)
                for qq, f in v.items():
                    out.setdefault(qq, {})["_q"] = f
            elif q == "_fy_overlap" and isinstance(v, dict):  # 연간만 재작성된 분류 변경(JYP) — 새/옛 연간 비율
                out.setdefault("_fy", {}).update(v)
    return out


def load_block(html):
    m = re.search(r"^const ISM = (\{.*?\});$", html, re.M | re.S)
    return (json.loads(m.group(1)), m) if m else (None, None)


def main():
    if not C2.DART_KEY:
        note_health("분기 손익(ISM)", "DART 키 없음"); print("DART 키 없음"); sys.exit(1)
    html = open(HTML, encoding="utf-8").read()
    old, m = load_block(html)
    old = old or {"s": {}}
    only = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), None)
    allp = "--all" in sys.argv
    C = corps(html)
    out = {"s": dict(old.get("s") or {})}
    fails, done = [], 0
    for nm, corp in C.items():
        if only and nm not in only:
            continue
        prev = out["s"].get(nm) or {}
        try:
            rep = reports(corp)
        except Exception as e:
            fails.append(f"{nm}: 목록 {type(e).__name__}"); continue
        time.sleep(0.3)
        if not allp and prev.get("src") == rep and prev.get("q") and ((nm not in SEG and not seed_of(nm)) or prev.get("seg")):
            continue                                      # 새 보고서 없음
        try:
            q = C2.dart_quarters("CFS", Y0, corp)
        except Exception as e:
            fails.append(f"{nm}: 손익 {type(e).__name__}"); continue
        # 연결이 없는 분기(종속회사가 없던 때 · 별도만 공시)는 별도로 채운다 — 엔에프씨(연결 2023Q1 뿐)·네오팜(2026 별도만)·시프트업(상장 초 별도)
        lastRep = max(rep) if rep else None
        lastQ = f"{lastRep[:4]}Q{PERIOD[lastRep[5:]]}" if lastRep else None
        span = [f"{y}Q{i}" for y in range(Y0, int(lastQ[:4]) + 1) for i in range(1, 5)] if lastQ else []
        span = [x for x in span if x <= lastQ]
        ofsq = []
        if not q or any(x not in q for x in span if x >= min(q or {lastQ: 0})) or (q and max(q) < lastQ):
            qo = C2.dart_quarters("OFS", Y0, corp) or {}
            for k, v in qo.items():
                if k not in q:
                    q[k] = v
                    ofsq.append(k)
            q = {k: q[k] for k in sorted(q)}
        fs = "OFS" if q and len(ofsq) == len(q) else "CFS"
        seg, how, restq = segs_of(nm, rep)
        sd = seed_of(nm)
        qfix, basis, old = {}, {}, {}
        fy = sd.pop("_fy", None)
        for qq, v in sd.items():                          # 시드의 특수 키 — 연결 손익 보정·옛 분류 표시·옛 분류 값
            if "_q" in v:
                qfix[qq] = v.pop("_q")
            if "_basis" in v:
                basis[qq] = v.pop("_basis")
            if "_old" in v:
                old[qq] = v.pop("_old")
        if sd:                                            # 시드 위에 파서 값을 덮는다
            for k, v in seg.items():
                sd.setdefault(k, {}).update(v)
                if basis.get(k) == "old" and k in restq and not v.get("_basis"):
                    basis.pop(k, None)                    # 새 보고서의 재작성 비교치로 덮인 분기만 지금 분류('est' = 조사 추정 표시는 남긴다)
                    # ⚠ 그 분기 자기 보고서에서 읽은 값은 옛 분류 그대로다(LG생활건강 3Q25·4Q25) — 'old' 를 지우면 전년비가 재분류만큼 틀린다
                v.pop("_basis", None)
            seg = {k: sd[k] for k in sorted(sd) if sd[k]}
            how = how or "조사 시드(옛 분기)"
        for qq, f in qfix.items():                        # dart_quarters 가 잘못 내는 분기(중단영업 재분류 등)를 시드 값으로
            q[qq] = {**q.get(qq, {}), **{k: v for k, v in f.items() if v is not None}}
        if prev.get("q") and len(q) < len(prev["q"]) - 1:
            fails.append(f"{nm}: 분기 {len(prev['q'])}→{len(q)} — 이전 값 유지")
            continue
        out["s"][nm] = {"corp": corp, "fs": fs, "q": q, "seg": seg or prev.get("seg") or {}, "segHow": how or prev.get("segHow"),
                        "src": rep}
        if ofsq and fs == "CFS":
            out["s"][nm]["ofs"] = sorted(ofsq)              # 별도로 채운 분기(화면이 표시)
        if qfix:
            out["s"][nm]["qfix"] = sorted(qfix)             # 시드로 고친 분기
        if basis:
            out["s"][nm]["segBasis"] = basis                # "old" = 옛 분류 그대로인 분기
        if old:
            out["s"][nm]["segOld"] = old                    # 재작성 분기의 옛 분류 값(새/옛 비율용)
        if fy:
            out["s"][nm]["segFy"] = fy                      # 연간 새/옛 분류 겹침(새/옛 비율용)
        done += 1
        lq = sorted(q)[-1] if q else "-"
        print(f"[ISM] {nm:10} {fs} 분기 {len(q)}개(마지막 {lq} 매출 {q.get(lq, {}).get('rev')}) · 부문 {len(seg)}개 분기")
    note_health("분기 손익(ISM)", ("; ".join(fails[:4]) if len(fails) > max(3, len(C) // 4) else None))
    if not done and m:
        print("[ISM] 새 보고서 없음"); return
    out["asOf"] = datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    out = {"asOf": out["asOf"], "s": out["s"]}
    block = "const ISM = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";"
    if m:
        html = html[:m.start()] + block + html[m.end():]
    else:
        a = re.search(r"^const TREND = ", html, re.M)
        html = html[:a.start()] + block + "\n" + html[a.start():]
    open(HTML, "w", encoding="utf-8").write(html)
    print(f"[ISM] 블록 갱신 {len(block) // 1024}KB · 이번에 받은 종목 {done} · 실패 {len(fails)}")
    for f in fails:
        print("   ", f)


if __name__ == "__main__":
    main()
