# -*- coding: utf-8 -*-
"""달바글로벌 러시아 — 얀덱스 Wordstat 키워드 탐침 (2026-09-21, 일회성).

로컬 PC 에는 YANDEX_API_KEY 가 없고 GitHub Actions secrets 에만 있다. 그래서 키워드 후보를
러너에서 돌려 결과를 diag/yandex_probe.json 에 커밋한다(diag_probe.py 와 같은 방식).

무엇을 가르려는가:
  ① 표기 — 달바는 러시아에서 라틴(dalba·d'alba)·키릴(дальба·д'альба·далба)이 섞여 쓰인다.
     어느 쪽이 실제 검색량을 들고 있는지 모르면 KT&G 'esse' 처럼 엉뚱한 것을 셀 수 있다.
  ② 크기 — 얀덱스는 절대 검색수를 주므로 경쟁 K뷰티 브랜드와 '누가 더 큰가'를 진짜로 비교한다.
  ③ 지역 — 러시아(225) 전국과 CIS(카자흐 159·벨라루스 149·우즈벡 171)를 따로 센다.

⚠ 일반명사 오염 검사가 핵심이다. 'alba' 는 라틴어·이탈리아어로 '새벽'이고 러시아어권에도
   Alba 브랜드가 여럿 있다(아로마티카·달바 구글 때 두 번 밟은 함정). 절대수가 큰 표기라고
   바로 쓰면 안 되고, 크기가 경쟁 브랜드 대비 말이 되는지까지 봐야 한다.
"""
import os, json, datetime, sys, time
sys.path.insert(0, ".")
import requests

KEY = os.environ.get("YANDEX_API_KEY", "")
FOLDER = os.environ.get("YANDEX_FOLDER_ID", "")
DYN = "https://searchapi.api.cloud.yandex.net/v2/wordstat/dynamics"
TOP = "https://searchapi.api.cloud.yandex.net/v2/wordstat/topRequests"
KST = datetime.timezone(datetime.timedelta(hours=9))

# 얀덱스 geobase. 달바가 실제로 팔리는 곳 — 러시아 + CIS.
REGIONS = {"러시아": "225", "카자흐": "159", "벨라루스": "149", "우즈벡": "171"}

# ① 표기 후보 (러시아 전국)
SPELLINGS = ["dalba", "d'alba", "дальба", "д'альба", "далба",
             "дальба спрей", "dalba спрей", "спрей с белым трюфелем"]
# ② 경쟁 브랜드 — 크기가 말이 되는지 보는 자
RIVALS = ["medicube", "cosrx", "laneige", "round lab", "beauty of joseon", "медикуб"]


def dynamics(phrase, freq="week", n=52, regions=None):
    end = datetime.date.today()
    end = end - datetime.timedelta(days=end.weekday() + 1)          # 직전 일요일
    start = end - datetime.timedelta(days=n * 7 - 1)                # 월요일
    ts = lambda d: d.strftime("%Y-%m-%dT00:00:00Z")
    body = {"folderId": FOLDER, "phrase": phrase, "period": "PERIOD_WEEKLY",
            "fromDate": ts(start), "toDate": ts(end)}
    if regions:
        body["regions"] = [str(r) for r in regions]
    r = requests.post(DYN, json=body, timeout=30,
                      headers={"Authorization": f"Api-Key {KEY}"})
    if r.status_code != 200:
        return {"err": f"{r.status_code}: " + " ".join(r.text.split())[:200]}
    rows = r.json().get("results") or []
    vals = []
    for it in rows:
        try:
            vals.append(int(float(it.get("count", 0))))
        except (TypeError, ValueError):
            pass
    if not vals:
        return {"err": "시계열 없음", "raw": str(r.json())[:200]}
    nz = [v for v in vals if v]
    return {"n": len(vals), "nz": len(nz), "max": max(vals), "min": min(vals),
            "avg": round(sum(vals) / len(vals)), "last4": vals[-4:],
            "first": rows[0].get("date", "")[:10], "last": rows[-1].get("date", "")[:10]}


def top_requests(phrase, regions=None):
    """연관 검색어 — 일반명사 오염을 이걸로 가른다.
       'alba' 계열이면 이탈리아 지명·다른 브랜드가 상위에 뜬다."""
    # numPhrases 는 필수다 — 없으면 400 "Value must be in the range of 1 to 2000".
    body = {"folderId": FOLDER, "phrase": phrase, "numPhrases": 15}
    if regions:
        body["regions"] = [str(r) for r in regions]
    r = requests.post(TOP, json=body, timeout=30,
                      headers={"Authorization": f"Api-Key {KEY}"})
    if r.status_code != 200:
        return {"err": f"{r.status_code}: " + " ".join(r.text.split())[:200]}
    d = r.json()
    out = {}
    for k in ("topRequests", "associations", "includingPhrases", "similarPhrases"):
        rows = d.get(k)
        if isinstance(rows, list) and rows:
            out[k] = [{"p": x.get("phrase", ""), "c": x.get("count", x.get("value", ""))}
                      for x in rows[:12]]
    return out or {"raw": str(d)[:400]}


def main():
    out = {"t": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST"),
           "key": bool(KEY and FOLDER), "spellings": {}, "rivals": {},
           "regions": {}, "top": {}}
    if not out["key"]:
        out["err"] = "YANDEX_API_KEY / YANDEX_FOLDER_ID 없음"
        json.dump(out, open("diag/yandex_probe.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("키 없음"); return

    print("① 표기 후보 (러시아 225 · 주별 52)")
    for kw in SPELLINGS:
        out["spellings"][kw] = dynamics(kw, regions=["225"])
        print(f"   {kw:28s} {out['spellings'][kw]}")
        time.sleep(0.4)

    print("②' 오염 후보 — alba 계열 단독 크기")
    for kw in ["alba", "альба", "d alba"]:
        out["spellings"][kw] = dynamics(kw, regions=["225"])
        print(f"   {kw:28s} {out['spellings'][kw]}")
        time.sleep(0.4)

    print("② 경쟁 브랜드 (러시아 225)")
    for kw in RIVALS:
        out["rivals"][kw] = dynamics(kw, regions=["225"])
        print(f"   {kw:28s} {out['rivals'][kw]}")
        time.sleep(0.4)

    # 표기 중 가장 큰 것으로 지역·연관어를 본다
    best = max(((k, v) for k, v in out["spellings"].items() if k in SPELLINGS),
               key=lambda kv: kv[1].get("avg", 0) if "err" not in kv[1] else -1)[0]
    out["best"] = best
    print(f"③ 지역별 — 기준 표기 {best!r}")
    for name, rid in REGIONS.items():
        out["regions"][name] = dynamics(best, regions=[rid])
        print(f"   {name:8s} {out['regions'][name]}")
        time.sleep(0.4)

    print("④' topRequests / regions 원본 — 어떤 필드가 오는지부터 본다")
    out["raw"] = {}
    for kw in ["dalba", "d'alba", "medicube", "дальба"]:
        for ep, body in (("topRequests", {"folderId": FOLDER, "phrase": kw, "numPhrases": 20,
                                          "regions": ["225"]}),
                         ("regions",     {"folderId": FOLDER, "phrase": kw})):
            try:
                r = requests.post(f"https://searchapi.api.cloud.yandex.net/v2/wordstat/{ep}",
                                  json=body, timeout=30,
                                  headers={"Authorization": f"Api-Key {KEY}"})
                out["raw"][f"{kw}|{ep}"] = (r.json() if r.status_code == 200
                                            else {"err": f"{r.status_code} " + " ".join(r.text.split())[:200]})
            except Exception as e:
                out["raw"][f"{kw}|{ep}"] = {"err": str(e)[:150]}
            print(f"   {kw}|{ep}: {json.dumps(out['raw'][f'{kw}|{ep}'], ensure_ascii=False)[:500]}")
            time.sleep(0.4)

    print("⑤ 구매의도·제품 구문 — 브랜드 신호인지 가르는 자")
    for kw in ["купить dalba", "dalba крем", "dalba сыворотка", "dalba отзывы",
               "medicube отзывы", "dalba wildberries"]:
        out["spellings"][kw] = dynamics(kw, regions=["225"])
        print(f"   {kw:28s} {out['spellings'][kw]}")
        time.sleep(0.4)

    print("④ 연관 검색어 (오염 검사)")
    # ⚠ 'alba' 는 이탈리아 지명·와인·다른 브랜드라 러시아에서도 쓰인다.
    #   d'alba 가 dalba 의 2.8배인 게 브랜드 신호인지 'alba' 오염인지를 여기서 가른다.
    for kw in [best, "dalba", "дальба", "alba"]:
        if kw in out["top"]:
            continue
        out["top"][kw] = top_requests(kw, regions=["225"])
        print(f"   {kw}: {json.dumps(out['top'][kw], ensure_ascii=False)[:400]}")
        time.sleep(0.4)

    os.makedirs("diag", exist_ok=True)
    json.dump(out, open("diag/yandex_probe.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("→ diag/yandex_probe.json")


if __name__ == "__main__":
    main()
