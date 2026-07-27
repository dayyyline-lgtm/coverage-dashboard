# -*- coding: utf-8 -*-
"""
텔레그램 전송 헬퍼 — 대시보드 알림/다이제스트를 폰으로 쏜다.

토큰·챗ID 우선순위: 환경변수(GitHub Actions) > secrets_local.py(로컬)
  TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID

토큰이 없으면 조용히 아무것도 안 하고 False 를 돌려준다(수집 파이프라인을 막지 않게).
"""
import os, json, urllib.request, urllib.parse, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    from secrets_local import TELEGRAM_BOT_TOKEN as _T, TELEGRAM_CHAT_ID as _C
except Exception:
    _T = _C = ""
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", _T)
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", _C)


def configured():
    return bool(BOT_TOKEN and CHAT_ID)


def send(text, chat_id=None, parse_mode="HTML", silent=False):
    """텔레그램 sendMessage. 성공 True / 미설정·실패 False.
       parse_mode=HTML 이라 <b> 굵게, <code> 등만 쓰면 된다(마크다운 이스케이프 지옥 회피)."""
    cid = chat_id or CHAT_ID
    if not (BOT_TOKEN and cid):
        print("[telegram] 토큰/챗ID 미설정 — 전송 생략")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": cid, "text": text[:4096], "parse_mode": parse_mode,
        "disable_web_page_preview": "true", "disable_notification": "true" if silent else "false",
    }).encode()
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20)
        ok = json.loads(r.read()).get("ok", False)
        print("[telegram] 전송", "성공" if ok else "실패")
        return ok
    except Exception as e:
        print("[telegram] 전송 실패:", str(e)[:120])
        return False


def get_chat_id():
    """봇에게 아무 메시지나 보낸 뒤 이걸 실행하면 chat_id 를 알려준다(최초 설정용)."""
    if not BOT_TOKEN:
        print("먼저 TELEGRAM_BOT_TOKEN 을 secrets_local.py 에 넣으세요."); return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    d = json.loads(urllib.request.urlopen(url, timeout=20).read())
    seen = {}
    for u in d.get("result", []):
        msg = u.get("message") or u.get("channel_post") or {}
        ch = msg.get("chat") or {}
        if ch.get("id"):
            seen[ch["id"]] = ch.get("title") or ch.get("username") or ch.get("first_name") or ""
    if not seen:
        print("업데이트가 없습니다. 봇에게 먼저 아무 메시지나 보낸 뒤 다시 실행하세요.")
    for cid, nm in seen.items():
        print(f"  chat_id = {cid}   ({nm})   ← 이걸 TELEGRAM_CHAT_ID 로 넣으세요")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "chatid":
        get_chat_id()
    elif len(sys.argv) > 1 and sys.argv[1] == "test":
        send("✅ <b>커버리지 대시보드</b> 텔레그램 연결 테스트 성공")
    else:
        print("사용법: python telegram_send.py chatid   |   python telegram_send.py test")
