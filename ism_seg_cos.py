"""화장품 브랜드사 부문 파서(ISM) — 2026-10-24 조사(scratchpad ism_A) · 원문 2025.03~2026.06 로 검산"""
import re

import ism_lib as L
from ism_lib import *  # noqa: F401,F403


# ── 이 묶음 공통 도구 ────────────────────────────────────────────────────────
def _notes(t):
    """연결재무제표 주석 시작(목차·정정 신고 본문 다음). 제목 태그가 없으면 0."""
    m = re.search(r"<TITLE[^>]*>[^<]*연결재무제표\s*주석", t)
    return m.start() if m else 0


def _tabs(t, start=0):
    for m in re.finditer(r"<TABLE[^>]*>(.*?)</TABLE>", t[start:], re.S):
        rows = []
        for tr in re.findall(r"<TR[^>]*>(.*?)</TR>", m.group(1), re.S):
            cs = [cell(c) for c in re.findall(r"<T[DHE][^>]*>(.*?)</T[DHE]>", tr, re.S)]
            if any(cs):
                rows.append(cs)
        if len(rows) >= 2:
            yield start + m.start(), rows


def rtab(t, names, need=2, start=0, unit=None, anycell=False, last=False):
    """start 뒤 표를 차례로 — 이름 줄이 need 개(서로 다른 키) 이상인 첫 표(이름이 행).
       → ({키: [숫자 칸(십억)…]}, 머리에 '3개월' 있음, 표 위치). 같은 키 여러 줄은 칸별 합(last=True 면 마지막 줄).
       anycell=True: 이름 칸이 숫자 바로 앞이 아니어도(사업부문 | 상표 설명 | 금액) 그 줄의 첫 이름 칸 뒤 숫자를 쓴다."""
    nk = {L._k(a): b for a, b in names.items()}
    for p, rows in _tabs(t, start):
        hits = []
        if anycell:
            for r in rows:
                j = next((j for j, c in enumerate(r) if L._k(c) in nk), None)
                if j is not None:
                    v = [c for c in r[j + 1:] if L._isnum(c)]
                    if v:
                        hits.append((nk[L._k(r[j])], v))
        else:
            hits = [(nk[L._k(a)], v) for a, v in labeled(rows) if L._k(a) in nk]
        if len({k for k, _ in hits}) < need:
            continue
        u = unit or unit_at(t, max(0, p - 500))
        out = {}
        for k, v in hits:
            vals = [num(x, u) for x in v]
            out[k] = vals if (last or k not in out) else [(a or 0) + (b or 0) for a, b in zip(out[k], vals)]
        return out, "3개월" in head_text(rows), p
    return {}, False, -1


def cur_prev(d, three):
    """rtab 결과 → (당기 누적, 전기 누적) — 칸이 [3개월, 누적, 전기 3개월, 전기 누적] 이거나 [당기, 전기]."""
    ci, pi = (1, 3) if three else (0, 1)
    cur = {k: [v[ci], None] for k, v in d.items() if len(v) > ci}
    prv = {k: [v[pi], None] for k, v in d.items() if len(v) > pi}
    return cur, prv


def ctab(t, names, start=0, rev=("수익", "수익(매출액)", "매출액", "외부매출액")):
    """지역·부문이 **열**인 표(2026 XBRL 양식 · '본사 소재지 국가 | 외국 | 지역 합계') — 머리 줄 이름 순서대로 수익 줄 숫자.
       머리에 '3개월'이 있으면 [3개월, 누적] 쌍에서 누적. → {키: [누적, None]}"""
    nk = {L._k(a): b for a, b in names.items()}
    rk = {L._k(x) for x in rev}
    for p, rows in _tabs(t, start):
        hr = None
        for r in rows[:6]:
            ks = [L._k(c) for c in r if L._k(c) in nk]
            if len(ks) >= 2:
                hr = ks
                break
        if not hr:
            continue
        rv = next((v for a, v in labeled(rows) if L._k(a) in rk), None)
        if not rv:
            continue
        u = unit_at(t, max(0, p - 500))
        st = 2 if "3개월" in head_text(rows) else 1
        out = {}
        for j, h in enumerate(hr):
            i = j * st + (st - 1)
            if i < len(rv):
                x = num(rv[i], u)
                k = nk[h]
                out[k] = [x if k not in out else (out[k][0] or 0) + (x or 0), None]
        return out
    return {}


HOME = {**KR_HOME, "국내 매출": "R한국"}
ABROAD = {"외국": "R해외", "해외": "R해외", "수출": "R해외", "해외 매출": "R해외"}


# ── 종목 파서 ───────────────────────────────────────────────────────────────
@seg("아모레퍼시픽")
def p_amore(t, q):
    """연결 주석 부문(화장품·HB 매출·영업이익) + 지역(한국·아시아·북미·기타)"""
    d = grab(t, "영업부문에 대한 공시", {"화장품사업부문": "화장품", "HB(Hair&Beauty) 사업부문": "HB",
                                     "HB(Hair and Beauty) 사업부문": "HB", "DB(Daily Beauty) 사업부문": "HB", "Daily Beauty 사업부문": "HB"})
    r = grab(t, "지역에 대한 공시", {"한국": "R한국", "아시아": "R아시아", "북미": "R북미", "기타": "R기타", "기타지역": "R기타"}, need=3)
    d.update({k: [v[0], None] for k, v in r.items()})
    return d, "cum"


@seg("달바글로벌")
def p_dalba(t, q):
    """연결 주석 지역(고객 소재지) 매출 — 한국·일본·미국·러시아·기타"""
    nm = {**KR_HOME, "일본": "R일본", "미국": "R미국", "러시아": "R러시아", "기타 국가": "R기타", "기타": "R기타"}
    n = t[_notes(t):]          # 정정 신고 본문·사업의 내용에 같은 이름의 다른 표(합계가 매출과 다름)가 먼저 나온다 — 주석에서만
    d = anyof(lambda: grab(n, "영업부문에 대한 공시", nm, need=3, metrics=False),
              lambda: grab(n, "지역별 외부고객으로부터의 수익", nm, need=3, metrics=False),
              lambda: grab(n, "지역별 정보", nm, need=3, metrics=False))
    return {k: [v[0], None] for k, v in d.items()}, "cum"


@seg("아로마티카")
def p_aromatica(t, q):
    """연결 주석 지역별 정보 — 국내·미국·일본·기타(+합계)"""
    nm = {"국내": "R한국", "미국": "R미국", "일본": "R일본", "기타": "R기타", "합 계": "합계", "합계": "합계"}
    d = grab(t, "지역별 정보", nm, need=3, metrics=False)
    out = {k: [v[0], None] for k, v in d.items()}
    raw, three, _ = rtab(t, nm, need=3, start=_notes(t))
    if raw and q[:4] >= "2026":
        out["_prev"] = cur_prev(raw, three)[1]     # 2025 은 별도만 공시 — 연결 전기 비교치로 1Q25·2Q25 를 채운다
    return out, "cum"


@seg("동국제약")
def p_dongkook(t, q):
    """연결 주석 영업부문 — 제약(센텔리안24 포함)·미용기기·화장품(리봄) 매출(영업이익 행 없음)"""
    d = grab_cols(t, "영업부문에 대한 공시", {"제약부문": "제약", "미용기기부문": "미용기기", "화장품부문": "화장품", "투자부문": "투자"})
    return {k: [v[0], None] for k, v in d.items()}, "cum"


@seg("브이티")
def p_vt(t, q):
    """연결 주석 부문정보 — 화장품·라미네이팅·기타 매출·영업이익 + 지역(국내·외국)"""
    d = anyof(lambda: grab_cols(t, "영업부문에 대한 공시", {"화장품": "화장품", "라미네이팅": "라미네이팅", "기타": "기타"}),
              lambda: grab_cols(t, "부문정보", {"화장품": "화장품", "라미네이팅": "라미네이팅", "기타": "기타"}))
    r = anyof(lambda: grab(t, "지역에 대한 공시", {**HOME, **ABROAD}, need=2, metrics=False),
              lambda: ctab(t, {**HOME, **ABROAD}, start=_notes(t)),                       # 2025 사업보고서·2026 반기: 열 양식
              lambda: cur_prev(*rtab(t, {**HOME, **ABROAD}, need=2, start=_notes(t))[:2])[0])  # 2025 분기·1Q26: 내수/수출 행
    d.update({k: [v[0], None] for k, v in r.items()})
    return d, "cum"


@seg("LG생활건강")
def p_lghh(t, q):
    """연결 주석 영업부문(HDB·Beauty·Refreshment 매출·영업이익) + 지역(한국·중국·일본·기타아시아·북미·유럽·기타)"""
    nm = {"HDB": "HDB", "Beauty": "Beauty", "Refreshment": "Refreshment"}
    d = grab_cols(t, "제품과 용역에 대한 공시", nm)
    pv = grab_cols(t, "제품과 용역에 대한 공시", nm, nth=1)       # 전기 비교치(재분류 반영)
    r = grab(t, "지역에 대한 공시", {"한국": "R한국", "중국": "R중국", "일본": "R일본", "기타 아시아": "R기타아시아",
                                 "기타아시아": "R기타아시아", "북미": "R북미", "중남미": "R기타", "유럽": "R유럽", "기타 국가": "R기타", "기타": "R기타"},
             need=3, metrics=False)
    d.update({k: [v[0], None] for k, v in r.items()})
    if pv and q[:4] >= "2026":
        d["_prev"] = pv
    return d, "cum"


@seg("에이피알")
def p_apr(t, q):
    """사업의 내용 주요 제품 현황 — 화장품/뷰티·뷰티디바이스·기타 매출 + 내수/수출 + 미국·유럽 법인 매출(내부거래 제거 전)"""
    d, _, _ = rtab(t, {"화장품/뷰티": "화장품", "뷰티디바이스": "디바이스", "뷰티 디바이스": "디바이스", "기타": "기타"},
                   need=2, unit=1e6, anycell=True)
    out = {k: [v[0], None] for k, v in d.items() if v}
    if "디바이스" not in out:
        return {}, "cum"
    x, _, _ = rtab(t, {"내수": "R한국", "수출": "R해외"}, need=2, unit=1e6, anycell=True, last=True)   # 마지막 줄 = 합계
    out.update({k: [v[0], None] for k, v in x.items() if v})
    s, three, _ = rtab(t, {"APR US INC": "R미국법인", "APR CORPORATION UK LTD": "R유럽법인", "APR Netherlands B.V.": "R유럽법인",
                           "APR FRANCE SAS": "R유럽법인", "APR JAPAN Co., Ltd.": "R일본법인"}, need=2, start=_notes(t))
    ri = 4 if three else 2                                       # [자산, 부채, (3개월 매출, 3개월 순익,) 누적 매출, …]
    out.update({k: [v[ri], None] for k, v in s.items() if len(v) > ri})
    return out, "cum"


@seg("TS트릴리온")
def p_ts(t, q):
    """연결 주석 고객과의 계약 수익 — 화장품(제품+상품)·공사(TS코어)·용역 + 지역(국내·미국·중국)"""
    nm = {"제품의 판매": "화장품", "상품의 판매": "화장품", "공사수입": "공사", "용역매출": "용역",
          "국내": "R한국", "미국": "R미국", "중국": "R중국"}
    d, three, _ = rtab(t, nm, need=3, start=_notes(t))
    cur, prv = cur_prev(d, three)
    if q[:4] >= "2026" and prv:
        cur["_prev"] = prv                      # 1Q25 원보고서에는 이 표가 없다 — 2026 전기 비교치로
    return cur, "cum"


@seg("클리오")
def p_clio(t, q):
    """연결 주석 영업부문 지역 — 국내·외국(수출) 매출(단일 부문)"""
    n0 = _notes(t)
    d = ctab(t, {**HOME, **ABROAD}, start=n0)                    # 2026·사업보고서: 열 양식
    if not d:
        raw, three, _ = rtab(t, {**HOME, **ABROAD}, need=2, start=n0)   # 2025 분기: 내수/수출 행
        d = cur_prev(raw, three)[0]
    return d, "cum"


@seg("네오팜")
def p_neopharm(t, q):
    """(별도) 주석 영업부문 지역 — 국내·외국(수출) 매출"""
    n0 = _notes(t) or 0
    d = ctab(t, {**HOME, **ABROAD}, start=n0)
    if not d:
        raw, three, _ = rtab(t, {**HOME, **ABROAD}, need=2, start=n0)
        d = cur_prev(raw, three)[0]
    return d, "cum"


@seg("아이패밀리에스씨")
def p_ifamily(t, q):
    """연결 주석 부문별 손익 — 화장품·웨딩 등 매출·영업이익(공통비 배분 전) + 지역(국내·해외 · 고객 소재지)"""
    raw, _, p = rtab(t, {"화장품사업부문": "화장품", "웨딩사업부문 등": "웨딩", "웨딩사업부문": "웨딩"}, need=2)
    if not raw:
        return {}, "cum"
    out = {k: [v[0], v[1] if len(v) > 1 else None] for k, v in raw.items()}
    r, three, _ = rtab(t, {"국내": "R한국", "해외": "R해외"}, need=2, start=p + 10)
    out.update(cur_prev(r, three)[0])
    return out, "cum"


@seg("마녀공장")
def p_manyo(t, q):
    """연결 주석 고객과의 계약 수익 지리적 시장 — 국내·아시아·북미·기타"""
    d, three, _ = rtab(t, {"국내": "R한국", "아시아": "R아시아", "북미": "R북미", "기타": "R기타"}, need=3, start=_notes(t))
    cur, prv = cur_prev(d, three)
    if q[:4] >= "2026" and prv:
        cur["_prev"] = prv                      # 1Q25 원보고서는 북미가 기타에 섞여 있다 — 2026 전기 비교치로 다시
    return cur, "cum"


@seg("토니모리")
def p_tonymoly(t, q):
    """연결 주석 지역 — 국내·해외 매출"""
    d, three, _ = rtab(t, {"국내": "R한국", "국내 매출": "R한국", "해외": "R해외", "해외 매출": "R해외"}, need=2, start=_notes(t))
    return cur_prev(d, three)[0], "cum"


@seg("에이블씨엔씨")
def p_able(t, q):
    """연결 주석 지역 매출 — 한국·중국·일본·기타아시아·유럽·북중미(면세 = 2025 중단영업)"""
    nm = {"한국": "R한국", "면세": "R한국", "중국": "R중국", "일본": "R일본", "기타아시아": "R기타아시아",
          "유럽": "R유럽", "북중미": "R북중미"}
    d, three, _ = rtab(t, nm, need=4, start=_notes(t))
    cur, prv = cur_prev(d, three)
    if q[:4] >= "2026" and prv:
        cur["_prev"] = prv                      # 2026 보고서는 면세 중단영업을 뺀 재작성 비교치
    return cur, "cum"
