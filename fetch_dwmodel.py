# -*- coding: utf-8 -*-
"""대원미디어 분기 손익 모델의 재료 -> index.html 의  const DWMODEL = {...};   (2026-09-29 신설)

화면 '대원미디어 분기 손익'(영화 흥행 탭 · js/app.js 의 renderDwModel)의 **실적 칸**.
컴투스 모델(fetch_c2model.py · C2MODEL)과 같은 방식이다 — DART 가 원본, 사람이 넣는 건 IR 분해뿐.

무엇이 들어 있나 (십억원)
  fin  {"2026Q2": {rev,cogs,gp,sga,op,pbt,np,npp,opex}}   연결 손익 — 전체 재무제표 API(fnlttSinglAcntAll)
  seg  {"2026Q2": {"라이선스/콘텐츠":[매출,영업손익], "유통":[..], "방송":[..], "출판":[..], "조정":[..]}}
       연결 주석 '부문정보' 표 — **누적**(1Q·반기·3Q·연간)으로만 나와서 분기 = 누적 차분(4Q = 연간 − 3Q 누적).
  imp  {"jpToy": {"2022-01": 2.8, ...}, "cnFig": {...}}  관세청 월별 **수입**($M) — Shop 선행지표(2026-09-29 사용자 "이치방쿠지 수입을 물려서")
       jpToy = 일본산 완구 HS 9503 전체(이치방쿠지 경품·애니메이트 굿즈·조립 키트 — 대원 Shop 이 파는 일본 캐릭터 상품)
       cnFig = 중국산 인형 중 '플라스틱으로 만든 것'(9503002130 = 피규어). 팝마트 등 대원과 무관한 수입도 섞인다.
       외부 정리(9/29)의 회귀 Shop = 7.17 × 일본 완구(3개월 선행) + 8.17 × 중국 피규어(R² 0.91)를 월별 값까지 재현 확인했다.
       nsHw = 중국산 게임기 '기타'(9504.50-9000 — 스위치 본체·조이콘 등 · TV 전용인 PS5·엑스박스는 -1000 이라 빠진다)
       nsSw = 일본산 9504.90-9090 '기타' = **스위치 실물 게임카드**(2026-09-29 확인 — 일본의 대한국 HS950450 수출과 월별 상관 0.84 ·
              연간 비율 0.98~1.17 · 일본이 개수를 적은 달 개당 24~30달러·47~117g = 포장 게임). 한국 결정사례는 없어 데이터로 한 추론이다.
  segCum {"2026-06": {...누적...}} · src {"2026-06": 접수번호}   원 누적값과 출처(다음 실행의 캐시)
  reclass {"2026-12": "2025-12 비교치 재분류: 방송 14.0→…"}   새 보고서의 전기 표가 우리 전년 값과 부문별로 다를 때(경고)
  ⚠ 부문은 **그 해 보고서의 원래 값**만 쓴다. 이 회사는 재분류 뒤 1Q·반기 비교치는 옛 기준, 3Q·사업보고서 비교치는
    새 기준으로 싣는다(2024 사업보고서에서 방송 일부 → 라이선스/콘텐츠) — 재작성 비교치를 쓰면 3Q24 방송 −5.3,
    원래 값으로도 2024 는 4Q24 방송 −10.1. 그래서 2025~ 만 쓰고, 음수·급감 분기는 빼고 경고한다.

⚠ 부문 표는 API 가 아니라 **보고서 원문(document.xml)** 에서 읽는다. 원문은 한 건 1~2MB 라 매일 전부 받지 않는다 —
  `src` 에 없는 접수번호(새 보고서·정정)만 받는다. 평소 요청은 목록 1건 + 재무제표 16건.
⚠ 표 검증: 파싱한 '합계 매출'이 같은 기간 연결 매출(재무제표 API)과 0.5% 안에서 맞을 때만 쓴다.
⚠ 부문 매출은 **내부거래 제거 전**이라 '조정'(음수)을 더해야 연결 매출이 된다.
⚠ IR 부문(신한 9/3 등 리포트의 라이선스·방송)과 DART 부문은 경계가 다르다 — IR '방송'(분기 7~8)은 DART 방송(3~4)
  + 라이선스/콘텐츠 일부다. 모델은 DART 부문을 뼈대로 쓰고, 유통 안의 닌텐도·TCG·Shop 만 IR(js 의 DW_IR)에서 나눈다.

  python fetch_dwmodel.py            # 수집·기록
  python fetch_dwmodel.py --dry-run  # 출력만
"""
import json, re, sys, io, zipfile, html as _html, urllib.request, datetime, copy

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, ".")
import fetch_c2model as C2                     # DART 키·분기 손익 함수·블록 교체를 같이 쓴다
from collector_health import note_health

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
CORP = "00351807"          # 대원미디어 (048910)
Y0 = 2024                  # 손익 2024Q1~ (2025 전년비용)
SEG_Y0 = "2025"            # 부문 2025Q1~ — 2024 는 기준이 섞여 있다(아래 main 의 주석)
ACC = {
    "rev":  (("ifrs-full_Revenue",), ("매출액", "수익(매출액)")),
    "cogs": (("ifrs-full_CostOfSales",), ("매출원가",)),
    "gp":   (("ifrs-full_GrossProfit",), ("매출총이익",)),
    "sga":  (("dart_TotalSellingGeneralAdministrativeExpense",), ("판매비와관리비",)),
    "op":   (("dart_OperatingIncomeLoss",), ("영업이익", "영업이익(손실)")),
    "pbt":  (("ifrs-full_ProfitLossBeforeTax",), ("법인세비용차감전순이익", "법인세비용차감전순이익(손실)")),
    "np":   (("ifrs-full_ProfitLoss",), ("당기순이익", "당기순이익(손실)")),
    "npp":  (("ifrs-full_ProfitLossAttributableToOwnersOfParent",), ()),
}
SEGS = ("라이선스/콘텐츠", "유통", "방송", "출판", "조정", "합계")


def C2_qadd(q, n):
    """'2026Q2' + n 분기"""
    k = int(q[:4]) * 4 + int(q[-1]) - 1 + n
    return f"{k // 4}Q{k % 4 + 1}"
PERIOD = {"03": 1, "06": 2, "09": 3, "12": 4}


def reports():
    """정기보고서 목록 → {"2026-06": 접수번호}. 정정·첨부추가가 있으면 최신 접수가 이긴다."""
    u = (f"https://opendart.fss.or.kr/api/list.json?crtfc_key={C2.DART_KEY}&corp_code={CORP}"
         f"&bgn_de={Y0}0101&pblntf_ty=A&page_count=100")
    d = json.loads(urllib.request.urlopen(u, timeout=25).read().decode())
    out = {}
    for r in sorted(d.get("list", []), key=lambda r: r["rcept_no"]):
        m = re.search(r"\((\d{4})\.(\d{2})\)", r["report_nm"])
        if m and m.group(2) in PERIOD and m.group(1) >= SEG_Y0:
            out[f"{m.group(1)}-{m.group(2)}"] = r["rcept_no"]
    return out


def _n(s):
    s = _html.unescape(re.sub(r"<[^>]+>", "", s)).replace(",", "").replace("\xa0", "").strip()
    if s in ("", "-", "−"):
        return 0.0
    neg = s.startswith("(") and s.endswith(")")
    try:
        v = float(s.strip("()"))
    except ValueError:
        return None
    return -v if neg else v


def seg_tables(rcept):
    """보고서 원문에서 '영업부문별 경영성과' 표 → [당기 누적, 전기 누적] (천원 → 십억)."""
    b = urllib.request.urlopen(f"https://opendart.fss.or.kr/api/document.xml?crtfc_key={C2.DART_KEY}"
                               f"&rcept_no={rcept}", timeout=90).read()
    z = zipfile.ZipFile(io.BytesIO(b))
    t = z.read(max(z.namelist(), key=lambda n: z.getinfo(n).file_size)).decode("utf-8", errors="replace")
    i = t.find("영업부문별")
    if i < 0:
        return None
    body = t[i:i + 20000]
    rows = []
    for tr in re.findall(r"<TR[^>]*>(.*?)</TR>", body, re.S):
        cells = [_html.unescape(re.sub(r"<[^>]+>", "", c)).strip()
                 for c in re.findall(r"<T[DHE][^>]*>(.*?)</T[DHE]>", tr, re.S)]
        if cells:
            rows.append(cells)
    tabs, head = [], None
    for c in rows:
        k = c[0].replace(" ", "")
        if k == "구분":
            head = [x.replace(" ", "") for x in c[1:]]
        elif head and k == "매출":
            tabs.append({"head": head, "rev": [_n(x) for x in c[1:]]})
        elif head and tabs and k in ("영업손익", "영업이익", "영업이익(손실)") and "op" not in tabs[-1]:
            tabs[-1]["op"] = [_n(x) for x in c[1:]]
        if len(tabs) >= 2 and "op" in tabs[1]:
            break
    out = []
    for tb in tabs[:2]:
        d = {}
        for j, nm in enumerate(tb["head"]):
            nm = "조정" if ("조정" in nm or "제거" in nm) else nm          # 2023 은 '연결조정'
            if nm in SEGS and j < len(tb["rev"]) and tb["rev"][j] is not None:
                op = tb.get("op", [])
                d[nm] = [round(tb["rev"][j] / 1e6, 3), round((op[j] if j < len(op) and op[j] is not None else 0) / 1e6, 3)]
        out.append(d)
    return out if out and "합계" in out[0] else None


IMP_FROM = "2022-01"


def imports():
    """관세청 품목별·국가별 수입(nitemtrade, 키 = DATA_GO_KR_KEY). 6자리 950300 으로 부르면 10자리·국가·월이 한 번에 온다.
       조회 기간이 1년 이내라 12개월씩. 반환 {"jpToy": {"2026-08": 6.2}, "cnFig": {...}} ($M)"""
    import urllib.parse
    import xml.etree.ElementTree as ET
    import fetch_trade as FT
    if not FT.DATA_GO_KR_KEY:
        raise RuntimeError("DATA_GO_KR_KEY 없음")
    now = datetime.datetime.now(KST)
    ms = []
    y, m = int(IMP_FROM[:4]), int(IMP_FROM[5:])
    while (y, m) <= (now.year, now.month):
        ms.append(f"{y}{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    # 계열 = (부르는 6자리, 원산지, 10자리 — None 이면 그 6자리 전체)
    SER = {"jpToy": ("950300", "JP", None), "cnFig": ("950300", "CN", "9503002130"),
           "nsHw": ("950450", "CN", "9504509000"), "nsSw": ("950490", "JP", "9504909090")}
    out = {k: {} for k in SER}
    for i in range(0, len(ms), 12):
        w = ms[i:i + 12]
        for hs6 in sorted({v[0] for v in SER.values()}):
            p = {"serviceKey": FT.DATA_GO_KR_KEY, "strtYymm": w[0], "endYymm": w[-1], "hsSgn": hs6}
            raw = urllib.request.urlopen(urllib.request.Request(FT.API + "?" + urllib.parse.urlencode(p, safe=""),
                                                                headers={"User-Agent": "Mozilla/5.0"}), timeout=90).read()
            root = ET.fromstring(raw)
            msg = root.findtext(".//resultMsg") or ""
            if msg and "정상" not in msg:
                raise RuntimeError(msg[:60])
            for it in root.iter("item"):
                g = lambda t: (it.findtext(t) or "").strip()
                ym, hs, cd = g("year"), g("hsCd"), g("statCd")
                if not re.fullmatch(r"\d{4}\.\d{2}", ym):
                    continue
                try:
                    v = float(g("impDlr").replace(",", "")) / 1e6
                except ValueError:
                    continue
                k = ym.replace(".", "-")
                for nm, (h6, cc, h10) in SER.items():
                    if h6 == hs6 and cd == cc and (h10 is None or hs == h10):
                        out[nm][k] = out[nm].get(k, 0) + v
    return {nm: {k: round(v, 3) for k, v in sorted(d.items())} for nm, d in out.items()}


def main():
    html = open(HTML, encoding="utf-8").read()
    old = {}
    m = re.search(r"const DWMODEL\s*=\s*(\{.*?\});", html, re.S)
    if m:
        try:
            old = json.loads(m.group(1))
        except json.JSONDecodeError:
            old = {}
    dead, warn = [], []
    try:
        fin = C2.dart_quarters("CFS", y0=Y0, corp=CORP, acc=ACC)
    except Exception as e:
        fin = {}
        dead.append(f"DART 재무제표: {str(e)[:60]}")
    fin = {k: {kk: round(vv, 3) for kk, vv in v.items()} for k, v in fin.items()}
    # C2._fs 는 네트워크 오류도 '아직 안 낸 보고서'처럼 None 으로 돌려준다 → 호출 하나만 실패해도 그 분기(3Q 면 4Q 까지)가 빠진다.
    # 이미 있던 분기가 빠지면 이전 값을 지키고 경고만 남긴다(빠진 채 저장하면 화면 추정 칸이 통째로 NaN — 2026-09-29 점검에서 발견).
    lost = sorted(k for k in old.get("fin", {}) if k not in fin)
    for k in lost:
        fin[k] = old["fin"][k]
    if lost and fin:
        warn.append(f"손익 재수집 실패 {','.join(lost)} — 이전 값 유지")

    # 연결 누적 매출(검증용) — 분기 매출을 해마다 쌓는다
    cum_rev = {}
    for y in range(Y0, datetime.datetime.now(KST).year + 1):
        s = 0.0
        for q in range(1, 5):
            v = (fin.get(f"{y}Q{q}") or {}).get("rev")
            if v is None:
                break
            s += v
            cum_rev[f"{y}-{('03', '06', '09', '12')[q-1]}"] = s

    keep = lambda d: {k: v for k, v in d.items() if k >= SEG_Y0}
    seg_cum = keep(copy.deepcopy(old.get("segCum", {})))
    src = keep(dict(old.get("src", {})))
    notes = dict(old.get("reclass", {}))          # 재분류 의심 기록(사람이 볼 것)
    try:
        reps = reports()
    except Exception as e:
        reps = {}
        warn.append(f"DART 목록: {str(e)[:50]}")
    for per, rc in sorted(reps.items()):
        if src.get(per) == rc and per in seg_cum:
            continue
        try:
            tb = seg_tables(rc)
        except Exception as e:
            warn.append(f"{per} 원문 실패")
            print(f"  {per} {rc} 원문 실패: {str(e)[:60]}")
            continue
        if not tb:
            warn.append(f"{per} 부문 표 없음")
            print(f"  {per} {rc} 부문 표 없음")
            continue
        cur = tb[0]
        tot, ref = cur["합계"][0], cum_rev.get(per)
        if ref and abs(tot / ref - 1) > 0.005:
            warn.append(f"{per} 부문 합계 불일치")
            print(f"  {per} 부문 합계 {tot:.1f} ≠ 연결 누적 {ref:.1f} — 버림")
            continue
        seg_cum[per], src[per] = cur, rc
        # 재분류 감지 — 이 보고서의 '전기' 표가 우리가 가진 전년 원래 값과 부문별로 다르면(합계는 같고) 부문 경계가 바뀐 것이다.
        # 경고만 남긴다: 이 회사는 재분류 뒤 1Q·반기 비교치는 옛 기준, 3Q·사업보고서 비교치는 새 기준으로 싣는다(2024 실측).
        py = f"{int(per[:4]) - 1}{per[4:]}"
        if len(tb) > 1 and py in seg_cum:
            diff = [f"{k} {seg_cum[py][k][0]:.1f}→{v[0]:.1f}" for k, v in tb[1].items()
                    if k not in ("합계", "조정") and k in seg_cum[py] and abs(v[0] - seg_cum[py][k][0]) > max(0.1, 0.01 * abs(v[0]))]
            if diff:
                notes[per] = f"{py} 비교치 재분류: " + " · ".join(diff)
                warn.append(f"{per} 부문 재분류 의심")
        print(f"  {per} {rc} 부문 {', '.join(f'{k} {v[0]:.1f}/{v[1]:.1f}' for k, v in cur.items())}")

    # 누적 → 분기 — 해마다 그 해 보고서의 **원래 값**만 쓴다(재작성 비교치를 섞으면 2024 처럼 3Q 방송이 −5.3 이 된다).
    # 2024 이전은 못 쓴다 — 2024 사업보고서부터 방송 일부가 라이선스/콘텐츠로 옮겨 가 4Q24 방송이 −10.1 로 나온다(2026-09-29 실측).
    # 안전장치: 부문 분기 매출이 음수이거나 직전 분기·전년 동기 둘 다의 절반 밑이면 기준이 섞인 것으로 보고 그 분기 부문을 뺀다(화면은 손익 합계만).
    seg = {}
    for y in sorted({p[:4] for p in seg_cum}):
        ps = [f"{y}-{m}" for m in ("03", "06", "09", "12")]
        for q, per in enumerate(ps, 1):
            cur = seg_cum.get(per)
            base = {} if q == 1 else seg_cum.get(ps[q - 2])
            if cur is None or base is None:
                continue
            seg[f"{y}Q{q}"] = {k: [round(v[0] - base.get(k, [0, 0])[0], 3), round(v[1] - base.get(k, [0, 0])[1], 3)]
                               for k, v in cur.items() if k != "합계"}
    for k in sorted(seg):
        p1 = seg.get(C2_qadd(k, -1), {}); p4 = seg.get(C2_qadd(k, -4), {})
        bad = [n for n, v in seg[k].items() if n != "조정" and (v[0] < 0 or (
            n in p1 and n in p4 and p1[n][0] > 1 and p4[n][0] > 1 and v[0] < 0.5 * min(p1[n][0], p4[n][0])))]
        if bad:
            warn.append(f"{k} 부문 이상({','.join(bad)}) — 뺌")
            print(f"  {k} 부문 이상 {bad} — 기준이 섞인 것으로 보고 뺌")
            del seg[k]

    try:
        imp = imports()
    except Exception as e:
        imp = old.get("imp", {})
        warn.append(f"관세청 수입: {str(e)[:40]}")
    if old.get("imp") and len(imp.get("jpToy", {})) < len(old["imp"].get("jpToy", {})):
        imp = old["imp"]                                   # 일부 창만 받아진 날 — 옛 값을 지킨다
        warn.append("관세청 수입 일부 실패 — 이전 값 유지")

    if not fin or not seg:
        note_health("대원미디어 모델", ("재료 수집 실패: " + " · ".join(dead + warn))[:160])
        print("[dwmodel] 실패 — " + " · ".join(dead + warn))
        sys.exit(1)
    # 부분 실패는 데이터를 저장하되 사유를 남긴다(runstep 은 성공 종료 때 수집기가 쓴 경고를 지우지 않는다)
    note_health("대원미디어 모델", (" · ".join(warn))[:160] if warn else None)

    out = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "stock": "대원미디어",
           "fin": fin, "seg": seg, "imp": imp, "reclass": notes, "segCum": seg_cum, "src": src}
    if warn:
        print("  경고:", " · ".join(warn))
    for k in sorted(fin)[-6:]:
        f, s = fin[k], seg.get(k, {})
        chk = sum(v[0] for v in s.values())
        print(f"  {k} 매출 {f.get('rev', 0):6.1f} 영업 {f.get('op', 0):5.1f} 순 {f.get('npp', 0):5.1f} | 부문 합 {chk:6.1f} · "
              + " ".join(f"{n[:2]} {v[0]:.1f}/{v[1]:.1f}" for n, v in s.items()))
    if "--dry-run" in sys.argv:
        return
    if imp.get("jpToy"):
        ks = sorted(imp["jpToy"])[-4:]
        print("  수입($M) 일본 완구", {k: imp["jpToy"][k] for k in ks}, "· 중국 피규어", {k: imp["cnFig"].get(k) for k in ks})
        print("  수입($M) 닌텐도 본체(중국)", {k: imp.get("nsHw", {}).get(k) for k in ks}, "· 게임카드(일본)", {k: imp.get("nsSw", {}).get(k) for k in ks})
    if all(old.get(k) == out.get(k) for k in ("fin", "seg", "src", "reclass", "imp")):
        print("변동 없음 — index.html 그대로 둠")
        return
    open(HTML, "w", encoding="utf-8").write(C2._put(html, "DWMODEL", out))
    print(f"[OK] DWMODEL 갱신 · 손익 {len(fin)}분기 · 부문 {len(seg)}분기")


if __name__ == "__main__":
    main()
