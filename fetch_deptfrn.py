# -*- coding: utf-8 -*-
"""
백화점 3사 외국인 노출도 — 점포 상권 외국인 카드결제 + 점포 소재 구 외국인 방문 (2026-11-25 · → DEPTFRN)

사용자: 남이 만든 '2026.10 노출도 비교'(현대 +28.2% · 롯데 +24.4% · 신세계 +23.9%) 화면을 주며 "어케 따는지 알아봐 · 대시보드에 넣게"
→ "대시보드에 넣고 백화점 데이터로 바꿀 수 있나".

두 가지를 같은 산식으로 받는다(둘 다 한국관광 데이터랩 내부 JSON · 키 불필요 · fetch_tourism.py 와 같은 엔드포인트).

  ① 점포 상권 카드결제(백화점 쪽)   qid LN_10_02_003 · SGG_CD = 행정동 8자리
     업종 소분류 '대형쇼핑몰'(백화점·쇼핑몰·대형마트·아울렛)의 **외국인 카드 결제액**(DTL_TOU_NUM · 천원) → 백만원으로 저장.
     점포가 있는 행정동만 받는다. 회현동(신세계 본점)·소공동(롯데 본점)·반포4동(신세계 강남)처럼 백화점이 사실상 그 동의
     대형쇼핑몰 전부인 곳이 있고, 삼성1동(코엑스몰)·여의동(IFC몰)·압구정동(갤러리아)·잠실6동(롯데월드몰)처럼 남의 몰이 섞인 곳이 있다.
  ② 소재 구 외국인 방문(처음 받은 화면의 방식)   qid LN_03_01_067 · SGG_CD = 시군구 5자리
     국적별 외국인 방문자 수(연인원 · SKT 이동통신 기반)를 다 더한 값 = 그 구의 월 외국인 방문자 수.
     2026.10 화면값 3사를 그대로 재현했다(YoY · 가속도 · 증분 · 기여 1위 전부).

산식(화면에서 계산 — renderDeptFrn): 회사 노출 YoY = Σ V(t) ÷ Σ V(t−12) − 1 · 기여 = 증분 ÷ 작년 합 · 가속도 = YoY(t) − YoY(t−1).
회사 → 동·구 배정은 아래 CO 한 곳(블록에 같이 싣는다 — 화면이 이걸 읽는다).

  python fetch_deptfrn.py            # 새 달이 나왔으면 그 달 + 직전 달(수정 반영)을 받는다 · 빠진 달은 회차당 예산만큼 메운다
  python fetch_deptfrn.py --dry-run  # 출력만
"""
import copy, json, re, sys, time, datetime, urllib.request, urllib.parse

from collector_health import note_health

HTML = "public/index.html"
KST = datetime.timezone(datetime.timedelta(hours=9))
URL = "https://datalab.visitkorea.or.kr/visualize/getTempleteData.do"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
START = "202301"              # 2022년 이전은 업종 구성이 달라(소공동 2019 카드액이 지금보다 크다) 쓰지 않는다
BUDGET_S = 140                # 러너 스텝 3분 안쪽 — 넘으면 받은 만큼 저장하고 다음 회차가 잇는다
SRC = "health"

# 행정동 — [코드, 이름, 점포, 섞임 메모(없으면 "")] · 2026.10 대형쇼핑몰 외국인 결제 5억 원 이상인 점포 동만
#   (그 밖 점포 동은 월 5억 원 미만이라 YoY 에 거의 안 닿는다: 롯데 노원·관악·미아·강남·은평 · 현대 목동·천호·미아·가든파이브)
DONG = {
    "11140520": ["소공동", "롯데 본점(에비뉴엘·영플라자)", ""],
    "11710710": ["잠실6동", "롯데 월드타워점", "롯데월드몰 섞임"],
    "11710680": ["잠실3동", "롯데 잠실점", ""],
    "26230520": ["부전2동", "롯데 부산본점", ""],
    "11500640": ["방화2동", "롯데 김포공항점", "롯데몰 김포공항 섞임"],
    "11230560": ["전농1동", "롯데 청량리점", ""],
    "11215840": ["자양3동", "롯데 건대스타시티점", ""],
    "11560535": ["영등포동", "롯데 영등포점 · 신세계 타임스퀘어점", "두 회사에 다 넣음"],
    "11140540": ["회현동", "신세계 본점", ""],
    "11650581": ["반포4동", "신세계 강남점", ""],
    "26350520": ["우2동", "신세계 센텀시티점", "26.1 부터 집계 끊김 · 합계에서 뺌"],
    "11680580": ["삼성1동", "현대 무역센터점", "스타필드 코엑스몰 섞임"],
    "11560540": ["여의동", "더현대 서울", "IFC몰 섞임"],
    "11680545": ["압구정동", "현대 압구정본점", "갤러리아 명품관 섞임"],
    "41135657": ["백현동", "현대 판교점", ""],
    "11410585": ["신촌동", "현대 신촌점", ""],
}
GU = {"중구": "11140", "영등포": "11560", "강남": "11680", "서초": "11650", "송파": "11710", "강동": "11740",
      "서대문": "11410", "성북": "11290", "양천": "11470", "동대문": "11230", "관악": "11620", "노원": "11350",
      "강북": "11305", "강서": "11500", "광진": "11215", "은평": "11380"}

# 회사 → 동(카드) · 구(방문). 구 배정은 처음 받은 화면의 숫자를 정확히 재현하는 조합(2026-11-25 역산):
#   현대 = 구로(디큐브시티 2025-06 폐점) 대신 송파(가든파이브) · 롯데 = 송파 2곳(잠실·월드타워) + 은평 · 같은 구에 점포가 둘이어도 한 번만 센다
CO = {
    "롯데쇼핑": {"card": ["11140520", "11710710", "11710680", "26230520", "11500640", "11560535", "11230560", "11215840"],
               "gu": [["중구", "본점"], ["송파", "잠실·월드타워"], ["영등포", "영등포"], ["강남", "강남"], ["동대문", "청량리"],
                      ["관악", "관악"], ["노원", "노원"], ["강북", "미아"], ["강서", "김포공항"], ["광진", "건대스타시티"], ["은평", "은평"]],
               "nStore": 12},
    "신세계": {"card": ["11140540", "11650581", "11560535"], "skip": ["26350520"],
             "gu": [["중구", "본점"], ["서초", "강남"], ["영등포", "타임스퀘어"]], "nStore": 3},
    "현대백화점": {"card": ["11680580", "11560540", "11680545", "41135657", "11410585"],
               "gu": [["강남", "압구정본점·무역센터"], ["영등포", "더현대 서울"], ["서대문", "신촌"], ["성북", "미아"],
                      ["양천", "목동"], ["강동", "천호"], ["송파", "가든파이브"]], "nStore": 8},
}


def _q(qid, sgg, ym):
    p = {"qid": qid, "SGG_CD": sgg, "BASE_YM1": ym, "BASE_YM2": ym, "tabDiv": "2", "srchAreaDate": "1",
         "sggIntgYnFlag": "N", "dnname": "x"}
    req = urllib.request.Request(URL, data=urllib.parse.urlencode(p).encode(), headers={
        "User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8")).get("list") or []


def card(dong, ym):
    """그 동·그 달 '대형쇼핑몰' 외국인 카드 결제액(백만원). 그 달이 아직 없으면 None."""
    L = _q("LN_10_02_003", dong, ym)
    if not L:
        return None
    m = next((x for x in L if x.get("DPTR_REGN_DTL_NM") == "대형쇼핑몰"), None)
    return int(round((m.get("DTL_TOU_NUM") or 0) / 1000)) if m else 0


def visit(gu, ym):
    """그 구·그 달 외국인 방문자 수(연인원 · 국적별 합). 그 달이 아직 없으면 None."""
    L = _q("LN_03_01_067", GU[gu], ym)
    if not L:
        return None
    return int(sum(int(x.get("DTL_TOU_NUM") or 0) for x in L))


def _months(a, b):
    out, y, m = [], int(a[:4]), int(a[4:])
    while f"{y}{m:02d}" <= b:
        out.append(f"{y}{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def _const(html, name):
    m = re.search(r"const %s\s*=\s*(\{.*?\});" % re.escape(name), html, re.S)
    return json.loads(m.group(1)) if m else None


def _put(html, name, obj):
    block = "const %s = %s;" % (name, json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
    pat = re.compile(r"const %s\s*=\s*\{.*?\};" % re.escape(name), re.S)
    if pat.search(html):
        return pat.sub(lambda m: block, html, count=1)
    liv = re.search(r"const LIVE\s*=\s*\{.*?\};", html, re.S)
    if not liv:
        raise RuntimeError("DEPTFRN 삽입 기준(const LIVE)을 못 찾음")
    return html[:liv.end()] + "\n" + block + html[liv.end():]


def main():
    html = open(HTML, encoding="utf-8").read()
    old = _const(html, "DEPTFRN") or {}
    keep = copy.deepcopy(old)
    now = datetime.datetime.now(KST)
    py, pm = (now.year, now.month - 1) if now.month > 1 else (now.year - 1, 12)
    last = f"{py}{pm:02d}"                       # 지난달까지만 — 진행 중인 달은 묻지 않는다(부분 값이 섞이지 않게)
    have = old.get("months") or []
    C = {k: dict(zip(have, v)) for k, v in (old.get("card") or {}).items()}
    V = {k: dict(zip(have, v)) for k, v in (old.get("gu") or {}).items()}

    # 새 달 — 받은 마지막 달 다음 달부터. 대표 동(소공동)·구(중구)로 먼저 물어 보고 없으면 끝.
    t0 = time.time()
    newest = have[-1] if have else None
    probe = [m for m in _months(START, last) if newest is None or m > newest]
    got = []
    for ym in probe:
        try:
            a, b = card("11140520", ym), visit("중구", ym)
        except Exception as e:
            note_health("백화점 외국인", f"{ym} 확인 실패: {type(e).__name__}: {str(e)[:80]}")
            print(f"[백화점 외국인] {ym} 확인 실패 — 기존 데이터 보존: {e}"); return
        if a is None or b is None:
            print(f"  {ym}: 아직 공표 전 (카드 {'있음' if a is not None else '없음'} · 방문 {'있음' if b is not None else '없음'})")
            break
        got.append(ym)
    # 새 달이 있으면 그 달들 + 직전 달(공표 뒤 수정 반영)을 전부, 없으면 빠진 칸만
    redo = set(got)
    if got and have:
        redo.add(have[-1])
    months = sorted(set(have) | set(got))
    if not months:
        print("[백화점 외국인] 받은 달이 없음"); return
    jobs = []
    for ym in months:
        for d in DONG:
            if ym in redo or C.get(d, {}).get(ym) is None:
                jobs.append(("c", d, ym))
        for g in GU:
            if ym in redo or V.get(g, {}).get(ym) is None:
                jobs.append(("v", g, ym))
    done = fail = 0
    for kind, key, ym in jobs:
        if time.time() - t0 > BUDGET_S:
            print(f"  시간 예산({BUDGET_S}초) — {done}/{len(jobs)}건 받고 멈춤(다음 회차가 잇는다)"); break
        try:
            v = card(key, ym) if kind == "c" else visit(key, ym)
        except Exception as e:
            fail += 1
            print(f"  {kind} {key} {ym} 실패: {str(e)[:80]}")
            if fail >= 6:
                note_health("백화점 외국인", f"{fail}건 연속 실패 · {type(e).__name__}: {str(e)[:80]}"); break
            continue
        fail = 0
        (C if kind == "c" else V).setdefault(key, {})[ym] = v
        done += 1
        time.sleep(0.15)

    co = {k: {"card": v["card"], "skip": v.get("skip", []), "gu": v["gu"], "nStore": v["nStore"]} for k, v in CO.items()}
    out = {"asOf": old.get("asOf"),
           "src": "한국관광 데이터랩 · ① 행정동 '대형쇼핑몰' 외국인 카드 결제액(백만원) ② 구 외국인 방문자 수(SKT 이동통신 · 연인원)",
           "months": months,
           "card": {d: [C.get(d, {}).get(m) for m in months] for d in DONG},
           "gu": {g: [V.get(g, {}).get(m) for m in months] for g in GU},
           "dong": DONG, "co": co}
    lm = months[-1]
    for k, v in CO.items():
        c = sum((C.get(d, {}).get(lm) or 0) for d in v["card"])
        g = sum((V.get(x[0], {}).get(lm) or 0) for x in v["gu"])
        print(f"  {lm} {k}: 점포 상권 카드 {c / 100:,.1f}억 · 소재 구 방문 {g:,}명")

    if "--dry-run" in sys.argv:
        print(f"(dry-run · {len(months)}개월 · 받은 칸 {done})"); return
    if {k: v for k, v in out.items() if k != "asOf"} == {k: v for k, v in keep.items() if k != "asOf"}:
        print("[백화점 외국인] 변동 없음 — SKIP")
        note_health("백화점 외국인", None); return
    out["asOf"] = now.strftime("%Y-%m-%d %H:%M KST")
    open(HTML, "w", encoding="utf-8").write(_put(html, "DEPTFRN", out))
    note_health("백화점 외국인", None)
    print(f"[OK] DEPTFRN 갱신 · {months[0]}~{lm} · 받은 칸 {done}")


if __name__ == "__main__":
    main()
