# -*- coding: utf-8 -*-
"""사전 밖 브랜드 — 일정 규모를 넘으면 사용자에게 묻는다 (2026-10-23 · 사용자 "사전에 없는 브랜드 일정규모 이상 되면 나한테 물어봐").

  python unknown_check.py <덤프 파일들>   아침 수집에서 ingest.py · lists.py 다음에 같은 덤프로 부른다
  python unknown_check.py                 덤프 없이 쌓인 기록만으로 다시 판정(점검용)
  python unknown_check.py --decide "이름=무시"   사용자 답을 적는다(무시 = 다시 안 묻는다 · 추가 = config.json 에 넣었다는 표시)

무엇을 보나
  · 덤프의 U 줄 = 제목에 Korean·K-beauty 가 들어갔는데 브랜드 사전(config.json brands)에 없는 상품.
    세부 카테고리(AMZSUB · U|ASIN|카테고리|순위|제목) · 7개국 뷰티 전체(AMZL · U|나라|ASIN|순위|제목).
  · 날마다 그날 U 줄을 data/subcat/unknown_daily.csv 에 쌓는다(unknown.csv 는 처음 본 날 한 줄뿐이라 규모를 못 잰다).
  · 브랜드 = 제목 첫 낱말(앞 꼬리표 [..] 를 떼고 · 세 글자 이하면 두 낱말). Korean·Original 같은 일반어로 시작하면 브랜드를 모른다 — 안 묻는다.

규모 기준 (하나라도 넘으면 묻는다)
  A. 7개국 중 한 나라라도 뷰티 '전체' Top100 에 든 적 있다
  B. 미국 세부 카테고리에서 SKU 3개 이상
  C. 미국 세부 카테고리 Top10 에 최근 7일 중 4일 이상(일별 기록이 쌓인 뒤부터)
  한 번 물은 브랜드는 data/subcat/unknown_asked.json 에 적고 다시 안 묻는다(답이 '무시'든 아직 없든).
출력: '[새 브랜드 확인] …' 줄 — 아침 보고에 그대로 붙이고 사용자에게 묻는다. 없으면 아무것도 안 찍는다.
"""
import csv
import datetime
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE.parent / "data"
DAILY = DATA / "subcat" / "unknown_daily.csv"
ASKED = DATA / "subcat" / "unknown_asked.json"
UNK_SUB = DATA / "subcat" / "unknown.csv"
UNK_LST = DATA / "lists" / "unknown.csv"

GENERIC = {"korean", "k-beauty", "kbeauty", "original", "exfoliating", "water", "enhancing", "the", "premium", "natural",
           "glow", "luxe", "at", "home", "lash", "eyelash", "hair", "face", "body", "new", "2", "3", "4", "5", "6", "10", "12", "a"}

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def brand_key(title):
    m = re.match(r"^\s*[\[【]([A-Za-z][A-Za-z.&' -]{1,20})[\]】]", title or "")   # [Mizon] 처럼 꼬리표가 브랜드인 경우
    if m and not re.search(r"pack|set|count|pcs|official|公式", m.group(1), re.I):
        name = m.group(1).strip()
        return re.sub(r"[^a-z0-9]", "", name.lower()) or None, name
    t = re.sub(r"^\s*(\[[^\]]*\]|【[^】]*】|\([^)]*\))\s*", "", title or "").strip()
    w = re.findall(r"[A-Za-zÀ-ÿĀ-ž0-9.:'&+]+", t)
    if not w:
        return None, None
    first = w[0].strip(".:'")
    if first.lower() in GENERIC:
        return None, None
    name = first if len(first) > 3 or len(w) < 2 else f"{first} {w[1]}"
    key = re.sub(r"[^a-z0-9à-ÿā-ž]", "", name.lower())
    return (key or None), name


def read_dumps(paths):
    rows = []                                   # (date, src, asin, where, rank, title)
    for p in paths:
        txt = pathlib.Path(p).read_text(encoding="utf-8")
        d = None
        for ln in txt.splitlines():
            f = ln.split("|")
            if f[0] in ("AMZSUB", "AMZL") and len(f) > 2:
                d = f[2]
            elif f[0] == "U" and d:
                if len(f) >= 6 and re.fullmatch(r"[A-Z]{2}", f[1]):  # AMZL: U|MK|ASIN|rank|title|crc
                    rows.append((d, "L", f[2], f[1], int(f[3]), "|".join(f[4:-1])))
                elif len(f) >= 6:                                    # AMZSUB: U|ASIN|cat|rank|title|crc
                    rows.append((d, "S", f[1], f[2], int(f[3]), "|".join(f[4:-1])))
    return rows


def load_daily():
    if not DAILY.exists():
        return []
    with DAILY.open(encoding="utf-8", newline="") as fh:
        r = csv.reader(fh)
        next(r, None)
        return [(a, b, c, d, int(e), f) for a, b, c, d, e, f in r]


def save_daily(rows):
    rows = sorted(set(rows))
    with DAILY.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "src", "asin", "where", "rank", "title"])
        w.writerows(rows)


def backfill():
    """일별 기록이 시작되기 전 것 — unknown.csv(처음 본 날 한 줄)를 관측 하나로 센다"""
    out = []
    if UNK_SUB.exists():
        for r in csv.DictReader(UNK_SUB.open(encoding="utf-8")):
            out.append((r["date"], "S", r["asin"], r["cat"], int(r["rank"]), r["title"]))
    if UNK_LST.exists():
        for r in csv.DictReader(UNK_LST.open(encoding="utf-8")):
            out.append((r["date"], "L", r["asin"], r["market"], int(r["rank"]), r["title"]))
    return out


def known_keys():
    """사전에 이미 있는 브랜드(패턴) — 덤프 쪽 매칭이 놓친 것까지 다시 묻지 않게"""
    try:
        cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    except Exception:
        return set()
    ks = set()
    for b in cfg.get("brands", []):
        for pat in [b[0]] + list(b[1] if len(b) > 1 else []):
            k = re.sub(r"[^a-z0-9à-ÿā-ž]", "", str(pat).lower())
            if k:
                ks.add(k)
    return ks


def judge(rows, today):
    since = (datetime.date.fromisoformat(today) - datetime.timedelta(days=6)).isoformat()
    g = {}
    for d, src, asin, where, rank, title in rows:
        k, name = brand_key(title)
        if not k:
            continue
        b = g.setdefault(k, {"name": name, "sku": set(), "mk": set(), "top10": set(), "best": 999, "ex": title})
        if src == "S":
            b["sku"].add(asin)
            if rank <= 10 and d >= since:
                b["top10"].add(d)
            b["best"] = min(b["best"], rank)
        else:
            b["mk"].add(where)
    hit = {}
    for k, b in g.items():
        why = []
        if b["mk"]:
            why.append(f"뷰티 전체 Top100({'·'.join(sorted(b['mk']))})")
        if len(b["sku"]) >= 3:
            why.append(f"세부 카테고리 SKU {len(b['sku'])}개")
        if len(b["top10"]) >= 4:
            why.append(f"세부 카테고리 Top10 최근 7일 중 {len(b['top10'])}일")
        if why:
            hit[k] = (b, why)
    return hit


def main(argv):
    if argv[:1] == ["--decide"]:
        asked = json.loads(ASKED.read_text(encoding="utf-8")) if ASKED.exists() else {}
        for a in argv[1:]:
            name, _, dec = a.partition("=")
            k, _ = brand_key(name)
            k = k or name.lower()
            asked.setdefault(k, {"name": name})["decision"] = dec or "무시"
        ASKED.write_text(json.dumps(asked, ensure_ascii=False, indent=1), encoding="utf-8")
        print("적었다:", ", ".join(argv[1:]))
        return 0

    new = read_dumps(argv)
    daily = load_daily()
    if new:
        days_new = {r[0] for r in new}
        daily = [r for r in daily if r[0] not in days_new] + new
        save_daily(daily)
    today = max([r[0] for r in daily] + [r[0] for r in backfill()] or [datetime.date.today().isoformat()])
    hit = judge(backfill() + daily, today)
    asked = json.loads(ASKED.read_text(encoding="utf-8")) if ASKED.exists() else {}
    known = known_keys()
    fresh = {k: v for k, v in hit.items() if k not in asked and k not in known}
    if not fresh:
        return 0
    for k, (b, why) in sorted(fresh.items(), key=lambda x: (-len(x[1][0]["sku"]), x[1][0]["best"])):
        print(f"[새 브랜드 확인] {b['name']} — {' · '.join(why)} · 예: {b['ex'][:60]}")
        asked[k] = {"name": b["name"], "asked": today, "why": why}
    ASKED.write_text(json.dumps(asked, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
