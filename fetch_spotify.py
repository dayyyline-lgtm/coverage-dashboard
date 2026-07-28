# -*- coding: utf-8 -*-
"""
Spotify 아티스트 지표 수집 — 엔터(하이브) 글로벌 음악 수요 신호.

공식 Web API. SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET 필요(없으면 스킵).
  - 토큰: client_credentials (Basic auth)
  - 아티스트: search → id, artists/{id} → followers.total, popularity(0~100)

⚠️ '월간 청취자'는 공식 API 에 없다. 대신:
  - popularity(0~100): 최근 스트리밍을 반영하는 알고리즘 점수 → 실시간 인기 신호(핵심)
  - followers: 팔로워(천천히 증가)
과거 시계열 무료 소스가 없어 매일 1점씩 누적한다.

  python fetch_spotify.py            # 수집·기록
  python fetch_spotify.py --dry-run  # 출력만
"""
import os, re, json, sys, base64, datetime, urllib.request, urllib.parse

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
DAYS = 180
CID = os.environ.get("SPOTIFY_CLIENT_ID", "")
CSEC = os.environ.get("SPOTIFY_CLIENT_SECRET", "")

# (종목, 라벨, 검색어) — 하이브 주요 아티스트. 찾은 아티스트ID(aid)는 데이터에 캐시.
ARTISTS = [
    ("하이브", "BTS",     "BTS"),
    ("하이브", "세븐틴",   "SEVENTEEN"),
    ("하이브", "르세라핌", "LE SSERAFIM"),
    ("하이브", "엔하이픈", "ENHYPEN"),
    ("하이브", "투바투",   "TOMORROW X TOGETHER"),
]


def available():
    return bool(CID and CSEC)


def _token():
    auth = base64.b64encode(f"{CID}:{CSEC}".encode()).decode()
    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    req = urllib.request.Request("https://accounts.spotify.com/api/token", data=data,
                                 headers={"Authorization": "Basic " + auth,
                                          "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))["access_token"]


def _get(url, tok):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def _artist_id(name, tok):
    d = _get("https://api.spotify.com/v1/search?"
             + urllib.parse.urlencode({"q": name, "type": "artist", "limit": 1}), tok)
    its = ((d.get("artists") or {}).get("items")) or []
    return its[0]["id"] if its else None


def _artist(aid, tok):
    d = _get(f"https://api.spotify.com/v1/artists/{aid}", tok)
    return int((d.get("followers") or {}).get("total") or 0), int(d.get("popularity") or 0)


def _const(html, name):
    m = re.search(r"const %s\s*=\s*(\{.*?\});" % re.escape(name), html, re.S)
    return json.loads(m.group(1)) if m else None


def _put(html, name, obj):
    block = "const %s = %s;" % (name, json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
    pat = re.compile(r"const %s\s*=\s*\{.*?\};" % re.escape(name), re.S)
    if pat.search(html):
        return pat.sub(lambda m: block, html, count=1)
    liv = re.search(r"const LIVE\s*=\s*\{.*?\};", html, re.S)
    if not liv:
        raise RuntimeError("SPOTIFY 삽입 기준(const LIVE)을 못 찾음")
    return html[:liv.end()] + "\n" + block + html[liv.end():]


def main():
    if not available():
        print("[spotify] 크레덴셜 없음 — 스킵"); return
    html = open(HTML, encoding="utf-8").read()
    today = datetime.datetime.now(KST).date().isoformat()
    prev = {(a["stock"], a["label"]): a
            for a in (_const(html, "SPOTIFY") or {}).get("artists", [])}
    try:
        tok = _token()
    except Exception as e:
        print(f"[spotify] 토큰 실패: {str(e)[:100]}"); return

    arts = []
    for stock, label, query in ARTISTS:
        old = prev.get((stock, label), {})
        aid = old.get("aid")
        hist = list(old.get("hist") or [])
        try:
            if not aid:
                aid = _artist_id(query, tok)
            if aid:
                fol, pop = _artist(aid, tok)
                pt = {"d": today, "fol": fol, "pop": pop}
                if hist and hist[-1].get("d") == today:
                    hist[-1] = pt
                else:
                    hist.append(pt)
                hist = hist[-DAYS:]
                print(f"  {label}: 팔로워 {fol:,} · 인기도 {pop}")
            else:
                print(f"  [{label}] 아티스트 못 찾음(query={query})")
        except Exception as e:
            print(f"  [{label}] 실패: {str(e)[:100]}")
        arts.append({"stock": stock, "label": label, "aid": aid, "hist": hist})

    sp = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "artists": arts}
    if "--dry-run" in sys.argv:
        print(json.dumps(sp, ensure_ascii=False, indent=1)[:700]); return
    open(HTML, "w", encoding="utf-8").write(_put(html, "SPOTIFY", sp))
    print(f"[OK] SPOTIFY 갱신 · {len(arts)}팀")


if __name__ == "__main__":
    main()
