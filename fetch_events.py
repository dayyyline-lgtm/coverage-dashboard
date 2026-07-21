# -*- coding: utf-8 -*-
"""
DART 전자공시 -> 이벤트 캘린더 수집
------------------------------------
index.html 의  const DART_EVENTS = [...];  블록을 갱신합니다.
(시세용 refresh_live.py 가 건드리는 LIVE 블록과 분리되어 서로 덮어쓰지 않음)

수집 내용
  - 기업설명회(IR) 개최  : 공시 원문에서 실제 개최 '일시'를 파싱 -> 미래 일정
  - 영업(잠정)실적 공시   : 실적 발표일
  - 배당/자사주/증자/주총 : 기업 이벤트

사용법
    python fetch_events.py
    (키는 secrets_local.py 의 DART_API_KEY, 또는 환경변수 DART_API_KEY)

DART 키 발급: https://opendart.fss.or.kr  (무료)
"""
import urllib.request, urllib.error, zipfile, io, json, re, sys, os, time, datetime
import html as html_mod

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HTML_PATH = "index.html"
CACHE = "corpcode_cache.json"
LOOKBACK_DAYS = 120          # 공시 조회 기간
KEEP_FROM_DAYS = 45          # 캘린더에 남길 과거 범위

try:
    from secrets_local import DART_API_KEY
except ImportError:
    DART_API_KEY = ""
DART_API_KEY = os.environ.get("DART_API_KEY", DART_API_KEY)

# 캘린더에 넣을 공시 (키워드 -> 표시타입)
INCLUDE = [
    (("기업설명회",), "ir"),
    (("영업(잠정)실적", "영업실적"), "earn"),
    (("배당",), "corp"),
    (("자기주식",), "corp"),
    (("유상증자", "무상증자", "전환사채", "신주인수권"), "corp"),
    (("주주총회",), "corp"),
]
# 노이즈 (지분 신고 등 — 이벤트가 아님)
EXCLUDE = ("소유상황보고서", "대량보유상황보고서", "최대주주등소유주식변동",
           "대규모기업집단현황", "특수관계인", "전환청구권행사")


def get(url, timeout=30):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=timeout).read()


def corp_map():
    """stock_code(6) -> corp_code(8). 한 번 받아서 캐시."""
    if os.path.exists(CACHE):
        return json.load(open(CACHE, encoding="utf-8"))
    print("DART 기업코드 다운로드 중… (최초 1회, 약 3.5MB)")
    raw = get(f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={DART_API_KEY}", 90)
    xml = zipfile.ZipFile(io.BytesIO(raw)).read("CORPCODE.xml").decode("utf-8")
    pairs = re.findall(
        r"<corp_code>(\d+)</corp_code>\s*<corp_name>(.*?)</corp_name>"
        r"(?:\s*<corp_eng_name>.*?</corp_eng_name>)?\s*<stock_code>\s*(\d{6})\s*</stock_code>", xml)
    m = {sc: cc for cc, _nm, sc in pairs}
    json.dump(m, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"  기업코드 {len(m)}건 캐시 완료 ({CACHE})")
    return m


def classify(report_nm):
    n = re.sub(r"\[.*?\]", "", report_nm).strip()
    if any(x in n for x in EXCLUDE):
        return None, n
    for keys, ty in INCLUDE:
        if any(k in n for k in keys):
            return ty, n
    return None, n


def ir_datetime(rcept_no):
    """IR 개최 공시 원문에서 실제 개최 일시와 주요내용을 뽑는다."""
    try:
        raw = get(f"https://opendart.fss.or.kr/api/document.xml?crtfc_key={DART_API_KEY}"
                  f"&rcept_no={rcept_no}", 30)
        z = zipfile.ZipFile(io.BytesIO(raw))
        doc = z.read(z.namelist()[0])
        txt = None
        for enc in ("utf-8", "cp949", "euc-kr"):
            try:
                txt = doc.decode(enc); break
            except UnicodeDecodeError:
                continue
        if not txt:
            return None, None
        txt = re.sub(r"<style.*?</style>", " ", txt, flags=re.S | re.I)
        txt = re.sub(r"\.xforms[^}]*\}", " ", txt)
        txt = re.sub(r"<[^>]+>", " ", txt)
        txt = re.sub(r"\s+", " ", txt)

        date = None
        i = txt.find("일시")
        if i > 0:
            m = re.search(r"(20\d{2}-\d{2}-\d{2})", txt[i:i + 200])
            if m:
                date = m.group(1)
        title = None
        for label in ("주요내용", "주 요 내 용", "설명회내용", "목적"):
            j = txt.find(label)
            if j < 0:
                continue
            t = txt[j + len(label): j + len(label) + 90].strip(" :·-")
            t = re.split(r"\s\d\s*\.\s", t)[0].strip(" :·-")
            t = html_mod.unescape(re.sub(r"\s+", " ", t))
            t = re.sub(r"^\(\s*요약\s*\)\s*", "", t).strip(" :·-")
            if len(t) >= 4:
                title = t[:38]
                break
        return date, title
    except Exception:
        return None, None


def main():
    if not DART_API_KEY:
        print("DART_API_KEY 가 없습니다. secrets_local.py 에 넣어주세요."); sys.exit(1)

    html = open(HTML_PATH, encoding="utf-8").read()
    m = re.search(r"const DATA = (\{.*?\});\n", html, re.S)
    records = json.loads(m.group(1))["records"]
    live = json.loads(re.search(r"const LIVE = (\{.*?\});\n", html, re.S).group(1))
    name2code = {n: v["code"] for n, v in live["stocks"].items()}

    cmap = corp_map()
    end = datetime.date.today()
    start = end - datetime.timedelta(days=LOOKBACK_DAYS)
    keep_from = (end - datetime.timedelta(days=KEEP_FROM_DAYS)).strftime("%Y-%m-%d")

    events, ir_hits = [], 0
    for idx, r in enumerate(records, 1):
        nm = r["name"]
        sc = name2code.get(nm)
        cc = cmap.get(sc) if sc else None
        if not cc:
            print(f"  [{idx}/{len(records)}] {nm}: 기업코드 없음"); continue
        try:
            d = json.loads(get(
                f"https://opendart.fss.or.kr/api/list.json?crtfc_key={DART_API_KEY}"
                f"&corp_code={cc}&bgn_de={start:%Y%m%d}&end_de={end:%Y%m%d}&page_count=100").decode("utf-8"))
        except Exception as e:
            print(f"  [{idx}/{len(records)}] {nm}: 조회 실패 {str(e)[:40]}"); continue

        n_co = 0
        for it in (d.get("list") or []):
            ty, clean = classify(it["report_nm"])
            if not ty:
                continue
            rd = it["rcept_dt"]
            date = f"{rd[:4]}-{rd[4:6]}-{rd[6:]}"
            title = clean
            if ty == "ir":                       # 원문에서 실제 개최일 파싱
                dt2, t2 = ir_datetime(it["rcept_no"])
                ir_hits += 1
                if dt2:
                    date = dt2
                title = t2 or "기업설명회(IR)"
                time.sleep(0.12)
            if date < keep_from:
                continue
            events.append({"co": nm, "code": sc, "date": date,
                           "title": title, "type": ty, "src": "DART"})
            n_co += 1
        print(f"  [{idx}/{len(records)}] {nm}: {n_co}건")
        time.sleep(0.12)

    # 같은 날 같은 종목 중복 제거
    seen, uniq = set(), []
    for e in sorted(events, key=lambda x: (x["date"], x["co"])):
        k = (e["co"], e["date"], e["type"])
        if k in seen:
            continue
        seen.add(k); uniq.append(e)

    block = "const DART_EVENTS = " + json.dumps(uniq, ensure_ascii=False) + ";"
    if "const DART_EVENTS =" in html:
        html = re.sub(r"const DART_EVENTS = \[.*?\];", block, html, count=1, flags=re.S)
    else:
        html = html.replace("/* ==== helpers ==== */", block + "\n\n/* ==== helpers ==== */", 1)
    open(HTML_PATH, "w", encoding="utf-8").write(html)

    future = [e for e in uniq if e["date"] >= end.strftime("%Y-%m-%d")]
    print(f"\n[OK] 이벤트 {len(uniq)}건 반영 (IR 원문 파싱 {ir_hits}건 / 향후 일정 {len(future)}건)")
    for e in future[:12]:
        print(f"   {e['date']}  {e['co']:8s} {e['title'][:34]}")


if __name__ == "__main__":
    main()
