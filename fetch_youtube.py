# -*- coding: utf-8 -*-
"""
YouTube 채널 통계 수집 — 엔터 IP 의 관심/컴백 신호(구독자·조회수).
엔터는 지금 데이터가 가장 비어 있고, 아티스트 컴백 때 채널 조회수가 급증한다.

공식 YouTube Data API v3(무료, 하루 10,000 유닛). YOUTUBE_API_KEY 없으면 조용히 스킵.
  - 채널 검색(search, 100유닛): 이름 → channelId. 한 번 찾으면 데이터에 cid 를 캐시해 재검색 안 함(1유닛)
  - 통계(channels.statistics, 1유닛): subscriberCount(구독자, 대형은 3자리 반올림) · viewCount(누적 조회수)

과거 시계열 무료 소스가 없어 매일 1점씩 누적. 누적 조회수의 '전일 대비 증가분'이 진짜 신호다.

  python fetch_youtube.py            # 수집·기록
  python fetch_youtube.py --dry-run  # 출력만
"""
import os, re, json, sys, datetime, urllib.request, urllib.parse

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
DAYS = 180
KEY = os.environ.get("YOUTUBE_API_KEY", "")

# (종목, 라벨, 검색어) — 검색으로 channelId 를 찾고, 찾은 뒤엔 데이터에 cid 를 저장해 재검색 안 함.
CHANNELS = [
    ("하이브",    "BTS",     "BANGTANTV"),
    ("하이브",    "세븐틴",   "SEVENTEEN"),
    ("하이브",    "르세라핌", "LE SSERAFIM"),
    ("하이브",    "엔하이픈", "ENHYPEN"),
    ("하이브",    "투바투",   "TOMORROW X TOGETHER"),
    ("SAMG엔터", "티니핑",   "Catch! Teenieping"),
]


def available():
    return bool(KEY)


def _api(path, **params):
    params["key"] = KEY
    url = f"https://www.googleapis.com/youtube/v3/{path}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def _resolve(query):
    d = _api("search", part="snippet", type="channel", q=query, maxResults=1)
    its = d.get("items") or []
    return (its[0].get("id") or {}).get("channelId") if its else None


def _stats(cid):
    d = _api("channels", part="statistics", id=cid)
    its = d.get("items") or []
    if not its:
        return None
    s = its[0].get("statistics") or {}
    return int(s.get("subscriberCount", 0) or 0), int(s.get("viewCount", 0) or 0)


def _latest_video(cid):
    """채널 최신 영상(=컴백 MV 후보) 1건: (videoId, 제목, 게시일)."""
    d = _api("search", part="snippet", channelId=cid, order="date", type="video", maxResults=1)
    its = d.get("items") or []
    if not its:
        return None
    vid = (its[0].get("id") or {}).get("videoId")
    sn = its[0].get("snippet") or {}
    return (vid, sn.get("title", "")[:40], (sn.get("publishedAt", "") or "")[:10]) if vid else None


def _video_views(vid):
    d = _api("videos", part="statistics", id=vid)
    its = d.get("items") or []
    return int(((its[0].get("statistics") or {}).get("viewCount")) or 0) if its else None


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
        raise RuntimeError("YT 삽입 기준(const LIVE)을 못 찾음")
    return html[:liv.end()] + "\n" + block + html[liv.end():]


def main():
    if not available():
        print("[youtube] YOUTUBE_API_KEY 없음 — 스킵"); return
    html = open(HTML, encoding="utf-8").read()
    today = datetime.datetime.now(KST).date().isoformat()
    prev = {(c["stock"], c["label"]): c
            for c in (_const(html, "YT") or {}).get("channels", [])}

    chans = []
    for stock, label, query in CHANNELS:
        old = prev.get((stock, label), {})
        cid = old.get("cid")
        hist = list(old.get("hist") or [])
        try:
            if not cid:
                cid = _resolve(query)                 # 최초 1회만 검색(이후 cid 재사용)
            st = _stats(cid) if cid else None
            if st:
                subs, views = st
                pt = {"d": today, "subs": subs, "views": views}
                if hist and hist[-1].get("d") == today:
                    hist[-1] = pt
                else:
                    hist.append(pt)
                hist = hist[-DAYS:]
                print(f"  {label}: 구독 {subs:,} · 조회 {views:,}")
            else:
                print(f"  [{label}] 채널 못 찾음(query={query})")
        except Exception as e:
            print(f"  [{label}] 실패: {str(e)[:100]}")

        # 최신 영상(컴백 MV) 조회수 추적 — 새 영상이 올라오면 그 영상으로 갈아탄다.
        mv = dict(old.get("mv") or {})
        try:
            lv = _latest_video(cid) if cid else None
            if lv:
                vid, vtitle, vpub = lv
                vv = _video_views(vid)
                if vv is not None:
                    if mv.get("id") != vid:                # 새 영상 → 시계열 새로 시작
                        mv = {"id": vid, "title": vtitle, "pub": vpub, "hist": []}
                    mvh = list(mv.get("hist") or [])
                    if mvh and mvh[-1].get("d") == today:
                        mvh[-1] = {"d": today, "v": vv}
                    else:
                        mvh.append({"d": today, "v": vv})
                    mv["hist"] = mvh[-DAYS:]
                    print(f"    최신영상 '{vtitle[:18]}' 조회 {vv:,}")
        except Exception as e:
            print(f"    [{label} MV] 실패: {str(e)[:70]}")

        chans.append({"stock": stock, "label": label, "cid": cid, "hist": hist, "mv": mv})

    yt = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "channels": chans}
    if "--dry-run" in sys.argv:
        print(json.dumps(yt, ensure_ascii=False, indent=1)[:700]); return
    open(HTML, "w", encoding="utf-8").write(_put(html, "YT", yt))
    print(f"[OK] YT 갱신 · {len(chans)}채널")


if __name__ == "__main__":
    main()
