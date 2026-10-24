"""카지노 월간 영업실적(DART 공정공시) -> index.html 의  const CASINO = {...};   (2026-10-24 신설 · 종목별 손익 모델 ISM)

파라다이스·롯데관광개발(드림타워)·GKL 은 매달 초 '(연결재무제표기준)영업(잠정)실적(공정공시)' 로 지난달 카지노 매출을 낸다.
  카지노매출액(테이블·머신) · 호텔 매출액(롯데관광) · 테이블 드롭액(당월·전월·전년동월) — 당월은 잠정, 다음 달 공시의 '전기실적'이 확정.
  월 합 = DART 분기 카지노 매출(롯데관광 6분기 전부 일치 · 2026-10-24 조사) → 진행 분기를 관측 달 + 남은 달(드롭 × 정상 홀드)로 세운다.
⚠ 제목이 분기 잠정실적과 같다 — '실적기간 당기실적'이 한 달인 것만 쓴다.
⚠ 파라다이스 2026-03 공시의 전년동월 칸이 '81.922'(쉼표 자리에 점) — 세 자리 점은 천 단위로 읽는다.
⚠ 롯데관광 카지노 매출은 순매출(GGR − 에이전트 수수료) — 카지노협회 집계와 다르다(공시 주석). GKL 은 참고(외국인 카지노 시장 온도).

python fetch_casino.py          # 최근 4개월 공시만(평소)
python fetch_casino.py --all    # 2024-01 부터 다시
"""
import datetime, html as _html, io, json, re, sys, time, urllib.request, zipfile

import fetch_c2model as C2
from collector_health import note_health

KST = datetime.timezone(datetime.timedelta(hours=9))
HTML = "public/index.html"
CORPS = {"파라다이스": "00171265", "롯데관광개발": "00231372", "GKL": "00557508"}
LINES = {"c": r"카지노\s*매출액", "t": r"-\s*테\s*이\s*블", "mc": r"-\s*머\s*신", "h": r"호텔\s*매출액"}


def get(u, t=60):
    return urllib.request.urlopen(u, timeout=t).read()


def filings(corp, bgn):
    out, page = [], 1
    while True:
        d = json.loads(get(f"https://opendart.fss.or.kr/api/list.json?crtfc_key={C2.DART_KEY}&corp_code={corp}"
                           f"&bgn_de={bgn}&pblntf_ty=I&page_count=100&page_no={page}").decode())
        out += [r for r in d.get("list", []) if "잠정" in r["report_nm"] and "실적" in r["report_nm"]]
        if page >= int(d.get("total_page") or 1):
            return sorted(out, key=lambda r: r["rcept_no"])
        page += 1
        time.sleep(0.3)


def text(rcept):
    z = zipfile.ZipFile(io.BytesIO(get(f"https://opendart.fss.or.kr/api/document.xml?crtfc_key={C2.DART_KEY}&rcept_no={rcept}")))
    t = z.read(max(z.namelist(), key=lambda n: z.getinfo(n).file_size)).decode("utf-8", errors="replace")
    return re.sub(r"(\s*\|\s*)+", " | ", re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " | ", t))))


def n(s):
    s = s.strip().replace("%", "")
    if re.fullmatch(r"\d{1,3}\.\d{3}", s):          # '81.922' = 81,922
        s = s.replace(".", "")
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def parse(tx):
    """한 달 공시 → (당월 'YYYY-MM', 전월, 전년동월, {키: [당월, 전월, 전년동월]}) · 한 달이 아니면 None."""
    m = re.search(r"당기실적 \| (\d{4})-(\d{2})-01 \| ~ \| (\d{4})-(\d{2})-(\d{2})", tx)
    if not m or (m.group(1), m.group(2)) != (m.group(3), m.group(4)):
        return None
    cur = f"{m.group(1)}-{m.group(2)}"
    y, mo = int(m.group(1)), int(m.group(2))
    prev = f"{y - (mo == 1)}-{12 if mo == 1 else mo - 1:02d}"
    yago = f"{y - 1}-{mo:02d}"
    i = tx.find("카지노")                                   # 당월 표(누계 표 앞)
    j = tx.find("당기누", i) if i >= 0 else -1
    blk = tx[i:j if j > i else i + 3000] if i >= 0 else ""
    vals = {}
    for k, pat in LINES.items():
        mm = re.search(pat + r" \| ([^|]+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \| ([^|]+)", blk)
        if mm:
            vals[k] = [n(mm.group(1)), n(mm.group(2)), n(mm.group(5))]
    dm = re.search(r"(?:드랍|드롭)액.*?=+ \| [^|]*?\| ([\d,]+) ([\d,]+) -?[\d.]+%? ([\d,]+)", tx)
    if dm:
        vals["d"] = [n(dm.group(1)), n(dm.group(2)), n(dm.group(3))]
    return cur, prev, yago, vals


def main():
    html = open(HTML, encoding="utf-8").read()
    m = re.search(r"^const CASINO = (\{.*?\});$", html, re.M | re.S)
    old = json.loads(m.group(1)) if m else {"m": {}}
    now = datetime.datetime.now(KST)
    bgn = "20240101" if ("--all" in sys.argv or not m) else (now - datetime.timedelta(days=130)).strftime("%Y%m%d")
    out = {"m": {k: dict(v) for k, v in (old.get("m") or {}).items()}}
    fails = []
    for nm, corp in CORPS.items():
        try:
            F = filings(corp, bgn)
        except Exception as e:
            fails.append(f"{nm} 목록 {type(e).__name__}"); continue
        M = out["m"].setdefault(nm, {})
        conf = set()                                         # 확정(다음 달 공시의 전월) 값으로 채운 달
        for r in F:
            try:
                p = parse(text(r["rcept_no"]))
            except Exception as e:
                fails.append(f"{nm} {r['rcept_no']} {type(e).__name__}"); continue
            time.sleep(0.35)
            if not p:
                continue
            cur, prev, yago, vals = p
            for idx, ym in ((2, yago), (0, cur), (1, prev)):     # 전년동월 < 당월(잠정) < 전월(확정) 순으로 덮는다
                if idx == 2 and ym in M:
                    continue
                if idx == 0 and ym in conf:
                    continue
                row = {k: round(v[idx] / 1000, 3) for k, v in vals.items() if v[idx] is not None}
                if row:
                    M[ym] = {**M.get(ym, {}), **row}
                    if idx == 1:
                        conf.add(ym)
        out["m"][nm] = {k: M[k] for k in sorted(M)}
        last = max(M) if M else "-"
        print(f"[카지노] {nm:6} 공시 {len(F)}건 · 월 {len(M)}개 · 마지막 {last} {M.get(last)}")
    note_health("카지노 월간(DART)", "; ".join(fails[:3]) if len(fails) > 3 else None)
    if m and old.get("m") == out["m"]:
        print("[카지노] 변동 없음"); return
    out = {"asOf": now.strftime("%Y-%m-%d %H:%M KST"), "unit": "십억원(드롭 d 포함)", "m": out["m"],
           "note": "c 카지노 매출(t 테이블 · mc 머신) · h 호텔 매출(롯데관광) · d 테이블 드롭액 — DART 월간 잠정실적, 전월 값은 다음 달 공시의 확정치"}
    block = "const CASINO = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";"
    if m:
        html = html[:m.start()] + block + html[m.end():]
    else:
        a = re.search(r"^const TREND = ", html, re.M)
        html = html[:a.start()] + block + "\n" + html[a.start():]
    open(HTML, "w", encoding="utf-8").write(html)
    print(f"[카지노] CASINO 블록 갱신 {len(block) // 1024}KB")


if __name__ == "__main__":
    main()
