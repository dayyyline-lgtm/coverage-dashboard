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

# (종목, 라벨, 검색어, 고정aid) — 하이브 주요 아티스트.
# 고정aid 를 주면 검색을 건너뛴다. 신인·동명이인은 search 가 엉뚱한 아티스트를 잡을 수
# 있어(예: 'CORTIS' 로 다른 밴드가 걸림) 검증한 ID 를 박아 둔다. None 이면 검색으로 찾는다.
# 찾은 aid 는 데이터에 캐시되어 다음 실행부터 재사용된다.
ARTISTS = [
    ("하이브", "BTS",     "BTS",                 None),
    ("하이브", "세븐틴",   "SEVENTEEN",           None),
    ("하이브", "르세라핌", "LE SSERAFIM",         None),
    ("하이브", "엔하이픈", "ENHYPEN",             None),
    ("하이브", "투바투",   "TOMORROW X TOGETHER", None),
    ("하이브", "캣츠아이", "KATSEYE",             "3c0gDdb9lhnHGFtP4prQpn"),
    ("하이브", "코르티스", "CORTIS",              "1ebt9HnXdyYA6KgLXr1n4P"),
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
    # UA 없이 보내면 러너 IP 에서 403 이 나는 사례가 있어 브라우저 UA 를 붙인다.
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok,
                                               "User-Agent": "Mozilla/5.0"})
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


def _top_track(aid, tok):
    """대표곡(현재 가장 인기 트랙) 이름·인기도 — 컴백 신곡이 뜨면 여기 반영된다."""
    d = _get(f"https://api.spotify.com/v1/artists/{aid}/top-tracks?market=KR", tok)
    ts = d.get("tracks") or []
    return (ts[0].get("name", "")[:30], int(ts[0].get("popularity") or 0)) if ts else (None, None)


def _latest_release(aid, tok):
    """최근 발매작(앨범·싱글) 이름·발매일 — 컴백/발매 시점 감지."""
    d = _get(f"https://api.spotify.com/v1/artists/{aid}/albums"
             "?include_groups=single,album&market=KR&limit=20", tok)
    its = d.get("items") or []
    if not its:
        return None, None
    its.sort(key=lambda x: x.get("release_date", ""), reverse=True)
    return its[0].get("name", "")[:30], its[0].get("release_date", "")


def _kworb_listeners():
    """kworb.net Spotify '월간 청취자' 랭킹 → {aid: (listeners, dailyDelta)}.
       행의 링크 href 에 Spotify 아티스트ID 가 그대로 들어 있어(artist/<aid>_songs.html)
       이름이 아니라 ID 로 매칭한다 — 'Seventeen' 동명 밴드 같은 오매칭을 피한다.
       실패하면 빈 dict(아래서 Spotify 메타로 폴백)."""
    try:
        req = urllib.request.Request("https://kworb.net/spotify/listeners.html",
                                     headers={"User-Agent": "Mozilla/5.0"})
        page = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
    except Exception as e:
        print(f"  [kworb] 목록 실패: {str(e)[:80]}"); return {}
    out = {}
    for m in re.finditer(
            r'artist/(\w+)_songs\.html">[^<]*</a></div></td>'
            r'<td>([\d,]+)</td><td>(-?[\d,]+)</td>', page):
        out[m.group(1)] = (int(m.group(2).replace(",", "")),
                           int(m.group(3).replace(",", "")))
    return out


def _spotify_meta_ml(aid):
    """kworb 미수록 아티스트 폴백 — Spotify 아티스트 페이지 메타설명의 월간청취자.
       'Artist · 4.8M monthly listeners.' → 4800000. ID 로 직접 접근하니 오매칭 없음.
       축약 표기라 정밀도는 kworb 보다 낮다(선의 미세 변화가 덜 잡힘). 실패 None."""
    try:
        req = urllib.request.Request(f"https://open.spotify.com/artist/{aid}",
                                     headers={"User-Agent": "Mozilla/5.0"})
        page = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    except Exception:
        return None
    m = re.search(r'([\d.,]+)\s*([KMB]?)\s*monthly listeners', page)
    if not m:
        return None
    try:
        num = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    return int(num * {"K": 1e3, "M": 1e6, "B": 1e9}.get(m.group(2), 1))


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

    kworb = _kworb_listeners()          # 월간 청취자(공식 API엔 없음) — aid 로 매칭
    yday = (datetime.datetime.now(KST).date() - datetime.timedelta(days=1)).isoformat()

    arts = []
    for stock, label, query, pin_aid in ARTISTS:
        old = prev.get((stock, label), {})
        aid = old.get("aid") or pin_aid          # 캐시 우선, 없으면 고정aid, 그것도 없으면 검색
        hist = list(old.get("hist") or [])
        art = {"stock": stock, "label": label, "aid": aid, "hist": hist}
        if not aid:
            try:
                aid = art["aid"] = _artist_id(query, tok)
            except Exception as e:
                print(f"  [{label}] id 검색 실패: {str(e)[:70]}")
        if not aid:
            print(f"  [{label}] 아티스트 못 찾음(query={query})"); arts.append(art); continue

        # 1) Spotify Web API — 인기도·팔로워·대표곡·최근작.
        #    러너 IP 가 403 을 내는 사례가 있어 여기서만 막고, 월간청취자(아래)는 계속 진행한다.
        fol = pop = tpop = None
        try:
            fol, pop = _artist(aid, tok)
            ttn, tpop = _top_track(aid, tok)
            rname, rdate = _latest_release(aid, tok)
            art["topTrack"] = ttn
            art["release"] = {"name": rname, "date": rdate}
        except Exception as e:
            print(f"  [{label}] Spotify API 실패(인기도·팔로워 스킵): {str(e)[:60]}")

        # 2) 월간 청취자 — 공식 API 와 무관(kworb 랭킹 / Spotify 아티스트 페이지 메타).
        #    kworb(정확·일간증감) 우선, 미수록이면 메타(축약). API 403 이어도 이건 수집된다.
        ml, delta = None, None
        if aid in kworb:
            ml, delta = kworb[aid]
        else:
            try:
                ml = _spotify_meta_ml(aid)
            except Exception:
                pass

        # 3) 오늘 점 — 잡힌 값만 담는다. 전부 실패면 점을 추가하지 않는다.
        pt = {"d": today}
        for k, v in (("fol", fol), ("pop", pop), ("tpop", tpop), ("ml", ml)):
            if v is not None:
                pt[k] = v
        if len(pt) > 1:
            by_d = {x["d"]: x for x in hist if x.get("d")}
            # 첫 수집이면 '어제' 한 점을 kworb 일간증감으로 복원한다(실측치). 선이 바로 그려진다.
            if (ml is not None and delta is not None
                    and not any(x.get("ml") is not None for x in hist)
                    and yday not in by_d):
                by_d[yday] = {"d": yday, "ml": ml - delta}
            cur = by_d.get(today, {"d": today})
            cur.update(pt)                       # 같은 날 재실행이면 값만 갱신
            by_d[today] = cur
            hist = [by_d[d] for d in sorted(by_d)]
            art["hist"] = hist[-DAYS:]
        print(f"  {label}: 인기도 {pop if pop is not None else '—'} · "
              f"팔로워 {fol if fol is not None else '—'} · "
              f"월간청취자 {f'{ml:,}' if ml is not None else '—'}")
        arts.append(art)

    sp = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "artists": arts}
    if "--dry-run" in sys.argv:
        print(json.dumps(sp, ensure_ascii=False, indent=1)[:700]); return
    open(HTML, "w", encoding="utf-8").write(_put(html, "SPOTIFY", sp))
    print(f"[OK] SPOTIFY 갱신 · {len(arts)}팀")


if __name__ == "__main__":
    main()
