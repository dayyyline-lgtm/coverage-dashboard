"""아마존 베스트셀러 수집 (curl_cffi). 브라우저 없이 TLS 지문만 크롬으로 위장한다.

핵심 원리 두 가지:
1. 베스트셀러 페이지의 `data-client-recs-list` 속성에 그 페이지 50개 전부의
   {순위, ASIN}이 JSON으로 들어있다. CSS 클래스명이 바뀌어도 안 깨지는 앵커.
2. 아마존은 페이지당 30개만 서버 렌더하고 31~50위는 지연 로딩한다.
   지연 로딩 엔드포인트(/acp/...)는 404라 막혔으므로, 빠진 구간은
   /dp/{ASIN} 상세 페이지를 개별 조회해서 메운다 (asin_cache로 중복 제거).
"""

import re
import json
import functools
import unicodedata
import time
import html as htmllib
import random
import datetime
from pathlib import Path

from bs4 import BeautifulSoup
from curl_cffi import requests


class BlockedError(Exception):
    """CAPTCHA / Robot Check 등으로 수집이 막힌 경우."""


# ---------------------------------------------------------------- 공통 유틸

def _sleep(rng):
    lo, hi = (rng if isinstance(rng, (list, tuple)) else (rng, rng))
    time.sleep(random.uniform(float(lo), float(hi)))


def parse_price(txt):
    """'$20.99' / '16,31 €' / '£16.99' / '1.299,00 €' → float."""
    if not txt:
        return None
    t = re.sub(r"[^\d.,]", "", txt.replace("\xa0", " "))
    if not t:
        return None
    if "," in t and "." in t:                       # 둘 다 있으면 뒤쪽이 소수점
        dec = max(t.rfind(","), t.rfind("."))
        t = re.sub(r"[.,]", "", t[:dec]) + "." + t[dec + 1:]
    else:
        for sep in (",", "."):
            if sep in t:
                tail = t.rsplit(sep, 1)[1]
                # 마지막 구분자 뒤가 2자리 이하이고 한 번만 나오면 소수점, 아니면 천단위
                t = t.replace(sep, "." if (len(tail) <= 2 and t.count(sep) == 1) else "")
    try:
        return round(float(t), 2)
    except ValueError:
        return None


def parse_int(txt):
    """'28,884' / '28.092' / '28 076' → 28884."""
    if not txt:
        return None
    d = re.sub(r"\D", "", txt)
    return int(d) if d else None


def parse_rating(txt):
    """'4.6 out of 5' / '4,6 von 5 Sternen' → 4.6."""
    if not txt:
        return None
    m = re.search(r"(\d+[.,]\d+|\d+)", txt)
    return float(m.group(1).replace(",", ".")) if m else None


def _norm(s):
    """비교용 정규화: 유니코드 아포스트로피·공백 통일 + 소문자."""
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("’", "'").replace("‘", "'").replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).lower()


@functools.lru_cache(maxsize=512)
def _brand_pattern(brand):
    # 단어경계 매칭. 단순 부분일치를 쓰면 'Anua'가 'manual'에, 'isoi'가 'poison'에 걸린다.
    return re.compile(r"(?<![a-z0-9])" + re.escape(_norm(brand)) + r"(?![a-z0-9])")


def match_brand(title, brands):
    """제목에서 브랜드를 찾아 그 이름을 반환. 대소문자·아포스트로피 표기차 무시."""
    if not title:
        return None
    t = _norm(title)
    for b in brands:
        if _brand_pattern(b).search(t):
            return b
    return None


# ---------------------------------------------------------------- HTTP

def make_session(market, impersonate="chrome"):
    """마켓별 세션. i18n-prefs 쿠키로 통화를 고정하는 게 핵심.

    이 쿠키가 없으면 아마존이 접속 IP 기준으로 통화를 환산해 내려준다
    (한국에서 amazon.com을 열면 가격이 KRW로 나온다).
    """
    s = requests.Session(impersonate=impersonate)
    domain = "." + market["domain"].replace("www.", "")
    s.cookies.set("i18n-prefs", market["currency"], domain=domain)
    return s


def get(session, url, market, referer=None, retries=3):
    headers = {"Accept-Language": market["lang"]}
    if referer:
        headers["Referer"] = referer
    last = None
    for attempt in range(retries):
        try:
            r = session.get(url, headers=headers, timeout=45)
            if r.status_code == 404:
                return None
            if r.status_code == 200:
                if re.search(r"validateCaptcha|Robot Check", r.text, re.I):
                    raise BlockedError(f"CAPTCHA에 걸렸습니다: {url}")
                return r.text
            last = f"HTTP {r.status_code}"
        except BlockedError:
            raise
        except Exception as e:                       # 네트워크 오류는 재시도
            last = f"{type(e).__name__}: {e}"
        time.sleep(2 ** attempt + random.random())
    raise BlockedError(f"{url} 수집 실패 ({last})")


# ---------------------------------------------------------------- 파싱

def parse_rank_map(page):
    """data-client-recs-list JSON → {순위: ASIN}. 페이지당 50개 전부."""
    m = re.search(r'data-client-recs-list="([^"]+)"', page)
    if not m:
        return {}
    try:
        recs = json.loads(htmllib.unescape(m.group(1)))
    except json.JSONDecodeError:
        return {}
    out = {}
    for r in recs:
        rank = r.get("metadataMap", {}).get("render.zg.rank")
        if rank and r.get("id"):
            out[int(rank)] = r["id"]
    return out


def parse_rendered(page):
    """서버 렌더된 항목(페이지당 상위 30개)의 상세를 {순위: {...}}로."""
    soup = BeautifulSoup(page, "html.parser")
    items = soup.select("#gridItemRoot") or [
        b.find_parent("div", id="gridItemRoot") or b.parent
        for b in soup.select(".zg-bdg-text")
    ]
    out = {}
    for it in items:
        if it is None:
            continue
        badge = it.select_one(".zg-bdg-text")
        if not badge or not re.search(r"\d", badge.get_text()):
            continue
        rank = int(re.sub(r"\D", "", badge.get_text()))

        img = it.select_one("img[alt]")
        price_el = it.select_one("span[class*='p13n-sc-price'], span.a-color-price")

        star = it.select_one("i[class*='a-star'] span.a-icon-alt") or \
            it.select_one("a[title*='out of 5'], span[aria-label*='out of 5']")
        star_txt = ""
        if star is not None:
            star_txt = star.get("title") or star.get("aria-label") or star.get_text()

        reviews = None
        for sp in it.select("span.a-size-small"):
            t = sp.get_text(strip=True)
            if re.search(r"\d", t) and re.fullmatch(r"[\d.,\s ()]+", t):
                reviews = parse_int(t)
                break

        out[rank] = {
            "title": (img["alt"].strip() if img else ""),
            "price": parse_price(price_el.get_text(strip=True) if price_el else None),
            "rating": parse_rating(star_txt),
            "reviews": reviews,
        }
    return out


# 상품 상세의 BSR 블록이 들어있는 컨테이너 후보 (레이아웃 변형 대응).
# '#1 Best Seller' 오렌지 뱃지(#zeitgeistBadge_feature_div 등)를 잡지 않으려면
# 반드시 이 컨테이너 안으로 범위를 좁혀야 한다.
_BSR_CONTAINERS = [
    "#detailBulletsWrapper_feature_div",
    "#detailBullets_feature_div",
    "#productDetails_detailBullets_sections1",
    "#prodDetails",
    "#item_details",
]


def _parse_bsr(soup):
    """BSR을 최상위/하위 두 단계로 반환.

    {"main_rank","main_cat","sub_rank","sub_cat"}

    **최상위 BSR이 실질 추적의 핵심이다.** 베스트셀러 리스트는 100위에서 잘리지만
    BSR은 순위권 밖에서도 계속 매겨진다. 제품이 리스트에서 빠져도 이 숫자로
    판매 추이를 이어서 볼 수 있다.
    """
    main = _bsr_entries(soup, with_paren=True)
    sub = _bsr_entries(soup, with_paren=False)
    return {
        "main_rank": main[-1][0] if main else None,
        "main_cat": main[-1][1] if main else None,
        "sub_rank": sub[-1][0] if sub else None,
        "sub_cat": sub[-1][1] if sub else None,
    }


def _bsr_entries(soup, with_paren):
    """BSR 줄에서 (순위, 카테고리명) 목록을 뽑는다.

    최상위 줄만 'Top 100 보기' 링크를 **괄호**로 달고 있어서 그걸로 두 단계를 가른다.
    with_paren=True 면 최상위 줄, False 면 하위 카테고리 줄.
    최상위 줄의 카테고리명은 링크 텍스트('See Top 100 in X')가 아니라 앞부분에서 뽑는다.
    """
    out = []
    for sel in _BSR_CONTAINERS:
        box = soup.select_one(sel)
        if not box:
            continue
        for a in box.select('a[href*="/gp/bestsellers/"], a[href*="/zgbs/"]'):
            block = a.find_parent(["li", "span", "td", "tr"])
            if not block:
                continue
            txt = block.get_text(" ", strip=True)
            if ("(" in txt) != with_paren:
                continue
            cat = a.get_text(strip=True)
            if with_paren:
                # '#31 in Beauty & Personal Care ( See Top 100 in ... )' → 괄호 앞만 본다
                head = txt.split("(")[0].strip()
                m = re.match(r"[^\d]*([\d.,]+)\s+\S+\s+(.+)$", head)
                if not m:
                    continue
                rank, cat = parse_int(m.group(1)), m.group(2).strip()
            else:
                if not cat or cat not in txt:
                    continue
                nums = re.findall(r"\d[\d.,]*", txt[:txt.rfind(cat)])
                if not nums:
                    continue
                rank = parse_int(nums[-1])
            if rank and (rank, cat) not in out:
                out.append((rank, cat))
        if out:
            break
    return out


def parse_detail(page):
    """/dp/{ASIN} 상세 페이지 파싱. 하위 카테고리 BSR까지 뽑는다."""
    soup = BeautifulSoup(page, "html.parser")

    title_el = soup.select_one("#productTitle")
    price_el = (soup.select_one("#corePrice_feature_div .a-offscreen")
                or soup.select_one("#corePriceDisplay_desktop_feature_div .a-offscreen")
                or soup.select_one(".a-price .a-offscreen"))
    star_el = soup.select_one("#acrPopover span.a-icon-alt") or soup.select_one("span.a-icon-alt")
    rev_el = soup.select_one("#acrCustomerReviewText")

    bsr = _parse_bsr(soup)

    return {
        "title": title_el.get_text(strip=True) if title_el else "",
        "price": parse_price(price_el.get_text(strip=True) if price_el else None),
        "rating": parse_rating(star_el.get_text(strip=True) if star_el else None),
        "reviews": parse_int(rev_el.get_text(strip=True) if rev_el else None),
        "bsr_main": bsr["main_rank"], "bsr_main_cat": bsr["main_cat"],
        "bsr_sub": bsr["sub_rank"], "bsr_sub_cat": bsr["sub_cat"],
    }


# ---------------------------------------------------------------- 캐시

def load_cache(path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def save_cache(path, cache):
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- 고정 추적 목록

def load_pinned(path):
    """한 번이라도 관심 브랜드로 잡힌 ASIN 목록. {"US:B09...": {brand,title,...}}"""
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def save_pinned(path, pinned):
    path.write_text(json.dumps(pinned, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- 수집

def list_url(market, node, page=1):
    base = f"https://{market['domain']}/gp/bestsellers/{str(node).strip('/')}"
    return base if page == 1 else f"{base}/?pg={page}"


def categories(market):
    """구버전 설정(category/top_n)도 받아주는 카테고리 목록."""
    cats = market.get("categories")
    if cats:
        return cats
    return [{"label": "Beauty", "node": market.get("category", "beauty"),
             "top_n": market.get("top_n", 50)}]


def collect_market(market, brands, cfg, cache, pinned, log=print):
    """한 마켓 수집 → 행 리스트.

    2단 구조다:
      (1) **발견** — 베스트셀러 리스트를 훑어 관심 브랜드 신규 ASIN을 찾는다.
      (2) **측정** — 고정 추적 중인 ASIN 전부의 BSR을 잰다. 리스트 100위 밖으로
          밀려나도 BSR은 계속 매겨지므로 추이가 안 끊긴다. 이게 핵심이다.
    """
    code = market["code"]
    session = make_session(market, cfg.get("impersonate", "chrome"))
    today = datetime.date.today().isoformat()
    tcfg = cfg.get("tracking", {})
    budget = [int(tcfg.get("max_detail_per_run", 160))]
    delay = cfg.get("detail", {}).get("delay", [1.5, 3.0])
    cats = categories(market)
    ref = list_url(market, cats[0]["node"])

    # ---------- (1) 리스트 수집 ----------
    sightings, rendered_by_asin = {}, {}
    for cat in cats:
        top_n = int(cat.get("top_n", 50))
        rank_map, rendered = {}, {}
        for pg in range(1, (2 if top_n > 50 else 1) + 1):
            url = list_url(market, cat["node"], pg)
            page = get(session, url, market)
            if page is None:
                raise BlockedError(f"{url} → 404 (categories 설정 확인)")
            rm = parse_rank_map(page)
            if not rm:
                dbg = Path(cfg["data_dir"]) / f"debug_{code}_{cat['label']}_p{pg}.html"
                dbg.write_text(page, encoding="utf-8")
                raise BlockedError(
                    f"[{code}/{cat['label']}] data-client-recs-list를 못 찾았습니다 → {dbg}")
            rank_map.update(rm)
            rendered.update(parse_rendered(page))
            _sleep(cfg.get("page_delay", [2, 4]))
        for rank, asin in rank_map.items():
            if rank > top_n:
                continue
            cur = sightings.get(asin)
            if cur is None or rank < cur["rank"]:
                sightings[asin] = {"cat": cat["label"], "rank": rank}
            d = rendered.get(rank)
            if d and d.get("title"):
                rendered_by_asin.setdefault(asin, d)
        log(f"[{code}/{cat['label']}] 순위 {len(rank_map)}개")

    # ---------- 상세 조회 (마켓 단위 예산 공유) ----------
    details = {}

    def detail(asin):
        if asin in details:
            return details[asin]
        if budget[0] <= 0:
            return None
        budget[0] -= 1
        try:
            page = get(session, f"https://{market['domain']}/dp/{asin}",
                       market, referer=ref, retries=2)
        except BlockedError as e:
            log(f"  ! {code}:{asin} 조회 중단 — {e}")
            budget[0] = 0
            return None
        _sleep(delay)
        d = parse_detail(page) if page else None
        if d and d["title"]:
            details[asin] = d
            cache[f"{code}:{asin}"] = {"title": d["title"], "first_seen": today}
            return d
        return None

    # ---------- (2) 제목 확정 → 브랜드 매칭 → 고정 목록 갱신 ----------
    titles, unknown = {}, []
    for asin in sightings:
        t = (rendered_by_asin.get(asin) or {}).get("title") \
            or cache.get(f"{code}:{asin}", {}).get("title", "")
        if t:
            titles[asin] = t
        else:
            unknown.append(asin)
    if unknown:
        log(f"[{code}] 신규 ASIN {len(unknown)}개 정체 확인...")
    for asin in unknown:
        d = detail(asin)
        if d:
            titles[asin] = d["title"]

    newly = 0
    for asin, t in titles.items():
        b = match_brand(t, brands)
        if not b:
            continue
        key = f"{code}:{asin}"
        if key not in pinned:
            pinned[key] = {"brand": b, "title": t, "first_seen": today}
            newly += 1
        pinned[key].update({"brand": b, "title": t, "last_seen": today})
    if newly:
        log(f"[{code}] 신규 추적 대상 {newly}개 추가")

    # ---------- (3) 고정 ASIN 전부 BSR 측정 (리스트 밖 포함) ----------
    mine = [k.split(":", 1)[1] for k in pinned if k.startswith(code + ":")]
    todo = [a for a in mine if a not in details]
    if todo:
        log(f"[{code}] BSR 측정 {len(todo)}건 (리스트 밖 포함)...")
    for asin in todo:
        detail(asin)

    # ---------- (4) 행 만들기 ----------
    rows = []
    for asin in mine:
        key = f"{code}:{asin}"
        info, d, s = pinned[key], details.get(asin), sightings.get(asin)
        lst = rendered_by_asin.get(asin) or {}
        if not d and not s:
            continue                      # 이번 실행에서 아무것도 못 얻음
        if d:
            info["last_seen"] = today      # BSR이 잡히면 리스트 밖이어도 살아있는 것
        rows.append({
            "market": code, "brand": info["brand"], "asin": asin,
            "title": (d or {}).get("title") or info.get("title", ""),
            "list_cat": (s or {}).get("cat"), "list_rank": (s or {}).get("rank"),
            "bsr_main": (d or {}).get("bsr_main"), "bsr_main_cat": (d or {}).get("bsr_main_cat"),
            "bsr_sub": (d or {}).get("bsr_sub"), "bsr_sub_cat": (d or {}).get("bsr_sub_cat"),
            # 리스트에 있으면 리스트 값이 그 순위에 오른 변형 기준이라 더 정확하다
            "price": lst.get("price") if lst.get("price") is not None else (d or {}).get("price"),
            "currency": market["currency"],
            "rating": lst.get("rating") if lst.get("rating") is not None else (d or {}).get("rating"),
            "reviews": lst.get("reviews") if lst.get("reviews") is not None else (d or {}).get("reviews"),
        })

    if budget[0] <= 0:
        log(f"[{code}] 상세 조회 예산 소진 — 나머지는 다음 실행에서 측정됩니다")
    log(f"[{code}] 수집 완료: {len(rows)}행 (추적 {len(mine)}개 중)")
    return rows


def retire(pinned, days, today, log=print):
    """오래 안 잡힌 ASIN은 추적 해제 (단종·리스팅 삭제 대응)."""
    if not days:
        return
    cut = (datetime.date.fromisoformat(today) - datetime.timedelta(days=int(days))).isoformat()
    gone = [k for k, v in pinned.items()
            if v.get("last_seen", v.get("first_seen", today)) < cut]
    for k in gone:
        pinned.pop(k)
    if gone:
        log(f"[정리] {len(gone)}개 ASIN 추적 해제 ({days}일 이상 미확인)")


def scrape_all(cfg, brands, log=print):
    """설정된 모든 마켓 수집. (행 리스트, 실패 마켓) 반환."""
    data_dir = Path(cfg["data_dir"])
    cache_path = data_dir / "asin_cache.json"
    pin_path = data_dir / "tracked_asins.json"
    cache, pinned = load_cache(cache_path), load_pinned(pin_path)
    today = datetime.date.today().isoformat()

    rows, failed = [], []
    for market in cfg["markets"]:
        if not market.get("enabled", True):
            continue
        try:
            rows += collect_market(market, brands, cfg, cache, pinned, log)
        except BlockedError as e:
            log(f"[{market['code']}] 실패: {e}")
            failed.append((market["code"], str(e)))
        finally:
            save_cache(cache_path, cache)
            save_pinned(pin_path, pinned)

    retire(pinned, cfg.get("tracking", {}).get("retire_after_days", 30), today, log)
    save_pinned(pin_path, pinned)
    return rows, failed
