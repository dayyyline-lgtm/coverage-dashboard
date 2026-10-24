"""게임별 한국 앱 매출순위(gamerscroll) -> index.html 의  const GRANK = {...};   (2026-10-24 신설 · 종목별 손익 모델 ISM)

카카오게임즈 모델(fetch_kgmodel.game_ranks)과 같은 페이지 — 게임마다 최근 90일 일별(구글·애플) + '월별 추이' 월평균(2025-12~).
일별은 날마다 쌓는다(540일). 화면 엔진(ism.js 의 ISM_PX.app)이 컴투스 순위→일매출 곡선(c2Rev)으로 분기 국내 매출을 세운다.
⚠ 한국 순위뿐 — 대만·일본·글로벌·웹 결제는 안 잡힌다(그래서 게임마다 계수 k 를 따로 맞춘다).
⚠ 주소는 gamerscroll 게임 DB(/ko/games/) 에서 — 아이온2·리니지 클래식은 페이지가 없다(404 · 2026-10-24).

python fetch_grank.py
"""
import datetime, json, re, sys

import fetch_kgmodel as K
from collector_health import nap, note_health

KST = datetime.timezone(datetime.timedelta(hours=9))
HTML = "public/index.html"
KEEP = 540
# (주소 조각, 표시명, 종목)
GAMES = [
    ("리니지m", "리니지M", "NC"), ("리니지2m", "리니지2M", "NC"), ("리니지w", "리니지W", "NC"),
    ("승리의-여신-니케", "승리의 여신: 니케", "시프트업"),
    ("쿠키런-킹덤", "쿠키런: 킹덤", "데브시스터즈"), ("쿠키런-오븐브레이크", "쿠키런: 오븐브레이크", "데브시스터즈"),
    ("쿠키런-모험의-탑", "쿠키런: 모험의 탑", "데브시스터즈"),
    ("배틀그라운드", "배틀그라운드 모바일", "크래프톤"),
]


def main():
    html = open(HTML, encoding="utf-8").read()
    m = re.search(r"^const GRANK = (\{.*?\});$", html, re.M | re.S)
    old = json.loads(m.group(1)) if m else {"g": {}}
    out, bad = {}, []
    for slug, nm, st in GAMES:
        prev = (old.get("g") or {}).get(slug) or {}
        d, mo = dict(prev.get("d") or {}), dict(prev.get("m") or {})
        try:
            dd, mm = K.game_ranks(slug)
            d.update(dd)
            mo.update(mm)
        except Exception as e:
            if "404" not in str(e):
                bad.append(f"{nm} {str(e)[:30]}")
        nap(0.4)
        if not d and not mo:
            continue
        keep = sorted(d)[-KEEP:]
        out[slug] = {"nm": nm, "st": st, "d": {k: d[k] for k in keep}, "m": dict(sorted(mo.items()))}
        last = keep[-1] if keep else "-"
        print(f"[게임순위] {nm:14} 일별 {len(keep)} · 월 {len(mo)} · {last} {d.get(last)}")
    note_health("게임 순위(gamerscroll)", "; ".join(bad[:3]) if len(bad) > 2 else None)
    if m and old.get("g") == out:
        print("[게임순위] 변동 없음"); return
    blk = {"asOf": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "g": out,
           "note": "gamerscroll 한국 매출순위 — d 일별 [구글, 애플] · m 월평균 [구글, 애플] · 200위 밖 = null"}
    block = "const GRANK = " + json.dumps(blk, ensure_ascii=False, separators=(",", ":")) + ";"
    if m:
        html = html[:m.start()] + block + html[m.end():]
    else:
        a = re.search(r"^const TREND = ", html, re.M)
        html = html[:a.start()] + block + "\n" + html[a.start():]
    open(HTML, "w", encoding="utf-8").write(html)
    print(f"[게임순위] GRANK 블록 갱신 {len(block) // 1024}KB")


if __name__ == "__main__":
    main()
