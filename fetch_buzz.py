# -*- coding: utf-8 -*-
"""
종목 무관 '지금 화제' 수집 — 구글 트렌드 · 네이트 · 나무위키 · 디시 흥한 마이너갤.
(2026-09-07 신설 · 2026-09-08 구글·네이트 추가. 트렌드 탭 맨 위 '지금 화제' 섹션.)

기존 트렌드 데이터는 전부 '종목 -> 주제' 구조다. 그래서 **우리가 이미 보고 있는 것만 보인다.**
이건 반대 방향이다 — 한국 인터넷 전체에서 지금 뭐가 뜨는지 먼저 보고, 그 중에 우리 종목이
있으면 배지를 단다. 커버리지 밖에서 올라오는 것을 알아채는 게 목적이다.

소스 — 넷 다 키·로그인 없이 urllib 로 열린다(2026-09-08 실측):

  구글      trends.google.com/trending/rss?geo=KR  -> 급상승 검색어 + **approx_traffic**(2000+·1000+·500+)
            + 관련 기사 3건. **셋 중 유일하게 '규모'가 붙는다** — 나무위키·네이트는 순위뿐이라
            1위가 얼마나 큰 건지 알 수 없다. 그래서 이걸 제일 위에 놓는다.
            ⚠ 옛 주소 `/trends/trendingsearches/daily/rss?geo=KR` 는 404 다(2026-09-08 실측).

  네이트    nate.com/js/data/jsonLiveKeywordDataV1.js -> [순위, 이슈문구, 등락기호, 변동폭, 검색어]
            **euc-kr** 이고 JSON 배열이다. 등락기호: n=신규 · +=상승 · -=하락 · s(또는 그 외)=유지.
            '이슈 문구'(사람이 읽는 한 줄)와 '실제 검색어'가 따로 온다 — 배지 매칭은 둘 다 본다.

  나무위키  search.namu.wiki/api/ranking   -> 문자열 10개(실시간 검색어). 점수·순위변동 없음.
            ⚠ **스냅샷이다.** 과거를 주지 않으므로 매 회차 찍어 쌓는 수밖에 없다.
            그래서 일별로 '그날 몇 회차에 등장했나'(kw[키워드] / n)를 센다 — 한 번 스친 것과
            하루 종일 걸려 있던 것이 갈린다. 수집이 장중에 몰리는 시각 편향이 있으므로
            회차 수 n 을 반드시 같이 남긴다(n 이 다른 날끼리 등장횟수를 직접 비교하면 안 된다).

  디시      gall.dcinside.com/m 의 '흥한갤 전체 순위' 레이어 -> **한 번의 요청에 300위 전부** SSR.
            (3개 <ul> 로 나뉘어 있을 뿐 페이지네이션 요청이 따로 없다.)
            사이트 정의: 전체 마이너 갤러리 순위 중 300위 이내 = 흥한갤, 20위 이내 = 대흥갤.
            ⚠ json2.dcinside.com/json0/gallmain/gallery_hot.php 는 **정식 갤러리 100위**다(마이너 0개).
              우리 커버리지 갤은 거의 다 마이너갤이라 그쪽은 안 쓴다.

DCGALL(글 수) 과 겹치는 게 아니라 보완이다 — 글 수는 **양**, 순위는 **전체 대비 상대 온도**다.
글이 줄어도 순위가 버티면 판 전체가 식은 것이고, 글은 그대로인데 순위가 밀리면 우리만 식은 것이다.

저장(BUZZ):
  gt.snap[]    최근 회차 {t, kw:[{kw,tr,n}]}               — 구글, tr 이 검색량 규모
  gt.days[]    {d, n:관측회차, kw:{키워드:등장회차}}
  nate.snap[]  최근 회차 {t, rows:[{r,t,kw,d,v}]}          — 네이트, d 가 등락기호
  namu.snap[]  최근 회차 {t, kw:[...]}                     — 화면 '지금'
  namu.days[]  {d, n:관측회차, kw:{키워드:등장회차}}        — 최근 60일
  dc.top[]     오늘 상위 20 {r, id, name, pr:전일순위}       — 화면 '지금'
  dc.galls[]   커버리지 매칭 갤 {stock,name,id,hist:[{d,r}]} — r=null 은 300위 밖

  python fetch_buzz.py            # 수집·기록
  python fetch_buzz.py --dry-run  # 출력만
"""
import re, json, sys, html as htmlmod, copy, datetime, urllib.request
from collector_health import ua, note_health

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
# ⚠ 상장사 사전을 넓히니 300개 중 69개가 걸렸다. 전부 400일씩 담으면 블록이 800KB 가 된다
#   (index.html 이 통째로 커져 배포마다 그만큼 나간다). 그래서 두 가지로 줄인다:
#   ① 보관 180일  ② 비커버리지는 **한 번이라도 상위 60위에 든 갤만** 추적 시작.
#   커버리지 종목은 순위와 무관하게 계속 담는다 — 권외로 밀린 것도 정보다.
DAYS = 180          # 갤러리 순위 보관 일수
NEW_RANK_CUT = 60   # 비커버리지 갤을 새로 추적하기 시작하는 순위 문턱
MAX_GALLS = 80      # 추적 갤 총 상한
NAMU_DAYS = 60      # 검색어 일별 집계 보관 일수
SNAPS = 12          # 최근 회차 스냅샷 보관 수
TOP_N = 20          # 화면에 띄우는 상위 갤 수 (= 사이트의 '대흥갤' 경계)

NAMU_URL = "https://search.namu.wiki/api/ranking"
DC_URL = "https://gall.dcinside.com/m"
GT_URL = "https://trends.google.com/trending/rss?geo=KR"
NATE_URL = "https://www.nate.com/js/data/jsonLiveKeywordDataV1.js"

# ══════════════════════════════════════════════════════════════════════════
# 상장사 사전 — '지금 화제' 의 핵심.
#
# 순위 목록 자체는 리서치가 아니다. "치지직 1위 · F1 3위"는 그냥 인터넷 잡담이다.
# 쓸모는 **상장사로 번역했을 때** 생긴다 — 블루 아카이브가 8위라는 사실은
# '넥슨게임즈(225570)' 로 읽혀야 의미가 된다.
#
# 그래서 커버리지 밖 상장사도 같이 담는다. 우리가 안 보는 종목이라도,
# 그 IP 가 뜨고 있다는 건 섹터 온도이자 경쟁 지형이다.
#
# ⚠ **확실한 것만 넣는다.** 개발사·퍼블리셔·모회사가 갈리는 경우가 많아 짐작하면 틀린다.
#    애매하면 넣지 않는다 — 틀린 배지는 없느니만 못하다.
#    (리센느·QWER·이세계아이돌 등은 소속사 확인이 안 돼 뺐다. 스텔라이브·미호요·쿠로게임즈·
#     스마일게이트·하이퍼그리프·Battlestate 는 비상장이라 뺐다.)
# ⚠ 키워드는 **좁게.** '제우스' 두 글자는 최우제 갤을 물고, '니케'는 나이키와 겹칠 수 있다.
#
# 한 항목이 여러 상장사에 걸리는 게 정상이다(블루 아카이브 = 넥슨게임즈 개발 + 넥슨 퍼블리싱).
# 그래서 값은 리스트다. 화면은 커버리지를 앞에 세우고 나머지를 병기한다.
#
# 형식: (키워드들, [(종목명, 코드, 시장, 커버리지여부), ...])
COV = 1
LISTED = [
    # ── 커버리지 종목 ───────────────────────────────────────────────
    (["아이온", "리니지", "쓰론 앤 리버티", "저니 오브 모나크", "블레이드 앤 소울"],
                                        [("NC", "036570", "KOSPI", COV)]),
    (["제우스 오만", "컴투스프로야구", "컴투스", "서머너즈 워", "서머너즈워"],
                                        [("컴투스", "078340", "KOSDAQ", COV)]),
    (["붉은사막", "검은사막", "도깨비(게임"], [("펄어비스", "263750", "KOSDAQ", COV)]),
    (["배틀그라운드", "PUBG", "인조이", "다크앤다커"], [("크래프톤", "259960", "KOSPI", COV)]),
    (["스텔라 블레이드", "스텔라블레이드", "승리의 여신", "니케"],
                                        [("시프트업", "462870", "KOSPI", COV)]),
    (["쿠키런"],                          [("데브시스터즈", "194480", "KOSDAQ", COV)]),
    (["탑툰"],                            [("탑코미디어", "134580", "KOSDAQ", COV)]),
    (["티니핑", "미니특공대"],               [("SAMG엔터", "419530", "KOSDAQ", COV)]),
    # 트릭컬 리바이브는 에피드게임즈 개발 · **하이브IM 퍼블리싱**이라 하이브에 걸린다.
    (["방탄소년단", "세븐틴", "뉴진스", "르세라핌", "아일릿", "투모로우바이투게더",
      "프로미스나인", "위버스", "트릭컬"],     [("하이브", "352820", "KOSPI", COV)]),
    (["트와이스", "스트레이 키즈", "엔믹스", "NMIXX", "데이식스"],
                                        [("JYP Ent.", "035900", "KOSDAQ", COV)]),
    (["에스파", "엔시티", "NCT", "레드벨벳"], [("에스엠", "041510", "KOSDAQ", COV)]),
    (["블랙핑크", "베이비몬스터"],            [("와이지엔터", "122870", "KOSDAQ", COV)]),
    (["바나나맛우유", "메로나", "붕어싸만코", "빙그레"],
                                        [("빙그레", "005180", "KOSPI", COV)]),
    (["불닭"],                            [("삼양식품", "003230", "KOSPI", COV)]),
        # ── 커버리지 밖 **국내 상장사** — 섹터 온도·경쟁 지형 ─────────────
    # ⚠ **해외 상장사는 넣지 않는다** (2026-09-08 정리). 디시 마이너갤 순위로
    #    넥슨(도쿄)·텐센트(홍콩)·닌텐도·MS·코나미를 따라가는 건 무리다 —
    #    한국 커뮤니티 한 곳의 순위가 그 회사 실적·주가에 닿는 경로가 없다.
    #    한때 넣었다가 표가 해외 종목으로 절반이 차서 정작 국내 종목이 안 읽혔다.
    #    블루 아카이브는 **넥슨게임즈(225570, 코스닥)가 개발사**라 그쪽으로만 남긴다.
    # ⚠ 그래서 던파·메이플·마비노기·포켓몬·우마무스메·유희왕 같은 키워드도 뺐다 —
    #    국내 상장 주체가 없다. 억지로 모회사를 붙이면 위와 같은 문제가 돌아온다.
    (["블루 아카이브", "블루아카이브", "퍼스트 디센던트", "서든어택"],
                                        [("넥슨게임즈", "225570", "KOSDAQ", 0)]),
    (["세븐나이츠", "나 혼자만 레벨업", "모두의마블", "제2의나라"],
                                        [("넷마블", "251270", "KOSPI", 0)]),
    (["오딘", "아키에이지", "패스 오브 엑자일", "패스오브엑자일"],
                                        [("카카오게임즈", "293490", "KOSDAQ", 0)]),
    (["디제이맥스", "P의 거짓", "브라운더스트"], [("네오위즈", "095660", "KOSDAQ", 0)]),
    (["미르", "나이트크로우"],               [("위메이드", "112040", "KOSDAQ", 0)]),
    (["치지직", "네이버웹툰", "제페토"],       [("네이버", "035420", "KOSPI", 0)]),
    (["카카오페이지", "멜론"],                [("카카오", "035720", "KOSPI", 0)]),
    (["아프리카TV", "SOOP"],               [("SOOP", "067160", "KOSDAQ", 0)]),
    (["레진코믹스"],                        [("키다리스튜디오", "020120", "KOSPI", 0)]),
    (["티빙", "스튜디오드래곤"],              [("CJ ENM", "035760", "KOSPI", 0)]),
]

# 갤러리 '이름'으로 상장사를 찾는다. id 로 하면 새 갤이 생겼을 때 못 잡는다.
COVER_KW = [(kw, hits) for kw, hits in LISTED]
UA = ua(referer="https://gall.dcinside.com/")


def _get(url, ref=None, enc="utf-8"):
    h = dict(UA)
    if ref:
        h["Referer"] = ref
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode(enc, "replace")


def _const(html_, name):
    m = re.search(r"const %s\s*=\s*(\{.*?\});" % re.escape(name), html_, re.S)
    return json.loads(m.group(1)) if m else None


def _put(html_, name, obj):
    block = "const %s = %s;" % (name, json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
    pat = re.compile(r"const %s\s*=\s*\{.*?\};" % re.escape(name), re.S)
    if pat.search(html_):
        return pat.sub(lambda m: block, html_, count=1)
    liv = re.search(r"const LIVE\s*=\s*\{.*?\};", html_, re.S)
    if not liv:
        raise RuntimeError("BUZZ 삽입 기준(const LIVE)을 못 찾음")
    return html_[:liv.end()] + "\n" + block + html_[liv.end():]


def hits_of(text):
    """이름에 걸리는 상장사들. [(종목명, 코드, 시장, 커버리지여부), ...] · 없으면 []."""
    t = str(text or "")
    out, seen = [], set()
    for kws, cos in LISTED:
        if any(k in t for k in kws):
            for c in cos:
                if c[0] not in seen:
                    seen.add(c[0]); out.append(c)
    # 커버리지를 앞에 세운다 — 화면에서 우리 종목이 먼저 읽혀야 한다.
    return sorted(out, key=lambda c: -c[3])


def stock_of(text):
    """대표 상장사 하나(커버리지 우선). 갤 추적 대상 선정에 쓴다."""
    h = hits_of(text)
    return h[0][0] if h else None


def fetch_namu():
    """실시간 검색어 10개. 문자열 배열이 그대로 온다."""
    j = json.loads(_get(NAMU_URL, ref="https://namu.wiki/"))
    kw = [str(x).strip() for x in j if str(x).strip()]
    if not kw:
        raise ValueError("검색어 0개")
    return kw


def fetch_google():
    """급상승 검색어 [{kw, tr(대략 검색량 문자열), n(관련기사 수)}, ...]. RSS 라 파서가 필요 없다."""
    t = _get(GT_URL)
    out = []
    for it in re.findall(r"<item>(.*?)</item>", t, re.S):
        ti = re.search(r"<title>(.*?)</title>", it, re.S)
        if not ti:
            continue
        tr = re.search(r"<ht:approx_traffic>(.*?)</ht:approx_traffic>", it, re.S)
        out.append({"kw": htmlmod.unescape(ti.group(1)).strip(),
                    "tr": (tr.group(1).strip() if tr else None),
                    "n": len(re.findall(r"<ht:news_item_title>", it))})
    if not out:
        raise ValueError("item 0개(RSS 구조 변경?)")
    return out


def fetch_nate():
    """[{r, t(이슈 문구), kw(검색어), d(등락기호), v(변동폭)}, ...]. euc-kr 이다."""
    t = _get(NATE_URL, ref="https://www.nate.com/", enc="euc-kr")
    j = json.loads(t[t.find("["):t.rfind("]") + 1])
    out = []
    for row in j:
        if not isinstance(row, list) or len(row) < 5:
            continue
        r, issue, sign, delta, kw = (str(x).strip() for x in row[:5])
        if not r.isdigit():
            continue
        out.append({"r": int(r), "t": issue, "kw": kw, "d": sign,
                    "v": int(delta) if str(delta).lstrip("-").isdigit() else 0})
    if not out:
        raise ValueError("행 0개")
    return sorted(out, key=lambda x: x["r"])


def fetch_dc():
    """흥한갤 300위 [(rank, id, name), ...]. 3개 <ul> 이 한 응답에 다 들어 있다."""
    h = _get(DC_URL)
    uls = re.findall(r'<ul class="pop_hotmgall_listbox"[^>]*>(.*?)</ul>', h, re.S)
    if not uls:
        raise ValueError("흥한갤 목록 블록 없음(마크업 변경?)")
    rows, seen = [], set()
    for ul in uls:
        for gid, r, nm in re.findall(
                r'href="/mgallery/board/lists/\?id=([^"]+)".*?<span class="num[^"]*">(\d+)\.</span>\s*([^<]+)</a>',
                ul, re.S):
            if gid in seen:
                continue
            seen.add(gid)
            rows.append((int(r), gid, htmlmod.unescape(nm).strip()))
    if len(rows) < 100:
        raise ValueError("목록 %d개뿐(파싱 실패?)" % len(rows))
    return sorted(rows)


def _same(a, b):
    return json.dumps(a, ensure_ascii=False, sort_keys=True) == json.dumps(b, ensure_ascii=False, sort_keys=True)


def main():
    html_ = open(HTML, encoding="utf-8").read()
    now = datetime.datetime.now(KST)
    today = now.date().isoformat()
    stamp = now.strftime("%Y-%m-%d %H:%M")
    prev = _const(html_, "BUZZ") or {}      # 비교용 원본 — 절대 수정하지 않는다
    # ⚠ 얕은 참조로 prev 를 제자리 수정하면 '변동 없음' 비교가 자기 자신과의 비교가 된다(2026-09-01 사고).
    old = copy.deepcopy(prev)

    fails = []

    # ── 나무위키 실시간 검색어 ─────────────────────────────────────────
    namu = old.get("namu") or {"src": "나무위키 실시간 검색어", "snap": [], "days": []}
    try:
        kw = fetch_namu()
        snap = [s for s in namu.get("snap", []) if s.get("t") != stamp]
        snap.append({"t": stamp, "kw": kw})
        namu["snap"] = snap[-SNAPS:]
        days = {d["d"]: d for d in namu.get("days", [])}
        day = days.setdefault(today, {"d": today, "n": 0, "kw": {}, "t": []})
        # 같은 회차(분 단위)가 이미 반영됐으면 두 번 세지 않는다 — 워커·cron 이중 발화 대비
        if stamp not in (day.get("t") or []):
            day["t"] = (day.get("t") or [])[-40:] + [stamp]
            day["n"] = day.get("n", 0) + 1
            for k in kw:
                day["kw"][k] = day["kw"].get(k, 0) + 1
        namu["days"] = sorted(days.values(), key=lambda x: x["d"])[-NAMU_DAYS:]
        namu["asOf"] = stamp
        print("[나무위키] %d개 · %s" % (len(kw), " · ".join(kw[:5])))
    except Exception as e:
        fails.append("나무위키: " + str(e)[:70])

    # ── 구글 트렌드 급상승(KR) ─────────────────────────────────────────
    # 셋 중 유일하게 검색량 규모가 붙는다. 나무위키와 같은 방식으로 '오늘 몇 회차에 걸렸나'를 센다.
    gt = old.get("gt") or {"src": "구글 트렌드 급상승(한국)", "snap": [], "days": []}
    try:
        rows = fetch_google()
        snap = [s for s in gt.get("snap", []) if s.get("t") != stamp]
        snap.append({"t": stamp, "kw": rows})
        gt["snap"] = snap[-SNAPS:]
        days = {d["d"]: d for d in gt.get("days", [])}
        day = days.setdefault(today, {"d": today, "n": 0, "kw": {}, "t": []})
        if stamp not in (day.get("t") or []):
            day["t"] = (day.get("t") or [])[-40:] + [stamp]
            day["n"] = day.get("n", 0) + 1
            for x in rows:
                day["kw"][x["kw"]] = day["kw"].get(x["kw"], 0) + 1
        gt["days"] = sorted(days.values(), key=lambda x: x["d"])[-NAMU_DAYS:]
        gt["asOf"] = stamp
        print("[구글] %d개 · %s" % (len(rows), " · ".join(f"{x['kw']}({x['tr']})" for x in rows[:4])))
    except Exception as e:
        fails.append("구글: " + str(e)[:70])

    # ── 네이트 실시간 이슈 ─────────────────────────────────────────────
    nate = old.get("nate") or {"src": "네이트 실시간 이슈", "snap": []}
    try:
        rows = fetch_nate()
        snap = [s for s in nate.get("snap", []) if s.get("t") != stamp]
        snap.append({"t": stamp, "rows": rows})
        nate["snap"] = snap[-SNAPS:]
        nate["asOf"] = stamp
        print("[네이트] %d개 · %s" % (len(rows), " · ".join(x["t"][:14] for x in rows[:4])))
    except Exception as e:
        fails.append("네이트: " + str(e)[:70])

    # ── 디시 흥한 마이너갤 순위 ────────────────────────────────────────
    dc = old.get("dc") or {"src": "디시인사이드 흥한 마이너 갤러리 순위", "n": 300, "top": [], "galls": []}
    try:
        rows = fetch_dc()
        rank = {gid: r for r, gid, _ in rows}
        dc["n"] = len(rows)
        # 상위 N — 전일 순위(pr)를 같이 남겨 화면에서 등락을 그린다.
        # 같은 날 재실행이면 어제 값을 그대로 이어받는다(오늘 것으로 덮으면 등락이 0 이 된다).
        if dc.get("d") == today:
            pr = {t["id"]: t.get("pr") for t in dc.get("top", [])}
        else:
            pr = {t["id"]: t.get("r") for t in dc.get("top", [])}
        dc["d"] = today
        dc["top"] = [{"r": r, "id": gid, "name": nm, "pr": pr.get(gid)} for r, gid, nm in rows[:TOP_N]]

        # 추적 대상 = 이미 추적 중인 갤 + DCGALL 에 있는 갤 + 이름이 커버리지에 걸린 갤
        galls = {g["id"]: g for g in dc.get("galls", [])}
        dcg = _const(html_, "DCGALL") or {}
        for g in dcg.get("galls", []):
            if g.get("kind") != "mgallery":
                continue
            e = galls.setdefault(g["id"], {"stock": g["stock"], "name": g["name"], "id": g["id"], "hist": []})
            # ⚠ 상장사 정보(co)는 아래 300위 루프에서 붙는데, DCGALL 갤이 **권외면 그 루프에 안 들어온다.**
            #   그러면 화면에서 코드·시장이 빈 채로 뜬다(탑코미디어가 그랬다). 여기서 미리 채운다.
            if not e.get("co"):
                hs = hits_of(g["name"]) or hits_of(g["stock"])
                if hs:
                    e["co"] = [[c[0], c[1], c[2], c[3]] for c in hs]
                    e["cov"] = 1 if any(c[3] for c in hs) else 0
        for r, gid, nm in rows:
            hs = hits_of(nm)
            if not hs:
                continue
            cov = any(c[3] for c in hs)
            if gid not in galls:
                # 커버리지는 순위 무관, 그 밖은 상위 60위에 들었을 때만 새로 잡는다.
                if not cov and r > NEW_RANK_CUT:
                    continue
                galls[gid] = {"stock": hs[0][0], "name": nm, "id": gid, "hist": []}
            # 여러 상장사에 걸리는 갤이 있다(블루 아카이브 = 넥슨게임즈 개발 + 넥슨 퍼블리싱).
            galls[gid]["co"] = [[c[0], c[1], c[2], c[3]] for c in hs]
            galls[gid]["cov"] = 1 if cov else 0
        for gid, g in galls.items():
            hist = [h for h in g.get("hist", []) if h.get("d") != today]
            hist.append({"d": today, "r": rank.get(gid)})
            g["hist"] = hist[-DAYS:]
        # ⚠ **매 실행 사전으로 다시 판정한다.** 옛 co 가 저장돼 있으면 사전에서 뺀 뒤에도
        #   그대로 남아 정리가 안 된다(해외 상장사를 걷어낸 날 실제로 안 지워졌다).
        # 300위 목록에 있으면 **이름을 정식 갤 이름으로 맞춘다.** DCGALL 이 먼저 시드한
        # 짧은 이름("제우스"·"컴프야")은 사전 키워드("제우스 오만"·"컴투스프로야구")에 안 걸린다.
        name_of = {gid: nm for _, gid, nm in rows}
        for gid, g in galls.items():
            if gid in name_of:
                g["name"] = name_of[gid]
        for g in galls.values():
            # 이름으로 먼저 보고, 안 걸리면 종목명으로 한 번 더(짧은 이름 갤 구제).
            hs2 = hits_of(g.get("name") or "") or hits_of(g.get("stock") or "")
            if hs2:
                g["co"] = [[c[0], c[1], c[2], c[3]] for c in hs2]
                g["cov"] = 1 if any(c[3] for c in hs2) else 0
            else:
                g.pop("co", None); g.pop("cov", None)

        # ⚠ 사전에서 뺀 항목은 **추적 목록에서도 지운다.** 안 그러면 옛 갤이 co 없이 남아
        #   화면 폴백이 엉뚱한 배지를 단다(해외 상장사를 걷어낸 2026-09-08 에 실제로 그랬다).
        keep = {g["id"] for g in (dcg.get("galls") or []) if g.get("kind") == "mgallery"}
        dropped = [gid for gid, g in galls.items() if not g.get("co") and gid not in keep]
        for gid in dropped:
            galls.pop(gid)
        if dropped:
            print(f"  사전에서 빠진 갤 {len(dropped)}개 정리")

        # 상한을 넘으면 '커버리지 우선 → 최근 순위 좋은 순'으로 자른다.
        def _cur(g):
            h = g.get("hist") or []
            return (h[-1].get("r") if h and h[-1].get("r") is not None else 9999)
        gl = sorted(galls.values(), key=lambda g: (-(g.get("cov") or 0), _cur(g)))[:MAX_GALLS]
        dc["galls"] = sorted(gl, key=lambda g: (-(g.get("cov") or 0), g["stock"], g["name"]))
        dc["asOf"] = stamp
        hit = " · ".join("%s %d위" % (g["name"], g["hist"][-1]["r"]) for g in dc["galls"] if g["hist"][-1]["r"])
        print("[디시] 흥한갤 %d개 · 1위 %s · 커버리지 %s" % (len(rows), rows[0][2], hit or "없음"))
    except Exception as e:
        fails.append("디시: " + str(e)[:70])

    # 소스가 넷이다(구글·네이트·나무위키·디시). 하나둘 흔들리는 건 늘 있는 일이라
    # **절반 넘게 죽을 때만** 기록한다 — 즉시 쏘면 진짜 고장을 무시하게 된다.
    note_health("버즈(구글·네이트·나무위키·디시)", " | ".join(fails) if len(fails) >= 3 else None)
    if len(fails) >= 4:
        print("[버즈] 전부 실패 — 기존 보존:", " | ".join(fails)); return
    if fails:
        print("  [실패]", " | ".join(fails))

    # 사전을 화면으로 같이 보낸다 — 매칭 규칙이 수집기와 화면에서 갈라지면
    # 배지가 서로 다르게 붙는다. 출처를 하나로 둔다.
    listed = [[list(kws), [[c[0], c[1], c[2], c[3]] for c in cos]] for kws, cos in LISTED]
    out = {"asOf": stamp + " KST", "listed": listed, "gt": gt, "nate": nate, "namu": namu, "dc": dc}
    if "--dry-run" in sys.argv:
        print(json.dumps(out, ensure_ascii=False)[:2000]); return
    # 시각(asOf·snap.t)만 바뀐 회차는 배포를 안 만든다 — 실제 값이 바뀐 것만 커밋한다.
    # 다만 namu.days 의 관측회차 n 이 매 회차 늘기 때문에 나무위키가 살아 있는 한 대개 '변동'이다.
    # 그래도 괜찮다 — refresh.yml 은 어차피 매시간 LIVE 를 커밋하고, 배포는 deploy_slot() 이 가른다.
    # 이 검사가 실제로 일하는 자리는 나무위키가 죽고 디시 순위도 그대로인 회차다.
    if prev and _same(prev.get("dc", {}).get("galls"), out["dc"].get("galls")) \
            and _same(prev.get("dc", {}).get("top"), out["dc"].get("top")) \
            and _same(prev.get("namu", {}).get("days"), out["namu"].get("days"))             and _same(prev.get("gt", {}).get("days"), out["gt"].get("days"))             and _same(prev.get("nate", {}).get("snap"), out["nate"].get("snap")):
        print("[버즈] 변동 없음 — 건너뜀"); return
    open(HTML, "w", encoding="utf-8").write(_put(html_, "BUZZ", out))
    print("[OK] BUZZ 갱신 · 소스 %d/4 · 갤 추적 %d개" % (4 - len(fails), len(dc.get("galls", []))))


if __name__ == "__main__":
    main()
