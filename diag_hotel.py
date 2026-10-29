"""호텔 ADR 바텀업 조사(일회성) — DART 정기보고서 'II. 사업의 내용'에서 호텔 관련 표·문장만 뽑는다.

러너에서 돈다(DART 키 = 시크릿). 결과는 diag_hotel_out/<회사>/<연월>_<접수번호>.txt —
diag_hotel.yml 이 main 이 아니라 따로 쓰는 가지(diag-hotel)에 올린다(main 을 무겁게 하지 않으려고).
찾는 것: 객실 매출(객실·식음 나눔) · 판매 가능/판매 객실 수 · 객실 가동률(투숙률·점유율) · 가격변동추이(객실 평균 단가) · 객실 수.
"""
import html as _html, io, json, os, re, sys, time, urllib.request, zipfile

KEY = os.environ.get("DART_API_KEY", "")
OUT = "diag_hotel_out"
CORPS = {                     # 이름: (corp_code, 시작 연도)
    "shilla":   ("00165680", 2009),   # 호텔신라
    "seobu":    ("00130383", 2009),   # 서부티엔디
    "gsretail": ("00140177", 2015),   # GS리테일 — 2015 파르나스호텔 인수 ~ 2025 GS피앤엘 분할
    "gspnl":    ("01882845", 2025),   # GS피앤엘
    "sreit":    ("01436558", 2021),   # 신한서부티엔디리츠 — 그랜드 머큐어·나인트리·신라스테이
}
KW = re.compile(r"객실|투숙|점유율|가동률|이용률|ADR|RevPAR|REVPAR|객단가|판매단가|평균단가|평균요금|평균 객실|숙박|OCC|Occupancy|"
                r"판매가능|판매 가능|판매객실|변동임대료|GOP|호텔")
PERIOD = {"03": 1, "06": 2, "09": 3, "12": 4}


def get(u, t=120, tries=3):
    for i in range(tries):
        try:
            return urllib.request.urlopen(u, timeout=t).read()
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(3 * (i + 1))


def reports(corp, y0):
    out, page = {}, 1
    while True:
        u = (f"https://opendart.fss.or.kr/api/list.json?crtfc_key={KEY}&corp_code={corp}"
             f"&bgn_de={y0}0101&end_de=20261231&pblntf_ty=A&page_count=100&page_no={page}")
        d = json.loads(get(u, 30).decode())
        for r in d.get("list", []):
            m = re.search(r"\((\d{4})\.(\d{2})\)", r["report_nm"])
            if m and m.group(2) in PERIOD:
                ym = f"{m.group(1)}-{m.group(2)}"
                out.setdefault(ym, []).append((r["rcept_no"], r["report_nm"].strip()))
        if page >= int(d.get("total_page") or 1):
            break
        page += 1
        time.sleep(0.3)
    return {k: sorted(v, reverse=True) for k, v in out.items()}      # 최신(정정) 먼저 — 받기 실패하면 그 앞 것


def dec(raw):
    """DART 원문은 UTF-8 과 EUC-KR 이 섞여 있다(2009~2022 상당수가 EUC-KR) — 선언을 보고, 없으면 UTF-8 → CP949 순."""
    m = re.search(rb'encoding="([^"]+)"', raw[:300])
    enc = (m.group(1).decode("ascii", "ignore").lower() if m else "")
    if enc in ("euc-kr", "euckr", "ks_c_5601-1987", "cp949", "ms949"):
        return raw.decode("cp949", errors="replace")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp949", errors="replace")


def cell(c):
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()


def table_lines(tb):
    rows = []
    for tr in re.findall(r"<TR[^>]*>(.*?)</TR>", tb, re.S):
        cs = [cell(c) for c in re.findall(r"<T[DHEU][^>]*>(.*?)</T[DHEU]>", tr, re.S)]
        if any(cs):
            rows.append("| " + " | ".join(cs) + " |")
    return rows


def section2(t):
    m = re.search(r"<TITLE[^>]*>\s*(?:II|Ⅱ)\.\s*사업의\s*내용", t)
    if not m:
        m = re.search(r"사업의\s*내용", t)
    if not m:
        return ""
    e = re.search(r"<TITLE[^>]*>\s*(?:III|Ⅲ)\.", t[m.end():])
    return t[m.start(): m.end() + (e.start() if e else 400000)]


def excerpt(s, cap=90000):
    out, prev, size = [], None, 0
    for mm in re.finditer(r"<TITLE[^>]*>(.*?)</TITLE>|<TABLE[^>]*>(.*?)</TABLE>|<P[^>]*>(.*?)</P>", s, re.S):
        if mm.group(1) is not None:
            line = "# " + cell(mm.group(1))
            out.append(line); size += len(line); prev = None
            continue
        if mm.group(2) is not None:
            rows = table_lines(mm.group(2))
            txt = "\n".join(rows)
            if len(rows) <= 2 and len(txt) < 200:          # 단위 상자·한 줄 표
                prev = ("U", txt)
                if KW.search(txt):
                    out.append(txt); size += len(txt); prev = None
                continue
            if KW.search(txt):
                if prev:
                    out.append(prev[1]); size += len(prev[1])
                out.append("T:\n" + txt); size += len(txt)
            prev = None
        else:
            p = cell(mm.group(3))
            if not p:
                continue
            if KW.search(p) or re.search(r"단위", p):
                out.append("P: " + p); size += len(p); prev = None
            else:
                prev = ("P", "P: " + p[:300])
        if size > cap:
            out.append("…(잘림)")
            break
    return "\n".join(out)


def main():
    if not KEY:
        print("DART 키 없음"); sys.exit(1)
    os.makedirs(OUT, exist_ok=True)
    index = []
    for nm, (corp, y0) in CORPS.items():
        os.makedirs(f"{OUT}/{nm}", exist_ok=True)
        try:
            rep = reports(corp, y0)
        except Exception as e:
            print(f"[{nm}] 목록 실패 {e}"); continue
        print(f"[{nm}] 보고서 {len(rep)}개 · {min(rep) if rep else '-'} ~ {max(rep) if rep else '-'}", flush=True)
        for ym in sorted(rep):
            cands = rep[ym]
            rc, rn = cands[0]
            fn = f"{OUT}/{nm}/{ym}_{rc}.txt"
            if os.path.exists(fn):
                continue
            try:
                best = ""
                for rc, rn in cands:                      # 정정 보고서가 zip 이 아니면(첨부정정 등) 그 앞 보고서
                    b = get(f"https://opendart.fss.or.kr/api/document.xml?crtfc_key={KEY}&rcept_no={rc}", 180)
                    try:
                        z = zipfile.ZipFile(io.BytesIO(b))
                    except zipfile.BadZipFile:
                        time.sleep(0.5); continue
                    for n in sorted(z.namelist(), key=lambda n: -z.getinfo(n).file_size):
                        s = section2(dec(z.read(n)))
                        if len(s) > len(best):
                            best = s
                        if best:
                            break
                    if best:
                        break
                fn = f"{OUT}/{nm}/{ym}_{rc}.txt"
                ex = excerpt(best)
                open(fn, "w", encoding="utf-8").write(f"### {nm} {ym} {rn} {rc} · 사업의 내용 {len(best):,}자\n{ex}\n")
                index.append({"c": nm, "ym": ym, "rc": rc, "nm": rn, "sec": len(best), "ex": len(ex)})
                print(f"   {ym} {rc} 원문 {len(best):,} → 발췌 {len(ex):,}", flush=True)
            except Exception as e:
                print(f"   {ym} {rc} 실패 {type(e).__name__} {str(e)[:100]}", flush=True)
                index.append({"c": nm, "ym": ym, "rc": rc, "nm": rn, "err": str(e)[:200]})
            time.sleep(0.5)
    json.dump(index, open(f"{OUT}/index.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main()
