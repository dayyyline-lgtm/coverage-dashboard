# -*- coding: utf-8 -*-
"""아마존 K뷰티 아침 메시지 — 7개국 뷰티 Top100 안 한국 브랜드 (2026-10-18 · PC 트래커의 '💄 아마존 K뷰티'를 대신한다).

  python lists_report.py              오늘 메시지를 화면에 찍기만 한다
  python lists_report.py --send       텔레그램으로 보낸다(환경변수 TELEGRAM_BOT_TOKEN · TELEGRAM_CHAT_ID). 하루 한 번 —
                                      data/lists/report_sent.json 에 보낸 날을 적고, 같은 날 다시 부르면 안 보낸다(--force 는 무시).
  python lists_report.py --date 2026-10-19   그날 기준으로 만든다(점검용)

규칙 (사용자 2026-10-18 "수집 실패가 계속 뜨는 게 싫다")
  · 나라마다 **그 나라를 받은 직전 날**과 비교한다. 하루 빠진 나라를 전날과 비교해 가짜 편입·이탈이 쏟아지던 트래커의 버그를 되풀이하지 않는다.
  · 하루 빠진 나라는 조용히 넘어간다. **이틀 연속** 못 받은 나라만 맨 아래 한 줄.
  · 2쪽을 못 받은 날(끝 순위 95 미만)은 그 나라를 50위까지만 비교한다.
  · 오늘 받은 나라가 하나도 없으면 보내지 않는다(아침 수집 자체가 안 돈 날은 07:40 점검이 휴대폰으로 알린다).
"""
import argparse
import datetime
import json
import os
import pathlib
import sys
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lists as LS  # noqa: E402

SENT = LS.DATA / "report_sent.json"
FLAG = {"US": "🇺🇸", "UK": "🇬🇧", "DE": "🇩🇪", "FR": "🇫🇷", "IT": "🇮🇹", "ES": "🇪🇸", "JP": "🇯🇵"}
NAME = {"US": "미국", "UK": "영국", "DE": "독일", "FR": "프랑스", "IT": "이탈리아", "ES": "스페인", "JP": "일본"}
WD = "월화수목금토일"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def md(d):
    x = datetime.date.fromisoformat(d)
    return f"{x.month}/{x.day}"


def short(t, brand):
    """긴 아마존 제목 → 브랜드 뒤 앞부분 34자"""
    s = (t or "").strip()
    if brand and s.lower().startswith(brand.lower()):
        s = s[len(brand):].lstrip(" -:|,")
    for sep in (" | ", " - ", ", ", " ("):
        if sep in s[8:]:
            s = s[:8 + s[8:].index(sep)]
    return (s[:34].rstrip() + "…") if len(s) > 35 else s


def build(today):
    cfg = LS.load_json(LS.CFG, None)
    by_name = {b[0]: b for b in cfg["brands"]}
    comps = cfg.get("companies", {})
    dm = LS.load_days()
    pos = LS.load_positions()
    titles = {x[0]: x[2] for x in LS.load_json(LS.MASTER, {"list": []})["list"]}
    ok = lambda d, mk: (d, mk) in dm and dm[(d, mk)]["status"] in ("ok", "part")
    have = [mk for mk in LS.MK if ok(today, mk)]
    if not have:
        return None
    dates = sorted({d for d, _ in dm})

    def prev_of(mk):
        return next((d for d in reversed(dates) if d < today and ok(d, mk)), None)

    def co_of(b):
        row = by_name.get(b)
        co = row[2] if row else ""
        st = (row[3] if row else "") or comps.get(co, {}).get("st", "")
        return co, st

    lines_mk, news, lost = [], [], []
    tot_now, tot_prev = {}, {}             # 회사(상장·상장준비) 또는 브랜드 → 개수 (오늘·직전 둘 다 받은 나라만)
    cmp_mk = []
    for mk in LS.MK:
        if mk not in have:
            continue
        p = prev_of(mk)
        cut = 100 if dm[(today, mk)]["maxr"] >= 95 else 50
        if p:
            cut = min(cut, 100 if dm[(p, mk)]["maxr"] >= 95 else 50)
        cur = [x for x in pos.get((today, mk), []) if x[0] <= cut]
        n = len(cur)
        txt = f"{FLAG[mk]} {NAME[mk]} {n}"
        if p:
            old = [x for x in pos.get((p, mk), []) if x[0] <= cut]
            d = n - len(old)
            txt += f"({d:+d})" if d else ""
            if p != (datetime.date.fromisoformat(today) - datetime.timedelta(days=1)).isoformat():
                txt += f"[vs {md(p)}]"
            if cut < 100:
                txt += "[50위까지]"
            ca, oa = {x[1] for x in cur}, {x[1] for x in old}
            news += [(mk, r, a, b) for r, a, b in cur if a not in oa]
            lost += [(mk, r, a, b) for r, a, b in old if a not in ca]
            cmp_mk.append(mk)
            for src, dst in ((cur, tot_now), (old, tot_prev)):
                for r, a, b in src:
                    co, st = co_of(b)
                    k = ("co", co) if st in ("L", "P") and co else ("br", b)
                    dst[k] = dst.get(k, 0) + 1
        lines_mk.append(txt)

    wd = WD[datetime.date.fromisoformat(today).weekday()]
    out = [f"💄 아마존 K뷰티 · {md(today)}({wd})", "", "각국 뷰티 Top100 안 한국 브랜드 제품 수 (직전 수집 대비)"]
    out.append(" · ".join(lines_mk[:4]))
    if lines_mk[4:]:
        out.append(" · ".join(lines_mk[4:]))
    if cmp_mk:
        def fmt(kind):
            ks = sorted({k for k in set(tot_now) | set(tot_prev) if k[0] == kind},
                        key=lambda k: (-tot_now.get(k, 0), -tot_prev.get(k, 0), k[1]))
            parts = []
            for k in ks:
                a, b = tot_now.get(k, 0), tot_prev.get(k, 0)
                if not a and not b:
                    continue
                parts.append(f"{k[1]} {a}" + (f"({a - b:+d})" if a != b else ""))
            return parts
        miss = [NAME[m] for m in LS.MK if m not in cmp_mk]
        scope = f"{len(cmp_mk)}개국 합" + (f" · {'·'.join(miss)} 빠짐" if miss else "")
        co = fmt("co")
        if co:
            out += ["", f"상장사·상장 준비 ({scope})", " · ".join(co[:10])]
        br = fmt("br")
        if br:
            out += ["", "그 밖 브랜드", " · ".join(br[:10]) + (f" 외 {len(br) - 10}" if len(br) > 10 else "")]

    def item(mk, r, a, b, tag):
        return f"  {FLAG[mk]} {tag}{r} {b} {short(titles.get(a, ''), b)}"
    listed_first = lambda x: (0 if co_of(x[3])[1] in ("L", "P") else 1, LS.MK.index(x[0]), x[1])
    if news:
        out += ["", "🆕 신규 편입"] + [item(*x, "#") for x in sorted(news, key=listed_first)[:12]]
        if len(news) > 12:
            out.append(f"  외 {len(news) - 12}개")
    if lost:
        out += ["", "⛔ 이탈"] + [item(*x, "전 #") for x in sorted(lost, key=listed_first)[:12]]
        if len(lost) > 12:
            out.append(f"  외 {len(lost) - 12}개")
    if cmp_mk and not news and not lost:
        out += ["", "편입·이탈 없음"]
    if not cmp_mk:
        out += ["", "첫 수집 — 내일부터 편입·이탈이 표시됩니다"]

    # 이틀 연속 못 받은 나라만
    y = (datetime.date.fromisoformat(today) - datetime.timedelta(days=1)).isoformat()
    gaps = []
    for mk in LS.MK:
        if mk in have or ok(y, mk):
            continue
        last = prev_of(mk)
        if last is None and not any(d < today and (d, mk) in dm for d in dates):
            continue                        # 한 번도 시도 안 한 나라(수집 시작 전)는 알리지 않는다
        gaps.append(f"{NAME[mk]}" + (f"(마지막 {md(last)})" if last else ""))
    if gaps:
        out += ["", "⚠️ 이틀째 못 받음: " + ", ".join(gaps)]
    return "\n".join(out)


def send(text):
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not (tok and chat):
        print("텔레그램 토큰·챗ID 가 없다 — 보내지 않는다")
        return False
    data = urllib.parse.urlencode({"chat_id": chat, "text": text, "disable_web_page_preview": "true"}).encode()
    with urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data=data), timeout=30) as r:
        return r.status == 200


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--date")
    a = ap.parse_args()
    today = a.date or LS.kst_now().strftime("%Y-%m-%d")
    text = build(today)
    if not text:
        print(f"{today}: 받은 나라가 없다 — 메시지 없음")
        return 0
    print(text)
    if not a.send:
        return 0
    st = LS.load_json(SENT, {})
    if st.get("date") == today:
        print(f"\n{today} 메시지는 이미 보냈다({st.get('at')}) — 다시 안 보낸다")
        return 0
    if send(text):
        SENT.write_text(json.dumps({"date": today, "at": LS.kst_now().strftime("%Y-%m-%d %H:%M")}, ensure_ascii=False) + "\n", encoding="utf-8")
        print("\n텔레그램 발송 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
