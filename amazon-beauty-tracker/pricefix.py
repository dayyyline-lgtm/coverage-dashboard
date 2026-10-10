"""트래커 가격 보정 — 상세 페이지(dp)에서 읽은 '남의 가격'을 같은 상품의 카드 가격으로 바꾼다.

원인(2026-10-11 실측): 상세 페이지의 가격 칸이 빈 상품(품절 · '모든 구매 옵션 보기' 등)에서
scraper.parse_detail 이 페이지 전체의 첫 .a-price 로 내려갔는데, 그건 '비슷한 상품' 캐러셀의
남의 가격이었다. 캐러셀은 소수점 칸을 비운 채 보내는 일이 많아 $17.99 가 1799.0 으로 찍혔다
(B0BFQ9RD5B: 가격 칸 비어 있음 → 첫 .a-price = sims 캐러셀 '$1799'). 소수점이 붙어 와서
숫자만으론 티가 안 나는 남의 가격도 섞인다(같은 상품이 $9.99 · $79.00 · $34.39 로 오락가락).

그래서 견줄 기준은 **카드 가격**(src=list·search — 그 카드에 붙은 그 상품의 가격)이다.
dp 가격이 30일 안의 카드 가격과 2.5배 넘게 다르면 카드 가격으로 바꾼다. 카드 가격이 없으면
소수점 빠진 1,000 이상(= $10 이상)만 버리고 나머지는 그대로 둔다 — 진짜 $249.00 기기와 가를 근거가 없다.

scraper.py 는 고쳤지만(2026-10-11 · 가격 칸 밖으로 안 내려간다) 이 PC 클론을 맞추기 전까지 새 행에도
섞이고, history.csv 의 지난 행은 그대로라 읽는 쪽(inject_amazon · subcat/model)에서 거른다.
"""

import bisect
import datetime

INT_CUR = ("USD", "EUR", "GBP")   # 소수점 빠짐을 볼 통화 — 엔화는 원래 정수
RATIO = 2.5                       # 카드 가격과 이만큼 넘게 다르면 남의 가격
WINDOW = 30                       # 카드 가격을 찾는 범위(일)
DROP_AT = 1000                    # 카드 가격이 없을 때: 소수점 없는 1,000 이상은 버린다


def _f(x):
    try:
        v = float(x)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def _day(s):
    try:
        return datetime.date.fromisoformat((s or "")[:10]).toordinal()
    except ValueError:
        return 0


def repair(rows):
    """history.csv 행(dict) 목록 → 같은 순서의 가격 목록(float|None). dp 행만 손댄다."""
    prices = [_f(r.get("price")) for r in rows]
    ref = {}
    for r, p in zip(rows, prices):
        if p is not None and (r.get("src") or "") in ("list", "search"):
            ref.setdefault((r.get("market"), r.get("asin")), []).append((_day(r.get("date")), p))
    for v in ref.values():
        v.sort()
    out = []
    for r, p in zip(rows, prices):
        if p is None or (r.get("src") or "") != "dp":
            out.append(p)
            continue
        q = None
        seq = ref.get((r.get("market"), r.get("asin")))
        if seq:
            d = _day(r.get("date"))
            i = bisect.bisect_left(seq, (d, -1.0))
            cand = [seq[j] for j in (i - 1, i) if 0 <= j < len(seq) and abs(seq[j][0] - d) <= WINDOW]
            if cand:
                q = min(cand, key=lambda x: abs(x[0] - d))[1]
        if q is not None:
            out.append(q if (p / q > RATIO or q / p > RATIO) else p)
        elif r.get("currency") in INT_CUR and p >= DROP_AT and abs(p - round(p)) < 1e-9:
            out.append(None)
        else:
            out.append(p)
    return out
