"""종목별 분기 손익 모델(ISM) — DART 원문 표 도구 + 부문 파서 등록부 (2026-10-24 · fetch_ism.py 가 쓴다)

종목별 부문 파서는 묶음마다 파일을 나눈다 — ism_seg_cos.py(화장품 브랜드) · ism_seg_odm.py(ODM·미용) · ism_seg_food.py(음식료·유통) ·
ism_seg_game.py(게임·레저) · ism_seg_ent.py(엔터). 각 파일은 `from ism_lib import *` 하고 @seg("종목") 로 등록한다.

파서 약속: fn(원문, "2026Q2") → ({"키": [매출, 영업이익|None], …, "_prev": {같은 표의 전년 같은 기간(재작성)}?}, "cum"|"3m")
  · 값은 십억원 · "cum" = 그 해 누적(1Q·반기·3Q·연간 — fetch_ism 이 차분), "3m" = 그 분기 3개월
  · 키: 부문은 짧은 한글, 지역은 "R" + 이름(R한국·R미국…) · docstring 첫 줄 = 화면 '부문 …' 설명
  · 2026 양식(앞으로 계속 쓰일 양식)을 읽으면 된다. 그 전 분기는 ism_seed/<묶음>.json(조사 때 원문에서 뽑은 값)이 채운다.
"""
import html as _html, io, re, time, urllib.request, zipfile

import fetch_c2model as C2

PERIOD = {"03": 1, "06": 2, "09": 3, "12": 4}
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
    for tb in re.findall(r"<TABLE[^>]*>(.*?)</TABLE>", t[i:i + span], re.S):
        if len(out) >= n:
            break
        rows = []
        for tr in re.findall(r"<TR[^>]*>(.*?)</TR>", tb, re.S):
            cs = [cell(c) for c in re.findall(r"<T[DHE][^>]*>(.*?)</T[DHE]>", tr, re.S)]
            if any(cs):
                rows.append(cs)
        if len(rows) >= 2 and max(len(r) for r in rows) >= 2:      # 글 상자(한 칸짜리 표)는 건너뛴다
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


def _k(s):
    return re.sub(r"[\s·ㆍ.,()\[\]&]", "", s or "")


def _isnum(c):
    c = (c or "").replace(",", "").replace(" ", "").strip()
    return bool(re.fullmatch(r"[\(△▲-]?\d+(\.\d+)?\)?|-|−", c)) and c not in ("",)


def labeled(rows):
    """병합 칸 때문에 들쭉날쭉한 행 → [(이름, [숫자 칸 원문…])]. 이름 = 숫자 앞의 마지막 글자 칸."""
    out = []
    for r in rows:
        js = [j for j, c in enumerate(r) if _isnum(c) and c.strip() not in ("-", "−")]
        if not js:
            continue
        lab = next((r[j] for j in range(js[0] - 1, -1, -1) if r[j].strip() and not _isnum(r[j])), "")
        out.append((lab, [c for c in r[js[0]:] if _isnum(c)]))
    return out


def head_text(rows):
    h = []
    for r in rows:
        if any(_isnum(c) and c.strip() not in ("-", "−") for c in r):
            break
        h.append(" ".join(r))
    return " ".join(h)


def find_occ(t, anchor, occ=0, after=None):
    """앵커의 occ 번째 위치(after 문구가 주어지면 그 뒤에서부터)."""
    st = t.find(after) if after else 0
    st = max(st, 0)
    pos = [m.start() for m in re.finditer(re.escape(anchor), t[st:])]
    return st + pos[occ] if len(pos) > occ else -1


def unit_at(t, i):
    m = re.search(r"단위\s*[:：]?\s*(천원|백만원|억원|원)", t[i:i + 6000]) if i >= 0 else None
    return {"천원": 1e3, "백만원": 1e6, "억원": 1e8, "원": 1.0}.get(m.group(1) if m else "천원", 1e3)


def grab(t, anchor, names, occ=0, after=None, ntab=6, metrics=None, idx=None, need=1, nth=0):
    """앵커 뒤 표에서 이름 줄(부문·지역이 행) → {화면 키: [매출, 영업이익|None]} (원문 단위 → 십억).
       names = {표의 이름: 화면 키} — 여러 이름을 한 키로 모으면 더한다(이름은 공백·기호 무시).
       칸 고르기: 머리에 '3개월'이 있으면 [3개월, 누적] 쌍에서 **누적**, metrics(머리의 지표 순서)가 둘이면 매출·영업이익 쌍.
       idx 를 주면 그 숫자 칸 번호(매출, 영업이익)를 그대로 쓴다."""
    i = find_occ(t, anchor, occ, after)
    if i < 0:
        return {}
    u = unit_at(t, i)
    nk = {_k(a): b for a, b in names.items()}
    for rows in tables_after(t, anchor, n=ntab, start=i):
        L = labeled(rows)
        hits = [(nk[_k(a)], v) for a, v in L if _k(a) in nk]
        if len(hits) < need:
            continue
        if nth:
            nth -= 1
            continue
        ht = head_text(rows)
        three = "3개월" in ht
        w = 2 if three else 1
        two = metrics if metrics is not None else (("영업" in ht and ("매출" in ht or "수익" in ht)))
        ri, oi = idx if idx else ((1 if three else 0), ((w + (1 if three else 0)) if two else None))
        out = {}
        for key, v in hits:
            r = num(v[ri], u) if ri < len(v) else None
            o = num(v[oi], u) if (oi is not None and oi < len(v)) else None
            x = out.get(key)
            out[key] = [r, o] if not x else [(x[0] or 0) + (r or 0), None if (o is None or x[1] is None) else x[1] + o]
        return out
    return {}


def grab_cols(t, anchor, names, rev_row=("매출액", "수익", "외부매출액", "수익(매출액)", "영업수익", "매출"),
              op_row=("영업이익", "영업이익(손실)", "영업손익", "부문이익"), occ=0, after=None, ntab=6, nth=0):
    """부문이 열인 표 — 머리 줄의 부문 이름 순서대로 '매출'·'영업이익' 줄의 숫자를 짝짓는다(같은 기간 누적 칸이 한 벌일 때)."""
    i = find_occ(t, anchor, occ, after)
    if i < 0:
        return {}
    u = unit_at(t, i)
    nk = {_k(a): b for a, b in names.items()}
    rk, ok = {_k(x) for x in rev_row}, {_k(x) for x in op_row}
    for rows in tables_after(t, anchor, n=ntab, start=i):
        hr = None
        for r in rows[:5]:
            ks = [_k(c) for c in r if _k(c) in nk]
            if ks:
                hr = ks
                break
        if not hr:
            continue
        L = labeled(rows)
        rv = next((v for a, v in L if _k(a) in rk), None)
        op = next((v for a, v in L if _k(a) in ok), None)
        if not rv:
            continue
        if nth:
            nth -= 1
            continue
        out = {}
        for j, h in enumerate(hr):
            if j < len(rv):
                key = nk[h]
                r, o = num(rv[j], u), (num(op[j], u) if op and j < len(op) else None)
                x = out.get(key)
                out[key] = [r, o] if not x else [(x[0] or 0) + (r or 0), None if (o is None or x[1] is None) else x[1] + o]
        return out
    return {}





def anyof(*fs):
    """앵커가 보고서마다 다를 때 — 앞에서부터 처음으로 값이 나오는 것."""
    for f in fs:
        d = f()
        if d:
            return d
    return {}


KR_HOME = {"본사 소재지 국가": "R한국", "대한민국": "R한국", "한국": "R한국", "국내": "R한국", "내수": "R한국"}


# ── 부문 파서 등록부 ──
SEG = {}


def seg(name):
    def deco(fn):
        SEG[name] = fn
        return fn
    return deco
