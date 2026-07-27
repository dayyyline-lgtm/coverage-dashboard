# -*- coding: utf-8 -*-
"""
텔레그램 전송 헬퍼 — 대시보드 알림/다이제스트를 폰으로 쏜다.

토큰·챗ID 우선순위: 환경변수(GitHub Actions) > secrets_local.py(로컬)
  TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID

토큰이 없으면 조용히 아무것도 안 하고 False 를 돌려준다(수집 파이프라인을 막지 않게).
"""
import os, json, urllib.request, urllib.parse, urllib.error, sys

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
       실패하면 이유(API 에러 본문)를 로그로 남기고, HTML 파싱 실패면 평문으로 재시도한다."""
    cid = chat_id or CHAT_ID
    if not BOT_TOKEN:
        print("[telegram] BOT_TOKEN 미설정 — 전송 생략"); return False
    if not cid:
        print("[telegram] CHAT_ID 미설정 — 전송 생략"); return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    def _post(pm):
        payload = {"chat_id": cid, "text": text[:4096], "disable_web_page_preview": "true"}
        if pm:
            payload["parse_mode"] = pm
        if silent:
            payload["disable_notification"] = "true"
        data = urllib.parse.urlencode(payload).encode()
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20)
            return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            print(f"[telegram] HTTP {e.code}: {' '.join(body.split())[:220]}")
            try:
                return json.loads(body)
            except Exception:
                return {"ok": False}
        except Exception as e:
            print(f"[telegram] 오류: {str(e)[:150]}")
            return {"ok": False}

    res = _post(parse_mode)
    if not res.get("ok") and parse_mode:          # HTML 파싱 오류 등 → 평문으로 재시도
        print("[telegram] 재시도(평문)")
        res = _post(None)
    ok = bool(res.get("ok"))
    print("[telegram] 전송", "성공" if ok else f"실패 {str(res)[:150]}")
    return ok


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
