# -*- coding: utf-8 -*-
"""트렌드 레터 — '움직인 것만' 보내는 아침 다이제스트 (2026-09-02 신설).

설계(사용자와 합의):
  · 개선이 주인공, 악화는 압축 한 줄, 평평한 계열은 통째로 생략.
    '좋아지는 것만'도 검토했지만 탑툰챗 한국 꺾임을 잡은 게 정확히 악화 신호였다 —
    커버 종목의 리스크를 레터가 숨기면 안 되므로 악화도 남긴다(대신 짧게).
  · 탑툰챗(탑코미디어)은 고정 상세 — 주간 지역별 + 매출 환산 + 한국 심층 + 일일 증분.
  · SAMG(티니핑·변신로봇)·제타 비교는 싣지 않는다(사용자 지시).

판정 규칙:
  · 일별 계열: 최근 3일 '중앙값' vs 그 전 7일 '중앙값'. 평균이 아니라 중앙값인 이유 —
    하루 스파이크(쿨로아600 ▂█▁ 유형)가 평균은 끌어올리지만 중앙값은 못 움직인다.
    지속된 변화만 잡고, 첫 신호는 하루 늦게 받는 것을 감수한다.
  · 주별 계열: 최근값 vs 전주. 같은 값이 한 주 내내 반복 발송되는 걸 막으려고
    trend_letter_sent.json 에 '이 기간은 이미 알렸다'를 남긴다(새 기간이 잡힌 날만 실림).
  · 문턱 ±15%. 지수 최대가 5 미만인 소음 계열은 제외.
  · 같은 그룹에서 3개 이상 걸리면 한 줄로 묶는다(아이온2 국가별이 5줄 도배하던 것).

발송: 하루 한 통(sent 날짜로 멱등). letter.yml 이 06시 데일리 레터 직후에 부른다.
  python trend_letter.py            # 발송 (오늘 이미 보냈으면 종료)
  python trend_letter.py --dry-run  # 출력만
  python trend_letter.py --force    # 오늘 기록 무시하고 재발송
"""
import re, json, sys, datetime, statistics

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import telegram_send

HTML = "public/index.html"
STATE = "trend_letter_sent.json"
KST = datetime.timezone(datetime.timedelta(hours=9))
BAR = "▁▂▃▄▅▆▇█"
PRICE = 2050                      # 방당 매출(원) — 2Q 15~18.6억 중간값 역산. 공시마다 재보정.
THRESH = 15                       # ±%
SKIP_GROUPS = {"변신로봇 IP", "변신로봇 IP 러시아", "티니핑 국가별",
               "AI 챗봇 경쟁", "제타(경쟁)"}
NM = {"KR": "한국", "JP": "일본", "TW": "중화권", "GLOBAL": "북미"}


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def spark(vals, n=10):
    vs = [v for v in vals[-n:] if v is not None]
    if not vs:
        return ""
    lo, hi = min(vs), max(vs)
    rng = (hi - lo) or 1
    return "".join(BAR[int((v - lo) / rng * 7)] if v is not None else " " for v in vals[-n:])


def _const(html, name):
    m = re.search(r"^const %s\s*=\s*(\{.*?\});\s*$" % name, html, re.M | re.S)
    return json.loads(m.group(1)) if m else None


def _load_state():
    try:
        d = json.load(open(STATE, encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def movers_of(TR, state):
    """(chg, prod, group, spark, last, unit) 목록과, 주별 계열의 새 기간 마커."""
    out, weekly_mark = [], {}
    for gname, g in (TR.get("groups") or {}).items():
        if gname in SKIP_GROUPS:
            continue
        freq = g.get("freq", "week")
        months = g.get("months") or []
        for i, prod in enumerate(g.get("products") or []):
            sers = g.get("naver") or []
            ser = sers[i] if i < len(sers) else []
            vals = [v for v in ser if v is not None]
            if len(vals) < 8 or max(vals) < 5:
                continue
            if freq == "date":
                cur = statistics.median(vals[-3:])
                base = statistics.median(vals[-10:-3])
                unit = "주비"
            else:
                cur, base = vals[-1], vals[-2]
                unit = "전주비"
                # 주별 계열은 새 기간이 잡힌 날만 싣는다 — 같은 값 일주일 반복 방지.
                key = f"{gname}|{prod}"
                mark = f"{len(ser)}|{months[-1] if months else ''}"
                weekly_mark[key] = mark
                if state.get("weekly", {}).get(key) == mark:
                    continue
            if base <= 0:
                continue
            chg = (cur / base - 1) * 100
            if abs(chg) < THRESH:
                continue
            out.append((chg, prod, gname, spark(ser), vals[-1], unit))
    return out, weekly_mark


def bundle(items):
    """같은 그룹 3개 이상이면 한 줄로 묶는다. 반환: 표시용 문자열 목록."""
    from collections import defaultdict
    by = defaultdict(list)
    for it in items:
        by[it[2]].append(it)
    lines = []
    for gname, its in by.items():
        its.sort(key=lambda x: -abs(x[0]))
        if len(its) >= 3:
            body = " ".join(f"{esc(p)}{c:+.0f}%" for c, p, _, _, _, _ in its)
            lines.append((max(abs(i[0]) for i in its), f"▪ {esc(gname)}: {body}"))
        else:
            for c, p, g, sp, last, unit in its:
                lines.append((abs(c), f"{sp} {last:>3} {c:+4.0f}%  {esc(p)} ({esc(g)}·{unit})"))
    lines.sort(key=lambda x: -x[0])
    return [l for _, l in lines]


def toptoon_block(T):
    L = []
    sites = {x["code"]: x for x in (T.get("sites") or [])}
    tot = {}
    L.append("━━ 탑툰챗 · 탑코미디어 ━━")
    for c in ("KR", "JP", "TW", "GLOBAL"):
        rows = ((sites.get(c) or {}).get("rank") or {}).get("weekly") or []
        if not rows:
            continue
        vals = [r["tot"] for r in rows]
        chg = (vals[-1] / vals[-2] - 1) * 100 if len(vals) > 1 and vals[-2] else 0
        L.append(f"{spark(vals)} {vals[-1]:>7,} {chg:+3.0f}%  {NM[c]}")
        for r in rows:
            tot[r["k"]] = tot.get(r["k"], 0) + r["tot"]
    if tot:
        tv = [tot[k] for k in sorted(tot)]
        L.append(f"{spark(tv)} {tv[-1]:>7,} {(tv[-1]/tv[-2]-1)*100:+3.0f}%  합계 · 정점比 {(tv[-1]/max(tv)-1)*100:+.0f}%")
        L.append(f"· 매출 환산 주 {tv[-1]*PRICE/1e8:.1f}억 · 3Q 페이스 {sum(tv[-9:])*PRICE/1e8/9*13:.0f}억")
    kr = sites.get("KR") or {}
    krw = (kr.get("rank") or {}).get("weekly") or []
    bks = [r.get("bk") for r in krw if r.get("bk") is not None]
    if bks and krw:
        L.append(f"· 한국 기존캐릭터 {bks[-1]:,}({bks[-1]/krw[-1]['tot']*100:.0f}%) {spark(bks, 6)}")
    users = (kr.get("rank") or {}).get("users") or []
    if users and users[-1].get("act") is not None:
        u = users[-1]
        L.append(f"· 결제믹스 활동 {u['act']:.1f} 컬렉션 {u['col']:.1f} · 신규유저 {u['new']}/{u['n']}")
    # 일일 증분(자체집계·전원 기준) — 어제 하루 방 생성·전환율. 쌓인 날만큼만 나온다.
    day = []
    for c in ("KR", "JP", "TW", "GLOBAL"):
        rows = [h for h in ((sites.get(c) or {}).get("hist") or []) if h.get("dchat") is not None]
        if rows:
            h = rows[-1]
            cv = f"·전환{h['cv']}%" if h.get("cv") is not None else ""
            day.append(f"{NM[c]} +{h['dchat']:,}{cv}")
    if day:
        L.append("· 어제 방생성(전원): " + " / ".join(day))
    return L


def build():
    html = open(HTML, encoding="utf-8").read()
    T = _const(html, "TOPTOON") or {}
    TR = _const(html, "TREND") or {}
    state = _load_state()
    movers, weekly_mark = movers_of(TR, state)
    ups = [m for m in movers if m[0] > 0]
    dns = [m for m in movers if m[0] < 0]

    now = datetime.datetime.now(KST)
    L = [f"📈 트렌드 레터 · {now.month}/{now.day}({'월화수목금토일'[now.weekday()]})", ""]
    L += toptoon_block(T)
    L.append("")
    if ups:
        L.append(f"━━ 📈 좋아지는 것 ({len(ups)}) ━━")
        L += bundle(ups)
        L.append("")
    if dns:
        L.append(f"━━ 📉 나빠지는 것 ({len(dns)}) ━━")
        for line in bundle(dns):
            # 악화는 막대 없이 압축 — 개선과 시각적 무게를 다르게 가져간다.
            L.append(re.sub(r"^[▁▂▃▄▅▆▇█ ]+ +\d+ ", "", line))
        L.append("")
    if not ups and not dns:
        L.append("오늘은 ±15% 넘게 움직인 계열이 없습니다.")
        L.append("")
    L.append(f"— ±{THRESH}% 기준 · 평평한 계열은 생략 —")
    body = "\n".join(L)
    return body, weekly_mark


def main():
    dry = "--dry-run" in sys.argv
    force = "--force" in sys.argv
    now = datetime.datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    state = _load_state()
    if not dry and not force and state.get("date") == today:
        print(f"[SKIP] 오늘({today}) 이미 발송"); return

    body, weekly_mark = build()
    text = ("<pre>" + esc_keep(body) + "</pre>\n"
            + '<a href="https://coverage-dashboard.pages.dev/#trends">전체 차트</a>')
    if dry:
        print(body)
        print(f"\n[dry-run · 본문 {len(body)}자]")
        return
    ok = telegram_send.send(text)
    print(f"[{'OK' if ok else 'FAIL'}] 트렌드 레터 {len(body)}자")
    if ok:
        st = {"date": today, "weekly": {**state.get("weekly", {}), **weekly_mark}}
        json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def esc_keep(s):
    # 본문은 esc() 를 조각마다 이미 적용했으므로 앰퍼샌드 중복 이스케이프만 피한다.
    return s


if __name__ == "__main__":
    main()
