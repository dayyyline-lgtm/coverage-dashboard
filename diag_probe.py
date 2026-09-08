"""러너 네트워크 진단 — '왜 로컬은 되고 Actions 는 안 되나'를 한 번에 찍는다 (2026-09-09).

게임머니(아이템매니아)는 도입일부터 Actions 에서 100% 타임아웃, 올리브영은 403, 메가박스는 절반쯤
타임아웃인데 이 PC(가정용 KR IP)에선 셋 다 0.2초에 200 이다. 헤더는 이미 맞췄으니 남는 변수는
**러너 IP** 다. 여기서는 단계를 쪼개 찍는다 — DNS · TCP 연결 · TLS · HTTP 응답. 어느 단계에서
멈추는지가 곧 차단 방식이다(TCP 에서 죽으면 IP 드롭, HTTP 403 이면 WAF, 다 되면 헤더/쿠키 문제).

결과는 diag/net_probe.json 에 남기고 워크플로가 커밋한다. 수집기와 무관한 일회성 도구다.
"""
import json, socket, ssl, time, urllib.request, urllib.parse, datetime, sys, concurrent.futures as cf
sys.path.insert(0, ".")
from collector_health import ua

KST = datetime.timezone(datetime.timedelta(hours=9))
OUT = {"t": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST"), "runner": {}, "probes": []}


def whoami():
    for u in ("https://ipinfo.io/json", "https://api.ipify.org?format=json"):
        try:
            with urllib.request.urlopen(u, timeout=10) as r:
                d = json.loads(r.read().decode())
                OUT["runner"].update({k: d[k] for k in ("ip", "org", "country", "region", "city") if k in d})
                if "ip" in OUT["runner"]: return
        except Exception as e:
            OUT["runner"][u] = f"{type(e).__name__}: {str(e)[:60]}"


def stages(host, port=443, timeout=15):
    """DNS → TCP → TLS 각 단계 시간. 어디서 죽는지."""
    s = {}
    t = time.time()
    try:
        ip = socket.gethostbyname(host); s["dns"] = round(time.time() - t, 2); s["ip"] = ip
    except Exception as e:
        s["dns_err"] = f"{type(e).__name__}: {str(e)[:60]}"; return s
    t = time.time()
    try:
        sock = socket.create_connection((ip, port), timeout=timeout); s["tcp"] = round(time.time() - t, 2)
    except Exception as e:
        s["tcp_err"] = f"{type(e).__name__}: {str(e)[:60]}"; return s
    t = time.time()
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(sock, server_hostname=host) as ss:
            s["tls"] = round(time.time() - t, 2); s["tls_ver"] = ss.version()
    except Exception as e:
        s["tls_err"] = f"{type(e).__name__}: {str(e)[:60]}"
    finally:
        try: sock.close()
        except Exception: pass
    return s


def http(name, url, headers, data=None, timeout=20):
    t = time.time()
    rec = {"name": name, "url": url.split("?")[0]}
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=timeout)
        b = r.read()
        rec.update({"status": r.status, "bytes": len(b), "sec": round(time.time() - t, 2),
                    "server": r.headers.get("Server"), "head": b[:90].decode("utf-8", "replace")})
    except urllib.error.HTTPError as e:
        body = b""
        try: body = e.read()[:300]
        except Exception: pass
        rec.update({"status": e.code, "sec": round(time.time() - t, 2), "server": e.headers.get("Server"),
                    "err_head": body.decode("utf-8", "replace")})
    except Exception as e:
        rec.update({"err": f"{type(e).__name__}: {str(e)[:80]}", "sec": round(time.time() - t, 2)})
    return rec


def main():
    whoami()
    IM = "https://www.itemmania.com"
    OY = "https://www.oliveyoung.co.kr/store/main/getBestList.do"
    MB = "https://www.megabox.co.kr/on/oh/ohc/Brch/schedulePage.do"
    mbh = ua(referer="https://www.megabox.co.kr/booking/timetable")
    mbh.update({"Accept": "application/json, text/plain, */*", "Content-Type": "application/json; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest"})
    today = datetime.datetime.now(KST).strftime("%Y%m%d")
    mb_body = json.dumps({"masterType": "brch", "brchNo": "1372", "firstAt": "N", "brchNo1": "1372",
                          "crtDe": today, "playDe": today}).encode()
    xml_h = ua(referer=IM + "/game_info/money/", extra={"Accept": "application/xml, text/xml, */*; q=0.01",
               "X-Requested-With": "XMLHttpRequest", "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors",
               "Sec-Fetch-Site": "same-origin"})
    jobs = [
        ("itemmania XML(수집기 헤더)", IM + "/_xml/gamemoney_avg.xml.php?gamecode=6027&servercode=1&count=3", xml_h, None),
        ("itemmania XML(헤더 없음)", IM + "/_xml/gamemoney_avg.xml.php?gamecode=6027&servercode=1&count=3", {"User-Agent": "curl/8.5"}, None),
        ("itemmania rank(doc)", IM + "/game_info/rank_game/", ua(referer=IM + "/", doc=True), None),
        ("itemmania 홈(http 80)", "http://www.itemmania.com/", ua(doc=True), None),
        ("oliveyoung best(doc)", OY, ua(referer="https://www.oliveyoung.co.kr/", doc=True), None),
        ("oliveyoung 홈(doc)", "https://www.oliveyoung.co.kr/store/main/main.do", ua(doc=True), None),
        ("oliveyoung global(doc)", "https://global.oliveyoung.com/", ua(doc=True), None),
        ("megabox schedulePage POST", MB, mbh, mb_body),
        ("megabox 홈(doc)", "https://www.megabox.co.kr/", ua(doc=True), None),
        ("대조군 CGV", "https://www.cgv.co.kr/", ua(doc=True), None),
        ("대조군 네이버", "https://www.naver.com/", ua(doc=True), None),
        ("대조군 gamebit", "https://gamebit.co.kr/jdata2/zeus/total_status.json", ua(referer="https://gamebit.co.kr/zeus"), None),
    ]
    with cf.ThreadPoolExecutor(8) as ex:
        futs = [ex.submit(http, *j) for j in jobs]
        st = {h: ex.submit(stages, h) for h in ("www.itemmania.com", "www.oliveyoung.co.kr", "www.megabox.co.kr", "www.cgv.co.kr")}
        OUT["probes"] = [f.result() for f in futs]
        OUT["stages"] = {h: f.result() for h, f in st.items()}
    import os
    os.makedirs("diag", exist_ok=True)
    json.dump(OUT, open("diag/net_probe.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(OUT, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
