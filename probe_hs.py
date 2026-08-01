# -*- coding: utf-8 -*-
"""관세청 nitemtrade 가 HS 몇 자리를 주는지 확인 (일회용).

'기초화장품 / 기타 화장품류' 구분은 330499 를 HS 10단위로 쪼개야 나온다.
우리 API 가 10단위를 준다면 증권사 표와 같은 기준으로 맞출 수 있다.
확인되면 이 파일은 지운다.
"""
import os, sys, urllib.request, urllib.parse, collections
import xml.etree.ElementTree as ET

KEY = os.environ.get("DATA_GO_KR_KEY", "")
API = "https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"


def call(hs, ym="202606"):
    p = {"serviceKey": KEY, "strtYymm": ym, "endYymm": ym, "hsSgn": hs}
    url = API + "?" + urllib.parse.urlencode(p, safe="")
    raw = urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
    root = ET.fromstring(raw)
    out = []
    for it in root.iter("item"):
        g = lambda t: (it.findtext(t) or "").strip()
        hs_, cd, amt = g("hsCd"), g("statCd"), g("expDlr")
        if hs_.isdigit():
            out.append((hs_, cd, amt))
    return out


if __name__ == "__main__":
    if not KEY:
        print("KEY 없음"); sys.exit(1)
    for hs in ["3304", "330499"]:
        rows = call(hs)
        lens = collections.Counter(len(h) for h, _, _ in rows)
        codes = sorted({h for h, _, _ in rows})
        print(f"\n[hsSgn={hs}] {len(rows)}행 · 자릿수분포 {dict(lens)}")
        print(f"  코드 {len(codes)}종: {codes[:14]}")
        # 330499 하위가 쪼개져 있으면 코드별 합계를 보여 준다
        agg = collections.defaultdict(float)
        for h, cd, amt in rows:
            try:
                agg[h] += float(amt.replace(",", ""))
            except ValueError:
                pass
        top = sorted(agg.items(), key=lambda x: -x[1])[:10]
        for h, v in top:
            print(f"    {h}  {v/1e6:,.1f} 백만달러")
