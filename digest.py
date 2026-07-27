# -*- coding: utf-8 -*-
"""
텔레그램 데일리 레터 — 중요한 신호만 간결하게.
(실적 서프라이즈=notify.py, 월간 수출=trade_digest.py 가 담당. 여긴 매일 요약.)

원칙:
  - 트렌드 데이터: TRACK 이 정한 계열만. 고정(pin) 은 매일, 나머지는 의미있게 움직였을 때만.
    같은 (종목, 그룹) 은 한 블록으로 묶어 서로 비교되게 찍는다.
  - 시세 급변(전일)엔 '왜 움직였나'를 준다. 근거가 센 순서로:
    실적발표(실제치 vs consSnap 컨센 → 상회/하회 × 주가방향으로 호실적반영/부진/셀온/
    악재선반영 판정, _surprise) > 그 밖의 공시 > 뉴스 헤드라인 > 트렌드 동반 > 섹터 전반.
    외부 API 는 쓰지 않는다. 근거가 하나도 없으면 아무 말도 붙이지 않는다(지어내지 않는다).
  - 카테고리: 소비재는 세부(화장품/미용/음식료/유통), 엔터·게임·호텔은 섹터.
  - 방향은 색 하나로만 (🔴상승·🔵하락, 한국식). 부호가 이미 방향을 말하므로 기호를 겹치지 않는다.
  - 줄이 넘치면 텔레그램이 다음 줄을 왼쪽 끝에 붙여 들여쓰기가 깨진다.
    그래서 폭(REASON_W·LABEL_W)을 정해 놓고 애초에 안 넘치게 자른다.
    자리 맞춤이 필요한 줄은 <code> 로 감싼다 — 밖은 가변폭이라 칸이 안 맞는다.

  python digest.py            # 전송
  python digest.py --dry-run  # 출력만
  python digest.py --alerts   # 일정·시세만(짧게)
"""
import re, json, sys, datetime, unicodedata
import telegram_send


HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
CHG_ALERT = 5.0
EVENT_DAYS = 7
NOTABLE_WOW = 15      # 트렌드 '의미있는' 전주비(%)
NOTABLE_BASE = 15     # 트렌드 기저(이 미만은 노이즈)
SPIKE = 30            # 급등/급락 태그
STREAK_MIN = 4        # 연속추세 태그(주)
# 폭(표시 칸 수). 텔레그램은 줄이 넘치면 다음 줄을 왼쪽 끝에 붙여 버려서
# 들여쓴 이유 줄이 두 줄이 되는 순간 모양이 무너진다. 애초에 안 넘치게 자른다.
REASON_W = 32         # 급변 이유 한 줄(들여쓰기 4칸 + 32 = 모바일 한 줄에 들어감)
LABEL_W = 12          # 트렌드 계열 이름 칸 (넘치면 자른다)
MOVERS_MAX = 5        # 급변 목록에 적을 종목 수. 더 늘리면 훑는 눈이 지친다
BLK = "▁▂▃▄▅▆▇█"
WD = ["월", "화", "수", "목", "금", "토", "일"]

# 레터에 올릴 계열 — (종목, 트렌드 그룹, 계열, 고정)
#   고정=True  : 움직임과 무관하게 매일 싣는다(매일 보고 싶다고 지정한 것)
#   고정=False : '의미있게 움직였을 때'만 (NOTABLE_WOW / STREAK_MIN)
# 연속으로 같은 (종목, 그룹) 이면 한 블록으로 묶여 서로 비교되게 찍힌다.
#
# 뺀 것: 배틀그라운드(크래프톤)·니케(시프트업).
#   둘 다 수년째 서비스 중이라 검색이 평탄하고, 움직여도 업데이트/이벤트라
#   실적 방향과 이어지지 않는다. 매일 볼 값이 아니다.
TRACK = [
    # 스킨부스터 3파전 — 리쥬란 단독으로 보면 '리쥬란이 빠진 건지 카테고리가
    # 빠진 건지'를 못 가른다. 경쟁 IP 와 나란히 놔야 점유 변화가 읽힌다.
    ("파마리서치", "스킨부스터", "리쥬란",   True),
    ("파마리서치", "스킨부스터", "리투오",   True),
    ("파마리서치", "스킨부스터", "셀르디엠", True),
    ("에이피알",   "K-뷰티 브랜드", "메디큐브", False),
    ("달바글로벌", "K-뷰티 브랜드", "달바",     False),
    ("리센스메디컬", "쿨로아600", "쿨로아600",  False),
    # 티니핑 국내(네이버) — 극장판 2편 개봉(8/5) 앞이라 홈마켓 관심이 곧 예매로 이어진다
    ("SAMG엔터", "티니핑 국가별", "한국", True),
    # 메탈카드봇 러시아(얀덱스) — 얀덱스는 절대 검색수를 줘서 크기 비교가 되는 유일한 소스
    ("SAMG엔터", "변신로봇 IP 러시아", "메탈카드봇", True),
    ("펄어비스", "펄어비스 IP", "붉은사막", False),
    # NC 신작 — 미출시라 평소엔 0 근처, 코믹마켓·테스터 모집 같은 이벤트에만 튄다.
    # 그 스파이크가 곧 신호라 조건부로 둔다(고정하면 매일 빈 줄만 나간다).
    ("NC", "아스트라에 오라티오", "아스트라에 오라티오", False),
]

# 레터에 찍을 이름. 계열 키가 그룹 안에서만 뜻이 통할 때 바꿔 준다.
# '티니핑 국가별' 안에서 계열 키는 나라 이름이라, 그대로 쓰면 레터에 '한국' 이 뜬다.
# 그룹명을 뗀 뒤로는 무엇의 한국인지 알 수 없다.
LABEL = {
    ("티니핑 국가별", "한국"): "티니핑",
    ("아스트라에 오라티오", "아스트라에 오라티오"): "아스오라",
}


def _const(html, name, br="{"):
    cl = "}" if br == "{" else "]"
    m = re.search(r"const %s\s*=\s*(\%s.*?\%s);" % (re.escape(name), br, cl), html, re.S)
    return json.loads(m.group(1)) if m else None


def _clean(s):
    return [v for v in s if v is not None]


def _wow(s):
    c = _clean(s)
    return None if len(c) < 2 or not c[-2] else (c[-1] / c[-2] - 1) * 100


def _streak(s):
    c = _clean(s)
    if len(c) < 2:
        return 0
    up, n = c[-1] > c[-2], 0
    for i in range(len(c) - 1, 0, -1):
        if c[i] != c[i - 1] and (c[i] > c[i - 1]) == up:
            n += 1
        else:
            break
    return n if up else -n


def _last(s):
    c = _clean(s)
    return c[-1] if c else None


def _w(s):
    """표시 폭 — 한글·전각은 두 칸을 먹는다.
       텔레그램 고정폭 글꼴에서 자리를 맞추려면 글자 수가 아니라 이 폭으로 세야 한다
       ('리쥬란' 3글자와 '셀르디엠' 4글자는 폭이 6 vs 8 이라 글자 수로 맞추면 어긋난다)."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _pad(s, n, right=False):
    sp = " " * max(0, n - _w(s))
    return (sp + s) if right else (s + sp)


# 한글 폭에 기대는 정렬(공백·전각공백 채우기)은 쓰지 않는다.
# 텔레그램 글꼴에서 한글:영문:전각공백 비율이 예측되지 않아 두 번 다 밀렸다.
# 정렬이 필요한 칸은 ASCII·블록문자만 담고, 한글은 정렬 대상에서 뺀다.
# 자세한 경위는 트렌드 렌더링 쪽 주석에 적어 뒀다.


def _cut(s, n):
    """표시 폭 n 칸으로 자른다. 글자 수로 자르면 한글이 섞였을 때 두 배로 길어져
       텔레그램에서 줄이 넘치고, 넘친 줄은 들여쓰기를 잃고 왼쪽 끝으로 붙는다."""
    if not s or _w(s) <= n:
        return s
    out = ""
    for c in s:
        if _w(out + c) > n - 1:
            break
        out += c
    return out + "…"


def _spark(s, n=10):
    c = _clean(s)[-n:]
    if len(c) < 2:
        return ""
    lo, hi = min(c), max(c)
    if hi == lo:
        return BLK[3] * len(c)
    # 바닥을 ▁ 이 아니라 ▂ 로 잡는다. ▁ 은 선이 너무 얇아 화면에서 안 보이는데,
    # 최솟값은 반드시 하나 이상 나오므로 계열 전체가 빈칸처럼 보이는 일이 생긴다
    # (티니핑이 실제로 그렇게 보였다).
    return "".join(BLK[1 + min(6, int((v - lo) / (hi - lo) * 6 + 0.5))] for v in c)


def _series(gobj, kw):
    prods = gobj.get("products") or []
    ser = gobj.get("naver") or gobj.get("google") or []
    if kw in prods and prods.index(kw) < len(ser):
        return ser[prods.index(kw)]
    return None


def _notable(tr):
    """레터에 실을 계열. dict 리스트로 돌려준다.
       고정(pin)은 무조건, 나머지는 의미있게 움직였을 때만.
       순서는 TRACK 순서를 유지한다 — 같은 그룹끼리 붙어 있어야 비교로 읽힌다."""
    groups = tr.get("groups") or {}
    rows = []
    for stock, gname, kw, pin in TRACK:
        g = groups.get(gname)
        s = _series(g, kw) if g else None
        if not s:
            continue
        last, w, st = _last(s), _wow(s), _streak(s)
        if last is None:
            continue
        if not pin:
            if last < NOTABLE_BASE:
                continue
            if not ((w is not None and abs(w) >= NOTABLE_WOW) or abs(st) >= STREAK_MIN):
                continue
        rows.append({"stock": stock, "group": gname, "kw": kw, "s": s,
                     "w": w, "streak": st, "pin": pin, "last": last,
                     # 얀덱스 그룹만 절대 검색수를 준다(peak=100 에 해당하는 실제 건수).
                     # 0~100 상대값끼리 크기를 비교하면 거짓말이 되므로 이때만 실수치를 쓴다.
                     "peak": (g or {}).get("peak"),
                     "src": ((g or {}).get("srcOf") or [None] * 99)[
                         ((g or {}).get("products") or []).index(kw)
                         if kw in ((g or {}).get("products") or []) else 0]})
    return rows


def _josa(word, with_batchim, without):
    """받침 여부에 맞는 조사. '리쥬란와' 처럼 어색해지는 걸 막는다.
       한글 음절은 (코드 - 0xAC00) % 28 이 0 이 아니면 받침이 있다."""
    if not word:
        return without
    c = ord(word[-1])
    if 0xAC00 <= c <= 0xD7A3:
        return with_batchim if (c - 0xAC00) % 28 else without
    return without                       # 숫자·영문으로 끝나면 관례상 받침 없는 쪽


def _compare(rows):
    """여러 계열을 나란히 놓은 블록의 해석 한 줄. 하나뿐이면 None.

       막대만 던져 놓으면 '누가 앞서고 있나'를 매번 눈으로 재야 한다.
       선두와 2위의 격차를 전주와 견줘 '벌어졌나 좁혀졌나'를 문장으로 준다.
       (얀덱스처럼 절대 검색수인 블록은 단위가 달라 격차를 %p 로 못 읽으므로 건너뛴다)"""
    if len(rows) < 2 or any(r["raw"].get("peak") for r in rows):
        return None
    cur = sorted(rows, key=lambda x: -x["raw"]["last"])
    top, sec = cur[0]["raw"], cur[1]["raw"]

    def prev(r):
        c = _clean(r["s"])
        return c[-2] if len(c) > 1 else None

    gap = top["last"] - sec["last"]
    pt, ps = prev(top), prev(sec)
    pgap = (pt - ps) if (pt is not None and ps is not None) else None
    t, s = top["kw"], sec["kw"]
    si, tw = _josa(s, "이", "가"), _josa(t, "과", "와")
    if gap <= 3:
        return f"{s}{si} {t}{tw} 대등 (격차 {gap:.0f}p)"
    if pgap is None:
        return f"{t} 선두 (2위 {s}{_josa(s, '과', '와')} {gap:.0f}p)"
    if pgap - gap >= 3:
        return f"{s}{si} {t} 추격 중 (격차 {pgap:.0f}→{gap:.0f}p)"
    if gap - pgap >= 3:
        return f"{t} 격차 확대 ({pgap:.0f}→{gap:.0f}p)"
    return f"{t} 선두 유지 (격차 {gap:.0f}p)"


def _arw(c):
    """등락 방향 — 한국식 색(상승 빨강·하락 파랑).
       텔레그램은 이모지로만 색을 낼 수 있다. 예전엔 네모+삼각형을 겹쳐 썼는데
       기호가 둘이라 지저분했다. 부호(+/-)가 이미 방향을 말하므로 색 하나면 충분하다."""
    return "🔴" if c > 0 else "🔵"


# 카테고리 아이콘 — 급변 목록을 훑을 때 '어느 판이 움직였나'가 글자보다 먼저 들어온다.
CAT_ICON = {"화장품": "💄", "미용": "💉", "유통": "🛒", "음식료": "🍜",
            "엔터": "🎤", "게임": "🎮", "호텔·레져": "🏨", "호텔레져": "🏨"}


def _cat(rec, name):
    r = rec.get(name)
    if not r:
        return ""
    return r.get("sub", "") if r.get("sector") == "소비재" else r.get("sector", "")


def _prev_bday(d):
    """직전 영업일 — 등락(직전 세션 결과)에 인과가 될 수 있는 뉴스 창의 시작점.
       화~금: 전 영업일=어제. 월: 전 영업일=금요일(주말 갭 포함)."""
    x = d - datetime.timedelta(days=1)
    while x.weekday() >= 5:
        x -= datetime.timedelta(days=1)
    return x


# 제목에 쓰이는 다른 표기. 커버리지 이름과 기사 표기가 다른 것만 적는다.
ALIAS = {
    "NC": ("엔씨소프트", "엔씨"),
    "JYP Ent.": ("JYP",),
    "와이지엔터": ("YG엔터", "와이지엔터"),
    "에스엠": ("SM엔터", "에스엠"),
    "앨엔씨바이오": ("엘앤씨바이오",),
    "서부T&D": ("서부티엔디",),
    "달바글로벌": ("달바",),
    "SAMG엔터": ("SAMG",),
    "롯데관광개발": ("롯데관광",),
    "LG생활건강": ("LG생건",),
}


def _match(item, name):
    """뉴스 1건이 이 종목 건인지 — 제목에 종목명(또는 다른 표기)이 있어야 한다.

       예전엔 수집기가 붙인 co 태그만 있어도 인정했다. 그 탓에 종목이 스쳐
       언급된 업종 기사('AI가 살린 메타버스 ETF' → 펄어비스)가 급등 이유로 붙었다.
       제목에 이름조차 없는 기사는 그 종목이 움직인 이유가 아니다."""
    t = item.get("t") or ""
    return any(a in t for a in (name,) + ALIAS.get(name, ()))


# 헤드라인에서 '무슨 일인가'를 뽑는 사전. 앞에서 걸리는 것부터 본다.
# 기사 제목을 그대로 옮기면 신문 문구(따옴표·말줄임·부제)가 그대로 들어와 읽기 나쁘다.
# 종류를 먼저 정하고, 제목은 근거로 짧게만 붙인다.
# 헤드라인 종류 → 아이콘. 종류 이름을 글자로 또 적지는 않는다 —
# 아이콘이 이미 말해 주는데 '계약 · ' 을 덧붙이면 정작 내용이 잘려 나간다.
GIST = [
    ("🤝", ("공동제작", "수주", "공급계약", "계약 체결", "납품", "MOU", "파트너십", "협약")),
    ("🌏", ("진출", "수출", "입점", "런칭", "론칭", "출시", "확장", "오픈")),
    ("💰", ("자사주", "배당", "주주환원", "소각")),
    ("🏦", ("유상증자", "전환사채", "CB 발행", "신주인수권")),
    ("🔗", ("인수", "합병", "지분 취득", "매각", "분할")),
    ("📑", ("목표주가", "투자의견", "커버리지 개시", "상향", "하향")),
    ("⚠️", ("소송", "제재", "조사", "리콜", "규제", "과징금", "횡령")),
    ("🏭", ("증설", "공장", "생산능력", "CAPA", "가동")),
]


def _gist(title, nm):
    """기사 제목 -> 아이콘 + 핵심 절 한 줄.
       제목 앞에 붙는 '회사명,' 과 부제(… 뒤)를 떼고 앞 절만 남긴다.
       신문 문구를 그대로 옮기면 따옴표·말줄임·부제가 섞여 읽기 나쁘다."""
    if not title:
        return None
    t = re.sub(r"^\s*[\[\(]?%s[\]\)]?\s*[,·:\-]\s*" % re.escape(nm), "", title).strip()
    t = re.split(r"\.\.\.|…|\|", t)[0].strip(" ,·-—")
    icon = next((e for e, ws in GIST if any(w in title for w in ws)), "📰")
    return f"{icon} {_cut(t, REASON_W - 2)}"


def _news(items, name, cut):
    """종목 관련, 날짜가 cut(직전 영업일) 이후인 최신 기사 제목. 없으면 None.
       cut 밖(오래된) 기사는 이번 등락과 인과가 없으므로 붙이지 않는다."""
    cand = [x for x in items if _match(x, name) and x.get("d", "")[:10] >= cut]
    if not cand:
        return None
    cand.sort(key=lambda x: x.get("d", ""), reverse=True)
    return _gist(cand[0]["t"], name)


_QLAST = {3: 31, 6: 30, 9: 30, 12: 31}


def _qn(k):
    return {"03": "1Q", "06": "2Q", "09": "3Q", "12": "4Q"}.get(k[4:6], k) if len(k) >= 6 else k


def _surprise(live, nm, chg, today):
    """발표된 최근 분기의 '실제 vs consSnap 컨센' → 서프라이즈 × 주가방향 해석 한 줄. 없으면 None.
       컨센(consSnap)이 보존돼 있고 시계열이 실제(e=False)로 바뀐, 분기말 80일 내 분기만 본다
       (오래된 분기를 이번 급변에 오귀속하지 않도록)."""
    r = (live.get("stocks") or {}).get(nm) or {}
    snap = (live.get("consSnap") or {}).get(nm) or {}
    qser = ((r.get("cons") or {}).get("quarter") or {}).get("series") or []
    hit = None
    for x in reversed(qser):
        k = x.get("k", "")
        if x.get("e") or k not in snap or len(k) < 6:   # 아직 컨센(추정)이거나 스냅샷 없음
            continue
        try:
            qe = datetime.date(int(k[:4]), int(k[4:6]), _QLAST.get(int(k[4:6]), 28))
        except ValueError:
            continue
        if (today - qe).days > 80:      # 오래된 분기 → 이번 급변과 무관
            break
        hit = x
        break
    if not hit:
        return None
    c = snap[hit["k"]]
    qn = _qn(hit["k"])
    co, ao, cr, ar = c.get("op"), hit.get("op"), c.get("rev"), hit.get("rev")
    up = chg > 0
    beat = miss = False
    if co is not None and ao is not None:
        if co < 0 <= ao:
            vs, beat = f"{qn} 영업 흑자전환(컨센 상회)", True
        elif ao < 0 <= co:
            vs, miss = f"{qn} 영업 적자전환(컨센 하회)", True
        elif co < 0 and ao < 0:                          # 둘 다 적자 → 축소/확대
            better = ao > co
            vs = f"{qn} 영업적자 {'축소' if better else '확대'}(컨센 {'상회' if better else '하회'})"
            beat, miss = better, not better
        else:
            base = abs(co) or abs(ao) or 1
            pct = (ao - co) / base * 100
            if pct >= 5:
                vs, beat = f"{qn} 영업익 컨센 {pct:+.0f}% 상회", True
            elif pct <= -5:
                vs, miss = f"{qn} 영업익 컨센 {pct:.0f}% 하회", True
            else:
                vs = f"{qn} 영업익 컨센 부합"
    elif cr and ar:                                      # 영업익 없으면 매출로
        pct = (ar / cr - 1) * 100
        if pct >= 5:
            vs, beat = f"{qn} 매출 컨센 {pct:+.0f}% 상회", True
        elif pct <= -5:
            vs, miss = f"{qn} 매출 컨센 {pct:.0f}% 하회", True
        else:
            vs = f"{qn} 매출 컨센 부합"
    else:
        return None
    if beat and up:
        return f"{vs}, 호실적 반영"
    if beat and not up:
        return f"{vs}에도 하락 → 셀온"
    if miss and not up:
        return f"{vs}, 실적 부진 반영"
    if miss and up:
        return f"{vs}에도 상승 → 악재 선반영/저점매수"
    return vs                                            # 컨센 부합


def build(html, alerts_only=False):
    today = datetime.datetime.now(KST).date()
    tr = _const(html, "TREND") or {"groups": {}}
    live = _const(html, "LIVE") or {}
    evs = _const(html, "DART_EVENTS", "[") or []
    mv = _const(html, "MOVIE") or {}
    data = _const(html, "DATA") or {"records": []}
    news = _const(html, "NEWS") or {"items": []}
    rec = {r["name"]: r for r in data.get("records", [])}
    nitems = news.get("items") or []
    news_cut = _prev_bday(today).isoformat()   # 이 등락과 인과 가능한 뉴스 창 시작(직전 영업일)

    end = (today + datetime.timedelta(days=EVENT_DAYS)).isoformat()
    soon = sorted([e for e in evs if e.get("type") in ("earn", "ir")
                   and today.isoformat() <= e.get("date", "") <= end], key=lambda e: e["date"])
    movers = sorted([(s.get("chgPct"), nm) for nm, s in (live.get("stocks") or {}).items()
                     if s.get("chgPct") is not None and abs(s["chgPct"]) >= CHG_ALERT],
                    key=lambda x: -abs(x[0]))
    notable = _notable(tr)

    chg_of = {nm: c for c, nm in movers}

    # 같은 카테고리가 통째로 움직였는지 — 개별 재료가 없을 때의 기본 설명.
    # 종목 뉴스가 없다고 '이유 없음'으로 두면, 실은 섹터 전반이 움직인 날을 놓친다.
    def _sector_move(nm):
        cat = _cat(rec, nm)
        if not cat:
            return None
        peers = [n for n, r in rec.items() if _cat(rec, n) == cat and n != nm]
        chgs = [(live.get("stocks") or {}).get(n, {}).get("chgPct") for n in peers]
        chgs = [c for c in chgs if c is not None]
        if len(chgs) < 3:
            return None
        me = chg_of.get(nm, 0)
        same = [c for c in chgs if (c > 0) == (me > 0) and abs(c) >= 1.5]
        if len(same) < len(chgs) * 0.6:
            return None
        return f"{cat} 섹터 전반 {'강세' if me > 0 else '약세'}(동반 {len(same)}/{len(chgs)}종목)"

    # 그 종목의 트렌드가 같은 방향으로 튀었는지 — 수요 쪽 근거가 되는 유일한 자체 데이터
    def _trend_move(nm):
        for r in notable:
            if r["stock"] != nm or r["w"] is None or abs(r["w"]) < SPIKE:
                continue
            if (r["w"] > 0) == (chg_of.get(nm, 0) > 0):
                return f"{r['kw']} 트렌드 전주비 {r['w']:+.0f}% 동반"
        return None

    def _why(nm):
        """키 없이 도는 규칙기반 이유. 근거가 센 순서로 본다.
           실적 > 그 밖의 공시 > 뉴스 헤드라인 > 트렌드 동반 > 섹터 전반.
           (예전엔 Claude API 로 추론했으나 키를 쓰지 않기로 해서 규칙만 남겼다.
            지어내지 않는 게 원칙이라, 아무 근거도 없으면 아무 말도 붙이지 않는다.)"""
        disc = [e for e in evs if e.get("co") == nm
                and news_cut <= e.get("date", "") <= today.isoformat()]
        head = _news(nitems, nm, news_cut)
        # 한 줄에 하나만 담는다. 예전엔 '공시: … · 뉴스헤드라인…' 처럼 둘을 이어 붙여
        # 줄이 넘쳤고, 넘친 줄은 들여쓰기를 잃고 왼쪽 끝에 붙어 모양이 깨졌다.
        if any(e.get("type") == "earn" for e in disc):
            sur = _surprise(live, nm, chg_of.get(nm, 0), today)
            if sur:
                return "📊 " + _cut(sur, REASON_W)           # 실제치 vs 컨센이 잡히면 그 해석이 이유
            # head 에는 _gist 가 이미 아이콘을 붙여 놨다. 앞에 📊 를 또 달면 아이콘이 겹친다.
            return "📊 실적발표" if not head else f"📊 실적발표 {head}"
        if disc:                                             # 실적 외 공시(IR·계약 등)
            return "📄 " + _cut(disc[0].get("title") or "공시", REASON_W)
        if head:
            return head                                      # _gist 가 이미 종류+이모지를 붙였다
        tm = _trend_move(nm)
        if tm:
            return "🔍 " + _cut(tm, REASON_W)
        sm = _sector_move(nm)
        return ("🏷 " + _cut(sm, REASON_W)) if sm else None

    # 오늘의 포인트
    pts = []
    for e in [x for x in soon if x["type"] == "earn"
              and (datetime.date.fromisoformat(x["date"]) - today).days <= 1][:2]:
        dd = (datetime.date.fromisoformat(e["date"]) - today).days
        pts.append(f"📊 {'오늘' if not dd else '내일'} <b>{e['co']}</b> 실적발표")
    sp = next((r for r in notable
               if r["w"] is not None and abs(r["w"]) >= SPIKE and r["last"] >= NOTABLE_BASE), None)
    if sp:
        pts.append(f"{'🔥' if sp['w'] > 0 else '🧊'} <b>{sp['stock']}</b> "
                   f"{LABEL.get((sp['group'], sp['kw']), sp['kw'])} 트렌드 {sp['w']:+.0f}%")
    # 급변 1위는 여기 안 적는다 — 바로 아래 '전일 급변' 첫 줄과 똑같은 내용이라
    # 같은 문장이 두 번 나오고, 이유까지 달면 줄이 넘쳐 줄바꿈이 깨진다.

    # ── 본문 ───────────────────────────────────────────────
    # 이모지는 섹션 머리에 1개씩만. 본문 줄에는 색(등락)만 쓴다.
    # 예전엔 줄마다 🟥▲ / 🔥급등 / ↗4주 가 겹쳐 붙어 읽는 데 방해가 됐다.
    # 부호와 숫자가 이미 방향·세기를 말하므로 기호를 더 얹지 않는다.
    out = []
    if pts:
        out.append("<b>✨ 오늘의 포인트</b>\n" + "\n".join("• " + p for p in pts))

    # 전일 시세 급변 — 가장 먼저. 오늘 당장 대응할 게 있다면 여기다.
    if movers:
        lines = []
        for c, nm in movers[:MOVERS_MAX]:
            cat = _cat(rec, nm)
            rs = _why(nm)
            lines.append(f"{_arw(c)} <b>{nm}</b> {c:+.1f}%"
                         + (f"  {CAT_ICON.get(cat, '')}<i>{cat}</i>" if cat else "")
                         + (f"\n    {rs}" if rs else ""))
        extra = (f"\n<i>외 {len(movers)-MOVERS_MAX}종목</i>"
                 if len(movers) > MOVERS_MAX else "")
        out.append(f"<b>📈 전일 급변</b> <i>(±{CHG_ALERT:.0f}%)</i>\n" + "\n".join(lines) + extra)

    # 트렌드 데이터 — 고정 계열은 매일, 나머지는 의미있게 움직였을 때만. 최근 10주 추이.
    # (종목, 그룹)이 같으면 한 블록으로 묶는다 — 리쥬란/리투오/셀르디엠처럼
    #  나란히 놓여야 '누가 뺏겼나'가 보이는 것들이 있다.
    if not alerts_only and notable:
        # 먼저 그룹별로 모은다. 자리(폭)는 그룹 안에서만 맞추면 된다 —
        # 비교는 같은 그룹 안에서 일어나고, 그룹마다 단위가 다르다(0~100 vs 주당 건수).
        # 종목 단위로 묶는다. 그룹명은 그 그룹이 두 계열 이상을 낼 때만 붙인다 —
        # 계열이 하나뿐이면 '변신로봇 IP 러시아 / 메탈카드봇' 처럼 같은 말을 두 번 하는 셈이다.
        # 출처(네이버·얀덱스)는 아예 뺐다. 단위가 이미 성격을 말한다
        # (0~100 = 상대지수 / N건 = 얀덱스 절대 검색수).
        gcount = {}
        for r in notable:
            gcount[(r["stock"], r["group"])] = gcount.get((r["stock"], r["group"]), 0) + 1

        blocks = []
        for r in notable:
            if not blocks or blocks[-1]["stock"] != r["stock"]:
                blocks.append({"stock": r["stock"], "groups": [], "rows": []})
            b = blocks[-1]
            if gcount[(r["stock"], r["group"])] > 1 and r["group"] not in b["groups"]:
                b["groups"].append(r["group"])
            b["rows"].append({
                "label": _cut(LABEL.get((r["group"], r["kw"]), r["kw"]), LABEL_W),
                "spark": _spark(r["s"]),
                # 얀덱스는 절대 검색수라 실제 건수를 그대로 쓴다. 나머지는 0~100 상대값.
                "lvl": (f"{round(r['last'] / 100 * r['peak']):,}건"
                        if r["peak"] else f"{r['last']:.0f}/100"),
                "wow": "" if r["w"] is None else f"{r['w']:+.0f}%",
                # 연속 추세는 '4주' 로만 적으니 무슨 뜻인지 알 수 없었다. 방향까지 적는다.
                "tail": (f" · {abs(r['streak'])}주 연속 {'상승' if r['streak'] > 0 else '하락'}"
                         if abs(r["streak"]) >= STREAK_MIN else ""),
                "raw": r})

        # 자리는 레터 전체에서 한 번만 잡는다.
        # 블록마다 따로 맞추면 블록이 바뀔 때마다 막대 시작점이 밀려서,
        # 겹쳐 보라고 넣은 스파크라인이 오히려 들쭉날쭉해 보인다.
        # 막대를 맨 앞에 둔다.
        #
        # 한글을 앞에 두고 폭을 맞추려던 시도가 두 번 다 실패했다.
        #   1차: 보통 공백으로 채움 → 텔레그램 글꼴에서 한글이 영문의 2배가 아니라
        #        1.82배라 한글 글자 수가 다르면 폭이 달라졌다.
        #   2차: 부족분을 전각공백(U+3000)으로 채움 → 브라우저(Consolas+맑은고딕)에서는
        #        딱 맞았지만 텔레그램에서는 여전히 밀렸다. 전각공백과 한글이
        #        같은 폭이 아닌 글꼴을 쓴다는 뜻이다.
        # 남의 글꼴 지표에 기대는 방식 자체가 틀렸다.
        # 막대를 첫 칸에 두면 앞에 채울 게 없어 어떤 글꼴에서도 반드시 맞는다.
        # 막대 뒤 숫자는 전부 ASCII 라 보통 공백으로 맞고, 이름은 정렬이 필요 없으니
        # 코드 블록 밖으로 빼서 굵게 쓴다(<code> 안에서는 굵게가 안 먹는다).
        rows = [x for b in blocks for x in b["rows"]]
        vw = max(_w(x["lvl"]) for x in rows)
        ww = max(len(x["wow"]) for x in rows)

        lines = []
        for b in blocks:
            if lines:
                lines.append("")                       # 종목 사이 한 줄 띄움
            solo = len(b["rows"]) == 1
            # 계열이 하나면 이름을 머리줄에 합친다 — 굳이 두 줄을 쓸 이유가 없다.
            lines.append(f"<b>{b['stock']}</b>"
                         + (" · " + " · ".join(b["groups"]) if b["groups"] else "")
                         + (" · " + b["rows"][0]["label"] if solo and not b["groups"] else ""))
            for x in b["rows"]:
                lines.append("<code>" + x["spark"] + " " + _pad(x["lvl"], vw, True)
                             + (" " + _pad(x["wow"], ww, True) if ww else "") + "</code>"
                             + ("" if solo and not b["groups"] else "  <b>" + x["label"] + "</b>")
                             + x["tail"])
            # 여러 계열을 나란히 놓은 블록엔 해석을 한 줄 붙인다.
            # 막대만 보고 '누가 앞서고 있나'를 매번 눈으로 재게 하지 않기 위해서다.
            cmp = _compare(b["rows"])
            if cmp:
                lines.append(f"<i>↳ {cmp}</i>")
        out.append("<b>📊 트렌드 데이터</b> <i>(최근 10주 · 전주비)</i>\n" + "\n".join(lines))

    # 임박 일정
    if soon:
        lines = []
        # 날짜별로 한 줄. 같은 날 여러 종목이면 한 줄에 모은다 —
        # 줄마다 날짜를 되풀이하니 눈이 어디를 봐야 할지 몰랐다.
        # 자리를 맞추는 칸은 D-day 하나뿐이다. 순수 ASCII 라 어떤 글꼴에서도 맞는다.
        byday = {}
        for e in soon[:10]:
            byday.setdefault(e["date"], []).append(e)
        for d in sorted(byday)[:5]:
            dt = datetime.date.fromisoformat(d)
            dd = (dt - today).days
            body = " · ".join(f"<b>{e['co']}</b> {'실적' if e['type'] == 'earn' else 'IR'}"
                              for e in byday[d])
            # 'D-0 오늘' 은 같은 말을 두 번 하는 것이라 날짜(요일)를 대신 붙인다.
            lines.append(f"<code>{_pad(f'D-{dd}', 3)} {d[5:7]}/{d[8:10]}({WD[dt.weekday()]})"
                         f"</code>  {body}")
        out.append("<b>📅 임박 일정</b>\n" + "\n".join(lines))

    # 예매 — 개봉 전 유일한 실시간 지표. 여러 편이면 한 섹션에 묶는다.
    bk = [(nm, p) for nm, p in (mv.get("booking") or {}).items() if p]
    if bk:
        lines = []
        for nm, ptsB in bk:
            p, prv = ptsB[-1], (ptsB[-2] if len(ptsB) > 1 else None)
            dr = f" ({p['rate']-prv['rate']:+.1f}%p)" if prv else " (수집 시작)"
            lines.append(f"<b>{nm.split(':')[0]}</b>  예매율 {p['rate']}%{dr} · "
                         f"예매 {p['book']:,}명")
        out.append("<b>🎬 예매</b>\n" + "\n".join(lines))

    if alerts_only:
        keep = [b for b in out if not b.startswith("<b>📊")]
        head = f"⏰ <b>커버리지 알림</b> · {today:%m/%d}({WD[today.weekday()]})"
        return (head + "\n\n" + "\n\n".join(keep)) if keep else ""

    head = f"🗞 <b>커버리지 데일리</b> · {today:%m/%d}({WD[today.weekday()]})"
    return (head + "\n\n" + ("\n\n".join(out) if out else "특이사항 없음.")
            + "\n\n<i>coverage-dashboard.pages.dev</i>")


def main():
    html = open(HTML, encoding="utf-8").read()
    msg = build(html, alerts_only=("--alerts" in sys.argv))
    if not msg:
        print("보낼 내용 없음."); return
    if "--dry-run" in sys.argv:
        print("─" * 52); print(re.sub(r"<[^>]+>", "", msg)); print("─" * 52)
        print(f"(dry-run · {len(msg)}자)")
    else:
        if not telegram_send.send(msg):
            sys.exit(1)


if __name__ == "__main__":
    main()
