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


def match_brand(title, brands):
    """제목에 브랜드 문자열이 포함되면 그 브랜드명을 반환 (대소문자 무시)."""
    if not title:
        return None
    t = title.lower()
    for b in brands:
        if b.lower() in t:
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


def _parse_sub_bsr(soup):
    """하위 카테고리 BSR을 (순위, 카테고리명)으로 반환. 없으면 (None, None).

    아마존 표기 (마켓마다 순위 접두사가 다르다):
        US/UK  Best Sellers Rank: #31 in Beauty ( See Top 100 in Beauty )
                                  #2 in Facial Masks
        DE     Amazon Bestseller-Rang: Nr. 7 in Kosmetik ( Siehe Top 100 ... )
                                       Nr. 1 in Gesichtsseren
        FR/IT/ES 는 n° / n. / nº 를 쓴다.

    그래서 '#숫자'로 찾으면 안 되고, **링크 텍스트가 곧 카테고리명**이라는 점을 이용한다.
    카테고리명 앞부분에서 마지막 숫자를 뽑으면 접두사 표기와 무관하게 순위가 나온다.
    최상위 항목만 'Top 100 보기' 링크를 괄호로 달고 있으므로 괄호가 있으면 건너뛴다
    (전체 카테고리 순위는 어차피 리스트에서 이미 알고 있다).
    """
    found = []
    for sel in _BSR_CONTAINERS:
        box = soup.select_one(sel)
        if not box:
            continue
        for a in box.select('a[href*="/gp/bestsellers/"], a[href*="/zgbs/"]'):
            block = a.find_parent(["li", "span", "td", "tr"])
            if not block:
                continue
            txt = block.get_text(" ", strip=True)
            if "(" in txt:                       # 최상위 카테고리 줄
                continue
            cat = a.get_text(strip=True)
            if not cat or cat not in txt:
                continue
            head = txt[:txt.rfind(cat)]          # 카테고리명 앞의 '#2 in' / 'Nr. 1 in'
            nums = re.findall(r"\d[\d.,]*", head)
            if not nums:
                continue
            pair = (parse_int(nums[-1]), cat)
            if pair[0] and pair not in found:
                found.append(pair)
        if found:
            break
    # 여러 개면 가장 깊은(마지막) 카테고리를 채택
    return found[-1] if found else (None, None)


def parse_detail(page):
    """/dp/{ASIN} 상세 페이지 파싱. 하위 카테고리 BSR까지 뽑는다."""
    soup = BeautifulSoup(page, "html.parser")

    title_el = soup.select_one("#productTitle")
    price_el = (soup.select_one("#corePrice_feature_div .a-offscreen")
                or soup.select_one("#corePriceDisplay_desktop_feature_div .a-offscreen")
                or soup.select_one(".a-price .a-offscreen"))
    star_el = soup.select_one("#acrPopover span.a-icon-alt") or soup.select_one("span.a-icon-alt")
    rev_el = soup.select_one("#acrCustomerReviewText")

    sub_rank, sub_cat = _parse_sub_bsr(soup)

    return {
        "title": title_el.get_text(strip=True) if title_el else "",
        "price": parse_price(price_el.get_text(strip=True) if price_el else None),
        "rating": parse_rating(star_el.get_text(strip=True) if star_el else None),
        "reviews": parse_int(rev_el.get_text(strip=True) if rev_el else None),
        "sub_bsr_rank": sub_rank,
        "sub_bsr_cat": sub_cat,
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


# ---------------------------------------------------------------- 수집

def bestsellers_url(market, page=1):
    base = f"https://{market['domain']}/gp/bestsellers/{market['category'].strip('/')}"
    return base if page == 1 else f"{base}/?pg={page}"


def scrape_market(market, brands, cfg, cache, log=print):
    """한 마켓의 top_n을 수집. [{market, rank, asin, title, price, ...}] 반환."""
    session = make_session(market, cfg.get("impersonate", "chrome"))
    top_n = int(market.get("top_n", 50))
    page_delay = cfg.get("page_delay", [2, 4])

    rank_map, rendered = {}, {}
    for page_no in range(1, (2 if top_n > 50 else 1) + 1):
        url = bestsellers_url(market, page_no)
        page = get(session, url, market)
        if page is None:
            raise BlockedError(f"{url} → 404 (category 설정을 확인하세요)")
        rm = parse_rank_map(page)
        if not rm:
            debug = Path(cfg["data_dir"]) / f"debug_{market['code']}_p{page_no}.html"
            debug.write_text(page, encoding="utf-8")
            raise BlockedError(
                f"[{market['code']}] data-client-recs-list를 못 찾았습니다. "
                f"아마존이 구조를 바꿨을 수 있습니다 → {debug}"
            )
        rank_map.update(rm)
        rendered.update(parse_rendered(page))
        _sleep(page_delay)

    items = []
    for rank in sorted(rank_map):
        if rank > top_n:
            continue
        asin = rank_map[rank]
        key = f"{market['code']}:{asin}"
        d = dict(rendered.get(rank) or {})
        if not d.get("title"):
            d["title"] = cache.get(key, {}).get("title", "")
        items.append({
            "market": market["code"], "rank": rank, "asin": asin,
            "title": d.get("title", ""), "price": d.get("price"),
            "currency": market["currency"], "rating": d.get("rating"),
            "reviews": d.get("reviews"),
            "sub_bsr_rank": None, "sub_bsr_cat": None,
            "_rendered": rank in rendered,
        })

    log(f"[{market['code']}] 순위+ASIN {len(items)}개 / 페이지 렌더 "
        f"{sum(1 for i in items if i['_rendered'])}개")

    _fill_details(session, market, brands, cfg, cache, items, log)
    for it in items:
        it.pop("_rendered", None)
    return items


def _fill_details(session, market, brands, cfg, cache, items, log):
    """렌더 안 된 구간을 /dp/ 개별 조회로 보강.

    mode=tracked(기본): 캐시에 없는 ASIN(정체 파악용) + 추적 브랜드 ASIN(최신 지표용)만.
    브랜드가 아닌 걸로 이미 판명된 ASIN은 다시 조회하지 않으므로 요청 수가 안 늘어난다.
    """
    dcfg = cfg.get("detail", {})
    mode = dcfg.get("mode", "tracked")
    if mode == "off":
        return

    # 1~30위는 리스트에 상세가 이미 있으므로 기본적으로 건너뛴다.
    # tracked_all_ranks: true 로 켜면 추적 브랜드는 순위와 무관하게 조회해서
    # 하위 카테고리 BSR까지 받아온다 (요청 수가 늘어나는 대신 지표가 좋아진다).
    all_ranks = bool(dcfg.get("tracked_all_ranks", False))

    targets = []
    for it in items:
        key = f"{market['code']}:{it['asin']}"
        cached_title = cache.get(key, {}).get("title", "")
        is_tracked = bool(match_brand(it["title"] or cached_title, brands))
        if it["_rendered"]:
            if all_ranks and is_tracked:
                targets.append(it)
            continue
        if mode == "all":
            targets.append(it)
        elif key not in cache:                       # 처음 보는 ASIN → 정체 확인 필요
            targets.append(it)
        elif is_tracked:
            targets.append(it)                       # 추적 브랜드 → 가격/리뷰 갱신

    cap = int(dcfg.get("max_per_run", 60))
    if len(targets) > cap:
        log(f"[{market['code']}] 상세 조회 대상 {len(targets)}개 중 {cap}개만 처리 "
            f"(detail.max_per_run 제한). 나머지는 다음 실행에서 이어집니다.")
        targets = targets[:cap]
    if not targets:
        return

    log(f"[{market['code']}] 상세 조회 {len(targets)}건...")
    ref = bestsellers_url(market)
    today = datetime.date.today().isoformat()
    ok = 0
    for it in targets:
        url = f"https://{market['domain']}/dp/{it['asin']}"
        try:
            page = get(session, url, market, referer=ref, retries=2)
        except BlockedError as e:
            log(f"  ! {it['asin']} 조회 중단: {e}")
            break
        if page:
            d = parse_detail(page)
            if d["title"]:
                if it["_rendered"]:
                    # 리스트 값이 그 순위에 실제로 오른 변형(variant) 기준이라 더 정확하다.
                    # (상세 페이지는 기본 선택 변형의 가격을 보여주므로 다를 수 있다)
                    fields = {k: d[k] for k in ("sub_bsr_rank", "sub_bsr_cat")
                              if d[k] is not None}
                else:
                    fields = {k: v for k, v in d.items() if v is not None}
                it.update(fields)
                cache[f"{market['code']}:{it['asin']}"] = {
                    "title": d["title"], "first_seen": today}
                ok += 1
        _sleep(dcfg.get("delay", [1.5, 3.0]))
    log(f"[{market['code']}] 상세 조회 성공 {ok}/{len(targets)}")


def scrape_all(cfg, brands, log=print):
    """설정된 모든 마켓 수집. (전체 아이템, 실패한 마켓 목록) 반환."""
    data_dir = Path(cfg["data_dir"])
    cache_path = data_dir / "asin_cache.json"
    cache = load_cache(cache_path)

    all_items, failed = [], []
    for market in cfg["markets"]:
        if not market.get("enabled", True):
            continue
        try:
            all_items += scrape_market(market, brands, cfg, cache, log)
        except BlockedError as e:
            log(f"[{market['code']}] 실패: {e}")
            failed.append((market["code"], str(e)))
        finally:
            save_cache(cache_path, cache)
    return all_items, failed
