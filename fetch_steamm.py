"""SteamCharts 월평균·최고 동접(게임별 출시 이후 전 기간) -> index.html 의  const STEAMM = {...};   (2026-10-24 · 종목별 손익 모델 ISM)

STEAM 블록(fetch_steam.py)은 최근 3개월 일별이라 분기 계수를 맞추기엔 짧다. 앱 페이지의 월별 표(Avg. Players · Peak Players)는
출시부터 다 준다(배그 116개월). 크래프톤 PC = 배그 월평균 동접의 분기 합 × 계수(0.24~0.41) · 시프트업 스텔라블레이드 PC 등.
'Last 30 Days' 줄은 진행 중인 달이라 뺀다.

python fetch_steamm.py
"""
import datetime, html as _html, json, re, urllib.request

from collector_health import ua, nap, note_health

KST = datetime.timezone(datetime.timedelta(hours=9))
HTML = "public/index.html"
APPS = {578080: "배틀그라운드", 3489700: "스텔라블레이드", 3321460: "붉은사막", 582660: "검은사막", 2429640: "쓰론앤리버티"}
MON = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                   "September", "October", "November", "December"], 1)}


def monthly(appid):
    t = urllib.request.urlopen(urllib.request.Request(f"https://steamcharts.com/app/{appid}", headers=ua(doc=True)),
                               timeout=30).read().decode("utf-8", "replace")
    tb = re.search(r'<table class="common-table">(.*?)</table>', t, re.S)
    out = {}
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", tb.group(1) if tb else "", re.S):
        c = [_html.unescape(re.sub(r"<[^>]+>", "", x)).strip() for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
        m = re.match(r"([A-Za-z]+) (\d{4})$", c[0]) if c else None
        if m and m.group(1) in MON and len(c) >= 5:
            try:
                out[f"{m.group(2)}-{MON[m.group(1)]:02d}"] = [round(float(c[1])), round(float(c[4]))]
            except ValueError:
                pass
    return dict(sorted(out.items()))


def main():
    html = open(HTML, encoding="utf-8").read()
    mm = re.search(r"^const STEAMM = (\{.*?\});$", html, re.M | re.S)
    old = json.loads(mm.group(1)) if mm else {"g": {}}
    g, bad = {}, []
    for appid, nm in APPS.items():
        try:
            m = monthly(appid)
        except Exception as e:
            bad.append(f"{nm} {str(e)[:30]}"); m = ((old.get("g") or {}).get(str(appid)) or {}).get("m") or {}
        if m:
            g[str(appid)] = {"t": nm, "m": m}
            print(f"[SteamCharts] {nm:8} {len(m)}개월 · 마지막 {max(m)} {m[max(m)]}")
        nap(1.0)
    note_health("SteamCharts 월별", "; ".join(bad) if len(bad) > 2 else None)
    if mm and old.get("g") == g:
        print("[SteamCharts] 변동 없음"); return
    out = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "g": g,
           "note": "SteamCharts 월별 [평균 동접, 최고 동접] — 진행 중인 달 제외"}
    block = "const STEAMM = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";"
    if mm:
        html = html[:mm.start()] + block + html[mm.end():]
    else:
        a = re.search(r"^const TREND = ", html, re.M)
        html = html[:a.start()] + block + "\n" + html[a.start():]
    open(HTML, "w", encoding="utf-8").write(html)
    print(f"[SteamCharts] STEAMM 블록 갱신 {len(block) // 1024}KB")


if __name__ == "__main__":
    main()
