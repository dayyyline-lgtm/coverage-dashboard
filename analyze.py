# -*- coding: utf-8 -*-
"""
급변 '왜' 추론 — Claude API(웹서치)로 각 급변 종목의 이유를 한 줄로 만든다.

digest.py 가 전일 급변 종목마다 호출한다. 로컬에 모아둔 근거
(공시·컨센 스냅샷·뉴스 헤드라인)를 먼저 주고, 뚜렷하지 않으면 web_search 로
그날의 실제 재료를 찾아 이유를 추론하게 한다.

- ANTHROPIC_API_KEY 가 없거나 SDK 미설치면 available()=False →
  digest.py 가 규칙기반(뉴스 헤드라인)으로 조용히 폴백한다. 레터는 안 끊긴다.
- 실적·공시가 재료면 컨센 대비 상회/하회로 해석. 재료 불명확하면 '뚜렷한 재료 없음'(=None).
"""
import os

try:
    import anthropic
except Exception:
    anthropic = None

MODEL = "claude-opus-5"           # 짧은 1줄이라 effort 낮춰 빠르고 싸게 돈다
NULL = "뚜렷한 재료 없음"          # 이 답이 오면 붙일 이유 없음 → None

SYSTEM = (
    "당신은 한국 주식 커버리지 애널리스트의 리서치 보조다. "
    "특정 커버 종목이 전일 크게 움직인 '이유'를 한국어 한 줄(45자 이내)로 알려준다.\n"
    "규칙:\n"
    "1) 주어진 공시·실적·컨센 정보에 뚜렷한 재료가 있으면 그것을 우선한다. "
    "실적이면 반드시 컨센 대비 상회/하회(또는 부합)를 명시한다.\n"
    "2) 로컬 근거가 약하면 web_search 로 '<종목명> 주가 급등(또는 급락) 이유 <날짜>'를 "
    "검색해 그날의 실제 재료를 확인한다.\n"
    "3) 근거를 못 찾으면 정확히 '" + NULL + "'만 출력한다. 억지로 지어내지 않는다.\n"
    "4) 출력은 이유 한 줄만. 접두사('이유:', '-')·따옴표·이모지·마침표 금지. "
    "확실치 않은 추론이면 문장 끝에 '로 추정'을 붙인다.\n"
    "예) '2Q 영업익 컨센 12% 상회' · '중국 규제 우려 부각' · '외국인 순매도 지속으로 추정'"
)


def available():
    return bool(anthropic and os.environ.get("ANTHROPIC_API_KEY"))


def _user(name, chg, cat, today, disclosures, cons, headlines):
    dr = "급등" if chg > 0 else "급락"
    return (
        f"종목: {name}" + (f" ({cat})" if cat else "") + "\n"
        f"전일 등락: {chg:+.1f}% ({dr})\n"
        f"기준일(KST): {today}\n"
        f"[공시(직전 영업일 전후)]: {disclosures or '없음'}\n"
        f"[컨센 스냅샷·밸류에이션]: {cons or '없음'}\n"
        f"[관련 뉴스 헤드라인(최근 창)]: {headlines or '없음'}\n"
        "위 종목이 왜 이렇게 움직였는지 한 줄로."
    )


def reason(name, chg, cat, today, disclosures, cons, headlines):
    """급변 1건 → 이유 한 줄. 근거 불명확이면 None. 실패해도 예외 없이 None."""
    if not available():
        return None
    try:
        client = anthropic.Anthropic().with_options(timeout=90)
        tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 3}]
        messages = [{"role": "user",
                     "content": _user(name, chg, cat, today, disclosures, cons, headlines)}]
        resp = None
        for _ in range(4):                       # 서버툴 pause_turn 대비 재개 루프
            resp = client.messages.create(
                model=MODEL,
                max_tokens=2048,
                output_config={"effort": "low"},
                system=SYSTEM,
                tools=tools,
                messages=messages,
            )
            if resp.stop_reason != "pause_turn":
                break
            messages.append({"role": "assistant", "content": resp.content})
        if resp is None or resp.stop_reason == "refusal":
            return None
        txt = "".join(b.text for b in resp.content if b.type == "text").strip()
        return _clean(txt)
    except Exception as e:
        print(f"[analyze] {name} 실패: {str(e)[:120]}")
        return None


def _clean(txt):
    if not txt:
        return None
    line = txt.splitlines()[0].strip().strip('"').strip("'").rstrip(".。 ")
    if not line or NULL in line:
        return None
    return line[:45]
