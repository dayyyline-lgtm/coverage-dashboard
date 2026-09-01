# -*- coding: utf-8 -*-
"""
탑툰챗(chat.toptoon.com) 공개 지표 수집 — 탑코미디어 AI 챗봇 사업의 '실측' 수요.

왜 이걸 보나
  탑코미디어는 웹툰 캐릭터 AI 채팅(탑툰챗)을 2026년에 국내→일본(5월)→북미(7월)로 넓혔고,
  실적 설명에서 AI 사업을 성장동력으로 든다. 그런데 그 사업의 사용량은 분기 실적 전엔 안 보인다.

무엇을 받나 (⚠ DAU 는 공개되지 않는다)
  탑툰챗은 캐릭터 카드에 '조회수·대화수·좋아요'를 공개한다. 전부 **누적값**이라
  매일 한 번 찍어 두고 **일별 증분**을 만든다 — 그게 '하루에 대화가 몇 건 새로 시작됐나'다.
  DAU 그 자체가 아니라 대리지표다. (유튜브 조회수를 일일 증분으로 쌓는 방식과 같다.)

⚠ 합계끼리 빼면 안 된다 (2026-09-01 실측)
  합계는 '그날 홈에 노출된 캐릭터들의 합' 이다. 누적값이 단조증가하는 건 **캐릭터별로만**이고,
  한 명이 홈에서 빠지면 그 사람 누적치가 통째로 사라져 합계가 줄어든다.

      KR  08-31 대화 1,320,016 (51명) → 09-01 1,316,732 (50명)   합계 -3,284
          같은 날 개별은 전부 증가 (신아영 +349 · 한나리 +316 · 장선영 +411 · 박채원 +675)

  그래서 증분은 **어제·오늘 둘 다 있는 캐릭터(교집합)** 로만 낸다 → hist 의 dchat·dview.
  그러려면 상위 16명뿐 아니라 **전 캐릭터의 직전값**이 필요하다 → sites[].snaps (최근 2일).
  누적 그래프도 원합계를 쓰면 같은 이유로 꺾이므로, 증분을 더해 올린 조정누적(cchat)을 쓴다.

수집 방법 — 카탈로그 API 가 우선, 홈 HTML 은 예비 (2026-09-01 전환)
  `/api/characters?limit=50&page=N` 이 **전체 캐릭터 목록**을 준다(지역당 2요청).
  홈 HTML 을 긁던 옛 방식은 '홈에 노출된 것'만 잡혀 KR 88명 중 51명뿐이었다 —
  대화 누적이 1,574,260 인데 1,321,441 로 보였다(**19% 과소집계**).
  카탈로그는 명단이 흔들리지 않아 증분도 훨씬 안정적이다.
  홈 파서(parse)는 카탈로그가 막힐 때를 위해 남겨 두고, 어느 쪽을 썼는지 hist 의 src 에 적는다
  — **기반이 다른 두 계열을 이어 붙이면 가짜 점프가 생기므로, src 가 바뀌는 날은 증분을 내지 않는다.**

  카탈로그에는 `startAt`·`createdAt` 이 있어 **월별 신규 캐릭터 투입량이 백필로 계산된다**
  (KR 3월 20 → 8월 8 로 반감). 콘텐츠 투입은 이 사업의 비용이자 성장 동력이라 같이 본다.

  python fetch_toptoonchat.py            # 수집·기록
  python fetch_toptoonchat.py --dry-run  # 출력만
"""
import re, json, sys, gzip, copy, datetime, urllib.request

from collector_health import ua, nap, note_health, looks_blocked

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
DAYS = 400                 # 합계 시계열 보관 일수
CHAR_HIST = 16             # 캐릭터별 시계열을 남길 상위 N명(파일 크기 관리)

# 4개 지역. JS 번들(showcase.chat.toptoon.com/.../chunks/*.js)에 다섯 주소가 박혀 있어 찾았다 —
# 홈 화면만 봐서는 국내·일본밖에 안 보인다.
#   chat.toptoon.net 과 chat.cn.toptoon.net 은 응답이 완전히 같다(같은 서비스) → 하나만 받는다.
# 각 지역의 주간 백필 시작 주가 진출 시점과 맞아떨어져 데이터 신뢰도를 교차검증해 준다:
#   KR 4월 1주 · JP 5월 4주 · TW 5월 4주 · GLOBAL 7월 1주(= 북미 진출)
SITES = [("KR",     "https://chat.toptoon.com/"),
         ("JP",     "https://chat.toptoon.jp/"),
         ("TW",     "https://chat.toptoon.net/"),
         ("GLOBAL", "https://chat.global.toptoon.com/")]


def fetch(url):
    req = urllib.request.Request(url, headers=ua(referer="https://chat.toptoon.com/"))
    r = urllib.request.urlopen(req, timeout=40)
    raw = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", "replace")


def parse(html):
    """캐릭터별 {id: (name, chat, view, like)}.

    flight 페이로드는 JSON 문자열 안에 있어 따옴표가 \\" 로 이스케이프돼 있다.
    객체 시작(id·name)을 잡고 '다음 객체 전까지'로 잘라 그 안의 카운트만 읽는다 —
    그래야 옆 캐릭터의 숫자를 잘못 물어오지 않는다."""
    u = html.replace('\\"', '"')
    out = {}
    for m in re.finditer(r'"id":"(\d+)","name":"([^"]{1,60})"', u):
        seg = u[m.end():m.end() + 4000]
        nx = seg.find('"id":"')
        if nx > 0:
            seg = seg[:nx]
        g = lambda k: (lambda x: int(x.group(1)) if x else None)(re.search(r'"%s":(\d+)' % k, seg))
        # 조회수 필드는 카드 목록에선 "views", 일부(멀티 작품) 객체에선 "viewCount" 다.
        chat, like = g("chatCount"), g("likeCount")
        view = g("views")
        if view is None:
            view = g("viewCount")
        if chat is None and view is None:
            continue                      # 카운트가 없는 객체(캐스트 미리보기 등)는 캐릭터가 아니다
        cid, name = m.group(1), m.group(2)
        old = out.get(cid)
        # 같은 캐릭터가 섹션마다 반복 등장한다. 값이 다르면 큰 쪽(가장 최신)을 남긴다.
        if not old or (chat or 0) > (old[1] or 0):
            out[cid] = (name, chat, view, like)
    return out


def catalog(base):
    """전체 캐릭터 카탈로그 -> ({id: (name, chat, view, like)}, 월별 신규 수).

    limit 은 서버가 50 으로 자른다(100·200 을 넣어도 50). 지역당 2요청이면 끝난다.
    startAt 이 없으면 createdAt 을 쓴다 — '언제부터 서비스에 있었나'가 우리가 보려는 것."""
    out, new = {}, {}
    page = 1
    while True:
        d = _api(base, f"/api/characters?limit=50&page={page}")
        rows = (d or {}).get("data") or []
        pg = (d or {}).get("pagination") or {}
        for x in rows:
            cid = str(x.get("id"))
            out[cid] = (x.get("name"), x.get("chatCount"), x.get("viewCount"), x.get("likeCount"))
            ym = (x.get("startAt") or x.get("createdAt") or "")[:7]
            if ym:
                new[ym] = new.get(ym, 0) + 1
        if page >= (pg.get("totalPages") or 1) or not rows:
            break
        page += 1
        nap(0.25)
    return out, new


def _snapshot(chars):
    """{id: [대화, 조회]} — 교집합 증분에 쓸 '전 캐릭터' 스냅샷.
       화면용 chars 는 상위 16명만 남기지만, 증분 계산은 전원이 있어야 정확하다."""
    return {cid: [c[1] or 0, c[2] or 0] for cid, c in chars.items()}


def _delta(base, cur):
    """어제·오늘 둘 다 있는 캐릭터만 더해 (대화증분, 조회증분, 교집합 인원)."""
    dc = dv = 0
    n = 0
    for cid, v in cur.items():
        b = base.get(cid)
        if not b:
            continue                       # 오늘 새로 뜬 캐릭터 — 증분을 알 수 없다
        n += 1
        # 개별 누적이 줄면 사이트 집계 정정이다. 음수를 그대로 더하면 총합이 오염된다.
        dc += max(0, v[0] - b[0])
        dv += max(0, v[1] - b[1])
    return dc, dv, n


# ══════════════════════════════════════════════════════════════════
# 랭킹 API — 여기가 이 수집기의 진짜 알맹이다 (2026-09-01 발견)
#
# 홈 HTML 의 누적 대화수는 '지금까지 얼마나'라 유량이 안 보이고, 명단이 흔들려 다루기 나쁘다.
# 그런데 사이트가 랭킹 API 를 그대로 열어 두고 있다 — 키·로그인 불필요.
#
#   /api/ranking/realtime                    지금 이 순간 활동지수 (유량!)
#   /api/ranking/weekly?periodKey=2026-28     주간 · 캐릭터 50명 + score
#   /api/ranking/monthly?periodKey=2026-07    월간
#   /api/ranking/{weekly,monthly}/periods     ★ 과거 기간 목록 = 백필이 된다
#   /api/ranking/user/weekly?periodKey=...    유저 랭킹(30명) · isNew = 신규 진입
#
# 백필 실측(2026-09-01): KR 주간 22주(4월 1주~), JP 14주(5월 4주~ = 일본 진출 시점과 일치).
# 다른 수집기 대부분이 '오늘부터 한 점씩'인데 이건 넉 달치를 한 번에 받는다.
#
# ⚠ tot 는 '상위 n명의 활동지수 합'이지 서비스 전체 활동량이 아니다.
#   초기엔 n 이 27~46 이라 50 이 찬 주차와 직접 비교하면 안 된다(그래서 n 을 같이 저장한다).
# 기간마다 남길 상위 캐릭터 수. 화면은 8명만 보여주지만 더 깊게 저장한다 —
# 주간 상위권 회전이 빨라서 12 로는 '이번 주 4위'가 직전 주 목록에 없는 일이 잦고,
# 그러면 순위변동을 '신규'로 오해하게 된다(실제로는 13위에서 올라온 것).
RANK_TOP = 20
RANK_REFRESH = 2           # 최신 N개 기간은 아직 집계 중일 수 있어 매번 다시 받는다


def _api(base, path):
    req = urllib.request.Request(base + path, headers=ua(referer=base))
    r = urllib.request.urlopen(req, timeout=30)
    raw = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        raw = gzip.decompress(raw)
    d = json.loads(raw.decode("utf-8", "replace"))
    if not d.get("success"):
        raise RuntimeError(str(d.get("error"))[:60])
    return d.get("data")


def _row(k, lab, items):
    return {"k": k, "lab": lab or k, "n": len(items),
            "tot": sum(x.get("score") or 0 for x in items),
            "top": [{"id": x.get("characterId"), "nm": x.get("name"),
                     "s": x.get("score"), "kind": x.get("kind")}
                    for x in items[:RANK_TOP]]}


def _periods(base, kind, have):
    """kind = weekly | monthly. 이미 받은 기간은 건너뛴다 — 첫 실행만 무겁다."""
    pers = _api(base, f"/api/ranking/{kind}/periods") or []      # 최신순
    fresh = {p["periodKey"] for p in pers[:RANK_REFRESH]}
    out = dict(have)
    got = 0
    for p in pers:
        k = p["periodKey"]
        have_k = out.get(k)
        # RANK_TOP 을 늘렸을 때 옛 기간이 얕은 채로 남지 않도록 스스로 다시 받는다.
        # (n 이 RANK_TOP 보다 작았던 기간은 더 받을 게 없으므로 제외)
        shallow = bool(have_k) and len(have_k.get("top") or []) < min(RANK_TOP, have_k.get("n") or 0)
        if have_k and k not in fresh and not shallow:
            continue
        d = _api(base, f"/api/ranking/{kind}?periodKey={k}") or {}
        out[k] = _row(k, p.get("label"), d.get("items") or [])
        got += 1
        nap(0.25)
    return [out[k] for k in sorted(out)], got


def _users(base, have):
    """유저 주간 랭킹 — 이름은 안 쌓는다. 필요한 건 '몇 명이 랭크됐고 몇 명이 신규냐'뿐이다."""
    pers = _api(base, "/api/ranking/user/weekly/periods") or []
    fresh = {p["periodKey"] for p in pers[:RANK_REFRESH]}
    out = dict(have)
    for p in pers:
        k = p["periodKey"]
        if k in out and k not in fresh:
            continue
        it = (_api(base, f"/api/ranking/user/weekly?periodKey={k}") or {}).get("items") or []
        out[k] = {"k": k, "lab": p.get("label") or k, "n": len(it),
                  "new": sum(1 for x in it if x.get("isNew"))}
        nap(0.25)
    return [out[k] for k in sorted(out)]


def rank(base, prev, today, hhmm):
    """사이트 하나의 랭킹 묶음. 실패해도 캐릭터 수집을 죽이지 않도록 호출부에서 감싼다."""
    prev = prev or {}
    idx = lambda key: {r["k"]: r for r in (prev.get(key) or [])}
    weekly,  gw = _periods(base, "weekly",  idx("weekly"))
    monthly, gm = _periods(base, "monthly", idx("monthly"))
    users = _users(base, idx("users"))

    # 실시간 — 하루 1점. 롤링 윈도 스냅샷이라 매일 같은 시각에 찍어야 비교가 된다.
    # 그래서 수집 시각(t)을 같이 남긴다 — 나중에 '이 점은 몇 시 것'인지 알아야 한다.
    it = (_api(base, "/api/ranking/realtime") or {}).get("items") or []
    r = _row(today, hhmm, it)
    rt = [x for x in (prev.get("rt") or []) if x.get("d") != today]
    rt.append({"d": today, "t": hhmm, "n": r["n"], "tot": r["tot"], "top": r["top"]})
    return {"weekly": weekly, "monthly": monthly, "users": users,
            "rt": rt[-DAYS:]}, (gw + gm)


def _put(html, name, obj):
    """해당 상수 블록만 교체. 없으면 LIVE 뒤에 새로 삽입한다."""
    block = "const %s = %s;" % (name, json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
    pat = re.compile(r"const %s\s*=\s*\{.*?\};" % re.escape(name), re.S)
    if pat.search(html):
        return pat.sub(lambda m: block, html, count=1)
    liv = re.search(r"const LIVE\s*=\s*\{.*?\};", html, re.S)
    if not liv:
        raise RuntimeError("삽입 기준(const LIVE)을 못 찾음")
    return html[:liv.end()] + "\n" + block + html[liv.end():]


def main():
    now = datetime.datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    html = open(HTML, encoding="utf-8").read()
    m = re.search(r"const TOPTOON = (\{.*?\});", html, re.S)
    old = {}
    if m:
        try:
            old = json.loads(m.group(1))
        except json.JSONDecodeError:
            old = {}

    # ⚠ 반드시 복사본을 만든다. 아래에서 sites[code] 를 제자리 수정(s["hist"]=...)하는데,
    #    얕게 가져오면 그 객체가 old 안의 바로 그 객체라 old 까지 같이 바뀐다.
    #    그러면 맨 끝의 '변동 없음' 비교가 자기 자신끼리 비교하게 돼 **항상 SKIP** 된다.
    #    도입 첫날(2026-08-31)은 블록이 없어서 비교를 안 탔기에 한 번 저장됐고,
    #    그 뒤로는 매 회차가 조용히 SKIP 돼 데이터가 9/1 까지 하루치에 멈춰 있었다.
    sites = {s.get("code"): s for s in copy.deepcopy(old.get("sites") or [])}
    ok_any, fails = False, []
    for code, url in SITES:
        base = url.rstrip("/")
        chars, newmap, src = {}, {}, "cat"
        try:
            chars, newmap = catalog(base)
        except Exception as e:
            fails.append(f"{code} 카탈로그 {type(e).__name__} {str(e)[:40]}")
            if looks_blocked(e):
                note_health("탑툰챗", f"{code} 차단 의심: {str(e)[:60]}")
        if not chars:                       # 카탈로그가 막히면 옛 방식(홈 HTML)으로 버틴다
            try:
                chars, src = parse(fetch(url)), "home"
            except Exception as e:
                fails.append(f"{code} 홈 {type(e).__name__} {str(e)[:40]}")
        nap(0.4)
        if not chars:
            fails.append(f"{code} 캐릭터 0개(구조 변경 의심)")
            continue
        ok_any = True
        tot_chat = sum(c[1] or 0 for c in chars.values())
        tot_view = sum(c[2] or 0 for c in chars.values())
        tot_like = sum(c[3] or 0 for c in chars.values())

        s = sites.get(code) or {"code": code, "url": url, "hist": [], "chars": []}

        # 전 캐릭터 스냅샷 — 최근 2일치만 들고 있는다(교집합 증분용, 사이트당 ~3KB).
        # 같은 날 재실행이면 오늘 것은 버리고 '오늘이 아닌 가장 최근 날'을 기준으로 삼는다.
        snap = _snapshot(chars)
        snaps = [x for x in (s.get("snaps") or []) if x.get("d") != today]
        prev_row = snaps[-1] if snaps else None

        # 합계 시계열 — 하루 1점. 같은 날 다시 돌면 그 날 값을 갱신한다.
        hist = [h for h in (s.get("hist") or []) if h.get("d") != today]
        row = {"d": today, "chat": tot_chat, "view": tot_view,
               "like": tot_like, "n": len(chars), "src": src}
        # 수집 경로(카탈로그/홈)가 바뀐 날은 기반이 달라 증분이 뜻을 잃는다 —
        # 51명 합계에서 88명 합계로 넘어가면 '하루에 25만 건'이라는 가짜 급증이 나온다.
        same_src = bool(prev_row) and (prev_row.get("src") or "home") == src
        if prev_row and not same_src:
            print(f"  {code} 수집 경로 {prev_row.get('src') or 'home'} → {src} · 이 날 증분은 건너뛴다")
        if prev_row and same_src:
            dc, dv, nc = _delta(prev_row["v"], snap)
            row["dchat"], row["dview"], row["nc"] = dc, dv, nc
            # 조정 누적 — 원합계는 명단이 바뀌면 꺾이므로 증분을 더해 올린다.
            prev_c = next((h["cchat"] for h in reversed(hist) if h.get("cchat") is not None), None)
            row["cchat"] = (tot_chat if prev_c is None else prev_c) + dc
            print(f"  {code} 증분(교집합 {nc}명): 대화 +{dc:,} · 조회 +{dv:,}")
        else:
            row["cchat"] = tot_chat        # 첫 점 / 경로 전환 직후는 원합계에서 다시 출발
            if not prev_row:
                print(f"  {code} 기준점 없음 — 증분은 다음 회차부터")
        hist.append(row)
        s["hist"] = hist[-DAYS:]
        s["snaps"] = (snaps + [{"d": today, "v": snap, "src": src}])[-2:]
        # 카탈로그 규모와 월별 신규 캐릭터 투입 — 콘텐츠 투입은 이 사업의 비용이자 동력이다.
        # startAt 기준이라 과거가 통째로 들어온다(백필).
        if newmap:
            s["cat"] = {"n": len(chars), "new": dict(sorted(newmap.items()))}

        # 캐릭터별 — 대화수 상위 CHAR_HIST 명만 시계열을 남긴다(나머지는 최신값만).
        prev = {c["id"]: c for c in (s.get("chars") or [])}
        top = sorted(chars.items(), key=lambda kv: -(kv[1][1] or 0))[:CHAR_HIST]
        newc = []
        for cid, (name, chat, view, like) in top:
            p = prev.get(cid) or {"id": cid, "hist": []}
            ph = [h for h in (p.get("hist") or []) if h.get("d") != today]
            ph.append({"d": today, "chat": chat, "view": view})
            newc.append({"id": cid, "name": name, "chat": chat, "view": view,
                         "like": like, "hist": ph[-DAYS:]})
        s["chars"] = newc
        s["url"] = url

        # 랭킹 — 실패해도 위의 캐릭터 수집은 살린다(둘은 별개 경로다).
        try:
            s["rank"], got = rank(base, s.get("rank"), today, now.strftime("%H:%M"))
            wk = s["rank"]["weekly"]
            print(f"  {code} 랭킹: 주간 {len(wk)}주(새로 {got}개) · "
                  f"실시간 활동지수 {s['rank']['rt'][-1]['tot']:,}"
                  + (f" · 최근주 {wk[-1]['lab']} {wk[-1]['tot']:,}" if wk else ""))
        except Exception as e:
            fails.append(f"{code} 랭킹 {type(e).__name__} {str(e)[:50]}")

        sites[code] = s
        print(f"  {code} 캐릭터 {len(chars)}명 · 대화 누적 {tot_chat:,} · 조회 누적 {tot_view:,}")

    if not ok_any:
        note_health("탑툰챗", "전 사이트 수집 실패: " + "; ".join(fails)[:120])
        print("[실패] 수집 0건 - index.html 그대로 둡니다"); sys.exit(1)
    if fails:
        print("  일부 실패:", "; ".join(fails))
    else:
        note_health("탑툰챗", None)

    out = {"asOf": now.strftime("%Y-%m-%d %H:%M KST"),
           "sites": [sites[c] for c, _ in SITES if c in sites]}

    if "--dry-run" in sys.argv:
        print(json.dumps(out, ensure_ascii=False)[:1200]); return

    # 값이 그대로면 파일을 건드리지 않는다(Cloudflare 빌드 절약).
    if m:
        a = dict(old); b = dict(out)
        a.pop("asOf", None); b.pop("asOf", None)
        if a == b:
            print("[SKIP] 변동 없음 - index.html 그대로 둠"); return
    open(HTML, "w", encoding="utf-8").write(_put(html, "TOPTOON", out))
    print(f"[OK] TOPTOON 갱신 · 사이트 {len(out['sites'])}곳")


if __name__ == "__main__":
    main()
