# -*- coding: utf-8 -*-
"""
스토어 판매·예약 순위 수집 — 게임 커버 종목의 '지금 팔리고 있나'(콘솔·PC 스토어).

동접(플레이)·리뷰(구매 후행)와 달리 스토어 순위는 '구매 시점'에 가장 가깝다. 특히 예약 순위는
출시 전 유일한 판매 신호다. 절대 판매량은 어디도 공개하지 않으므로 **순위만** 매일 1점씩 쌓는다.
(2026-09-04 신설. 붉은사막 Enhanced 확장팩 '미지의 여정'(10/15) 예약이 첫 대상.)

소스 — 전부 키 없이 urllib 로 열린다(2026-09-04 실측):
  PS 스토어  web.np.playstation.com/api/graphql/v1/op  categoryGridRetrieve (persisted query 해시)
             · 예약 카테고리  3bf499d7…  products, 기본 정렬 sales30(=30일 최다판매) → 순서가 곧 예약 판매순위
             · PS5 전체     d0446d4b…  concepts 6,967개, sortBy sales30 / downloads30 으로 정렬 → 상위 300 안 순위
             · 지역은 x-psn-store-locale-override 헤더(en-US · ko-KR · ja-JP · en-GB)
             ⚠ 해시가 사이트 배포로 바뀔 수 있다 — 응답이 비면 note_health 로 알린다(watchdog).
  Steam      store.steampowered.com/search/results/?filter=topsellers&cc=  국가별 '최고 판매' 100줄(DLC·번들 포함)
             filter=popularwishlist  위시리스트 상위 100(미출시작 = 예약 관심)
             공식 IStoreTopSellersService.GetWeeklyTopSellers 는 access_token 이 필요해(응답 빈 객체) 안 쓴다.
  MS 스토어  microsoft.com/{loc}/store/top-paid/games/xbox · /pc, coming-soon/games/xbox  — SSR JSON 카드 50개
  안 되는 것  에픽(컬렉션이 정적 큐레이션) · 아마존(캡차) · 닌텐도(대상 게임 없음)

저장(STORERANK.items[]): {stock,title,src,region,n,hist:[{d,r}]} — r=null 은 '목록 밖'. n 은 목록 크기.
같은 날 재실행은 그날 값을 덮는다. 목록을 못 받은 날은 점을 안 찍는다(0 이나 null 로 채우지 않는다).

  python fetch_storerank.py            # 수집·기록
  python fetch_storerank.py --dry-run  # 출력만
"""
import re, json, sys, html, datetime, urllib.request, urllib.parse
from collector_health import ua, nap, note_health

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
DAYS = 400
PS_HASH = "88c0b9a1273c6d320c51cd73e390924e21ae28bf09f01cde8b84b1034b16cd03"
PS_PRE, PS_ALL = "3bf499d7-7acf-4931-97dd-2667494ee2c9", "d0446d4b-dc9a-4f1e-86ec-651f099c9b29"
REGION = {"kr": "한국", "us": "미국", "jp": "일본", "gb": "영국", "de": "독일", "global": "글로벌"}

# (종목, 표시명, Steam appid, 스토어 이름 키워드)  — 키워드는 PS·MS 카드 제목에 대고 부분일치.
# ⚠ 'PUBG' 만 쓰면 'PUBG: Black Budget' 도 잡힌다. 'Crimson' 은 'Crimson Moon' 과 겹친다. 좁게 쓸 것.
TITLES = [
    ("펄어비스", "붉은사막",              3321460, ["Crimson Desert", "붉은사막", "紅の砂漠"]),
    ("펄어비스", "붉은사막 DLC(미지의 여정)",   None,    ["Charting the Unknown", "미지의 여정", "未知なる旅路"]),
    ("펄어비스", "검은사막",              582660,  ["Black Desert", "검은사막", "黒い砂漠"]),
    ("크래프톤", "배틀그라운드",          578080,  ["PUBG: BATTLEGROUNDS", "배틀그라운드", "PUBG: BATTLEGROUNDS"]),
    ("크래프톤", "PUBG 블랙버짓(미출시)",  4077740, ["Black Budget"]),
    ("시프트업", "스텔라블레이드",        3489700, ["Stellar Blade", "스텔라 블레이드", "스텔라블레이드"]),
    ("NC",      "쓰론 앤 리버티",         2429640, ["Throne and Liberty", "THRONE AND LIBERTY", "쓰론 앤 리버티"]),
]
UA = ua(referer="https://store.playstation.com/")


def _get(url, hdr=None):
    h = dict(UA); h.update(hdr or {})
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")


def _match(name):
    """카드 제목 → 우리 표시명. 확장팩 키워드를 본편보다 먼저 본다(제목에 둘 다 들어 있다)."""
    nm = name or ""
    for stock, title, appid, keys in sorted(TITLES, key=lambda t: 0 if "DLC" in t[1] else 1):
        if any(k in nm for k in keys):
            return title
    return None


# ---------- PS 스토어 ----------
def ps_grid(cid, loc, size=100, off=0, sort=None):
    v = {"id": cid, "pageArgs": {"size": size, "offset": off}, "sortBy": sort, "filterBy": [], "facetOptions": []}
    url = "https://web.np.playstation.com/api/graphql/v1/op?" + urllib.parse.urlencode({
        "operationName": "categoryGridRetrieve",
        "variables": json.dumps(v, separators=(",", ":")),
        "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": PS_HASH}}, separators=(",", ":"))})
    d = json.loads(_get(url, {"content-type": "application/json", "accept": "application/json",
                              "x-psn-store-locale-override": loc}))
    g = (d.get("data") or {}).get("categoryGridRetrieve") or {}
    items = g.get("products") or g.get("concepts") or []
    return [it.get("name") or "" for it in items], g


def ps_list(cid, loc, sort=None, pages=3):
    names, total = [], None
    for p in range(pages):
        nm, g = ps_grid(cid, loc, off=p * 100, sort=sort)
        names += nm
        total = (g.get("pageInfo") or {}).get("totalCount")
        if (g.get("pageInfo") or {}).get("isLast") or not nm:
            break
        nap(0.4)
    return names, total


# ---------- Steam ----------
def steam_rows(filt, cc=None):
    """검색 결과 100줄의 appid 목록(순서 = 순위). 번들은 'a,b,c' 로 여러 appid."""
    url = ("https://store.steampowered.com/search/results/?filter=%s&infinite=1&start=0&count=100"
           "&ignore_preferences=1&l=english" % filt) + (f"&cc={cc}" if cc else "")
    d = json.loads(_get(url, {"referer": "https://store.steampowered.com/search/"}))
    rows = re.findall(r'data-ds-appid="([\d,]+)"[^>]*>.*?<span class="title">([^<]*)</span>',
                      d.get("results_html", ""), re.S)
    return [(set(int(x) for x in a.split(",") if x), html.unescape(t).strip()) for a, t in rows]


# ---------- MS 스토어 ----------
def ms_cards(loc, path):
    h = _get(f"https://www.microsoft.com/{loc}/store/{path}", {"accept": "text/html"})
    cards = re.findall(r'"compName":"Product Cards: Games".*?"productId":"([a-z0-9]{12})".*?"title":"([^"]+)"', h, re.S)
    seen, out = set(), []
    for pid, t in cards:
        if pid in seen:
            continue
        seen.add(pid); out.append(html.unescape(t))
    return out


# ---------- 공통 ----------
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
        raise RuntimeError("STORERANK 삽입 기준(const LIVE)을 못 찾음")
    return html_[:liv.end()] + "\n" + block + html_[liv.end():]


def collect():
    """[(src, region, n, {title: rank}), ...]  실패한 목록은 빠진다."""
    out, fails = [], []

    def add(src, region, n, ranks, top3):
        out.append({"src": src, "region": region, "n": n, "ranks": ranks, "top3": top3})
        hit = " · ".join(f"{t} {r}위" for t, r in ranks.items()) or "없음"
        print(f"  {src:9s} {REGION.get(region, region):4s} n={n:<4} {hit}")

    # PS — 예약(products) · 전체 판매·다운로드(concepts). 지역 4곳.
    for loc, region in [("en-US", "us"), ("ko-KR", "kr"), ("ja-JP", "jp"), ("en-GB", "gb")]:
        for src, cid, sort, pages in [("ps_pre", PS_PRE, None, 3),
                                      ("ps_sales", PS_ALL, {"name": "sales30", "isAscending": False}, 3),
                                      ("ps_dl", PS_ALL, {"name": "downloads30", "isAscending": False}, 3)]:
            try:
                names, total = ps_list(cid, loc, sort, pages)
                if not names:
                    raise ValueError("빈 목록(해시 변경?)")
                ranks = {}
                for i, nm in enumerate(names, 1):
                    t = _match(nm)
                    if t and t not in ranks:
                        ranks[t] = i
                n = total if src == "ps_pre" else len(names)     # 예약은 목록 전체(끝까지 받음), 전체는 상위 300 안
                add(src, region, n, ranks, names[:3])
            except Exception as e:
                fails.append(f"{src}/{region}: {str(e)[:60]}")
            nap(0.5)

    # Steam — 국가별 최고판매 100 · 위시리스트 100(글로벌)
    by_app = {appid: title for _, title, appid, _ in TITLES if appid}
    for cc in ["kr", "us", "jp", "de"]:
        try:
            rows = steam_rows("topsellers", cc)
            ranks = {}
            for i, (apps, nm) in enumerate(rows, 1):
                for a in apps:
                    t = by_app.get(a)
                    if t and t not in ranks:
                        ranks[t] = i
            add("steam_top", cc, len(rows), ranks, [nm for _, nm in rows[:3]])
        except Exception as e:
            fails.append(f"steam_top/{cc}: {str(e)[:60]}")
        nap(0.6)
    try:
        rows = steam_rows("popularwishlist")
        ranks = {}
        for i, (apps, nm) in enumerate(rows, 1):
            for a in apps:
                t = by_app.get(a)
                if t and t not in ranks:
                    ranks[t] = i
        add("steam_wish", "global", len(rows), ranks, [nm for _, nm in rows[:3]])
    except Exception as e:
        fails.append(f"steam_wish: {str(e)[:60]}")

    # MS 스토어 — Xbox 유료 인기(미국·한국·일본) · PC 유료 인기(미국) · Xbox 출시 예정(미국, 예약)
    for src, loc, region, path in [("xbox_top", "en-us", "us", "top-paid/games/xbox"),
                                   ("xbox_top", "ko-kr", "kr", "top-paid/games/xbox"),
                                   ("xbox_top", "ja-jp", "jp", "top-paid/games/xbox"),
                                   ("pc_top",   "en-us", "us", "top-paid/games/pc"),
                                   ("xbox_soon", "en-us", "us", "coming-soon/games/xbox")]:
        try:
            names = ms_cards(loc, path)
            if not names:
                raise ValueError("카드 0개(마크업 변경?)")
            ranks = {}
            for i, nm in enumerate(names, 1):
                t = _match(nm)
                if t and t not in ranks:
                    ranks[t] = i
            add(src, region, len(names), ranks, names[:3])
        except Exception as e:
            fails.append(f"{src}/{region}: {str(e)[:60]}")
        nap(0.5)
    return out, fails


def main():
    html_ = open(HTML, encoding="utf-8").read()
    today = datetime.datetime.now(KST).date().isoformat()
    old = _const(html_, "STORERANK") or {}
    items = {(it["title"], it["src"], it["region"]): it for it in old.get("items", [])}

    lists, fails = collect()
    total_lists = 4 * 3 + 4 + 1 + 5
    if fails:
        print("  [실패]", " | ".join(fails))
    # 절반 넘게 실패하면 기록(부분 실패는 늘 있는 일). PS 해시가 바뀌면 12개가 한꺼번에 빠지므로 여기서 걸린다.
    note_health("스토어 순위", f"{len(fails)}/{total_lists} 목록 실패: {fails[0]}" if len(fails) > total_lists / 2 else None)
    if not lists:
        print("[스토어 순위] 받은 목록 없음 — 기존 보존"); return

    stock_of = {title: stock for stock, title, _, _ in TITLES}
    for L in lists:
        for stock, title, appid, keys in TITLES:
            # 목록에 없는 제목도 '목록 밖(null)'으로 남긴다 — 단, 그 소스에서 한 번이라도 잡힌 적 있는 제목만
            # (스텔라블레이드가 스팀 위시리스트에 없는 건 정보가 아니다).
            key = (title, L["src"], L["region"])
            r = L["ranks"].get(title)
            if r is None and key not in items:
                continue
            it = items.setdefault(key, {"stock": stock, "title": title, "src": L["src"], "region": L["region"], "n": L["n"], "hist": []})
            it["n"] = L["n"]
            hist = [h for h in it["hist"] if h.get("d") != today]
            hist.append({"d": today, "r": r})
            it["hist"] = hist[-DAYS:]

    obj = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
           "lists": [{"src": L["src"], "region": L["region"], "n": L["n"], "top3": L["top3"]} for L in lists],
           "items": sorted(items.values(), key=lambda x: (x["stock"], x["title"], x["src"], x["region"]))}
    if "--dry-run" in sys.argv:
        print(json.dumps({k: v for k, v in obj.items() if k != "lists"}, ensure_ascii=False)[:1500]); return
    open(HTML, "w", encoding="utf-8").write(_put(html_, "STORERANK", obj))
    print(f"[OK] STORERANK 갱신 · 목록 {len(lists)}개 · 계열 {len(obj['items'])}개")


if __name__ == "__main__":
    main()
