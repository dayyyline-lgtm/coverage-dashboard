# -*- coding: utf-8 -*-
"""330790 하위 부호 전수 확인 (일회용).

한 달만 보면 수출 0 인 부호가 안 잡힌다. 여러 달을 훑어 전 부호를 모은다.
'기타(3307909000)' 가 42% 를 차지하는데 그게 무엇인지가 관건 —
330790 을 마스크팩과 동일시해도 되는지가 여기서 갈린다.
확인되면 이 파일은 지운다.
"""
import os, sys, urllib.request, urllib.parse, collections
import xml.etree.ElementTree as ET

KEY = os.environ.get("DATA_GO_KR_KEY", "")
API = "https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"
MONTHS = ["202601", "202602", "202603", "202604", "202605", "202606",
          "202506", "202412", "202306", "202206"]


def call(hs, ym):
    p = {"serviceKey": KEY, "strtYymm": ym, "endYymm": ym, "hsSgn": hs}
    url = API + "?" + urllib.parse.urlencode(p, safe="")
    try:
        raw = urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
    except Exception as e:
        print(f"  ! {ym} 실패 {str(e)[:50]}"); return {}
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
    names, tot = {}, collections.defaultdict(float)
    permonth = {}
    for ym in MONTHS:
        d = call("330790", ym)
        permonth[ym] = d
        for h, (v, n) in d.items():
            names[h] = n
            tot[h] += v
    print("\n=== 330790 하위 부호 (조사한 10개월 합계) ===")
    s = sum(tot.values())
    for h, v in sorted(tot.items(), key=lambda x: -x[1]):
        print(f"  {h}  {v/1e6:>9,.1f}  ({v/s*100:>5.1f}%)  {names[h]}")
    print("\n=== 월별 마스크팩 비중 ===")
    for ym in MONTHS:
        d = permonth[ym]
        m = d.get("3307904000", (0, ""))[0]
        a = sum(v for v, _ in d.values())
        if a:
            print(f"  {ym}  전체 {a/1e6:>7,.1f}  마스크팩 {m/1e6:>7,.1f}  ({m/a*100:>5.1f}%)")
