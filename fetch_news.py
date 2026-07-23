# -*- coding: utf-8 -*-
"""
종목별 뉴스 수집 스크립트
------------------------
public/index.html 안의  const NEWS = {...};  블록을 최신 뉴스로 교체합니다.

사용법:
    python fetch_news.py

수집처: 네이버 금융 종목뉴스 (키 불필요 · 시세/리포트와 같은 출처)
  https://finance.naver.com/item/news_news.naver?code=<종목코드>

같은 기사가 여러 종목에 걸리는 경우가 많아 URL 기준으로 합치고,
관련 종목을 모두 달아 둡니다. 데이터 변동이 없으면 파일을 건드리지 않습니다.
"""
import urllib.request, urllib.parse, json, re, time, datetime, sys, html as htmlmod

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML_PATH = "public/index.html"
UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com/"}

PER_STOCK = 3      # 종목당 최대 기사 수 (중복 제거 후)
TOTAL_MAX = 120    # 전체 상한 (파일 크기 관리)
PAUSE = 0.25       # 요청 간격 (초)
SIM = 0.45         # 제목 유사도 임계값(글자 2-gram 겹침계수). 이상이면 재탕으로 보고 하나만 남김.
                   # 재탕 기사(≈0.8+)는 확실히 제거, 완전히 다른 기사(≈0.1-)는 보존.
                   # 더 공격적으로 걸러려면 낮추되(예 0.35) 멀쩡한 기사까지 지울 위험이 커진다.

KST = datetime.timezone(datetime.timedelta(hours=9))


def clean(s):
    """태그 제거 + HTML 엔티티 복원"""
    s = re.sub(r"<[^>]+>", "", s)
    return htmlmod.unescape(s).replace("\xa0", " ").strip()


def _norm(t):
    """제목을 비교용으로 정규화 — 괄호·문장부호·공백 제거."""
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)|【[^】]*】|<[^>]*>", "", t)
    return re.sub(r"[^\w가-힣]", "", t).lower()


def _ngrams(t, n=2):
    """글자 2-gram 집합 — 한국어 조사/띄어쓰기 차이에 강하다(단어 비교보다 견고)."""
    s = _norm(t)
    return {s[i:i + n] for i in range(len(s) - n + 1)} if len(s) >= n else ({s} if s else set())


def _similar(a, b):
    """두 제목이 사실상 같은 내용인가 — 정규화 포함관계 또는 글자 2-gram 겹침계수."""
    na, nb = _norm(a), _norm(b)
    if na and nb and (na == nb or na in nb or nb in na):
        return True
    ga, gb = _ngrams(a), _ngrams(b)
    if not ga or not gb:
        return False
    inter = len(ga & gb)
    # 겹침계수(min 기준): 한 제목의 핵심이 다른 제목에 상당부분 포함되면 같은 사안으로 봄
    return inter / min(len(ga), len(gb)) >= SIM


def dedupe(arts, limit):
    """비슷한 제목(같은 사안 재탕)을 걸러 서로 다른 기사만 limit 개 남긴다."""
    kept = []
    for a in arts:
        if any(_similar(a["t"], k["t"]) for k in kept):
            continue
        kept.append(a)
        if len(kept) >= limit:
            break
    return kept


def fetch_stock_news(code):
    url = ("https://finance.naver.com/item/news_news.naver"
           f"?code={code}&page=1&sm=title_entity_id.basic")
    req = urllib.request.Request(url, headers=UA)
    raw = urllib.request.urlopen(req, timeout=15).read().decode("euc-kr", "replace")

    rows = re.findall(
        r'<td class="title">\s*<a href="([^"]+)"[^>]*>(.*?)</a>'
        r'.*?<td class="info">(.*?)</td>'
        r'.*?<td class="date">(.*?)</td>',
        raw, re.S)

    out = []
    for href, title, src, dt in rows:
        t = clean(title)
        if not t:
            continue
        link = htmlmod.unescape(href)
        if link.startswith("/"):
            link = "https://finance.naver.com" + link
        d = clean(dt).replace(".", "-", 2)          # 2026.07.23 03:30 -> 2026-07-23 03:30
        out.append({"t": t, "u": link, "s": clean(src), "d": d})
    return out


def main():
    src = open(HTML_PATH, encoding="utf-8").read()

    m = re.search(r"const DATA = (\{.*?\});\n", src, re.S)
    if not m:
        print("[!] DATA 블록을 찾지 못했습니다."); sys.exit(1)
    records = json.loads(m.group(1))["records"]

    m = re.search(r"const LIVE = (\{.*?\});\n", src, re.S)
    live = json.loads(m.group(1)) if m else {"stocks": {}}
    codes = {n: v.get("code") for n, v in live.get("stocks", {}).items() if v.get("code")}

    by_url, ok, fail = {}, 0, []
    for r in records:
        name = r["name"]
        code = codes.get(name)
        if not code:
            fail.append(name + "(코드없음)"); continue
        try:
            arts = dedupe(fetch_stock_news(code), PER_STOCK)   # 유사 기사 제거 후 상위 3
            ok += 1
        except Exception as e:
            fail.append(f"{name}({type(e).__name__})"); continue

        for a in arts:
            hit = by_url.get(a["u"])
            if hit:
                if name not in hit["co"]:
                    hit["co"].append(name)          # 같은 기사에 관련 종목 추가
            else:
                by_url[a["u"]] = {"co": [name], "sector": r["sector"], "sub": r["sub"], **a}
        print(f"  {name:<8} {len(arts)}건")
        time.sleep(PAUSE)

    items = sorted(by_url.values(), key=lambda x: x["d"], reverse=True)[:TOTAL_MAX]
    news = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "items": items}

    # 변동 없으면 파일을 건드리지 않는다 (asOf 는 비교에서 제외)
    old = re.search(r"const NEWS = (\{.*?\});\n", src, re.S)
    if old:
        try:
            prev = json.loads(old.group(1))
            if prev.get("items") == items:
                print(f"\n[SKIP] 뉴스 변동 없음 - index.html 그대로 둠 ({len(items)}건)")
                return
        except Exception:
            pass

    block = "const NEWS = " + json.dumps(news, ensure_ascii=False) + ";\n"
    if old:
        new_src = re.sub(r"const NEWS = \{.*?\};\n", lambda _: block, src, count=1, flags=re.S)
    else:
        # 최초 실행 — LIVE 블록 바로 뒤에 삽입
        anchor = re.search(r"const LIVE = \{.*?\};\n", src, re.S)
        if not anchor:
            print("[!] 삽입 위치(LIVE 블록)를 찾지 못했습니다."); sys.exit(1)
        new_src = src[:anchor.end()] + block + src[anchor.end():]

    open(HTML_PATH, "w", encoding="utf-8").write(new_src)
    print(f"\n[OK] 뉴스 {len(items)}건 갱신 (종목 {ok}개 수집" +
          (f" / 실패 {len(fail)}: {', '.join(fail[:5])}" if fail else "") + ")")


if __name__ == "__main__":
    main()
