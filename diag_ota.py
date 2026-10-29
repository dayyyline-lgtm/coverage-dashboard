"""예약 사이트 과거 흔적(일회성 · 2차 — 커먼 크롤만, 2025 가을~2026 초 사본) — 커먼 크롤·웨이백에 남은 KAYAK 계열 호텔 페이지에서 monthlyStayPrice(숙박월별 평균 검색가)를 찾는다.

왜: 2026-10-29 KAYAK 수집은 2026년 1~9월 값만 준다(지난 12개월 검색 평균). 2025년 가을~겨울에 찍힌 사본이 있으면
그 안의 7~9월 값 = 2025년 7~9월 숙박 → 2026년 같은 달과 견줘 '예약 사이트 기준 전년비'가 나온다.
러너에서 돈다(컨테이너는 두 곳에 못 닿는다). 결과는 diag_ota_out/ → diag_ota.yml 이 diag-ota 가지에만 올린다.
"""
import gzip, io, json, os, re, sys, time, urllib.parse, urllib.request

T0 = time.time()
BUDGET = 40 * 60
OUT = "diag_ota_out"
UA = {"User-Agent": "Mozilla/5.0 (research; coverage-dashboard diag)"}

H = {   # KAYAK 정식 주소(2026-10-29 kayak.com 에서 확인)
    "gic": "Seoul-Hotels-Grand-Intercontinental-Seoul-Parnas.82365.ksp",
    "westin": "Seoul-Hotels-The-Westin-Seoul-Parnas.1072878518.ksp",
    "pjeju": "Seogwipo-Hotels-Parnas-Hotel-Jeju.1070436092.ksp",
    "nt_md1": "Seoul-Hotels-Nine-Tree-Hotel-Myeongdong.496105.ksp",
    "nt_md2": "Seoul-Hotels-NINE-TREE-BY-PARNAS-SEOUL-MYEONGDONG-2.2731798.ksp",
    "nt_ins": "Seoul-Hotels-NINE-TREE-BY-PARNAS-SEOUL-INSADONG.5554595.ksp",
    "nt_ddm": "Seoul-Hotels-Nine-Tree-Hotel-Dongdaemun.6019223.ksp",
    "nt_pg": "Seongnam-Hotels-NINE-TREE-BY-PARNAS-SEOUL-PANGYO.7536808.ksp",
    "nt_ys": "Seoul-Hotels-Nine-Tree-Premier-Rokaus-Hotel-Seoul-Yongsan.1070670581.ksp",
    "shilla_seoul": "Seoul-Hotels-The-Shilla-Seoul.76540.ksp",
    "shilla_jeju": "Seogwipo-Hotels-The-Shilla-Jeju.86274.ksp",
    "gm_ys": "Seoul-Hotels-Grand-Mercure-Ambassador-Hotel-and-Residences-Seoul-Yongsan.2992812.ksp",
    "ns_ys": "Seoul-Hotels-Novotel-Suites-Ambassador-Seoul-Yongsan.2992813.ksp",
    "nv_ys": "Seoul-Hotels-Novotel-Ambassador-Seoul-Yongsan.2991340.ksp",
    "is_ys": "Seoul-Hotels-ibis-Styles-Ambassador-Seoul-Yongsan.2991349.ksp",
    "stay_ghm": "Seoul-Hotels-Shilla-Stay-Gwanghwamun.2450802.ksp",
    "stay_mapo": "Seoul-Hotels-Shilla-Stay-Mapo.2330447.ksp",
    "stay_jeju": "Jeju-City-Hotels-Shilla-Stay-Jeju.2259231.ksp",
    "stay_iho": "Jeju-City-Hotels-Shilla-Stay-Plus-IhoTewoo-Ocean-Front.10357751.ksp",
    "stay_dongtan": "Hwaseong-Hotels-Shilla-Stay-Dongtan.728662.ksp",
    "stay_yeoksam": "Seoul-Hotels-Shilla-Stay-Yeoksam.2154992.ksp",
    "stay_sdm": "Seoul-Hotels-Shilla-Stay-Seodaemun.806452.ksp",
    "stay_guro": "Seoul-Hotels-Shilla-Stay-Guro.2450800.ksp",
    "stay_hud": "Busan-Hotels-Shilla-Stay-Haeundae.2757890.ksp",
    "stay_seocho": "Seoul-Hotels-Shilla-Stay-Seocho.2757891.ksp",
    "stay_samsung": "Seoul-Hotels-Shilla-Stay-Samsung.6080159.ksp",
}
ID2K = {re.search(r"\.(\d+)\.ksp$", p).group(1): k for k, p in H.items()}
CITIES = sorted({p.split("-Hotels-")[0] for p in H.values()})
DOMAINS = ["www.kayak.com", "www.kayak.co.kr", "www.kayak.co.uk", "ca.kayak.com", "www.kayak.co.jp", "www.kayak.de",
           "www.kayak.fr", "www.kayak.com.au", "www.kayak.sg", "www.kayak.com.hk", "www.momondo.com", "www.kayak.ie",
           "www.kayak.es", "www.kayak.it", "www.kayak.nl", "www.kayak.ch", "www.kayak.co.in", "www.kayak.com.my"]


def left():
    return BUDGET - (time.time() - T0)


def get(u, t=60, tries=4, hdr=None, raw=False):
    last = None
    for i in range(tries):
        try:
            rq = urllib.request.Request(u, headers={**UA, **(hdr or {})})
            with urllib.request.urlopen(rq, timeout=t) as r:
                b = r.read()
                return (r.status, b) if raw else (r.status, b.decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, b"" if raw else ""
            last = e
            time.sleep(4 * (i + 1) + (10 if e.code in (429, 503) else 0))
        except Exception as e:
            last = e
            time.sleep(4 * (i + 1))
    raise last


MSP = re.compile(r'"monthlyStayPrice"\s*:\s*\{[^{}]*?"values"\s*:\s*\[([^\]]*)\]')
WSP = re.compile(r'"weeklyStayPrice"\s*:\s*\{[^{}]*?"values"\s*:\s*\[([^\]]*)\]')
CUR = re.compile(r'"(?:currencyCode|currency)"\s*:\s*"([A-Z]{3})"')


def extract(html):
    m = MSP.search(html)
    w = WSP.search(html)
    cur = None
    if m:
        # 통화: 값 근처의 currency 키 → 없으면 페이지 첫 currency
        seg = html[max(0, m.start() - 3000): m.end() + 3000]
        c = CUR.search(seg) or CUR.search(html)
        cur = c.group(1) if c else None
    return {
        "m": [float(x) for x in m.group(1).split(",") if x.strip()] if m else None,
        "w": [float(x) for x in w.group(1).split(",") if x.strip()] if w else None,
        "cur": cur,
        "len": len(html),
        "title": (re.search(r"<title[^>]*>(.*?)</title>", html, re.S) or [None, ""])[1][:120].strip() if html else "",
        "has_msp_word": "monthlyStayPrice" in html,
    }


def wayback(results):
    """웨이백 CDX — 호텔·도메인마다 접두어 질의(쿼리 문자열 변형까지)."""
    caps = []
    for dom in DOMAINS:
        for k, p in H.items():
            if left() < 60 * 18:
                print("[wb] 시간 예산 — CDX 중단", flush=True); return caps
            u = ("https://web.archive.org/cdx/search/cdx?url=" + urllib.parse.quote(f"{dom}/{p}", safe="/")
                 + "&matchType=prefix&from=2024&output=json&fl=timestamp,original,statuscode,length&limit=200")
            try:
                st, t = get(u, 60, 3)
            except Exception as e:
                print(f"[wb] {dom} {k} CDX 실패 {e}", flush=True); time.sleep(3); continue
            if st != 200 or not t.strip():
                continue
            try:
                rows = json.loads(t)[1:]
            except Exception:
                continue
            for ts, orig, sc, ln in rows:
                caps.append({"src": "wb", "k": k, "dom": dom, "ts": ts, "url": orig, "sc": sc, "len": ln})
            if rows:
                print(f"[wb] {dom} {k} 사본 {len(rows)}개 ({rows[0][0][:8]}~{rows[-1][0][:8]})", flush=True)
            time.sleep(0.8)
    return caps


WANT = ["CC-MAIN-2025-47", "CC-MAIN-2025-43", "CC-MAIN-2025-51", "CC-MAIN-2026-04", "CC-MAIN-2026-08",
        "CC-MAIN-2025-38", "CC-MAIN-2026-12", "CC-MAIN-2025-33", "CC-MAIN-2026-17", "CC-MAIN-2026-21"]
CC_DOMS = ["www.kayak.com", "www.momondo.com", "www.kayak.co.kr", "www.kayak.co.uk", "ca.kayak.com"]
DOM_CUR = {"www.kayak.com": "USD", "www.momondo.com": "USD", "www.kayak.co.kr": "KRW", "www.kayak.co.uk": "GBP", "ca.kayak.com": "CAD"}


def cc_collections():
    st, t = get("https://index.commoncrawl.org/collinfo.json", 60)
    have = {c["id"]: c for c in json.loads(t)}
    return [have[i] for i in WANT if i in have]


def commoncrawl(results):
    caps = []
    try:
        cols = cc_collections()
    except Exception as e:
        print("[cc] 목록 실패", e); return caps
    print("[cc] 컬렉션", [c["id"] for c in cols], flush=True)
    for dom in CC_DOMS:
        for c in cols:
            for city in CITIES:
                if left() < 60 * 3:
                    print("[cc] 시간 예산 — 색인 중단", flush=True); return caps
                u = (f"{c['cdx-api']}?url=" + urllib.parse.quote(f"{dom}/{city}-Hotels-", safe="/")
                     + "&matchType=prefix&output=json&limit=20000")
                t = None
                for i in range(5):
                    try:
                        st, t = get(u, 120, 1)
                        break
                    except Exception as e:
                        print(f"[cc] {c['id']} {dom} {city} 재시도 {i+1} {str(e)[:60]}", flush=True); time.sleep(8 + 8 * i)
                if t is None:
                    continue
                n = 0
                for line in t.splitlines():
                    if not line.startswith("{"):
                        continue
                    try:
                        r = json.loads(line)
                    except Exception:
                        continue
                    m = re.search(r"\.(\d+)\.ksp", r.get("url", ""))
                    if m and m.group(1) in ID2K and str(r.get("status")) == "200":
                        cap = {"src": "cc", "col": c["id"], "k": ID2K[m.group(1)], "dom": dom, "ts": r.get("timestamp"),
                               "url": r.get("url"), "sc": r.get("status"), "fn": r.get("filename"),
                               "off": int(r.get("offset", 0)), "ln": int(r.get("length", 0))}
                        try:
                            x = extract(fetch_cc(cap))
                        except Exception as e:
                            x = {"err": f"{type(e).__name__} {str(e)[:80]}"}
                        cap.update({"m": x.get("m"), "cur": DOM_CUR.get(dom), "title": x.get("title"), "err": x.get("err")})
                        caps.append(cap)
                        print(f"   {c['id']} {cap['ts'][:8]} {dom} {cap['k']} → {cap['m'] if cap['m'] else ('없음 ' + str(cap.get('title') or cap.get('err'))[:60])}", flush=True)
                        json.dump(caps, open(f"{OUT}/cc_pages.json", "w"), ensure_ascii=False, indent=0)
                        n += 1
                if n:
                    print(f"[cc] {c['id']} {dom} {city} 우리 호텔 {n}개", flush=True)
                time.sleep(1.2)
    return caps


def fetch_cc(cap):
    st, b = get(f"https://data.commoncrawl.org/{cap['fn']}", 90, 3,
                hdr={"Range": f"bytes={cap['off']}-{cap['off'] + cap['ln'] - 1}"}, raw=True)
    rec = gzip.GzipFile(fileobj=io.BytesIO(b)).read()
    # WARC 헤더 → HTTP 헤더 → 본문
    parts = rec.split(b"\r\n\r\n", 2)
    body = parts[2] if len(parts) > 2 else rec
    return body.decode("utf-8", "replace")


def fetch_wb(cap):
    st, t = get(f"https://web.archive.org/web/{cap['ts']}id_/{cap['url']}", 90, 3)
    return t


def main():
    os.makedirs(OUT, exist_ok=True)
    caps = commoncrawl([])
    json.dump(caps, open(f"{OUT}/cc_pages.json", "w"), ensure_ascii=False, indent=0)
    print(f"끝 · 커먼 크롤 사본 {len(caps)}개 · 월별 값 있는 것 {sum(1 for c in caps if c.get('m'))}개", flush=True)
    return
    print(f"사본 후보 {len(caps)}개", flush=True)
    # 2025-06 ~ 2026-10 사본만 본다(호텔·도메인·달마다 하나씩 — 같은 달 여러 개면 맨 뒤)
    pick = {}
    for c in caps:
        if not c.get("ts") or c["ts"][:6] < "202506":
            continue
        if str(c.get("sc")) not in ("200", "-"):
            continue
        key = (c["k"], c["dom"], c["ts"][:6], c["src"])
        if key not in pick or c["ts"] > pick[key]["ts"]:
            pick[key] = c
    sel = sorted(pick.values(), key=lambda c: (c["ts"][:6] >= "202509" and c["ts"][:6] <= "202602", c["ts"]), reverse=True)
    print(f"받을 사본 {len(sel)}개", flush=True)
    res = []
    for c in sel:
        if left() < 90:
            print("시간 예산 — 본문 받기 중단", flush=True); break
        try:
            html = fetch_cc(c) if c["src"] == "cc" else fetch_wb(c)
            x = extract(html)
        except Exception as e:
            x = {"err": f"{type(e).__name__} {str(e)[:120]}"}
        r = {**{k: c[k] for k in ("src", "k", "dom", "ts", "url")}, **x}
        res.append(r)
        print(f"  {c['src']} {c['ts'][:8]} {c['dom']} {c['k']} → "
              f"{'월별 ' + str(x.get('m'))[:90] + ' ' + str(x.get('cur')) if x.get('m') else ('없음 ' + str(x.get('title') or x.get('err'))[:80])}",
              flush=True)
        json.dump(res, open(f"{OUT}/pages.json", "w"), ensure_ascii=False, indent=0)
        time.sleep(1.0)
    json.dump(res, open(f"{OUT}/pages.json", "w"), ensure_ascii=False, indent=0)
    print(f"끝 · 월별 값 있는 사본 {sum(1 for r in res if r.get('m'))}개 / {len(res)}개", flush=True)


if __name__ == "__main__":
    main()
