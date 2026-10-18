#!/usr/bin/env python3
"""카카오게임즈 분기 손익 모델의 재료 -> index.html 의  const KGMODEL = {...};   (2026-10-13 신설)

화면 '카카오게임즈 분기 손익'(트렌드 탭 · js/app.js 의 renderKgModel)의 **실적 칸**.
컴투스(C2_IR)와 달리 IR 수기 입력이 필요 없다 — DART 보고서 원문에 둘 다 있다.

  fin   연결 손익(계속영업) — 전체 재무제표 API(fetch_c2model.dart_quarters 재사용)
  seg   PC게임 · 모바일게임 매출 — 원문 'II. 사업의 내용 > 주요 제품 등의 현황'(누적 → 분기 차분)
  cost  영업비용 항목 — 원문 주석 '영업비용'(연결) · 3개월 칸. 사업보고서는 연간이라 4Q = 연간 − 1~3Q
        매출연동비 = 앱마켓·플랫폼 수수료 + 개발사 수익배분(주석 주1). 퍼블리셔라 매출을 총액으로 잡고 이걸 비용으로 낸다.
  rk    게임별 한국 매출순위(2026-10-18 신설) — gamerscroll 게임 페이지. 최근 90일 **일별**(차트에 박힌 JSON) +
        2025-12 부터 **월평균**(월별 추이 표). 일별은 매일 받아 쌓는다(90일 창이 밀려도 안 잃게). 200위 밖 = null.
        화면이 이걸로 게임별 국내 매출을 세고, DART 모바일 실적 − 국내 게임 합 = 해외·기타로 둔다.

⚠ 2025 3Q 에 골프(카카오VX)·무선통신을 중단영업으로 뺐다. 2025 1Q·반기 원본은 골프가 섞여 있어
  **2026 보고서의 전기 비교치(재작성)를 우선**한다(fin 은 dart_quarters 가 이미 그렇게 한다).
⚠ 보고서 접수번호를 `src` 에 남기고, 이미 받은 보고서는 원문을 다시 받지 않는다(평소 목록 1 + 재무 API 12요청).

  python fetch_kgmodel.py            # 수집·저장
  python fetch_kgmodel.py --dry-run  # 출력만
"""
import datetime, html as _html, io, json, re, sys, urllib.parse, urllib.request, zipfile

import fetch_c2model as C2
try:
    from collector_health import note_health, ua, nap
except Exception:
    def note_health(*a, **k): pass
    def ua(**k): return {"User-Agent": "Mozilla/5.0"}
    def nap(x): pass

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
CORP = "01137383"          # 카카오게임즈 (293490)
Y0 = "2024"
PERIOD = {"03": 1, "06": 2, "09": 3, "12": 4}
# 비용 묶음 — 주석 계정 → 모델 줄
COST = {
    "rs":  ("매출연동비",),
    "lab": ("급여", "퇴직급여", "주식보상비용", "복리후생비"),
    "fee": ("지급수수료",),
    "mkt": ("광고선전비",),
    "dep": ("감가상각비", "사용권자산상각비", "무형자산상각비"),
}

# 게임별 순위 — (키, 표시명, gamerscroll 주소 조각, 손익표 줄). 줄: dk 도깨비 · odin · uma · aaw · etc(기타 국내)
# ⚠ 주소는 gamerscroll 게임 DB(/ko/games/) 목록에서 찾았다 — 아키에이지 워는 'archeage-war' 가 붙는다.
#   새 게임이 나오면 여기 한 줄. 페이지가 아직 없으면(404) 조용히 건너뛴다(도깨비도 출시 열흘쯤 뒤에 생겼다).
GAMES = [
    ("dk",    "도깨비의세계",          "도깨비의세계",                  "dk"),
    ("odin",  "오딘: 발할라 라이징",    "오딘-발할라-라이징",             "odin"),
    ("uma",   "우마무스메",            "우마무스메-프리티-더비",          "uma"),
    ("aaw",   "아키에이지 워",          "아키에이지-워-archeage-war",     "aaw"),
    ("ares",  "아레스",               "아레스-라이즈-오브-가디언즈",       "etc"),
    ("rom",   "롬(R.O.M)",            "롬-리멤버-오브-마제스티",          "etc"),
    ("pcr",   "프린세스 커넥트",        "프린세스-커넥트-redive",          "etc"),
    ("fpop",  "프렌즈팝콘",            "프렌즈팝콘",                    "etc"),
    ("gt",    "가디언 테일즈",          "가디언-테일즈",                  "etc"),
    ("es",    "에버소울",              "에버소울-eversoul",              "etc"),
]
RK_KEEP = 540          # 일별 보관 일수


def game_ranks(slug):
    """gamerscroll 게임 페이지 → ({날짜: [구글, 애플]}, {YYYY-MM: [구글, 애플]}). 없는 순위 = None."""
    u = "https://gamerscroll.com/ko/games/" + urllib.parse.quote(slug) + "/"
    t = urllib.request.urlopen(urllib.request.Request(u, headers=ua(doc=True)), timeout=25).read().decode("utf-8", "replace")
    daily, monthly = {}, {}
    m = re.search(r'\{"labels":\["\d{4}-\d{2}-\d{2}"', t)
    if m:
        o, _ = json.JSONDecoder().raw_decode(t[m.start():])
        ser = {x["name"]: x["values"] for x in o.get("series", [])}
        g, a = ser.get("구글플레이", []), ser.get("앱스토어", [])
        for i, d in enumerate(o.get("labels", [])):
            gv = g[i] if i < len(g) else None
            av = a[i] if i < len(a) else None
            daily[d] = [gv, av]
    for tb in re.findall(r"<table[^>]*>(.*?)</table>", t, re.S | re.I):
        rows = [[_html.unescape(re.sub(r"<[^>]+>", "", x)).strip()
                 for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
                for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S | re.I)]
        rows = [r for r in rows if r]
        if not rows or rows[0][0] != "월":
            continue
        for c in rows[1:]:
            mm = re.match(r"(\d{4})년\s*(\d+)월", c[0])
            if not mm or len(c) < 4:
                continue
            num = lambda x: float(x) if re.match(r"^\d+(\.\d+)?$", x) else None
            monthly[f"{mm.group(1)}-{int(mm.group(2)):02d}"] = [num(c[3]), num(c[1])]    # [구글, 애플]
    return daily, monthly


def ranks(old_rk):
    """게임별 순위를 받아 옛 일별 기록과 합친다. 실패한 게임은 옛 값을 그대로 둔다."""
    out, bad = {}, []
    for key, nm, slug, line in GAMES:
        prev = (old_rk or {}).get(key) or {}
        d, m = dict(prev.get("d") or {}), dict(prev.get("m") or {})
        try:
            dd, mm = game_ranks(slug)
            d.update(dd)
            m.update(mm)
        except Exception as e:
            if "404" not in str(e):
                bad.append(f"{nm} {str(e)[:30]}")
        nap(0.4)
        if not d and not m:
            continue
        keep = sorted(d)[-RK_KEEP:]
        out[key] = {"nm": nm, "line": line, "d": {k: d[k] for k in keep}, "m": dict(sorted(m.items()))}
    return out, bad


def reports():
    """정기보고서 → {"2026-06": 접수번호}. 정정이 있으면 최신 접수가 이긴다."""
    u = (f"https://opendart.fss.or.kr/api/list.json?crtfc_key={C2.DART_KEY}&corp_code={CORP}"
         f"&bgn_de={Y0}0101&pblntf_ty=A&page_count=100")
    d = json.loads(urllib.request.urlopen(u, timeout=25).read().decode())
    out = {}
    for r in sorted(d.get("list", []), key=lambda r: r["rcept_no"]):
        m = re.search(r"\((\d{4})\.(\d{2})\)", r["report_nm"])
        if m and m.group(2) in PERIOD and m.group(1) >= Y0:
            out[f"{m.group(1)}-{m.group(2)}"] = r["rcept_no"]
    return out


def _n(s):
    s = _html.unescape(re.sub(r"<[^>]+>", "", s)).replace(",", "").replace("\xa0", "").replace("　", "").strip()
    if s in ("", "-", "−"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    try:
        v = float(s.strip("()"))
    except ValueError:
        return None
    return -v if neg else v


def _rows(t):
    out = []
    for tr in re.findall(r"<TR[^>]*>(.*?)</TR>", t, re.S):
        c = [x for x in re.findall(r"<T[DHE][^>]*>(.*?)</T[DHE]>", tr, re.S)]
        c = [_html.unescape(re.sub(r"<[^>]+>", "", x)).replace("\xa0", " ").replace("　", " ").strip() for x in c]
        c = [x for x in c if x]
        if c:
            out.append(c)
    return out


def _doc(rcept):
    b = urllib.request.urlopen(f"https://opendart.fss.or.kr/api/document.xml?crtfc_key={C2.DART_KEY}"
                               f"&rcept_no={rcept}", timeout=120).read()
    z = zipfile.ZipFile(io.BytesIO(b))
    return z.read(max(z.namelist(), key=lambda n: z.getinfo(n).file_size)).decode("utf-8", errors="replace")


def products(t):
    """'주요 제품 등의 현황' → {"pc": 당기 누적, "mob": ...} (십억). 첫 숫자 칸 = 당기."""
    i = t.find("주요 제품 등의 현황")
    if i < 0:
        return None
    out = {}
    for c in _rows(t[i:i + 15000]):
        k = c[0].replace(" ", "")
        key = "pc" if k.startswith("PC") else "mob" if k.startswith("모바일") else None
        if key and key not in out:
            nums = [_n(x) for x in c[1:]]
            nums = [x for x in nums if x is not None and abs(x) >= 100]       # 비중(%) 칸은 버린다
            if nums:
                out[key] = round(nums[0] / 1e3, 3)                             # 백만원 → 십억
        if len(out) == 2:
            break
    return out if len(out) == 2 else None


def region(t):
    """'영업부문별 연결 매출실적' → {"ov": 해외 당기 누적, "dom": 국내} (십억). 첫 숫자 칸 = 당기."""
    i = t.find("영업부문별 연결 매출실적")
    if i < 0:
        return None
    out = {}
    for c in _rows(t[i:i + 8000]):
        for j, x in enumerate(c):
            k = x.replace(" ", "")
            key = "ov" if k == "해외" else "dom" if k == "국내" else None
            if key and key not in out:
                nums = [_n(y) for y in c[j + 1:]]
                nums = [y for y in nums if y is not None]
                if nums:
                    out[key] = round(nums[0] / 1e3, 3)
                break
        if len(out) == 2:
            break
    return out if len(out) == 2 else None


def costs(t):
    """주석 '영업비용 - 연결' 첫 표(당기) → {계정: [3개월, 누적]} 또는 사업보고서면 {계정: [연간]} (십억).
       표의 칸 순서가 [합계 3개월·누적, 중단 3개월·누적, 계속 3개월·누적] 이라 **뒤에서부터** 계속영업을 읽는다.
       계정 줄에는 계속영업 칸만 숫자가 있다(2026 반기 원문 실측 — 항목 합이 계속영업 합계와 맞는다).
       전기(비교) 표도 같이 돌려준다: (당기, 전기)."""
    m = re.search(r"영업비용\s*-\s*연결", t)
    if not m:
        return None
    seg = t[m.start(): m.start() + 60000]
    stop = re.search(r"\d+\.\s*법인세", seg)
    if stop:
        seg = seg[:stop.start()]
    tabs, cur = [], None
    for c in _rows(seg):
        k = c[0].replace(" ", "")
        if k in ("당반기", "전반기", "당분기", "전분기", "당기", "전기", "당기누적", "전기누적") or k.startswith(("당반기", "전반기", "당분기", "전분기")):
            cur = {}
            tabs.append(cur)
            continue
        if cur is None:
            continue
        nums = [_n(x) for x in c[1:]]
        nums = [x for x in nums if x is not None]
        if not nums:
            continue
        nm = re.sub(r"\(주\d*\)", "", k)
        if nm == "영업비용" or nm.startswith("영업비용합계") or nm == "합계":
            cur["_tot"] = [round(x / 1e6, 3) for x in nums]
        elif nm not in cur:
            cur[nm] = [round(x / 1e6, 3) for x in nums]
    tabs = [x for x in tabs if x]
    return (tabs[0], tabs[1] if len(tabs) > 1 else None) if tabs else None


def group(tab, idx):
    """계정 → 모델 줄 묶음. idx = 읽을 칸(뒤에서부터 -2 = 3개월, -1 = 누적/연간)."""
    if not tab:
        return None
    pick = lambda v: v[idx] if len(v) >= -idx else v[-1]
    out, used = {}, set()
    for k, names in COST.items():
        s = 0.0
        for nm in names:
            if nm in tab:
                s += pick(tab[nm])
                used.add(nm)
        out[k] = round(s, 3)
    out["oth"] = round(sum(pick(v) for nm, v in tab.items() if nm not in used and nm != "_tot"), 3)
    if "_tot" in tab:
        out["tot"] = pick(tab["_tot"])
    return out


def qadd(q, n):
    k = int(q[:4]) * 4 + int(q[-1]) - 1 + n
    return f"{k // 4}Q{k % 4 + 1}"


def main():
    html = open(HTML, encoding="utf-8").read()
    old = {}
    m = re.search(r"const KGMODEL\s*=\s*(\{.*?\});", html, re.S)
    if m:
        try:
            old = json.loads(m.group(1))
        except json.JSONDecodeError:
            old = {}
    dead, warn = [], []
    try:
        cfs = C2.dart_quarters("CFS", y0=int(Y0), corp=CORP)
    except Exception as e:
        cfs = {}
        dead.append(f"재무 API: {str(e)[:60]}")
    fin = {k: {kk: round(vv, 2) for kk, vv in v.items()} for k, v in cfs.items() if k >= "2024Q1"}

    # 원문 — 누적 PC/모바일, 비용(3개월·누적, 전기 비교)
    src = dict(old.get("src") or {})
    raw = dict(old.get("raw") or {})                 # {"2026-06": {"prod":..., "cost":[당기, 전기]}}
    try:
        reps = reports()
    except Exception as e:
        reps = {}
        dead.append(f"보고서 목록: {str(e)[:60]}")
    for per, rc in sorted(reps.items()):
        if src.get(per) == rc and per in raw and "reg" in raw[per]:
            continue
        try:
            t = _doc(rc)
        except Exception as e:
            warn.append(f"{per} 원문 실패")
            print(f"  [경고] {per} 원문 실패: {e}")
            continue
        p, c, rg = products(t), costs(t), region(t)
        if not p:
            warn.append(f"{per} 주요제품 표 못 찾음")
        if not c:
            print(f"  [참고] {per} 영업비용 주석 못 찾음(옛 양식) — 다음 해 보고서의 전기 비교치로 채운다")
        raw[per] = {"prod": p, "cost": list(c) if c else None, "reg": rg}
        src[per] = rc
        print(f"  {per} {rc} · 제품 {p} · 비용 표 {len(c) if c else 0}개")

    # 분기 PC/모바일 — 누적 차분
    seg = {}
    for per in sorted(raw):
        y, mm = per.split("-")
        q = PERIOD[mm]
        p = (raw[per] or {}).get("prod")
        if not p:
            continue
        prev = (raw.get(f"{y}-{['', '03', '06', '09'][q - 1]}") or {}).get("prod") if q > 1 else {"pc": 0, "mob": 0}
        if prev is None:
            continue
        seg[f"{y}Q{q}"] = {k: round(p[k] - prev[k], 2) for k in ("pc", "mob")}

    # 분기 국내/해외 — 누적 차분(국내·해외 합 = 연결 매출)
    reg = {}
    for per in sorted(raw):
        y, mm = per.split("-")
        q = PERIOD[mm]
        r = (raw[per] or {}).get("reg")
        if not r:
            continue
        prev = (raw.get(f"{y}-{['', '03', '06', '09'][q - 1]}") or {}).get("reg") if q > 1 else {"ov": 0, "dom": 0}
        if prev is None:
            continue
        reg[f"{y}Q{q}"] = {k: round(r[k] - prev[k], 2) for k in ("ov", "dom")}

    # 분기 비용 — 당기 3개월(분기보고서) · 전기 3개월(재작성 비교치가 우선) · 4Q = 연간 − 1~3Q
    cost, rest = {}, {}
    for per in sorted(raw):
        y, mm = per.split("-")
        q = PERIOD[mm]
        c = (raw[per] or {}).get("cost")
        if not c:
            continue
        if q < 4:
            g = group(c[0], -2)
            if g:
                cost[f"{y}Q{q}"] = g
            gp = group(c[1], -2) if len(c) > 1 else None
            if gp:
                rest[f"{int(y) - 1}Q{q}"] = gp
        else:
            g = group(c[0], -1)
            if g:
                cost[f"{y}A"] = g
            gp = group(c[1], -1) if len(c) > 1 else None
            if gp:
                rest[f"{int(y) - 1}A"] = gp
    for k, v in rest.items():
        cost[k] = v                                   # 재작성 비교치가 이긴다
    for k in [k for k in cost if k.endswith("A")]:
        y = k[:4]
        qs = [cost.get(f"{y}Q{i}") for i in (1, 2, 3)]
        if all(qs):
            cost[f"{y}Q4"] = {kk: round(cost[k][kk] - sum(x[kk] for x in qs), 3) for kk in cost[k] if all(kk in x for x in qs)}
        del cost[k]
    for q in fin:
        if q >= "2024Q1" and q not in cost:
            warn.append(f"{q} 비용 항목 없음")
    # 검산 — 항목 합 = 연결 영업비용
    for q, v in sorted(cost.items()):
        s = sum(v[k] for k in ("rs", "lab", "fee", "mkt", "dep", "oth"))
        ox = (fin.get(q) or {}).get("opex")
        if ox and abs(s - ox) > max(1.0, ox * 0.02):
            warn.append(f"{q} 비용 합 {s:.1f} ≠ 영업비용 {ox:.1f}")
        v.pop("tot", None)

    rk, bad = ranks(old.get("rk"))
    if bad:
        warn.append("순위 " + " · ".join(bad))
    if len(bad) > len(GAMES) // 2:
        rk = old.get("rk") or rk

    if not fin:
        note_health("카카오게임즈 모델", ("재료 수집 실패: " + " · ".join(dead + warn))[:160])
        print("[kgmodel] 실패 — " + " · ".join(dead + warn))
        sys.exit(1)
    note_health("카카오게임즈 모델", (" · ".join(dead + warn))[:160] if (dead or warn) else None)

    out = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "stock": "카카오게임즈",
           "fin": fin, "seg": dict(sorted(seg.items())), "cost": dict(sorted(cost.items())), "reg": dict(sorted(reg.items())), "src": src, "raw": raw, "rk": rk}
    for k, v in rk.items():
        ds = sorted(v["d"])
        print(f"  순위 {v['nm']:12s} 일별 {len(ds)}일 {ds[0] if ds else '-'}~{ds[-1] if ds else '-'} · 최근 {v['d'][ds[-1]] if ds else '-'} · 월 {len(v['m'])}")
    for q in sorted(fin)[-6:]:
        print(f"  {q} 연결 {fin[q]} · 부문 {seg.get(q)} · 국내/해외 {reg.get(q)} · 비용 {cost.get(q)}")
    if warn:
        print("  경고: " + " · ".join(warn))
    if "--dry-run" in sys.argv:
        return
    if old and all(old.get(k) == out.get(k) for k in ("fin", "seg", "cost", "rk", "reg")):
        print("변동 없음 — index.html 그대로 둠")
        return
    open(HTML, "w", encoding="utf-8", newline="").write(C2._put(html, "KGMODEL", out))
    print(f"[OK] KGMODEL 갱신 · 분기 {len(fin)} · 부문 {len(seg)} · 비용 {len(cost)}")


if __name__ == "__main__":
    main()
