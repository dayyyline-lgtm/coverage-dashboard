# -*- coding: utf-8 -*-
"""서울 생활인구 — 단기체류 외국인 · 호텔·백화점이 있는 행정동의 '서울 외국인 중 비중' (2026-11-27 → const SPOP)

사용자: "백화점 외국인 체류 시간 같은 건 활용 안 하나" → 찾아 보니 서울시·KT 생활인구(단기체류 외국인)가 행정동 × 시간대 × 날짜로 있다 → "일단 붙여보자".

출처(서울 열린데이터광장 · 키 불필요 · 월별 zip):
  ① 옛 판  OA-14993 '행정동 단위 서울 생활인구(단기체류 외국인)'  2017~2026-07 (생산 끝 · seq = YYMM · infSeq 3)
  ② 새 판  OA-23018 '[단기외국인] 행정동별 서울 생활인구(250m)'   2026-06~    (seq = YYYYMM · infSeq 1 · 한 달 늦게 · 국적별 칸)
  ⚠ 새 판 zip 은 날짜별 CSV 여러 개이고, 파일마다 구분자(쉼표·세미콜론)가 다르며 동 코드 뒤에 공백이 붙는다.

무엇을 내나 — 동마다 달마다
  새벽(02~05시) 평균 인원 = 그 동에 묵는 외국인 ≈ 호텔 투숙객 · 낮(10~21시) 평균 인원 = 상권에 온 외국인
  비중 = 그 동 ÷ 서울 전체(같은 판 안에서). ⚠ 서울 전체가 2023~2026 내내 15~19만 명으로 평평하다(방한객은 크게 늘었는데) —
  KT 로밍 위주로 잡혀 수준·전년비는 성장을 낮게 잡는다(서울신라 판매 객실과 전년비 상관 −0.19). 그래서 '비중'과 분기 사이 흐름만 본다.
  검산(2026-11-27): 삼성1동 새벽 — 인터컨티넨탈 코엑스 폐관(24Q2→24Q3) −44% · 웨스틴 개관(25Q3→25Q4) +50% · GS 판매 객실과 분기 사이 변화 상관 0.99.
  옛 판 → 새 판은 같은 달인데 동마다 수준이 0.4~1.7배 다르다(집계 방식 변경) → 겹친 달(2026-06·07)의 비율로 동마다 눈금을 맞춰 잇는다.

  python fetch_spop.py           # 새 판 빠진 달만 받아 붙인다(평소 · 새 달이 없으면 요청 1건)
  python fetch_spop.py --seed    # 옛 판 2023-01~2026-07 + 새 판 전부 다시(약 250MB 내려받음 · 이 PC 에서)
  python fetch_spop.py --dry-run

중간 결과(동별 월평균 · 대상 동만)는 spop/monthly.json — 원본 재배포 금지 조건이라 원자료는 저장소에 두지 않는다.
"""
import copy, csv, datetime, io, json, os, re, sys, time, urllib.parse, urllib.request, zipfile

from collector_health import note_health

HTML = "public/index.html"
STORE = "spop/monthly.json"
KST = datetime.timezone(datetime.timedelta(hours=9))
URL = "https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?useCache=false"
START = "202301"
OLD_END = "202607"
NIGHT = {"02", "03", "04", "05"}
DAY = {f"{h:02d}" for h in range(10, 22)}
SRC = "서울 생활인구(외국인)"

# 대상 행정동 — [이름, 무엇이 있나, 종목들, 쓰는 시간대(n 새벽 · d 낮)]
DONG = {
    "11170625": ["한강로동", "서울드래곤시티(서부T&D) · 용산역", ["서부T&D"], "n"],
    "11680580": ["삼성1동", "그랜드 인터컨티넨탈·웨스틴(GS피앤엘) · 현대 무역센터 · 코엑스", ["GS피앤엘", "현대백화점"], "nd"],
    "11140580": ["장충동", "서울신라 · 신라면세 서울(호텔신라)", ["호텔신라"], "nd"],
    "11140520": ["소공동", "롯데 본점 · 롯데호텔 · 웨스틴조선", ["롯데쇼핑"], "d"],
    "11710710": ["잠실6동", "롯데 월드타워점 · 롯데월드몰", ["롯데쇼핑"], "d"],
    "11710680": ["잠실3동", "롯데 잠실점", ["롯데쇼핑"], "d"],
    "11560535": ["영등포동", "롯데 영등포점 · 신세계 타임스퀘어점", ["롯데쇼핑", "신세계"], "d"],
    "11215840": ["자양3동", "롯데 건대스타시티점", ["롯데쇼핑"], "d"],
    "11140540": ["회현동", "신세계 본점 · 신세계면세 명동", ["신세계"], "d"],
    "11650581": ["반포4동", "신세계 강남점", ["신세계"], "d"],
    "11680545": ["압구정동", "현대 압구정본점 · 갤러리아 명품관", ["현대백화점"], "d"],
    "11560540": ["여의동", "더현대 서울 · IFC몰", ["현대백화점"], "d"],
    "11410585": ["신촌동", "현대 신촌점", ["현대백화점"], "d"],
}


def _const(html, name):
    m = re.search(r"const %s\s*=\s*(\{.*?\});" % re.escape(name), html, re.S)
    return json.loads(m.group(1)) if m else None


def _put(html, name, obj):
    block = "const %s = %s;" % (name, json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
    pat = re.compile(r"const %s\s*=\s*\{.*?\};" % re.escape(name), re.S)
    if pat.search(html):
        return pat.sub(lambda m: block, html, count=1)
    at = re.search(r"const DEPTFRN\s*=\s*\{.*?\};", html, re.S) or re.search(r"const LIVE\s*=\s*\{.*?\};", html, re.S)
    if not at:
        raise RuntimeError("SPOP 삽입 기준(const DEPTFRN · LIVE)을 못 찾음")
    return html[:at.end()] + "\n" + block + html[at.end():]


def _months(a, b):
    y, m = int(a[:4]), int(a[4:])
    out = []
    while f"{y}{m:02d}" <= b:
        out.append(f"{y}{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def download(src, ym, timeout=300):
    """→ zip 바이트 · 아직 없는 달이면 None(사이트가 작은 HTML 을 준다)"""
    inf, seq, iseq = ("OA-14993", ym[2:], "3") if src == "old" else ("OA-23018", ym, "1")
    data = urllib.parse.urlencode({"infId": inf, "seq": seq, "infSeq": iseq, "seqNo": ""}).encode()
    req = urllib.request.Request(URL, data=data, headers={"Referer": "https://data.seoul.go.kr/", "User-Agent": "Mozilla/5.0"})
    err = None
    for t in range(3):
        try:
            b = urllib.request.urlopen(req, timeout=timeout).read()
            return b if b[:2] == b"PK" else None
        except Exception as e:
            err = e
            time.sleep(5 * (t + 1))
    raise err


def reduce_zip(b):
    """zip → {"tot": [새벽, 낮], "days": n, "d": {동: [새벽, 낮]}} (그달 평균 인원)"""
    z = zipfile.ZipFile(io.BytesIO(b))
    acc = {}                      # 동 → [새벽 합, 새벽 칸, 낮 합, 낮 칸]
    slots = {"n": set(), "d": set()}
    tot = [0.0, 0.0]
    days = set()
    for n in z.namelist():
        raw = z.read(n)
        for enc in ("cp949", "utf-8-sig"):
            try:
                txt = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        ls = txt.split("\n", 2)
        first = ls[1] if len(ls) > 1 else ls[0]          # 머리줄은 쉼표인데 값 줄은 세미콜론인 파일이 있다(250m 판 · 2026-08~) — 값 줄로 고른다
        sep = ";" if first.count(";") > first.count(",") else ","
        r = csv.reader(io.StringIO(txt), delimiter=sep)
        next(r, None)
        for row in r:
            if len(row) < 4:
                continue
            d, h, dong = row[0].strip(), row[1].strip().zfill(2), row[2].strip()
            try:
                v = float(row[3])
            except ValueError:
                continue
            if not d.isdigit() or len(d) != 8:
                continue
            days.add(d)
            a = acc.setdefault(dong, [0.0, 0, 0.0, 0])
            if h in NIGHT:
                a[0] += v; a[1] += 1; tot[0] += v; slots["n"].add((d, h))
            elif h in DAY:
                a[2] += v; a[3] += 1; tot[1] += v; slots["d"].add((d, h))
    if not acc:
        raise RuntimeError("행을 하나도 못 읽음")
    nn, nd = max(len(slots["n"]), 1), max(len(slots["d"]), 1)
    out = {"tot": [round(tot[0] / nn, 1), round(tot[1] / nd, 1)], "days": len(days), "d": {}}
    for k in DONG:
        a = acc.get(k)
        if a:
            out["d"][k] = [round(a[0] / max(a[1], 1), 1), round(a[2] / max(a[3], 1), 1)]
    return out


def build(S):
    """old·new → 이어 붙인 월별 블록"""
    old, new = S.get("old", {}), S.get("new", {})
    ov = [m for m in old if m in new]
    months = sorted(m for m in set(old) | set(new) if m >= START)
    def share(rec, k, j):
        x = rec["d"].get(k)
        return x[j] / rec["tot"][j] * 100 if x and rec["tot"][j] > 0 else None
    out = {}
    tot = [[], []]
    for j in (0, 1):
        kt = [old[m]["tot"][j] / new[m]["tot"][j] for m in ov if new[m]["tot"][j] > 0]
        kt = sum(kt) / len(kt) if kt else 1.0
        for m in months:
            tot[j].append(round(old[m]["tot"][j]) if m in old else round(new[m]["tot"][j] * kt))
    for k in DONG:
        o = {"s": [[], []], "p": [[], []], "k": [None, None]}
        for j in (0, 1):
            ks = [share(old[m], k, j) / share(new[m], k, j) for m in ov if share(old[m], k, j) and share(new[m], k, j)]
            kp = [old[m]["d"][k][j] / new[m]["d"][k][j] for m in ov if k in old[m]["d"] and k in new[m]["d"] and new[m]["d"][k][j] > 0]
            ks = sum(ks) / len(ks) if ks else None
            kp = sum(kp) / len(kp) if kp else None
            o["k"][j] = round(ks, 3) if ks else None
            for m in months:
                if m in old:
                    s, p = share(old[m], k, j), (old[m]["d"].get(k) or [None, None])[j]
                elif ks:
                    s0, p0 = share(new[m], k, j), (new[m]["d"].get(k) or [None, None])[j]
                    s, p = (s0 * ks if s0 else None), (p0 * kp if p0 and kp else None)
                else:
                    s = p = None
                o["s"][j].append(None if s is None else round(s, 3))
                o["p"][j].append(None if p is None else round(p))
        out[k] = o
    return months, tot, out, (max(old) if old else None), sorted(new)


def main():
    seed = "--seed" in sys.argv
    dry = "--dry-run" in sys.argv
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    S = json.load(open(STORE, encoding="utf-8")) if os.path.exists(STORE) else {"old": {}, "new": {}}
    now = datetime.datetime.now(KST)
    py, pm = (now.year, now.month - 1) if now.month > 1 else (now.year - 1, 12)
    last = f"{py}{pm:02d}"
    jobs = []
    if seed:
        jobs += [("old", m) for m in _months(START, OLD_END) if m not in S["old"]]
        jobs += [("new", m) for m in _months("202606", last) if m not in S["new"]]
    elif "--redo-new" in sys.argv:
        S["new"] = {}
        jobs += [("new", m) for m in _months("202606", last)]
    else:
        have = sorted(S["new"])
        nxt = _months(have[-1], last)[1:] if have else _months("202606", last)
        jobs += [("new", m) for m in nxt]
    got = 0
    for src, ym in jobs:
        try:
            b = download(src, ym)
        except Exception as e:
            note_health(SRC, f"{src} {ym} 내려받기 실패: {type(e).__name__}: {str(e)[:80]}")
            print(f"[생활인구] {src} {ym} 내려받기 실패 — 기존 데이터 보존: {e}")
            break
        if b is None:
            print(f"  {src} {ym}: 아직 공개 전")
            if src == "new":
                break
            continue
        try:
            rec = reduce_zip(b)
        except Exception as e:
            note_health(SRC, f"{src} {ym} 파일을 못 읽음: {str(e)[:80]}")
            print(f"[생활인구] {src} {ym} 파일을 못 읽음: {e}")
            break
        S[src][ym] = rec
        got += 1
        print(f"  {src} {ym}: {rec['days']}일 · 서울 새벽 {rec['tot'][0]:,.0f}명 · 낮 {rec['tot'][1]:,.0f}명")
    if not dry and got:
        json.dump(S, open(STORE, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    if not S["old"]:
        print("[생활인구] 옛 판이 없다 — --seed 를 먼저"); return
    months, tot, dong, oe, nw = build(S)
    html = open(HTML, encoding="utf-8").read()
    old = _const(html, "SPOP") or {}
    out = {"asOf": old.get("asOf"),
           "src": "서울 열린데이터광장 · 서울시·KT 생활인구(단기체류 외국인) — ~2026-07 OA-14993 · 2026-08~ OA-23018(250m 판 · 겹친 2026-06·07 비율로 동마다 이어 붙임)",
           "months": months, "oldEnd": oe, "tot": tot,
           "dong": {k: {"nm": v[0], "what": v[1], "co": v[2], "use": v[3], **dong[k]} for k, v in DONG.items()}}
    lm = months[-1]
    for k, v in out["dong"].items():
        print(f"  {lm} {v['nm']}: 새벽 비중 {v['s'][0][-1]}% ({v['p'][0][-1]}명) · 낮 비중 {v['s'][1][-1]}% ({v['p'][1][-1]}명) · 이음 배수 {v['k']}")
    if dry:
        print(f"(dry-run · {months[0]}~{lm})"); return
    if {k: v for k, v in out.items() if k != "asOf"} == {k: v for k, v in old.items() if k != "asOf"}:
        print("[생활인구] 변동 없음 — SKIP"); note_health(SRC, None); return
    out["asOf"] = now.strftime("%Y-%m-%d %H:%M KST")
    open(HTML, "w", encoding="utf-8").write(_put(html, "SPOP", out))
    note_health(SRC, None)
    print(f"[OK] SPOP 갱신 · {months[0]}~{lm}")


if __name__ == "__main__":
    main()
