# -*- coding: utf-8 -*-
"""커버 품목 HS 지도 만들기 (일회용).

관세청 API 는 statKor 필드로 공식 품목명을 그대로 준다.
숫자가 맞는지로 부호를 고르다가 두 번 틀렸다(기초 330499, 마스크팩 330790).
품목명을 먼저 봐야 한다. 확인되면 이 파일은 지운다.
"""
import os, sys, urllib.request, urllib.parse, collections
import xml.etree.ElementTree as ET

KEY = os.environ.get("DATA_GO_KR_KEY", "")
API = "https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"

# 6자리를 먼저 훑고, 금액이 큰 6자리는 10자리까지 내려간다
FAMILIES = ["3303", "3304", "3305", "3307", "1902", "3005"]
DRILL_MIN = 20e6      # 6자리 수출액이 이 이상이면 10자리도 본다 (달러)


def call(hs, ym="202606"):
    p = {"serviceKey": KEY, "strtYymm": ym, "endYymm": ym, "hsSgn": hs}
    url = API + "?" + urllib.parse.urlencode(p, safe="")
    try:
        raw = urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
    except Exception as e:
        print(f"  ! {hs} 실패 {str(e)[:60]}"); return {}
    amt, nm = collections.defaultdict(float), {}
    for it in ET.fromstring(raw).iter("item"):
        g = lambda t: (it.findtext(t) or "").strip()
        h = g("hsCd")
        if not h.isdigit():
            continue
        nm.setdefault(h, g("statKor"))
        try:
            amt[h] += float(g("expDlr").replace(",", ""))
        except ValueError:
            pass
    return {h: (amt[h], nm.get(h, "")) for h in amt}


if __name__ == "__main__":
    if not KEY:
        print("KEY 없음"); sys.exit(1)
    for fam in FAMILIES:
        six = call(fam)
        tot = sum(v for v, _ in six.values())
        print(f"\n═══ HS {fam}  (26.06 수출 {tot/1e6:,.1f} 백만달러) ═══")
        for h, (v, n) in sorted(six.items(), key=lambda x: -x[1][0]):
            print(f"  {h:<10} {v/1e6:>8,.1f}  {n}")
            if v >= DRILL_MIN and len(h) == 6:
                for h2, (v2, n2) in sorted(call(h).items(), key=lambda x: -x[1][0]):
                    if v2 > 0:
                        print(f"      {h2:<12} {v2/1e6:>8,.1f}  {n2}")
