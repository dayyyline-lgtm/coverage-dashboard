# -*- coding: utf-8 -*-
"""국내 H&B 채널 판매 랭킹 — 올리브영 베스트 100 (2026-09-08 신설 → `BEAUTY`).

왜 필요했나
  화장품이 커버리지에서 가장 큰 섹터(8종목)인데 **국내 채널 지표가 하나도 없었다.**
  갖고 있던 건 전부 해외뿐이다 — 관세청 수출(`TRADE`), 아마존(`AMAZON`), 러시아·일본 쇼핑(`SHOP`).
  올리브영은 국내 H&B 1위 채널이고 베스트 100 이 실판매 기반이라, '지금 국내에서 뭐가 팔리나'를
  가장 직접적으로 보여 준다.

  ⚠ 처음엔 403 이었다. `ua(doc=True)`(Accept: text/html + Sec-Fetch-* + sec-ch-ua)로 바꾸니
    200·373KB 가 그대로 왔다. 기본 헤더는 `Accept: application/json` 이라 XHR 처럼 보이는데,
    사람이 주소창에 쳐서는 절대 안 나오는 조합이라 WAF 가 그걸로 가른다.

```
/store/main/getBestList.do    베스트 100 (판매순) · SSR HTML · 브랜드 + 상품명, 순서가 곧 순위
```

무엇을 지표로 삼나 — **브랜드 노출 수와 최고 순위**다. 개별 상품 순위는 기획전·증정 때문에
하루 단위로 크게 흔들리지만, "그 브랜드가 100 위 안에 몇 개 올려 두고 있나"는 훨씬 안정적이다.

  ① `brands[]` — 커버리지 종목으로 **직접 매칭되는 브랜드**만. 자회사·판권까지 확인된 것만 넣는다.
  ② `indie`   — 대형사 브랜드가 **아닌** 것의 비중. 실리콘투(유통)·한국콜마/코스맥스(ODM)는
     자기 브랜드가 없어 직접 매칭이 원리적으로 불가능하다. 인디 비중이 그들의 대리지표다.
     ⚠ **대리지표라고 화면에 반드시 적을 것.** 인디 브랜드가 전부 그들의 고객인 건 아니다.
  ③ `top[]`   — 오늘 상위 20 스냅샷. '지금 뭐가 팔리나'를 눈으로 보는 용도.

안 넣은 것 — 화해(hwahae.co.kr) 랭킹
  `__NEXT_DATA__` 로 깔끔하게 열리고 `rank_delta` 까지 준다. 그런데 기본 랭킹이 '급상승'이고
  `is_advertised: true` 다. 실제로 2026-09-08 1위가 리뷰 52건짜리 무명 브랜드였다 —
  판매 신호가 아니라 광고 노출로 보인다. **판매 지표로 쓸 수 없어 뺐다.**
  나중에 넣으려면 '카테고리별'(ranking_type RANKING) 쪽을 봐야 한다.

  python fetch_beauty.py            # 수집·기록
  python fetch_beauty.py --dry-run  # 출력만
"""
import re, json, sys, html as htmlmod, copy, datetime, urllib.request
from collector_health import ua, note_health

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
DAYS = 400
TOP_N = 20
OY = "https://www.oliveyoung.co.kr/store/main/getBestList.do"

# 브랜드 → 커버리지 종목. **소유·판권이 확인된 것만.** 짐작으로 넣지 말 것.
#  ⚠ 비디비치는 신세계인터내셔날(아모레 아님) · 홀리카홀리카는 엔프라니 · 롬앤은 아이패밀리에스씨 ·
#    클리오/페리페라/구달은 클리오 — 전부 커버리지 밖이라 안 넣는다. 넣으면 조용히 틀린 숫자가 된다.
BRAND_STOCK = {
    "에이피알":   ["메디큐브", "에이프릴스킨", "포맨트", "널디", "글램디"],
    "달바글로벌": ["달바"],
    "아모레퍼시픽": ["라네즈", "이니스프리", "헤라", "에스트라", "마몽드", "아이오페", "한율",
                 "려", "미쟝센", "프리메라", "일리윤", "에뛰드", "해피바스", "비레디", "롱테이크"],
    "LG생활건강": ["더페이스샵", "CNP", "빌리프", "숨37", "오휘", "이자녹스", "닥터그루트",
                "피지오겔", "유시몰", "케어존", "프레시안", "비욘드", "글린트", "티엔"],
}
STOCK_OF = {b: s for s, bs in BRAND_STOCK.items() for b in bs}
# 인디 비중을 재려면 '대형사'의 정의가 필요하다. 커버리지 대형사 + 비커버리지 대형사를 같이 넣는다
# — 안 그러면 아모레·LG만 빠지고 나머지 대기업 브랜드가 전부 '인디'로 세어져 비중이 부풀려진다.
BIG_OTHER = ["메디힐", "라로슈포제", "비쉬", "세타필", "아벤느", "유리아쥬", "닥터지", "제로이드",
             "디오디너리", "뉴트로지나", "아이소이", "홀리카홀리카", "클리오", "페리페라", "구달",
             "쉬크", "질레트", "도브", "케라시스", "미쟝센", "엘라스틴", "려", "댕기머리", "리엔",
             "비디비치", "연작", "설화수", "헤라", "오휘", "숨37", "이자녹스", "정관장", "센카"]


def _get(url, ref=None):
    req = urllib.request.Request(url, headers=ua(referer=ref, doc=True))
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


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
        raise RuntimeError("BEAUTY 삽입 기준(const LIVE)을 못 찾음")
    return html_[:liv.end()] + "\n" + block + html_[liv.end():]


def fetch_oy():
    """[(순위, 브랜드, 상품명), ...] — 목록 순서가 곧 판매순위다."""
    t = _get(OY, "https://www.oliveyoung.co.kr/")
    brands = [htmlmod.unescape(x).strip() for x in re.findall(r'class="tx_brand"[^>]*>([^<]+)<', t)]
    names = [htmlmod.unescape(x).strip() for x in re.findall(r'class="tx_name"[^>]*>([^<]+)<', t)]
    if len(brands) < 50 or len(brands) != len(names):
        raise RuntimeError(f"파싱 실패 — 브랜드 {len(brands)} · 상품 {len(names)} (마크업 변경?)")
    return [(i + 1, b, n) for i, (b, n) in enumerate(zip(brands, names))]


def _same(a, b):
    return json.dumps(a, ensure_ascii=False, sort_keys=True) == json.dumps(b, ensure_ascii=False, sort_keys=True)


def main():
    html_ = open(HTML, encoding="utf-8").read()
    now = datetime.datetime.now(KST)
    today = now.date().isoformat()
    prev = _const(html_, "BEAUTY") or {}
    old = copy.deepcopy(prev)          # ⚠ 얕은 참조로 prev 를 고치면 '변동 없음' 이 자기 비교가 된다

    try:
        rows = fetch_oy()
    except Exception as e:
        note_health("올리브영", f"{type(e).__name__} {str(e)[:80]}")
        print("[올리브영] 실패:", e); sys.exit(1)
    note_health("올리브영", None)

    oy = old.get("oy") or {"src": "올리브영 베스트", "brands": [], "indie": {"hist": []}}
    oy["d"], oy["n"] = today, len(rows)
    oy["top"] = [{"r": r, "b": b, "p": p} for r, b, p in rows[:TOP_N]]

    # ① 커버리지 브랜드 — 노출 수(c)와 최고 순위(b)
    per = {}
    for r, b, _ in rows:
        st = STOCK_OF.get(b)
        if not st:
            continue
        d = per.setdefault(b, {"stock": st, "c": 0, "b": r})
        d["c"] += 1
        d["b"] = min(d["b"], r)
    tracked = {g["brand"]: g for g in (oy.get("brands") or [])}
    for b in per:
        tracked.setdefault(b, {"brand": b, "stock": per[b]["stock"], "hist": []})
    for b, g in tracked.items():
        cur = per.get(b)
        hist = [h for h in g.get("hist", []) if h.get("d") != today]
        hist.append({"d": today, "c": cur["c"] if cur else 0, "b": cur["b"] if cur else None})
        g["hist"] = hist[-DAYS:]
    oy["brands"] = sorted(tracked.values(), key=lambda g: (g["stock"], g["brand"]))

    # ② 인디 비중 — 대형사가 아닌 브랜드의 상품 수. 실리콘투·콜마·코스맥스의 **대리지표**다.
    big = set(BIG_OTHER) | set(STOCK_OF)
    indie = [b for _, b, _ in rows if b not in big]
    ih = [h for h in (oy.get("indie") or {}).get("hist", []) if h.get("d") != today]
    ih.append({"d": today, "c": len(indie), "u": len(set(indie)), "n": len(rows)})
    oy["indie"] = {"hist": ih[-DAYS:]}

    hit = " · ".join(f"{b} {v['c']}개(최고 {v['b']}위)" for b, v in sorted(per.items(), key=lambda x: x[1]["b"]))
    print(f"[올리브영] 베스트 {len(rows)}개 · 1위 {rows[0][1]} {rows[0][2][:24]}")
    print(f"  커버리지: {hit or '없음'}")
    print(f"  인디(대형사 제외) {len(indie)}개 / {len(rows)} = {len(indie)/len(rows)*100:.0f}%")

    out = {"asOf": now.strftime("%Y-%m-%d %H:%M KST"), "oy": oy}
    if "--dry-run" in sys.argv:
        print(json.dumps(out, ensure_ascii=False)[:1200]); return
    if prev and _same(prev.get("oy", {}).get("brands"), out["oy"].get("brands")) \
            and _same(prev.get("oy", {}).get("indie"), out["oy"].get("indie")) \
            and _same(prev.get("oy", {}).get("top"), out["oy"].get("top")):
        print("[올리브영] 변동 없음 — 건너뜀"); return
    open(HTML, "w", encoding="utf-8").write(_put(html_, "BEAUTY", out))
    print(f"[OK] BEAUTY 갱신 · 추적 브랜드 {len(oy['brands'])}개")


if __name__ == "__main__":
    main()
