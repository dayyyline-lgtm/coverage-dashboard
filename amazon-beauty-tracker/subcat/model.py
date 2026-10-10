# -*- coding: utf-8 -*-
"""AMZSUB 추정 매출 — 세부 카테고리 순위 → 아마존 전체 순위(BSR) → 월 판매량 → × 가격 (2026-10-11).

사용자: "이 데이터를 아마존 top 100 과 누적 매출액 순위로 그래프 시각화". 세부 카테고리 Top100 은 순위뿐이라 매출이 없다.
그래서 같은 저장소의 트래커(history.csv · 미국 상품 페이지 실측)로 두 단계를 맞춘다.

  1) 세부 순위 → 전체 순위.  log 전체BSR = α_c + β · log 세부순위
     · 트래커 행마다 '전체 #m · 세부 카테고리 #r' 이 같이 찍혀 있다 → 카테고리 이름을 맞춰(ALIAS) 실측 쌍으로 쓴다.
       β 는 카테고리 고정효과를 둔 공통 기울기, α_c 는 카테고리마다.
     · 쌍이 없는 카테고리는 '같은 날 같은 SKU 가 두 카테고리에 동시에 오른 자리'로 이어 맞춘다(뷰티 전체 = 전체 순위 그대로, α 0 · β 1).
     · 그래도 닿지 않는 카테고리는 실측 카테고리들의 α 중앙값(사전값)으로 둔다.
  2) 전체 순위 → 월 판매량.  log 판매량 = a + b1 · min(x, x0) + b2 · max(0, x − x0),  x = log 전체BSR, x0 = log 1000
     · 트래커가 상품 페이지에서 읽은 '지난주/지난달 N+개 구매' 배지(최근 8주). 1,024위 안은 주간 배지만 쓴다 —
       월간 배지는 '10K+' 처럼 성겨서 상위권을 크게 깎는다(10위 안 제품이 10,000 으로 찍힌 행이 많다).
     · 배지는 구간의 아랫값이라 판매량이 낮게 나오는 쪽이다(트래커 '하한'과 같은 성격).
  3) 가격 = 그날 카드 가격(collector 가 2026-10-11 부터 줌) → 가장 가까운 날의 카드 가격 → 트래커 가격(USD) →
     같은 카테고리 SKU 가격 중앙값 → 전체 중앙값.

SKU 하나가 여러 카테고리에 오르면 보정 근거가 가장 많은 카테고리의 순위로 환산한다(뷰티 전체가 있으면 그것).
개별 SKU 는 오차가 크다(전체 순위 추정 ±1.7배 · 판매량 곡선 ±3배 수준) — 회사 합계와 추이로 볼 것.
"""
import collections
import csv
import datetime
import math
import statistics as st

# 트래커가 상품 페이지 BSR 줄에서 읽는 카테고리 이름 → 세부 카테고리 번호(config.cats 위치). 이름이 같으면 따로 안 적는다.
# 상품 페이지는 'Facial Serums' · 베스트셀러 페이지 제목은 'Face Serums' 처럼 같은 노드를 다르게 부른다.
ALIAS = {
    "facial serums": 148, "facial masks": 49, "facial toners & astringents": 53, "facial skin care products": 45,
    "eye masks": 55, "neck & décolleté moisturizers": 142, "facial treatments & masks": 56, "eye treatment serums": 119,
    "facial cleansing gels": 47, "facial cleansing products": 46, "concealers & neutralizing makeup": 25,
    "eye treatment products": 54, "hair care products sets & kits": 81, "bb facial creams": 98, "facial night creams": 141,
    "eye wrinkle pads & patches": 121, "facial creams & moisturizers": 52, "body skin care products": 42, "face powder": 27,
    "foundation makeup": 26, "facial tinted moisturizers": 104,
}
TRACK_DAYS = 56          # 보정에 쓰는 트래커 기간
LINK_DAYS = 30           # 이어 맞추기에 쓰는 세부 카테고리 기간
PRIOR_W = 2.0            # α 사전값의 무게(실측 쌍 2개 만큼)
X0 = math.log(1000)      # 판매량 곡선의 꺾이는 점(전체 1,000위)
# 트래커 자료가 모자랄 때 쓰는 곡선(2026-10-11 적합: 배지 3,747개 · 1위 13.4만 · 100위 1.8만 · 1,000위 6,835 · 1만위 1,503개/월)
UNITS_DEFAULT = (11.808, -0.431, -0.658)
FX_USD = {"USD": 1.0}


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def load_tracker(path, asof, days=TRACK_DAYS):
    """미국 행만, asof 로부터 days 일 안. [{date, asin, m, sub, subcat, u, per, price}]"""
    cut = (datetime.date.fromisoformat(asof) - datetime.timedelta(days=days)).isoformat()
    out = []
    try:
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r.get("market") != "US" or (r.get("date") or "") < cut:
                    continue
                out.append({"date": r["date"], "asin": r["asin"], "m": _f(r.get("bsr_main")), "sub": _f(r.get("bsr_sub")),
                            "subcat": (r.get("bsr_sub_cat") or "").strip(), "u": _f(r.get("bought")),
                            "per": r.get("bought_period") or "",
                            "price": _f(r.get("price")) if (r.get("currency") or "USD") in FX_USD else None})
    except FileNotFoundError:
        pass
    return out


def _lstsq(X, y):
    k = len(X[0])
    A = [[sum(X[i][p] * X[i][q] for i in range(len(X))) for q in range(k)] for p in range(k)]
    b = [sum(X[i][p] * y[i] for i in range(len(X))) for p in range(k)]
    for i in range(k):
        for j in range(i + 1, k):
            f = A[j][i] / A[i][i]
            for q in range(i, k):
                A[j][q] -= f * A[i][q]
            b[j] -= f * b[i]
    x = [0.0] * k
    for i in reversed(range(k)):
        x[i] = (b[i] - sum(A[i][q] * x[q] for q in range(i + 1, k))) / A[i][i]
    return x


def _ols(pts):
    """구간 중앙값 회귀 — log10 순위 0.25 칸마다 (x 중앙값, y 중앙값, 개수)를 내고 개수로 가중한 직선.
    배지에는 아주 낮은 값(같은 상품군의 다른 옵션 배지 등)이 섞여 평균 회귀를 끌어내린다 — 중앙값이 튼튼하다."""
    bins = collections.defaultdict(list)
    for x, y in pts:
        bins[int(x / math.log(10) * 4)].append((x, y))
    rows = [(st.median(x for x, _ in v), st.median(y for _, y in v), len(v)) for v in bins.values() if len(v) >= 5]
    if len(rows) < 2:
        rows = [(x, y, 1) for x, y in pts]
    w = sum(n for _, _, n in rows)
    mx = sum(x * n for x, _, n in rows) / w
    my = sum(y * n for _, y, n in rows) / w
    sxx = sum(n * (x - mx) ** 2 for x, _, n in rows)
    b = sum(n * (x - mx) * (y - my) for x, y, n in rows) / sxx
    return my - b * mx, b


def units_curve(trk):
    """위(1,024위 안) = 주간 배지만으로 직선 · 아래 = 전체 배지의 기울기를 1,000위에서 이어 붙인다.
    한 번에 꺾은선 회귀를 하면 꼬리(수천 개)에 끌려 상위권이 배지의 절반으로 나온다(2026-10-11 검산: 300위 안 배지 ÷ 추정 1.3~2.4배)."""
    top = [(math.log(r["m"]), math.log(r["u"])) for r in trk if r["m"] and r["u"] and 1 <= r["m"] < 1024 and r["per"] == "week"]
    tail = [(math.log(r["m"]), math.log(r["u"])) for r in trk if r["m"] and r["u"] and r["m"] >= 1024]
    if len(top) < 80 or len(tail) < 200:
        a, b1, b2 = UNITS_DEFAULT
        return {"a": a, "b1": b1, "b2": b2, "n": len(top) + len(tail), "sd": None, "dflt": 1}
    a1, b1 = _ols(top)
    _, b2 = _ols(tail)
    cv = {"a": round(a1, 4), "b1": round(b1, 4), "b2": round(b2, 4), "n": len(top) + len(tail), "dflt": 0}
    res = [y - math.log(units_month(cv, x)) for x, y in top + tail]
    cv["sd"] = round(st.pstdev(res), 3)
    return cv


def units_month(cv, logm):
    return math.exp(cv["a"] + cv["b1"] * min(logm, X0) + cv["b2"] * max(0.0, logm - X0))


def calibrate(cats, trk, slots):
    """slots: {(date, asin): [(cat 번호, 순위), …]} — 이어 맞추기용(최근 LINK_DAYS).
    반환 {beta, alpha[], supp[] (보정 근거 수), direct (실측 쌍 있는 카테고리 수), linked (이어 맞춘 카테고리 수), npairs}"""
    nc = len(cats)
    low = {(c[1] or "").replace("＆", "&").lower(): i for i, c in enumerate(cats)}
    tri = collections.defaultdict(list)
    for r in trk:
        if r["m"] and r["sub"] and r["subcat"]:
            nm = r["subcat"].lower()
            c = ALIAS.get(nm, low.get(nm))
            if c is not None and c != 0:
                tri[c].append((math.log(r["sub"]), math.log(r["m"])))
    num = den = 0.0
    for ps in tri.values():
        if len(ps) < 3:
            continue
        mx = st.mean(x for x, _ in ps)
        my = st.mean(y for _, y in ps)
        num += sum((x - mx) * (y - my) for x, y in ps)
        den += sum((x - mx) ** 2 for x, _ in ps)
    beta = num / den if den > 0 else 1.2
    bt = lambda c: 1.0 if c == 0 else beta
    direct_a = [st.mean(y - beta * x for x, y in ps) for ps in tri.values() if ps]
    mu = st.median(direct_a) if direct_a else 4.0
    links = collections.defaultdict(list)       # c → [(상대 카테고리, 상대 순위, 내 순위)]
    for ss in slots.values():
        if len(ss) < 2:
            continue
        for i in range(len(ss)):
            for j in range(len(ss)):
                if i != j:
                    links[ss[i][0]].append((ss[j][0], ss[j][1], ss[i][1]))
    alpha = [mu] * nc
    alpha[0] = 0.0
    for _ in range(300):
        mx = 0.0
        for c in range(1, nc):
            s, w = PRIOR_W * mu, PRIOR_W
            for x, y in tri.get(c, ()):
                s += y - beta * x
                w += 1
            for o, ro, rr in links.get(c, ()):
                s += alpha[o] + bt(o) * math.log(ro) - beta * math.log(rr)
                w += 1
            new = s / w
            mx = max(mx, abs(new - alpha[c]))
            alpha[c] = new
        if mx < 1e-7:
            break
    supp = [0.0] * nc
    for c in range(nc):
        supp[c] = 1e9 if c == 0 else len(tri.get(c, ())) + 0.5 * len(links.get(c, ()))
    return {"beta": beta, "alpha": alpha, "supp": supp, "direct": sum(1 for c in tri if tri[c]),
            "linked": sum(1 for c in range(1, nc) if not tri.get(c) and links.get(c)), "npairs": sum(len(v) for v in tri.values())}


def est_logm(ss, cal):
    """[(cat 번호, 순위)] → log 전체 순위. 보정 근거가 가장 많은 카테고리 하나로."""
    c, r = max(ss, key=lambda t: (cal["supp"][t[0]], -t[1]))
    return cal["alpha"][c] + (1.0 if c == 0 else cal["beta"]) * math.log(r), c


def validate(cal, cv, trk, slots):
    """보정에 쓴 자료 안에서의 맞춤 정도 — 트래커가 ±3일 안에 잰 SKU 의 전체 순위·배지 판매량과 비교(중앙 배수)."""
    by = collections.defaultdict(list)
    for r in trk:
        if r["m"]:
            by[r["asin"]].append(r)
    em, eu = [], []
    for (d, a), ss in slots.items():
        cand = [r for r in by.get(a, ()) if abs((datetime.date.fromisoformat(r["date"]) - datetime.date.fromisoformat(d)).days) <= 3]
        if not cand:
            continue
        r = min(cand, key=lambda r: abs((datetime.date.fromisoformat(r["date"]) - datetime.date.fromisoformat(d)).days))
        lm, _ = est_logm(ss, cal)
        em.append(abs(lm - math.log(r["m"])))
        if r["u"]:
            eu.append(math.log(units_month(cv, lm)) - math.log(r["u"]))
    out = {"n": len(em)}
    if em:
        out["bsrX"] = round(math.exp(st.median(em)), 2)
    if eu:
        out["nu"] = len(eu)
        out["uBias"] = round(math.exp(st.median(eu)), 2)      # 추정 ÷ 배지 의 중앙값 (1 이면 맞음, 1 밑이면 추정이 낮다)
    return out


def clean_price(p):
    """트래커 가격에 소수점이 빠진 값이 섞여 있다($14.16 → 1416.0 · $164.61 → 16461.0 — 2026-10-11 미국 행 236개).
    300 달러 넘는 정수는 센트로 읽고, 그래도 600 달러가 넘거나 1 달러 밑이면 버린다."""
    if not p or p <= 0:
        return None
    if p >= 300 and abs(p - round(p)) < 1e-9:
        p = p / 100.0
    return p if 1 <= p <= 600 else None


def tracker_prices(trk):
    out = {}
    for r in sorted(trk, key=lambda r: r["date"]):
        p = clean_price(r["price"])
        if p:
            out[r["asin"]] = p
    return out


def price_lookup(card, asin, date):
    """card: {asin: [(date, usd)] 날짜순}. 그날 이전 마지막 가격 → 없으면 그 뒤 첫 가격."""
    seq = card.get(asin)
    if not seq:
        return None
    best = None
    for d, p in seq:
        if d <= date:
            best = p
        elif best is None:
            return p
        else:
            break
    return best


def estimate(cats, hist, trk, card, asof):
    """hist: {날짜: [(cat_id, 순위, asin)]} → (est, meta)
    est: {날짜: {asin: (월 판매량, 가격 USD, 하루 매출 USD, 가격 출처 c/t/m/g)}}"""
    corder = {c[0]: i for i, c in enumerate(cats)}
    dates = sorted(hist)
    slots_all = {}
    for d in dates:
        g = collections.defaultdict(list)
        for cid, r, a in hist[d]:
            if cid in corder:
                g[a].append((corder[cid], r))
        for a, ss in g.items():
            slots_all[(d, a)] = ss
    cut = (datetime.date.fromisoformat(asof) - datetime.timedelta(days=LINK_DAYS)).isoformat()
    cal = calibrate(cats, trk, {k: v for k, v in slots_all.items() if k[0] >= cut})
    cv = units_curve(trk)
    tp = tracker_prices(trk)
    # 카테고리별 가격 중앙값 — 가격을 아는 SKU(카드·트래커)의 '환산에 쓴 카테고리'로 묶는다
    known = {}
    for (d, a), ss in slots_all.items():
        p = price_lookup(card, a, d) or tp.get(a)
        if p:
            known[a] = (p, est_logm(ss, cal)[1])
    by_cat = collections.defaultdict(list)
    for p, c in known.values():
        by_cat[c].append(p)
    cat_med = {c: st.median(v) for c, v in by_cat.items() if len(v) >= 3}
    g_med = st.median([p for p, _ in known.values()]) if known else 18.0
    est, src_n = {}, collections.Counter()
    for (d, a), ss in slots_all.items():
        lm, c = est_logm(ss, cal)
        u = units_month(cv, lm)
        p, src = price_lookup(card, a, d), "c"
        if not p:
            p, src = tp.get(a), "t"
        if not p:
            p, src = cat_med.get(c), "m"
        if not p:
            p, src = g_med, "g"
        est.setdefault(d, {})[a] = (u, p, u * p / 30.0, src)
        if d == dates[-1]:
            src_n[src] += 1
    meta = {"a": cv["a"], "b1": cv["b1"], "b2": cv["b2"], "nu": cv["n"], "sd": cv["sd"], "dflt": cv["dflt"],
            "beta": round(cal["beta"], 3), "direct": cal["direct"], "linked": cal["linked"], "npairs": cal["npairs"],
            "ncat": len(cats), "val": validate(cal, cv, trk, slots_all), "px": dict(src_n), "gmed": round(g_med, 2)}
    return est, meta
