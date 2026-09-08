# -*- coding: utf-8 -*-
"""
채용 공고 — 생산 확대의 선행 신호 (2026-09-08 신설 → `JOBS`).

왜 채용인가
  공장이 생산직·검사원·지게차를 뽑는다는 건 **이미 물량이 잡혔다**는 뜻이다. 캐펙스는 공시가
  분기 뒤에 나오고, 수출은 선적 뒤에 잡힌다. 채용 공고는 그 앞에서 움직인다.
  2026-09-08 실측: 삼양식품이 8/28~9/2 사이에 원주·밀양·익산 공장 생산직·품질검사원을 13건 —
  전부 현장직 — 동시에 올렸다. 이런 걸 숫자로 매일 찍자는 것이다.

소스 — 사람인 검색 페이지 (키 없이 · `ua(doc=True)`)
  /zf_user/search/recruit?searchword=회사명&recruitSort=reg_dt&recruitPageCount=50
  공고마다 회사명(csn) · 제목 · 지역(도·시) · 직무 태그 · 등록일 · rec_idx 가 온다.

  ⚠ 회사명 **정확일치**로 걸러야 한다. '삼양식품' 검색에 삼양그룹·협력사·인력파견이 절반 섞인다
    (실측 13/50). 검색어가 아니라 `corp_name` 을 (주)·주식회사 떼고 비교한다.
  ⚠ 회사 페이지(csn)로 받으면 더 깨끗하지만 마크업이 달라 item_recruit 이 없다 — 검색으로 간다.
  ⚠ **대기업은 여기 없다.** 아모레·LG생건·CJ제일제당·신세계·롯데는 자사 채용 사이트만 쓴다(실측 0건).
    0 은 '채용 안 함'이 아니라 '이 소스에 안 올림'이다. 화면에 반드시 그렇게 적는다.
  ⚠ 워크넷(고용노동부)은 별도 인증키가 필요하다(data.go.kr 키로는 '유효하지 않은 인증키').
    원티드는 IT·스타트업 위주라 생산직이 없다. 잡코리아는 사람인과 겹친다. 사람인 하나로 간다.

무엇을 지표로 삼나
  ① 현장직(plant) 공고 수 — 직무 태그에 제조·생산·가공·품질·검사·물류·설비·공정·포장·자재·지게차.
     사무(연구·마케팅·영업·경영)와 나눈다. **현장직이 생산 신호**다.
  ② 지역별 — 지역이 곧 공장이다(밀양=삼양 밀양2공장, 평택=에이피알·코스맥스, 세종=한국콜마).
  ③ 신규 — 전일 rec_idx 집합과 비교해 오늘 새로 뜬 공고. 등록일 문자열보다 정확하다.

저장(JOBS.cos[]): {stock, q, hist:[{d, n, p, o, new, reg:{지역:수}}], open:[{rec,title,sec,region,day,plant}]}
  hist 는 하루 1점(같은 날 재실행은 덮는다) · open 은 최근 스냅샷만.

  python fetch_jobs.py            # 수집·기록
  python fetch_jobs.py --dry-run  # 출력만
"""
import re, json, sys, html as htmlmod, copy, datetime, urllib.request, urllib.parse
from collector_health import ua, nap, note_health

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
DAYS = 400
SEARCH = ("https://www.saramin.co.kr/zf_user/search/recruit?searchword={q}"
          "&recruitPage={p}&recruitSort=reg_dt&recruitPageCount=50&searchType=search")
PAGES = 2            # 정확일치가 50건을 넘는 회사(실리콘투 26건)가 있어 2쪽까지 본다

# (종목, 검색어, 정확일치로 인정할 회사명들 — (주)·주식회사 를 뗀 형태)
# 대기업(자사 채용 사이트 전용)은 넣어 두되 0 이 정상이라는 걸 화면에서 밝힌다(BIG).
COS = [
    ("에이피알",     "에이피알",       ["에이피알"]),
    ("아모레퍼시픽",  "아모레퍼시픽",    ["아모레퍼시픽"]),
    ("LG생활건강",   "LG생활건강",     ["LG생활건강", "엘지생활건강"]),
    ("달바글로벌",   "달바글로벌",      ["달바글로벌"]),
    ("한국콜마",     "한국콜마",       ["한국콜마"]),
    ("실리콘투",     "실리콘투",       ["실리콘투"]),
    ("코스맥스",     "코스맥스",       ["코스맥스"]),
    ("제닉",        "제닉",          ["제닉"]),
    ("제이투케이바이오", "제이투케이바이오", ["제이투케이바이오"]),
    ("티앤엘",      "티앤엘",         ["티앤엘"]),
    ("신세계",      "신세계",         ["신세계"]),
    ("롯데쇼핑",     "롯데쇼핑",       ["롯데쇼핑"]),
    ("현대백화점",   "현대백화점",      ["현대백화점"]),
    ("BGF리테일",   "BGF리테일",      ["BGF리테일", "비지에프리테일"]),
    ("GS리테일",    "GS리테일",       ["GS리테일", "지에스리테일"]),
    ("파마리서치",   "파마리서치",      ["파마리서치"]),
    ("앨엔씨바이오",  "엘앤씨바이오",    ["엘앤씨바이오"]),
    ("리센스메디컬",  "리센스메디컬",    ["리센스메디컬"]),
    ("그래피",      "그래피",         ["그래피"]),
    ("삼양식품",     "삼양식품",       ["삼양식품"]),
    ("CJ제일제당",   "CJ제일제당",     ["CJ제일제당", "씨제이제일제당"]),
    ("농심",        "농심",          ["농심"]),
    ("빙그레",      "빙그레",         ["빙그레"]),
    ("하이브",      "하이브",         ["하이브"]),
    ("JYP Ent.",    "JYP엔터테인먼트", ["JYP엔터테인먼트", "제이와이피엔터테인먼트"]),
    ("에스엠",      "에스엠엔터테인먼트", ["에스엠엔터테인먼트"]),
    ("와이지엔터",   "와이지엔터테인먼트", ["와이지엔터테인먼트"]),
    ("SAMG엔터",    "에스에이엠지엔터테인먼트", ["에스에이엠지엔터테인먼트"]),
    ("탑코미디어",   "탑코미디어",      ["탑코미디어", "탑코"]),
    ("크래프톤",     "크래프톤",       ["크래프톤"]),
    ("NC",         "엔씨소프트",      ["엔씨소프트"]),
    ("펄어비스",     "펄어비스",       ["펄어비스"]),
    ("시프트업",     "시프트업",       ["시프트업"]),
    ("데브시스터즈",  "데브시스터즈",    ["데브시스터즈"]),
    ("컴투스",      "컴투스",         ["컴투스"]),
    ("호텔신라",     "호텔신라",       ["호텔신라"]),
    ("롯데관광개발",  "롯데관광개발",    ["롯데관광개발"]),
    ("파라다이스",   "파라다이스",      ["파라다이스"]),
    ("GS피앤엘",    "GS피앤엘",       ["GS피앤엘", "지에스피앤엘"]),
    ("서부T&D",     "서부티엔디",      ["서부티엔디", "서부T&D"]),
]
# 자사 채용 사이트만 쓰는 대기업 — 사람인 0 건이 정상. 화면에 '이 소스에 안 올림'으로 적는다.
BIG = {"아모레퍼시픽", "LG생활건강", "CJ제일제당", "신세계", "롯데쇼핑", "현대백화점", "농심",
       "하이브", "NC", "크래프톤", "호텔신라", "롯데관광개발"}

# ── 현장직 판정 (2026-09-08 v2) ─────────────────────────────────────────
# v1 은 제목+태그를 한 문자열로 붙여 단어를 찾았다. 그러자 **'온라인 MD' 가 '라인' 으로 현장직**이 됐고
# (23건 오탐 — 달바글로벌 영업 17건이 전부 현장으로), 하이브 '안전관리(중대재해)' 도 현장이 됐다.
# 사람인 직무 태그는 표준화된 어휘라 **태그 단위로** 보면 정확하다. 제목은 거부어로만 쓴다.
PLANT_TAG = ["제조", "가공", "생산", "공정", "검사", "품질", "설비", "자재", "물류", "지게차", "포장",
             "출하", "입고", "금형", "용접", "사출", "조립", "QC", "보전", "OP"]
# ⚠ 'QA' 는 뺐다 — 소프트웨어 QA(컴투스 'Web QA')가 현장으로 잡힌다. 공장 QA 는 QC·품질 태그가 따로 붙는다.
# 이 태그가 있으면 사무직이다(현장 태그와 겹치면 제목으로 가른다).
OFFICE_TAG = ["영업", "마케팅", "MD", "개발", "프로그래", "회계", "재무", "인사", "기획", "디자인",
              "안전관리자", "연예", "보안", "네트워크", "인프라", "콘텐츠", "사이트", "쇼핑몰", "온라인"]
# 제목에 이게 있으면 태그가 뭐라 해도 사무직(SAMG '시스템운영 및 보안관리' 가 품질검사원 태그를 달고 있었다).
TITLE_OFFICE = ["영업", "마케팅", "MD", "시스템", "보안", "회계", "인사", "기획", "디자인", "개발자",
                "프로그래머", "PM", "연구원", "R&D", "설계 엔지니어", "안전관리", "보건관리",
                "Web", "카페", "하우스키핑", "구매부", "SCM"]
# 제목만으로 현장이 분명한 말.
TITLE_PLANT = ["공장", "생산직", "교대", "지게차", "검사원", "Operator", "오퍼레이터", "포장", "출하", "제조기술"]


def is_plant(item):
    tags = item.get("sec") or []
    title = item.get("title") or ""
    if any(w in title for w in TITLE_OFFICE):
        return False
    p_tag = any(any(k in t for k in PLANT_TAG) for t in tags)
    o_tag = any(any(k in t for k in OFFICE_TAG) for t in tags)
    if p_tag and not o_tag:
        return True
    if any(w in title for w in TITLE_PLANT):
        return True
    return False


def _get(url):
    req = urllib.request.Request(url, headers=ua(referer="https://www.saramin.co.kr/", doc=True))
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def _norm(name):
    return re.sub(r"\(주\)|주식회사|㈜|\s+", "", name or "")


def parse(t):
    out = []
    for b in re.split(r'<div class="item_recruit"', t)[1:]:
        corp = re.search(r'class="corp_name">.*?<a[^>]*>(.*?)</a>', b, re.S)
        cname = htmlmod.unescape(re.sub(r"<[^>]+>", "", corp.group(1))).strip() if corp else ""
        title = re.search(r'class="job_tit">\s*<a[^>]*title="([^"]*)"', b)
        cond = re.search(r'class="job_condition">(.*?)</div>', b, re.S)
        ct = [x.strip() for x in re.sub(r"<[^>]+>", "|", cond.group(1)).split("|") if x.strip()] if cond else []
        sector = re.search(r'class="job_sector">(.*?)</div>', b, re.S)
        sec = [htmlmod.unescape(x).strip() for x in re.findall(r'>([^<]+)</a>', sector.group(1))] if sector else []
        day = re.search(r'class="job_day">([^<]*)<', b)
        rec = re.search(r'rec_idx=(\d+)', b)
        if not rec:
            continue
        # 지역 = 조건의 앞 두 토큰이 '도 시' 인데, 시가 없는 경우(세종·서울) 두 번째가 경력/학력이라 걸러낸다
        region = " ".join(x for x in ct[:2] if not re.search(r"경력|신입|학력|졸|무관|년", x))
        out.append({"corp": cname, "rec": rec.group(1),
                    "title": htmlmod.unescape(title.group(1)) if title else "",
                    "region": region, "sec": sec[:5],
                    "day": (day.group(1).strip() if day else "")})
    return out


def fetch_company(q, names):
    rows = []
    for p in range(1, PAGES + 1):
        t = _get(SEARCH.format(q=urllib.parse.quote(q), p=p))
        got = parse(t)
        if not got:
            break
        rows += got
        if len(got) < 50:
            break
        nap(0.6)
    ok = {_norm(n) for n in names}
    mine, seen = [], set()
    for r in rows:
        if _norm(r["corp"]) in ok and r["rec"] not in seen:
            seen.add(r["rec"]); mine.append(r)
    return mine


def _const(html_, name):
    m = re.search(r"const %s\s*=\s*(\{.*?\});" % re.escape(name), html_, re.S)
    return json.loads(m.group(1)) if m else None


def _put(html_, name, obj):
    block = "const %s = %s;" % (name, json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
    pat = re.compile(r"const %s\s*=\s*\{.*?\};" % re.escape(name), re.S)
    if pat.search(html_):
        return pat.sub(lambda m: block, html_, count=1)
    liv = re.search(r"const LIVE\s*=\s*\{.*?\};", html_, re.S)
    if not liv:
        raise RuntimeError("JOBS 삽입 기준(const LIVE)을 못 찾음")
    return html_[:liv.end()] + "\n" + block + html_[liv.end():]


def main():
    html_ = open(HTML, encoding="utf-8").read()
    now = datetime.datetime.now(KST)
    today = now.date().isoformat()
    prev = _const(html_, "JOBS") or {}
    old = {c["stock"]: c for c in copy.deepcopy(prev.get("cos") or [])}   # ⚠ deepcopy — 얕은 참조 함정

    cos, fails = [], []
    for stock, q, names in COS:
        try:
            mine = fetch_company(q, names)
        except Exception as e:
            fails.append(f"{stock}: {str(e)[:40]}")
            if stock in old:
                cos.append(old[stock])          # 실패한 날은 기존 것 보존
            continue
        prev_recs = {o["rec"] for o in (old.get(stock) or {}).get("open") or []}
        opn = []
        reg = {}
        for r in mine:
            pl = is_plant(r)
            opn.append({"rec": r["rec"], "title": r["title"][:60], "sec": r["sec"][:5],
                        "region": r["region"], "day": r["day"], "plant": 1 if pl else 0})
            if pl and r["region"]:
                reg[r["region"]] = reg.get(r["region"], 0) + 1
        p = sum(x["plant"] for x in opn)
        new = len([x for x in opn if prev_recs and x["rec"] not in prev_recs]) if prev_recs else None
        hist = [h for h in (old.get(stock) or {}).get("hist") or [] if h.get("d") != today]
        hist.append({"d": today, "n": len(opn), "p": p, "o": len(opn) - p, "new": new, "reg": reg})
        cos.append({"stock": stock, "q": q, "big": 1 if stock in BIG else 0,
                    "hist": hist[-DAYS:], "open": opn})
        tag = " · ".join(f"{k} {v}" for k, v in sorted(reg.items(), key=lambda x: -x[1])[:3])
        print(f"  {stock:10s} 공고 {len(opn):2d} · 현장 {p:2d}" + (f" · 신규 {new}" if new is not None else "") + (f" · {tag}" if tag else ""))
        nap(0.7)

    if len(fails) > len(COS) / 2:
        note_health("채용공고", f"{len(fails)}/{len(COS)} 실패: {fails[0]}")
        print("[채용] 절반 넘게 실패 — 기존 보존"); sys.exit(1)
    note_health("채용공고", None)
    if fails:
        print("  일부 실패:", " | ".join(fails))

    out = {"asOf": now.strftime("%Y-%m-%d %H:%M KST"), "src": "사람인 채용공고(회사명 정확일치)", "cos": cos}
    if "--dry-run" in sys.argv:
        print(json.dumps(out, ensure_ascii=False)[:1500]); return
    if prev and json.dumps(prev.get("cos"), ensure_ascii=False, sort_keys=True) == \
            json.dumps(out["cos"], ensure_ascii=False, sort_keys=True):
        print("[채용] 변동 없음 — 건너뜀"); return
    open(HTML, "w", encoding="utf-8").write(_put(html_, "JOBS", out))
    tot = sum(c["hist"][-1]["n"] for c in cos); pl = sum(c["hist"][-1]["p"] for c in cos)
    print(f"[OK] JOBS 갱신 · {len(cos)}종목 · 공고 {tot} (현장 {pl})")


if __name__ == "__main__":
    main()
