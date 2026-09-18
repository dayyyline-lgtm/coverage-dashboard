# -*- coding: utf-8 -*-
"""
종목별 뉴스 수집 스크립트
------------------------
public/index.html 안의  const NEWS = {...};  블록을 최신 뉴스로 교체합니다.

사용법:
    python fetch_news.py

수집처: 네이버 종목뉴스 JSON (키 불필요 · 시세/리포트와 같은 출처)
  https://api.stock.naver.com/news/stock/<종목코드>?pageSize=&page=1

⚠ 2026-09-18: 옛 주소 finance.naver.com/item/news_news.naver 가 **HTTP 410 Gone** 이 됐다.
  네이버가 그 페이지를 내렸다. 로컬·러너 양쪽에서 41/41 종목 실패라 뉴스 탭이 통째로 비어 있었고,
  수집기가 '0건 = 변동 없음' 으로 조용히 넘어가 눈에 띄지 않았다(health.json 에는 남아 있었다).
  지금은 모바일 앱이 쓰는 JSON API 를 쓴다 — 응답은 [{total, items:[...]}] 묶음 배열이고
  한 묶음이 같은 사건의 기사 뭉치다(total>1 이면 연관기사). 우리는 묶음마다 대표 1건만 쓴다.

같은 기사가 여러 종목에 걸리는 경우가 많아 URL 기준으로 합치고,
관련 종목을 모두 달아 둡니다. 데이터 변동이 없으면 파일을 건드리지 않습니다.
"""
import urllib.request, urllib.parse, json, re, time, datetime, sys, html as htmlmod

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML_PATH = "public/index.html"
# 네이버 금융 스크래핑 — 고정 UA 는 차단 목록에 가장 먼저 오른다.
# 브라우저 헤더 한 벌 + 흔들린 간격으로 바꾸고, 막히면 health.json 에 남긴다.
from collector_health import ua, nap, note_health

UA = ua(referer="https://m.stock.naver.com/")

PER_STOCK = 10     # 종목당 최대 기사 수 (중복 제거 후)
                   # 커버리지 표의 뉴스 링크는 '제목에 종목명이 든 기사'만 연결하는데,
                   # 3건만 담으면 그 3건이 전부 범용 시황기사일 때 링크가 사라진다.
                   # (실제로 29종목 중 18종목이 그래서 빈칸이었다.) 후보를 넉넉히 둔다.
TOTAL_MAX = 300    # 전체 상한 (파일 크기 관리) — 29종목 x 10건 수용
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


def article_url(it):
    """기사 본문 주소. API 가 mobileNewsUrl 을 주지만 없을 때는 oid/aid 로 만든다."""
    u = it.get("mobileNewsUrl") or ""
    if u.startswith("http"):
        return u.split("?")[0]
    oid, aid = it.get("officeId") or "", it.get("articleId") or ""
    return f"https://n.news.naver.com/mnews/article/{oid}/{aid}" if oid and aid else ""


def fetch_stock_news(code):
    url = f"https://api.stock.naver.com/news/stock/{code}?pageSize={PER_STOCK * 2}&page=1"
    raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15).read()
    data = json.loads(raw.decode("utf-8", "replace"))

    out = []
    for blk in (data or []):
        # 묶음 = 같은 사건의 기사 뭉치(total>1). 첫 건이 대표 기사다 — 연관기사까지 담으면
        # 종목당 10건이 한 사건으로 다 차 버린다.
        for it in (blk.get("items") or [])[:1]:
            t = clean(it.get("title") or "")
            u = article_url(it)
            if not t or not u:
                continue
            dt = str(it.get("datetime") or "")          # 202609180701 -> 2026-09-18 07:01
            d = (f"{dt[0:4]}-{dt[4:6]}-{dt[6:8]} {dt[8:10]}:{dt[10:12]}" if len(dt) >= 12 else "")
            out.append({"t": t, "u": u, "s": clean(it.get("officeName") or ""), "d": d})
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
        nap(PAUSE)

    # 몇 종목 빠지는 건 늘 있는 일이고, 절반 넘게 실패하면 '막혔다'로 본다.
    # watchdog.py 가 이 기록을 읽어 별도 알림을 쏜다.
    if records and len(fail) > len(records) * 0.5:
        note_health("네이버 금융(뉴스)", f"{len(fail)}/{len(records)}종목 실패 · {fail[0] if fail else ''}")
    else:
        note_health("네이버 금융(뉴스)", None)

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
