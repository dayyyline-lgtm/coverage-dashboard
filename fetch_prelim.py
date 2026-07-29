# -*- coding: utf-8 -*-
"""
잠정실적 자동 수집 — DART '영업(잠정)실적(공정공시)'에서 매출액·영업이익을 끌어온다.

네이버 재무 API 는 정식 보고서(분기/반기/사업보고서)가 올라와야 실적을 준다(분기말+45일).
그 전에 회사가 공시로 먼저 내는 '잠정실적'을 DART 에서 받아 index.html 의 PRELIM 에 넣어 두면,
실적 프리뷰 '발표완료' 가 발표 즉시 컨센 스냅샷과 비교(서프라이즈)된다.
정식 실적이 API 에 잡히면 화면이 자동으로 그쪽(apiAct)을 우선하므로 PRELIM 은 자연히 물러난다.

  document.xml 파싱: '매출액/영업이익 ... 당해실적 <숫자>' (억원). 분기는 당기 종료월(03/06/09/12).
  단위는 시리즈(LIVE.cons.series)와 맞춰 십억원으로 저장(= 억원/10).

  python fetch_prelim.py            # 수집·기록
  python fetch_prelim.py --dry-run  # 출력만
"""
import io, re, json, sys, time, zipfile, datetime
from fetch_events import DART_API_KEY, get, corp_map

HTML = "public/index.html"


def _const(html, name, arr=False):
    op, cl = (r"\[", r"\]") if arr else (r"\{", r"\}")
    m = re.search(r"const %s\s*=\s*(%s.*?%s)\s*;" % (re.escape(name), op, cl), html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None      # 손으로 쓴 JS 리터럴(따옴표 없는 키 등)은 파싱 불가 → 새로 시작


def _codes(html):
    live = _const(html, "LIVE") or {}
    data = _const(html, "DATA") or {}
    names = [r["name"] for r in (data.get("records") or [])]
    return {nm: ((live.get("stocks") or {}).get(nm) or {}).get("code") for nm in names}


def _num(s):
    try:
        return float(str(s).replace(",", "").strip())
    except Exception:
        return None


_UNIT = {"원": 1e-8, "천원": 1e-5, "백만원": 1e-2, "억원": 1.0, "십억원": 10.0}   # → 억원 배수


def parse_prelim(doc):
    """공정공시 문서에서 매출액·영업이익 '당해실적' + 분기(YYYYMM) 추출. 값은 억원으로 정규화.
       단위(백만원/억원/원…)는 회사마다 달라 문서에서 직접 감지해 환산한다."""
    txt = re.sub(r"<[^>]+>", " ", doc)
    txt = re.sub(r"\s+", " ", txt)
    um = re.search(r"단위\s*[:：]?\s*(십억원|백만원|억원|천원|원)", txt)
    mult = _UNIT.get(um.group(1)) if um else None      # 단위 못 찾으면 신뢰 불가 → None

    def after(kw):
        m = re.search(re.escape(kw) + r"\s*당해실적\s*([\-\d,]+)", txt)
        v = _num(m.group(1)) if m else None
        return (v * mult) if (v is not None and mult) else None

    rev, op = after("매출액"), after("영업이익")
    q = None
    for m in re.finditer(r"20\d\d[.\-](0[369]|12)[.\-](30|31)", txt):   # 분기말 일자
        q = re.sub(r"[.\-]", "", m.group(0))[:6]; break
    return rev, op, q, (um.group(1) if um else None)


def _quarter_from_date(rd):
    """폴백: 접수일(YYYYMMDD) → 직전 분기말. 잠정은 분기 끝나고 1~2달 안에 낸다."""
    if len(rd) < 6:
        return None
    y, mo = int(rd[:4]), int(rd[4:6])
    return {1: f"{y-1}12", 2: f"{y-1}12", 4: f"{y}03", 5: f"{y}03",
            7: f"{y}06", 8: f"{y}06", 10: f"{y}09", 11: f"{y}09"}.get(mo)


def _put(html, obj):
    block = "const PRELIM = " + json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + ";"
    pat = re.compile(r"const PRELIM\s*=\s*\{.*?\};", re.S)
    if not pat.search(html):
        raise RuntimeError("index.html 에서 const PRELIM 블록을 못 찾음")
    return pat.sub(lambda m: block, html, count=1)


def main():
    if not DART_API_KEY:
        print("DART_API_KEY 없음 — 스킵"); return
    html = open(HTML, encoding="utf-8").read()
    prelim = dict(_const(html, "PRELIM") or {})     # 기존 값 유지(수집 실패해도 안 지움)
    consSnap = (_const(html, "LIVE") or {}).get("consSnap") or {}
    cm = corp_map()
    end = datetime.date.today()
    start = end - datetime.timedelta(days=75)
    found = 0
    for nm, code in _codes(html).items():
        cc = cm.get(code) if code else None
        if not cc:
            continue
        try:
            lst = json.loads(get(
                f"https://opendart.fss.or.kr/api/list.json?crtfc_key={DART_API_KEY}"
                f"&corp_code={cc}&bgn_de={start:%Y%m%d}&end_de={end:%Y%m%d}&page_count=100").decode("utf-8"))
        except Exception as e:
            print(f"  [{nm}] 목록 실패: {str(e)[:50]}"); continue
        cand = [it for it in (lst.get("list") or [])
                if "잠정" in it.get("report_nm", "") and "실적" in it.get("report_nm", "")]
        if not cand:
            continue
        it = sorted(cand, key=lambda x: x.get("rcept_dt", ""))[-1]
        try:
            raw = get(f"https://opendart.fss.or.kr/api/document.xml?crtfc_key={DART_API_KEY}"
                      f"&rcept_no={it['rcept_no']}", 40)
            z = zipfile.ZipFile(io.BytesIO(raw))
            doc = z.read(z.namelist()[0]).decode("utf-8", "replace")
        except Exception as e:
            print(f"  [{nm}] 문서 실패: {str(e)[:50]}"); continue
        rev, op, q, unit = parse_prelim(doc)
        q = q or _quarter_from_date(it.get("rcept_dt", ""))
        if (rev is None and op is None) or not q:
            print(f"  [{nm}] 파싱 실패(rev={rev} op={op} q={q} 단위={unit})"); continue
        # 십억원(시리즈 단위)으로 환산
        rv10 = round(rev / 10, 1) if rev is not None else None
        ov10 = round(op / 10, 1) if op is not None else None
        # sanity — 발표 전 컨센 스냅샷이 있어야(발표완료에 뜨려면 필수) + 값이 컨센의 0.4~2.6배 범위.
        # 공정공시는 회사마다 단위·양식이 달라 오파싱이 잦아, 컨센과 크게 어긋나면 버린다.
        cs = (consSnap.get(nm) or {}).get(q)
        if not cs:
            print(f"  [{nm}] {q} 잠정 감지했으나 컨센 스냅샷 없음 — 보류"); continue
        chk = None
        if rv10 and cs.get("rev"):
            chk = rv10 / cs["rev"]
        elif ov10 and cs.get("op") and cs["op"] > 0:
            chk = ov10 / cs["op"]
        if chk is None or not (0.4 <= chk <= 2.6):
            print(f"  [{nm}] {q} 오파싱 의심(컨센대비 {chk}) — 버림 (rev={rev} op={op} 단위={unit})"); continue
        prelim.setdefault(nm, {})[q] = {"rev": rv10, "op": ov10}
        found += 1
        rv = f"{rev:,.0f}" if rev is not None else "—"
        ov = f"{op:,.0f}" if op is not None else "—"
        print(f"  {nm} {q} 잠정: 매출 {rv} · 영업익 {ov} 억원 (단위 {unit}, {it['rcept_dt']})")
        time.sleep(0.3)

    if "--dry-run" in sys.argv:
        print(json.dumps(prelim, ensure_ascii=False)); return
    if not found:
        print("잠정 공시 없음 — index.html 그대로 둠"); return
    open(HTML, "w", encoding="utf-8").write(_put(html, prelim))
    print(f"[OK] PRELIM 갱신 — 잠정 {found}건")


if __name__ == "__main__":
    main()
