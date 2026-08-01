# -*- coding: utf-8 -*-
"""관세청 잠정치 API 탐색 (일회용).

화장품 세부품목(기초·색조·마스크팩)을 잠정치로 받을 수 있는 경로가 있는지 확인한다.
- '주요품목별 10일 단위 잠정치' 는 반도체·철강·승용차 등 10개만 준다는 설명이라 화장품이 없을 가능성이 높다.
- 기존 nitemtrade(확정)가 당월을 주는지도 같이 본다.
확인되면 이 파일은 지운다.
"""
import os, sys, urllib.request, urllib.parse
import xml.etree.ElementTree as ET

KEY = os.environ.get("DATA_GO_KR_KEY", "")
UA = {"User-Agent": "Mozilla/5.0"}

CANDIDATES = [
    # (설명, base, 파라미터)
    ("주요품목 잠정(추정1)", "https://apis.data.go.kr/1220000/expitemtrade/getExpitemtradeList", {}),
    ("주요품목 잠정(추정2)", "https://apis.data.go.kr/1220000/ExpItemTradeTemp/getExpItemTradeTempList", {}),
    ("주요국가 잠정(추정1)", "https://apis.data.go.kr/1220000/expctrtrade/getExpctrtradeList", {}),
    ("품목별 수출입실적GW", "https://apis.data.go.kr/1220000/Itemtrade/getItemtradeList",
     {"strtYymm": "202607", "endYymm": "202607", "hsSgn": "3304"}),
    ("품목국가별(현행,확정)", "https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList",
     {"strtYymm": "202607", "endYymm": "202607", "hsSgn": "3304"}),
    ("품목국가별 6월(대조군)", "https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList",
     {"strtYymm": "202606", "endYymm": "202606", "hsSgn": "3304"}),
]


def probe(name, base, extra):
    p = {"serviceKey": KEY}
    p.update(extra)
    url = base + "?" + urllib.parse.urlencode(p, safe="")
    try:
        raw = urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=40).read()
    except Exception as e:
        print(f"  [{name}] 요청 실패: {type(e).__name__} {str(e)[:110]}")
        return
    txt = raw.decode("utf-8", "replace")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        print(f"  [{name}] XML 아님: {txt[:160]}")
        return
    msg = (root.findtext(".//resultMsg") or root.findtext(".//errMsg") or "").strip()
    items = list(root.iter("item"))
    print(f"  [{name}] msg={msg[:60]!r} item={len(items)}")
    if items:
        # 첫 항목의 태그·값을 보여 준다(어떤 필드가 오는지 확인)
        one = items[0]
        print("      " + " · ".join(f"{c.tag}={(c.text or '').strip()[:22]}" for c in one)[:400])
        # 화장품이 잡히는지
        names = {(c.text or "") for it in items for c in it if c.tag.lower().endswith(("nm", "name"))}
        hit = [n for n in names if "화장" in n or "3304" in n]
        print(f"      화장품 관련 항목: {hit[:6] if hit else '없음'} (전체 {len(names)}종)")


if __name__ == "__main__":
    if not KEY:
        print("DATA_GO_KR_KEY 없음"); sys.exit(1)
    for name, base, extra in CANDIDATES:
        probe(name, base, extra)
