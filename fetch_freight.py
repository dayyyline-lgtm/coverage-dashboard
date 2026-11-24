"""유럽 운송비 -> index.html 의  const FREIGHT = {...};   (2026-11-24 신설)

사용자: "유럽 내 운송비 가격 추이 — 에이피알이 영향받는 가격(트럭) 확인" → "트럭도 세세하게" → "각 지표가 무엇을 의미하는지 정리 + 관련 종목 대시보드에".
화면 = 종목 페이지 손익 탭 '유럽 운송비'(renderFreight · FREIGHT_MAP 종목) + 트렌드 탭 '유럽 경유가'·'아시아→유럽 해상운임'(injectFreightTrends).

자동으로 받는 것 둘:
  ① 경유가 — EU 집행위원회 Weekly Oil Bulletin 'Price developments 2005 onwards'(xlsx · 세금 포함 · 매주 월요일 가격을 목요일쯤 공개).
     EU 가중평균 + 독일·프랑스·이탈리아·스페인·네덜란드·벨기에·폴란드 · 2022-01 부터 · €/L.
     트럭 운행비의 가장 큰 변동 항목이라 '유럽 트럭 운임의 주간 대용 지표'로 쓴다(3Q26 운임 상승의 주원인 = 경유 · Upply·Ti·IRU).
     ⚠ 파일이 4MB 라 마지막 값이 9일 안쪽이면 받지 않는다(새 값은 일주일에 한 번).
     ⚠ openpyxl 없이 표준 라이브러리로 읽는다(러너 events.yml 은 requests·trendspy 만 깐다).
  ② 해상운임 — Drewry World Container Index 주간 평가(drewry.co.uk · 목요일) 본문에서 종합·상하이→로테르담·상하이→제노바 $/40ft.
     처음엔 freight/wci_seed.json(기사로 모은 과거값)으로 시작하고, 그 뒤 매주 그 주 평가를 덧붙인다.
손으로 넣는 것: freight/manual.json(유럽 도로운임 분기 지수·노선 €/km · 프랑스 월간 €/km · TIMOCOM · KCCI) — 그대로 FREIGHT.man.

python fetch_freight.py                 # 러너(events.yml 05시 · freight.yml)
python fetch_freight.py --xlsx <파일>    # 받아 둔 Oil Bulletin 파일로(로컬 시험 · 첫 시드)
"""
import datetime, io, json, re, sys, urllib.request, zipfile
import xml.etree.ElementTree as ET

from collector_health import note_health, ua

KST = datetime.timezone(datetime.timedelta(hours=9))
HTML = "public/index.html"
WOB = "https://energy.ec.europa.eu/document/download/906e60ca-8b6a-44e7-8589-652854d2fd3f_en?filename=Weekly_Oil_Bulletin_Prices_History_maticni_4web.xlsx"
WOB_PAGE = "https://energy.ec.europa.eu/data-and-analysis/weekly-oil-bulletin_en"
WCI = "https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry"
CTRY = ["EU", "DE", "FR", "IT", "ES", "NL", "BE", "PL"]
START = "2022-01-01"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def get(url, tries=3, timeout=90):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=ua(doc=True))
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception as e:
            last = e
    raise last


# ── ① Oil Bulletin xlsx — 표준 라이브러리로 '세금 포함' 시트만 ─────────────────────
def _col(ref):
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_sheet(data, want="Prices with taxes"):
    z = zipfile.ZipFile(io.BytesIO(data))
    sst = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            sst.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rmap = {r.get("Id"): r.get("Target") for r in rels}
    target = None
    for sh in wb.find("m:sheets", NS):
        if sh.get("name", "").strip().lower() == want.lower():
            target = rmap[sh.get("{%s}id" % NS["r"])]
    if not target:
        raise RuntimeError(f"시트 '{want}' 없음")
    path = "xl/" + target.lstrip("/").replace("xl/", "", 1) if not target.startswith("xl/") else target
    rows = []
    for _, el in ET.iterparse(z.open(path)):
        if el.tag != "{%s}row" % NS["m"]:
            continue
        r = {}
        for c in el.findall("m:c", NS):
            v = c.find("m:v", NS)
            if v is None:
                continue
            t, x = c.get("t"), v.text
            if t == "s":
                x = sst[int(x)]
            else:
                try:
                    x = float(x)
                except (TypeError, ValueError):
                    pass
            r[_col(c.get("r"))] = x
        rows.append(r)
        el.clear()
    return rows


def diesel_from_xlsx(data):
    rows = read_sheet(data)
    hdr = rows[0]
    idx = {}
    for i, h in hdr.items():
        if isinstance(h, str) and h.endswith("_price_with_tax_diesel"):
            idx[h.split("_")[0]] = i
    miss = [c for c in CTRY if c not in idx]
    if miss:
        raise RuntimeError(f"열 없음: {miss}")
    base = datetime.date(1899, 12, 30)
    out = {}
    for r in rows[1:]:
        d = r.get(0)
        if not isinstance(d, float):
            continue
        day = (base + datetime.timedelta(days=int(d))).isoformat()
        if day < START:
            continue
        vals = []
        for c in CTRY:
            v = r.get(idx[c])
            vals.append(round(v / 1000, 3) if isinstance(v, float) and v > 0 else None)
        if vals[0] is not None:
            out[day] = vals
    if len(out) < 100:
        raise RuntimeError(f"주 수가 너무 적다({len(out)})")
    w = sorted(out)
    s = {c: [out[d][i] for d in w] for i, c in enumerate(CTRY)}
    # 검산 — EU 평균은 1~3.5 €/L 안쪽이어야 한다(단위가 바뀌면 여기서 멈춘다)
    bad = [v for v in s["EU"] if v is not None and not (0.8 < v < 3.5)]
    if bad:
        raise RuntimeError(f"EU 경유가 범위 밖 {bad[:3]}")
    return {"w": w, "c": CTRY, "s": s}


# ── ② Drewry WCI — 이번 주 평가 본문에서 ──────────────────────────────────────
MON = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def _num(s):
    return int(s.replace(",", ""))


def wci_from_html(html):
    txt = re.sub(r"<[^>]+>", " ", html)
    txt = re.sub(r"&nbsp;|&#160;", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    m = re.search(r"assessment for \w+,? (\d{1,2}) ([A-Za-z]{3})[a-z]* (\d{4})", txt)
    if not m:
        raise RuntimeError("평가일을 못 찾음")
    d = datetime.date(int(m.group(3)), MON[m.group(2).lower()[:3]], int(m.group(1))).isoformat()
    body = txt[m.end(): m.end() + 4000]
    comp = re.search(r"World Container Index \(WCI\)[^$]{0,160}?\$([\d,]{4,6}) per 40", body)

    def lane(dest):
        # 'Shanghai to Rotterdam … $3,496' · 'Shanghai–Rotterdam … $3,496' · 'to Rotterdam rose 3% to $2,552'
        # '… to $3,997 per 40ft container from Shanghai to Rotterdam'(값이 앞) 을 먼저 — 아니면 다음 문장의 값을 집는다.
        # 뒤 값을 찾을 땐 문장 끝('. ')·글머리(•)를 넘지 않는다.
        gap = r"(?:(?!\.\s|•)[^$]){0,90}?"
        for p in (r"\$([\d,]{4,6}) per 40\s?ft(?: container)?,? (?:from|on) Shanghai\s*(?:to|–|-)\s*%s" % dest,
                  r"Shanghai\s*(?:to|–|-)\s*%s%s\$([\d,]{4,6})" % (dest, gap),
                  r"to %s(?:(?!\.\s|•)[^$]){0,40}?\$([\d,]{4,6})" % dest):
            x = re.search(p, body)
            if x:
                return _num(x.group(1))
        return None

    row = [d, _num(comp.group(1)) if comp else None, lane("Rotterdam"), lane("Genoa")]
    for v in row[1:]:
        if v is not None and not (500 <= v <= 25000):
            raise RuntimeError(f"WCI 값 범위 밖 {row}")
    if row[1] is None and row[2] is None:
        raise RuntimeError("WCI 값을 못 찾음")
    return row


def merge_wci(old_h, row):
    by = {r[0]: list(r) for r in old_h}
    cur = by.get(row[0], [row[0], None, None, None])
    by[row[0]] = [row[0]] + [n if n is not None else o for n, o in zip(row[1:], cur[1:])]
    return [by[k] for k in sorted(by)]


# ── 블록 ──────────────────────────────────────────────────────────────────
def main():
    xlsx = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--xlsx=")), None)
    if "--xlsx" in sys.argv:
        xlsx = sys.argv[sys.argv.index("--xlsx") + 1]
    now = datetime.datetime.now(KST)
    html = open(HTML, encoding="utf-8").read()
    m = re.search(r"^const FREIGHT = (\{.*?\});$", html, re.M | re.S)
    old = json.loads(m.group(1)) if m else {}
    out = json.loads(json.dumps(old)) if old else {}
    bad = []

    # ① 경유가
    dz = old.get("diesel")
    last = dz["w"][-1] if dz and dz.get("w") else None
    stale = (not last) or (now.date() - datetime.date.fromisoformat(last)).days >= 9
    if xlsx or stale:
        try:
            data = open(xlsx, "rb").read() if xlsx else get(WOB)
            dz = diesel_from_xlsx(data)
            print(f"[FREIGHT] 경유가 {len(dz['w'])}주 · 마지막 {dz['w'][-1]} EU €{dz['s']['EU'][-1]}")
        except Exception as e:
            bad.append(f"경유가 {type(e).__name__}: {e}")
            print(f"[FREIGHT] 경유가 실패 {e}")
    else:
        print(f"[FREIGHT] 경유가 마지막 {last} — 새 주 전이라 건너뜀")
    if dz:
        out["diesel"] = dz

    # ② WCI
    h = (old.get("wci") or {}).get("h")
    if not h:
        h = json.load(open("freight/wci_seed.json", encoding="utf-8"))["h"]
    if not xlsx:
        try:
            row = wci_from_html(get(WCI, timeout=40).decode("utf-8", "replace"))
            prev = next((r for r in reversed(h) if r[0] < row[0] and r[2]), None)
            if prev and row[2] and abs(row[2] / prev[2] - 1) > 0.45:
                raise RuntimeError(f"로테르담 주간 변화가 너무 크다 {prev} → {row}")
            h = merge_wci(h, row)
            print(f"[FREIGHT] WCI {row}")
        except Exception as e:
            bad.append(f"WCI {type(e).__name__}: {e}")
            print(f"[FREIGHT] WCI 실패 {e}")
    out["wci"] = {"h": h, "cols": ["평가일", "종합", "상하이→로테르담", "상하이→제노바"],
                  "src": "Drewry World Container Index · 주간(목) 스팟 · $/40ft · 기본운임+유류할증+기타 할증(도착지 THC 제외)"}

    # 손으로 넣는 값
    out["man"] = json.load(open("freight/manual.json", encoding="utf-8"))
    out.pop("asOf", None)
    note_health("유럽 운송비", "; ".join(bad) if bad else None)
    if m and json.dumps({k: v for k, v in old.items() if k != "asOf"}, sort_keys=True) == json.dumps(out, sort_keys=True):
        print("[FREIGHT] 변동 없음"); return
    out = {"asOf": now.strftime("%Y-%m-%d %H:%M KST"), **out,
           "srcDiesel": "EU 집행위원회 Weekly Oil Bulletin · 경유 소비자가(세금 포함) · 매주 월요일 가격 · €/L", "srcPage": WOB_PAGE}
    block = "const FREIGHT = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";"
    if m:
        html = html[:m.start()] + block + html[m.end():]
    else:
        a = re.search(r"^const ECOS = ", html, re.M)
        html = html[:a.start()] + block + "\n" + html[a.start():]
    open(HTML, "w", encoding="utf-8").write(html)
    print(f"[FREIGHT] 블록 갱신 {len(block) // 1024}KB")


if __name__ == "__main__":
    main()
