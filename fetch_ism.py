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

# 전용 모델이 있는 종목은 받지 않는다(그쪽 수집기가 원본)
SKIP = {"컴투스", "대원미디어", "카카오게임즈", "디어유"}
# corpcode_cache.json 에 없는 종목(신규 상장 등) — DART company.json 으로 확인한 고유번호
CORP_EXTRA = {}


# ── 원문 표 도구 ──────────────────────────────────────────────────────────────
_DOC = {}


def doc(rcept):
    """보고서 원문 본문(가장 큰 파일). 한 회차 안에서는 캐시."""
    if rcept in _DOC:
        return _DOC[rcept]
    b = urllib.request.urlopen(f"https://opendart.fss.or.kr/api/document.xml?crtfc_key={C2.DART_KEY}"
                               f"&rcept_no={rcept}", timeout=120).read()
    z = zipfile.ZipFile(io.BytesIO(b))
    t = z.read(max(z.namelist(), key=lambda n: z.getinfo(n).file_size)).decode("utf-8", errors="replace")
    _DOC[rcept] = t
    time.sleep(0.4)
    return t


def cell(c):
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", "", c))).strip()


def num(s, unit=1.0):
    """'1,234' · '(1,234)' · '△1,234' · '-' → 십억원(unit = 원 단위 배수: 천원 1e3 · 백만원 1e6 · 원 1)."""
    s = (s or "").replace(",", "").replace("\xa0", "").replace(" ", "").strip()
    if s in ("", "-", "−", "–"):
        return 0.0
    neg = (s.startswith("(") and s.endswith(")")) or s[:1] in ("△", "▲") or s.startswith("-")
    s = s.strip("()△▲-")
    try:
        v = float(s)
    except ValueError:
        return None
    return round((-v if neg else v) * unit / 1e9, 4)


def tables_after(t, anchor, n=3, span=60000, start=0):
    """앵커 문구 뒤의 표 n 개 → [[셀,…],…] 목록. 앵커가 없으면 []."""
    i = t.find(anchor, start)
    if i < 0:
        return []
    out = []
    for tb in re.findall(r"<TABLE[^>]*>(.*?)</TABLE>", t[i:i + span], re.S)[:n]:
        rows = []
        for tr in re.findall(r"<TR[^>]*>(.*?)</TR>", tb, re.S):
            cs = [cell(c) for c in re.findall(r"<T[DHE][^>]*>(.*?)</T[DHE]>", tr, re.S)]
            if any(cs):
                rows.append(cs)
        out.append(rows)
    return out


def unit_of(t, anchor):
    """앵커 근처의 '(단위 : 천원)' → 원 단위 배수."""
    i = t.find(anchor)
    seg = t[i:i + 4000] if i >= 0 else ""
    m = re.search(r"단위\s*[:：]?\s*(천원|백만원|억원|원)", seg)
    return {"천원": 1e3, "백만원": 1e6, "억원": 1e8, "원": 1.0}.get(m.group(1) if m else "천원", 1e3)


def qadd(q, n):
    k = int(q[:4]) * 4 + int(q[-1]) - 1 + n
    return f"{k // 4}Q{k % 4 + 1}"


def cum_to_q(cum):
    """{"2026Q2": {부문: [매출, 영업이익]}} 누적 → 분기(차분). Q1 은 그대로."""
    out = {}
    for q, d in cum.items():
        if q.endswith("Q1"):
            out[q] = d
            continue
        p = cum.get(qadd(q, -1))
        if not p:
            continue
        o = {}
        for k, (r, op) in d.items():
            if k in p:
                pr, pop = p[k]
                o[k] = [round(r - pr, 3) if r is not None and pr is not None else None,
                        round(op - pop, 3) if op is not None and pop is not None else None]
        out[q] = o
    return out


# ── 종목별 부문 파서 ─────────────────────────────────────────────────────────
# 함수(t, period_q) → {"부문": [매출, 영업이익|None]} 와 "cum"|"3m" 표시. 리서치 뒤 종목마다 붙인다.
SEG = {}


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


def segs_of(nm, rep):
    """정기보고서마다 부문 표 → 분기 부문 손익."""
    fn = SEG.get(nm)
    if not fn:
        return {}, None
    cum, three = {}, {}
    for ym, rc in sorted(rep.items()):
        q = f"{ym[:4]}Q{PERIOD[ym[5:]]}"
        try:
            d, kind = fn(doc(rc), q)
        except Exception as e:
            print(f"   [{nm}] {ym} 부문 파싱 실패: {type(e).__name__} {str(e)[:80]}")
            continue
        if not d:
            continue
        (cum if kind == "cum" else three)[q] = d
    out = cum_to_q(cum) if cum else {}
    out.update(three)
    return {k: out[k] for k in sorted(out)}, (fn.__doc__ or "").strip().split("\n")[0]


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
        if not allp and prev.get("src") == rep and prev.get("q") and (nm not in SEG or prev.get("seg")):
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
        seg, how = segs_of(nm, rep)
        if prev.get("q") and len(q) < len(prev["q"]) - 1:
            fails.append(f"{nm}: 분기 {len(prev['q'])}→{len(q)} — 이전 값 유지")
            continue
        out["s"][nm] = {"corp": corp, "fs": fs, "q": q, "seg": seg or prev.get("seg") or {}, "segHow": how or prev.get("segHow"),
                        "src": rep}
        if ofsq and fs == "CFS":
            out["s"][nm]["ofs"] = sorted(ofsq)              # 별도로 채운 분기(화면이 표시)
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
