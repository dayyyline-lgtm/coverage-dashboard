# -*- coding: utf-8 -*-
"""3307(마스크팩류로 쓰고 있는 항목)의 실제 구성 확인 (일회용).

3307 은 '조제향료·화장품류(따로 분류되지 않은 것)' 라 넓다.
면도용·데오도란트·입욕제·방향제까지 들어간다. 마스크팩만 뽑으려면 하위 부호가 필요하다.
확인되면 이 파일은 지운다.
"""
import os, sys, urllib.request, urllib.parse, collections
import xml.etree.ElementTree as ET

KEY = os.environ.get("DATA_GO_KR_KEY", "")
API = "https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"
NAMES = {
    "330710": "면도용 제품류", "330720": "인체용 탈취제·발한억제제",
    "330730": "목욕용 조제품", "330741": "향(방향제)", "330749": "기타 방향제",
    "330790": "기타 (마스크팩 추정)",
}


def call(hs, ym="202606"):
    p = {"serviceKey": KEY, "strtYymm": ym, "endYymm": ym, "hsSgn": hs}
    url = API + "?" + urllib.parse.urlencode(p, safe="")
    raw = urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
    agg = collections.defaultdict(float)
    for it in ET.fromstring(raw).iter("item"):
        g = lambda t: (it.findtext(t) or "").strip()
        h = g("hsCd")
        if not h.isdigit():
            continue
        try:
            agg[h] += float(g("expDlr").replace(",", ""))
        except ValueError:
            pass
    return agg


if __name__ == "__main__":
    if not KEY:
        print("KEY 없음"); sys.exit(1)
    for hs in ["3307", "330790"]:
        agg = call(hs)
        tot = sum(agg.values())
        print(f"\n[hsSgn={hs}] 합계 {tot/1e6:,.1f} 백만달러 · {len(agg)}개 코드")
        for h, v in sorted(agg.items(), key=lambda x: -x[1]):
            share = v / tot * 100 if tot else 0
            print(f"  {h:<12} {v/1e6:>8,.1f}  ({share:4.1f}%)  {NAMES.get(h,'')}")
