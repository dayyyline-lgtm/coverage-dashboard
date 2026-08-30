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

수집 방법
  홈페이지 HTML 안 Next.js flight 페이로드에 캐릭터 배열이 그대로 들어 있다(브라우저 불필요).
  한 번 요청에 캐릭터 80~90개가 잡힌다(홈에 노출된 것 기준. 전체 목록은 아니다).
  같은 캐릭터가 여러 섹션(인기/신규/트렌드)에 중복 등장하므로 id 로 합친다.

  python fetch_toptoonchat.py            # 수집·기록
  python fetch_toptoonchat.py --dry-run  # 출력만
"""
import re, json, sys, gzip, datetime, urllib.request

from collector_health import ua, nap, note_health, looks_blocked

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
DAYS = 400                 # 합계 시계열 보관 일수
CHAR_HIST = 16             # 캐릭터별 시계열을 남길 상위 N명(파일 크기 관리)
SITES = [("KR", "https://chat.toptoon.com/"),
         ("JP", "https://chat.toptoon.jp/")]


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

    sites = {s.get("code"): s for s in (old.get("sites") or [])}
    ok_any, fails = False, []
    for code, url in SITES:
        try:
            chars = parse(fetch(url))
        except Exception as e:
            fails.append(f"{code} {type(e).__name__} {str(e)[:60]}")
            if looks_blocked(e):
                note_health("탑툰챗", f"{code} 차단 의심: {str(e)[:60]}")
            continue
        nap(0.4)
        if not chars:
            fails.append(f"{code} 캐릭터 0개(구조 변경 의심)")
            continue
        ok_any = True
        tot_chat = sum(c[1] or 0 for c in chars.values())
        tot_view = sum(c[2] or 0 for c in chars.values())
        tot_like = sum(c[3] or 0 for c in chars.values())

        s = sites.get(code) or {"code": code, "url": url, "hist": [], "chars": []}
        # 합계 시계열 — 하루 1점. 같은 날 다시 돌면 그 날 값을 갱신한다.
        hist = [h for h in (s.get("hist") or []) if h.get("d") != today]
        hist.append({"d": today, "chat": tot_chat, "view": tot_view,
                     "like": tot_like, "n": len(chars)})
        s["hist"] = hist[-DAYS:]

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
