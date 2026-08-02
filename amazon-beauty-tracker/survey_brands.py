"""일회성 조사: 6개 마켓 Beauty + Skin Care 랭킹에서 K뷰티 브랜드를 전수 탐색.

트래킹 대상을 정하기 위한 사전 조사용. 정기 실행 대상이 아니다.
결과: data/survey_result.json (브랜드 x 마켓 x 순위)
"""
import sys, re, json, time, unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scraper import (make_session, get, parse_rank_map, parse_rendered, parse_detail,
                     load_cache, save_cache, BlockedError)

BASE = Path(__file__).parent
DATA = BASE / "data"

MARKETS = [
    ("US", "www.amazon.com",   "en-US,en;q=0.9", "USD", 100),
    ("UK", "www.amazon.co.uk", "en-GB,en;q=0.9", "GBP", 50),
    ("DE", "www.amazon.de",    "de-DE,de;q=0.9", "EUR", 50),
    ("FR", "www.amazon.fr",    "fr-FR,fr;q=0.9", "EUR", 50),
    ("IT", "www.amazon.it",    "it-IT,it;q=0.9", "EUR", 50),
    ("ES", "www.amazon.es",    "es-ES,es;q=0.9", "EUR", 50),
]
# 마켓별 카테고리: (라벨, 노드경로)
CATS = {
    "US": [("Beauty", "beauty"), ("SkinCare", "beauty/11060451")],
    "UK": [("Beauty", "beauty"), ("SkinCare", "beauty/118464031")],
    "DE": [("Beauty", "beauty"), ("SkinCare", "beauty/122878031")],
    "FR": [("Beauty", "beauty"), ("SkinCare", "beauty/211020031")],
    "IT": [("Beauty", "beauty"), ("SkinCare", "beauty/6306897031")],
    "ES": [("Beauty", "beauty"), ("SkinCare", "beauty/6397934031")],
}

# 브랜드 -> 운영사 (상장사는 종목코드). 매칭은 단어경계 기준이라 'Anua'가 'manual'에 안 걸린다.
BRANDS = {
    # --- 상장 브랜드사 ---
    "medicube": "에이피알 278470", "AGE-R": "에이피알 278470", "APRILSKIN": "에이피알 278470",
    "LANEIGE": "아모레퍼시픽 090430", "innisfree": "아모레퍼시픽 090430",
    "COSRX": "아모레퍼시픽 090430", "Sulwhasoo": "아모레퍼시픽 090430",
    "illiyoon": "아모레퍼시픽 090430", "Mamonde": "아모레퍼시픽 090430",
    "ETUDE": "아모레퍼시픽 090430", "HERA": "아모레퍼시픽 090430",
    "belif": "LG생활건강 051900", "CNP": "LG생활건강 051900", "OHUI": "LG생활건강 051900",
    "Dr.Groot": "LG생활건강 051900", "THE FACE SHOP": "LG생활건강 051900",
    "Wellage": "LG생활건강 051900",
    "CLIO": "클리오 237880", "peripera": "클리오 237880", "goodal": "클리오 237880",
    "Ma:nyo": "마녀공장 439090", "Manyo": "마녀공장 439090",
    "VT Cosmetics": "브이티 018290", "Reedle": "브이티 018290",
    "TONYMOLY": "토니모리 214420",
    "MISSHA": "에이블씨엔씨 078520", "A'PIEU": "에이블씨엔씨 078520", "APIEU": "에이블씨엔씨 078520",
    "d'Alba": "달바글로벌", "dAlba": "달바글로벌",
    "Real Barrier": "네오팜 092730", "Atopalm": "네오팜 092730",
    "Rejuran": "파마리서치 214450",
    "rom&nd": "아이패밀리에스씨 114840", "romand": "아이패밀리에스씨 114840",
    "It's Skin": "잇츠한불 226320",
    "Coreana": "코리아나 027050",
    # --- 비상장 (IPO 후보 포함) ---
    "Beauty of Joseon": "구다이글로벌", "TIRTIR": "구다이글로벌",
    "SKIN1004": "구다이글로벌", "LAKA": "구다이글로벌", "AMUSE": "구다이글로벌",
    "Anua": "더파운더즈(IPO 준비)",
    "BIODANCE": "바이오던스", "Cellimax": "셀리맥스", "Melaxin": "닥터멜락신",
    "Round Lab": "라운드랩", "Torriden": "토리든", "numbuzin": "넘버즈인",
    "Abib": "아비브", "Purito": "퓨리토", "Mediheal": "엘앤피코스메틱",
    "Haruharu": "하루하루원더", "Isntree": "이즈앤트리", "Cell Fusion C": "셀퓨전씨",
    "isoi": "아이소이", "Huxley": "헉슬리", "SKINFOOD": "스킨푸드",
    "Dr.Jart": "닥터자르트(에스티로더)", "Dr. Jart": "닥터자르트(에스티로더)",
    "SOME BY MI": "썸바이미", "Mixsoon": "믹순", "AXIS-Y": "액시스와이",
    "Beplain": "비플레인", "Skinfood": "스킨푸드", "TOCOBO": "토코보",
    "I'm From": "아임프롬", "ma:nyo": "마녀공장 439090", "Nacific": "나시픽",
    "Pyunkang Yul": "편강율", "Klairs": "클레어스", "By Wishtrend": "위시트렌드",
    "Benton": "벤톤", "Etude House": "아모레퍼시픽 090430", "banila co": "바닐라코",
    "hince": "힌스", "dasique": "데이지크", "BBIA": "삐아", "Dr.G": "고운세상코스메틱",
    "Sungboon": "성분에디터", "MEDIPEEL": "메디필", "Medi-Peel": "메디필",
    "ONE THING": "원씽", "Aromatica": "아로마티카", "Innisfree": "아모레퍼시픽 090430",
}


def norm(s):
    """비교용 정규화: 유니코드 아포스트로피/공백 통일 + 소문자."""
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("’", "'").replace("‘", "'").replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).lower()


_PATTERNS = {b: re.compile(r"(?<![a-z0-9])" + re.escape(norm(b)) + r"(?![a-z0-9])")
             for b in BRANDS}


def match(title):
    t = norm(title)
    for b, pat in _PATTERNS.items():
        if pat.search(t):
            return b
    return None


def main():
    cache = load_cache(DATA / "asin_cache.json")
    found, stats = {}, {}
    detail_budget = 45          # 마켓·카테고리당 상세 조회 상한 (예의 + 시간)

    for code, dom, lang, cur, top_n in MARKETS:
        for label, node in CATS[code]:
            mk = {"code": code, "domain": dom, "category": node, "currency": cur, "lang": lang}
            s = make_session(mk)
            base = f"https://{dom}/gp/bestsellers/{node}"
            rank_map, rendered = {}, {}
            try:
                for pg in range(1, (2 if top_n > 50 else 1) + 1):
                    url = base if pg == 1 else f"{base}/?pg={pg}"
                    h = get(s, url, mk)
                    if not h:
                        break
                    rank_map.update(parse_rank_map(h))
                    rendered.update(parse_rendered(h))
                    time.sleep(2.5)
            except BlockedError as e:
                print(f"[{code}/{label}] 실패: {e}", file=sys.stderr)
                continue

            # 제목 없는 순위는 캐시 -> 상세조회 순으로 채운다
            titles, need = {}, []
            for rank, asin in sorted(rank_map.items()):
                if rank > top_n:
                    continue
                t = (rendered.get(rank) or {}).get("title") or ""
                if not t:
                    t = cache.get(f"{code}:{asin}", {}).get("title", "")
                if t:
                    titles[rank] = (asin, t)
                else:
                    need.append((rank, asin))

            spent = 0
            for rank, asin in need:
                if spent >= detail_budget:
                    break
                try:
                    p = get(s, f"https://{dom}/dp/{asin}", mk, referer=base, retries=2)
                except BlockedError:
                    break
                if p:
                    d = parse_detail(p)
                    if d["title"]:
                        titles[rank] = (asin, d["title"])
                        cache[f"{code}:{asin}"] = {"title": d["title"], "first_seen": "survey"}
                spent += 1
                time.sleep(2.0)
            save_cache(DATA / "asin_cache.json", cache)

            hits = 0
            for rank, (asin, t) in titles.items():
                b = match(t)
                if b:
                    hits += 1
                    found.setdefault(b, []).append(
                        {"market": code, "cat": label, "rank": rank, "asin": asin, "title": t[:70]})
            stats[f"{code}/{label}"] = {"순위확보": len(rank_map), "제목확보": len(titles),
                                        "K뷰티": hits}
            print(f"[{code}/{label}] 순위 {len(rank_map)} / 제목 {len(titles)} / K뷰티 {hits}건")

    (DATA / "survey_result.json").write_text(
        json.dumps({"found": found, "stats": stats, "owners": BRANDS},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n브랜드 {len(found)}개 발견 → data/survey_result.json")


if __name__ == "__main__":
    main()
