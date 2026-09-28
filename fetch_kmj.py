# -*- coding: utf-8 -*-
"""한투 김명주 텔레그램 '주요 국가 아마존 뷰티 Top 100 내 브랜드별 제품 수' -> index.html 의  const KMJAMZ = {...};
(2026-09-29 신설)

왜 이걸 받나
  한투 화장품/유통 김명주 채널(t.me/kmj_retailcosmetics)이 2026-05-28 부터 거의 매일(주말·연휴 빼고)
  KST 07:30 전후에 아마존 뷰티 베스트셀러 Top100 안의 K뷰티 제품을 **텍스트로** 올린다.
    1. 에이피알 Top 100 내 제품 수: 미국 8개, 영국 7개, 독일 3개, 프랑스 10개, 스페인 10개
    - 제로모공패드: 미국 2위, 영국 1위, 독일 11위, 프랑스 10위, 스페인 26위
  우리 아마존 트래커(AMAZON)는 2026-08-02 에 시작했고 유럽은 탑50 까지만 읽는다. 이 채널이 주는 것:
    ① 8/2 이전 두 달(6월 프라임데이 포함) ② 유럽 51~100위 ③ 트래커가 빠진 날.
  2026-09-29 검산: 겹치는 30일 314쌍(브랜드×국가×날짜) 중 91% 가 **제품별 순위까지 완전 일치** — 같은 시각
  같은 리스트를 본다. 어긋난 날은 대부분 우리 트래커가 그날 일부 국가를 못 받은 날이었다.

무엇을 받나 — 평소 요청 1건
  https://t.me/s/kmj_retailcosmetics            공개 미리보기(키·로그인 불필요) · 최근 글 ~20개
  https://t.me/s/kmj_retailcosmetics?before=N   그 앞 20개 — 블록이 없거나 빈 구간이 있으면 거슬러 올라간다
  첫 실행(백필)은 5/28 글(id 7787)까지 약 30페이지.

무엇을 남기나
  KMJAMZ.asOf     **마지막 글의 날짜**(수집 시각이 아니다) — due_today('KMJAMZ', 8) 가 '오늘 글이 아직 없으면
                  다음 회차가 다시 본다' 로 쓴다. 수집 시각은 fetched.
  KMJAMZ.brands   {이름: {en(트래커 브랜드명), stock, since(채널이 처음 다룬 날)}}
  KMJAMZ.prod     [[브랜드, 제품명], ...]  — 제품 사전(인덱스로 참조)
  KMJAMZ.days     [{d, id, r:[[제품번호, US, UK, DE, FR, ES], ...]}]  순위 0 = 그 나라 Top100 밖
  값이 그대로면 파일을 건드리지 않는다(deepcopy 비교).

주의
  · **답글은 인용된 원글(js-message_reply_text)이 먼저 나온다.** 본문은 js-message_text 만 잡는다.
    처음에 인용문을 본문으로 읽어 김명주 코멘트 6건이 '잘린 순위 글'로 둔갑했다.
  · 글에 브랜드가 없는 날 = 그날 Top100 에 0개다(우리 트래커로 19번 중 18번 확인). 단 **채널이 그 브랜드를
    다루기 시작한 날(since) 전은 0 이 아니라 '모름'** 이다(아누아·조선미녀 6/18, 라네즈 6/29).
  · 2026-05-28 한 번은 '아모레퍼시픽(코스알엑스, 라네즈)' 로 묶여 왔는데 제품이 전부 코스알엑스였다 → 코스알엑스.
  · 날짜는 제목의 (MM/DD) — KST 게시일이다. 같은 날짜 글이 두 번이면 뒤의 것(정정)을 쓴다.
  · 제품명은 공백·NBSP 만 다른 변형이 섞인다('제로모공 클렌징폼'/'제로 모공 클렌징 폼') → 공백을 지운 키로 합친다.

  python fetch_kmj.py            # 수집·기록
  python fetch_kmj.py --dry-run  # 출력만
  python fetch_kmj.py --rebuild  # 파서를 고친 뒤 — 5/28 글부터 다시 받아 통째로 새로 쓴다
"""
import re, json, sys, copy, datetime, urllib.request, html as htmlmod
from collector_health import ua, nap, note_health

HTML = "public/index.html"
CH = "kmj_retailcosmetics"
KST = datetime.timezone(datetime.timedelta(hours=9))
FIRST_ID = 7787                 # 시리즈 첫 글(2026-05-28)
MK = ["US", "UK", "DE", "FR", "ES"]
CC = {"미국": "US", "영국": "UK", "독일": "DE", "프랑스": "FR", "스페인": "ES"}
CPAT = "|".join(CC)
# 채널 표기 → (표시 이름, 우리 트래커 브랜드명, 종목)
BRAND = {
    "에이피알":   ("에이피알", "medicube", "에이피알"),
    "달바글로벌": ("달바글로벌", "d'Alba", "달바글로벌"),
    "코스알엑스": ("코스알엑스", "COSRX", "아모레퍼시픽"),
    "라네즈":     ("라네즈", None, "아모레퍼시픽"),
    "아누아":     ("아누아", "Anua", None),
    "조선미녀":   ("조선미녀", "Beauty of Joseon", None),
}
MAX_PAGES = 45                  # 백필 상한(20개 × 45 = 900글 — 5/28 이후 약 600글)


def canon_brand(label):
    s = label.replace("\xa0", " ").strip()
    if "코스알엑스" in s:                      # '아모레퍼시픽_코스알엑스' · 5/28 '아모레퍼시픽(코스알엑스, 라네즈)'
        return "코스알엑스"
    if "라네즈" in s:
        return "라네즈"
    for k in BRAND:
        if k in s:
            return k
    return s                                   # 새 브랜드 — 그대로 담고 로그로 알린다


def fetch_page(before=None):
    url = f"https://t.me/s/{CH}" + (f"?before={before}" if before else "")
    req = urllib.request.Request(url, headers=ua(referer=f"https://t.me/s/{CH}", doc=True))
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def parse_page(b):
    """[(id, datetime_utc, text)] — 답글이면 본문(js-message_text)만."""
    out = []
    for m in re.split(r'<div class="tgme_widget_message_wrap', b)[1:]:
        pid = re.search(r'data-post="%s/(\d+)"' % CH, m)
        if not pid:
            continue
        dt = re.search(r'datetime="([^"]+)"', m)
        t = re.search(r'<div class="tgme_widget_message_text js-message_text[^>]*>(.*?)</div>', m, re.S)
        txt = ""
        if t:
            txt = re.sub(r"<br\s*/?>", "\n", t.group(1))
            txt = htmlmod.unescape(re.sub(r"<[^>]+>", "", txt))
        out.append((int(pid.group(1)), dt.group(1) if dt else None, txt))
    return out


def parse_post(pid, dt, txt):
    """아마존 순위 글이면 {d, id, brands:{브랜드: {제품명: {MK: 순위}}}}, 아니면 None."""
    lines = txt.replace("\xa0", " ").strip().split("\n")
    first = lines[0] if lines else ""
    if not ("아마존" in first and "Top" in first and "제품 수" in first):
        return None
    kst = datetime.datetime.fromisoformat(dt).astimezone(KST) if dt else datetime.datetime.now(KST)
    t = re.search(r"\((\d{1,2})/(\d{1,2})\)", first)
    if t:
        mo, dd = int(t.group(1)), int(t.group(2))
        y = kst.year - (1 if (mo == 12 and kst.month == 1) else 0)
        d = f"{y}-{mo:02d}-{dd:02d}"
    else:
        d = kst.strftime("%Y-%m-%d")
    brands, cur, cnt = {}, None, {}
    for raw in lines[1:]:
        line = raw.strip()
        h = re.match(r"^\d+\s*[.)]\s*(.+?)\s*(?:Top|TOP)\s*100\s*내\s*제품\s*수\s*[:：]\s*(.*)$", line)
        if h:
            cur = canon_brand(h.group(1))
            brands.setdefault(cur, {})
            cnt[cur] = {CC[c]: int(n) for c, n in re.findall(r"(%s)\s*(\d+)\s*개" % CPAT, h.group(2))}
            continue
        p = re.match(r"^[-·•]\s*(.+?)\s*[:：]\s*(.*)$", line)
        if p and cur is not None:
            rk = {CC[c]: int(n) for c, n in re.findall(r"(%s)\s*(\d+)\s*위" % CPAT, p.group(2))}
            rk = {k: v for k, v in rk.items() if 1 <= v <= 100}
            if rk:
                name = re.sub(r"\s+", " ", p.group(1)).strip()
                prev = brands[cur].get(name, {})
                prev.update(rk)
                brands[cur][name] = prev
    if not brands:
        return None
    # 개수 줄 vs 제품 줄 — 어긋나면 기록만(2026-09-29 실측 1,073건 중 5건). 제품 줄을 믿는다.
    off = []
    for b, c in cnt.items():
        for mk in set(c) | {m for v in brands[b].values() for m in v}:
            got = sum(1 for v in brands[b].values() if mk in v)
            if got != c.get(mk, 0):
                off.append(f"{b} {mk} 개수줄 {c.get(mk, 0)} vs 제품줄 {got}")
    return {"d": d, "id": pid, "brands": brands, "off": off}


def load_block(html):
    m = re.search(r"^const KMJAMZ = (\{.*?\});$", html, re.M | re.S)
    if not m:
        return None, None
    try:
        return json.loads(m.group(1)), m
    except json.JSONDecodeError:
        return None, m


def key(name):
    return re.sub(r"\s+", "", name).lower()


def main():
    dry = "--dry-run" in sys.argv
    rebuild = "--rebuild" in sys.argv          # 파서를 고쳤을 때 — 5/28 부터 다시 받는다
    html = open(HTML, encoding="utf-8").read()
    old, m = load_block(html)
    base = copy.deepcopy(old) if (old and not rebuild) else {"brands": {}, "prod": [], "days": []}
    have_ids = {x["id"] for x in base["days"]}
    last_id = max(have_ids) if have_ids else 0
    need_back = not have_ids                    # 첫 실행 = 백필

    posts, pages, before = {}, 0, None
    try:
        while pages < MAX_PAGES:
            msgs = parse_page(fetch_page(before))
            pages += 1
            if not msgs:
                break
            for pid, dt, txt in msgs:
                p = parse_post(pid, dt, txt)
                if p:
                    posts[pid] = p
            lo = min(x[0] for x in msgs)
            # 평소: 마지막으로 받은 글까지 닿으면 멈춘다. 백필: 시리즈 첫 글까지.
            stop_at = FIRST_ID if need_back else last_id
            if lo <= stop_at or (before is not None and lo >= before):
                break
            before = lo
            nap(1.0)
    except Exception as e:
        note_health("김명주 아마존", f"수집 실패: {type(e).__name__}: {str(e)[:120]}")
        print("[KMJ] 실패:", e)
        sys.exit(1)
    if pages and not posts and need_back:
        note_health("김명주 아마존", "백필에서 순위 글을 하나도 못 찾음 — 글 형식 변경 의심")
        print("[KMJ] 순위 글 0건"); sys.exit(1)
    note_health("김명주 아마존", None)

    # 제품 사전·날짜 병합
    out = copy.deepcopy(base)
    prod = out["prod"]
    pidx = {(b, key(n)): i for i, (b, n) in enumerate(prod)}
    days = {x["d"]: x for x in out["days"]}
    new_brands = set()
    for pid in sorted(posts):
        p = posts[pid]
        if p["d"] in days and days[p["d"]]["id"] > pid:
            continue                            # 같은 날짜의 더 뒤(정정) 글이 이미 있다
        rows = []
        for b, items in p["brands"].items():
            if b not in BRAND:
                new_brands.add(b)
            info = out["brands"].setdefault(b, {"en": (BRAND.get(b) or (None, None, None))[1],
                                                "stock": (BRAND.get(b) or (None, None, None))[2], "since": p["d"]})
            if p["d"] < info["since"]:
                info["since"] = p["d"]
            for name, rk in items.items():
                k = (b, key(name))
                if k not in pidx:
                    pidx[k] = len(prod)
                    prod.append([b, name])
                else:
                    prod[pidx[k]][1] = name        # 표기는 최신으로
                rows.append([pidx[k]] + [rk.get(mk, 0) for mk in MK])
        rows.sort(key=lambda r: (prod[r[0]][0], min([v for v in r[1:] if v] or [999])))
        days[p["d"]] = {"d": p["d"], "id": pid, "r": rows}
        for o in p["off"]:
            print(f"  [{p['d']}] {o}")
    out["days"] = sorted(days.values(), key=lambda x: x["d"])
    out["mk"] = MK
    out["src"] = f"https://t.me/{CH}"
    out["note"] = ("한투증권 김명주 텔레그램 '주요 국가 아마존 뷰티 Top 100 내 브랜드별 제품 수'(각국 Best Sellers in Beauty "
                   "Top100). 글에 없는 브랜드 = 그날 Top100 0개. since 전은 채널이 다루기 전이라 '모름'.")
    if new_brands:
        print("  ⚠ 사전에 없는 브랜드:", ", ".join(sorted(new_brands)), "— BRAND 에 넣을 것")

    d0, d1 = (out["days"][0]["d"], out["days"][-1]["d"]) if out["days"] else ("-", "-")
    print(f"[KMJ] 페이지 {pages} · 새 글 {len([p for p in posts if p not in have_ids])} · 날짜 {len(out['days'])}일({d0}~{d1}) · 제품 {len(prod)}")
    if out["days"]:
        last = out["days"][-1]
        agg = {}
        for r in last["r"]:
            b = prod[r[0]][0]
            a = agg.setdefault(b, [0] * len(MK))
            for j in range(len(MK)):
                a[j] += 1 if r[1 + j] else 0
        for b, a in agg.items():
            print(f"  {last['d']} {b:6} " + " ".join(f"{mk}{n}" for mk, n in zip(MK, a)))

    cmp_old = {k: v for k, v in (old or {}).items() if k not in ("asOf", "fetched")}
    cmp_new = {k: v for k, v in out.items() if k not in ("asOf", "fetched")}
    if dry:
        print("[dry-run] 저장 안 함"); return
    if old is not None and cmp_old == cmp_new:
        print("[KMJ] 변동 없음 — 파일 그대로"); return
    now = datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    final = {"asOf": d1, "fetched": now}      # asOf 를 맨 앞에 — due_today 가 이 자리를 읽는다
    final.update({k: v for k, v in out.items() if k not in ("asOf", "fetched")})
    block = "const KMJAMZ = " + json.dumps(final, ensure_ascii=False, separators=(",", ":")) + ";"
    if m:
        html = html[:m.start()] + block + html[m.end():]
    else:
        anchor = re.search(r"^const TREND = ", html, re.M)
        if not anchor:
            print("삽입 위치(const TREND)를 못 찾았습니다"); sys.exit(1)
        html = html[:anchor.start()] + block + "\n" + html[anchor.start():]
    open(HTML, "w", encoding="utf-8").write(html)
    print(f"[KMJ] KMJAMZ 블록 갱신 ({len(block)//1024}KB · 마지막 글 {d1})")


if __name__ == "__main__":
    main()
