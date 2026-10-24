"""ODM·유통·미용 부문 파서(ISM) — 2026-10-24 조사(scratchpad ism_B_odm) · 원문 2025.03~2026.06 로 검산"""
import re

from ism_lib import *  # noqa: F401,F403
import ism_lib as L


# ── 이 묶음 전용 도구 ─────────────────────────────────────────────────────────
def _lead(c, unit):
    """'67,059,662 (44,623)' 처럼 괄호 병기(천달러)가 붙은 칸 → 앞 숫자만."""
    c = (c or "").strip()
    m = re.match(r"^([\(△▲-]?[\d,]+(?:\.\d+)?\)?)(\s*\(.*\))?$", c)
    return num(m.group(1), unit) if m else None


def _row_vals(r, unit):
    return [v for v in (_lead(c, unit) for c in r) if v is not None]


def item_table(t, anchor, items, kinds, occ=0, ntab=4):
    """품목 × (수출/내수/소계) 표 → {품목: {구분: 값(첫 숫자 칸 = 당기 누적)}}.
       품목 칸은 첫 줄에만 있고 다음 줄들은 구분만 있으므로 '지금 품목'을 이어 간다. 구분이 없는 줄은 구분 ''."""
    i = find_occ(t, anchor, occ)
    if i < 0:
        return {}
    u = unit_at(t, i)
    ik, kk = {L._k(x): x for x in items}, {L._k(x): x for x in kinds}
    dash = lambda c: c.strip() in ("-", "−")
    for rows in tables_after(t, anchor, n=ntab, start=i):
        out, cur = {}, None
        for r in rows:
            js =[j for j, c in enumerate(r) if (_lead(c, 1) is not None or dash(c))]      # '-' = 0 (당기 칸이 비어도 자리를 지킨다)
            if not js:
                continue
            first = js[0]
            lab = [L._k(c) for c in r[:first]]
            it = next((ik[x] for x in lab if x in ik), None)
            if it:
                cur = it
            kd = next((kk[x] for x in lab if x in kk), "")
            if not cur:
                continue
            v = 0.0 if dash(r[first]) else _lead(r[first], u)
            out.setdefault(cur, {}).setdefault(kd, v)
        if len(out) >= 2:
            return out
    return {}


def geo_wide(t, anchor, occ=0, ntab=4):
    """'지역에 대한 공시'(나라가 열 · 머리가 두세 줄: 지역 → 본사 소재지 국가/외국 → 나라들) → {나라 이름: 값}, 합계.
       값 순서 = 본사 소재지 국가가 '외국' 앞이면 [본사, 나라들…, 합계], 뒤면 [나라들…, 본사, 합계]."""
    i = find_occ(t, anchor, occ)
    if i < 0:
        return {}, None
    u = unit_at(t, i)
    for rows in tables_after(t, anchor, n=ntab, start=i):
        head = []
        for r in rows:
            if any(L._isnum(c) and c.strip() not in ("-", "−") for c in r):
                break
            head.append([c for c in r if c.strip()])
        hr = next((h for h in head if "본사 소재지 국가" in h and "외국" in h), None)
        if not hr or not head:
            continue
        home_first = hr.index("본사 소재지 국가") < hr.index("외국")
        names = [c for c in head[-1] if c not in ("지역", "지역 합계")]
        lab = labeled(rows)
        if not lab:
            continue
        vals = [num(c, u) for c in lab[0][1]]
        order = (["본사 소재지 국가"] + names) if home_first else (names + ["본사 소재지 국가"])
        if len(vals) != len(order) + 1:
            continue
        return dict(zip(order, vals[:-1])), vals[-1]
    return {}, None


def fixed_geo(d, total, fixed):
    """나라 목록이 보고서마다 바뀌는 표 — 늘 있는 나라만 키로, 나머지는 R기타(= 합계 − 그 나라들)로 같은 정의를 지킨다.
       늘 있는 나라 중 하나라도 빠지면 그 보고서의 지역 값은 버린다(정의가 달라지므로)."""
    nk = {L._k(a): b for a, b in fixed.items()}
    out = {}
    for a, v in d.items():
        k = nk.get(L._k(a))
        if k:
            out[k] = (out.get(k) or 0) + (v or 0)
    if set(out) != set(fixed.values()) or total is None:
        return {}
    out["R기타"] = round(total - sum(out.values()), 4)
    return {k: [v, None] for k, v in out.items()}


# ── 종목 ───────────────────────────────────────────────────────────────────────
@seg("한국콜마")
def p_kolmar(t, q):
    """연결 주석 영업부문(화장품·의약품(HK이노엔)·식품·패키징 매출·영업이익) + 지역(한국·중국·미국·기타)"""
    d = grab_cols(t, "제품과 용역에 대한 공시", {"화장품": "화장품", "의약품": "의약품", "식품": "식품", "패키징": "패키징"})
    g, tot = geo_wide(t, "지역에 대한 공시")
    d.update(fixed_geo(g, tot, {"본사 소재지 국가": "R한국", "중국": "R중국", "미국": "R미국"}))
    return d, "cum"


@seg("코스맥스")
def p_cosmax(t, q):
    """연결 주석 지역(법인 소재지 · 내부거래 제거 전) — 국내·아시아(중국·인니·태국)·미국 매출"""
    i = find_occ(t, "지역에 대한 공시")
    if i < 0:
        return {}, "cum"
    u = unit_at(t, i)
    for rows in tables_after(t, "지역에 대한 공시", n=6, start=i):
        ht = head_text(rows)
        if not (("국내" in ht or "본사 소재지 국가" in ht) and "아시아" in ht and "미국" in ht):   # 2025 사업보고서는 '본사 소재지 국가 | 외국 → 아시아 | 미국'
            continue
        lab = [(a, v) for a, v in labeled(rows) if L._k(a) in ("매출액", "수익", "수익매출액", "외부매출액")]
        if lab and len(lab[0][1]) >= 4:
            v = [num(c, u) for c in lab[0][1]]
            return {"R국내": [v[0], None], "R아시아": [v[1], None], "R미국": [v[2], None]}, "cum"
    return {}, "cum"


S2_FIX = {"유럽연합(*1)": "R유럽", "EU(*1)": "R유럽", "미국": "R미국", "United States": "R미국", "영국": "R영국", "United Kingdom": "R영국",
          "아랍에미리트": "RUAE", "United Arab Emirates": "RUAE", "캐나다": "R캐나다", "Canada": "R캐나다",
          "말레이시아": "R말레이시아", "Malaysia": "R말레이시아", "본사 소재지 국가": "R한국", "Korea": "R한국"}


@seg("실리콘투")
def p_silicon2(t, q):
    """연결 주석 지역별 매출 — 유럽(EU)·미국·영국·UAE·캐나다·말레이시아·한국 + 기타(러시아·인니 등 = 합계 − 이들)"""
    g, tot = geo_wide(t, "지역에 대한 공시")
    if not g:                                             # 3Q 보고서는 세로형(영문 나라 이름)
        i = find_occ(t, "지역별 매출액")
        if i >= 0:
            u = unit_at(t, i)
            for rows in tables_after(t, "지역별 매출액", n=4, start=i):
                lab = labeled(rows)
                if sum(1 for a, _ in lab if L._k(a) in {L._k(x) for x in S2_FIX}) >= 4:
                    g = {a: num(v[0], u) for a, v in lab if L._k(a) != "합계"}
                    tot = next((num(v[0], u) for a, v in lab if L._k(a) == "합계"), None)
                    break
    fx = {}
    for a, k in S2_FIX.items():
        if L._k(a) in {L._k(x) for x in g}:
            fx[a] = k
    out = fixed_geo(g, tot, fx)
    need = {"R유럽", "R미국", "R영국", "RUAE", "R캐나다", "R말레이시아", "R한국"}
    return (out if need <= set(out) else {}), "cum"


@seg("제닉")
def p_genic(t, q):
    """연결 주석 지역별 매출 — 한국(바이오던스 등 국내 OEM)·유럽·북미·아시아"""
    d = grab(t, "지역별 매출", {"한국": "R한국", "아시아": "R아시아", "유럽": "R유럽", "북미": "R북미"}, need=3, metrics=False)
    return {k: [v[0], None] for k, v in d.items()}, "cum"


@seg("엔에프씨")
def p_nfc(t, q):
    """매출실적(별도) — 완제품(인디 브랜드 ODM)·소재(화장품 원료)·상품·기타"""
    it = item_table(t, "가. 매출실적", ["소재", "벌크", "완제품", "상품", "기타", "합계"], ["수출", "내수", "소계"])
    s = lambda k: (it.get(k) or {}).get("소계")
    if s("완제품") is None or s("소재") is None:
        return {}, "cum"
    return {"완제품": [s("완제품"), None], "소재": [s("소재"), None], "상품": [s("상품"), None],
            "기타": [round((s("벌크") or 0) + (s("기타") or 0), 4), None]}, "cum"


@seg("제이투케이바이오")
def p_j2kbio(t, q):
    """연결 주석 영업부문 — 화장품원료·임상서비스 매출 + 지역(한국·해외)"""
    d = grab(t, "영업부문별 매출액", {"화장품원료 제조 및 판매": "원료", "임상서비스": "임상"}, need=2, metrics=False)
    out = {k: [v[0], None] for k, v in d.items()}
    r = grab(t, "지역별 매출", {"대한민국": "R한국", "합계": "_t"}, need=2, metrics=False)
    if "R한국" in r and "_t" in r:
        out["R한국"] = [r["R한국"][0], None]
        out["R해외"] = [round(r["_t"][0] - r["R한국"][0], 4), None]
    return out, "cum"


@seg("파마리서치")
def p_pharmaresearch(t, q):
    """매출현황(연결) — 의료기기(리쥬란)·화장품·의약품 × 내수/수출"""
    it = item_table(t, "가. 매출현황", ["의료기기", "화장품", "의약품", "기타", "합계"], ["내 수", "수 출", "계"])
    g = lambda a, b: (it.get(a) or {}).get(b)
    if g("의료기기", "내 수") is None:
        return {}, "cum"
    return {"의료기기내수": [g("의료기기", "내 수"), None], "의료기기수출": [g("의료기기", "수 출"), None],
            "화장품내수": [g("화장품", "내 수"), None], "화장품수출": [g("화장품", "수 출"), None],
            "의약품": [g("의약품", "계"), None], "기타": [g("기타", "계"), None]}, "cum"


@seg("앨엔씨바이오")
def p_lncbio(t, q):
    """매출실적(별도) — 인체조직이식재(리투오·메가덤)·의료기기·기타(코스메슈티컬·제약·반품) · 연결과의 차이는 자회사"""
    it = item_table(t, "가. 매출실적", ["인체조직이식재", "의료기기", "코스메슈티컬", "제약", "기타", "반품충당부채", "합계"], ["수출", "내수", "소계"])
    s = lambda k: (it.get(k) or {}).get("소계")
    if s("인체조직이식재") is None:
        return {}, "cum"
    etc = sum((s(k) or 0) for k in ("코스메슈티컬", "제약", "기타")) + ((it.get("반품충당부채") or {}).get("") or 0)
    return {"인체조직": [s("인체조직이식재"), None], "의료기기": [s("의료기기"), None], "기타": [round(etc, 4), None]}, "cum"


@seg("그래피")
def p_graphy(t, q):
    """주요제품 현황(별도) — 레진(Tera Harz Clear·Tera Harz)·장비·기타(프린터·경화기·교정장치·교육)"""
    i = find_occ(t, "주요제품 등의 현황")
    if i < 0:
        return {}, "cum"
    u0 = unit_at(t, i)
    for rows in tables_after(t, "주요제품 등의 현황", n=3, start=i):
        raw = {L._k(a): v[0] for a, v in labeled(rows)}
        if "TeraHarzClear" not in raw or "합계" not in raw:
            continue
        # 2025 반기·3Q 보고서는 표기 단위('백만원')와 실제 숫자(천원·원)가 다르다 — 누적 매출이 0.5~200십억 안에 드는 단위를 고른다
        u = next((x for x in (u0, 1.0, 1e3, 1e6) if 0.5 <= (num(raw["합계"], x) or 0) <= 200), u0)
        lab = {k: num(v, u) for k, v in raw.items()}
        resin = (lab.get("TeraHarzClear") or 0) + (lab.get("TeraHarz") or 0)
        return {"레진": [round(resin, 4), None], "장비기타": [round(lab["합계"] - resin, 4), None]}, "cum"
    return {}, "cum"


@seg("리센스메디컬")
def p_recens(t, q):
    """연결 주석 지역별 매출 — 국내·아시아·미국·기타(유럽 포함)"""
    d = grab(t, "지역별 정보", {"국내": "R한국", "아시아": "R아시아", "미국": "R미국", "유럽": "R기타", "기타": "R기타"}, need=3, metrics=False)
    return {k: [v[0], None] for k, v in d.items()}, "cum"


@seg("티앤엘")
def p_tnl(t, q):
    """매출실적 — 창상치료재(하이드로콜로이드 여드름패치) 수출·내수 · 정형외과용 고정재 · 기타"""
    a = "1) 매출실적" if t.find("1) 매출실적") >= 0 else "매출실적"     # 2025 분기 보고서는 번호 없이 '매출실적'
    i = find_occ(t, a)
    if i < 0:
        return {}, "cum"
    u = unit_at(t, i)
    for rows in tables_after(t, a, n=2, start=i):
        heads = [j for j, r in enumerate(rows) if r and L._k(r[0]) in ("합계", "총계") and len(r) > 2 and L._k(r[1]) == "수출"]
        if len(heads) < 3:
            continue
        def nxt(j, lab):                                    # j 뒤 첫 '내수'·'소계' 줄 (2025 1Q 는 달러 괄호가 따로 한 줄)
            return next((k for k in range(j + 1, min(j + 5, len(rows))) if rows[k] and L._k(rows[k][0]) == lab), None)

        def trip(j):                                       # (수출, 내수, 소계, 소계 줄 위치)
            x = _row_vals(rows[j], u)
            jd = nxt(j, "내수")
            js = nxt(jd if jd is not None else j, "소계")
            d_ = _row_vals(rows[jd], u) if jd is not None else []
            s_ = _row_vals(rows[js], u) if js is not None else []
            return (x[0] if x else None, d_[0] if d_ else None, s_[0] if s_ else None, js)
        w, o = trip(heads[0]), trip(heads[1])
        j = next((k for k in range((o[3] or heads[1]) + 1, len(rows))
                  if rows[k] and L._k(rows[k][0]) == "기타" and len(rows[k]) > 1 and L._k(rows[k][1]) == "수출"), None)
        e = trip(j) if j is not None else (None, None, None, None)
        if w[0] is None or o[2] is None:
            continue
        return {"창상수출": [w[0], None], "창상내수": [w[1], None], "정형": [o[2], None], "기타": [e[2], None]}, "cum"
    return {}, "cum"
