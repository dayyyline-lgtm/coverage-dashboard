# -*- coding: utf-8 -*-
"""게임비트(gamebit.co.kr) 쌀먹 거래대금 수집 -> index.html 의  const GAMEBIT = {...};

왜 이걸 보나 (2026-09-02 신설)
  아이템매니아 시세(fetch_gamemoney.py)는 '가격'만 준다. 쌀먹(RMT) 경제가 실제로 얼마나 도는지는
  '양'을 봐야 하는데, 게임비트가 거래소(플랫폼 M/B) 합산 분봉 캔들에 **거래량(원화)** 을 실어 준다.
  게임머니 가격이 오르는데 거래대금까지 늘면 신규·복귀 유입이 진짜고, 가격만 오르고 양이 줄면
  공급 고갈(이탈)이다. 둘을 나눠 봐야 한다.

무엇을 받나
  /{game}                             index-config JSON: jsonDir·서버 목록(serverDisplayUnits)·단위
  /jdata2/{game}/total_status.json    서버별 현재가·등락 (전 서버 평균 시세 = 아이템매니아엔 없던 것)
  /v3_get_chart_data.php?game=&sid=&type=min   분봉 {time, open, high, low, close, volume}
    · ⚠ volume 은 원화가 아니라 **게임머니 수량**이다(2026-09-02 검증). 처음엔 원화로 읽어
      아이온2 하루 9,040억·리클 137억이 나왔다. 서버 JSON 의 거래내역 합(제우스 8서버 7,130만원)과
      맞추면 원화 = 수량 × 그 캔들 종가 ÷ 단위수량(defaultGameUnit 의 '1만다이아'→1e4, '1천만키나'→1e7,
      'ADENA'→1e4[아데나 시세는 1만당 가격], '1천다이아'→1e3). 아이온은 수량이 만키나 단위라 ×10,000 을 먼저 곱한다
      (사이트 normalizeVolumeToKRW 와 같은 계수).
    · 사이트가 약 2주치만 들고 있다 → 첫 수집 때 그만큼 백필, 이후 매일 쌓아 늘린다.
    · 오늘(수집 시각까지)은 부분치라 저장은 하되 화면은 전일까지가 확정이다.

어디를 보나 — 전 서버를 다 받는다(제우스 30 · 아이온2 44 · 리니지클래식 31).
  리니지M 은 280서버라 앞 20서버 표본으로 고정(요청 수). 하루 ~130요청, 간격 0.15s.
  ⚠ 단위가 게임마다 다르다(1만다이아·1천만키나·ADENA…). 아이템매니아 '게임머니' 와 같은 물건이
    아닐 수 있으니 두 소스의 가격을 직접 비교하지 말 것 — 방향만 겹쳐 본다.

  python fetch_gamebit.py            # 수집·기록
  python fetch_gamebit.py --dry-run  # 출력만
"""
import re, json, sys, gzip, copy, datetime, urllib.request, collections

from collector_health import ua, nap, note_health, looks_blocked

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
BASE = "https://gamebit.co.kr"
DAYS = 400
GAMES = [
    {"key": "zeus",     "stock": "컴투스", "name": "제우스",     "max": None},
    {"key": "aion",     "stock": "NC",    "name": "아이온2",    "max": None},
    {"key": "lineage",  "stock": "NC",    "name": "리니지클래식", "max": None},
    {"key": "lineagem", "stock": "NC",    "name": "리니지M",    "max": 20},   # 280서버 → 표본
]
VOL_MULT = {"aion": 10_000, "maple": 100_000_000, "mapleworld": 100_000_000}   # 수량 단위 보정(사이트 계수)


def unit_qty(unit):
    """defaultGameUnit → 가격이 걸린 수량. '1만다이아/W'→1e4 · '1천만키나/W'→1e7 · 'ADENA/W'→1e4 · '1천다이아/W'→1e3"""
    u = (unit or "").split("/")[0]
    if "ADENA" in u.upper():
        return 10_000
    m = re.match(r"(\d+)?(천만|만|천)?", u)
    n = int(m.group(1)) if m and m.group(1) else 1
    k = {"천만": 10_000_000, "만": 10_000, "천": 1_000, None: 1}[m.group(2) if m else None]
    return n * k


def get(path, ref="/"):
    req = urllib.request.Request(BASE + path, headers=ua(referer=BASE + ref))
    r = urllib.request.urlopen(req, timeout=30)
    raw = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", "replace")


def config(game):
    h = get(f"/{game}")
    m = re.search(r'index-config[^>]*>(.*?)</script>', h, re.S)
    if not m:
        raise RuntimeError("index-config 없음")
    return json.loads(m.group(1))


def _put(html, name, obj):
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
    m = re.search(r"const GAMEBIT = (\{.*?\});", html, re.S)
    old = {}
    if m:
        try:
            old = json.loads(m.group(1))
        except json.JSONDecodeError:
            old = {}
    prev = {g["key"]: g for g in copy.deepcopy(old.get("games") or [])}   # deepcopy — 자기비교 SKIP 방지

    games, fails, ok_any = [], [], False
    for g in GAMES:
        p = prev.get(g["key"]) or {}
        hist = {h["d"]: h for h in (p.get("hist") or [])}
        try:
            cfg = config(g["key"])
        except Exception as e:
            fails.append(f"{g['name']} config {type(e).__name__}")
            games.append(p if p.get("hist") else {**g, "hist": []}); continue
        sids = list((cfg.get("serverDisplayUnits") or {}).keys())
        # 표본 서버는 처음 정한 목록으로 고정 — 명단이 흔들리면 합계가 흔들린다
        if g["max"]:
            sids = (p.get("sample") or sids[:g["max"]])
        mult = VOL_MULT.get(g["key"], 1)
        uq = unit_qty(cfg.get("defaultGameUnit", ""))
        day_vol = collections.defaultdict(float)
        day_cnt = collections.Counter()
        day_px = collections.defaultdict(list)
        got = 0
        for sid in sids:
            try:
                d = json.loads(get(f"/v3_get_chart_data.php?game={g['key']}&sid={sid}&type=min", f"/{g['key']}"))
            except Exception as e:
                if looks_blocked(e):
                    note_health("게임비트", f"{g['name']} 차단 의심: {str(e)[:60]}")
                continue
            got += 1
            last_by_day = {}
            for x in d or []:
                k = datetime.datetime.fromtimestamp(int(x["time"]), KST).strftime("%Y-%m-%d")
                v = float(x.get("volume") or x.get("vol") or 0) * mult      # 게임머니 수량
                c = float(x.get("close") or 0)
                if v > 0 and c > 0:
                    day_vol[k] += v * c / uq; day_cnt[k] += 1               # → 원화
                last_by_day[k] = c
            for k, c in last_by_day.items():
                if c > 0:
                    day_px[k].append(c)
            nap(0.15)
        if not got:
            fails.append(f"{g['name']} 서버 0개 수신")
            games.append(p if p.get("hist") else {**g, "hist": []}); continue
        ok_any = True
        for k in set(day_vol) | set(day_px):
            row = {"d": k, "krw": round(day_vol.get(k, 0)), "n": day_cnt.get(k, 0),
                   "p": round(sum(day_px[k]) / len(day_px[k]), 1) if day_px.get(k) else None,
                   "sv": got}
            if k == today:
                row["partial"] = True             # 수집 시각까지의 부분치
            # 확정된 날(과거)은 사이트가 더 완전한 값을 줄 수 있으므로 늘 덮어쓴다
            hist[k] = row
        hs = [hist[k] for k in sorted(hist)][-DAYS:]
        games.append({"key": g["key"], "stock": g["stock"], "name": g["name"],
                      "unit": cfg.get("defaultGameUnit", ""), "uq": uq, "servers": got,
                      "sample": sids if g["max"] else None, "hist": hs})
        yd = [h for h in hs if not h.get("partial")]
        if yd:
            h = yd[-1]
            print(f"  {g['name']:8s} {h['d']} 거래대금 {h['krw']/1e4:,.0f}만원 · {h['n']}건 · 평균가 {h['p']} · 서버 {got} · {len(hs)}일치")

    if not ok_any:
        note_health("게임비트", "전부 실패: " + "; ".join(fails)[:120])
        print("[실패] 수집 0건"); sys.exit(1)
    if fails:
        print("  일부 실패:", "; ".join(fails))
    else:
        note_health("게임비트", None)

    out = {"asOf": now.strftime("%Y-%m-%d %H:%M KST"), "src": "게임비트 거래소 합산 분봉",
           "games": games}
    if "--dry-run" in sys.argv:
        print(json.dumps(out, ensure_ascii=False)[:800]); return
    if m:
        a, b = dict(old), dict(out); a.pop("asOf", None); b.pop("asOf", None)
        if a == b:
            print("[SKIP] 변동 없음"); return
    open(HTML, "w", encoding="utf-8").write(_put(html, "GAMEBIT", out))
    print(f"[OK] GAMEBIT 갱신 · 게임 {len(games)}개")


if __name__ == "__main__":
    main()
