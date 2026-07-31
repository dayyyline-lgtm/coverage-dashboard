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
import os, re, json, sys, base64, datetime, urllib.request, urllib.parse, urllib.error

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
DAYS = 180
CID = os.environ.get("SPOTIFY_CLIENT_ID", "")
CSEC = os.environ.get("SPOTIFY_CLIENT_SECRET", "")

DEBUG_PATH = "spotify_debug.json"
_RAW = {}   # 진단: aid → /v1/artists 응답에 followers·popularity 가 실제로 담겨오는지
# 이 앱 권한으로 막힌 엔드포인트. 한 번 403 이면 12팀 내내 같으므로 그 뒤로는 안 부른다.
BLOCKED = {}

# (종목, 라벨, 검색어, 고정aid) — 엔터 커버 종목의 주요 아티스트.
# 고정aid 를 주면 검색을 건너뛴다. 신인·동명이인은 search 가 엉뚱한 아티스트를 잡을 수
# 있어(예: 'CORTIS' 로 다른 밴드, 'EXO' 로 다른 그룹) 검증한 ID 를 박아 둔다.
# None 이면 검색으로 찾고, 찾은 aid 는 데이터에 캐시되어 다음 실행부터 재사용된다.
ARTISTS = [
    # 하이브
    ("하이브", "BTS",     "BTS",                 None),
    ("하이브", "세븐틴",   "SEVENTEEN",           None),
    ("하이브", "르세라핌", "LE SSERAFIM",         None),
    ("하이브", "엔하이픈", "ENHYPEN",             None),
    ("하이브", "투바투",   "TOMORROW X TOGETHER", None),
    ("하이브", "캣츠아이", "KATSEYE",             "3c0gDdb9lhnHGFtP4prQpn"),
    ("하이브", "코르티스", "CORTIS",              "1ebt9HnXdyYA6KgLXr1n4P"),
    # 에스엠 (SM)
    ("에스엠", "에스파",     "aespa",       "6YVMFz59CuY7ngCxTxjpxE"),
    ("에스엠", "라이즈",     "RIIZE",       "2jOm3cYujQx6o1dxuiuqaX"),
    ("에스엠", "엔시티드림", "NCT DREAM",   "1gBUSTR3TyDdTVFIaQnc02"),
    ("에스엠", "레드벨벳",   "Red Velvet",  "1z4g3DjTBBZKhvAroFlhOM"),
    ("에스엠", "엑소",       "EXO",         "3cjEqqelV9zb4BYE3qDQ4O"),
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
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # 스포티파이는 거절 사유를 본문 JSON 에 적어 보낸다
        # ({"error":{"status":403,"message":"..."}}). 예전엔 이걸 버리고
        # 'HTTP Error 403: Forbidden' 만 남겨서 왜 막혔는지 알 수가 없었다.
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code} {url.split('/v1/')[-1][:40]} · {body}") from None


def _artist_id(name, tok):
    d = _get("https://api.spotify.com/v1/search?"
             + urllib.parse.urlencode({"q": name, "type": "artist", "limit": 1}), tok)
    its = ((d.get("artists") or {}).get("items")) or []
    return its[0]["id"] if its else None


def _artist(aid, tok):
    """팔로워·인기도. 이 앱 권한으로는 안 오는 경우가 있어 (None, None) 을 돌려줄 수 있다.

       ⚠️ 이 앱은 확장 권한(Extended Quota)이 없어 카탈로그 응답이 깎여서 온다.
          200 은 오지만 followers·popularity 키 자체가 빠진다
          (오는 키: external_urls·href·id·images·name·type·uri).
          0 으로 채우면 인기도 추이선이 바닥에 깔리므로 None 으로 둔다."""
    d = _get(f"https://api.spotify.com/v1/artists/{aid}", tok)
    _RAW[aid] = {"has_followers": "followers" in d,
                 "followers_total": (d.get("followers") or {}).get("total"),
                 "has_popularity": "popularity" in d,
                 "popularity": d.get("popularity"),
                 "keys": sorted(d.keys())}
    fol = (d.get("followers") or {}).get("total")
    pop = d.get("popularity")
    return (int(fol) if fol is not None else None,
            int(pop) if pop is not None else None)


def _top_track(aid, tok):
    """대표곡(현재 가장 인기 트랙) 이름·인기도 — 컴백 신곡이 뜨면 여기 반영된다."""
    d = _get(f"https://api.spotify.com/v1/artists/{aid}/top-tracks?market=KR", tok)
    ts = d.get("tracks") or []
    return (ts[0].get("name", "")[:30], int(ts[0].get("popularity") or 0)) if ts else (None, None)


# albums 는 파라미터 조합에 따라 400("Invalid limit")이 난다.
# 앞에서부터 시도해 처음 통하는 조합을 기억하고, 다음 아티스트부터는 그것만 쓴다.
# (문자열을 손으로 이어 붙이던 걸 urlencode 로 바꿨다 — include_groups 의 쉼표 인코딩 문제도 같이 배제)
_ALB_TRIED = {"ok": None}
_ALB_PARAMS = [
    {"include_groups": "single,album", "market": "KR", "limit": "50"},
    {"include_groups": "single,album", "market": "KR"},
    {"include_groups": "single,album"},
    {"market": "KR"},
    {},
]


def _latest_release(aid, tok):
    """최근 발매작(앨범·싱글) 이름·발매일 — 컴백/발매 시점 감지."""
    cands = [_ALB_TRIED["ok"]] if _ALB_TRIED["ok"] is not None else _ALB_PARAMS
    last = None
    for p in cands:
        url = f"https://api.spotify.com/v1/artists/{aid}/albums"
        if p:
            url += "?" + urllib.parse.urlencode(p)
        try:
            d = _get(url, tok)
        except Exception as e:
            last = e
            continue
        _ALB_TRIED["ok"] = p
        its = d.get("items") or []
        if not its:
            return None, None
        its.sort(key=lambda x: x.get("release_date", ""), reverse=True)
        return its[0].get("name", "")[:30], its[0].get("release_date", "")
    raise last if last else RuntimeError("albums: 응답 없음")


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


def _kworb_artist(aid):
    """kworb 아티스트 페이지 → 총 스트림·일간 스트림.
       일간 스트림(sd)이 핵심 — 실시간 소비/수요 플로우로, 컴백 때 즉시 튄다
       (월간청취자보다 반응이 빠르다). 실패 None.

       요약행 구조:  Streams</td><td>{총}</td> · Daily</td><td>{일간}</td>"""
    try:
        req = urllib.request.Request(f"https://kworb.net/spotify/artist/{aid}_songs.html",
                                     headers={"User-Agent": "Mozilla/5.0"})
        p = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
    except Exception as e:
        print(f"  [kworb-곡] {aid} 실패: {str(e)[:60]}"); return None
    num = lambda s: int(s.replace(",", ""))
    tot = re.search(r'Streams</td><td>([\d,]+)</td>', p)
    day = re.search(r'Daily</td><td>([\d,]+)</td>', p)
    if not (tot and day):
        return None
    return {"str": num(tot.group(1)), "sd": num(day.group(1))}


def _spotify_meta_ml(aid):
    """kworb 미수록 아티스트(상위 2500위 밖) 폴백 — Spotify 아티스트 페이지의 월간청취자.
       ID 로 직접 접근하니 오매칭 없음. 실패 None.

       ⚠️ 페이지엔 두 표기가 공존한다:
         - 본문 정밀값:  '4,788,568 monthly listeners'  ← 이걸 써야 일 변동이 잡힌다
         - 메타 축약값:  'Artist · 4.8M monthly listeners.'  ← 반올림이라 값이 멈춰 보임
       예전엔 축약값만 긁어 세븐틴·라이즈 등이 4.8M/2.8M 로 고정됐다. 정밀값 우선."""
    try:
        req = urllib.request.Request(f"https://open.spotify.com/artist/{aid}",
                                     headers={"User-Agent": "Mozilla/5.0"})
        page = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    except Exception:
        return None
    # 1) 정밀(쉼표 구분 절대수) 우선 — 최소 5자리라 'X,XXX,XXX' 만 잡고 축약(4.8M)은 안 잡힘
    m = re.search(r'([\d,]{5,})\s*monthly listeners', page)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            pass
    # 2) 폴백: 축약 표기(4.8M) — 정밀값이 없을 때만
    m = re.search(r'([\d.]+)\s*([KMB])\s*monthly listeners', page)
    if m:
        try:
            return int(float(m.group(1)) * {"K": 1e3, "M": 1e6, "B": 1e9}[m.group(2)])
        except (ValueError, KeyError):
            pass
    return None


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
        print(f"[spotify] 토큰 실패: {str(e)[:100]}")
        json.dump({"asOf": today, "token_ok": False, "token_err": str(e)[:200]},
                  open(DEBUG_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return
    dbg = []   # 진단: 아티스트별 API 성패

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
        # 항목마다 따로 감싼다. 예전엔 셋을 한 try 로 묶어서, 못 쓰는 항목 하나
        # (top-tracks 403) 때문에 뒤의 최근 발매작까지 통째로 건너뛰었다.
        # 그리고 이 앱이 못 쓰는 엔드포인트는 한 번 막히면 12팀 내내 똑같이 막히므로,
        # 처음 한 번만 확인하고 그 뒤로는 부르지 않는다(무의미한 호출·경고 반복 제거).
        fol = pop = tpop = None
        api_err = None
        try:
            fol, pop = _artist(aid, tok)
        except Exception as e:
            api_err = f"{type(e).__name__}: {str(e)[:120]}"
        # 4xx 는 이 앱·이 요청이 구조적으로 막혔다는 뜻이라 12팀 내내 똑같이 실패한다.
        # 403 만 보고 있었더니 albums 의 400 은 못 걸러 매번 12번씩 재시도했다.
        def _try(kind, fn):
            if BLOCKED.get(kind) is True:
                return None
            try:
                v = fn()
                BLOCKED[kind] = False
                return v
            except Exception as e:
                m = re.search(r"HTTP (4\d\d)", str(e))
                if m:
                    BLOCKED[kind] = True
                    BLOCKED[kind + "_why"] = str(e)[:200]
                return None

        tt = _try("top", lambda: _top_track(aid, tok))
        if tt:
            _, tpop = tt
            art["topTrack"] = tt[0]
        rel = _try("alb", lambda: _latest_release(aid, tok))
        if rel and rel[0]:
            art["release"] = {"name": rel[0], "date": rel[1]}
        api_err = api_err or BLOCKED.get("top_why") or BLOCKED.get("alb_why")
        dbg.append({"label": label, "aid": aid, "fol": fol, "pop": pop,
                    "err": api_err, "raw": _RAW.get(aid)})

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

        # 2-b) 일간 스트림(플로우) — 실시간 소비 신호. 총·일간.
        ka = _kworb_artist(aid) or {}
        str_tot, sd = ka.get("str"), ka.get("sd")

        # 3) 오늘 점 — 잡힌 값만 담는다. 전부 실패면 점을 추가하지 않는다.
        pt = {"d": today}
        for k, v in (("fol", fol), ("pop", pop), ("tpop", tpop),
                     ("ml", ml), ("str", str_tot), ("sd", sd)):
            # 실제 아티스트가 팔로워·인기도 0 일 수는 없다 → 0 이면 'API 무응답'으로 보고
            # 저장하지 않는다(0을 넣으면 인기도 추이선이 바닥에 깔려 그려짐).
            # 월간청취자(ml)는 0이 진짜 '없음'이라 그대로 둔다.
            if v is not None and not (k in ("fol", "pop", "tpop") and v == 0):
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
        print(f"  {label}: 월간청취자 {f'{ml:,}' if ml is not None else '—'} · "
              f"일간스트림 {f'{sd:,}' if sd is not None else '—'}")
        arts.append(art)

    # 이 앱이 뭘 쓸 수 있는지 한 줄로 정리한다.
    # 예전엔 팀마다 'Spotify API 실패' 를 12줄 찍어서 수집 전체가 죽은 것처럼 보였는데,
    # 실제로는 월간청취자·스트림(kworb)이 정상 수집되고 있었다.
    nofp = sum(1 for x in dbg if x["fol"] is None and x["pop"] is None)
    if nofp:
        print(f"  [권한] 공식 API 가 팔로워·인기도를 주지 않음 ({nofp}/{len(dbg)}팀) — "
              f"확장 권한(Extended Quota) 없는 앱의 제한. 월간청취자·스트림으로 대체 중.")
    for k, ko in (("top", "대표곡"), ("alb", "최근 발매작")):
        if BLOCKED.get(k) is True:
            print(f"  [권한] {ko} 조회 막힘 — {BLOCKED.get(k + '_why', '')[:150]}")

    # 진단 파일 — /v1/artists 가 팔로워·인기도를 실제로 주는지 커밋되어 남는다.
    n0 = sum(1 for x in dbg if not x["fol"] and not x["pop"])
    json.dump({"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
               "token_ok": True, "zero_count": n0, "total": len(dbg),
               "blocked": BLOCKED, "artists": dbg},
              open(DEBUG_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    sp = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "artists": arts}
    if "--dry-run" in sys.argv:
        print(json.dumps(sp, ensure_ascii=False, indent=1)[:700]); return
    open(HTML, "w", encoding="utf-8").write(_put(html, "SPOTIFY", sp))
    print(f"[OK] SPOTIFY 갱신 · {len(arts)}팀")


if __name__ == "__main__":
    main()
