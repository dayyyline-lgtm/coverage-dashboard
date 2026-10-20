# -*- coding: utf-8 -*-
"""K뷰티 채널 모델용 월평균 환율 (2026-10-20) — 원화 / 외화 1단위.

ECB 기준환율(무료·키 없음)의 EUR 대비 월평균으로 교차환율을 만든다:  원/X = (원/EUR) ÷ (X/EUR).
· 지난달까지 = 월평균 시계열(M.*.EUR.SP00.A) · 이번 달 = 그날까지의 일별 평균(D.*) — 월이 끝나면 다음 회차가 월평균으로 갈아 끼운다.
· 러너(GitHub Actions)에서 돈다 — 클라우드 세션 셸은 ECB 에 닿지 않는다(허용 목록).
· 출력 kbeauty/data/fx_month.csv  ym,USD,GBP,EUR,JPY,CAD   (JPY 는 1엔당 원)
  값이 바뀐 게 없으면 파일을 안 쓴다(빌드 한도). 실패하면 옛 파일을 그대로 두고 종료코드 1.
"""
import csv
import datetime as dt
import io
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "fx_month.csv"
CUR = ["USD", "GBP", "JPY", "CAD", "KRW"]
START = "2023-01"
API = "https://data-api.ecb.europa.eu/service/data/EXR/{f}.{c}.EUR.SP00.A?startPeriod={s}&format=csvdata"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "coverage-dashboard/kbeauty fx", "Accept": "text/csv"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8")


def series(freq, start):
    """{통화: {기간: 값}} — 값은 통화/EUR"""
    txt = get(API.format(f=freq, c="+".join(CUR), s=start))
    out = {}
    for row in csv.DictReader(io.StringIO(txt)):
        c, p, v = row.get("CURRENCY"), row.get("TIME_PERIOD"), row.get("OBS_VALUE")
        if c and p and v:
            out.setdefault(c, {})[p] = float(v)
    return out


def build():
    m = series("M", START)
    today = (dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(hours=9)).date()      # 러너는 UTC — 달은 KST 로 끊는다
    cur_ym = today.strftime("%Y-%m")
    rows = {}
    for ym in sorted(m.get("KRW", {})):
        r = {"EUR": m["KRW"][ym]}
        for c in ("USD", "GBP", "JPY", "CAD"):
            if ym in m.get(c, {}):
                r[c] = m["KRW"][ym] / m[c][ym]
        rows[ym] = r
    # 월평균이 아직 안 나온 달(이번 달 · 월초 며칠은 지난달도) — 일별 평균. days 칸 = 평균 낸 영업일 수
    last = max(rows) if rows else START
    y, mo = map(int, last.split("-"))
    nxt = f"{y + (mo == 12)}-{(mo % 12) + 1:02d}"
    if nxt <= cur_ym:
        d = series("D", nxt + "-01")
        for ym in sorted({x[:7] for x in d.get("KRW", {})}):
            days = sorted(x for x in d["KRW"] if x.startswith(ym))
            r = {"EUR": sum(d["KRW"][x] for x in days) / len(days)}
            for c in ("USD", "GBP", "JPY", "CAD"):
                kr = [d["KRW"][x] / d[c][x] for x in days if x in d.get(c, {})]
                if kr:
                    r[c] = sum(kr) / len(kr)
            r["_days"] = len(days)
            rows[ym] = r
    return rows


def main():
    try:
        rows = build()
    except Exception as e:                                  # noqa: BLE001
        print("[FX] 실패:", e)
        return 1
    if not rows:
        print("[FX] 빈 응답")
        return 1
    lines = ["ym,USD,GBP,EUR,JPY,CAD,days"]
    for ym in sorted(rows):
        r = rows[ym]
        lines.append(",".join([ym] + [f"{r[c]:.4f}" if c in r else "" for c in ("USD", "GBP", "EUR", "JPY", "CAD")] + [str(r.get("_days", ""))]))
    text = "\n".join(lines) + "\n"
    old = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
    if text == old:
        print(f"[FX] 변동 없음 · {len(rows)}개월")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    last = sorted(rows)[-1]
    print(f"[FX] {len(rows)}개월 · 마지막 {last} USD {rows[last].get('USD', 0):.1f} · EUR {rows[last].get('EUR', 0):.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
