"""문체부 '방한 관광 동향' 월간 보도자료 → tourism_mcst.json 자동 갱신 (2026-11-26 · 사용자 "지금까지 채운 거 다 자동수집되게").

그동안 손으로 옮기던 두 가지를 보도자료 PDF 에서 바로 읽는다:
  ind  = '관광 분야 카드 소비액 규모(억 원)' 표 — 그해 1~N월 업종별(쇼핑·숙박·의료웰니스·식음료·기타) + 전체
  cum  = 붙임 '시장별' 표의 그해 1~N월 누계(전체 · 국가별) — fetch_tourism.apply_mcst 가 데이터랩 1~(N−1)월을 빼서 N월 속보(flash)를 만든다

어디서: mcst.go.kr 보도자료 게시판(키·로그인 없음). 목록 1~2쪽에서 제목에 방한·외래·관광객이 든 글을 열고,
  첨부 PDF 이름에 '방한'·'동향'이 든 것(작성 부서 국제관광정책과)을 받는다. 공표 = 매달 하순(10월분 2026-11-26 08:00).
언제: fetch_tourism.py 가 부른다 — 오늘이 20일 이후이고 지난달 업종별(ind)이 아직 없을 때만(그 밖엔 요청 0건).

  python mcst_press.py --check <보도자료.pdf>   PDF 하나를 읽어 무엇이 나오는지 찍는다(파일은 안 바꾼다)
  python mcst_press.py --apply <보도자료.pdf>   그 PDF 로 tourism_mcst.json 을 갱신한다(사이트를 못 열 때 손으로)
  python mcst_press.py --fetch                  사이트에서 찾아 갱신(날짜 조건 무시)
"""
import datetime, html as H, io, json, os, re, sys, urllib.parse, urllib.request

from collector_health import ua, nap, note_health

KST = datetime.timezone(datetime.timedelta(hours=9))
MCST = "tourism_mcst.json"
BASE = "https://www.mcst.go.kr/site/s_notice/press/"
KEYS = ["쇼핑업", "숙박업", "의료웰니스업", "식음료업", "기타"]
NAT = {"중국": "CN", "일본": "JP", "대만": "TW", "홍콩": "HK", "필리핀": "PH", "베트남": "VN",
       "싱가포르": "SG", "인도네시아": "ID", "태국": "TH", "말레이시아": "MY"}


def _num(s):
    return int(s.replace(",", ""))


def parse_text(text):
    """보도자료 PDF 의 글자(pdfplumber extract_text 를 이어 붙인 것) → {ym, year, ind:{YYYYMM:[쇼핑…기타, 전체]}, cum:{total, nat}}.
    표 모양이 바뀌어 검산이 안 맞으면 ValueError — 틀린 숫자를 넣느니 안 넣는다."""
    t = text.replace("’", "'").replace("‘", "'").replace("′", "'").replace("’", "'")
    m = re.search(r"(20\d{2})\s*년\s*(\d{1,2})\s*월\s*방한\s*관광\s*동향", t)
    if not m:
        raise ValueError("'YYYY년 N월 방한 관광 동향' 문구가 없음 — 월간 동향 보도자료가 아니다")
    year, mon = int(m.group(1)), int(m.group(2))
    ym = f"{year}{mon:02d}"
    out = {"ym": ym, "year": year}
    # ① 업종별 카드 소비 — '카드 소비액 규모' 표(전체가 맨 앞 열)
    i = t.find("카드 소비액 규모")
    if i < 0:
        raise ValueError("'관광 분야 카드 소비액 규모' 표가 없음")
    seg = t[i:]
    j = seg.find("합계")
    if j < 0:
        raise ValueError("카드 소비액 표에 합계 줄이 없음")
    head = seg[:400]
    pos = {k: head.find(k) for k in KEYS}
    if min(pos.values()) < 0:
        raise ValueError(f"카드 소비액 표 머리글에 업종이 다 없음: {pos}")
    order = sorted(KEYS, key=lambda k: pos[k])                       # 표에 실린 업종 순서
    ym2 = re.search(r"'(\d{2})\s*년\s*관광\s*분야\s*카드", t)
    ty = 2000 + int(ym2.group(1)) if ym2 else year
    ind = {}
    for line in seg[:j].splitlines():
        r = re.match(r"^\s*(\d{1,2})\s*월\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s*$", line)
        if not r:
            continue
        mo, tot, vals = int(r.group(1)), _num(r.group(2)), [_num(r.group(k)) for k in range(3, 8)]
        row = [vals[order.index(k)] for k in KEYS]
        if abs(sum(row) - tot) > 5:
            raise ValueError(f"카드 소비액 {mo}월: 업종 합 {sum(row):,} ≠ 전체 {tot:,}")
        ind[f"{ty}{mo:02d}"] = row + [tot]
    tl = re.match(r"^\s*합계\s+([\d,]+)", seg[j:j + 80])
    if not ind:
        raise ValueError("카드 소비액 표에서 달 줄을 하나도 못 읽음")
    if tl and abs(_num(tl.group(1)) - sum(v[-1] for v in ind.values())) > 12:
        raise ValueError(f"카드 소비액 합계 {tl.group(1)} ≠ 달 합 {sum(v[-1] for v in ind.values()):,}")
    if max(ind) != f"{ty}{mon:02d}" or ty != year:
        raise ValueError(f"카드 소비액 표 마지막 달 {max(ind)} ≠ 보도 달 {ym}")
    out["ind"] = ind
    # ② 1~N월 누계 — 붙임 '시장별' 표('구분(단위 : 명)' 아래 · 두 번째 숫자 열 = 올해)
    k = t.find("(단위 : 명)")
    if k < 0:
        k = t.find("단위 : 명")
    if k < 0:
        raise ValueError("붙임 시장별 표('단위 : 명')가 없음")
    blk = t[k:k + 4000]
    e = re.search(r"\n\s*◦|\n\s*□", blk)
    if e:
        blk = blk[:e.start()]
    hdr = re.search(r"'(\d{2})\s*년\s*\(\s*1\s*~\s*(\d{1,2})\s*월", blk)
    if hdr and (2000 + int(hdr.group(1)) == year - 1) and int(hdr.group(2)) != mon:
        raise ValueError(f"시장별 표 기간 1~{hdr.group(2)}월 ≠ 보도 달 {mon}월")
    nat, total = {}, None
    for line in blk.splitlines():
        r = re.match(r"^\s*(.+?)\s+([\d,]{4,})\s+([\d,]{4,})\s+[+\-−]?[\d.]+\s*%\s*$", line)
        if not r:
            continue
        nm, a, b = r.group(1).strip(), _num(r.group(2)), _num(r.group(3))
        if nm == "전체":
            total = b
        elif nm in NAT:
            nat[NAT[nm]] = b
    if total is None:
        raise ValueError("시장별 표에 '전체' 누계 줄이 없음")
    if len(nat) < 8:
        raise ValueError(f"시장별 표에서 나라를 {len(nat)}개만 읽음")
    if sum(nat.values()) >= total:
        raise ValueError("나라별 누계 합이 전체보다 크다 — 열을 잘못 읽었다")
    out["cum"] = {"total": total, "nat": nat}
    return out


def pdf_text(data):
    import pdfplumber
    with pdfplumber.open(io.BytesIO(data)) as p:
        return "\n".join((pg.extract_text() or "") for pg in p.pages)


def _get(url, doc=True, timeout=30, tries=3):
    """게시판이 가끔 응답 없이 연결을 끊는다(러너 2026-11-26 RemoteDisconnected) — 3번까지 간격을 늘려 다시."""
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=dict(ua(referer=BASE + "pressList.jsp", doc=doc), Connection="close"))
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            last = e
            if k < tries - 1:
                nap(3 * (k + 1))
    raise RuntimeError(f"{url.split('?')[0].rsplit('/', 1)[-1]}: {type(last).__name__}: {last}")


def find_release(pages=2, days=45):
    """게시판에서 이번 '방한 관광 동향' 보도자료를 찾는다 → (게시일, 제목, PDF 주소) 목록(최근 것부터)."""
    today = datetime.datetime.now(KST).date()
    rows = []
    for pg in range(1, pages + 1):
        h = _get(BASE + f"pressList.jsp?pCurrentPage={pg}").decode("utf-8", "replace")
        for m in re.finditer(r'href="pressView\.jsp\?pSeq=(\d+)"[^>]*title="([^"]*)".*?aria-label="게시일">\s*(\d{4})\.(\d{2})\.(\d{2})', h, re.S):
            d = datetime.date(int(m.group(3)), int(m.group(4)), int(m.group(5)))
            if (today - d).days <= days:
                rows.append((d, m.group(1), H.unescape(m.group(2))))
        nap(0.8)
    out = []
    for d, seq, title in rows:
        if not re.search(r"방한|외래|관광객|관광\s*동향", title):
            continue
        v = _get(BASE + f"pressView.jsp?pSeq={seq}").decode("utf-8", "replace")
        nap(0.8)
        for u in re.findall(r'(https?://www\.mcst\.go\.kr/servlets/eduport/front/upload/UplDownloadFile\?[^"\'<>\s]+)', v):
            u = H.unescape(u)
            q = urllib.parse.parse_qs(urllib.parse.urlparse(u).query)
            fn = (q.get("pFileName") or [""])[0]
            if fn.lower().endswith(".pdf") and "방한" in fn and "동향" in fn:
                out.append((d, title, u))
                break
    return sorted(set(out), reverse=True)


def apply(res, path=MCST, src=""):
    """parse_text 결과를 tourism_mcst.json 에 넣는다. 바뀐 게 있으면 True."""
    J = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    before = json.dumps(J, ensure_ascii=False, sort_keys=True)
    J.setdefault("ind_keys", KEYS)
    if J["ind_keys"] != KEYS:
        raise ValueError(f"tourism_mcst.json ind_keys {J['ind_keys']} 가 예상과 다르다")
    ind = J.setdefault("ind", {})
    for m, row in res["ind"].items():
        ind[m] = row                       # 최신 보도자료가 이긴다(앞 달 수정 반영)
    J["ind"] = {m: ind[m] for m in sorted(ind)}
    ym = res["ym"]
    J["ind_src"] = f"문체부 보도자료 {src} '{ym[:4]}년 {int(ym[4:])}월 방한 관광 동향' · 관광 분야 카드 소비액(억 원) · 기타 = 운송·여가서비스·여행업 등"
    cum = J.setdefault("cum", {})
    cum[ym] = {"total": res["cum"]["total"], "nat": res["cum"]["nat"], "src": f"문체부 보도자료 {src} · 붙임 시장별 1~{int(ym[4:])}월 누계"}
    J["cum"] = {m: cum[m] for m in sorted(cum)}
    changed = json.dumps(J, ensure_ascii=False, sort_keys=True) != before
    if changed:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(J, f, ensure_ascii=False, indent=2)
            f.write("\n")
    return changed


def due(path=MCST):
    """지난달 업종별(ind)이 아직 없고 오늘이 20일 이후인가 — 보도자료는 매달 하순에 전월분이 나온다."""
    now = datetime.datetime.now(KST)
    if now.day < 20:
        return False
    prev = (now.replace(day=1) - datetime.timedelta(days=1)).strftime("%Y%m")
    try:
        J = json.load(open(path, encoding="utf-8"))
    except Exception:
        return True
    return prev not in (J.get("ind") or {})


def update(force=False, path=MCST):
    """사이트에서 찾아 갱신. 바뀌면 True. 실패는 health 에 남기고 False(방한 관광 수집 전체를 막지 않는다)."""
    if not force and not due(path):
        return False
    try:
        rel = find_release()
    except Exception as e:
        note_health("문체부 방한관광 보도자료", f"게시판을 못 엶: {type(e).__name__}: {str(e)[:160]}")
        print(f"  문체부 보도자료: 게시판을 못 엶 — {type(e).__name__}: {e}")
        return False
    if not rel:
        print("  문체부 보도자료: 이번 달 '방한 관광 동향' 글이 아직 없음")
        note_health("문체부 방한관광 보도자료", None)
        return False
    d, title, url = rel[0]
    try:
        res = parse_text(pdf_text(_get(url, doc=False, timeout=60)))
    except Exception as e:
        note_health("문체부 방한관광 보도자료", f"{d} '{title[:30]}' PDF 를 못 읽음: {type(e).__name__}: {str(e)[:160]}")
        print(f"  문체부 보도자료 {d}: PDF 를 못 읽음 — {type(e).__name__}: {e}")
        return False
    note_health("문체부 방한관광 보도자료", None)
    ch = apply(res, path, src=d.isoformat())
    print(f"  문체부 보도자료 {d} '{title}': {res['ym']} · 업종별 {len(res['ind'])}개월 · 누계 {res['cum']['total']:,}명 · "
          f"{'갱신' if ch else '변동 없음'}")
    return ch


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] in (["--check"], ["--apply"]) and len(a) > 1:
        r = parse_text(pdf_text(open(a[1], "rb").read()))
        print(json.dumps(r, ensure_ascii=False, indent=1))
        if a[0] == "--apply":
            print("갱신" if apply(r, src=a[2] if len(a) > 2 else "") else "변동 없음")
    elif a[:1] == ["--fetch"]:
        update(force=True)
    else:
        print(__doc__)
