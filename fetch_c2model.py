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
  qrev   {"2019Q1": 107.7, ...}   분기 매출(십억, 연결). 4Q = 연간 − 3Q누적
  qop    같은 형식의 영업이익
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

# 검색 키워드 -> 화면 이름. 한 요청에 묶여 같은 스케일로 온다.
GAMES = {
    "서머너즈워": "서머너즈워",
    "컴투스프로야구": "컴투스프로야구",
    "제우스 오만의 신": "제우스",
    "MLB 9이닝스": "MLB 9이닝스",
}


def dart_quarters(y0=2019):
    """분기 매출·영업이익(십억, 연결).
       1Q·반기·3Q 보고서의 '당기' 는 그 분기 단독값이고, 사업보고서는 연간이라 4Q = 연간 − 3Q누적."""
    rev, op = {}, {}
    y1 = datetime.datetime.now(KST).year
    for y in range(y0, y1 + 1):
        acc = {}
        for rc, q in (("11013", 1), ("11012", 2), ("11014", 3), ("11011", 4)):
            u = (f"https://opendart.fss.or.kr/api/fnlttSinglAcnt.json?crtfc_key={DART_KEY}"
                 f"&corp_code={CORP}&bsns_year={y}&reprt_code={rc}")
            try:
                d = json.loads(urllib.request.urlopen(u, timeout=25).read().decode())
            except Exception:
                continue
            if d.get("status") != "000":
                continue
            cur = {}
            for r in d["list"]:
                if r.get("fs_div") != "CFS":
                    continue
                if r["account_nm"] in ("매출액", "영업이익"):
                    def num(s):
                        s = (s or "").replace(",", "").strip()
                        try:
                            return float(s) / 1e9
                        except ValueError:
                            return None
                    cur[r["account_nm"]] = (num(r.get("thstrm_amount")),
                                            num(r.get("thstrm_add_amount")))
            if cur:
                acc[q] = cur
        for q in (1, 2, 3):
            if q in acc:
                if acc[q].get("매출액", (None,))[0] is not None:
                    rev[f"{y}Q{q}"] = round(acc[q]["매출액"][0], 2)
                if acc[q].get("영업이익", (None,))[0] is not None:
                    op[f"{y}Q{q}"] = round(acc[q]["영업이익"][0], 2)
        if 4 in acc and 3 in acc:
            for nm, tgt in (("매출액", rev), ("영업이익", op)):
                yr = acc[4].get(nm, (None, None))[0]
                add3 = acc[3].get(nm, (None, None))[1]
                if yr is not None and add3 is not None:
                    tgt[f"{y}Q4"] = round(yr - add3, 2)
    return rev, op


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
        rev, op = dart_quarters()
    except Exception as e:
        rev, op, _ = {}, {}, dead.append(f"DART: {str(e)[:60]}")
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
           "stock": "컴투스", "qrev": rev, "qop": op,
           "games": GAMES, "search": search}

    qs = sorted(rev)
    print(f"  분기 실적 {len(qs)}개 {qs[0]}~{qs[-1]} · 최근 {rev[qs[-1]]:.1f}십억")
    for k, v in search.items():
        ms = sorted(v)
        print(f"  검색 {GAMES.get(k,k):14s} {len(ms)}개월 {ms[0]}~{ms[-1]} 최근 {v[ms[-1]]:.1f}")

    if "--dry-run" in sys.argv:
        return
    m = re.search(r"const C2MODEL\s*=\s*(\{.*?\});", html, re.S)
    if m:
        try:
            old = json.loads(m.group(1))
            if all(old.get(k) == out.get(k) for k in ("qrev", "qop", "search")):
                print("변동 없음 — index.html 그대로 둠")
                return
        except json.JSONDecodeError:
            pass
    open(HTML, "w", encoding="utf-8").write(_put(html, "C2MODEL", out))
    print(f"[OK] C2MODEL 갱신 · 분기 {len(rev)} · 검색 {len(search)}계열")


if __name__ == "__main__":
    main()
