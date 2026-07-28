# -*- coding: utf-8 -*-
"""
써클차트(구 가온) 앨범 판매량 수집 — 엔터 종목의 실물 수요/매출 신호.

공개 JSON API(키 불필요):  POST https://circlechart.kr/data/api/chart/album
  파라미터: nationGbn=T · termGbn=month|week · hitYear=YYYY · targetTime=MM|주차 · PageSize
  응답 List[*]: ARTIST_NAME · ALBUM_NAME · Album_CNT(기간 판매) · Total_CNT(누적) · SERVICE_RANKING

public/index.html 의  const CIRCLE = {...};  블록을 교체한다. 변동 없으면 건드리지 않는다.
  CIRCLE = { asOf, month:{periods, byStock, byArtist, top}, week:{...} }
    - byStock  : 종목별 그 기간 소속 아티스트 앨범판매 합계(회사 수요 총량)
    - byArtist : 추적 아티스트별 앨범판매(스포티파이 뷰와 짝)
    - top      : 최신 기간 상위 앨범(회사 태그 포함) — 각주·랭킹 표시용

  python fetch_circle.py            # 수집·기록
  python fetch_circle.py --dry-run  # 출력만

⚠ 한국 사이트라 미국 러너에서 지역차단(403/타임아웃)될 수 있다. 실패하면 기존 데이터를 보존한다.
"""
import os, re, json, sys, time, datetime, urllib.request, urllib.parse

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
API = "https://circlechart.kr/data/api/chart/album"
MONTHS_BACK = 12
WEEKS_BACK = 13
PAGE = 100
PAUSE = 0.3

# 종목 → 소속 대표 아티스트(회사 합계용, 넓게). Circle ARTIST_NAME 을 정규화해 부분매칭.
# 앨범 판매 상위는 대형 그룹이 대부분이라 이 정도면 회사 총량의 대부분을 포착한다.
# ⚠ Circle 은 한글명("방탄소년단"·"투모로우바이투게더")으로 적는 경우가 많아 한글 별칭 필수.
#    (_norm 이 괄호는 떼므로 "Stray Kids (스트레이 키즈)" 는 영문키로 이미 잡힌다)
ROSTER = {
    "하이브": ["BTS", "방탄소년단", "RM", "Jin", "SUGA", "Agust D", "j-hope", "제이홉",
             "Jimin", "Jung Kook", "정국",
             "SEVENTEEN", "세븐틴", "TOMORROW X TOGETHER", "TXT", "투모로우바이투게더",
             "LE SSERAFIM", "르세라핌", "ENHYPEN", "엔하이픈", "NewJeans", "뉴진스",
             "ILLIT", "아일릿", "BOYNEXTDOOR", "보이넥스트도어", "&TEAM", "앤팀",
             "TWS", "투어스", "KATSEYE", "캣츠아이", "CORTIS", "코르티스",
             "fromis_9", "프로미스나인"],
    "JYP Ent.": ["Stray Kids", "스트레이키즈", "TWICE", "트와이스", "ITZY", "있지",
               "NMIXX", "엔믹스", "DAY6", "데이식스", "NiziU", "니쥬",
               "Xdinary Heroes", "엑스디너리히어로즈", "VCHA", "NEXZ"],
    "에스엠": ["aespa", "에스파", "RIIZE", "라이즈", "NCT DREAM", "엔시티드림",
             "NCT 127", "엔시티127", "NCT U", "NCT WISH", "엔시티위시", "WayV", "웨이션브이",
             "Red Velvet", "레드벨벳", "EXO", "엑소", "SHINee", "샤이니",
             "SUPER JUNIOR", "슈퍼주니어", "Girls' Generation", "소녀시대",
             "TVXQ", "동방신기", "TAEYEON", "태연", "BAEKHYUN", "백현", "DOYOUNG",
             "Hearts2Hearts", "SuperM"],
    "와이지엔터": ["BLACKPINK", "블랙핑크", "JENNIE", "제니", "LISA", "ROSÉ", "로제",
               "JISOO", "TREASURE", "트레저", "BABYMONSTER", "베이비몬스터",
               "WINNER", "위너", "AKMU", "악뮤", "BIGBANG", "빅뱅"],
}

# 개별 아티스트 브레이크다운 — (종목, 표시라벨, [Circle 매칭키...]).
# 스택 막대의 색 구간이 된다. '기타(그 외)' 를 줄이려 주요 판매 아티스트를 넓게 담는다.
# 매칭은 토큰 단위(_keymatch) — 짧은 라틴키(RM·EXO·TWS 등)는 정확히 한 토큰과 일치해야
# 잡히므로 'P1Harmony' 의 'ha(rm)ony' 같은 오매칭이 없다.
ARTIST_CANON = [
    ("하이브", "방탄소년단", ["BTS", "방탄소년단"]),
    ("하이브", "세븐틴", ["SEVENTEEN", "세븐틴"]),
    ("하이브", "르세라핌", ["LE SSERAFIM", "르세라핌"]),
    ("하이브", "엔하이픈", ["ENHYPEN", "엔하이픈"]),
    ("하이브", "투바투", ["TOMORROW X TOGETHER", "TXT", "투모로우바이투게더"]),
    ("하이브", "보이넥스트도어", ["BOYNEXTDOOR", "보이넥스트도어"]),
    ("하이브", "뉴진스", ["NewJeans", "뉴진스"]),
    ("하이브", "아일릿", ["ILLIT", "아일릿"]),
    ("하이브", "투어스", ["TWS", "투어스"]),
    ("하이브", "앤팀", ["&TEAM", "앤팀"]),
    ("하이브", "캣츠아이", ["KATSEYE", "캣츠아이"]),
    ("하이브", "코르티스", ["CORTIS", "코르티스"]),
    ("JYP Ent.", "스트레이키즈", ["Stray Kids", "스트레이키즈"]),
    ("JYP Ent.", "트와이스", ["TWICE", "트와이스"]),
    ("JYP Ent.", "있지", ["ITZY", "있지"]),
    ("JYP Ent.", "엔믹스", ["NMIXX", "엔믹스"]),
    ("JYP Ent.", "데이식스", ["DAY6", "데이식스"]),
    ("에스엠", "에스파", ["aespa", "에스파"]),
    ("에스엠", "라이즈", ["RIIZE", "라이즈"]),
    ("에스엠", "엔시티드림", ["NCT DREAM", "엔시티드림"]),
    ("에스엠", "엔시티127", ["NCT 127", "엔시티127"]),
    ("에스엠", "엔시티위시", ["NCT WISH", "엔시티위시"]),
    ("에스엠", "레드벨벳", ["Red Velvet", "레드벨벳"]),
    ("에스엠", "엑소", ["EXO", "엑소"]),
    ("에스엠", "샤이니", ["SHINee", "샤이니"]),
    ("에스엠", "하츠투하츠", ["Hearts2Hearts", "하츠투하츠"]),
    ("와이지엔터", "블랙핑크", ["BLACKPINK", "블랙핑크"]),
    ("와이지엔터", "트레저", ["TREASURE", "트레저"]),
    ("와이지엔터", "베이비몬스터", ["BABYMONSTER", "베이비몬스터"]),
    ("와이지엔터", "제니", ["JENNIE", "제니"]),
    ("와이지엔터", "로제", ["ROSÉ", "로제"]),
]


def _tokens(s):
    """아티스트/키를 토큰으로. 괄호(현지명)는 떼고 영숫자·한글 덩어리로 나눈다.
       'Stray Kids (스트레이 키즈)' -> ['stray','kids'] · '방탄소년단' -> ['방탄소년단']"""
    s = re.sub(r"\([^)]*\)", "", s or "").lower()
    return re.findall(r"[0-9a-z]+|[가-힣]+", s)


def _keymatch(art_tokens, art_concat, key_tokens):
    """키가 아티스트에 매칭되나. 짧은 라틴 단일토큰(rm·exo·tws)은 '정확히 한 토큰과 일치'라야
       한다 — 부분매칭을 허용하면 'RM' 이 'P1Ha(rm)ony' 에 걸린다. 그 외(한글·다토큰·긴 라틴)는
       연결형 부분매칭."""
    if not key_tokens:
        return False
    if len(key_tokens) == 1 and re.fullmatch(r"[0-9a-z]+", key_tokens[0]) and len(key_tokens[0]) <= 4:
        return key_tokens[0] in art_tokens
    return "".join(key_tokens) in art_concat


# 키를 토큰으로 미리 변환(한 번만)
_ROSTER_K = {st: [_tokens(k) for k in ks] for st, ks in ROSTER.items()}
_CANON_K = [(st, lab, [_tokens(k) for k in ks]) for st, lab, ks in ARTIST_CANON]


def _stock_of(artist):
    at = _tokens(artist); ac = "".join(at)
    for st, keylist in _ROSTER_K.items():
        if any(_keymatch(at, ac, kt) for kt in keylist):
            return st
    return None


def _canon_of(artist):
    """아티스트 -> 브레이크다운 표시라벨(없으면 None → '기타' 로 묶임)."""
    at = _tokens(artist); ac = "".join(at)
    for st, lab, keylist in _CANON_K:
        if any(_keymatch(at, ac, kt) for kt in keylist):
            return lab
    return None


def _fetch(term, year, tt):
    """term=month|week. 실패·빈 응답이면 [] 반환."""
    body = urllib.parse.urlencode({
        "nationGbn": "T", "termGbn": term, "serviceGbn": "",
        "hitYear": str(year), "targetTime": str(tt), "yearTime": "3",
        "PageSize": str(PAGE), "curUrl": "/page_chart/album.circle"}).encode()
    req = urllib.request.Request(API, data=body, headers={
        "User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://circlechart.kr/page_chart/album.circle"})
    try:
        raw = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
        d = json.loads(raw)
    except Exception as e:
        print(f"    [{term} {year}/{tt}] 요청 실패: {str(e)[:70]}"); return []
    L = d.get("List")
    if not isinstance(L, dict) or not L:
        return []
    rows = []
    for k in sorted(L, key=lambda x: int(x)):
        it = L[k]
        try:
            cnt = int(str(it.get("Album_CNT") or "0").replace(",", "") or 0)
        except ValueError:
            cnt = 0
        rows.append({"artist": (it.get("ARTIST_NAME") or "").strip(),
                     "album": (it.get("ALBUM_NAME") or "").strip(),
                     "cnt": cnt,
                     "tot": int(str(it.get("Total_CNT") or "0").replace(",", "") or 0),
                     "rank": int(str(it.get("SERVICE_RANKING") or "0") or 0)})
    return rows


def _agg(rows):
    """한 기간 rows → (byStock 합계, byArtist 합계, top 앨범 리스트)."""
    by_stock = {st: 0 for st in ROSTER}
    by_artist = {lab: 0 for _, lab, _ in ARTIST_CANON}
    top = []
    for i, r in enumerate(rows):
        st = _stock_of(r["artist"])
        if st:
            by_stock[st] += r["cnt"]
        lab = _canon_of(r["artist"])
        if lab:
            by_artist[lab] += r["cnt"]
        if i < 20:
            top.append({"album": r["album"][:40], "artist": r["artist"], "cnt": r["cnt"],
                        "rank": r["rank"], "stock": st})
    return by_stock, by_artist, top


def _month_periods(now):
    """수집할 (year, month) 목록 — 최신(데이터 있는) 달부터 과거로 MONTHS_BACK 개. 라벨도 함께."""
    y, m = now.year, now.month
    # 이번 달은 아직 미집계일 수 있다 — 데이터 있으면 포함, 없으면 지난달부터.
    if not _fetch("month", y, f"{m:02d}"):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    out = []
    for _ in range(MONTHS_BACK):
        out.append((y, m, f"{str(y)[2:]}.{m:02d}"))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(out))


def _latest_week(now):
    """데이터가 있는 최신 주차를 찾는다(ISO 주차 ±로 탐색)."""
    y, wk = now.isocalendar()[0], now.isocalendar()[1]
    for d in (1, 0, -1, -2, -3):
        w = wk + d
        if w >= 1 and _fetch("week", y, w):
            return y, w
    return y, wk


def _week_periods(now):
    """최신 주차부터 과거로 WEEKS_BACK 개 (year, week, 라벨)."""
    y, w = _latest_week(now)
    out = []
    for _ in range(WEEKS_BACK):
        out.append((y, w, f"{str(y)[2:]}W{w:02d}"))
        w -= 1
        if w < 1:
            y, w = y - 1, 52          # 연초 경계는 대략 52주로(정확도보다 연속성 우선)
    return list(reversed(out))


def _collect(term, periods):
    """periods=[(year, tt, label)] → {periods, byStock, byArtist, top}. 기간 실패는 건너뛴다."""
    labels, bs, ba = [], {st: [] for st in ROSTER}, {lab: [] for _, lab, _ in ARTIST_CANON}
    last_top = []
    for y, tt, lab in periods:
        rows = _fetch(term, y, tt)
        if not rows:
            print(f"    {lab}: 데이터 없음(건너뜀)"); continue
        st, ar, top = _agg(rows)
        labels.append(lab)
        for k in bs:
            bs[k].append(st[k])
        for k in ba:
            ba[k].append(ar[k])
        last_top = top
        print(f"    {lab}: {sum(st.values()):,}장 (상위 {top[0]['artist']} {top[0]['cnt']:,})")
        time.sleep(PAUSE)
    # 계속 0인 종목/아티스트는 뺀다(노이즈)
    bs = {k: v for k, v in bs.items() if any(v)}
    ba = {k: v for k, v in ba.items() if any(v)}
    return {"periods": labels, "byStock": bs, "byArtist": ba, "top": last_top}


def main():
    now = datetime.datetime.now(KST)
    print("[월간 앨범판매 수집]")
    month = _collect("month", _month_periods(now))
    print("[주간 앨범판매 수집]")
    week = _collect("week", _week_periods(now))
    if not month["periods"] and not week["periods"]:
        print("[!] 수집 실패(지역차단 가능) — 기존 데이터 보존, 종료"); return

    circle = {"asOf": now.strftime("%Y-%m-%d %H:%M KST"), "month": month, "week": week,
              "artistStock": {lab: st for st, lab, _ in ARTIST_CANON}}
    if "--dry-run" in sys.argv:
        for term in ("month", "week"):
            b = circle[term]
            print(f"\n== {term} · 기간 {b['periods']}")
            for st, v in b["byStock"].items():
                print(f"   {st}: 최근 {v[-1]:,}장" if v else st)
        return

    src = open(HTML, encoding="utf-8").read()
    block = "const CIRCLE = " + json.dumps(circle, ensure_ascii=False, separators=(",", ":")) + ";"
    old = re.search(r"const CIRCLE\s*=\s*\{.*?\};", src, re.S)
    if old:
        # 변동 없으면 파일 안 건드림(asOf 제외 비교)
        try:
            prev = json.loads(re.search(r"const CIRCLE\s*=\s*(\{.*?\});", src, re.S).group(1))
            prev.pop("asOf", None)
            cur = dict(circle); cur.pop("asOf", None)
            if prev == cur:
                print("[SKIP] 써클차트 변동 없음"); return
        except Exception:
            pass
        new_src = src[:old.start()] + block + src[old.end():]
    else:
        anchor = re.search(r"const SPOTIFY\s*=\s*\{.*?\};", src, re.S) or \
                 re.search(r"const LIVE\s*=\s*\{.*?\};\n", src, re.S)
        if not anchor:
            print("[!] 삽입 기준(SPOTIFY/LIVE)을 못 찾음"); sys.exit(1)
        new_src = src[:anchor.end()] + "\n" + block + src[anchor.end():]
    open(HTML, "w", encoding="utf-8").write(new_src)
    print(f"[OK] CIRCLE 갱신 · 월 {len(month['periods'])}기간 · 주 {len(week['periods'])}기간")


if __name__ == "__main__":
    main()
