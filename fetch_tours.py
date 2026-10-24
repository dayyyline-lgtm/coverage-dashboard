"""K-pop 투어 공연일·매출 -> index.html 의  const TOURS = {...};   (2026-10-24 신설 · 종목별 손익 모델 ISM)

하이브·JYP·YG 의 분기 공연 매출은 '그 분기에 무슨 투어가 몇 회 돌았나'가 정한다(하이브 2Q26 공연 647.7 중 BTS 아리랑 24회 ≈ 415).
전년 동기 × 성장률로는 못 맞춘다. 두 소스를 공연일 단위로 합친다:
  ① 위키백과 투어 문서의 'Tour dates' 표 — 앞으로의 일정까지(BTS 아리랑 88회 · 1Q27 까지) + Billboard Boxscore 매출(보고된 회차)
  ② TouringData(WordPress JSON) — 보고된 회차의 매출이 위키보다 많다(세븐틴·엔하이픈·TXT·르세라핌·스키즈·트와이스)
같은 날짜는 TouringData 매출이 이긴다. 화면(ism.js ISM_PX.kpoptour)이 분기마다 [보고 매출 + 미보고 회차 × 그 투어 회당 평균] × 분기 환율.
⚠ 블랙핑크(YG)는 매출이 전부 미보고 — 회수만 쓴다(kpopshows). ⚠ 위키 API 는 연속 요청에 429 — 3초 간격.
⚠ 표 양식이 문서마다 다르다(연도가 머리글에만 · rowspan 매출 · 레그별 표 여러 개). 회차 수가 크게 줄면 기존 값을 둔다.

python fetch_tours.py
"""
import datetime, html as _html, json, re, sys, time, urllib.parse, urllib.request

from collector_health import ua, note_health

KST = datetime.timezone(datetime.timedelta(hours=9))
HTML = "public/index.html"
WUA = {"User-Agent": "coverage-dashboard/1.0 (equity research; github.com/dayyyline-lgtm) Python-urllib"}
MON = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                   "September", "October", "November", "December"], 1)}
# id · 표시명 · 종목 · 아티스트 · 위키 문서 · TouringData 글 제목(검색해서 id 를 찾는다)
TOURS = [
    ("arirang", "BTS 아리랑 월드투어", "하이브", "BTS", "Arirang World Tour", None),
    ("svt_new", "세븐틴 NEW_", "하이브", "SEVENTEEN", "New World Tour", "NEW_ Tour (2025)"),
    ("svt_rh", "세븐틴 Right Here", "하이브", "SEVENTEEN", "Right Here World Tour", "Right Here Tour (2024)"),
    ("enh_wtl", "엔하이픈 Walk the Line", "하이브", "ENHYPEN", None, "Walk the Line Tour (2024)"),
    ("txt_act", "TXT Act: Tomorrow", "하이브", "TXT", None, "Act: Tomorrow Tour (2025)"),
    ("lsf_ech", "르세라핌 Easy Crazy Hot", "하이브", "LE SSERAFIM", "Easy Crazy Hot Tour", "Easy Crazy Hot Tour (2025)"),
    ("skz_dom", "스트레이키즈 Dominate", "JYP Ent.", "Stray Kids", "Dominate World Tour", "Dominate Tour (2024)"),
    ("twc_tif", "트와이스 This Is For", "JYP Ent.", "TWICE", "This Is For World Tour", "This Is For Tour (2025)"),
    ("bp_dl", "블랙핑크 Deadline", "와이지엔터", "BLACKPINK", "Deadline World Tour", None),
    # 2026-10-25 — 앞으로의 일정이 잡힌 투어(매출 미보고 → 화면이 같은 아티스트 지난 투어 회당 매출을 빌린다)
    ("skz_runit", "스트레이키즈 Run It", "JYP Ent.", "Stray Kids", "Run It World Tour", None),
    ("aespa_hl", "에스파 SYNK: Hyper Line", "에스엠", "aespa", "Synk: Hyper Line", None),
    ("aespa_pl", "에스파 SYNK: Parallel Line", "에스엠", "aespa", "Synk: Parallel Line", None),
    ("aespa_cx", "에스파 SYNK: Complaexity", "에스엠", "aespa", "Synk: Complaexity", None),
]


def get(u, h, t=30):
    return urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=t).read()


# ── 위키백과 ────────────────────────────────────────────────────────────
def wikitext(title):
    u = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "parse", "page": title, "prop": "wikitext", "format": "json", "redirects": 1})
    for i in range(3):
        try:
            d = json.loads(get(u, WUA))
            return d["parse"]["wikitext"]["*"] if "parse" in d else ""
        except urllib.error.HTTPError as e:
            if e.code != 429 or i == 2:
                raise
            time.sleep(10 * (i + 1))
    return ""


def _clean(c):
    c = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>|<!--.*?-->", "", c, flags=re.S)
    c = re.sub(r"\{\{[Ee]fn\|.*?\}\}", "", c)
    c = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", c)
    c = re.sub(r"\{\{(?:sort|nts|nowrap)\|[^|}]*\|?([^}]*)\}\}", r"\1", c)
    return c.strip()


def wiki_shows(w):
    """'Tour dates' 절의 표들 → {날짜: [usd|None, 관객|None]} · rowspan 매출·관객은 그 날짜들에 똑같이 나눈다."""
    i = max(w.find("==Tour dates"), w.find("== Tour dates"))
    if i < 0:
        return {}
    k = w.find("\n==", i + 6)
    while k > 0 and w[k:k + 4] == "\n===":                 # 하위 절(레그)은 같은 절로 본다
        k = w.find("\n==", k + 4)
    body = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>|<!--.*?-->", "", w[i:k if k > 0 else len(w)], flags=re.S)
    out = {}
    for tab in re.findall(r"\{\|(.*?)\n\|\}", body, re.S):
        heads = [_clean(h.split("|")[-1]) for h in re.findall(r"\n![^\n]*", tab.split("\n|-")[0] + "\n" if "\n|-" in tab else tab)]
        if not heads:
            heads = [_clean(h.split("|")[-1]) for h in re.findall(r"\n![^\n]*", tab)[:9]]
        hl = [h.lower() for h in heads]
        ia = next((n for n, h in enumerate(hl) if "attendance" in h), None)
        ir = next((n for n, h in enumerate(hl) if "revenue" in h or "gross" in h), None)
        yr = next((re.search(r"(20\d\d)", h).group(1) for h in heads if re.search(r"date.*20\d\d", h, re.I)), None)
        ncol, pend = len(heads), {}
        for r in tab.split("\n|-"):
            m = re.search(r"\n!\s*(?:scope=\"row\"[^|]*\|)?\s*(?:\{\{[^}]*\|)?([A-Z][a-z]+ \d{1,2})(?:, (\d{4}))?", r)
            if not m:
                continue
            mo, dd = m.group(1).split()
            y = m.group(2) or yr
            if mo not in MON or not y:
                continue
            d = datetime.date(int(y), MON[mo], int(dd)).isoformat()
            cells, col, vals = iter(re.findall(r"\n\|\s*([^\n]*)", r)), 1, {}
            while col < ncol:
                if col in pend and pend[col][0] > 0:
                    vals[col] = pend[col][1]; pend[col][0] -= 1; col += 1; continue
                c = next(cells, None)
                if c is None:
                    break
                mm = re.match(r'(?:[^|]*?)rowspan="?(\d+)"?[^|]*\|\s*(.*)', c)
                if mm:
                    n = int(mm.group(1)); pend[col] = [n - 1, (mm.group(2), n)]; vals[col] = (mm.group(2), n)
                else:
                    vals[col] = (c, 1)
                col += 1

            def g(kk):
                if kk is None or kk not in vals:
                    return None, 1
                return _clean(vals[kk][0]), vals[kk][1]
            av, an = g(ia)
            rv, rn = g(ir)
            att = usd = None
            if av:
                mm = re.search(r"([\d,]{3,})\s*/", av) or re.search(r"([\d,]{4,})", av)
                if mm:
                    att = round(int(mm.group(1).replace(",", "")) / an)
            if rv:
                mm = re.search(r"\$\s*([\d,\.]+)\s*(million)?", rv, re.I)
                if mm:
                    v = float(mm.group(1).replace(",", ""))
                    usd = round((v * 1e6 if mm.group(2) else v) / rn)
            out[d] = [usd, att]
    return out


# ── TouringData ────────────────────────────────────────────────────────
def td_find(title):
    d = json.loads(get("https://touringdata.org/wp-json/wp/v2/search?" + urllib.parse.urlencode({"search": title, "per_page": 10}), ua()))
    norm = lambda s: re.sub(r"\W+", "", _html.unescape(s).lower())
    for x in d:
        if norm(x["title"]) == norm(title):
            return x["id"]
    return None


def td_shows(pid):
    d = json.loads(get(f"https://touringdata.org/wp-json/wp/v2/posts/{pid}?_fields=id,modified,content", ua()))
    out = {}
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", d["content"]["rendered"], re.S):
        cells = [_html.unescape(re.sub(r"<[^>]+>", " ", x)).strip() for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
        if len(cells) < 2:
            continue
        m = re.match(r"\s*([A-Z][a-z]+)\s+(\d{1,2})(?:\s*-\s*(?:([A-Z][a-z]+)\s+)?(\d{1,2}))?,\s*(\d{4})", cells[0])
        if not m or m.group(1) not in MON:
            continue
        mo, d1, mo2, d2, y = m.groups()
        sh = re.search(r"(\d+)\s*shows?", " ".join(cells[1:]))
        n = int(sh.group(1)) if sh else 1
        rev = re.search(r"\$\s*([\d,]+)", cells[1])
        usd = float(rev.group(1).replace(",", "")) / n if rev else None
        start = datetime.date(int(y), MON[mo], int(d1))
        for j in range(n):                                   # 여러 회차 묶음은 연속한 날로 편다(분기 배정용)
            out[(start + datetime.timedelta(days=j)).isoformat()] = [round(usd) if usd else None, None]
    return out, d.get("modified", "")


def main():
    html = open(HTML, encoding="utf-8").read()
    mm = re.search(r"^const TOURS = (\{.*?\});$", html, re.M | re.S)
    old = json.loads(mm.group(1)) if mm else {"t": {}}
    T, bad = {}, []
    for tid, nm, stock, artist, wiki, td in TOURS:
        shows, src = {}, []
        if wiki:
            try:
                w = wiki_shows(wikitext(wiki))
                if w:
                    shows.update(w); src.append("wiki")
            except Exception as e:
                bad.append(f"{nm} 위키 {str(e)[:30]}")
            time.sleep(3)
        if td:
            try:
                pid = td_find(td)
                if pid:
                    t, _ = td_shows(pid)
                    for d, v in t.items():                    # 매출은 TouringData 가 이긴다(관객은 위키 것을 둔다)
                        u0 = shows.get(d, [None, None])
                        shows[d] = [v[0] if v[0] is not None else u0[0], u0[1]]
                    src.append("td")
                else:
                    bad.append(f"{nm} TouringData 글 없음")
            except Exception as e:
                bad.append(f"{nm} TD {str(e)[:30]}")
            time.sleep(1)
        prev = (old.get("t") or {}).get(tid)
        if prev and len(shows) < 0.7 * len(prev.get("s") or []):      # 표가 깨진 날 — 기존 값을 둔다
            bad.append(f"{nm} 회차 {len(prev['s'])}→{len(shows)}(기존 유지)")
            T[tid] = prev; continue
        if not shows:
            if prev:
                T[tid] = prev
            continue
        s = [[d] + shows[d] for d in sorted(shows)]
        T[tid] = {"nm": nm, "st": stock, "ar": artist, "src": src, "s": s}
        rep = [x for x in s if x[1]]
        print(f"[투어] {nm:22} {len(s)}회({s[0][0]}~{s[-1][0]}) · 매출 보고 {len(rep)}회 ${sum(x[1] for x in rep) / 1e6:,.1f}M · {'+'.join(src)}")
    note_health("K-pop 투어", "; ".join(bad[:3]) if len(bad) > 2 else None)
    if mm and old.get("t") == T:
        print("[투어] 변동 없음"); return
    out = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "t": T,
           "note": "공연일별 [날짜, 매출 USD(보고된 회차), 관객] — 위키백과 Tour dates 표 + TouringData(Billboard Boxscore). 매출 없는 회차 = 미보고 또는 앞으로의 일정"}
    block = "const TOURS = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";"
    if mm:
        html = html[:mm.start()] + block + html[mm.end():]
    else:
        a = re.search(r"^const TREND = ", html, re.M)
        html = html[:a.start()] + block + "\n" + html[a.start():]
    open(HTML, "w", encoding="utf-8").write(html)
    print(f"[투어] TOURS 블록 갱신 {len(block) // 1024}KB")


if __name__ == "__main__":
    if "--dry" in sys.argv:
        for tid, nm, stock, artist, wiki, td in TOURS:
            if wiki:
                w = wiki_shows(wikitext(wiki)); print(nm, "wiki", len(w), sum(1 for v in w.values() if v[0])); time.sleep(3)
        sys.exit()
    main()
