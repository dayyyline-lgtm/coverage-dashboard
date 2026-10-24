"""게임·호텔·레저 부문 파서(ISM) — 2026-10-24 조사(scratchpad ism_E) · 원문 2025.03~2026.06 로 검산
크래프톤·NC·시프트업·데브시스터즈·펄어비스 · 호텔신라·롯데관광개발·파라다이스·GS피앤엘·서부T&D"""
import re

from ism_lib import *  # noqa: F401,F403
import ism_lib as L


def _n(s):
    """이름 정규화 — 공백·기호·각주 '(*1)'·'(주1)' 제거."""
    s = re.sub(r"\((?:\*|주)\s*\d*\)|\(\*\d*\)|\*\d*", "", s or "")
    return L._k(s)


def _tables(t, pred, start=0, n=1):
    """원문에서 pred(표 텍스트)를 만족하는 표 n 개 → [행…] 목록(앞에서부터)."""
    out = []
    for m in re.finditer(r"<TABLE[^>]*>(.*?)</TABLE>", t[start:], re.S):
        x = m.group(1)
        if not pred(x):
            continue
        rows = []
        for tr in re.findall(r"<TR[^>]*>(.*?)</TR>", x, re.S):
            cs = [L.cell(c) for c in re.findall(r"<T[DHE][^>]*>(.*?)</T[DHE]>", tr, re.S)]
            if any(cs):
                rows.append(cs)
        out.append((start + m.start(), rows))
        if len(out) >= n:
            break
    return out


def _cols(rows, names, rev_lab, op_lab=(), u=1e3):
    """부문·지역이 열인 표 — 머리 줄의 이름 순서대로 매출(rev_lab 줄)·영업이익(op_lab 줄) 숫자를 짝짓는다.
       머리에 '3개월'이 있으면 [3개월, 누적] 쌍이라 누적(2j+1)을 쓴다. 같은 키로 모이면 더한다."""
    nk = {_n(a): b for a, b in names.items()}
    hr = None
    for r in rows[:7]:
        cs = [c for c in r if c.strip()]
        js = [j for j, c in enumerate(cs) if _n(c) in nk]
        if len(js) >= 2:
            hr = [(_n(c) if _n(c) in nk else None) for c in cs[js[0]:]]     # 이름 없는 열(석유류·합계)도 자리를 지킨다
            break
    if not hr:
        return {}
    pair = "3개월" in head_text(rows)
    lab = labeled(rows)
    rk, ok = {_n(x) for x in rev_lab}, {_n(x) for x in op_lab}
    rv = next((v for a, v in lab if _n(a) in rk), None)
    op = next((v for a, v in lab if _n(a) in ok), None) if ok else None
    if not rv:
        return {}
    out = {}
    for j, h in enumerate(hr):
        if h is None:
            continue
        i = 2 * j + 1 if pair else j
        if i >= len(rv):
            continue
        r = num(rv[i], u)
        o = num(op[i], u) if op and i < len(op) else None
        key = nk[h]
        x = out.get(key)
        out[key] = [r, o] if not x else [(x[0] or 0) + (r or 0), None if (o is None or x[1] is None) else x[1] + o]
    return out


def _seg_rows(rows, segs, names, u):
    """부문 이름이 첫 칸에 한 번만 나오고 그 아래 지역·구분 줄이 이어지는 표(병합 칸) → {(부문, 이름): 첫 숫자(당기 누적)}."""
    out, cur = {}, None
    sk = {_n(a): b for a, b in segs.items()}
    nk = {_n(a): b for a, b in names.items()}
    for r in rows:
        c0 = _n(r[0]) if r else ""
        hit = next((sk[k] for k in sk if c0.startswith(k)), None)
        if hit:
            cur = hit
        txt = [c for c in r if c.strip() and not L._isnum(c)]
        nums = [c for c in r if L._isnum(c)]
        if not cur or not nums or not txt:
            continue
        nm = nk.get(_n(txt[-1]))
        if nm:
            out[(cur, nm)] = num(nums[0], u)
    return out


# ───────────────────────── 게임 ─────────────────────────

@seg("크래프톤")
def p_krafton(t, q):
    """연결 주석 '수익의 구분'(PC·모바일·콘솔·광고 및 콘텐츠·기타 매출) + 매출실적 게임 지역(한국·아시아·미주유럽·기타)"""
    d = {}
    i = t.find("수익의 구분")
    for _, rows in _tables(t, lambda x: "모바일" in x and "콘솔" in x and "PC" in x, start=max(i, 0), n=1):
        d = _cols(rows, {"PC": "PC", "모바일": "모바일", "콘솔": "콘솔", "광고 및 콘텐츠": "광고", "광고 및 컨텐츠": "광고",
                         "광고": "광고", "기타": "기타"},
                  ("고객과의 계약에서 생기는 수익", "고객과의계약에서생기는수익", "수익"), u=1e3)
    j = t.find("매출실적")
    if j >= 0:
        for _, rows in _tables(t, lambda x: "아메리카" in x and "아시아" in x, start=j, n=1):
            g = _seg_rows(rows, {"게임": "게임", "광고": "광고"},
                          {"대한민국": "R한국", "아시아": "R아시아", "아메리카/유럽": "R미주유럽", "기타": "R기타"}, unit_at(t, j))
            for (s, k), v in g.items():
                if s == "게임":
                    d[k] = [v, None]
    return d, "cum"


NC_PROD = {"리니지": "리니지", "아이온2": "아이온2", "기타 PC게임": "기타PC", "리니지M": "리니지M", "리니지2M": "리니지2M",
           "리니지W": "리니지W", "모바일 캐주얼": "캐주얼", "기타": "기타"}


@seg("NC")
def p_nc(t, q):
    """매출실적 게임별(리니지·아이온2·기타PC·리니지M·2M·W·모바일 캐주얼·기타 — 2026 양식) + 주석 지역(한국·대만·미국·일본·유럽·동남아)"""
    d = {}
    i = t.find("주요 서비스 등의 현황")
    for _, rows in _tables(t, lambda x: "리니지M" in x and "리니지W" in x, start=max(i, 0), n=1):
        # 2026 양식만(로열티 줄이 게임별로 녹은 표). 2025 옛 양식(로열티·온라인 게임 줄)은 시드가 채운다 — 기준이 달라 섞지 않는다
        if not any("기타 PC게임" in " ".join(r) or "모바일 캐주얼" in " ".join(r) for r in rows):
            break
        u = unit_at(t, i)
        nk = {_n(a): b for a, b in NC_PROD.items()}
        for r in rows:
            txt = [c for c in r if c.strip() and not L._isnum(c) and "%" not in c]
            nums = [c for c in r if L._isnum(c) and "%" not in c]
            if not txt or not nums:
                continue
            k = next((nk[_n(c)] for c in txt if _n(c) in nk), None)
            if k and k not in d:
                d[k] = [num(nums[0], u), None]
    j = t.find("지역별 정보")
    if j >= 0:
        for _, rows in _tables(t, lambda x: "대만" in x and "일본" in x and "한국" in x, start=j, n=1):
            r = _cols(rows, {"한국": "R한국", "일본": "R일본", "대만": "R대만", "미국": "R미국", "유럽": "R유럽",
                             "베트남": "R동남아", "싱가포르": "R동남아", "캐나다": "R기타"},
                      ("고객과의 계약에서 생기는 수익", "고객과의계약에서생기는수익", "외부고객으로부터의 수익", "수익"), u=1e3)
            d.update({k: [v[0], None] for k, v in r.items()})
    return d, "cum"


@seg("시프트업")
def p_shiftup(t, q):
    """사업의 내용 주요 제품(승리의 여신: 니케·스텔라 블레이드·기타) + 매출실적 지역(한국·아시아·미주·기타)"""
    d = grab(t, "주요 제품 등의 현황", {"승리의 여신: 니케": "니케", "스텔라 블레이드": "스텔라", "기타": "기타"}, need=2, metrics=False)
    d = {k: [v[0], None] for k, v in d.items()}
    r = grab(t, "매출실적", {"대한민국": "R한국", "아시아": "R아시아", "아메리카": "R미주", "유럽": "R기타", "기타": "R기타"},
             need=2, metrics=False)
    d.update({k: [v[0], None] for k, v in r.items()})
    return d, "cum"


@seg("데브시스터즈")
def p_devsisters(t, q):
    """매출실적 — 게임(국내·국외)·IP(상품·라이선스·TCG)·기타(벤처조합 보수)"""
    j = t.find("매출실적")
    if j < 0:
        return {}, "cum"
    for _, rows in _tables(t, lambda x: "국외" in x and "국내" in x and "소계" in x, start=j, n=1):
        g = _seg_rows(rows, {"게임": "게임", "IP": "IP", "기타": "기타", "합계": "합계"},
                      {"국내": "국내", "국외": "국외", "소계": "소계"}, unit_at(t, j))
        d = {}
        if ("게임", "국내") in g:
            d["게임국내"] = [g[("게임", "국내")], None]
        if ("게임", "국외") in g:
            d["게임국외"] = [g[("게임", "국외")], None]
        if ("IP", "소계") in g:
            d["IP"] = [g[("IP", "소계")], None]
        if ("기타", "소계") in g:
            d["기타"] = [g[("기타", "소계")], None]
        return d, "cum"
    return {}, "cum"


PA_REG = {"국내": "R한국", "미주/유럽": "R미주유럽", "미주ㆍ유럽 등": "R미주유럽", "미주·유럽 등": "R미주유럽", "아시아": "R아시아",
          "기타지역": "R기타", "중단영업": "중단"}


@seg("펄어비스")
def p_pearlabyss(t, q):
    """연결 주석 지역(국내·미주유럽·아시아·기타) 매출 — '중단'(CCP 매각, 음수 조정) 포함 · 전기 재작성치를 _prev 로"""
    d = grab(t, "지역에 대한 공시", PA_REG, need=3, metrics=False)
    d = {k: [v[0], None] for k, v in d.items()}
    if d and "중단" in d:                                       # 중단영업이 있는 보고서(2026~)는 전기 표도 재작성 기준
        pv = grab(t, "지역에 대한 공시", PA_REG, need=3, metrics=False, nth=1)
        if pv and "중단" in pv:
            d["_prev"] = {k: [v[0], None] for k, v in pv.items()}
    return d, "cum"


# ───────────────────────── 호텔·레저 ─────────────────────────

@seg("호텔신라")
def p_shilla(t, q):
    """연결 주석 영업부문(TR·호텔레저 매출·영업이익) + 지역(한국·아시아·미주 매출·영업이익)"""
    d = grab_cols(t, "영업부문에 대한 공시", {"TR부문": "TR", "호텔레저부문 등": "호텔레저", "호텔레저부문등": "호텔레저"},
                  rev_row=("총매출액", "매출액", "수익"), op_row=("영업손익", "영업이익"))
    r = grab_cols(t, "지역에 대한 공시", {"한국": "R한국", "아시아": "R아시아", "미주 등": "R미주"},
                  rev_row=("총매출액", "매출액", "수익"), op_row=("영업손익", "영업이익"))
    d.update(r)
    return d, "cum"


@seg("롯데관광개발")
def p_lottetour(t, q):
    """주요 제품(카지노·호텔·여행·리테일·인터넷 매출) + 주석 부문(드림타워 복합리조트·여행 매출·영업이익)"""
    d = grab(t, "주요 제품 및 서비스 현황", {"카지노": "카지노", "호텔업": "호텔", "여행업": "여행X", "리테일": "리테일기타",
                                       "임대": "리테일기타", "용역": "리테일기타", "인터넷정보제공": "리테일기타"}, need=3, metrics=False)
    d = {k: [v[0], None] for k, v in d.items()}
    s = grab_cols(t, "부문정보에 대한 공시", {"여행관련 서비스부문": "여행", "드림타워 복합리조트부문": "드림타워",
                                        "제주복합리조트부문": "드림타워", "인터넷 언론 부문": "인터넷"},
                  rev_row=("수익", "수익(매출액)", "매출액"), op_row=("영업이익(손실)", "영업이익", "영업손익"))
    if s:
        d.update({k: v for k, v in s.items() if k in ("여행", "드림타워")})
        d.pop("여행X", None)
    elif "여행X" in d:                                          # 부문 표를 못 읽은 보고서(2025 분기) — 여행 매출만
        d["여행"] = d.pop("여행X")
    return d, "cum"


@seg("파라다이스")
def p_paradise(t, q):
    """연결 주석 영업부문(카지노 3곳·호텔 부산·복합리조트 P-City·기타 — 외부고객 매출·영업손익)"""
    i = t.find("부문별 수익, 영업이익")
    if i < 0:
        i = t.find("영업부문")
    d = {}
    for _, rows in _tables(t, lambda x: "복합리조트" in x and "카지노" in x and ("영업손익" in x or "영업이익" in x)
                           and "외부고객" in x, start=max(i, 0), n=1):
        pair = "3개월" in head_text(rows)
        u = unit_at(t, i)
        nk = {"카지노": "카지노", "호텔": "호텔", "복합리조트": "복합리조트", "기타": "기타"}
        for r in rows:
            k = next((nk[_n(c)] for c in r[:3] if _n(c) in nk), None)
            if not k or k in d or len(r) < 6:
                continue
            # 빈 칸(부문간 수익 없음)이 있어 왼쪽부터 세면 밀린다 — 오른쪽 끝에서 센다
            # 한 칸: [… 외부, 영업손익, 상각] · 3개월/누적: [… 외부3, 외부누적, 영업3, 영업누적, 상각3, 상각누적]
            ri, oi = (-5, -3) if pair else (-3, -2)
            d[k] = [num(r[ri], u), num(r[oi], u)]
    return d, "cum"


@seg("GS피앤엘")
def p_gspnl(t, q):
    """사업의 내용 사업장별 영업부문(IC·웨스틴·제주·나인트리·파르나스타워·기타 — 매출·영업이익)"""
    for st, rows in _tables(t, lambda x: "IC호텔" in x and "외부고객" in x and "나인트리" in x, n=1):
        return _cols(rows, {"IC호텔": "IC", "웨스틴호텔": "웨스틴", "Westin호텔": "웨스틴", "제주호텔": "제주", "나인트리호텔": "나인트리",
                            "파르나스타워": "타워", "공통 및 기타": "기타"},
                     ("외부고객으로부터의 수익",), ("보고부문 영업이익(손실)", "보고부문 영업이익"), u=unit_at(t, max(st - 300, 0))), "cum"
    return {}, "cum"


@seg("서부T&D")
def p_seobu(t, q):
    """사업의 내용 부문 요약(쇼핑몰·물류·관광호텔·식기(코렐)·임대기타 — 매출·영업이익)
       2025 석유류판매는 중단영업(연결 매출에서 빠짐)이라 읽지 않는다."""
    for st, rows in _tables(t, lambda x: "쇼핑몰운영" in x and "관광호텔업" in x and "영업이익" in x and "자산" in x, n=1):
        return _cols(rows, {"쇼핑몰운영": "쇼핑몰", "물류시설운영": "물류", "관광호텔업": "호텔", "식기류 제조 및 판매": "식기",
                            "임대및기타사업": "임대기타"},
                     ("매출액",), ("영업이익(손실)", "영업이익"), u=unit_at(t, max(st - 300, 0))), "cum"
    return {}, "cum"
