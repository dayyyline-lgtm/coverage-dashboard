# -*- coding: utf-8 -*-
"""에이피알 분기 손익(비용 구조) 모델의 재료 -> index.html 의  const APRMODEL = {...};   (2026-10-30 신설)

화면 = 종목 페이지 손익 탭 '분기 손익 — 비용 구조'(js/aprmodel.js 의 renderAprModel). 사용자(2026-10-30, 3Q26 컨콜 뒤):
"4Q·내년 추정치 하향을 고려해 IS 를 — 컨콜 기준으로 물류비·마케팅비가 개선된다고 보면 안 된다" → 비용을 줄마다 보이게 했다.

무엇이 들어 있나 (십억원)
  q   {"2026Q2": {rev, cogs, gp, sga, op, pbt, np, npp, ooi, ooe, sg:{ad,cm,fr,hr,fee,dep,pk,etc}}}
      손익 = 전체 재무제표 API(fnlttSinglAcntAll · 4Q = 연간 − 3Q 누적 · 다음 해 비교치 우선 — C2.dart_quarters)
      ooi·ooe = 기타영업수익·비용(IFRS 18 조기 적용 2026Q1~ — 외화 매출채권 평가손익이 영업이익 안에 들어온다)
      sg  = 연결 주석 '판매비와 관리비' — ad 광고선전비 · cm 판매수수료 · fr 운반비 · hr 인건비(급여·퇴직·복리·주식보상) ·
            fee 지급수수료 · dep 상각(감가·사용권·무형) · pk 포장비 · etc 나머지(= 판관비 − 위 합)
  src {"2026-06": 접수번호}   주석을 읽은 보고서(새 보고서·정정만 원문을 받는다)
  cum {"2026-06": {...누적...}}  주석이 누적만 주는 분기(반기·3Q)·연간을 차분할 때 쓰는 원 값

⚠ 주석 표 양식이 해마다 다르다 — 2024 = '당분기/전분기'(1Q)·'당기/전기'(연간) 열 · 2025~ = XBRL '3개월/누적' 열(반기·3Q)·한 열(1Q·연간).
  '3개월' 열이 있으면 그걸, 없으면 1Q·연간은 첫 열, 반기·3Q 는 누적 차분. 항목 합 ≠ 손익계산서 판관비(1% 넘게)면 그 분기 주석을 버리고 경고.
⚠ 3Q26 실적(10/29 발표)은 DART 3분기보고서(11월 중순) 전이라 여기엔 없다 — 화면(APR_IR)이 잠정실적·컨콜 비율로 채운다.

  python fetch_aprmodel.py            # 수집·기록
  python fetch_aprmodel.py --dry-run  # 출력만
"""
import json, re, sys, datetime, copy

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, ".")
import fetch_c2model as C2
import ism_lib as L
from collector_health import note_health

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
CORP = "01190568"          # 에이피알 (278470)
Y0 = 2024
ACC = {
    "rev":  (("ifrs-full_Revenue",), ("매출액", "수익(매출액)")),
    "cogs": (("ifrs-full_CostOfSales",), ("매출원가",)),
    "gp":   (("ifrs-full_GrossProfit",), ("매출총이익",)),
    "sga":  (("dart_TotalSellingGeneralAdministrativeExpenses",), ("판매비와 관리비", "판매비와관리비")),
    "ooi":  (("dart_OtherOperatingIncome",), ("기타영업수익",)),
    "ooe":  (("dart_OtherOperatingExpense",), ("기타영업비용",)),
    "op":   (("dart_OperatingIncomeLoss",), ("영업이익", "영업이익(손실)")),
    "pbt":  (("ifrs-full_ProfitLossBeforeTax",), ("법인세비용차감전순이익", "법인세비용차감전순이익(손실)")),
    "np":   (("ifrs-full_ProfitLoss",), ("당기순이익", "당기순이익(손실)", "반기순이익", "분기순이익")),
    "npp":  (("ifrs-full_ProfitLossAttributableToOwnersOfParent",), ()),
}
# 판관비 주석 항목 → 묶음
SG = {
    "ad": ("광고선전비",), "cm": ("판매수수료",), "fr": ("운반비",),
    "hr": ("급여", "퇴직급여", "주식보상비용", "복리후생비"), "fee": ("지급수수료",),
    "dep": ("감가상각비", "사용권자산감가상각비", "사용권자산상각비", "무형자산상각비", "무형자산감가상각비"), "pk": ("포장비",),
}
PER = {"03": 1, "06": 2, "09": 3, "12": 4}


def reports():
    import urllib.request
    u = (f"https://opendart.fss.or.kr/api/list.json?crtfc_key={C2.DART_KEY}&corp_code={CORP}"
         f"&bgn_de={Y0}0101&pblntf_ty=A&page_count=100")
    d = json.loads(urllib.request.urlopen(u, timeout=25).read().decode())
    out = {}
    for r in sorted(d.get("list", []), key=lambda r: r["rcept_no"]):
        m = re.search(r"\((\d{4})\.(\d{2})\)", r["report_nm"])
        if m and m.group(2) in PER and m.group(1) >= str(Y0):
            out[f"{m.group(1)}-{m.group(2)}"] = r["rcept_no"]       # 정정이면 나중 접수가 이긴다
    return out


def _lab(c):
    c = re.sub(r",\s*판관비$", "", c.strip())
    return re.sub(r"\(환입\)|\s", "", c)


def sga_note(t):
    """연결 주석 '판매비와 관리비' 첫 표 → ({항목: 값}, 열 종류 '3m'|'one'|'cum'). 못 찾으면 (None, None)."""
    i = t.find("연결재무제표 주석")
    i = 0 if i < 0 else i
    for m in re.finditer(r"판매비와\s*관리비", t[i:]):
        a = i + m.start()
        for tb in re.findall(r"<TABLE[^>]*>(.*?)</TABLE>", t[a:a + 60000], re.S)[:4]:
            if "광고선전비" not in tb:
                continue
            u = L.unit_at(t, a) if hasattr(L, "unit_at") else None
            unit = 1e3 if "천원" in t[a:a + 3000] else (1e6 if "백만원" in t[a:a + 3000] else 1.0)
            if u:
                unit = u
            kind = "3m" if "3개월" in tb else "one"
            out = {}
            for tr in re.findall(r"<TR[^>]*>(.*?)</TR>", tb, re.S):
                cs = [L.cell(c) for c in re.findall(r"<T[DHE][^>]*>(.*?)</T[DHE]>", tr, re.S)]
                cs = [c for c in cs if c]
                labs = [c for c in cs if re.search(r"[가-힣]", c) and L.num(c) is None]
                nums = [c for c in cs if L.num(c) is not None and re.search(r"\d", c)]
                if not labs or not nums:
                    continue
                k = _lab(labs[-1])
                if k in out:                       # 같은 표에 전기 블록이 이어 나온다 — 첫 줄(당기)만
                    continue
                out[k] = L.num(nums[0], unit)
            if out:
                return out, kind
    return None, None


def group(raw):
    g = {k: round(sum(raw.get(x, 0) or 0 for x in names), 3) for k, names in SG.items()}
    tot = raw.get("판매비와관리비") or raw.get("판매비와관리비합계") or raw.get("합계")
    return g, tot


def main():
    dry = "--dry-run" in sys.argv
    if not C2.DART_KEY:
        print("[SKIP] DART 키 없음"); return
    html = open(HTML, encoding="utf-8").read()
    m = re.search(r"const APRMODEL\s*=\s*(\{.*?\});", html, re.S)
    old = json.loads(m.group(1)) if m else {}
    prev = copy.deepcopy(old)
    q = C2.dart_quarters("CFS", Y0, CORP, ACC)
    if not q:
        note_health("에이피알 모델", "DART 손익을 못 받음"); sys.exit(1)
    rep = reports()
    src, cum = dict(old.get("src", {})), dict(old.get("cum", {}))
    warn = []
    for per, rc in sorted(rep.items()):
        if src.get(per) == rc and per in cum:
            continue
        try:
            t = L.doc(rc)
        except Exception as e:
            warn.append(f"{per} 원문 못 받음 {str(e)[:60]}"); continue
        raw, kind = sga_note(t)
        if not raw:
            warn.append(f"{per} 판관비 주석을 못 찾음"); continue
        g, tot = group(raw)
        cum[per] = {"kind": kind, "g": g, "tot": tot}
        src[per] = rc
    # 분기 값 — 3m 열이면 그대로, 1Q·연간 한 열이면 1Q 그대로·4Q = 연간 − 3Q 누적, 반기·3Q 누적만이면 차분
    sg = {}
    for per in sorted(cum):
        y, mm = per.split("-"); qi = PER[mm]; c = cum[per]
        key = f"{y}Q{qi}"
        if c["kind"] == "3m" or qi == 1:
            sg[key] = dict(c["g"]); sg[key]["_tot"] = c["tot"]
        else:
            p = cum.get(f"{y}-{('03','06','09')[qi-2]}")
            if qi == 4:          # 사업보고서 = 연간 → 4Q = 연간 − (1~3Q 분기 합)
                qs = [sg.get(f"{y}Q{i}") for i in (1, 2, 3)]
                if all(qs):
                    sg[key] = {k: round(c["g"][k] - sum(x[k] for x in qs), 3) for k in SG}
                    sg[key]["_tot"] = (c["tot"] - sum(x["_tot"] for x in qs)) if c["tot"] is not None and all(x.get("_tot") is not None for x in qs) else None
            elif p:              # 누적 열만 있는 반기·3Q(옛 양식) — 직전 누적을 뺀다
                sg[key] = {k: round(c["g"][k] - p["g"][k], 3) for k in SG}
                sg[key]["_tot"] = (c["tot"] - p["tot"]) if c["tot"] is not None and p["tot"] is not None else None
    out_q = {}
    for k in sorted(q):
        v = dict(q[k])
        s = sg.get(k)
        if s and v.get("sga"):
            tot = s.get("_tot") if s.get("_tot") is not None else v["sga"]
            if abs(tot - v["sga"]) > 0.01 * v["sga"]:
                warn.append(f"{k} 주석 판관비 {tot:.1f} ≠ 손익 {v['sga']:.1f} — 주석 버림")
            else:
                g = {kk: s[kk] for kk in SG}
                g["etc"] = round(v["sga"] - sum(g.values()), 3)
                v["sg"] = g
        out_q[k] = v
    out = {"asOf": old.get("asOf"), "corp": CORP, "q": out_q, "src": src, "cum": cum}
    if warn:
        print("[경고]", " · ".join(warn))
    for k in sorted(out_q)[-6:]:
        v = out_q[k]; s = v.get("sg") or {}
        print(f"  {k} 매출 {v.get('rev', 0):.1f} 원가 {v.get('cogs', 0):.1f} 판관비 {v.get('sga', 0):.1f} 영업이익 {v.get('op', 0):.1f}"
              + (f" · 광고 {s['ad']:.1f} 수수료 {s['cm']:.1f} 운반 {s['fr']:.1f} 인건 {s['hr']:.1f}" if s else " · 주석 없음"))
    cmp_old = {k: v for k, v in prev.items() if k != "asOf"}
    cmp_new = {k: v for k, v in out.items() if k != "asOf"}
    if cmp_old == cmp_new:
        print("[SKIP] 변동 없음"); return
    out["asOf"] = datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    if dry:
        print("[dry-run] 기록 안 함"); return
    html = C2._put(html, "APRMODEL", out)
    open(HTML, "w", encoding="utf-8").write(html)
    note_health("에이피알 모델", None if not [w for w in warn if "못 받음" in w] else " · ".join(warn)[:200])
    print("[OK] APRMODEL 갱신", out["asOf"])


if __name__ == "__main__":
    main()
