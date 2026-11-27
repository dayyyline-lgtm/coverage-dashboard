# -*- coding: utf-8 -*-
"""신한서부티엔디리츠 IR 자료 → 리츠 실측 월별 ADR·투숙률 자동 추가 (2026-11-27 · 사용자 "앞으로 알아서 업뎃되게")

리츠가 IR 자료를 홈페이지 공시 게시판(shsbreit.com · bid=7)에 PDF 로 올린다(NDR·Corporate Day 때마다 · 분기에 2~3번).
'호텔 자산 실적' 쪽의 ADR·OCC 차트(호텔 셋: 용산 그랜드 머큐어 · 신라스테이 광화문 · 신라스테이 마포)에서 **올해 선**의 좌표를 읽어
이미 가진 올해 달 값으로 눈금(기울기·절편)을 맞추고, 그 뒤 새 달을 더한다. ADR 은 점 옆 숫자 라벨이 있으면 그 값(천원 · 정수).

  python hotel_adr/reit_ir.py            # 새 게시물만 받아 넣기 → 바뀌면 build.py 로 블록 다시 만들기
  python hotel_adr/reit_ir.py --dry-run  # 읽기만
  python hotel_adr/reit_ir.py --pdf 파일 # 내려받은 PDF 로 시험

⚠ 맞춤이 어긋나면(ADR 잔차 3천원 · 투숙률 1.5%p 넘음 · 겹치는 달 4개 미만) 넣지 않고 health 에 남긴다 — 사람이 RUNBOOK 대로 손으로.
⚠ 해가 바뀌어 올해 선이 1~3점뿐이면 겹치는 달이 모자라 1월 판은 못 읽는다(그다음 판에서 저절로 붙는다).
"""
import io, json, os, re, sys, html, subprocess, urllib.parse, urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collector_health import note_health

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, "data", "reit_monthly.json")
BASE = "https://shsbreit.com"
LIST = BASE + "/kr/sub/disclosure/disclosure.php?bid=7"
HOTELS = ["gm_ys", "stay_ghm", "stay_mapo"]          # 쪽 왼쪽부터
TITLES = {"gm_ys": "그랜드머큐어", "stay_ghm": "광화문", "stay_mapo": "마포"}
NOW_C = (0.0, 0.275, 1.0)                              # 올해 선 색(2026-04·10·11 판 같음)


def get(u, t=60):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=t).read()


def posts():
    """게시판 첫 쪽 → [(idx, 제목, 날짜, pdf 경로)] — 제목에 IR·NDR·Corporate 가 든 것만."""
    t = get(LIST, 30).decode("utf-8", "replace")
    out = []
    for m in re.finditer(r'href="[^"]*mode=view&(?:amp;)?bid=7&(?:amp;)?idx=(\d+)[^"]*"[^>]*>(.*?)</a>', t, re.S):
        ttl = re.sub(r"\s+", " ", html.unescape(re.sub("<[^>]+>", "", m.group(2)))).strip()
        if not re.search(r"IR|NDR|Corporate|기업설명", ttl, re.I):
            continue
        v = get(f"{BASE}/kr/sub/disclosure/disclosure.php?mode=view&bid=7&idx={m.group(1)}", 30).decode("utf-8", "replace")
        pdf = re.findall(r'href="([^"]*\.pdf)"', v)
        d = re.findall(r"(\d{4})[.-](\d{2})[.-](\d{2})", v)
        if pdf and d:
            out.append((int(m.group(1)), ttl, "-".join(d[0]), html.unescape(pdf[0])))
    return out


def read_pdf(b):
    """→ {호텔: {"occ": [y…], "adr": [y…], "lab": {i: 정수}}} (올해 선 좌표 · 점 i = i+1 월)"""
    import pdfplumber
    with pdfplumber.open(io.BytesIO(b)) as d:
        for pg in d.pages:
            t = pg.extract_text() or ""
            if "호텔" not in t or "ADR" not in t or "OCC" not in t:
                continue
            cs = [c for c in pg.curves if tuple(round(x, 3) for x in (c.get("stroking_color") or ())) == NOW_C and len(c.get("pts") or []) >= 3]
            if len(cs) < 6:
                continue
            W = float(pg.width)
            ws = pg.extract_words()
            out = {}
            for j, k in enumerate(HOTELS):
                x0, x1 = W * j / 3, W * (j + 1) / 3
                mine = sorted([c for c in cs if x0 <= c["x0"] < x1], key=lambda c: c["top"])
                if len(mine) < 2:
                    return None
                occ, adr = mine[0], mine[-1]                  # 위 = 투숙률 · 아래 = ADR
                pts = [(float(x), float(y)) for x, y in adr["pts"]]
                lab = {}
                for i, (x, y) in enumerate(pts):              # 점 바로 위 숫자 라벨(±9px · 위로 30px 안)
                    near = [w for w in ws if w["text"].isdigit() and 2 <= len(w["text"]) <= 3
                            and abs((w["x0"] + w["x1"]) / 2 - x) < 9 and 0 < y - w["bottom"] < 30]
                    if near:
                        lab[i] = int(min(near, key=lambda w: y - w["bottom"])["text"])
                out[k] = {"occ": [float(y) for _, y in occ["pts"]], "adr": [y for _, y in pts], "lab": lab}
            return out
    return None


def fit(known, ys):
    """known = [(i, 값)] · ys = 좌표 → (값 = a + b·y 의 함수, 최대 잔차)"""
    xs = [ys[i] for i, _ in known]; vs = [v for _, v in known]
    n = len(xs); mx = sum(xs) / n; mv = sum(vs) / n
    b = sum((x - mx) * (v - mv) for x, v in zip(xs, vs)) / sum((x - mx) ** 2 for x in xs)
    a = mv - b * mx
    return (lambda y: a + b * y), max(abs(a + b * x - v) for x, v in zip(xs, vs))


def merge(R, got, key):
    """새 달을 R 에 더한다 → [(호텔, 달, adr, occ)] · 실패 사유 목록"""
    added, bad = [], []
    for k, g in got.items():
        M = R["m"].get(k, {})
        if not M:
            continue
        Y = max(m[:4] for m in M)
        n = len(g["adr"])
        known = [(i, M[f"{Y}-{i + 1:02d}"]) for i in range(n) if f"{Y}-{i + 1:02d}" in M]
        if len(known) < 4:
            bad.append(f"{k} 겹치는 달 {len(known)}개"); continue
        fa, ra = fit([(i, v[0]) for i, v in known], g["adr"])
        fo, ro = fit([(i, v[1]) for i, v in known], g["occ"][:n])
        if ra > 3 or ro > 1.5:
            bad.append(f"{k} 맞춤 잔차 ADR {ra:.1f} · 투숙률 {ro:.1f}"); continue
        for i in range(n):
            ym = f"{Y}-{i + 1:02d}"
            if ym in M:
                continue
            a = g["lab"].get(i)
            a2 = round(fa(g["adr"][i]), 1)
            if a is None or abs(a - a2) > 6:                 # 라벨이 없거나 엉뚱하면 좌표 값
                a = a2
            o = round(fo(g["occ"][i]), 1) if i < len(g["occ"]) else None
            M[ym] = [float(a), o, key]
            added.append((k, ym, a, o))
    return added, bad


def main():
    dry = "--dry-run" in sys.argv
    R = json.load(open(P, encoding="utf-8"))
    seen = {v[1] for v in R["src"].values() if isinstance(v, list) and len(v) > 1}
    todo = []
    if "--pdf" in sys.argv:
        f = sys.argv[sys.argv.index("--pdf") + 1]
        todo.append(("rtest", "시험", open(f, "rb").read(), f))
    else:
        try:
            ps = posts()
        except Exception as e:
            note_health("리츠 IR(호텔 ADR)", f"게시판 실패: {str(e)[:60]}"); print("[REIT] 게시판 실패", e); return
        for idx, ttl, d, pdf in sorted(ps):
            url = f"{BASE}/kr/sub/disclosure/disclosure.php?mode=view&bid=7&idx={idx}"
            if url in seen or BASE + pdf in seen:
                continue
            key = "r" + d[2:4] + d[5:7]
            while key in R["src"]:
                key += "b"
            try:
                todo.append((key, f"신한서부티엔디리츠 {ttl}({d} · 홈페이지 IR 게시판) — 호텔 자산 실적 차트 자동 판독(올해 선 · 겹친 달로 눈금 맞춤 · ADR 은 숫자 라벨)",
                             get(BASE + urllib.parse.quote(pdf), 90), url))
            except Exception as e:
                print("[REIT] PDF 실패", ttl, e)
    if not todo:
        print("[REIT] 새 IR 자료 없음"); note_health("리츠 IR(호텔 ADR)", None); return
    tot, bads = [], []
    for key, desc, b, url in todo:
        got = read_pdf(b)
        if not got:
            bads.append(f"{desc[:30]}: 호텔 실적 차트를 못 찾음")
            if not dry and key != "rtest":
                R["src"][key] = [desc + " — 차트 없음(건너뜀)", url]
            continue
        added, bad = merge(R, got, key)
        bads += bad
        if key != "rtest" and not dry:
            R["src"][key] = [desc, url]
        tot += added
        for a in added:
            print(f"[REIT] {a[0]} {a[1]} ADR {a[2]} · 투숙률 {a[3]}")
    note_health("리츠 IR(호텔 ADR)", (" · ".join(bads))[:160] if bads else None)
    if dry or "--pdf" in sys.argv:
        print("[REIT] 읽기만 —", len(tot), "칸"); return
    json.dump(R, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(P, "a", encoding="utf-8").write("\n")
    if tot:
        subprocess.run([sys.executable, os.path.join(HERE, "build.py")], check=False)
    print(f"[REIT] {len(tot)}칸 추가")


if __name__ == "__main__":
    main()
