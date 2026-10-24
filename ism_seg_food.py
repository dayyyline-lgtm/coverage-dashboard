"""음식료·유통 부문 파서(ISM) — 2026-10-24 조사(scratchpad ism_C) · 원문 2025.03~2026.06 로 검산
삼양식품·농심·빙그레·CJ제일제당·KT&G·신세계·롯데쇼핑·현대백화점·BGF리테일·GS리테일"""
import re

from ism_lib import *  # noqa: F401,F403
import ism_lib as L

_TB = re.compile(r"<TABLE[^>]*>(.*?)</TABLE>", re.S)


def _rows(tb):
    rows = []
    for tr in re.findall(r"<TR[^>]*>(.*?)</TR>", tb, re.S):
        cs = [cell(c) for c in re.findall(r"<T[DHE][^>]*>(.*?)</T[DHE]>", tr, re.S)]
        if any(cs):
            rows.append(cs)
    return rows


def _unit(t, pos):
    """표 바로 앞(3천 자 안)의 '(단위 : 천원)' → 원 단위 배수."""
    ms = list(re.finditer(r"단위\s*[:：]?\s*(천원|백만원|억원|원)", t[max(0, pos - 3000):pos + 400]))
    return {"천원": 1e3, "백만원": 1e6, "억원": 1e8, "원": 1.0}.get(ms[-1].group(1) if ms else "천원", 1e3)


def _find(t, must, anchor=None, nth=0, deny=()):
    """앵커 뒤(없으면 문서 처음부터) 표 중 must 글자를 다 담고 deny 글자는 없는 nth 번째 → (행 목록, 단위배수)."""
    st = t.find(anchor) if anchor else 0
    if st < 0:
        return None, None
    for m in _TB.finditer(t, st):
        rows = _rows(m.group(1))
        if len(rows) < 2:
            continue
        flat = " ".join(" ".join(r) for r in rows)
        if all(x in flat for x in must) and not any(x in flat for x in deny):
            if nth:
                nth -= 1
                continue
            return rows, _unit(t, m.start())
    return None, None


def _vals(rows, pats):
    """이름이 pats(공백·기호 무시) 중 하나인 첫 숫자 줄 → 숫자 칸 원문 목록."""
    ks = [L._k(p) for p in pats]
    for lab, v in labeled(rows):
        if L._k(lab) in ks:
            return v
    return None


def _first_n(v, n, u):
    return [num(x, u) for x in (v or [])[:n]]


def _region_order(rows, home=("대한민국", "한국", "국내")):
    """지역이 열인 표의 머리 → 값 칸 순서의 지역 이름(본국 → '외국' 자리에 다음 줄 나라들 → 조정 …)."""
    order = []
    for r in rows:
        if any(L._isnum(c) and c.strip() not in ("-", "−") for c in r):
            break
        names = [c.strip() for c in r if c.strip() and not re.fullmatch(r"(지역|지역\s*합계|부문의 합계|영업부문|부문|구\s*분|부문계|합\s*계)", c.strip())]
        if not order:
            if any(h in names for h in home):
                order = names
        elif "외국" in order:
            i = order.index("외국")
            order[i:i + 1] = names
    return order


# ── 음식료 ────────────────────────────────────────────────────────────────────
@seg("삼양식품")
def p_samyang(t, q):
    """매출실적(품목별) 수출·내수 + 주석 '외부 고객으로부터의 수익' 지역(한국·미국·중국·일본·인니·유럽)"""
    d = {}
    rows, u = _find(t, ["면스낵", "수 출", "내 수"], "매출실적")
    if rows:
        exp, tot, flag = None, None, False
        for r in rows:
            if any(L._k(c) == "소계" for c in r):
                flag = True
            v = [c for c in r if L._isnum(c) and c.strip() not in ("-", "−")]
            lab = next((c for c in reversed([c for c in r if not L._isnum(c)]) if c.strip()), "")
            if flag and exp is None and L._k(lab) == "수출" and v:
                exp = num(v[0], u)
            if v:
                tot = num(v[0], u) if L._k(r[0]) == "합계" else tot
        if exp is not None and tot:
            d["수출"] = [exp, None]
            d["내수"] = [round(tot - exp, 4), None]       # 내수 = 합계(물류용역·기타 포함) − 수출
    rows, u = _find(t, ["미국", "중국"], "외부 고객으로부터의 수익에 대한 공시")
    if rows:
        order = _region_order(rows)
        v = _vals(rows, ["수익(매출액)", "수익", "외부고객으로부터의 수익", "부문별수익"])
        nm = {"대한민국": "R한국", "미국": "R미국", "중국": "R중국", "일본": "R일본", "인도네시아": "R인니",
              "유럽": "R유럽", "싱가포르": "R싱가포르", "싱가폴": "R싱가포르"}
        if v:
            for j, a in enumerate(order):
                if a in nm and j < len(v) - 1:                # 마지막 칸은 합계 — 빈 칸(싱가포르)이 빠지면 그 뒤 이름은 버린다
                    d[nm[a]] = [num(v[j], u), None]
    return d, "cum"


@seg("농심")
def p_nongshim(t, q):
    """주석 '사업지역부문별 영업정보' — 지역별 외부매출·부문영업손익(한국·중국·미국·캐나다·일본·호주·베트남·유럽·러시아)"""
    rows, u = _find(t, ["미국", "중국", "외부고객"], "사업지역부문별 영업정보")
    if not rows:
        return {}, "cum"
    order = _region_order(rows)
    rv = _vals(rows, ["외부고객으로부터의 수익", "외부고객으로부터의수익"])
    op = _vals(rows, ["부문영업손익", "부문영업이익"])
    nm = {"한국": "R한국", "중국": "R중국", "미국": "R미국", "미국(*)": "R미국", "캐나다": "R캐나다", "일본": "R일본",
          "호주": "R호주", "베트남": "R베트남", "유럽": "R유럽", "러시아": "R러시아"}
    d = {}
    if rv and len(rv) >= len(order):
        for j, a in enumerate(order):
            if a in nm:
                d[nm[a]] = [num(rv[j], u), num(op[j], u) if op and j < len(op) else None]
        for k in ("R유럽", "R러시아"):                        # 유럽 2025Q2 · 러시아 2026Q2 신설 — 없던 분기는 0(누적 차분이 끊기지 않게)
            d.setdefault(k, [0.0, 0.0])
    return d, "cum"


@seg("빙그레")
def p_binggrae(t, q):
    """주석 영업부문(단일 부문)의 제품군 수익 — 냉장(우유·유음료)·냉동(아이스크림 등)"""
    rows, u = _find(t, ["냉장", "냉동"], "영업부문에 대한 공시")
    if not rows:
        return {}, "cum"
    v = _vals(rows, ["수익", "수익(매출액)", "매출액"])
    if not v:
        return {}, "cum"
    ht = head_text(rows)
    a, b = (1, 3) if "3개월" in ht else (0, 1)      # 반기·3분기 = [3개월, 누적] 쌍 → 누적
    return {"냉장": [num(v[a], u), None], "냉동": [num(v[b], u), None]}, "cum"


@seg("CJ제일제당")
def p_cj(t, q):
    """주석 영업부문 — 식품·바이오·물류(CJ대한통운) 외부매출·영업이익(F&C 는 2025 중 중단영업)"""
    def one(nth):
        rows, u = _find(t, ["식품", "바이오", "물류", "영업이익"], "영업부문에 대한 공시", nth=nth, deny=("Feed",))
        if not rows:
            return {}
        ext = _vals(rows, ["수익", "수익(매출액)", "순매출액"])
        op = _vals(rows, ["영업이익(손실)", "영업이익"])
        if not ext or not op:
            return {}
        if "3개월" in head_text(rows):                      # 반기·3분기: [식품 3개월, 누적, 바이오 3개월, 누적, 물류 3개월, 누적, …]
            r = [num(ext[j], u) for j in (1, 3, 5)]
            o = [num(op[j], u) for j in (1, 3, 5)]
        elif _vals(rows, ["내부매출액"]) or len(ext) < 8:      # 1분기: '수익' = 외부매출
            r, o = [num(x, u) for x in ext[:3]], [num(x, u) for x in op[:3]]
        else:                                                # 사업보고서: '수익' = 총액 → 부문별 제거액(4칸 뒤)을 더한다
            r = [round(num(ext[j], u) + num(ext[j + 4], u), 4) for j in range(3)]
            o = [num(x, u) for x in op[:3]]
        return {k: [r[j], o[j]] for j, k in enumerate(("식품", "바이오", "물류"))}
    d = one(0)
    if d and q[:4] >= "2026":
        pv = one(1)                                          # 전기 비교치(재작성 — F&C 제외·셀렉타 복귀)
        if pv:
            d["_prev"] = pv
    return d, "cum"


@seg("KT&G")
def p_ktg(t, q):
    """주석 '부문손익' — 담배·인삼·부동산·기타 외부매출·영업이익 + 지역별 정보(국내·해외)"""
    d = {}
    rows, u = _find(t, ["담배", "인삼", "부동산", "외부고객"], "부문손익")
    if rows:
        rv = _first_n(_vals(rows, ["외부고객으로부터의 수익", "외부고객으로부터의수익"]), 4, u)
        op = _first_n(_vals(rows, ["보고부문영업손익", "보고부문 영업손익", "영업이익(손실)"]), 4, u)
        if len(rv) == 4:
            for j, k in enumerate(("담배", "인삼", "부동산", "기타")):
                d[k] = [rv[j], op[j] if j < len(op) else None]
    rows, u = _find(t, ["국내", "해외", "매출액"], "지역별 정보")
    if rows:
        v = _vals(rows, ["매출액"])
        if v and len(v) >= 2:
            d["R한국"] = [num(v[0], u), None]
            d["R해외"] = [num(v[1], u), None]
    return d, "cum"


# ── 유통 ──────────────────────────────────────────────────────────────────────
@seg("신세계")
def p_shinsegae(t, q):
    """주석 영업부문 — 백화점·도소매(인터내셔날 등)·부동산·호텔·면세(DF) 순매출·영업이익 + 백화점·면세 총매출(GMV)"""
    rows, u = _find(t, ["백화점", "면세업", "순매출액", "특정매입원가"], "영업부문")
    if not rows:
        return {}, "cum"
    gm, nt, op = _vals(rows, ["총매출액", "총매출액(주1)"]), _vals(rows, ["순매출액"]), _vals(rows, ["영업이익(손실)", "영업이익"])
    if not nt or len(nt) < 11:
        return {}, "cum"
    # 칸: 본사·서울·수도권·그외지역·백화점 소계·도소매·부동산·호텔·면세·기타·제거·합계
    d = {}
    for k, j in (("백화점", 4), ("도소매", 5), ("부동산", 6), ("호텔", 7), ("면세", 8), ("기타", 9)):
        d[k] = [num(nt[j], u), num(op[j], u) if op and j < len(op) else None]
    if gm and len(gm) >= 9:
        d["백화점GMV"] = [num(gm[4], u), None]
        d["면세GMV"] = [num(gm[8], u), None]
    return d, "cum"


@seg("롯데쇼핑")
def p_lotte(t, q):
    """주석 영업부문 — 백화점·할인점·하이마트·슈퍼·홈쇼핑·컬처웍스·이커머스·기타 매출(연결조정 전)·영업이익"""
    rows, u = _find(t, ["할인점", "이커머스", "영업이익"], "영업부문에 대한 공시", deny=("비 중", "총자산", "매출내역"))
    if not rows:
        return {}, "cum"
    rv = _first_n(_vals(rows, ["매출", "매출액"]), 8, u)
    op = _first_n(_vals(rows, ["영업이익(손실)", "영업이익"]), 8, u)
    if len(rv) < 8:
        return {}, "cum"
    ks = ("백화점", "할인점", "하이마트", "슈퍼", "홈쇼핑", "컬처웍스", "이커머스", "기타")
    return {k: [rv[j], op[j] if j < len(op) else None] for j, k in enumerate(ks)}, "cum"


@seg("현대백화점")
def p_hyundai(t, q):
    """주석 '영업부문의 재무현황' — 백화점·면세점(현대디에프)·제조(지누스) 순매출·영업이익 + 총매출(GMV)"""
    rows, u = _find(t, ["백화점", "면세점", "총매출액"], "영업부문의 재무현황")
    if not rows:
        return {}, "cum"
    gm = _first_n(_vals(rows, ["총매출액"]), 3, u)
    nt = _first_n(_vals(rows, ["매출액"]), 3, u)
    op = _first_n(_vals(rows, ["계속영업이익(손실)", "영업이익(손실)", "영업이익"]), 3, u)
    if len(nt) < 3:
        return {}, "cum"
    d = {k: [nt[j], op[j] if j < len(op) else None] for j, k in enumerate(("백화점", "면세", "지누스"))}
    if len(gm) == 3:
        d["백화점GMV"] = [gm[0], None]
        d["면세GMV"] = [gm[1], None]
    return d, "cum"


@seg("BGF리테일")
def p_bgf(t, q):
    """'연결기준 매출실적 요약' — 편의점·물류·식품제조·광고/택배·기타 매출(내부거래 제거 전 · 영업이익 없음)"""
    d = grab(t, "연결기준 매출실적 요약", {"편의점": "편의점", "물 류": "물류", "물류": "물류", "식품 제조/유통": "식품제조",
                                         "광고/택배/전자상거래주1)": "광고택배", "광고/택배/전자상거래": "광고택배",
                                         "기타 부문": "기타", "기타부문": "기타"}, need=3, metrics=False)
    return {k: [v[0], None] for k, v in d.items()}, "cum"


@seg("GS리테일")
def p_gs(t, q):
    """주석 영업부문 — 편의점(GS25)·수퍼마켓(GS더프레시)·홈쇼핑·공통및기타(개발 포함) 매출·영업이익"""
    nm = {"편의점": "편의점", "수퍼마켓": "수퍼", "홈쇼핑": "홈쇼핑", "공통및기타": "기타", "개발": "기타"}
    d = grab_cols(t, "영업부문에 대한 공시", nm,
                  rev_row=("수익", "수익(매출액)", "외부고객으로부터의 수익", "매출액"),
                  op_row=("영업이익(손실)", "보고부문 영업이익(손실)", "영업이익"))
    return d, "cum"
