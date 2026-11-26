# -*- coding: utf-8 -*-
"""
방한 외래관광객 월별 수집 — 호텔/면세/카지노 수요 신호(호텔신라·파라다이스·GKL·롯데관광개발 등).

한국관광공사 data.go.kr API 는 폐기됐고, 데이터랩은 공식 공개 API 가 없다. 대신 데이터랩
내부 시각화 엔드포인트가 키 없이 깨끗한 최신 JSON 을 준다(치지직과 같은 성격 — 비공식이라
구조가 바뀌면 조용히 멈출 수 있음. 실패 시 기존 데이터 보존).

  POST /visualize/getTempleteData.do  ·  BASE_YM1~BASE_YM2 기간
  · NAT_08_01_004    '방한 외래관광객 추이' — list[].PSON_NUM = 그 달 공식 총계(한국관광통계 · 2015-01~)
  · TS_01_16_004_NEW 입국 공항·항구별 — TOU_NUM1~13(인천공항·김해·김포·제주공항·기타공항 5개·부산항·인천항·제주항·기타항구)
  · NAT_08_01_021    '글로벌 방한관광객' — 기간 합 국적별(총계 줄 + 국적 205개 · 전년 같은 기간 대비 PER) → 한 달씩 부른다

⚠ 2026-10-29 전엔 TS_01_16_004_NEW 의 TOU_NUM1 을 '총계'로 읽었다 — 실제로는 **인천공항 입국분만**(총계의 61%)이었다.
  13칸을 다 더하면 공식 총계와 한 명까지 맞는다(2026-09 2,062,042). 그래서 total = 공식 총계, ports.icn = 옛 값.

외국인 신용카드 관광소비(2026-11-26 추가 · 사용자 "문체부 10월 동향 나왔는데 이거 쌓는 데 있지 않나"):
  · NAT_11_02_001 (국가별 방한현황(빅데이터) 페이지 · tarCd 없이 = 전국) — TOU_NUM 원 · PREV_TOU_NUM 전년 같은 달 · 2018-01~.
    문체부 보도자료의 '관광 분야 카드 소비액' 합계와 억 원까지 같다(2026-10 20,843억 · 2025 1~10월 12조 2,476억).
    방한객 총계보다 먼저 올라온다(2026-10분: 11/26 아침에 카드는 있고 총계는 0).
  · 업종별 금액(쇼핑·숙박·의료웰니스·식음료)은 데이터랩이 전국 단위로 안 준다 — 국가별은 비율(%)만(NAT_11_02_003 tarCd),
    시도별 합(LN_10_02_002)은 지역에 안 붙는 결제(숙박 예약·운송)가 빠져 전국의 78%뿐. 그래서 보도자료 표를 tourism_mcst.json 에 손으로 옮긴다.
  · flash = 데이터랩 공표 전 달의 총계(보도자료 누계 − 데이터랩 앞 달들). 그 달이 데이터랩에 올라오면 저절로 빠진다.

  python fetch_tourism.py              # 수집·기록(국적은 빠진 달 + 최근 3개월)
  python fetch_tourism.py --backfill   # 국적을 START 부터 전부 다시
  python fetch_tourism.py --dry-run    # 출력만
"""
import os, re, json, sys, time, datetime, urllib.request, urllib.parse

HTML = "public/index.html"
MCST = "tourism_mcst.json"        # 문체부 보도자료에서 손으로 옮기는 값(업종별 카드 소비 · 공표 전 총계)
CARD_START = "201801"
KST = datetime.timezone(datetime.timedelta(hours=9))
URL = "https://datalab.visitkorea.or.kr/visualize/getTempleteData.do"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
START = "201901"                  # 2019 대비를 보려고 코로나 전부터
# 입국 공항·항구 — TS_01_16_004_NEW 의 TOU_NUM 번호(2026-09 NAT_08_01_007 공항·항구별 값으로 맞춰 봤다)
PORTS = [("icn", "인천공항", [1]), ("pus", "김해공항", [2]), ("gmp", "김포공항", [3]), ("cju", "제주공항", [4]),
         ("air", "기타공항", [5, 6, 7, 8, 9]), ("bsp", "부산항", [10]), ("icp", "인천항", [11]),
         ("cjp", "제주항", [12]), ("sea", "기타항구", [13])]
# 국적 — 2025-10~2026-09 방한객 상위 12개(나머지는 그 밖 = 총계 − 12개). 코드는 데이터랩 PTL_NAT_CD.
NATS = ["CN", "JP", "TW", "US", "HK", "PH", "VN", "SG", "ID", "TH", "MY", "CA"]


def _q(qid, a, b, **extra):
    p = {"qid": qid, "BASE_YM1": a, "BASE_YM2": b,
         "srchBgngYear": a[:4], "srchEndYear": b[:4], "srchBgngMm": a[4:], "srchEndMm": b[4:],
         "srchAreaDate": "1", "adminYn": "", "NAT_CD": ""}
    p.update(extra)
    req = urllib.request.Request(URL, data=urllib.parse.urlencode(p).encode(), headers={
        "User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8")).get("list") or []


def _card_rows(end):
    """전국 외국인 신용카드 관광소비(원) — [(YYYYMM, 원, 전년 같은 달 원)] · 아직 없는 달(0)은 뺀다."""
    p = {"qid": "NAT_11_02_001", "BASE_YM1": CARD_START, "BASE_YM2": end, "srchAreaDate": "1", "tabDiv": "2"}
    req = urllib.request.Request(URL, data=urllib.parse.urlencode(p).encode(), headers={
        "User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        L = json.loads(r.read().decode("utf-8")).get("list") or []
    return sorted((x["BASE_YM"], float(x.get("TOU_NUM") or 0), float(x.get("PREV_TOU_NUM") or 0))
                  for x in L if (x.get("TOU_NUM") or 0) > 0)


def card_block(rows):
    """[(ym, 원, 전년 원)] → {months, v(억 원 · 소수 1자리)}. 전년 같은 달 값이 우리 열과 어긋나면 경고(과거 수정 공표)."""
    by = {m: v for m, v, _ in rows}
    for m, v, pv in rows:
        y = f"{int(m[:4]) - 1}{m[4:]}"
        if pv and y in by and abs(by[y] - pv) > max(1e8, pv * 0.002):
            print(f"  ⚠ 카드 {m} 의 전년값 {pv / 1e8:,.0f}억 ≠ {y} 값 {by[y] / 1e8:,.0f}억 — 과거 달이 수정됐을 수 있음")
    return {"months": [m for m, _, _ in rows], "v": [round(v / 1e8, 1) for _, v, _ in rows],
            "src": "한국관광 데이터랩 · 외국인 신용카드 관광소비액(국가별 방한현황(빅데이터) · 전국) · 억 원"}


def apply_mcst(tourism, path=MCST):
    """tourism_mcst.json(문체부 보도자료 손 입력)을 블록에 합친다 — ind(업종별 카드 소비) · flash(공표 전 총계).
    ind 는 행 합 = 전체(±3억 · 반올림) · 전체 = 데이터랩 카드 합계(±2억)인지 검산하고 어긋나면 경고만 한다."""
    if not os.path.exists(path):
        return tourism
    J = json.load(open(path, encoding="utf-8"))
    keys, ind = J.get("ind_keys") or [], J.get("ind") or {}
    card = tourism.get("card") or {}
    cby = dict(zip(card.get("months") or [], card.get("v") or []))
    if ind:
        ms = sorted(ind)
        for m in ms:
            row = ind[m]
            if abs(sum(row[:len(keys)]) - row[len(keys)]) > 3:
                print(f"  ⚠ 업종별 카드 {m}: 업종 합 {sum(row[:len(keys)]):,} ≠ 전체 {row[len(keys)]:,} — 옮겨 적기 확인")
            if m in cby and abs(cby[m] - row[len(keys)]) > 2:
                print(f"  ⚠ 업종별 카드 {m}: 보도자료 전체 {row[len(keys)]:,}억 ≠ 데이터랩 {cby[m]:,.1f}억")
        tourism["ind"] = {"keys": keys, "months": ms, "v": [[ind[m][i] for m in ms] for i in range(len(keys))],
                          "tot": [ind[m][len(keys)] for m in ms], "src": J.get("ind_src") or "문체부 보도자료"}
    # 공표 전 총계 — 데이터랩 마지막 달 바로 다음 달만 붙인다(그 달이 올라오면 이 줄은 아무 일도 안 한다)
    M, T = tourism["months"], tourism["total"]
    for m in sorted(J.get("flash") or {}):
        if m in M:
            continue
        nxt = f"{int(M[-1][:4]) + (M[-1][4:] == '12')}{(int(M[-1][4:]) % 12) + 1:02d}"
        if m != nxt:
            print(f"  ⚠ flash {m} 는 데이터랩 마지막 달({M[-1]}) 바로 다음이 아니라 건너뜀"); continue
        f = J["flash"][m]
        M.append(m); T.append(int(f["total"]))
        for row in tourism["ports"]["v"]:
            row.append(None)
        tourism["flash"] = {"ym": m, "src": f.get("src") or "문체부 보도자료"}
        print(f"  {m[:4]}.{m[4:]}: {int(f['total']):,}명 (문체부 보도자료 속보 · 데이터랩 공표 대기)")
    return tourism


def _now_ym():
    d = datetime.datetime.now(KST).date()
    return f"{d.year}{d.month:02d}"


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
        raise RuntimeError("TOURISM 삽입 기준(const LIVE)을 못 찾음")
    return html[:liv.end()] + "\n" + block + html[liv.end():]


def main():
    html = open(HTML, encoding="utf-8").read()
    old = _const(html, "TOURISM") or {}
    end = _now_ym()
    try:
        rows = [x for x in _q("NAT_08_01_004", START, end) if x.get("PSON_NUM")]
        prow = [x for x in _q("TS_01_16_004_NEW", START, end) if x.get("TOU_NUM1")]
    except Exception as e:
        print(f"[관광] 실패: {str(e)[:120]} — 기존 데이터 보존"); return
    if not rows:
        print("[관광] 빈 응답 — 보존"); return
    rows.sort(key=lambda x: x["BASE_DATE"])
    months = [x["BASE_DATE"] for x in rows]
    total = [int(x["PSON_NUM"]) for x in rows]

    pby = {x["BASE_YM"]: x for x in prow}
    ports = {"keys": [k for k, _, _ in PORTS], "names": [n for _, n, _ in PORTS],
             "v": [[(sum(int(pby[m].get(f"TOU_NUM{i}") or 0) for i in ix) if m in pby else None) for m in months]
                   for _, _, ix in PORTS]}
    for m, t in zip(months, total):          # 13칸 합 = 공식 총계인지 검산(어긋나면 칸 번호가 바뀐 것)
        if m in pby:
            s = sum(int(pby[m].get(f"TOU_NUM{i}") or 0) for i in range(1, 14))
            if abs(s - t) > 2:
                print(f"  ⚠ {m} 공항·항구 합 {s:,} ≠ 총계 {t:,} — 칸 번호 확인")

    # 국적 — 이미 있는 달은 옮기고, 빠진 달 + 최근 3개월만 새로(수정 공표 반영) · --backfill 은 전부
    on = old.get("nat") or {}
    have = {m: {c: on["v"][c][i] for c in on.get("v", {})} for i, m in enumerate(on.get("months", []))
            if on.get("v")}
    names = dict(on.get("names") or {})
    need = months if "--backfill" in sys.argv else [m for m in months if m not in have or m in months[-3:]]
    for m in need:
        try:
            L = _q("NAT_08_01_021", m, m)
        except Exception as e:
            print(f"  국적 {m} 실패: {str(e)[:80]} — 그 달은 이전 값"); continue
        if not L:
            continue
        row = {}
        for x in L:
            c = x.get("PTL_NAT_CD") or ""
            if c in NATS:
                row[c] = int(x.get("TOU_NUM") or 0)
                names[c] = x.get("NAT_NM")
        have[m] = row
        time.sleep(0.4)
    nm = [m for m in months if m in have]
    nat = {"months": nm, "names": {c: names.get(c, c) for c in NATS},
           "v": {c: [have[m].get(c) for m in nm] for c in NATS}}

    tourism = {"asOf": old.get("asOf"), "src": "한국관광 데이터랩 · 한국관광통계(법무부 출입국)",
               "months": months, "total": total, "ports": ports, "nat": nat}
    for m, t in zip(months[-3:], total[-3:]):
        print(f"  {m[:4]}.{m[4:]}: {t:,}명")
    lm = months[-1]
    top = sorted(((nat["names"][c], have.get(lm, {}).get(c) or 0) for c in NATS), key=lambda x: -x[1])[:5]
    print("  " + lm + " 국적 상위: " + " · ".join(f"{n} {v:,}" for n, v in top))

    # 외국인 신용카드 관광소비 — 실패하면 이전 값을 그대로 둔다(총계·국적 수집과 따로)
    try:
        crow = _card_rows(end)
        tourism["card"] = card_block(crow) if crow else old.get("card")
        if crow:
            c = tourism["card"]
            print(f"  카드 관광소비 {c['months'][-1][:4]}.{c['months'][-1][4:]}: {c['v'][-1]:,.1f}억 · {len(c['months'])}개월")
    except Exception as e:
        print(f"  카드 관광소비 실패: {str(e)[:100]} — 이전 값 유지")
        tourism["card"] = old.get("card")
    if not tourism.get("card"):
        tourism.pop("card", None)
    apply_mcst(tourism)
    lm = tourism["months"][-1]

    if "--dry-run" in sys.argv:
        print(f"(dry-run · {len(months)}개월 · 최근 {lm} · 국적 {len(nm)}개월)"); return
    same = {k: v for k, v in tourism.items() if k != "asOf"} == {k: v for k, v in old.items() if k != "asOf"}
    if same:
        print("[관광] 변동 없음 — SKIP"); return
    tourism["asOf"] = datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    open(HTML, "w", encoding="utf-8").write(_put(html, "TOURISM", tourism))
    print(f"[OK] TOURISM 갱신 · {len(months)}개월 · 국적 {len(nm)}개월")


if __name__ == "__main__":
    main()
