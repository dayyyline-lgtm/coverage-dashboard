# -*- coding: utf-8 -*-
"""컴투스 매출 모델의 재료 수집 -> index.html 의  const C2MODEL = {...};

왜 이걸 따로 받나 (2026-09-21 신설)
  트렌드 데이터로 월별 매출을 추정하려면 **맞출 대상(공시 실적)이 길게** 있어야 한다.
  화면의 `LIVE` 는 분기 6개(1.5년)뿐이라 계절성·기저 오차를 잴 표본이 안 된다.
  DART 주요계정은 2019년까지 그대로 주므로 여기서 27분기를 받는다.

  검색은 네이버 데이터랩 **월별**. 데이터랩은 한 번의 요청으로 7년치를 주고(실측 93개월),
  한 요청 안의 키워드끼리는 **같은 스케일로 정규화**된다. 요청이 다르면 스케일이 달라지므로
  게임 키워드는 **반드시 한 요청에 묶어서** 받아야 서로 비교된다.

무엇이 들어 있나
  qrev   {"2019Q1": 107.7, ...}   분기 매출(십억, 연결). 4Q = 연간 − 3Q누적 · 다음 해 비교치(재작성) 우선
  qop    같은 형식의 영업이익
  fin    {"2026Q2": {"c": {rev,opex,op,pbt,np,npp}, "s": {rev,opex,op}}}  2024Q1~ 연결(c)·별도(s) 손익
         — 화면 '게임별 분기 손익'의 실적 칸. 별도 = 컴투스 본사(게임), 연결 − 별도 = 자회사 (2026-09-28)
  search {"서머너즈워": {"2019-01": 3.2, ...}, ...}  월별 검색지수(상대)
  games  검색 키워드 -> 화면 표시용 이름

⚠ 이 블록은 **모델의 입력**이지 화면 표시용이 아니다. 계수·추정식은 js/app.js 의 C2 모델에 있다.
⚠ 분기 매출은 **연결(CFS)** 이다. 컴투스 연결엔 미디어(위지윅 등) 등 비게임이 섞여 있어
  게임 검색만으로 레벨을 설명할 수 없다(실측 R²=0.18). 그래서 모델은 레벨을 공시 기저에서 잡는다.

  python fetch_c2model.py            # 수집·기록
  python fetch_c2model.py --dry-run  # 출력만
"""
import json, re, sys, urllib.request, datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 키는 **환경변수 우선**(러너) → secrets_local(이 PC). 러너에는 secrets_local.py 가 없으므로
# import 를 통째로 감싸지 않으면 그 자리에서 죽는다(2026-09-21 도입 때 이 함정을 밟을 뻔했다).
import os
sys.path.insert(0, ".")
NAVER_CLIENT_ID = NAVER_CLIENT_SECRET = ""
DART_KEY = ""
try:
    from secrets_local import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
    import secrets_local as _S
    DART_KEY = next((getattr(_S, k) for k in dir(_S) if "DART" in k.upper()), "")
except Exception:
    pass
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", NAVER_CLIENT_ID)
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", NAVER_CLIENT_SECRET)
DART_KEY = os.environ.get("DART_API_KEY", DART_KEY)

from collector_health import note_health

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
CORP = "00476498"          # 컴투스
SEARCH_FROM = "2019-01-01"
FIN_FROM_YEAR = 2024       # 분기 손익표 실적 칸은 2024Q1 부터(2025 전년비 계산용). 별도(OFS)도 여기부터 받는다

# 검색 키워드 -> 화면 이름. 한 요청에 묶여 같은 스케일로 온다.
GAMES = {
    "서머너즈워": "서머너즈워",
    "컴투스프로야구": "컴투스프로야구",
    "제우스 오만의 신": "제우스",
    "MLB 9이닝스": "MLB 9이닝스",
}


# 손익 계정 — account_id 가 먼저, 안 맞으면 이름. 컴투스는 2Q23 부터 '성격별'(영업수익/영업비용)로
# 바꿨고 그 두 보고서(2023 반기·3Q)는 account_id 가 '-표준계정코드 미사용-' 이라 이름으로만 잡힌다.
# ⚠ 예전엔 주요계정 API(fnlttSinglAcnt)에서 '매출액'만 찾아서 2Q23~4Q23 매출이 통째로 빠졌다(2026-09-28 발견).
ACC = {
    "rev":  (("ifrs-full_Revenue",), ("영업수익", "매출액", "수익(매출액)")),
    "opex": (("ifrs-full_OperatingExpense",), ("영업비용",)),
    "op":   (("dart_OperatingIncomeLoss",), ("영업이익", "영업이익(손실)")),
    "pbt":  (("ifrs-full_ProfitLossBeforeTax",), ("법인세비용차감전순이익", "법인세비용차감전순이익(손실)")),
    "np":   (("ifrs-full_ProfitLoss",), ("당기순이익", "당기순이익(손실)")),
    "npp":  (("ifrs-full_ProfitLossAttributableToOwnersOfParent",), ()),
}
REPORTS = (("11013", 1), ("11012", 2), ("11014", 3), ("11011", 4))


def _num(s):
    s = (s or "").replace(",", "").strip()
    try:
        return float(s) / 1e9
    except ValueError:
        return None


def _pick(rows, key):
    """손익(IS·CIS)에서 계정 하나. 같은 계정이 두 번 나오면 첫 줄(손익 본문)."""
    ids, nms = ACC[key]
    for r in rows:
        if r.get("sj_div") not in ("IS", "CIS"):
            continue
        if r.get("account_id") in ids or (r.get("account_nm") or "").strip() in nms:
            return r
    return None


def _fs(y, rc, fs_div):
    u = (f"https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json?crtfc_key={DART_KEY}"
         f"&corp_code={CORP}&bsns_year={y}&reprt_code={rc}&fs_div={fs_div}")
    try:
        d = json.loads(urllib.request.urlopen(u, timeout=25).read().decode())
    except Exception:
        return None
    return d["list"] if d.get("status") == "000" else None


def dart_quarters(fs_div="CFS", y0=2019):
    """분기 손익(십억) — 전체 재무제표 API(fnlttSinglAcntAll).
       1Q·반기·3Q 보고서의 thstrm_amount 는 그 분기 3개월, 사업보고서는 연간이라 4Q = 연간 − 3Q누적.
       **다음 해 보고서의 비교치(재작성)를 우선한다** — 2023 은 엔피 중단영업 재분류로 매출이
       1Q 192.7→182.8 처럼 바뀌었는데, 원래 값을 쓰면 연간(재작성)과 분기 합이 안 맞는다.
       반환: {"2026Q2": {"rev":..,"opex":..,"op":..,"pbt":..,"np":..,"npp":..}, ...}"""
    y1 = datetime.datetime.now(KST).year
    raw = {}                                    # (y, q) -> rows
    for y in range(y0, y1 + 1):
        for rc, q in REPORTS:
            rows = _fs(y, rc, fs_div)
            if rows:
                raw[(y, q)] = rows
    orig, rest = {}, {}
    for (y, q), rows in raw.items():
        for key in ACC:
            r = _pick(rows, key)
            if not r:
                continue
            if q < 4:
                v, pv = _num(r.get("thstrm_amount")), _num(r.get("frmtrm_q_amount"))
                if v is not None:
                    orig.setdefault(f"{y}Q{q}", {})[key] = v
                if pv is not None:                        # 전년 같은 분기(재작성)
                    rest.setdefault(f"{y-1}Q{q}", {})[key] = pv
            else:
                r3 = _pick(raw.get((y, 3), []), key)
                if r3:
                    yr, c9 = _num(r.get("thstrm_amount")), _num(r3.get("thstrm_add_amount"))
                    if yr is not None and c9 is not None:
                        orig.setdefault(f"{y}Q4", {})[key] = yr - c9
                    pyr, pc9 = _num(r.get("frmtrm_amount")), _num(r3.get("frmtrm_add_amount"))
                    if pyr is not None and pc9 is not None:
                        rest.setdefault(f"{y-1}Q4", {})[key] = pyr - pc9
    out = {}
    for k in sorted(set(orig) | set(rest)):
        v = dict(orig.get(k, {}))
        v.update(rest.get(k, {}))                # 재작성 비교치가 있으면 그걸로
        if v.get("opex") is None and v.get("rev") is not None and v.get("op") is not None:
            v["opex"] = v["rev"] - v["op"]       # 기능별 양식(1Q23 이전)은 영업비용 줄이 없다
        out[k] = {kk: round(vv, 3) for kk, vv in v.items() if vv is not None}
    return out


def naver_months(keywords, start=SEARCH_FROM):
    """월별 검색지수. 한 요청이라 키워드끼리 같은 스케일이다."""
    import requests
    end = datetime.datetime.now(KST).date().isoformat()
    body = {"startDate": start, "endDate": end, "timeUnit": "month",
            "keywordGroups": [{"groupName": k, "keywords": [k]} for k in keywords]}
    r = requests.post("https://openapi.naver.com/v1/datalab/search",
                      headers={"X-Naver-Client-Id": NAVER_CLIENT_ID,
                               "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
                               "Content-Type": "application/json"},
                      data=json.dumps(body), timeout=30)
    r.raise_for_status()
    out = {}
    for g in r.json()["results"]:
        out[g["title"]] = {d["period"][:7]: round(d["ratio"], 2) for d in g["data"]}
    return out


def _put(html, name, obj):
    block = "const %s = %s;" % (name, json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
    pat = re.compile(r"const %s\s*=\s*\{.*?\};" % re.escape(name), re.S)
    if pat.search(html):
        return pat.sub(lambda m: block, html, count=1)
    liv = re.search(r"const LIVE\s*=\s*\{.*?\};", html, re.S)
    if not liv:
        raise RuntimeError("C2MODEL 삽입 기준(const LIVE)을 못 찾음")
    return html[:liv.end()] + "\n" + block + html[liv.end():]


def main():
    html = open(HTML, encoding="utf-8").read()
    dead = []
    try:
        cfs = dart_quarters("CFS")
        ofs = dart_quarters("OFS", y0=FIN_FROM_YEAR)
    except Exception as e:
        cfs, ofs, _ = {}, {}, dead.append(f"DART: {str(e)[:60]}")
    rev = {k: round(v["rev"], 2) for k, v in cfs.items() if "rev" in v}
    op = {k: round(v["op"], 2) for k, v in cfs.items() if "op" in v}
    # 분기 손익표(화면 '게임별 분기 손익')의 실적 칸 — 연결(c)·별도(s). 별도 = 컴투스 본사 = 게임,
    # 연결 − 별도 = 자회사. 장르·비용 항목 분해는 DART 에 없어 IR 자료(js 의 C2_IR)에서 온다.
    fin = {}
    for k in sorted(cfs):
        if k[:4] < str(FIN_FROM_YEAR):
            continue
        c = {kk: round(vv, 2) for kk, vv in cfs[k].items()}
        s = {kk: round(ofs[k][kk], 2) for kk in ("rev", "opex", "op") if kk in ofs.get(k, {})}
        fin[k] = {"c": c, "s": s} if s else {"c": c}
    try:
        search = naver_months(list(GAMES))
    except Exception as e:
        search = {}
        dead.append(f"네이버: {str(e)[:60]}")

    if not rev or not search:
        note_health("컴투스 모델", ("재료 수집 실패: " + " · ".join(dead))[:160])
        print("[c2model] 실패 — " + " · ".join(dead))
        sys.exit(1)
    note_health("컴투스 모델", None)

    out = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
           "stock": "컴투스", "qrev": rev, "qop": op, "fin": fin,
           "games": GAMES, "search": search}

    qs = sorted(rev)
    print(f"  분기 실적 {len(qs)}개 {qs[0]}~{qs[-1]} · 최근 {rev[qs[-1]]:.1f}십억")
    for k in sorted(fin)[-3:]:
        print(f"  {k} 연결 {fin[k]['c']} · 별도 {fin[k].get('s')}")
    for k, v in search.items():
        ms = sorted(v)
        print(f"  검색 {GAMES.get(k,k):14s} {len(ms)}개월 {ms[0]}~{ms[-1]} 최근 {v[ms[-1]]:.1f}")

    if "--dry-run" in sys.argv:
        return
    m = re.search(r"const C2MODEL\s*=\s*(\{.*?\});", html, re.S)
    if m:
        try:
            old = json.loads(m.group(1))
            if all(old.get(k) == out.get(k) for k in ("qrev", "qop", "fin", "search")):
                print("변동 없음 — index.html 그대로 둠")
                return
        except json.JSONDecodeError:
            pass
    open(HTML, "w", encoding="utf-8").write(_put(html, "C2MODEL", out))
    print(f"[OK] C2MODEL 갱신 · 분기 {len(rev)} · 검색 {len(search)}계열")


if __name__ == "__main__":
    main()
