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
import urllib.parse
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


# ★ 아마존이 스스로 공개하는 판매량 배지.
#
# 'BSR → 판매량' 환산의 **정답지**다. 정글스카우트가 셀러 패널로 사 모으는 그 데이터를
# 아마존이 상품 페이지에 직접 띄워준다. 6개 마켓 전부 있고 표기만 다르다:
#
#   US  100K+ bought in past month      UK  10K+ bought in past week
#   DE  8000+ gekauft Mal im letzten Monat
#   FR  Plus de 4 k achetés au cours du mois dernier      ← '+' 기호가 없다
#   IT  10.000+ acquistati nel mese scorso                ← 천단위 점
#   ES  4 mil+ comprados el mes pasado                    ← 'mil' = 천
#
# 주의 1: 구간값이라 정확한 수가 아니라 **하한**이다(100K+ 는 10만 이상).
# 주의 2: 월간 배지와 주간 배지가 따로 있다. 주간은 4.33을 곱해 월 기준으로 맞춘 뒤,
#         둘 중 **큰 쪽**을 쓴다. 하한값이므로 큰 쪽이 정보량이 많다.
_BOUGHT_SELECTORS = [
    "#socialProofingAsinFaceout_feature_div",
    "#social-proofing-faceout-title",
    "#pqv-bought-in-last-month",
]
# 숫자부는 **탐욕적으로** 잡아야 한다. 비탐욕이면 이탈리아 '10.000+'에서 '10'만 먹는다.
_BOUGHT_NUM = re.compile(r"(\d[\d.,]*\d|\d)\s*(k|m|mil|mila|tsd)?\b", re.I)
_WEEK_WORDS = ("week", "woche", "semaine", "semana", "settimana")
_MONTH_WORDS = ("month", "monat", "mois", "mes", "mese")
_MULT = {"k": 1_000, "m": 1_000_000, "mil": 1_000, "mila": 1_000, "tsd": 1_000}
WEEKS_PER_MONTH = 4.33


def bought_from_text(txt):
    """배지 문구 한 줄 → (월 환산 개수, 원표기 기간). 상세페이지·검색카드 공용."""
    if not txt:
        return None, None
    low = txt.lower()
    # 주 단위를 먼저 본다 ('mes'가 'mese'의 일부라 월을 먼저 보면 오판한다)
    pos, period = None, None
    for w in _WEEK_WORDS:
        if w in low:
            pos, period = low.index(w), "week"
            break
    if period is None:
        for w in _MONTH_WORDS:
            if w in low:
                pos, period = low.index(w), "month"
                break
    if period is None:
        return None, None

    # 기간 단어 **앞쪽**에서 마지막 숫자를 쓴다. 검색 카드는 배지 앞에 평점이 붙어
    # ('4.7 out of 5 stars (1.1K) 1K+ bought in past month') 앞에서부터 찾으면
    # 평점 4.7 을 판매량으로 읽는다.
    ms = list(_BOUGHT_NUM.finditer(txt[:pos]))
    if not ms:
        return None, None
    m = ms[-1]
    num = parse_price(m.group(1))
    if not num:
        return None, None
    units = num * _MULT.get((m.group(2) or "").lower(), 1)
    return int(round(units * (WEEKS_PER_MONTH if period == "week" else 1))), period


def _parse_bought(soup):
    """상품 상세의 판매량 배지 → (월 환산, 원표기, 월배지 원본, 주배지 원본).

    아마존은 월간 배지와 주간 배지를 **따로** 띄운다. 둘 다 원본으로 남긴다.
    주간을 월로 환산해 하나로 합쳐 버리면 훨씬 짧은 관측창을 잃는다 —
    주간은 최근 7일이라 월간(30일)보다 변화를 빨리 보여준다.
    """
    raw = {"month": None, "week": None}
    for sel in _BOUGHT_SELECTORS:
        el = soup.select_one(sel)
        if not el:
            continue
        units, period = bought_from_text(el.get_text(" ", strip=True))
        if not units or not period:
            continue
        base = units / WEEKS_PER_MONTH if period == "week" else units   # 원표기로 되돌린다
        if raw[period] is None or base > raw[period]:
            raw[period] = base
    m = raw["month"]
    w = raw["week"]
    cand = [(m, "month")] + ([(w * WEEKS_PER_MONTH, "week")] if w else [])
    cand = [c for c in cand if c[0]]
    if not cand:
        return None, None, None, None
    best, period = max(cand)
    return (int(round(best)), period,
            int(round(m)) if m else None, int(round(w)) if w else None)


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


_PARENT_RE = re.compile(r'"parentAsin"\s*:\s*"([A-Z0-9]{10})"')


def parse_parent(page):
    """부모 ASIN. 변형(용량·색상)들이 이걸 공유한다.

    판매량 배지는 **부모 단위(제품군 합계)** 로 보인다. 그래서 같은 부모를 가진
    ASIN을 둘 이상 추적하면 판매량이 중복 집계된다. 이 값을 기록해 두면
    중복을 자동으로 걸러낼 수 있다.
    """
    m = _PARENT_RE.search(page or "")
    return m.group(1) if m else None


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
    bought, period, bm, bw = _parse_bought(soup)

    return {
        "bought": bought, "bought_period": period,
        "bought_m": bm, "bought_w": bw,
        "parent_asin": parse_parent(page),
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


# ---------------------------------------------------------------- 브랜드 검색

# 검색 결과 카드 한 장에 ASIN·제목·가격·평점·판매량이 다 들어있다.
# 베스트셀러 리스트만 보면 top100에 든 제품만 잡혀서, 매출이 여러 제품에 넓게
# 퍼진 브랜드(COSRX 등)가 심하게 과소평가된다. 검색은 카탈로그 전체를 훑는다.
# 다만 검색 카드의 판매량 배지 커버리지는 24~72%로 들쭉날쭉하다(상세페이지는 100%).
# 그래서 검색은 **발견**용이고, 정밀 측정은 /dp/ 가 맡는다.
_CARD = 'div[data-asin][data-component-type="s-search-result"]'
_TITLE_SELS = ["[data-cy='title-recipe']", "h2 a span", "h2 span"]


def _card_title(card):
    for sel in _TITLE_SELS:
        el = card.select_one(sel)
        if el:
            t = el.get_text(" ", strip=True)
            if len(t) > 12:          # 'COSRX' 같은 브랜드 라벨만 잡히는 경우를 거른다
                return t
    return ""


def _card_badge(card):
    """검색 카드에서 판매량 배지 **문구만** 골라 파싱한다.

    카드 전체 텍스트를 그냥 넘기면 '4.6 out of 5 stars' 의 4.6 을 판매량으로 읽는다.
    배지 문구를 담은 짧은 요소를 먼저 찾아야 한다.
    """
    for el in card.select("span, div"):
        txt = el.get_text(" ", strip=True)
        if not (8 < len(txt) < 70) or not re.search(r"\d", txt):
            continue
        low = txt.lower()
        if any(w in low for w in _WEEK_WORDS + _MONTH_WORDS):
            units, period = bought_from_text(txt)
            if units:
                return units, period
    return None, None


def search_brand(session, market, brand, max_pages=3, delay=(2.0, 3.5), log=print):
    """브랜드 검색으로 카탈로그 발견. {asin: {...}} 반환."""
    found = {}
    base = f"https://{market['domain']}/s"
    query = urllib.parse.quote(brand)
    for pg in range(1, int(max_pages) + 1):
        url = f"{base}?k={query}&i=beauty" + (f"&page={pg}" if pg > 1 else "")
        try:
            page = get(session, url, market, referer=f"https://{market['domain']}/", retries=2)
        except BlockedError as e:
            # 삼키지 않고 올린다. 예전엔 여기서 break 만 하고 다음 브랜드로 넘어가
            # 이미 막힌 마켓을 9개 브랜드 내내 두드렸다(2026-08-04: US·ES 가 그렇게
            # 503 을 줄줄이 맞았고 그 뒤 DE·FR·IT 가 CAPTCHA 로 막혔다).
            # 차단 신호를 받으면 그 마켓에서 바로 물러나는 게 회복이 빠르다.
            log(f"  ! {market['code']}/{brand} 검색 중단 — {e}")
            raise
        if not page:
            break
        cards = BeautifulSoup(page, "html.parser").select(_CARD)
        if not cards:
            # 검색 요청을 연달아 많이 하면 아마존이 카드 없는 페이지를 돌려준다.
            # 조용히 넘어가면 그 마켓 전체가 통째로 비는데 로그엔 아무것도 안 남는다
            # (실제로 UK/DE가 이렇게 0건이 됐다). 한 번 쉬었다 재시도한다.
            if pg == 1:
                log(f"  · {market['code']}/{brand} 검색 결과 0 — 20초 쉬고 재시도")
                time.sleep(20)
                page = get(session, url, market,
                           referer=f"https://{market['domain']}/", retries=2)
                cards = BeautifulSoup(page, "html.parser").select(_CARD) if page else []
                if not cards:
                    log(f"  ! {market['code']}/{brand} 검색 실패 (카드 0) — 이 브랜드 건너뜀")
            if not cards:
                break
        added = 0
        for c in cards:
            asin = c.get("data-asin")
            title = _card_title(c)
            # 검색은 유사 제품도 섞어서 준다. 제목에 브랜드가 있어야 인정.
            if not asin or not title or not _brand_pattern(brand).search(_norm(title)):
                continue
            if asin in found:
                continue
            units, period = _card_badge(c)
            bm = units if period == "month" else None
            bw = int(round(units / WEEKS_PER_MONTH)) if period == "week" and units else None
            price_el = c.select_one(".a-price .a-offscreen")
            star = c.select_one("span.a-icon-alt")
            found[asin] = {
                "title": title,
                "price": parse_price(price_el.get_text(strip=True)) if price_el else None,
                "bought": units, "bought_period": period,
                "bought_m": bm, "bought_w": bw,
                "rating": parse_rating(star.get_text(strip=True)) if star else None,
            }
            added += 1
        if added == 0:
            break
        _sleep(delay)
    return found


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

    # ---------- (3) 브랜드 검색으로 카탈로그 전체 발견 ----------
    # 베스트셀러 리스트만 보면 top100에 든 제품만 잡혀서, 매출이 여러 제품에 넓게
    # 퍼진 브랜드가 심하게 과소평가된다(COSRX US: 리스트 1개 vs 검색 110개).
    scfg = cfg.get("search", {})
    from_search = {}
    if scfg.get("enabled", True):
        want = scfg.get("brands", "auto")
        if want == "auto":
            want = sorted({v["brand"] for v in pinned.values()})
        for b in want:
            try:
                hits = search_brand(session, market, b, scfg.get("max_pages", 3),
                                    scfg.get("delay", [2.0, 3.5]), log)
            except BlockedError as e:
                log(f"[{code}] 차단 감지 — 이 마켓 브랜드 검색을 여기서 접습니다: {e}")
                break
            for asin, info in hits.items():
                key = f"{code}:{asin}"
                if key not in pinned:
                    pinned[key] = {"brand": b, "title": info["title"], "first_seen": today}
                pinned[key].update({"brand": b, "title": info["title"], "last_seen": today})
                from_search[asin] = info
            if hits:
                log(f"[{code}] 검색 {b}: 카탈로그 {len(hits)}개 "
                    f"(판매량 {sum(1 for v in hits.values() if v['bought'])}개)")

    # ---------- (4) 판매량 상위는 /dp/ 로 정밀 측정 ----------
    # 검색 카드의 배지 커버리지는 24~72%로 들쭉날쭉하지만 상세페이지는 100%다.
    # 예산 안에서 '많이 팔리는 순'으로 정확히 잰다.
    mine = [k.split(":", 1)[1] for k in pinned if k.startswith(code + ":")]
    dcfg = cfg.get("detail", {})
    per_brand = int(dcfg.get("top_per_brand", 5))
    topn = int(dcfg.get("top_per_market", 45))

    def _weight(a):
        if a in sightings:
            return 10 ** 9 - sightings[a]["rank"]      # 리스트 진입분이 최우선
        return (from_search.get(a) or {}).get("bought") or 0

    # 예산을 **브랜드별로 나눈다**. 그냥 판매량 순으로 자르면 큰 브랜드가 다 먹어서
    # 작은 브랜드는 BSR이 하나도 안 잡히고, 결국 브랜드 비교가 다시 왜곡된다.
    by_brand = {}
    for a in mine:
        if a in details:
            continue
        by_brand.setdefault(pinned[f"{code}:{a}"]["brand"], []).append(a)
    todo = []
    for b, asins in by_brand.items():
        todo += sorted(asins, key=_weight, reverse=True)[:per_brand]
    todo = sorted(todo, key=_weight, reverse=True)[:topn]
    if todo:
        log(f"[{code}] 정밀 측정(/dp/) {len(todo)}건")
    for asin in todo:
        detail(asin)

    # ---------- (4) 행 만들기 ----------
    rows = []
    for asin in mine:
        key = f"{code}:{asin}"
        info, d, s = pinned[key], details.get(asin), sightings.get(asin)
        lst = rendered_by_asin.get(asin) or {}
        sr = from_search.get(asin) or {}
        if not d and not s and not sr:
            continue                      # 이번 실행에서 아무것도 못 얻음
        if d:
            info["last_seen"] = today      # BSR이 잡히면 리스트 밖이어도 살아있는 것
        rows.append({
            "market": code, "brand": info["brand"], "asin": asin,
            "title": (d or {}).get("title") or info.get("title", ""),
            "list_cat": (s or {}).get("cat"), "list_rank": (s or {}).get("rank"),
            "bsr_main": (d or {}).get("bsr_main"), "bsr_main_cat": (d or {}).get("bsr_main_cat"),
            "bsr_sub": (d or {}).get("bsr_sub"), "bsr_sub_cat": (d or {}).get("bsr_sub_cat"),
            # 아마존이 직접 공개하는 월간 판매량(하한). 가격과 곱하면 매출 추정이 된다.
            "bought": (d or {}).get("bought") or sr.get("bought"),
            "bought_period": (d or {}).get("bought_period") or sr.get("bought_period"),
            "bought_m": (d or {}).get("bought_m") or sr.get("bought_m"),
            "bought_w": (d or {}).get("bought_w") or sr.get("bought_w"),
            "src": "dp" if d else ("search" if sr else "list"),
            "parent_asin": (d or {}).get("parent_asin"),
            # 리스트에 있으면 리스트 값이 그 순위에 오른 변형 기준이라 더 정확하다
            "price": (lst.get("price") if lst.get("price") is not None
                      else (d or {}).get("price") if (d or {}).get("price") is not None
                      else sr.get("price")),
            "currency": market["currency"],
            "rating": (lst.get("rating") if lst.get("rating") is not None
                       else (d or {}).get("rating") if (d or {}).get("rating") is not None
                       else sr.get("rating")),
            "reviews": lst.get("reviews") if lst.get("reviews") is not None else (d or {}).get("reviews"),
        })

    seen_parents = {}
    for r in rows:
        pa = r.get("parent_asin")
        if pa:
            seen_parents.setdefault(pa, []).append(r["asin"])
    dups = {k: v for k, v in seen_parents.items() if len(v) > 1}
    if dups:
        # 판매량 배지가 부모 단위라 같은 부모를 여러 개 세면 매출이 부풀려진다
        for pa, asins in dups.items():
            log(f"[{code}] ⚠ 같은 부모({pa}) ASIN {len(asins)}개 — 판매량 중복 가능: "
                + ", ".join(asins))

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
    gap = cfg.get("market_gap", [60, 90])

    live = [m for m in cfg["markets"] if m.get("enabled", True)]

    # 마켓 순서를 날마다 한 칸씩 돌린다.
    #
    # 실측(2026-08-04~09 run.log): 막힌 마켓은 DE(3번째)·FR(4번째)·IT(5번째)뿐이고
    # US·UK(1·2번째)는 한 번도 없었다. 늦게 도는 마켓일수록 그 회차에 이미 쌓인
    # 요청량 때문에 불리하다. 순서를 고정해 두면 **늘 같은 나라만** 구멍이 나서
    # 그 나라 시계열만 성기게 된다. 돌려 두면 손해가 고르게 퍼진다.
    # (무작위가 아니라 날짜 기준이라 같은 날 재실행하면 순서가 같다 — 재현 가능.)
    if len(live) > 1:
        live = live[datetime.date.today().toordinal() % len(live):] + \
               live[:datetime.date.today().toordinal() % len(live)]
        log(f"[순서] {' → '.join(m['code'] for m in live)}")

    def run_market(market, first):
        """한 마켓 수집. 성공하면 True."""
        if not first:
            # 마켓을 갈아탈 때 한 박자 쉰다. 예전엔 이 휴식이 브랜드 검색 블록 안에 있어서
            # 검색을 끄면 같이 사라졌고, 6개국을 쉬지 않고 이어 두드리게 됐다.
            _sleep(gap)
        try:
            rows.extend(collect_market(market, brands, cfg, cache, pinned, log))
            return True
        except BlockedError as e:
            log(f"[{market['code']}] 실패: {e}")
            failed.append((market["code"], str(e)))
            # 한 마켓이 막히면 다음 마켓도 곧 막힌다(같은 IP다). 더 길게 쉰다.
            _sleep([g * 3 for g in gap])
            return False
        finally:
            save_cache(cache_path, cache)
            save_pinned(pin_path, pinned)

    for i, market in enumerate(live):
        run_market(market, i == 0)

    # ── 실패한 마켓만 맨 끝에서 한 번 더
    #
    # CAPTCHA 는 `get()` 의 재시도 루프가 즉시 raise 한다(그 자리에서 다시 치면
    # 또 CAPTCHA 만 맞고 차단 신호만 키운다 — 그 판단은 옳다). 문제는 **그 뒤로
    # 아무 시도도 안 한다**는 것이었다. 첫 요청 한 번 운이 나쁘면 그 마켓 하루치가
    # 통째로 날아갔다(실측: 6회차 중 4번, 늘 베스트셀러 첫 요청에서).
    #
    # 그래서 재시도를 '그 자리'가 아니라 **전 마켓을 다 돈 뒤**로 미룬다.
    #   · 원래 시도와 수십 분 벌어진다 (가장 긴 냉각)
    #   · collect_market 이 마켓마다 세션을 새로 만든다 = 쿠키·지문이 새것
    #   · 실패가 없는 날엔 요청이 한 건도 안 는다
    retry_n = int(cfg.get("retry_failed_markets", 1))
    if failed and retry_n > 0:
        # 냉각을 더 길게 잡을수록 통과율은 오르지만 아침 브리핑이 늦어진다.
        # 3~5분 + 그 마켓 수집(~5분) = 실패한 날만 도착이 약 10분 밀린다.
        cool = cfg.get("retry_cooldown", [180, 300])
        stuck = [c for c, _ in failed]
        log(f"[재시도] 막혔던 마켓 {', '.join(stuck)} — {cool[0]}~{cool[1]}초 쉬었다가 다시")
        _sleep(cool)
        failed.clear()
        for i, code in enumerate(stuck):
            market = next((m for m in live if m["code"] == code), None)
            if market and run_market(market, i == 0):
                log(f"[재시도] {code} 성공")

    retire(pinned, cfg.get("tracking", {}).get("retire_after_days", 30), today, log)
    save_pinned(pin_path, pinned)
    return rows, failed
