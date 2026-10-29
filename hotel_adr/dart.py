# -*- coding: utf-8 -*-
"""호텔 ADR 바텀업 재료 — DART 정기보고서 '사업의 내용'의 객실 매출·투숙률 (2026-10-29)

  python3 hotel_adr/dart.py              러너(시크릿 DART_API_KEY): 새 정기보고서만 받아 hotel_adr/dart/rooms.json 에 더하고,
                                         바뀌었으면 hotel_adr/build.py 로 ADR 블록을 다시 만든다(events.yml 매일 05시 · 평소 목록 3요청)
  python3 hotel_adr/dart.py --seed DIR   일회성 조사(diag_hotel.py → diag-hotel 가지) 발췌 파일에서 과거 보고서를 한 번에 읽는다

보고서마다 '누적' 값을 그대로 둔다(분기 차분·연간 재작성 우선은 build.py bu_block). 값은 전부 백만원.
  shilla  호텔신라 매출 유형 표 '호텔객실'(연결 = 서울신라 · 제주신라 · 신라스테이 임차 12곳 — 위탁 지점·신라모노그램은 수수료라 안 들어간다) · 2009~
          단위가 바뀐다: ~2012.09 억원 · 2012.12 천원 · 2013~ 백만원 / 2014.09~ 표에 전년·전전년 연간이 같이 실린다
  gspnl   GS피앤엘 매출 유형 표 '객실수입'(파르나스호텔 · 2022~ 연간 · 2025~ 분기 누적) +
          '(3) 전체 객실수 및 투숙률 실적' 호텔별 객실 수 · 누적 투숙률(2025 사업보고서~ · 2023~ 연간)
  seobu   서부T&D 매출 유형 표 '관광호텔업 · 객실, 식음료수입'(서울드래곤시티 — 객실과 식음이 한 칸이라 ADR 이 아니라 가용 객실당 매출) · 2017.12~
"""
import html as _html, io, json, os, re, sys, time, urllib.request, zipfile
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "dart", "rooms.json")
KST = timezone(timedelta(hours=9))
CORPS = {"shilla": ("00165680", 2009, "호텔신라"), "gspnl": ("01882845", 2024, "GS피앤엘"), "seobu": ("00130383", 2017, "서부T&D")}
PERIOD = {"03": 1, "06": 2, "09": 3, "12": 4}
KW = re.compile(r"객실|투숙|호텔")


def key():
    k = os.environ.get("DART_API_KEY", "")
    if not k:
        try:
            sys.path.insert(0, ROOT)
            import secrets_local as S                       # noqa: E402 — 이 PC 에서 돌릴 때
            k = next((getattr(S, a) for a in dir(S) if "DART" in a.upper()), "")
        except Exception:
            pass
    return k


# ── 원문 → 줄(표는 '| 칸 | 칸 |') ─────────────────────────────────────────────
def _cell(c):
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()


def _dec(raw):
    """DART 원문은 UTF-8 과 EUC-KR 이 섞여 있다(2009~2022 상당수가 EUC-KR)."""
    m = re.search(rb'encoding="([^"]+)"', raw[:300])
    enc = (m.group(1).decode("ascii", "ignore").lower() if m else "")
    if enc in ("euc-kr", "euckr", "ks_c_5601-1987", "cp949", "ms949"):
        return raw.decode("cp949", errors="replace")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp949", errors="replace")


def _section2(t):
    m = re.search(r"<TITLE[^>]*>\s*(?:II|Ⅱ)\.\s*사업의\s*내용", t) or re.search(r"사업의\s*내용", t)
    if not m:
        return ""
    e = re.search(r"<TITLE[^>]*>\s*(?:III|Ⅲ)\.", t[m.end():])
    return t[m.start(): m.end() + (e.start() if e else 400000)]


def lines_of(sec):
    """사업의 내용 → 호텔 관련 표·문장만 줄로(diag_hotel.py 발췌와 같은 모양 — 파서가 둘 다 읽는다)."""
    out = []
    for mm in re.finditer(r"<TITLE[^>]*>(.*?)</TITLE>|<TABLE[^>]*>(.*?)</TABLE>|<P[^>]*>(.*?)</P>", sec, re.S):
        if mm.group(1) is not None:
            out.append("# " + _cell(mm.group(1)))
        elif mm.group(2) is not None:
            rows = []
            for tr in re.findall(r"<TR[^>]*>(.*?)</TR>", mm.group(2), re.S):
                cs = [_cell(c) for c in re.findall(r"<T[DHEU][^>]*>(.*?)</T[DHEU]>", tr, re.S)]
                if any(cs):
                    rows.append("| " + " | ".join(cs) + " |")
            txt = "\n".join(rows)
            if KW.search(txt) or "단위" in txt:
                out.extend(rows)
        else:
            p = _cell(mm.group(3))
            if p and (KW.search(p) or "단위" in p):
                out.append("P: " + p)
    return out


# ── 파서 ─────────────────────────────────────────────────────────────────────
def _num(s):
    s = (s or "").replace(",", "").replace("\xa0", "").strip()
    if not s or s in ("-", "−", "–") or s.endswith("%"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    try:
        v = float(s.strip("()"))
    except ValueError:
        return None
    return -v if neg else v


def _cells(ln):
    return [c.strip() for c in ln.strip().strip("|").split("|")]


def p_shilla(lines, ym):
    """매출 유형 표 '호텔객실' → [누적, 전년 연간, 전전년 연간] 백만원."""
    for ln in lines:
        c = _cells(ln)
        if len(c) < 2 or not re.fullmatch(r"(기타\()?호텔객실\)?", c[0]):
            continue
        if ym <= "2012-09":                       # 억원 · [당기, 비중, 전기, 비중]
            v = _num(c[1]); return {"v": [v * 100 if v is not None else None]}
        if ym == "2012-12":                       # 천원
            v = _num(c[1]); return {"v": [v / 1000 if v is not None else None]}
        if ym < "2014-09":                        # [당기, 비중]
            return {"v": [_num(c[1])]}
        return {"v": [_num(x) for x in c[1:4]]}
    return None


GS_KEY = [(r"그랜드\s*인터컨티넨탈", "gic"), (r"웨스틴|인터컨티넨탈\s*서울\s*코엑스", "westin"), (r"파르나스\s*호텔\s*제주|파르나스호텔\s*제주", "pjeju"),
          (r"명동\s*(Ⅱ|II|2)", "nt_md2"), (r"명동", "nt_md1"), (r"인사동", "nt_ins"), (r"동대문", "nt_ddm"), (r"판교", "nt_pg"), (r"로카우스|용산", "nt_ys")]


def p_gspnl(lines, ym):
    """'객실수입' 행(숫자가 가장 많은 것 · 천원이면 백만원으로) + 투숙률 표."""
    best = None
    for ln in lines:
        c = _cells(ln)
        if len(c) >= 2 and c[0] == "객실수입":
            v = [_num(x) for x in c[1:] if not x.endswith("%")]
            v = [x for x in v if x is not None]
            if v and (best is None or len(v) > len(best)):
                best = v
    if best is not None:
        best = [x / 1000 if x > 5e6 else x for x in best]       # 천원 표(5조원 넘는 객실수입은 없다)
    occ, head, hdr = {}, None, None
    for ln in lines:
        c = _cells(ln)
        if len(c) >= 4 and c[0] == "구분" and "투숙률" in c[2]:
            head = hdr = c[2:]
            continue
        if head:
            k = next((kk for pat, kk in GS_KEY if re.search(pat, c[0])), None)
            if not k or len(c) < 3:
                head = None if not k else head
                continue
            occ[k] = [_num(c[1])] + [_num(x.replace("%", "")) for x in c[2:2 + len(head)]]
    out = {}
    if best is not None:
        out["v"] = best[:3]
    if occ:
        out["o"] = occ
        out["oh"] = hdr
    return out or None


def p_seobu(lines, ym):
    """'관광호텔업 | 객실, 식음료수입' → [누적, 전년 연간, 전전년 연간] 백만원(원문 천원)."""
    for ln in lines:
        c = _cells(ln)
        if len(c) >= 3 and c[0] == "관광호텔업" and re.fullmatch(r"객실\s*,\s*식음료수입", c[1]):
            return {"v": [(_num(x) / 1000 if _num(x) is not None else None) for x in c[2:5]]}
    return None


PARSE = {"shilla": p_shilla, "gspnl": p_gspnl, "seobu": p_seobu}


# ── 저장 ─────────────────────────────────────────────────────────────────────
def load():
    try:
        return json.load(open(OUT, encoding="utf-8"))
    except Exception:
        return {"r": {k: {} for k in CORPS}}


def save(D):
    D["asOf"] = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(D, f, ensure_ascii=False, indent=1, sort_keys=True)


def seed(d):
    """diag_hotel.py 발췌(<회사>/<연월>_<접수번호>.txt)에서 한 번에."""
    D = load()
    n = 0
    for co in CORPS:
        p = os.path.join(d, co)
        if not os.path.isdir(p):
            continue
        for f in sorted(os.listdir(p)):
            m = re.match(r"(\d{4}-\d{2})_(\d+)\.txt$", f)
            if not m:
                continue
            ym, rc = m.groups()
            lines = open(os.path.join(p, f), encoding="utf-8").read().splitlines()
            r = PARSE[co](lines, ym)
            if r:
                r["rc"] = rc
                D["r"].setdefault(co, {})[ym] = r
                n += 1
    save(D)
    print(f"[ADR-DART] 시드 {n}건 → {OUT}")


def _get(u, t=60):
    for i in range(3):
        try:
            return urllib.request.urlopen(u, timeout=t).read()
        except Exception:
            if i == 2:
                raise
            time.sleep(3 * (i + 1))


def run(dry=False):
    """dry = 최근 보고서 2개씩을 다시 받아 읽고 저장된 값(시드)과 견주기만 한다(파서 점검 · diag_hotel_dry.yml)."""
    K = key()
    if not K:
        sys.exit("DART 키 없음")
    D = load()
    new = []
    for co, (corp, y0, nm) in CORPS.items():
        y0 = max(y0, datetime.now(KST).year - 2)               # 평소엔 최근 2년만 본다(과거는 시드)
        d = json.loads(_get(f"https://opendart.fss.or.kr/api/list.json?crtfc_key={K}&corp_code={corp}"
                            f"&bgn_de={y0}0101&pblntf_ty=A&page_count=100", 30).decode())
        reps = {}
        for r in d.get("list", []):
            m = re.search(r"\((\d{4})\.(\d{2})\)", r["report_nm"])
            if m and m.group(2) in PERIOD:
                reps.setdefault(f"{m.group(1)}-{m.group(2)}", []).append(r["rcept_no"])
        for ym in (sorted(reps)[-2:] if dry else sorted(reps)):
            rcs = sorted(reps[ym], reverse=True)               # 정정 보고서가 앞
            have = D["r"].get(co, {}).get(ym)
            if have and have.get("rc") == rcs[0] and not dry:
                continue
            got = None
            for rc in rcs:
                try:
                    z = zipfile.ZipFile(io.BytesIO(_get(f"https://opendart.fss.or.kr/api/document.xml?crtfc_key={K}&rcept_no={rc}", 180)))
                except zipfile.BadZipFile:
                    continue
                sec = ""
                for n in sorted(z.namelist(), key=lambda n: -z.getinfo(n).file_size):
                    sec = _section2(_dec(z.read(n)))
                    if sec:
                        break
                got = PARSE[co](lines_of(sec), ym) if sec else None
                if got:
                    got["rc"] = rc
                    break
                time.sleep(0.4)
            if dry:
                same = bool(got and have and {k: v for k, v in got.items() if k != "rc"} == {k: v for k, v in have.items() if k != "rc"})
                print(f"[dry] {nm} {ym} {'시드와 같음' if same else '다름/없음'} · 읽은 값 {json.dumps(got, ensure_ascii=False)[:400]}")
                continue
            if got:
                D["r"].setdefault(co, {})[ym] = got
                new.append(f"{nm} {ym}")
            else:
                print(f"   [{nm}] {ym} 객실 표를 못 읽음 — 양식이 바뀌었는지 볼 것")
            time.sleep(0.4)
    if not new:
        print("[ADR-DART] 새 보고서 없음")
        return False
    save(D)
    print("[ADR-DART] 더함:", " · ".join(new))
    return True


def main():
    a = sys.argv[1:]
    if a and a[0] == "--seed":
        seed(a[1])
        return
    if a and a[0] == "--dry":
        run(dry=True)
        return
    if run():
        sys.path.insert(0, HERE)
        import build                                          # noqa: E402
        build.inject(build.build())


if __name__ == "__main__":
    main()
