# -*- coding: utf-8 -*-
"""
종목 무관 '지금 화제' 수집 — 나무위키 실시간 검색어 + 디시인사이드 흥한 마이너 갤러리 순위.
(2026-09-07 신설. 트렌드 탭 맨 위 '지금 화제' 섹션.)

기존 트렌드 데이터는 전부 '종목 -> 주제' 구조다. 그래서 **우리가 이미 보고 있는 것만 보인다.**
이건 반대 방향이다 — 한국 인터넷 전체에서 지금 뭐가 뜨는지 먼저 보고, 그 중에 우리 종목이
있으면 배지를 단다. 커버리지 밖에서 올라오는 것을 알아채는 게 목적이다.

소스 — 둘 다 키·로그인 없이 urllib 로 열린다(2026-09-07 실측):

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
DAYS = 400          # 갤러리 순위 보관 일수
NAMU_DAYS = 60      # 검색어 일별 집계 보관 일수
SNAPS = 12          # 최근 회차 스냅샷 보관 수
TOP_N = 20          # 화면에 띄우는 상위 갤 수 (= 사이트의 '대흥갤' 경계)

NAMU_URL = "https://search.namu.wiki/api/ranking"
DC_URL = "https://gall.dcinside.com/m"

# 갤러리 '이름'으로 커버리지 종목을 찾는다. id 로 하면 새 갤이 생겼을 때 못 잡는다.
# ⚠ 좁게 쓸 것 — '제우스' 두 글자는 최우제 갤을 문다(DCGALL 주석의 같은 함정).
COVER_KW = [
    ("NC",        ["아이온", "리니지", "쓰론 앤 리버티", "저니 오브 모나크", "블레이드 앤 소울"]),
    ("컴투스",     ["제우스 오만", "컴투스", "서머너즈 워", "서머너즈워"]),
    ("펄어비스",   ["붉은사막", "검은사막", "도깨비(게임"]),
    ("크래프톤",   ["배틀그라운드", "PUBG", "인조이", "다크앤다커"]),
    ("시프트업",   ["스텔라 블레이드", "스텔라블레이드", "승리의 여신", "니케"]),
    ("데브시스터즈", ["쿠키런"]),
    ("탑코미디어", ["탑툰"]),
    ("SAMG엔터",  ["티니핑", "미니특공대"]),
    ("하이브",     ["방탄소년단", "세븐틴", "뉴진스", "르세라핌", "아일릿", "투모로우바이투게더"]),
    ("JYP Ent.",  ["트와이스", "스트레이 키즈", "엔믹스", "데이식스"]),
    ("에스엠",     ["에스파", "엔시티", "NCT", "레드벨벳"]),
    ("와이지엔터", ["블랙핑크", "베이비몬스터"]),
]
UA = ua(referer="https://gall.dcinside.com/")


def _get(url, ref=None):
    h = dict(UA)
    if ref:
        h["Referer"] = ref
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


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


def stock_of(name):
    for stock, keys in COVER_KW:
        for k in keys:
            if k in name:
                return stock
    return None


def fetch_namu():
    """실시간 검색어 10개. 문자열 배열이 그대로 온다."""
    j = json.loads(_get(NAMU_URL, ref="https://namu.wiki/"))
    kw = [str(x).strip() for x in j if str(x).strip()]
    if not kw:
        raise ValueError("검색어 0개")
    return kw


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
            if g.get("kind") == "mgallery":
                galls.setdefault(g["id"], {"stock": g["stock"], "name": g["name"], "id": g["id"], "hist": []})
        for r, gid, nm in rows:
            st = stock_of(nm)
            if st and gid not in galls:
                galls[gid] = {"stock": st, "name": nm, "id": gid, "hist": []}
        for gid, g in galls.items():
            hist = [h for h in g.get("hist", []) if h.get("d") != today]
            hist.append({"d": today, "r": rank.get(gid)})
            g["hist"] = hist[-DAYS:]
        dc["galls"] = sorted(galls.values(), key=lambda g: (g["stock"], g["name"]))
        dc["asOf"] = stamp
        hit = " · ".join("%s %d위" % (g["name"], g["hist"][-1]["r"]) for g in dc["galls"] if g["hist"][-1]["r"])
        print("[디시] 흥한갤 %d개 · 1위 %s · 커버리지 %s" % (len(rows), rows[0][2], hit or "없음"))
    except Exception as e:
        fails.append("디시: " + str(e)[:70])

    # 둘 다 실패했을 때만 기록한다 — 한쪽 실패는 다음 회차에 메워진다
    note_health("버즈(나무위키·디시)", " | ".join(fails) if len(fails) >= 2 else None)
    if len(fails) >= 2:
        print("[버즈] 둘 다 실패 — 기존 보존:", " | ".join(fails)); return
    if fails:
        print("  [실패]", " | ".join(fails))

    out = {"asOf": stamp + " KST", "namu": namu, "dc": dc}
    if "--dry-run" in sys.argv:
        print(json.dumps(out, ensure_ascii=False)[:2000]); return
    # 시각(asOf·snap.t)만 바뀐 회차는 배포를 안 만든다 — 실제 값이 바뀐 것만 커밋한다.
    # 다만 namu.days 의 관측회차 n 이 매 회차 늘기 때문에 나무위키가 살아 있는 한 대개 '변동'이다.
    # 그래도 괜찮다 — refresh.yml 은 어차피 매시간 LIVE 를 커밋하고, 배포는 deploy_slot() 이 가른다.
    # 이 검사가 실제로 일하는 자리는 나무위키가 죽고 디시 순위도 그대로인 회차다.
    if prev and _same(prev.get("dc", {}).get("galls"), out["dc"].get("galls")) \
            and _same(prev.get("dc", {}).get("top"), out["dc"].get("top")) \
            and _same(prev.get("namu", {}).get("days"), out["namu"].get("days")):
        print("[버즈] 변동 없음 — 건너뜀"); return
    open(HTML, "w", encoding="utf-8").write(_put(html_, "BUZZ", out))
    print("[OK] BUZZ 갱신 · 검색어 %d회차 · 갤 추적 %d개" % (len(namu.get("snap", [])), len(dc.get("galls", []))))


if __name__ == "__main__":
    main()
