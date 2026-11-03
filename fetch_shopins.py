"""네이버 쇼핑인사이트(쇼핑 카테고리 안 키워드 클릭 추이 + 연령별 클릭) -> index.html 의  const SHOPINS = {...};   (2026-11-03)

검색 트렌드(TREND · 데이터랩 검색어트렌드)는 '네이버에서 검색한 양'이다. 쇼핑인사이트는 **네이버쇼핑 안에서 그 키워드로 상품을 누른 양**이라
구매 쪽에 한 걸음 더 가깝다. 같은 데이터랩 키를 쓰되, 네이버 개발자센터 앱 설정 '사용 API'에 **데이터랩(쇼핑인사이트)** 이 체크돼 있어야 한다.
  · 옛 개발자센터 키(openapi.naver.com · X-Naver-Client-Id)를 먼저 쓰고, 401/403 이면 NAVER API HUB 키(NCP_APIGW_KEY_ID · NCP_APIGW_KEY)로 다시 시도한다.
    (2026-07-31 부터 새 앱은 HUB 로만 만든다 · 옛 키는 2027-06-30 까지 — 둘 다 없으면 이번 회차는 건너뛰고 기존 값을 둔다.)
  · 비율은 **요청 하나 안에서 최고 = 100** 이다. 그룹끼리 높이를 견주면 안 된다(그룹 안 계열끼리만 비교).
  · 주별 104주 · 끝은 **지난 일요일**(진행 중인 주를 섞지 않는다). 연령별은 월별 24개월 · 끝은 지난달 말일.
  · 화면은 app.js injectShopInsTrends — 트렌드 탭 종목별 주제로 붙는다(TREND_STOCK · 경쟁사 섞인 그룹은 TREND_OWNER).

python fetch_shopins.py
"""
import datetime, json, os, re, time

from collector_health import note_health

try:
    from secrets_local import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
except ImportError:
    NAVER_CLIENT_ID = NAVER_CLIENT_SECRET = ""
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", NAVER_CLIENT_ID)
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", NAVER_CLIENT_SECRET)
NCP_ID = os.environ.get("NCP_APIGW_KEY_ID", "")
NCP_KEY = os.environ.get("NCP_APIGW_KEY", "")

KST = datetime.timezone(datetime.timedelta(hours=9))
HTML = "public/index.html"
CATS = {"50000002": "화장품/미용", "50000006": "식품", "50000005": "출산/육아", "50000008": "생활/건강"}

# 그룹 = (이름, 카테고리, [(표시 이름, [검색어…])], 이 주제를 붙일 종목, {계열: 주인 종목} — 남의 계열이 섞일 때만)
# 한 요청 최대 5개 계열. 검색어는 계열당 여러 개 가능(합쳐서 하나의 계열).
GROUPS = [
    # ── 화장품 ──
    ("에이피알 브랜드 쇼핑클릭", "50000002", [("메디큐브", ["메디큐브", "에이지알"]), ("에이프릴스킨", ["에이프릴스킨"]), ("포맨트", ["포맨트"])], ["에이피알"], None),
    ("아모레퍼시픽 브랜드 쇼핑클릭", "50000002", [("설화수", ["설화수"]), ("라네즈", ["라네즈"]), ("코스알엑스", ["코스알엑스"]),
                                         ("일리윤", ["일리윤"]), ("에스트라", ["에스트라", "아토베리어"])], ["아모레퍼시픽"], None),
    ("LG생활건강 브랜드 쇼핑클릭", "50000002", [("후", ["더후", "후 화장품"]), ("숨37", ["숨37"]), ("CNP", ["CNP", "차앤박"]),
                                          ("피지오겔", ["피지오겔"]), ("닥터그루트", ["닥터그루트"])], ["LG생활건강"], None),
    ("클리오 브랜드 쇼핑클릭", "50000002", [("클리오", ["클리오"]), ("페리페라", ["페리페라"]), ("구달", ["구달"])], ["클리오"], None),
    ("네오팜 브랜드 쇼핑클릭", "50000002", [("아토팜", ["아토팜"]), ("제로이드", ["제로이드"]), ("리얼베리어", ["리얼베리어"])], ["네오팜"], None),
    ("에이블씨엔씨 브랜드 쇼핑클릭", "50000002", [("미샤", ["미샤"]), ("어퓨", ["어퓨"])], ["에이블씨엔씨"], None),
    ("엔에프씨 고객사 브랜드 쇼핑클릭", "50000002", [("이퀄베리", ["이퀄베리"]), ("셀리맥스", ["셀리맥스"]), ("닥터엘시아", ["닥터엘시아"])], ["엔에프씨"], None),
    # 한 브랜드 종목은 비슷한 체급끼리 묶어 '누가 더 눌리나'를 본다 — 주인표가 계열별 신호를 가른다.
    ("색조 브랜드 쇼핑클릭", "50000002", [("롬앤", ["롬앤"]), ("클리오", ["클리오"]), ("페리페라", ["페리페라"]), ("힌스", ["힌스"]), ("토니모리", ["토니모리"])],
     ["아이패밀리에스씨", "토니모리", "클리오", "LG생활건강"],
     {"롬앤": "아이패밀리에스씨", "토니모리": "토니모리", "클리오": "클리오", "페리페라": "클리오", "힌스": "LG생활건강"}),
    ("기초 중소형 브랜드 쇼핑클릭", "50000002", [("달바", ["달바"]), ("마녀공장", ["마녀공장"]), ("리들샷", ["리들샷", "VT코스메틱"]),
                                           ("센텔리안24", ["센텔리안24", "마데카크림"]), ("아로마티카", ["아로마티카"])],
     ["달바글로벌", "마녀공장", "브이티", "동국제약", "아로마티카"],
     {"달바": "달바글로벌", "마녀공장": "마녀공장", "리들샷": "브이티", "센텔리안24": "동국제약", "아로마티카": "아로마티카"}),
    ("탈모샴푸 쇼핑클릭", "50000002", [("TS샴푸", ["TS샴푸", "티에스샴푸"]), ("려", ["려샴푸"]), ("닥터그루트", ["닥터그루트"]),
                                   ("닥터포헤어", ["닥터포헤어"]), ("라보에이치", ["라보에이치"])],
     ["TS트릴리온"], {"TS샴푸": "TS트릴리온", "려": "아모레퍼시픽", "닥터그루트": "LG생활건강"}),
    ("리쥬란 화장품 쇼핑클릭", "50000002", [("리쥬란", ["리쥬란", "리쥬란크림"]), ("바이오던스", ["바이오던스"])],
     ["파마리서치", "제닉"], {"리쥬란": "파마리서치", "바이오던스": "제닉"}),
    # ── 식품 ──
    ("라면 브랜드 쇼핑클릭", "50000006", [("불닭볶음면", ["불닭볶음면", "불닭"]), ("신라면", ["신라면"]), ("짜파게티", ["짜파게티"]),
                                     ("진라면", ["진라면"]), ("삼양라면", ["삼양라면"])],
     ["삼양식품", "농심"], {"불닭볶음면": "삼양식품", "삼양라면": "삼양식품", "신라면": "농심", "짜파게티": "농심"}),
    ("농심 제품 쇼핑클릭", "50000006", [("신라면", ["신라면"]), ("짜파게티", ["짜파게티"]), ("너구리", ["너구리"]), ("새우깡", ["새우깡"]),
                                   ("신라면툼바", ["신라면툼바", "툼바"])], ["농심"], None),
    ("CJ제일제당 제품 쇼핑클릭", "50000006", [("비비고 만두", ["비비고 만두", "비비고만두"]), ("햇반", ["햇반"]), ("고메", ["고메"]),
                                         ("스팸", ["스팸"]), ("비비고 김치", ["비비고 김치", "비비고김치"])], ["CJ제일제당"], None),
    ("빙그레 제품 쇼핑클릭", "50000006", [("바나나맛우유", ["바나나맛우유"]), ("메로나", ["메로나"]), ("투게더", ["투게더"]),
                                     ("요플레", ["요플레"]), ("붕어싸만코", ["붕어싸만코"])], ["빙그레"], None),
    ("정관장 쇼핑클릭", "50000006", [("정관장", ["정관장"]), ("에브리타임", ["정관장 에브리타임", "에브리타임"]), ("홍삼정", ["홍삼정"])], ["KT&G"], None),
    # ── 완구 ──
    ("변신·캐릭터 완구 쇼핑클릭", "50000005", [("티니핑", ["티니핑", "캐치티니핑"]), ("메탈카드봇", ["메탈카드봇"]),
                                         ("헬로카봇", ["헬로카봇"]), ("또봇", ["또봇"])],
     ["SAMG엔터"], {"티니핑": "SAMG엔터", "메탈카드봇": "SAMG엔터"}),
]
# 연령별 클릭 비중 — 종목의 대표 브랜드 하나씩(새 수요층이 들어오는지). 이름 · 카테고리 · 검색어 · 종목
AGE = [
    ("메디큐브", "50000002", "메디큐브", "에이피알"), ("설화수", "50000002", "설화수", "아모레퍼시픽"),
    ("더후", "50000002", "더후", "LG생활건강"), ("달바", "50000002", "달바", "달바글로벌"),
    ("롬앤", "50000002", "롬앤", "아이패밀리에스씨"), ("클리오", "50000002", "클리오", "클리오"),
    ("리들샷", "50000002", "리들샷", "브이티"), ("마녀공장", "50000002", "마녀공장", "마녀공장"),
    ("불닭볶음면", "50000006", "불닭볶음면", "삼양식품"), ("신라면", "50000006", "신라면", "농심"),
    ("티니핑", "50000005", "티니핑", "SAMG엔터"),
]
AGES = ["10", "20", "30", "40", "50", "60"]


class AuthError(Exception):
    pass


def _post(path, body):
    """옛 개발자센터 → (401/403) → API HUB 순서. 쓴 경로를 같이 돌려준다."""
    import requests
    tries = []
    if NAVER_CLIENT_ID:
        tries.append(("legacy", "https://openapi.naver.com/v1/datalab/shopping/" + path,
                      {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}))
    if NCP_ID:
        tries.append(("hub", "https://naverapihub.apigw.ntruss.com/shopping/v1/" + path,
                      {"X-NCP-APIGW-API-KEY-ID": NCP_ID, "X-NCP-APIGW-API-KEY": NCP_KEY}))
    if not tries:
        raise AuthError("네이버 키 없음")
    last = None
    for via, url, h in tries:
        h = dict(h); h["Content-Type"] = "application/json"
        r = requests.post(url, headers=h, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), timeout=25)
        if r.status_code in (401, 403):
            last = f"{via} {r.status_code} {r.text[:120]}"; continue
        r.raise_for_status()
        return r.json(), via
    raise AuthError(last or "인증 실패")


def week_window(today):
    end = today - datetime.timedelta(days=today.weekday() + 1)        # 지난 일요일(완결된 주의 끝)
    start = end - datetime.timedelta(days=7 * 104 - 1)                 # 그 주 포함 104주(월요일 시작)
    return start, end


def month_window(today):
    end = today.replace(day=1) - datetime.timedelta(days=1)            # 지난달 말일
    y, m = end.year, end.month - 23
    while m < 1:
        m += 12; y -= 1
    return datetime.date(y, m, 1), end


def fetch_group(cat, series, start, end):
    body = {"startDate": start.isoformat(), "endDate": end.isoformat(), "timeUnit": "week", "category": cat,
            "keyword": [{"name": lab, "param": kws} for lab, kws in series], "device": "", "gender": "", "ages": []}
    d, via = _post("category/keywords", body)
    per = {}
    for res in d.get("results", []):
        per[res.get("title")] = {x["period"]: x["ratio"] for x in res.get("data", [])}
    return per, via


def fetch_age(cat, kw, start, end):
    body = {"startDate": start.isoformat(), "endDate": end.isoformat(), "timeUnit": "month", "category": cat,
            "keyword": kw, "device": "", "gender": "", "ages": []}
    d, via = _post("category/keyword/age", body)
    by = {}
    for res in d.get("results", []):
        for x in res.get("data", []):
            by.setdefault(x["period"][:7], {})[str(x.get("group"))] = x["ratio"]
    return by, via


def mondays(start, end):
    out, d = [], start
    while d <= end:
        out.append(d.isoformat()); d += datetime.timedelta(days=7)
    return out


def main():
    today = datetime.datetime.now(KST).date()
    html = open(HTML, encoding="utf-8").read()
    m = re.search(r"^const SHOPINS = (\{.*?\});$", html, re.M | re.S)
    old = json.loads(m.group(1)) if m else {}
    ws, we = week_window(today)
    axis = mondays(ws, we)
    ms, me = month_window(today)
    out_g, out_a, bad, via_used = {}, {}, [], set()
    try:
        for name, cat, series, stocks, owners in GROUPS:
            try:
                per, via = fetch_group(cat, series, ws, we)
                via_used.add(via)
                s = [[per.get(lab, {}).get(p) for p in axis] for lab, _ in series]
                out_g[name] = {"cat": cat, "catNm": CATS.get(cat, cat), "labels": [x[0] for x in series],
                               "w": axis, "s": s, "stocks": stocks, "own": owners or {}}
                nz = [sum(1 for v in row if v) for row in s]
                print(f"[쇼핑] {name:24} 0아닌 주 {nz}")
            except AuthError:
                raise
            except Exception as e:
                bad.append(f"{name} {type(e).__name__}"); print(f"[쇼핑] {name} 실패: {str(e)[:120]}")
                if (old.get("g") or {}).get(name): out_g[name] = old["g"][name]
            time.sleep(0.3)
        for label, cat, kw, stock in AGE:
            try:
                by, via = fetch_age(cat, kw, ms, me)
                via_used.add(via)
                months = sorted(by)
                # 연령별 비율도 '요청 안 최고=100' 이라 그달 합으로 나눠 비중(%)으로 바꾼다.
                share = {a: [] for a in AGES}
                for mo in months:
                    tot = sum(by[mo].get(a) or 0 for a in AGES)
                    for a in AGES:
                        v = by[mo].get(a)
                        share[a].append(round(v / tot * 100, 1) if (tot and v is not None) else None)
                out_a[label] = {"cat": cat, "kw": kw, "stock": stock, "m": months, "s": [share[a] for a in AGES]}
                print(f"[쇼핑] 연령 {label:8} {len(months)}개월")
            except AuthError:
                raise
            except Exception as e:
                bad.append(f"연령 {label} {type(e).__name__}"); print(f"[쇼핑] 연령 {label} 실패: {str(e)[:120]}")
                if (old.get("age") or {}).get(label): out_a[label] = old["age"][label]
            time.sleep(0.3)
    except AuthError as e:
        # 키에 쇼핑인사이트 권한이 없다 — 실패로 남기되 기존 값은 그대로 둔다(화면이 안 비게).
        print(f"[쇼핑] 인증 실패 — 네이버 개발자센터 앱 '사용 API'에 데이터랩(쇼핑인사이트)을 추가해야 합니다: {e}")
        note_health("네이버 쇼핑인사이트", f"인증 실패(쇼핑인사이트 권한 없음) {str(e)[:80]}")
        return
    note_health("네이버 쇼핑인사이트", "; ".join(bad) if bad else None)
    if not out_g and not out_a:
        print("[쇼핑] 받은 것 없음 — 블록 그대로"); return
    if m and old.get("g") == out_g and old.get("age") == out_a:
        print("[쇼핑] 변동 없음"); return
    block_obj = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "via": sorted(via_used),
                 "note": "네이버 데이터랩 쇼핑인사이트 · 카테고리 안 키워드 클릭 추이(요청 안 최고=100 · 주별 · 완결된 주만) + 연령별 클릭 비중(월별 · 그달 합=100)",
                 "g": out_g, "age": out_a}
    block = "const SHOPINS = " + json.dumps(block_obj, ensure_ascii=False, separators=(",", ":")) + ";"
    if m:
        html = html[:m.start()] + block + html[m.end():]
    else:
        a = re.search(r"^const TREND = ", html, re.M)
        html = html[:a.start()] + block + "\n" + html[a.start():]
    open(HTML, "w", encoding="utf-8").write(html)
    print(f"[쇼핑] 블록 갱신 {len(block) // 1024}KB · 그룹 {len(out_g)} · 연령 {len(out_a)} · 경로 {sorted(via_used)}")


if __name__ == "__main__":
    main()
