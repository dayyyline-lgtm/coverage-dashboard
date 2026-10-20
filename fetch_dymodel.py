#!/usr/bin/env python3
"""디어유(버블) 분기 손익 모델의 재료 -> index.html 의  const DYMODEL = {...};   (2026-10-20 신설)

화면 '디어유 분기 손익'(종목 페이지 손익 탭 · js/app.js 의 renderDyModel)의 **실적 칸**과 선행 지표.
카카오게임즈처럼 IR 수기 입력 없이 DART 원문에서 다 읽는다. 국가별(중국·일본…) 구독 비중만 IR 장표에 있어 화면(DY_IR)에 수기로 둔다.

  fin   연결 손익 — 전체 재무제표 API(fetch_c2model.dart_quarters 재사용). 2Q24 부터 연결(Dear U International), 그 앞은 별도와 같다.
  seg   매출 실적 — 원문 'II. 사업의 내용 > 매출(영업수익) > 매출 실적' 표(천원 · 누적 → 분기 차분)
        bd 버블 내수 · bo 버블 수출 · od 기타 내수 · oo 기타 수출(해외 로열티 = 일본 JV·QQ뮤직·JOOX + 라이선스)
  sub   분기 평균 구독수(만) · 해외 이용 비중(%) — 원문 문장 '2분기 평균 197만의 구독수' · '해외 이용 비중은 66%'
        ⚠ 구독수는 '구독 건수'다(한 사람이 아티스트 둘이면 2). 버블 포 재팬·더 버블(북미)·QQ뮤직 버블은 안 들어간다.
  jp    일본 JV(Dear U plus · 관계기업) 영업수익 — 주석 '특수관계자 거래' 당기 누적. 새 양식(엔터티가 열인 표 · 2025 사업보고서~)만 읽는다.
  cost  영업비용 항목 — 주석 '영업비용'(연결) · 3개월 칸. 사업보고서는 연간이라 4Q = 연간 − 1~3Q
        fee 지급수수료(앱마켓 결제수수료 + PG + 서버 등 · 소속사 몫은 매출에서 순액으로 빠져 여기 없다) · lab 인건비 · dep 상각 · oth 기타(광고선전비 포함)
  fx    분기 평균 환율(원/달러 · 원/위안) — 네이버 환율 일별(해외 ARPU 를 달러로 되돌리는 재료)
  rk    버블 앱 매출순위 — 애플 '소셜 네트워킹'(6005) 매출 100 · 구글 플레이 'SOCIAL' 매출 100, 나라별. 하루 1점(05시).
        Dear U 가 낸 앱(리슨·bubble with STARS·JYPnation·STARSHIP…)만 담는다. {"apps":[[id, 이름]], "d":{날짜:{"i_kr":"앱번호:순위,…"}}}

⚠ '순액법' — 소속사 몫(엔터테인먼트 수수료)은 매출과 지급수수료에서 같이 뺀다(2023 사업보고서 원재료 절).
  그래서 매출 = 결제액 − 소속사 몫, 지급수수료 = 앱마켓·PG 수수료 + 서버 등. 결제액(총매출)은 IR 장표에만 있다.
⚠ 보고서 접수번호를 `src` 에 남기고, 이미 받은 보고서는 원문을 다시 받지 않는다(평소 목록 1 + 재무 API 14 + 환율 2×16 + 순위 10요청).

  python fetch_dymodel.py            # 수집·저장
  python fetch_dymodel.py --dry-run  # 출력만
"""
import datetime, html as _html, io, json, re, sys, urllib.parse, urllib.request, zipfile

import fetch_c2model as C2
try:
    from collector_health import note_health, ua, nap
except Exception:
    def note_health(*a, **k): pass
    def ua(**k): return {"User-Agent": "Mozilla/5.0"}
    def nap(x): pass

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
CORP = "01456011"          # 디어유 (376300)
Y0 = "2024"
PERIOD = {"03": 1, "06": 2, "09": 3, "12": 4}
# ⚠ 광고선전비는 따로 두지 않는다 — 옛 양식(~2025 3Q)에는 계정이 없고 기타비용에 들어 있어, 새 양식 연간에서 1~3Q 를 빼면
#   4Q 광고비가 1년치로 튀고 기타가 음수가 된다(2025 4Q 0.80 / −0.24). 기타(oth)에 같이 담는다(분기 0.1~0.2 수준).
COST = {
    "fee": ("지급수수료",),
    "lab": ("급여", "퇴직급여", "복리후생비", "주식보상비용"),
    "dep": ("감가상각비", "사용권자산상각비", "무형자산상각비"),
}
FX_FROM = "2023-01-01"
# 앱 순위 — (키, 애플 RSS 국가) · (키, 구글 gl, hl). 중국은 구글이 없어 애플만(중국 앱스토어에 리슨·JYPnation 이 잡힌다).
RK_IOS = [("kr", "kr"), ("cn", "cn"), ("jp", "jp"), ("tw", "tw"), ("th", "th"), ("us", "us")]
RK_AND = [("kr", "KR", "ko"), ("jp", "JP", "ja"), ("tw", "TW", "zh-TW"), ("us", "US", "en")]
RK_KEEP = 400
# 일본 JV(버블 포 재팬 · 2024-06 출시) 수익이 특수관계자 표에 처음 나온 보고서. 그 앞 보고서에 없는 건 0 이다.
JP_FROM = "2024-09"


# ── DART 원문 ─────────────────────────────────────────────────────────────
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


def _doc(rcept):
    b = urllib.request.urlopen(f"https://opendart.fss.or.kr/api/document.xml?crtfc_key={C2.DART_KEY}"
                               f"&rcept_no={rcept}", timeout=120).read()
    z = zipfile.ZipFile(io.BytesIO(b))
    return z.read(max(z.namelist(), key=lambda n: z.getinfo(n).file_size)).decode("utf-8", errors="replace")


def _cell(x):
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", "", x)).replace("\xa0", " ").replace("　", " ")).strip()


def _n(s, dash0=False):
    s = (s or "").replace(",", "").replace(" ", "")
    if s in ("-", "−", "–"):
        return 0.0 if dash0 else None
    neg = s.startswith("(") and s.endswith(")")
    try:
        v = float(s.strip("()"))
    except ValueError:
        return None
    return -v if neg else v


def _tables(t):
    """[[행 [칸…]]…] — 빈 칸도 남긴다(특수관계자 표는 칸 위치가 엔터티다)."""
    out = []
    for tb in re.findall(r"<TABLE[^>]*>(.*?)</TABLE>", t, re.S | re.I):
        rows = []
        for tr in re.findall(r"<TR[^>]*>(.*?)</TR>", tb, re.S | re.I):
            c = [_cell(x) for x in re.findall(r"<T[DHE][^>]*>(.*?)</T[DHE]>", tr, re.S | re.I)]
            if any(c):
                rows.append(c)
        if rows:
            out.append(rows)
    return out


def _plain(t):
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", t)).replace("\xa0", " ").replace("　", " "))


def subs(t):
    """'N분기 평균 197만의 구독수' · '해외 이용 비중은 66%' → (분기, 구독수 만, 해외 비중 %)."""
    p = _plain(t)
    m = re.search(r"([1-4])\s*분기\s*평균\s*([\d,.]+)\s*만\s*의?\s*구독", p)
    o = re.search(r"해외\s*이용\s*비중[은이]?\s*(\d+(?:\.\d+)?)\s*%", p)
    return (int(m.group(1)) if m else None, float(m.group(2).replace(",", "")) if m else None,
            float(o.group(1)) if o else None)


def products(t):
    """'매출 실적' 표 → {"bo","bd","oo","od"} 당기 누적(십억). 첫 숫자 칸 = 당기."""
    i = t.find("매출 실적")
    if i < 0:
        i = t.find("매출실적")
    if i < 0:
        return None
    for rows in _tables(t[i:i + 20000])[:2]:
        out, item = {}, None
        for c in rows:
            c = [x for x in c if x]
            if not c:
                continue
            k0 = c[0].replace(" ", "")
            if "bubble" in c[0].lower():
                item, c = "b", c[1:]
            elif k0 == "기타":
                item, c = "o", c[1:]
            elif k0.startswith("합계"):
                item, c = None, c[1:]
            if not c or item is None:
                continue
            lab = c[0].replace(" ", "")
            key = {"수출": "o", "내수": "d"}.get(lab)
            nums = [_n(x) for x in c[1:]]
            nums = [x for x in nums if x is not None]
            if key and nums and item + key not in out:
                out[item + key] = round(nums[0] / 1e6, 3)                    # 천원 → 십억
        if len(out) == 4:
            return out
    return None


def costs(t):
    """주석 '영업비용'(연결이 먼저 나온다) → (당기 {계정: [3개월, 누적]}, 전기 {…}) (십억).
       두 양식을 다 읽는다 —
         옛 양식(~2025 3Q): 표 하나, 칸 = [당기 3개월, 당기 누적, 전기 3개월, 전기 누적] · 1Q·사업보고서는 [당기, 전기] · 천원
         새 양식(2025 사업보고서~): '당기/전기(당반기/전반기…)' 소표 둘, 칸 = [3개월, 누적] 또는 [연간] · 원"""
    m = re.search(r"\d+\.\s*영업비용\s*(\(연결\))?", _plain(t))
    if not m:
        return None
    # 원문 XML 에서 같은 제목의 자리를 다시 찾는다
    for mm in re.finditer(r"영업비용", t):
        seg = t[mm.start(): mm.start() + 80000]
        head = _plain(seg[:3000])
        if not re.match(r"영업비용\s*(\(연결\))?\s*(영업비용에 대한 공시|당(기|반기|분기)|\s*\(단위)", head):
            continue
        stop = re.search(r"금융수익\s*및\s*금융비용", seg)
        if stop:
            seg = seg[:stop.start()]
        unit = 1e9 if re.search(r"단위\s*:\s*원", _plain(seg[:6000])) else 1e6
        tabs = _tables(seg)
        if not tabs:
            continue
        cur, prev, parts = {}, {}, []
        for rows in tabs:
            for c in rows:
                cc = [x for x in c if x]
                if not cc:
                    continue
                k0 = cc[0].replace(" ", "")
                if k0 in ("당기", "전기", "당반기", "전반기", "당분기", "전분기") or re.match(r"^(당|전)(기|반기|분기)(\d분기)?$", k0):
                    parts.append({})
                    continue
                # 첫 숫자 칸 앞의 마지막 글자 칸 = 계정
                lab, nums = None, []
                for x in cc:
                    v = _n(x, dash0=True)
                    if v is None and not nums:
                        lab = x.replace(" ", "")
                    elif v is not None:
                        nums.append(v)
                if not lab or not nums:
                    continue
                lab = re.sub(r"\(주\d*\)|\(\*\d*\)", "", lab)
                tgt = parts[-1] if parts else cur
                if lab in ("영업비용", "합계", "영업비용합계"):
                    tgt["_tot"] = [x / unit for x in nums]
                elif lab not in tgt:
                    tgt[lab] = [x / unit for x in nums]
        if parts:                                   # 새 양식
            cur = parts[0]
            prev = parts[1] if len(parts) > 1 else {}
            norm = lambda d: {k: (v if len(v) >= 2 else [None, v[0]]) for k, v in d.items()}
            cur, prev = norm(cur), norm(prev)
        else:                                       # 옛 양식 — 칸 4개 = [당3, 당누, 전3, 전누] · 2개 = [당, 전]
            c2, p2 = {}, {}
            for k, v in cur.items():
                if len(v) >= 4:
                    c2[k], p2[k] = [v[0], v[1]], [v[2], v[3]]
                elif len(v) >= 2:
                    c2[k], p2[k] = [v[0], v[0]], [v[1], v[1]]       # 1Q 는 3개월 = 누적 · 사업보고서는 연간(아래에서 처리)
            cur, prev = c2, p2
        if len(cur) >= 5:
            return cur, prev
    return None


def group(tab, idx):
    """계정 → 모델 줄. idx 0 = 3개월, 1 = 누적(연간)."""
    if not tab:
        return None
    pick = lambda v: v[idx] if v[idx] is not None else v[1]
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
        out["tot"] = round(pick(tab["_tot"]), 3)
    return out


def japan(t):
    """주석 '특수관계자 거래' → Dear U plus(일본 JV) 영업수익 당기 누적(십억). 못 읽으면 None.
       양식이 보고서마다 번갈아 바뀐다 —
         열 양식(2025 사업보고서·2026 반기): 엔터티가 열, '영업수익' 행에서 Dear U plus 칸 · 원
         행 양식(2024~2025 분기·2026 1Q): 엔터티가 행, 칸 = [영업수익 당기, 전기, 금융수익…, 영업비용…] · 천원
       ⚠ 관계기업 '요약 재무정보' 표에도 Dear U plus 와 '영업수익'이 같이 나온다(그건 JV 자신의 매출이다).
         그래서 SM(에스엠엔터테인먼트)이 같이 있는 표 = 특수관계자 거래 표만 본다."""
    for tm in re.finditer(r"<TABLE[^>]*>(.*?)</TABLE>", t, re.S | re.I):
        rows = _tables(tm.group(0))
        rows = rows[0] if rows else []
        flat = [x for r in rows for x in r]
        if not any(x.startswith("Dear U plus") for x in flat) or not any("에스엠엔터테인먼트" in x for x in flat):
            continue
        before = _plain(t[max(0, tm.start() - 1500): tm.start()])
        unit = 1e6 if ("천원" in before[-300:] or any("천원" in x for x in flat[:3])) else 1e9
        # 열 양식 = Dear U plus 가 다른 엔터티 이름들과 한 줄에 있다(숫자가 아닌 칸이 셋 이상)
        hi = next((i for i, r in enumerate(rows) if any(x.startswith("Dear U plus") for x in r)
                   and sum(1 for x in r if x and _n(x, dash0=True) is None) > 3), None)
        if hi is not None:                                        # 열 양식
            names = list(rows[hi])
            while names and not names[0]:
                names = names[1:]
            j = next(k for k, x in enumerate(names) if x.startswith("Dear U plus"))
            for r in rows[hi + 1:]:
                if r and r[0].replace(" ", "").startswith("영업수익"):
                    vals = r[1:]
                    if len(vals) < len(names):
                        break
                    v = _n(vals[j], dash0=True)
                    return round((v or 0.0) / unit, 4)
            continue
        head = " ".join(x for r in rows[:3] for x in r)
        pos = {w: head.find(w) for w in ("영업수익", "금융수익", "영업비용", "채권", "채무")}
        first = min((p, w) for w, p in pos.items() if p >= 0) if any(p >= 0 for p in pos.values()) else (0, None)
        if first[1] != "영업수익":
            continue                                              # 첫 지표 칸이 영업수익이 아닌 표(채권·채무 잔액 등)
        for r in rows:
            k = next((i for i, x in enumerate(r) if x.startswith("Dear U plus")), None)
            if k is None:
                continue
            v = _n(r[k + 1], dash0=True) if k + 1 < len(r) else None
            if v is not None:
                return round(v / unit, 4)
    return None


# ── 환율 · 앱 순위 ────────────────────────────────────────────────────────
def fx_quarters():
    """분기 평균 {"USD": {"2026Q2": 1502.8}, "CNY": {...}} — 네이버 환율 일별(60개씩 페이지)."""
    out = {}
    for key, code in (("USD", "FX_USDKRW"), ("CNY", "FX_CNYKRW")):
        allv = {}
        for p in range(1, 40):
            u = (f"https://m.stock.naver.com/front-api/marketIndex/prices?category=exchange&reutersCode={code}"
                 f"&page={p}&pageSize=60")
            d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=ua()), timeout=20).read())
            r = d.get("result") or []
            for x in r:
                try:
                    allv[x["localTradedAt"]] = float(str(x["closePrice"]).replace(",", ""))
                except (KeyError, ValueError):
                    pass
            if len(r) < 60 or (allv and min(allv) < FX_FROM):
                break
            nap(0.15)
        q = {}
        for d, v in allv.items():
            if d < FX_FROM:
                continue
            k = f"{d[:4]}Q{(int(d[5:7]) - 1) // 3 + 1}"
            q.setdefault(k, []).append(v)
        out[key] = {k: round(sum(v) / len(v), 1) for k, v in sorted(q.items())}
        out[key + "_n"] = {k: len(v) for k, v in sorted(q.items())}          # 그 분기에 관측한 영업일 수(진행 중 분기 판단용)
    return out


def ranks_today():
    """오늘 버블 앱 순위 → ({"i_kr": [(id, 이름, 순위)…]}, 실패 목록)."""
    import fetch_appstore as AP
    got, bad = {}, []
    for k, cc in RK_IOS:
        try:
            u = f"https://itunes.apple.com/{cc}/rss/topgrossingapplications/limit=100/genre=6005/json"
            d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=ua()), timeout=30).read().decode("utf-8"))
            es = d.get("feed", {}).get("entry", [])
            if not es:
                raise RuntimeError("빈 목록")
            got["i_" + k] = [((e.get("id", {}).get("attributes", {}) or {}).get("im:bundleId", ""), e.get("im:name", {}).get("label", ""), i)
                             for i, e in enumerate(es, 1) if "dear u" in e.get("im:artist", {}).get("label", "").lower()]
        except Exception as e:
            bad.append(f"애플 {k} {str(e)[:30]}")
        nap(0.3)
    for k, gl, hl in RK_AND:
        try:
            got["a_" + k] = [(pk, t, r) for r, t, dev, pk in _google_social(AP, gl, hl) if "dear u" in (dev or "").lower()]
        except Exception as e:
            bad.append(f"구글 {k} {str(e)[:30]}")
        nap(0.3)
    return got, bad


def _google_social(AP, gl, hl):
    """fetch_appstore.google 과 같은 RPC — 카테고리만 GAME → SOCIAL."""
    inner = [[None, [[8, [20, 100]], None, None, AP.G_FEATS], [2, "topgrossing", "SOCIAL"]]]
    req = [[["vyAe2", json.dumps(inner, separators=(",", ":")), None, "generic"]]]
    body = "f.req=" + urllib.parse.quote(json.dumps(req, separators=(",", ":")))
    u = f"https://play.google.com/_/PlayStoreUi/data/batchexecute?rpcids=vyAe2&hl={hl}&gl={gl}&rt=c"
    h = ua(doc=True)
    h["Content-Type"] = "application/x-www-form-urlencoded;charset=UTF-8"
    h["Accept"] = "*/*"
    t = urllib.request.urlopen(urllib.request.Request(u, data=body.encode(), headers=h), timeout=45).read().decode("utf-8", "replace")
    for line in t[t.index("\n") + 1:].split("\n"):
        s = line.strip()
        if not s.startswith("[["):
            continue
        try:
            a = json.loads(s)
            if a and a[0] and a[0][0] == "wrb.fr":
                lst = json.loads(a[0][2])[0][1][0][28][0]
                out = [(i, it[0][3], it[0][14], it[0][0][0]) for i, it in enumerate(lst, 1)]
                if not out:
                    raise RuntimeError("빈 목록")
                return out
        except (ValueError, IndexError, TypeError):
            pass
    raise RuntimeError("응답에서 목록을 못 찾음")


def merge_ranks(old, today, got):
    """옛 기록 + 오늘. 앱은 번호로 줄여 담는다(번호 = apps 위치 · 맨 뒤에만 덧붙인다)."""
    apps = [list(x) for x in (old or {}).get("apps", [])]
    idx = {a[0]: i for i, a in enumerate(apps)}
    days = dict((old or {}).get("d") or {})
    rec = {}
    for key, lst in got.items():
        parts = []
        for ident, nm, r in lst:
            if not ident:
                continue
            if ident not in idx:
                idx[ident] = len(apps)
                apps.append([ident, nm])
            parts.append(f"{idx[ident]}:{r}")
        rec[key] = ",".join(parts)
    if rec:
        days[today] = rec
    keep = sorted(days)[-RK_KEEP:]
    return {"apps": apps, "d": {k: days[k] for k in keep}}


def qadd(q, n):
    k = int(q[:4]) * 4 + int(q[-1]) - 1 + n
    return f"{k // 4}Q{k % 4 + 1}"


def main():
    html = open(HTML, encoding="utf-8").read()
    old = {}
    m = re.search(r"const DYMODEL\s*=\s*(\{.*?\});", html, re.S)
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
    try:
        ofs = C2.dart_quarters("OFS", y0=int(Y0), corp=CORP)
    except Exception:
        ofs = {}
    # 연결은 2Q24 부터다. 그 앞 분기(연결 비교치도 없는 분기)는 별도로 채운다 — 종속회사가 없던 때라 같다.
    fin = {}
    for k in sorted(set(cfs) | set(ofs)):
        if k < "2024Q1":
            continue
        v = cfs.get(k) or ofs.get(k)
        if v and "rev" in v and "op" in v:
            fin[k] = {kk: round(vv, 3) for kk, vv in v.items()}
            if k not in cfs:
                fin[k]["ofs"] = 1

    src = dict(old.get("src") or {})
    raw = dict(old.get("raw") or {})
    try:
        reps = reports()
    except Exception as e:
        reps = {}
        dead.append(f"보고서 목록: {str(e)[:60]}")
    cache = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--cache=")), None)   # 개발용 — 받아 둔 원문 폴더
    for per, rc in sorted(reps.items()):
        if src.get(per) == rc and per in raw:
            continue
        try:
            if cache:
                import os
                f = os.path.join(cache, rc + ".xml")
                t = open(f, encoding="utf-8").read() if os.path.exists(f) else _doc(rc)
            else:
                t = _doc(rc)
        except Exception as e:
            warn.append(f"{per} 원문 실패")
            print(f"  [경고] {per} 원문 실패: {e}")
            continue
        sq, sn, ov = subs(t)
        p, c, jp = products(t), costs(t), japan(t)
        if not p:
            warn.append(f"{per} 매출 실적 표 못 찾음")
        if not c:
            warn.append(f"{per} 영업비용 주석 못 찾음")
        if sq is None:
            print(f"  [참고] {per} 구독수 문장 못 찾음")
        raw[per] = {"prod": p, "cost": [c[0], c[1]] if c else None, "sq": sq, "sn": sn, "ov": ov, "jp": jp}
        src[per] = rc
        print(f"  {per} {rc} · 매출 {p} · 구독 {sq}Q {sn}만 해외 {ov}% · 일본 JV {jp} · 비용 {len(c[0]) if c else 0}계정")

    def prev_per(per):
        y, mm = per.split("-")
        q = PERIOD[mm]
        return f"{y}-{['', '03', '06', '09'][q - 1]}" if q > 1 else None

    # 분기 매출 실적 — 누적 차분
    seg, jpq = {}, {}
    for per in sorted(raw):
        y, mm = per.split("-")
        q = PERIOD[mm]
        p = (raw[per] or {}).get("prod")
        pp = (raw.get(prev_per(per)) or {}).get("prod") if q > 1 else {"bo": 0, "bd": 0, "oo": 0, "od": 0}
        if p and pp:
            seg[f"{y}Q{q}"] = {k: round(p[k] - pp[k], 3) for k in ("bd", "bo", "od", "oo")}
        jget = lambda pr: 0.0 if (pr and pr < JP_FROM and (raw.get(pr) or {}).get("jp") is None) else (raw.get(pr) or {}).get("jp")
        j = jget(per)
        jprev = jget(prev_per(per)) if q > 1 else 0.0
        if j is not None and jprev is not None:
            jpq[f"{y}Q{q}"] = round(j - jprev, 4)

    # 구독수 — 문장의 분기가 보고서 분기와 같을 때만(사업보고서 = 4분기)
    sub = {}
    for per in sorted(raw):
        y, mm = per.split("-")
        r = raw[per] or {}
        if r.get("sn") is not None and r.get("sq") == PERIOD[mm]:
            sub[f"{y}Q{PERIOD[mm]}"] = {"n": r["sn"], "ov": r.get("ov")}
        elif r.get("ov") is not None:
            sub[f"{y}Q{PERIOD[mm]}"] = {"n": None, "ov": r.get("ov")}

    # 분기 비용 — 당기 3개월 · 전기 3개월(재작성 비교치 우선) · 4Q = 연간 − 1~3Q
    cost, rest = {}, {}
    for per in sorted(raw):
        y, mm = per.split("-")
        q = PERIOD[mm]
        c = (raw[per] or {}).get("cost")
        if not c:
            continue
        if q < 4:
            g = group(c[0], 0)
            if g:
                cost[f"{y}Q{q}"] = g
            gp = group(c[1], 0) if c[1] else None
            if gp:
                rest[f"{int(y) - 1}Q{q}"] = gp
        else:
            g = group(c[0], 1)
            if g:
                cost[f"{y}A"] = g
            gp = group(c[1], 1) if c[1] else None
            if gp:
                rest[f"{int(y) - 1}A"] = gp
    for k, v in rest.items():
        cost[k] = v                                   # 재작성 비교치(다음 해 보고서 · 새 양식)가 이긴다
    for k in [k for k in cost if k.endswith("A")]:
        y = k[:4]
        qs = [cost.get(f"{y}Q{i}") for i in (1, 2, 3)]
        if all(qs):
            cost[f"{y}Q4"] = {kk: round(cost[k][kk] - sum(x[kk] for x in qs), 3) for kk in cost[k] if all(kk in x for x in qs)}
        del cost[k]
    # 검산 — 항목 합 = 연결 영업비용 · 매출 실적 합 = 연결 매출
    for q, v in sorted(cost.items()):
        s = sum(v.get(k, 0) for k in ("fee", "lab", "dep", "oth"))
        ox = (fin.get(q) or {}).get("opex")
        if ox and abs(s - ox) > max(0.3, ox * 0.02):
            warn.append(f"{q} 비용 합 {s:.1f} ≠ 영업비용 {ox:.1f}")
        v.pop("tot", None)
    for q, v in sorted(seg.items()):
        rv = (fin.get(q) or {}).get("rev")
        s = sum(v.values())
        if rv and abs(s - rv) > max(0.2, rv * 0.01):
            warn.append(f"{q} 매출 실적 합 {s:.1f} ≠ 연결 매출 {rv:.1f}")

    try:
        fx = fx_quarters()
    except Exception as e:
        fx = old.get("fx") or {}
        warn.append(f"환율 {str(e)[:40]}")

    today = datetime.datetime.now(KST).date().isoformat()
    try:
        got, bad = ranks_today()
    except Exception as e:
        got, bad = {}, [str(e)[:40]]
    if bad:
        warn.append("앱 순위 " + " · ".join(bad))
    rk = merge_ranks(old.get("rk"), today, got) if got else (old.get("rk") or {"apps": [], "d": {}})

    if not fin or not seg:
        note_health("디어유 모델", ("재료 수집 실패: " + " · ".join(dead + warn))[:160])
        print("[dymodel] 실패 — " + " · ".join(dead + warn))
        sys.exit(1)
    note_health("디어유 모델", (" · ".join(dead + warn))[:160] if (dead or warn) else None)

    out = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "stock": "디어유",
           "fin": fin, "seg": dict(sorted(seg.items())), "sub": dict(sorted(sub.items())), "jp": dict(sorted(jpq.items())),
           "cost": dict(sorted(cost.items())), "fx": fx, "src": src, "raw": raw, "rk": rk}
    for q in sorted(fin)[-10:]:
        print(f"  {q} 연결 {fin[q]} · 매출 {seg.get(q)} · 구독 {sub.get(q)} · 일본 {jpq.get(q)} · 비용 {cost.get(q)}")
    for k, v in got.items():
        print(f"  순위 {k}: " + " · ".join(f"{nm[:18]} {r}" for _, nm, r in v))
    print(f"  환율 USD {dict(list((fx.get('USD') or {}).items())[-4:])} · CNY {dict(list((fx.get('CNY') or {}).items())[-2:])}")
    if warn:
        print("  경고: " + " · ".join(warn))
    if "--dry-run" in sys.argv:
        return
    if old and all(old.get(k) == out.get(k) for k in ("fin", "seg", "sub", "jp", "cost", "fx", "rk")):
        print("변동 없음 — index.html 그대로 둠")
        return
    open(HTML, "w", encoding="utf-8", newline="").write(C2._put(html, "DYMODEL", out))
    print(f"[OK] DYMODEL 갱신 · 분기 {len(fin)} · 매출 실적 {len(seg)} · 구독 {len(sub)} · 비용 {len(cost)} · 순위 {len(rk['d'])}일")


if __name__ == "__main__":
    main()
