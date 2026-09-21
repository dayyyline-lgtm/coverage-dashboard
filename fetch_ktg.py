# -*- coding: utf-8 -*-
"""
KT&G 유라시아(카자흐스탄 허브) 실측 — 2026-09-21 신설 → `KTG`.

왜
  키움(2026-09-21) 'KT&G 해외담배 질적 성장 (feat. 카자흐스탄)' — ESSE 초슬림이 알마티 브랜드 1위,
  카자흐 점유율 5.1%('22)→9.6%('25) 3위, 유통 커버리지 50→80%, 현지 생산분 40% 를 키르기스·러시아·
  우즈벡·타지크·아르메니아로 수출, 몽골(EAEU 임시협정)·HnB 직접사업(올해). 이 주장들을 **회사 자료가
  아닌 곳**에서 매일 재는 것이 목적이다. 네 소스 전부 키 없이 열린다(관세청만 data.go.kr 키).

① 관세청 — 한국발 담배 수출, 국가별 월별 (nitemtrade · DATA_GO_KR_KEY)
   240220 궐련 · 2403 기타담배(240399 = 가열담배 스틱류가 여기 잡힌다 · 240391 재구성담배).
   2026-09-21 실측(천$): 카자흐 240220 2024 월 300~600 → 2025 50~130 → 2026 0 (26.04 98 뿐).
   러시아·우즈벡·타지크도 2026 에 0 으로 수렴 → **한국 수출이 카자흐 현지생산으로 대체된 것이 그대로 보인다.**
   몽골만 한국발이 살아 있다(2026.1~8 $16.5M · 2024 $46.9M · 2025 $14.7M) — KT&G 가 몽골 점유 50%+ 라
   이 계열이 곧 KT&G 몽골 프록시다. EAEU-몽골 협정(26.07)으로 카자흐 발로 옮겨 가면 여기가 준다.
   ⚠ API 는 조회기간 1년 이내만 받는다 → 연도별 창으로 나눠 부른다(fetch_trade 와 같은 함정).
   ⚠ HS 2401(잎담배)·필터·권지는 안 본다 — KT&G 카자흐 공장 원료가 한국발인지 확인 안 됨.

② 알마티 온라인 리테일 — newelitalco.kz (Elitalco) 담배 카탈로그 · 키 없이 · doc 헤더
   상품마다 **누적 구매횟수("N раз")** 가 찍힌다 — 와일드베리즈 리뷰수와 같은 성질의 판매 대리지표.
   2026-09-21 실측: 75 SKU · Esse 7 SKU 누적 6,133 (브랜드 1위) · Chapman 20 SKU 5,429 · Parliament 1,685 ·
   Marlboro 901 · Winston 533. ESSE EXCHANGE W 단일 SKU 3,664 = 전체 1위. 보고서 '알마티 1위' 가 독립 데이터로 맞다.
   가격: ESSE 1,340~1,365₸ · Winston 1,370 · Marlboro 1,380 · Parliament 1,510 · Chapman 1,540 (법정 최저가 1,060).
   ⚠ 누적치라 **일별 증분(오늘−어제)** 이 신호다. 첫날은 증분이 없다. 가격 '1' 은 미표시(품절·문의)다.
   ⚠ 한 리테일러 한 도시다. 전국·오프라인이 아니다 — 화면 문구에서 이 단서를 빼면 안 된다.
   ⚠ 카자흐는 담배 온라인 판매가 법으로 금지돼 있어 이런 사이트는 언제든 닫힐 수 있다. 실패는 기록만.

③ Kaspi.kz — 카자흐 최대 마켓플레이스, HnB **기기** (스틱·궐련은 안 판다 — 온라인 담배 금지)
   /yml/product-view/pl/results?text=…&c=750000000(알마티) JSON · 카드에 reviewsQuantity·unitPrice.
   2026-09-21 실측: IQOS ILUMA 기기 17 SKU · 리뷰 합 764 (i ONE 검정 193). **lil SOLID 는 0 SKU** —
   KT&G 의 HnB 기기가 카자흐 최대 채널에 없다는 뜻. lil 카드가 생기는 날 = 직접사업 개시 신호.
   리뷰 증분 = 기기 판매 대리지표(와일드베리즈와 같은 논리).

④ hh.kz(HeadHunter 카자흐) — KT&G 두 법인의 채용 공고 수
   판매법인 9856755 'KT&G GLOBAL KAZAKHSTAN' · 생산법인 10258777 'KT&G Kazakhstan'(село Кокозек = 공장).
   2026-09-21 실측: 판매 8건 — 사바트 지원(Специалист по поддержке сбыта) **코스타나이·우랄스크**(북부·서부
   신규 권역 = 커버리지 80% 계획의 실물), HR·AR&Retail·Back Office·Customer Care·IT·HSE / 생산 2건.
   ⚠ api.hh.ru 는 이 IP 를 403 으로 막는다(헤더 무관). HTML 검색 페이지는 열린다 → 그쪽을 파싱한다.

없는 것 — 확인해 봤다
  · 구글 트렌드 토픽 ID(/m/0nbct0r ESSE) 는 카자흐에서 임계 미만(5/54주). 문자열 'esse' 는 KZ·RU 모두
    연관검색어가 담배 변종(exchange·change·mango·himalaya…)이라 쓸 수 있다. **우즈벡 'esse' 는 에세이다**
    (9월 개학에 4→36 급등). 트렌드 그룹은 fetch_trends.py 의 'ESSE 국가별' 참고.
  · 카자흐 통계청(Taldau) 3,699개 지표 중 '사이렛 생산' 단독 지표는 없다(산업생산 지표의 세부 사전 안).
    월별 생산·수출은 energyprom.kz / DATA HUB(1cb) 기사로 본다 — 2025 24.4십억개비(+36%), 26.1~5 수출 6.7십억(3.7배),
    1Q26 수출 $42.5M(+77% · 키르기스 57%). 세 공장(PMI·JTI·KT&G) 이 모두 알마티주 일리구라 지역으로도 못 가른다.
  · Wolt/Glovo IQOS 매장은 JS 렌더라 가격이 안 잡힌다(공개 API 없음).

  python fetch_ktg.py             # 수집·기록
  python fetch_ktg.py --dry-run   # 출력만
"""
import copy, datetime, json, os, re, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
import html as htmlmod

from collector_health import ua, nap, note_health

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
DAYS = 400

try:
    from secrets_local import DATA_GO_KR_KEY
except ImportError:
    DATA_GO_KR_KEY = ""
DATA_GO_KR_KEY = os.environ.get("DATA_GO_KR_KEY", DATA_GO_KR_KEY)

# ── ① 관세청 ──────────────────────────────────────────────
API = "https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"
CTY = [("KZ", "카자흐스탄"), ("RU", "러시아"), ("UZ", "우즈베키스탄"), ("KG", "키르기스스탄"),
       ("TJ", "타지키스탄"), ("AM", "아르메니아"), ("MN", "몽골")]
HS_ITEMS = [
    {"key": "cig", "hs": "2402", "match": lambda h: h.startswith("240220"), "label": "궐련(240220)"},
    {"key": "oth", "hs": "2403", "match": lambda h: h.startswith("2403"),   "label": "기타·가열담배(2403)"},
]


def _customs_call(hs, start, end):
    p = {"serviceKey": DATA_GO_KR_KEY, "strtYymm": start, "endYymm": end, "hsSgn": hs}
    url = API + "?" + urllib.parse.urlencode(p, safe="")
    raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=90).read()
    root = ET.fromstring(raw)
    msg = root.findtext(".//resultMsg") or ""
    if msg and "정상" not in msg:
        raise RuntimeError(msg[:70])
    rows = []
    for it in root.iter("item"):
        g = lambda t: (it.findtext(t) or "").strip()
        ym, h, cd = g("year"), g("hsCd"), g("statCd")
        if not re.fullmatch(r"\d{4}\.\d{2}", ym) or not h.isdigit() or not re.fullmatch(r"[A-Z]{2}", cd):
            continue
        try:
            exp = float(g("expDlr").replace(",", ""))
        except ValueError:
            continue
        rows.append((ym.replace(".", ""), h, cd, exp))
    return rows


def fetch_customs(months=32):
    if not DATA_GO_KR_KEY:
        raise RuntimeError("DATA_GO_KR_KEY 없음")
    today = datetime.datetime.now(KST).date().replace(day=1)
    ms = []
    for i in range(months, 0, -1):
        y, m = today.year, today.month - i
        while m <= 0:
            m += 12; y -= 1
        ms.append(f"{y}{m:02d}")
    years = sorted({m[:4] for m in ms})
    raw = {}
    for item in HS_ITEMS:
        for y in years:
            s, e = max(f"{y}01", ms[0]), min(f"{y}12", ms[-1])
            if s > e:
                continue
            for ym, h, cd, exp in _customs_call(item["hs"], s, e):
                raw[(ym, h, cd)] = raw.get((ym, h, cd), 0.0) + exp
            nap(0.4)
    series = {}
    for item in HS_ITEMS:
        per = {}
        for cd, nm in CTY + [("ALL", "전체")]:
            ser = []
            for m in ms:
                tot, hit = 0.0, False
                for (ym, h, c), v in raw.items():
                    if ym != m or not item["match"](h):
                        continue
                    if cd != "ALL" and c != cd:
                        continue
                    tot += v; hit = True
                ser.append(round(tot / 1000, 1) if hit else None)   # 천달러
            per[cd] = ser
        series[item["key"]] = {"label": item["label"], "by": per}
    return {"months": ms, "cty": dict(CTY), "unit": "천달러", "series": series}


# ── ② Elitalco (알마티) ───────────────────────────────────
EL_URL = "https://newelitalco.kz/ru/catalog/cigarettes/"
KTG_BRANDS = {"esse", "bohem", "time", "raison", "carnival", "pine", "this", "tonino lamborghini"}


def _get(url, doc=True, extra=None, timeout=40):
    h = ua(doc=doc)
    if not doc:
        h["Accept"] = "application/json, text/plain, */*"
    if extra:
        h.update(extra)
    r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout)
    return r.read().decode("utf-8", "replace")


def _el_parse(t):
    rows = []
    for box in re.finditer(r'<div class="product-item-box" data-prodid="(\d+)"(.*?)(?=<div class="product-item-box"|$)', t, re.S):
        pid, body = box.group(1), box.group(2)
        ld = re.search(r'<script type="application/ld\+json">(.*?)</script>', body, re.S)
        try:
            j = json.loads(ld.group(1)) if ld else {}
        except Exception:
            j = {}
        buys = re.search(r"(\d+)\s*раз", body)
        try:
            price = int(float((j.get("offers") or {}).get("price") or 0))
        except (TypeError, ValueError):
            price = 0
        rows.append({"id": pid, "name": htmlmod.unescape((j.get("name") or "").strip()),
                     "brand": htmlmod.unescape(((j.get("brand") or {}).get("name") or "").strip()),
                     "price": price if price > 100 else None,          # '1' = 미표시
                     "buys": int(buys.group(1)) if buys else None,
                     "avail": ((j.get("offers") or {}).get("availability") or "").split("/")[-1]})
    return rows


def fetch_elitalco():
    rows, seen = [], set()
    for p in range(1, 8):
        t = _get(EL_URL + (f"?page={p}" if p > 1 else ""))
        got = _el_parse(t)
        new = [r for r in got if r["id"] not in seen]
        if not new:
            break
        rows += new; seen.update(r["id"] for r in new)
        nap(0.5)
    if len(rows) < 20:
        raise RuntimeError(f"카탈로그가 너무 작다 {len(rows)}")
    # 브랜드 표기가 흔들린다(Marboro/Marlboro · Captain black) — 소문자·공백 제거로 합친다
    def bkey(b):
        b = (b or "?").strip().lower()
        b = {"marboro": "marlboro", "captain black": "captain black", "ld club": "ld", "l&m": "l&m"}.get(b, b)
        return b
    brands = {}
    for r in rows:
        k = bkey(r["brand"])
        d = brands.setdefault(k, {"brand": k, "sku": 0, "buys": 0, "prices": []})
        d["sku"] += 1; d["buys"] += r["buys"] or 0
        if r["price"]:
            d["prices"].append(r["price"])
    out_b = []
    for k, d in sorted(brands.items(), key=lambda x: -x[1]["buys"]):
        pr = sorted(d["prices"])
        out_b.append({"brand": k, "sku": d["sku"], "buys": d["buys"],
                      "pmin": pr[0] if pr else None, "pmed": pr[len(pr) // 2] if pr else None,
                      "ktg": 1 if k in KTG_BRANDS else 0})
    esse = [{"name": r["name"], "price": r["price"], "buys": r["buys"], "avail": r["avail"]}
            for r in rows if bkey(r["brand"]) in KTG_BRANDS]
    top = [{"name": r["name"], "brand": bkey(r["brand"]), "price": r["price"], "buys": r["buys"]}
           for r in sorted(rows, key=lambda r: -(r["buys"] or 0))[:15]]
    return {"n": len(rows), "brands": out_b, "esse": esse, "top": top}


# ── ③ Kaspi ──────────────────────────────────────────────
KASPI = "https://kaspi.kz/yml/product-view/pl/results"
ACC = re.compile(r"стичниц|панель|чехол|крышк|кейс|кабел|держател|зарядн|адаптер|наклей|стик", re.I)


def _kaspi(q, pages=3):
    cards = []
    for page in range(pages):
        u = KASPI + "?" + urllib.parse.urlencode({"text": q, "page": page, "sort": "relevance", "qs": "", "ui": "d", "i": "-1", "c": "750000000"})
        t = _get(u, doc=False, extra={"Referer": "https://kaspi.kz/shop/search/?text=" + urllib.parse.quote(q), "X-KS-City": "750000000"})
        d = json.loads(t)
        got = d.get("data") or []
        if not got:
            break
        cards += got
        nap(0.5)
    return cards


def fetch_kaspi():
    def devices(cards, pat):
        out = {}
        for c in cards:
            ti = (c.get("title") or "")
            if not re.search(pat, ti, re.I) or ACC.search(ti):
                continue
            out[c.get("id") or ti] = {"t": ti[:60], "p": c.get("unitPrice"), "r": c.get("reviewsQuantity") or 0}
        return list(out.values())
    iq = devices(_kaspi("iqos"), r"^IQOS")
    lil = devices(_kaspi("lil solid"), r"\blil\b")
    glo = devices(_kaspi("glo hyper"), r"\bglo\b")
    if not iq:
        raise RuntimeError("IQOS 기기 카드 0 — 응답 형식이 바뀌었나")
    summ = lambda L: {"sku": len(L), "reviews": sum(x["r"] for x in L),
                      "pmin": min((x["p"] for x in L if x["p"]), default=None)}
    return {"iqos": summ(iq), "lil": summ(lil), "glo": summ(glo),
            "iqosTop": sorted(iq, key=lambda x: -x["r"])[:6], "lilList": lil[:6]}


# ── ④ hh.kz ──────────────────────────────────────────────
HH_ENT = [("sales", "9856755", "KT&G GLOBAL KAZAKHSTAN(판매)"), ("prod", "10258777", "KT&G Kazakhstan(생산·Кокозек 공장)")]


def fetch_hh():
    out = {}
    for key, eid, label in HH_ENT:
        t = _get(f"https://hh.kz/search/vacancy?employer_id={eid}&items_on_page=50")
        n = re.search(r"Найдено\s+(\d+)", t)
        titles = [htmlmod.unescape(x) for x in re.findall(r'data-qa="serp-item__title[^"]*"[^>]*>(?:<[^>]+>)*([^<]{3,120})<', t)]
        cities = [htmlmod.unescape(x) for x in re.findall(r'data-qa="vacancy-serp__vacancy-address[^"]*"[^>]*>(?:<[^>]+>)*([^<]{2,60})<', t)]
        if n is None and not titles and "hh.kz" not in t[:3000]:
            raise RuntimeError(f"{eid} 페이지 형식 불명")
        cnt = int(n.group(1)) if n else len(titles)
        reg = {}
        for c in cities:
            c0 = c.split(",")[0].strip()
            reg[c0] = reg.get(c0, 0) + 1
        out[key] = {"id": eid, "label": label, "n": cnt,
                    "titles": [f"{ti} · {cities[i] if i < len(cities) else ''}".strip(" ·") for i, ti in enumerate(titles[:20])],
                    "reg": reg}
        nap(0.6)
    return out


# ── 통합 ─────────────────────────────────────────────────
def _const(html_, name):
    m = re.search(r"const %s\s*=\s*(\{.*?\});" % re.escape(name), html_, re.S)
    return json.loads(m.group(1)) if m else None


def _put(html_, name, obj):
    block = "const %s = %s;" % (name, json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
    pat = re.compile(r"const %s\s*=\s*\{.*?\};" % re.escape(name), re.S)
    if pat.search(html_):
        return pat.sub(lambda m: block, html_, count=1)
    liv = re.search(r"const LIVE\s*=\s*\{.*?\};", html_, re.S)
    if not liv:
        raise RuntimeError("KTG 삽입 기준(const LIVE)을 못 찾음")
    return html_[:liv.end()] + "\n" + block + html_[liv.end():]


def main():
    html_ = open(HTML, encoding="utf-8").read()
    now = datetime.datetime.now(KST)
    today = now.date().isoformat()
    prev = _const(html_, "KTG") or {}
    old = copy.deepcopy(prev)                       # ⚠ deepcopy — 얕은 참조 함정
    out = {"asOf": now.strftime("%Y-%m-%d %H:%M KST"), "stock": "KT&G"}
    fails = []

    # ① 관세청
    try:
        out["customs"] = fetch_customs()
        s = out["customs"]["series"]["cig"]["by"]
        last = [(cd, [v for v in ser if v is not None][-1:]) for cd, ser in s.items()]
        print("  [관세청] 궐련 최근(천$): " + " · ".join(f"{cd} {v[0] if v else '-'}" for cd, v in last))
    except Exception as e:
        fails.append(f"관세청: {str(e)[:50]}")
        if old.get("customs"): out["customs"] = old["customs"]

    # ② Elitalco
    try:
        el = fetch_elitalco()
        hist = [h for h in (old.get("retail") or {}).get("hist") or [] if h.get("d") != today]
        hist.append({"d": today, "b": {b["brand"]: [b["buys"], b["sku"], b["pmed"]] for b in el["brands"][:12]},
                     "tot": sum(b["buys"] for b in el["brands"])})
        out["retail"] = {"src": "Elitalco(newelitalco.kz) 알마티 온라인 리테일 · 담배 카탈로그 누적 구매횟수",
                         "city": "알마티", "n": el["n"], "brands": el["brands"], "esse": el["esse"], "top": el["top"],
                         "hist": hist[-DAYS:]}
        b0 = el["brands"][0]
        print(f"  [리테일] {el['n']} SKU · 1위 {b0['brand']} 누적 {b0['buys']:,} ({b0['sku']} SKU · 중간가 {b0['pmed']}₸)")
    except Exception as e:
        fails.append(f"Elitalco: {str(e)[:50]}")
        if old.get("retail"): out["retail"] = old["retail"]

    # ③ Kaspi
    try:
        ks = fetch_kaspi()
        hist = [h for h in (old.get("hnb") or {}).get("hist") or [] if h.get("d") != today]
        hist.append({"d": today, "iq": [ks["iqos"]["sku"], ks["iqos"]["reviews"], ks["iqos"]["pmin"]],
                     "lil": [ks["lil"]["sku"], ks["lil"]["reviews"]], "glo": [ks["glo"]["sku"], ks["glo"]["reviews"]]})
        out["hnb"] = {"src": "Kaspi.kz(알마티) 검색 — HnB 기기 SKU·누적 리뷰 (스틱·궐련은 온라인 판매 금지라 없음)",
                      "iqos": ks["iqos"], "lil": ks["lil"], "glo": ks["glo"], "iqosTop": ks["iqosTop"], "lilList": ks["lilList"],
                      "hist": hist[-DAYS:]}
        print(f"  [Kaspi] IQOS 기기 {ks['iqos']['sku']} SKU 리뷰 {ks['iqos']['reviews']:,} · lil {ks['lil']['sku']} SKU · glo {ks['glo']['sku']} SKU")
    except Exception as e:
        fails.append(f"Kaspi: {str(e)[:50]}")
        if old.get("hnb"): out["hnb"] = old["hnb"]

    # ④ hh.kz
    try:
        hh = fetch_hh()
        hist = [h for h in (old.get("jobs") or {}).get("hist") or [] if h.get("d") != today]
        hist.append({"d": today, "sales": hh["sales"]["n"], "prod": hh["prod"]["n"],
                     "reg": hh["sales"]["reg"]})
        out["jobs"] = {"src": "hh.kz(HeadHunter 카자흐) — KT&G 판매법인·생산법인 공개 채용 수",
                       "ent": hh, "hist": hist[-DAYS:]}
        print(f"  [hh.kz] 판매법인 {hh['sales']['n']}건 {hh['sales']['reg']} · 생산법인 {hh['prod']['n']}건")
    except Exception as e:
        fails.append(f"hh.kz: {str(e)[:50]}")
        if old.get("jobs"): out["jobs"] = old["jobs"]

    if len(fails) >= 3:
        note_health("KT&G 유라시아", f"{len(fails)}/4 실패: {' | '.join(fails)[:120]}")
        print("[KTG] 소스 절반 넘게 실패 — 기존 보존"); sys.exit(1)
    note_health("KT&G 유라시아", None)
    if fails:
        print("  일부 실패:", " | ".join(fails))

    if "--dry-run" in sys.argv:
        print(json.dumps(out, ensure_ascii=False)[:2000]); return
    strip = lambda o: json.dumps({k: v for k, v in (o or {}).items() if k != "asOf"}, ensure_ascii=False, sort_keys=True)
    if prev and strip(prev) == strip(out):
        print("[KTG] 변동 없음 — 건너뜀"); return
    open(HTML, "w", encoding="utf-8").write(_put(html_, "KTG", out))
    print(f"[OK] KTG 갱신 · 소스 {4 - len(fails)}/4")


if __name__ == "__main__":
    main()
