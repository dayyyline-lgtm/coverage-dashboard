# -*- coding: utf-8 -*-
"""330790 하위 10자리 부호의 실제 품목명 확인 (일회용).

마스크팩이 330790 전체인지 3307904000 하나인지 가른다.
API 응답에 품목명 필드가 있는지부터 본다. 확인되면 이 파일은 지운다.
"""
import os, sys, urllib.request, urllib.parse, collections
import xml.etree.ElementTree as ET

KEY = os.environ.get("DATA_GO_KR_KEY", "")


def dump(api, params, label):
    url = api + "?" + urllib.parse.urlencode(params, safe="")
    try:
        raw = urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
    except Exception as e:
        print(f"[{label}] 실패 {type(e).__name__} {str(e)[:80]}"); return
    root = ET.fromstring(raw)
    items = list(root.iter("item"))
    print(f"\n[{label}] {len(items)}건")
    if not items:
        print("   ", (root.findtext('.//resultMsg') or '')[:80]); return
    print("    필드:", [c.tag for c in items[0]])
    seen = {}
    for it in items:
        g = lambda t: (it.findtext(t) or "").strip()
        h = g("hsCd")
        if h and h not in seen:
            seen[h] = {c.tag: (c.text or "").strip()[:40] for c in it
                       if c.tag not in ("expDlr", "expWgt", "impDlr", "impWgt", "balPayments")}
    for h, v in sorted(seen.items()):
        print(f"    {h}: {v}")


if __name__ == "__main__":
    if not KEY:
        print("KEY 없음"); sys.exit(1)
    # 1) 품목국가별(현행 사용) — 품목명 필드가 있나
    dump("https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList",
         {"serviceKey": KEY, "strtYymm": "202606", "endYymm": "202606", "hsSgn": "330790"},
         "nitemtrade 330790")
    # 2) 품목별(국가 없음) — 이쪽은 품목명을 준다고 알려져 있다
    dump("https://apis.data.go.kr/1220000/Itemtrade/getItemtradeList",
         {"serviceKey": KEY, "strtYymm": "202606", "endYymm": "202606", "hsSgn": "330790"},
         "Itemtrade 330790")
