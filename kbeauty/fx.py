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
# 틱톡샵 미국 밖 나라 판매액을 달러로 바꿀 통화(2026-11-27 · FastMoss 나라별 샵) — 따로 fx_tt.csv 에 쓴다(fx_month.csv 를 읽는 곳의 칸 순서는 그대로)
CUR_TT = ["IDR", "MYR", "PHP", "THB", "SGD", "MXN", "BRL", "PLN", "CZK", "HUF"]
OUT_TT = HERE / "data" / "fx_tt.csv"
START = "2023-01"
API = "https://data-api.ecb.europa.eu/service/data/EXR/{f}.{c}.EUR.SP00.A?startPeriod={s}&format=csvdata"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "coverage-dashboard/kbeauty fx", "Accept": "text/csv"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8")


def series(freq, start):
    """{통화: {기간: 값}} — 값은 통화/EUR"""
    txt = get(API.format(f=freq, c="+".join(CUR + CUR_TT), s=start))
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
        for c in ("USD", "GBP", "JPY", "CAD") + tuple(CUR_TT):
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
            for c in ("USD", "GBP", "JPY", "CAD") + tuple(CUR_TT):
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
    # 틱톡샵 나라 통화(원 / 1단위 · 2026-11-27) — 베트남 동은 ECB 에 없어 phase.py 가 고정값을 쓴다
    tt = ["ym," + ",".join(CUR_TT)] + [",".join([ym] + [f"{rows[ym][c]:.6f}" if c in rows[ym] else "" for c in CUR_TT]) for ym in sorted(rows)]
    tt_text = "\n".join(tt) + "\n"
    if not OUT_TT.exists() or OUT_TT.read_text(encoding="utf-8") != tt_text:
        OUT_TT.write_text(tt_text, encoding="utf-8", newline="\n")
        print(f"[FX] 틱톡샵 나라 통화 {len(CUR_TT)}개 · {len(rows)}개월")
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
