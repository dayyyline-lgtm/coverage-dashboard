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
    global LAST
    LAST = {"ok": ok, "has_token": bool(BOT_TOKEN), "has_chat": bool(CHAT_ID),
            "detail": str(res)[:260]}
    print("[telegram] 전송", "성공" if ok else f"실패 {str(res)[:150]}")
    return ok


LAST = {}       # 마지막 send 결과(진단용) — 호출자가 파일로 남길 수 있게 노출
RICH_MODE = ""  # 마지막 send_rich 가 표(rich)로 갔는지, 평문으로 떨어졌는지(사유)


def _api(method, data=None, body=None, ctype=None, timeout=60):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    hd = {"Content-Type": ctype} if ctype else {}
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, data=body if body is not None else data, headers=hd), timeout=timeout)
        return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8", "replace")
        print(f"[telegram] {method} HTTP {e.code}: {' '.join(txt.split())[:220]}")
        try:
            return json.loads(txt)
        except Exception:
            return {"ok": False}
    except Exception as e:
        print(f"[telegram] {method} 오류: {str(e)[:150]}")
        return {"ok": False}


def send_rich(html, fallback=None, chat_id=None, silent=False):
    """sendRichMessage(Bot API 10.1 · <h2>·<p>·<table bordered> 를 그대로 그린다).
       실패하면 fallback(평문)을 sendMessage 로. 3만 자를 넘기면 앞에서 자른다(호출자가 나눌 것)."""
    cid = chat_id or CHAT_ID
    if not (BOT_TOKEN and cid):
        print("[telegram] 토큰·챗ID 미설정 — 전송 생략"); return False
    p = {"chat_id": cid, "rich_message": {"html": html[:30000]}}
    if silent:
        p["disable_notification"] = True
    res = _api("sendRichMessage", body=json.dumps(p, ensure_ascii=False).encode("utf-8"), ctype="application/json; charset=utf-8")
    global RICH_MODE
    if res.get("ok"):
        RICH_MODE = "rich"
        print("[telegram] rich 전송 성공"); return True
    RICH_MODE = "plain: " + str(res.get("description", res))[:120]
    print(f"[telegram] rich 실패 {str(res)[:200]} — 평문으로")
    return send(fallback or html, chat_id=cid, parse_mode=None if fallback else "HTML", silent=silent)


def send_photos(paths, caption="", chat_id=None, silent=False, captions=None):
    """사진 여러 장을 앨범(sendMediaGroup · 10장씩)으로. caption = 첫 장에만 · captions = 장마다. 한 장이면 sendPhoto."""
    import uuid, mimetypes
    cid = chat_id or CHAT_ID
    if not (BOT_TOKEN and cid):
        print("[telegram] 토큰·챗ID 미설정 — 전송 생략"); return False
    ok = True
    for g in range(0, len(paths), 10):
        grp = paths[g:g + 10]
        bnd = "----tg" + uuid.uuid4().hex
        parts = []

        def field(name, val):
            parts.append(f'--{bnd}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{val}\r\n'.encode("utf-8"))

        def filepart(name, path):
            ct = mimetypes.guess_type(path)[0] or "application/octet-stream"
            parts.append(f'--{bnd}\r\nContent-Disposition: form-data; name="{name}"; filename="{os.path.basename(path)}"\r\n'
                         f'Content-Type: {ct}\r\n\r\n'.encode("utf-8") + open(path, "rb").read() + b"\r\n")

        field("chat_id", cid)
        if silent:
            field("disable_notification", "true")
        caps = (captions[g:g + 10] if captions else [caption if (g == 0 and i == 0) else "" for i in range(len(grp))])
        cap = caps[0] if caps else ""
        if len(grp) == 1:
            if cap:
                field("caption", cap[:1024])
            filepart("photo", grp[0])
            method = "sendPhoto"
        else:
            media = []
            for i, p in enumerate(grp):
                m = {"type": "photo", "media": f"attach://p{i}"}
                if i < len(caps) and caps[i]:
                    m["caption"] = caps[i][:1024]
                media.append(m)
                filepart(f"p{i}", p)
            field("media", json.dumps(media, ensure_ascii=False))
            method = "sendMediaGroup"
        parts.append(f"--{bnd}--\r\n".encode())
        res = _api(method, body=b"".join(parts), ctype=f"multipart/form-data; boundary={bnd}", timeout=120)
        print(f"[telegram] {method} {len(grp)}장", "성공" if res.get("ok") else f"실패 {str(res)[:200]}")
        ok = ok and bool(res.get("ok"))
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
