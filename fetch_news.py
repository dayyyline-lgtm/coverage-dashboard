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

PER_STOCK = 5      # 종목당 최대 기사 수
TOTAL_MAX = 160    # 전체 상한 (파일 크기 관리)
PAUSE = 0.25       # 요청 간격 (초)

KST = datetime.timezone(datetime.timedelta(hours=9))


def clean(s):
    """태그 제거 + HTML 엔티티 복원"""
    s = re.sub(r"<[^>]+>", "", s)
    return htmlmod.unescape(s).replace("\xa0", " ").strip()


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
            arts = fetch_stock_news(code)[:PER_STOCK]
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
