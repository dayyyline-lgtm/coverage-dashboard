"""엔터·콘텐츠 부문 파서(ISM) — 2026-10-24 조사(scratchpad ism_D_ent) · 원문 2024.12~2026.06 로 검산"""
from ism_lib import *  # noqa: F401,F403
import ism_lib as L


def _rows(t, anchor, occ=0, ntab=4, after=None):
    """앵커 뒤 표들(행 목록)과 단위 배수."""
    i = find_occ(t, anchor, occ, after)
    if i < 0:
        return [], 1e3
    return tables_after(t, anchor, n=ntab, start=i), unit_at(t, i)


def _cols(t, anchor, names, rev_rows, op_rows=(), occ=0, ntab=4):
    """부문·지역이 열인 표 — 머리의 이름 순서(처음 나온 것만)대로 매출·영업이익 줄의 숫자를 짝짓는다.
       반기·3Q 처럼 [3개월, 누적] 쌍이면 누적 칸을 쓴다. 같은 키로 모이는 이름은 더한다."""
    tabs, u = _rows(t, anchor, occ, ntab)
    nk = {L._k(a): b for a, b in names.items()}
    rk, ok = {L._k(x) for x in rev_rows}, {L._k(x) for x in op_rows}
    for rows in tabs:
        # 머리 = 이름이 가장 많이 걸린 줄. 칸 위치를 그대로 쓴다(빈 칸 '' 도 한 칸 — 방송제작매출 빈칸에서 밀린 적 있다)
        best = max(rows[:8], key=lambda r: sum(L._k(c) in nk for c in r), default=None)
        if not best or not any(L._k(c) in nk for c in best):
            continue
        head = [L._k(c) for c in best[1:]]
        pos = {}
        for j, k in enumerate(head):
            if k in nk and k not in pos:                     # 같은 이름이 두 번(부문간 수익 칸)이면 처음 것
                pos[k] = j
        def row(keys):
            for r in rows:
                if r and L._k(r[0]) in keys:
                    return r[1:]
            return None
        rv, op = row(rk), (row(ok) if ok else None)
        if not rv:
            continue
        pair = "3개월" in head_text(rows) and len(rv) >= 2 * len(pos)
        out = {}
        for k, j in pos.items():
            jj = 2 * j + 1 if pair else j
            if jj >= len(rv):
                continue
            key = nk[k]
            r = num(rv[jj], u)
            o = num(op[jj], u) if op and jj < len(op) else None
            x = out.get(key)
            out[key] = [r, o] if not x else [(x[0] or 0) + (r or 0), None if (o is None or x[1] is None) else x[1] + o]
        return out
    return {}


def _first(rows_by_label, u):
    return {k: [num(v[0], u), None] for k, v in rows_by_label.items() if v}


@seg("하이브")
def p_hybe(t, q):
    """II.4 제품별 매출(음반·공연·MD·콘텐츠·광고출연·팬클럽) + 지역(국내·아시아·북미·기타) + 주석 영업부문(음악·플랫폼·테크 매출·영업이익)"""
    nm = {"음반, 음원 등": "음반", "콘서트, 팬미팅 등": "공연", "광고 수익, 출연료 수익 등": "광고출연",
          "공식 상품(MD), IP 라이선싱 등": "MD", "영상콘텐츠, 영상출판물 등": "콘텐츠", "팬클럽 등": "팬클럽"}
    d = anyof(lambda: grab(t, "제품별 매출액", nm, need=4, metrics=False, idx=(0, None)),       # 2025.12~
              lambda: grab(t, "가. 매출 실적", nm, need=4, metrics=False, idx=(0, None)))      # 2025 분기 양식
    r = grab(t, "지역별 매출액", {"국내": "R한국", "아시아": "R아시아", "북미": "R북미", "기타국가": "R기타"},
             need=3, metrics=False, idx=(0, None))          # 북미 두 줄(고객 계약 + 전대 임대료)은 더해진다
    d.update({k: [v[0], None] for k, v in r.items()})
    s = _cols(t, "부문별 손익", {"음악": "음악부문", "플랫폼": "플랫폼부문", "테크 기반 미래성장": "테크부문"},
              rev_rows=("외부고객으로부터의 수익", "고객과의 계약에서 생기는 수익"), op_rows=("영업이익", "영업이익(손실)"))
    d.update(s)
    return d, "cum"


@seg("JYP Ent.")
def p_jyp(t, q):
    """II.4 매출 실적(연결) — 음반/음원·콘서트·광고·출연료·MD·기타(2026 새 분류만) + 주석 영업부문(엔터·음악출판·유통판매) + 지역(국내·해외)"""
    tabs, u = _rows(t, "매출 실적", ntab=2)
    d = {}
    lab = dict()
    for a, v in (labeled(tabs[0]) if tabs else []):
        lab.setdefault(L._k(a), v)
    if "MD" in lab:                      # 2026 새 분류만 — 옛 분류(MD·유튜브가 기타에 섞임)는 시드(_basis old)가 채운다
        for nm, key in (("음반/음원", "음반"), ("콘서트", "콘서트"), ("광고", "광고"), ("출연료", "출연료"), ("MD", "MD"), ("초상권외", "기타")):
            v = lab.get(L._k(nm))
            if v:
                d[key] = [num(v[0], u), None]
    sn = {"엔터테인먼트": "엔터부문", "음악출판업": "음악출판부문", "유통판매업": "유통판매부문"}
    rv, ov = ("수익", "수익(매출액)", "매출액", "매출"), ("영업이익(손실)", "영업이익", "영업손익")
    s = anyof(lambda: _cols(t, "영업부문에 대한 공시", sn, rev_rows=rv, op_rows=ov),       # 2025~ 양식
              lambda: _cols(t, "영업부문", sn, rev_rows=rv, op_rows=ov))                 # 2024 양식('구 분 | 엔터테인먼트 …' 표)
    d.update(s)
    r = _cols(t, "지역에 대한 공시", {"본사 소재지 국가": "R한국", "외국": "R해외"}, rev_rows=("수익", "수익(매출액)", "매출액"))
    d.update({k: [v[0], None] for k, v in r.items()})
    return d, "cum"


@seg("에스엠")
def p_sm(t, q):
    """주석 영업부문(엔터·광고대행·기타) + 지역(국내·일본·기타 국외) + II.2 주요 제품(음반/음원·매니지먼트·공연영상)"""
    rv = ("매출액", "수익(매출액)", "수익")
    sg = {"엔터테인먼트": "엔터", "광고대행": "광고대행", "기타": "기타부문"}
    rg = {"국내": "R한국", "일본": "R일본", "기타": "R기타", "기타 국외": "R기타", "기타 국가": "R기타"}
    d = anyof(lambda: _cols(t, "영업부문에 대한 공시", sg, rev_rows=rv),                       # 부문이 열(2026 양식·사업보고서)
              lambda: grab(t, "영업부문에 대한 공시", sg, need=2, metrics=False))             # 부문이 행(2025 반기·3Q)
    r = anyof(lambda: _cols(t, "지역에 대한 공시", rg, rev_rows=rv),
              lambda: grab(t, "지역에 대한 공시", rg, need=2, metrics=False))
    d.update({k: [v[0], None] for k, v in r.items()})
    p = grab(t, "주요 제품 등의 매출 현황", {"음악청취용": "음반", "출연료": "매니지먼트", "공연, 영상 콘텐츠 제작 등": "공연영상"},
             need=3, metrics=False, idx=(0, None))
    d.update({k: [v[0], None] for k, v in p.items()})
    return d, "cum"


@seg("와이지엔터")
def p_yg(t, q):
    """주석 '고객과의 계약에서 생기는 수익' 유형별(상제품·음악서비스·공연·용역) 매출 + 지역(국내·외국)"""
    rv = ("매출액",)
    d = _cols(t, "수익의 구분에 대한 공시", {"상제품매출": "상제품", "음악서비스매출": "음악서비스", "공연매출": "공연",
                                       "광고사업매출": "용역", "방송제작매출": "용역", "용역매출": "용역"}, rev_rows=rv)
    d = {k: [v[0], None] for k, v in d.items()}
    # 지역: 머리가 2단(국내 | 외국 → 일본·기타 국외)이라 위치로 못 짝짓는다 → 국내 = 첫 칸, 해외 = 합계 − 국내
    tabs, u = _rows(t, "지역에 대한 공시", ntab=3)
    for rows in tabs:
        r = next((x for x in rows if x and L._k(x[0]) == "매출액"), None)
        if not r:
            continue
        v = [c for c in r[1:] if L._isnum(c)]
        pair = "3개월" in head_text(rows)
        if len(v) >= (6 if pair else 3):
            kr, tot = num(v[1 if pair else 0], u), num(v[-1], u)
            if kr is not None and tot is not None:
                d["R한국"], d["R해외"] = [kr, None], [round(tot - kr, 4), None]
        break
    return d, "cum"


_SAMG_T = {"상품": "제품", "제품": "제품", "콘텐츠제작": "용역", "라이선스": "라이선스", "용역": "용역", "기타": "기타"}


@seg("SAMG엔터")
def p_samg(t, q):
    """II.4 매출실적 유형별(제품·라이선스·용역·기타 — 국내+수출 계) + 주석 영업손익 지역(한국·해외)"""
    tabs, u = _rows(t, "가. 매출실적", ntab=2)
    d = {}
    for rows in tabs:
        cur = None
        for r in rows:
            c0 = L._k(r[0]) if r else ""
            if c0 in _SAMG_T:
                cur = _SAMG_T[c0]
            if cur and any(L._k(c) == "계" for c in r):
                j = next(j for j, c in enumerate(r) if L._k(c) == "계")
                v = r[j + 1] if j + 1 < len(r) else ""
                x = num(v, u)
                if x is not None:
                    d[cur] = [round((d.get(cur, [0])[0] or 0) + x, 4), None]
        if d:
            break
    r = grab(t, "매출액의 내역", {"한국": "R한국", "해외": "R해외"}, need=2, metrics=False)
    d.update({k: [v[0], None] for k, v in r.items()})
    return d, "cum"


@seg("탑코미디어")
def p_topco(t, q):
    """II.4 매출실적 — 플랫폼·유통·기타 × 내수/해외(합병 전 2025.03 은 콘텐츠 서비스 한 줄) + 내수·해외 합계"""
    tabs, u = _rows(t, "가. 매출실적", ntab=2)
    d = {}
    for rows in tabs:
        typ, tot = None, False
        for r in rows:
            cs = [L._k(c) for c in r]
            for c in cs:
                if c in ("플랫폼", "유통", "기타"):
                    typ, tot = c, False
                elif c in ("합계", "계"):
                    tot = True
            sub = next((c for c in cs if c in ("내수", "해외", "수출")), None)
            if not sub:
                continue
            js = [j for j, c in enumerate(r) if L._isnum(c)]
            if not js:
                continue
            x = num(r[js[0]], u)
            if x is None:
                continue
            reg = "R한국" if sub == "내수" else "R해외"
            if tot:
                d[reg] = [x, None]
            elif typ:
                key = typ + ("내수" if sub == "내수" else "해외") if typ != "기타" else "기타"
                d[key] = [round((d.get(key, [0])[0] or 0) + x, 4), None]
        if d:
            break
    return d, "cum"
