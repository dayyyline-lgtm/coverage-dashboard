# -*- coding: utf-8 -*-
"""산업통상부 '주요 유통업체 매출 동향' 자동 수집 → retail_ingest 로 RETAIL 블록에 한 달 추가   (2026-11-11 신설)

사용자(11/11): "유통업체 10월치 안 들어간 것 아니냐 — 언제 나오는지 파악하고 안 놓치게".
그때까지는 '크롬 예약 작업'이 붙임을 읽어 raw JSON 을 넘겼는데, 그 예약이 어디서 도는지 이 저장소에서 확인이 안 됐다.
붙임 PDF 는 크롬 없이 받아지고(공개 첨부 · 텍스트 PDF) pdfplumber 로 표 글자가 깨끗이 나온다 → 사람·크롬 없이 돈다.

공표 시점: 조사기준월 **익월 말**(PDF 참고란 "익월말 공표") · 2026 실측은 전부 **수요일 11:00** —
  3/25 · 5/27 · 6/24 · 7/29 · 8/26 · 9/23 · 10/28 (넷째 또는 마지막 수요일 · 23~29일).
  10월치는 11/25(수) 11:00 이 유력. retail.yml 이 매월 20~31일 KST 11~19시 매시 이 스크립트를 부른다.

흐름: 보도자료 게시판 1쪽(50건) 제목에서 "'YY년 N월 주요 유통업체 매출 동향"(상반기 묶음 포함) → 게시물의 .pdf 붙임 →
      본문 표 + 붙임 표를 raw JSON 으로(retail_ingest.py 맨 위 모양) → retail_ingest.check/ingest → 블록 + retail_out.json.
      트래커 DB(claude.ai 아티팩트)는 러너가 못 쓴다 — retail_out.json 만 남긴다.

  python fetch_retail.py                 # 다음 달(블록 latest + 1)이 게시됐으면 넣는다 · 없으면 조용히 끝
  python fetch_retail.py --ym 26.09 --check   # 그 달을 받아 파싱·검증만(블록 그대로) — 이미 든 달과 대조
  python fetch_retail.py --pdf a.pdf --ym 26.07 --check

종료코드: 0 = 넣었거나 아직 게시 전 · 2 = 게시됐는데 파싱/검증 실패(health 에 남아 watchdog 이 알린다) · 3 = 게시판에 못 닿음.
"""
import argparse, datetime, io, json, os, re, sys, urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import retail_ingest as RI
from collector_health import note_health

KST = datetime.timezone(datetime.timedelta(hours=9))
BASE = "https://www.motir.go.kr"
BOARD = BASE + "/kor/article/ATCL3f49a5a8c"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
EV = {"27.01": "설 선판매", "27.02": "설(2/7)"}          # 명절 시점(화면·텔레그램 띠) — 해마다 손으로
O_ORDER = [0, 1, 2, 4, 5, 3, 6, 7, 8, 9]                 # 붙임 온라인 [가전,도서,패션,스포츠,화장품,아동,…] → ingest 순서


def get(url, ref=None, timeout=30):
    h = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/pdf,*/*"}
    if ref:
        h["Referer"] = ref
    return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout).read()


def find_post(ym):
    """게시판 1~2쪽(50건씩)에서 그 달 보도자료 번호."""
    yy, mm = ym[:2], int(ym[3:])
    pat = re.compile(r"(?:&#039;|['’‘])\s*" + yy + r"년\s*(?:상반기\s*및\s*)?" + str(mm) + r"월\s*주요\s*유통업체\s*매출\s*동향")
    for p in (1, 2):
        h = get(f"{BOARD}?pageIndex={p}&rowPageC=50").decode("utf-8", "replace")
        for no, title in re.findall(r"article\.view\('(\d+)'\)[^>]*>(.*?)</a>", h, re.S):
            if pat.search(re.sub(r"<[^>]+>", " ", title)):
                return no
    return None


def pdf_of(no):
    view = f"{BOARD}/{no}/view"
    h = get(view).decode("utf-8", "replace")
    for href, txt in re.findall(r'href="(/attach/down/[^"]+)"[^>]*>(.*?)</a>', h, re.S):
        if ".pdf" in re.sub(r"<[^>]+>", "", txt).lower():
            return get(BASE + href, ref=view, timeout=60)
    # 링크 글자가 따로 있는 양식 — pdf 다운로드 글자 바로 앞의 링크
    m = re.search(r'href="(/attach/down/[^"]+)"[^<]{0,300}?[^<]*\.pdf', h)
    if m:
        return get(BASE + m.group(1), ref=view, timeout=60)
    raise RuntimeError(f"게시물 {no} 에 pdf 붙임이 없다")


# ── PDF 텍스트 → raw ─────────────────────────────────────────────────────────
NUM = r"△?-?\d+(?:\.\d+)?"


def nums(s):
    return [-float(x[1:]) if x.startswith("△") else float(x) for x in re.findall(NUM, s)]


def lines_of(pdf):
    import pdfplumber
    with pdfplumber.open(io.BytesIO(pdf)) as p:
        pages = [pg.extract_text() or "" for pg in p.pages]
    return pages


def row_val(text, label, idx=-1):
    """'라벨 v1 v2 …' 줄에서 값 하나(기본 마지막)."""
    for ln in text.splitlines():
        if re.match(r"^\s*" + label + r"\s", ln):
            v = nums(ln[len(re.match(r"^\s*" + label, ln).group(0)):])
            if v:
                return v[idx]
    return None


def month_rows(sec, start_kw, stop_kw):
    """섹션 안 [start_kw 다음 ~ stop_kw 전] 월 행 → [(월, [값…])]."""
    a = sec.find(start_kw)
    b = sec.find(stop_kw, a + 1) if a >= 0 else -1
    if a < 0:
        return []
    part = sec[a:b if b > 0 else None]
    out = []
    for ln in part.splitlines():
        m = re.match(r"^\s*(?:['’‘]\s*\d\d\.\s*)?(\d{1,2})월\s+(.*)$", ln)
        if m:
            v = nums(m.group(2))
            if v:
                out.append((int(m.group(1)), v))
    return out


def section(full, head, nxt):
    a = full.find(head)
    if a < 0:
        raise ValueError(f"붙임 '{head}' 절을 못 찾음")
    b = full.find(nxt, a + 1) if nxt else -1
    return full[a:b if b > 0 else None]


def parse(pdf, ym):
    pages = lines_of(pdf)
    full = "\n".join(pages)
    mm = int(ym[3:])
    p1 = pages[0] + "\n" + (pages[1] if len(pages) > 1 else "")
    # 머리 — 본문 '업태별 전년 동월 대비' 표(마지막 열 = 대상 월)
    t = p1[p1.find("유통업태별"):]
    head = {k: row_val(t, k) for k in ("전체", "오프라인", "온라인")}
    chan = {"M": row_val(t, "대형마트"), "B": row_val(t, "백화점"), "C": row_val(t, "편의점"), "S": row_val(t, r"S\s*S\s*M")}
    # 상품군별(본문) — 오프라인 줄 = F
    g = p1[p1.find("상품군별 전년 동월"):]
    F = None
    for ln in g.splitlines():
        if re.match(r"^\s*오프라인\s", ln):
            F = nums(ln)[:8]; break
    # 업태별 매출 구성비 — 마지막 열
    c = p1[p1.find("업태별 매출 구성비"):]
    comp = {"편의점": row_val(c, "편의점"), "온라인": row_val(c, "온라인")}
    # 발표 시각
    rm = re.search(r"(20\d\d)\.\s*(\d{1,2})\.\s*(\d{1,2})\.\s*\([^)]*\)\s*(\d{1,2}:\d\d)", pages[0])
    rel = f"{rm.group(1)}-{int(rm.group(2)):02d}-{int(rm.group(3)):02d} {rm.group(4)}" if rm else ""

    secs = {"M": ("□ 대형마트", "□ 백화점"), "B": ("□ 백화점", "□ 편의점"), "C": ("□ 편의점", "□ 준대규모점포"),
            "S": ("□ 준대규모점포", "□ 온라인"), "O": ("□ 온라인", "참고")}
    yoy, sh, sh_prev, kpi, stores = {}, {}, {}, {}, {}
    for ch, (a, b) in secs.items():
        sec = section(full, a, b)
        rows = month_rows(sec, "전년동월 대비", "전년동기 대비")
        if not rows or rows[-1][0] != mm:
            raise ValueError(f"{ch} 전년동월 표 마지막 행이 {mm}월이 아님({rows[-1][0] if rows else '없음'})")
        v = rows[-1][1]
        yoy[ch] = [v[i] for i in O_ORDER] if ch == "O" else v
        srows = month_rows(sec, "상품군별 매출 비중", "구매건수" if ch != "O" else "※")
        if ch != "O":
            if not srows or srows[-1][0] != mm:
                raise ValueError(f"{ch} 비중 표 마지막 행이 {mm}월이 아님")
            sh[ch] = srows[-1][1]
            if len(srows) >= 2 and srows[-2][0] == (mm - 2) % 12 + 1:
                sh_prev[ch] = srows[-2][1]
            k = {}
            for lab, key in (("구매건수", "구매건수"), ("구매단가", "구매단가"), (r"점포\s*증가율", "점포 증가율"),
                             (r"점포당\s*매출(?:액)?", "점포당 매출")):
                val = row_val(sec, lab)
                if val is not None:
                    k[key] = val
            kpi[ch] = k
            sm = re.search(r"점포\s*수\s*:\s*([\d,]+)\s*개", sec)
            if sm:
                stores[ch] = int(sm.group(1).replace(",", ""))
    yoy["F"] = F
    raw = {"ym": ym, "release": f"{rel} ({mm}월호)".strip(), "head": head, "chan": chan, "yoy": yoy,
           "sh": sh, "sh_prev": sh_prev, "kpi": kpi, "comp": comp, "stores": stores}
    if EV.get(ym):
        raw["ev"] = EV[ym]
    return raw


def compare(raw, doc):
    """이미 블록에 든 달과 대조 — 틀린 칸 목록."""
    diff = []
    for k in ("전체", "오프라인", "온라인"):
        if raw["head"].get(k) != doc["yoy"]["head"].get(k):
            diff.append(f"head.{k} {raw['head'].get(k)} ≠ {doc['yoy']['head'].get(k)}")
    for ch in "MBCSOF":
        if raw["yoy"].get(ch) != doc["yoy"].get(ch):
            diff.append(f"yoy.{ch} {raw['yoy'].get(ch)} ≠ {doc['yoy'].get(ch)}")
    for ch, kv in (doc.get("kpi") or {}).items():
        for k, v in kv.items():
            if raw["kpi"].get(ch, {}).get(k) != v:
                diff.append(f"kpi.{ch}.{k} {raw['kpi'].get(ch, {}).get(k)} ≠ {v}")
    return diff


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ym"); ap.add_argument("--pdf"); ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    html = open(RI.HTML, encoding="utf-8").read()
    blk, m = RI.load_block(html)
    ly, lm = int(blk["latest"][:2]), int(blk["latest"][3:])
    ym = a.ym or (f"{ly:02d}.{lm + 1:02d}" if lm < 12 else f"{ly + 1:02d}.01")
    if a.pdf:
        pdf = open(a.pdf, "rb").read()
    else:
        try:
            no = find_post(ym)
        except Exception as e:
            print(f"[RETAIL] 게시판에 못 닿음: {e}")
            note_health("유통업체 매출동향", f"산업부 게시판 접속 실패: {str(e)[:80]}")
            sys.exit(3)
        if not no:
            now = datetime.datetime.now(KST)
            print(f"[RETAIL] {ym} 아직 게시 전 ({now:%m-%d %H:%M} KST)")
            return
        print(f"[RETAIL] {ym} 게시물 {no}")
        pdf = pdf_of(no)
    try:
        raw = parse(pdf, ym)
    except Exception as e:
        print(f"[RETAIL] 파싱 실패: {e}")
        note_health("유통업체 매출동향", f"{ym} 보도자료는 나왔는데 PDF 파싱 실패: {str(e)[:100]}")
        sys.exit(2)
    raw["src"] = f"{int(ym[3:])}월호 자동 수집(PDF)"
    bad = RI.check(raw)
    print(f"[RETAIL] {ym} 파싱: 머리 {raw['head']} · 업태 {raw['chan']} · 발표 {raw['release']}")
    old = {d["ym"]: d for d in blk["months"]}.get(ym)
    if old:
        diff = compare(raw, old)
        print("[RETAIL] 블록의 같은 달과 대조: " + ("전부 일치" if not diff else " / ".join(diff)))
    if bad:
        print("[RETAIL] 검증 실패: " + " / ".join(bad))
        if not a.check:
            note_health("유통업체 매출동향", f"{ym} 검증 실패: {' / '.join(bad)[:120]}")
        sys.exit(2)
    if a.check:
        print(json.dumps(raw, ensure_ascii=False)[:1200])
        return
    doc, revised = RI.ingest(blk, raw)
    json.dump({"doc": doc, "revised_prev": revised}, open("retail_out.json", "w", encoding="utf-8"), ensure_ascii=False)
    open(RI.HTML, "w", encoding="utf-8").write(RI.write_block(html, m, blk))
    note_health("유통업체 매출동향", None)
    print(f"[RETAIL] {ym} 블록 갱신 · 레벨 " + " ".join(f"{k}={v}" for k, v in doc["L"].items()))


if __name__ == "__main__":
    main()
