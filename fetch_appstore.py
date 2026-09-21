# -*- coding: utf-8 -*-
"""
양대 마켓 게임 매출순위(한국) — 게임 커버 종목의 매출 프록시.

  · 애플 앱스토어 : 마케팅 RSS(키 불필요). genre=6014(게임) Top100 매출·무료.
  · 구글 플레이   : 스토어 웹앱이 쓰는 batchexecute RPC(키·쿠키 불필요). GAME Top100 매출·무료.

**구글은 공식 무료 API 가 없다.** 예전엔 그래서 애플만 받았는데(2026-09-18 이전), 국내 게임 매출은
구글 비중이 애플보다 커서 애플만 보면 반쪽이었다. 스토어 '최고 매출' 탭이 부르는 요청을 그대로
재현한다 — 2026-09-18 확인: 페이로드에서 없어도 되는 부분을 전부 걷어내면
`[[null,[[8,[20,100]],null,null,FEATS],[2,"topgrossing","GAME"]]]` 만 남는다(FEATS 는 필수 · 빼면 빈 목록).

⚠ 비공개 내부 RPC 라 구글이 배포하면 깨질 수 있다. 깨지면 응답이 200 인데 목록이 0 개다 →
  note_health 로 남기고 애플만 저장한다(둘 다 실패해야 종료코드 1).
  다시 딸 때는 브라우저에서 스토어 카테고리 페이지를 열고 **XHR 을 후킹**해 '최고 매출' 탭을
  누르면 f.req 가 통째로 잡힌다(fetch 후킹으로는 안 잡힌다 — 이 페이지는 XHR 을 쓴다).

**한국만 보면 반쪽이다**(2026-09-21 다국가 확대). 니케는 매출 주력이 일본이고(구글 JP 3위),
컴투스 MLB 는 대만에서 잡힌다(애플 TW 17위). 한국 차트만 보면 시프트업·컴투스의 해외 매출이
통째로 안 보인다 — 컴투스는 국내 앱차트로 잡히는 몫이 전사의 10% 뿐이었다.
그래서 **매출순위는 KR·US·JP·TW 네 나라**를 받는다. 무료순위는 신규 유입 지표라 한국만 받는다
(해외까지 받으면 요청이 두 배가 되는데 쓰임이 적다).

**종목별 대표작 하나가 아니라 잡히는 게임을 전부 담는다**(2026-09-18 개편).
예전엔 종목당 '가장 높은 순위 하나'만 저장해서 리니지M·리니지W·아이온2 가 한 줄로 뭉갰다.
지금은 (마켓, 앱) 단위로 따로 쌓고, 화면에서 종목·마켓별 한 그룹에 게임을 계열로 그린다.

매칭은 **개발사 이름이 먼저**다(자체 퍼블리싱은 이걸로 전부 걸린다). 퍼블리셔가 다른 게임은
제목 키워드로 잡는다 — 니케는 iOS 퍼블리셔가 'Level Infinite'(텐센트)라 개발사만 보면 놓친다.

  python fetch_appstore.py            # 수집·기록
  python fetch_appstore.py --dry-run  # 출력만
"""
import urllib.request, urllib.parse, json, re, sys, datetime

from collector_health import ua, nap, note_health

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
DAYS = 180

# 매출순위를 받을 나라. (코드, 애플 RSS 국가, 구글 gl, 구글 hl)
COUNTRIES = [("KR", "kr", "KR", "ko"), ("US", "us", "US", "en"),
             ("JP", "jp", "JP", "ja"), ("TW", "tw", "TW", "zh-TW")]

# ── 종목 매칭 ────────────────────────────────────────────────────────────────
# (1) 개발사/퍼블리셔 이름(소문자 부분일치). 두 마켓의 표기가 달라 둘 다 적는다.
#     애플 'NC Corp.' / 구글 'NC Corporation' · 애플 'Com2uS Corp.' / 구글 'Com2uS'
PUB = {
    "데브시스터즈": ["devsisters"],
    "크래프톤":   ["krafton", "pubg"],
    "NC":        ["ncsoft", "nc corp"],
    "펄어비스":   ["pearl abyss", "pearlabyss"],
    "시프트업":   ["shift up", "shiftup"],
    "컴투스":     ["com2us"],
}
# 이름이 겹치는 다른 상장사는 빼야 한다 — 컴투스홀딩스가 'Com2uS Holdings' 다.
PUB_NOT = {"컴투스": ["holdings"]}
# (2) 퍼블리셔가 남인 게임은 제목으로. (니케 = Level Infinite 등)
# ⚠ 나라마다 제목이 현지어다 — 일본 '勝利の女神：NIKKE' · 대만 'MLB：9局職棒26'.
#   개발사로 안 걸리는 게임(퍼블리셔가 남인 경우)은 **현지 표기까지** 넣어야 잡힌다.
TITLE = {
    "시프트업":   ["니케", "nikke", "스텔라 블레이드", "stellar blade", "勝利の女神"],
    "크래프톤":   ["배틀그라운드", "pubg", "펍지", "인조이", "inzoi", "絕地求生"],
    "NC":        ["리니지", "아이온", "저니 오브 모나크", "저니오브모나크", "블레이드 앤 소울",
                 "lineage", "aion", "throne and liberty", "天堂"],
    "펄어비스":   ["검은사막", "black desert", "crimson desert", "黑色沙漠"],
    "데브시스터즈": ["쿠키런", "cookie run", "クッキーラン"],
    "컴투스":     ["서머너즈", "컴투스프로야구", "컴프야", "제우스: 오만", "mlb 9이닝스",
                 "summoners war", "サマナーズ", "9局職棒", "mlb 9 innings", "mlb：9局職棒"],
}

# 구글 플레이 RPC 에 필수인 feature id 목록(2026-09-18 스토어 요청에서 추출).
# 빼거나 다른 값으로 바꾸면 응답은 200 인데 목록이 비어 온다.
G_FEATS = [96, 108, 72, 100, 27, 177, 183, 222, 8, 57, 169, 110, 11, 184, 16, 1, 139, 152,
           194, 165, 68, 163, 211, 9, 71, 31, 176, 195, 12, 64, 151, 320, 150, 148, 113,
           104, 55, 56, 145, 32, 34, 10, 122]


def apple(kind, cc="kr"):
    """애플 게임 Top100 -> [(순위, 제목, 개발사, 번들ID)]"""
    u = "https://itunes.apple.com/%s/rss/%s/limit=100/genre=6014/json" % (cc, kind)
    d = json.loads(urllib.request.urlopen(
        urllib.request.Request(u, headers=ua()), timeout=30).read().decode("utf-8"))
    out = []
    for i, e in enumerate(d.get("feed", {}).get("entry", []), 1):
        out.append((i, e.get("im:name", {}).get("label", ""),
                    e.get("im:artist", {}).get("label", ""),
                    (e.get("id", {}).get("attributes", {}) or {}).get("im:bundleId", "")))
    return out


def google(chart_id, n=100, gl="KR", hl="ko"):
    """구글 플레이 게임 Top100 -> [(순위, 제목, 개발사, 패키지)]"""
    inner = [[None, [[8, [20, n]], None, None, G_FEATS], [2, chart_id, "GAME"]]]
    req = [[["vyAe2", json.dumps(inner, separators=(",", ":")), None, "generic"]]]
    body = "f.req=" + urllib.parse.quote(json.dumps(req, separators=(",", ":")))
    u = ("https://play.google.com/_/PlayStoreUi/data/batchexecute?rpcids=vyAe2"
         "&hl=%s&gl=%s&rt=c" % (hl, gl))
    h = ua(doc=True)
    h["Content-Type"] = "application/x-www-form-urlencoded;charset=UTF-8"
    h["Accept"] = "*/*"
    t = urllib.request.urlopen(urllib.request.Request(u, data=body.encode(), headers=h),
                               timeout=45).read().decode("utf-8", "replace")
    obj = None
    # 응답은 앞에 방어 접두어가 붙고, 길이 줄과 JSON 줄이 번갈아 온다
    for line in t[t.index("\n") + 1:].split("\n"):
        s = line.strip()
        if not s.startswith("[["):
            continue
        try:
            a = json.loads(s)
            if a and a[0] and a[0][0] == "wrb.fr":
                obj = json.loads(a[0][2])
                break
        except Exception:
            pass
    if obj is None:
        raise RuntimeError("응답에서 wrb.fr 을 못 찾음")
    lst = obj[0][1][0][28][0]          # 목록 위치도 배포마다 흔들릴 수 있다
    out = []
    for i, it in enumerate(lst, 1):
        c = it[0]
        out.append((i, c[3], c[14], c[0][0]))
    return out


def owner(title, artist):
    """이 앱이 어느 커버 종목 것인가. 개발사 우선, 없으면 제목 키워드."""
    a, t = (artist or "").lower(), (title or "").lower()
    for st, pubs in PUB.items():
        if any(p in a for p in pubs) and not any(x in a for x in PUB_NOT.get(st, [])):
            return st
    for st, kws in TITLE.items():
        if any(k in t for k in kws):
            return st
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
        raise RuntimeError("APPRANK 삽입 기준(const LIVE)을 못 찾음")
    return html[:liv.end()] + "\n" + block + html[liv.end():]


def main():
    html = open(HTML, encoding="utf-8").read()
    today = datetime.datetime.now(KST).date().isoformat()
    old = _const(html, "APPRANK") or {}
    # cc 가 없는 옛 기록은 전부 한국이다(2026-09-21 다국가 확대 전)
    prev = {(a.get("cc", "KR"), a.get("mk"), a.get("id")): a for a in old.get("apps", [])}

    charts, dead = {}, []
    for cc, acc, gl, hl in COUNTRIES:
        # 매출순위는 네 나라 전부, 무료순위(신규 유입)는 한국만
        jobs = [("ios", "gr", lambda k=acc: apple("topgrossingapplications", k)),
                ("and", "gr", lambda g=gl, h=hl: google("topgrossing", 100, g, h))]
        if cc == "KR":
            jobs += [("ios", "fr", lambda: apple("topfreeapplications", "kr")),
                     ("and", "fr", lambda: google("topselling_free", 100, "KR", "ko"))]
        for mk, key, fn in jobs:
            try:
                charts[(cc, mk, key)] = fn()
                nap(0.4)
            except Exception as e:
                charts[(cc, mk, key)] = []
                dead.append("%s/%s/%s: %s" % (cc, mk, key, str(e)[:50]))
        for mk in ("ios", "and"):
            if not charts.get((cc, mk, "gr")):
                dead.append("%s %s 매출차트가 비어 있음" % (cc, mk))

    if not charts.get(("KR", "ios", "gr")) and not charts.get(("KR", "and", "gr")):
        note_health("앱스토어", ("양대 마켓 매출차트 전부 실패: " + " · ".join(dead))[:160])
        print("[appstore] 두 마켓 다 실패 — " + " · ".join(dead))
        sys.exit(1)
    if dead:
        # 한쪽만 죽은 건 기록만 남긴다 — 구글 RPC 가 깨지면(200·목록 0 포함) 여기로 드러난다
        note_health("앱스토어", ("일부 실패: " + " · ".join(dead))[:160])
        print("[appstore] 일부 실패 — " + " · ".join(dead))
    else:
        note_health("앱스토어", None)

    # ── 오늘 잡힌 것 모으기 ──────────────────────────────────────────────
    apps = {}
    for (cc, mk, key), rows in charts.items():
        for rank, title, artist, ident in rows:
            st = owner(title, artist)
            if not st or not ident:
                continue
            a = apps.setdefault((cc, mk, ident),
                                {"stock": st, "cc": cc, "mk": mk, "nm": title, "id": ident, "pt": {}})
            a["nm"] = title
            a["pt"][key] = rank        # 같은 앱이 매출·무료 양쪽에 있으면 한 점에 담는다

    # ── 옛 기록 이어붙이기 ───────────────────────────────────────────────
    # 개편 전에는 종목당 iOS 대표작 한 줄(games[])이었다. 그 점이 어느 게임이었는지는 같이 저장해 둔
    # 제목(t · 30자로 잘림)으로 알 수 있으므로, 제목이 맞는 앱으로 옮겨 담아 이력을 잇는다.
    legacy = {}
    ios_titles = {t: i for _, t, _, i in charts.get(("KR", "ios", "gr"), []) + charts.get(("KR", "ios", "fr"), [])}
    for g in old.get("games", []):
        for p in g.get("hist", []):
            t = p.get("t")
            if not t:
                continue
            ident = next((i for nm, i in ios_titles.items() if nm.startswith(t)), None)
            if ident:
                legacy.setdefault(("KR", "ios", ident), {})[p["d"]] = {
                    k: v for k, v in p.items() if k in ("gr", "fr")}

    out_apps = []
    keys = list(prev.keys()) + [k for k in apps if k not in prev]
    for k in keys:
        cur = apps.get(k)
        hist = {p["d"]: dict(p) for p in ((prev.get(k) or {}).get("hist") or [])}
        for d, v in legacy.get(k, {}).items():          # 옛 기록은 비어 있는 날만 채운다
            if d not in hist:
                hist[d] = dict(v, d=d)
        if cur and cur["pt"]:
            hist[today] = dict(cur["pt"], d=today)
        if not hist:
            continue
        base = cur or prev.get(k) or {}
        out_apps.append({"stock": base.get("stock"), "cc": k[0], "mk": k[1], "nm": base.get("nm"),
                         "id": k[2], "hist": [hist[d] for d in sorted(hist)][-DAYS:]})
    out_apps.sort(key=lambda a: (a["stock"] or "", a["cc"], a["mk"], (a["hist"][-1].get("gr") or 999)))

    out = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "apps": out_apps}

    for cc, _, _, _ in COUNTRIES:
        for mk, nm in (("ios", "앱스토어"), ("and", "구글플레이")):
            got = [a for a in out_apps if a["cc"] == cc and a["mk"] == mk and a["hist"][-1].get("d") == today]
            if not got:
                continue
            print("  [%s] %s: %d개" % (cc, nm, len(got)))
            for a in sorted(got, key=lambda x: x["hist"][-1].get("gr") or 999):
                p = a["hist"][-1]
                print("    %-6s %-28s 매출 %s위 · 무료 %s위"
                      % (a["stock"], a["nm"][:26], p.get("gr") or "—", p.get("fr") or "—"))

    if "--dry-run" in sys.argv:
        return
    old_h = {(a.get("cc", "KR"), a.get("mk"), a.get("id")): a.get("hist") for a in old.get("apps", [])}
    new_h = {(a["cc"], a["mk"], a["id"]): a["hist"] for a in out_apps}
    if old_h == new_h and old_h:
        print("변동 없음 — index.html 그대로 둠")
        return
    open(HTML, "w", encoding="utf-8").write(_put(html, "APPRANK", out))
    print("[OK] APPRANK 갱신 · 앱 %d개" % len(out_apps))


if __name__ == "__main__":
    main()
