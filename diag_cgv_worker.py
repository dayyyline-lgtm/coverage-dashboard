# -*- coding: utf-8 -*-
# CGV 를 Cloudflare 워커 경유로 부르면 열리나 — 러너(미국)에서 확인하는 진단 (2026-09-28, diag_probe.py 가 부른다)
# 러너 IP(Azure AS8075)는 CGV 가 403 이다. 워커는 '부르는 쪽에 가까운 데이터센터'에서 돌므로, 러너가 부르면 미국 colo 에서 돈다.
# 한국 colo(ICN)에서는 200 확인(이 PC). 여기서 workerColo·cgvSees.loc 가 미국일 때도 200 이면 워커 중계(좌석 수집)로 간다.
# 공개 Workers Playground 에 익명 세션으로 시험 워커를 올린다 — 토큰·비밀값 없음, 매번 새 세션. 비공식 API 라 진단 전용.
"""CGV reachability probe from Cloudflare's edge via the public Workers Playground (headless, stdlib only).

How it works (reverse-engineered from workers.cloudflare.com/playground/assets/index-*.js, 2026-09-28):
  1. GET  https://workers.cloudflare.com/playground            -> Set-Cookie: user=<session>   (anonymous, no login)
  2. POST https://workers.cloudflare.com/playground/api/worker  multipart {index.js, metadata} + that cookie
                                                                 -> {"preview": <token>, "tail": <devtools url>}
  3. POST https://<random-uuid>.cloudflarepreviews.com/<path>    headers X-CF-Token=<token>, cf-raw-http: true,
     X-CF-HTTP-Method: GET  -> the worker's raw response (its headers come back prefixed with cf-ew-raw-).
The worker runs in the Cloudflare colo nearest to *this* machine (ICN from Korea, US colo from a GitHub runner).
No lz-string needed: the URL hash is only for sharing; the upload API takes plain multipart.
"""
import http.cookiejar, json, time, urllib.error, urllib.request, uuid

PLAYGROUND = "https://workers.cloudflare.com/playground"
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

WORKER_JS = r"""
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36";
const AL = "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7";
const API_H = { "User-Agent": UA, "Accept": "application/json, text/plain, */*", "Accept-Language": AL, "Referer": "https://cgv.co.kr/ticket/" };
const DOC_H = { "User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
  "Accept-Language": AL, "Upgrade-Insecure-Requests": "1", "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate",
  "Sec-Fetch-Site": "none", "Sec-Fetch-User": "?1" };
const C = "https://cgv.co.kr/api/v1/booking";
// Built per request: at module (global) scope Workers freeze Date.now() at 0 -> scnYmd would be 19700101.
function ymd(d) { return new Date(Date.now() + 9 * 3600e3 + d * 86400e3).toISOString().slice(0, 10).replace(/-/g, ""); }
const tests = () => [
  ["trace_cgv_zone", "https://cgv.co.kr/cdn-cgi/trace", { headers: API_H }],
  ["home_root_doc", "https://cgv.co.kr/", { headers: DOC_H }],
  ["home_www_doc", "https://www.cgv.co.kr/", { headers: DOC_H }],
  ["api_list", C + "/searchAtktTopPostrList?coCd=A420&movNm=&div=&attrCd=", { headers: API_H }],
  ["api_scn_0001_" + ymd(0), C + "/searchMovScnInfo?coCd=A420&siteNo=0001&scnYmd=" + ymd(0) + "&rtctlScopCd=08", { headers: API_H }],
  ["api_scn_0001_" + ymd(1), C + "/searchMovScnInfo?coCd=A420&siteNo=0001&scnYmd=" + ymd(1) + "&rtctlScopCd=08", { headers: API_H }],
  ["api_list_uaOnly", C + "/searchAtktTopPostrList?coCd=A420&movNm=&div=&attrCd=", { headers: { "User-Agent": UA } }],
  ["api_list_noHeaders", C + "/searchAtktTopPostrList?coCd=A420&movNm=&div=&attrCd=", {}],
];
export default {
  async fetch(req) {
    const out = { workerColo: req.cf && req.cf.colo, workerCountry: req.cf && req.cf.country, results: [] };
    for (const [name, u, init] of tests()) {
      const t0 = Date.now();
      try {
        const r = await fetch(u, { redirect: "manual", ...init });
        const t = await r.text();
        let dataLen = null;
        if ((r.headers.get("content-type") || "").includes("json")) {
          try { const d = JSON.parse(t).data; dataLen = Array.isArray(d) ? d.length : null; } catch (e) {}
        }
        const plain = r.status >= 400 ? t.replace(/<style[\s\S]*?<\/style>/g, "").replace(/<script[\s\S]*?<\/script>/g, "")
          .replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim() : t;
        out.results.push({ name, status: r.status, ms: Date.now() - t0, server: r.headers.get("server"),
          cfMitigated: r.headers.get("cf-mitigated"), location: r.headers.get("location"), len: t.length, dataLen,
          head: name.startsWith("trace") ? t : plain.slice(0, 150) });
      } catch (e) { out.results.push({ name, err: String(e), ms: Date.now() - t0 }); }
    }
    return new Response(JSON.stringify(out), { headers: { "content-type": "application/json; charset=utf-8" } });
  },
};
"""


def _multipart(parts):
    """parts: [(field, filename, content_type, bytes)] -> (body, content_type)"""
    b = "----cgvprobe" + uuid.uuid4().hex
    out = []
    for field, fname, ctype, data in parts:
        out.append((f"--{b}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{fname}\"\r\n"
                    f"Content-Type: {ctype}\r\n\r\n").encode() + data + b"\r\n")
    out.append(f"--{b}--\r\n".encode())
    return b"".join(out), f"multipart/form-data; boundary={b}"


def _read(opener, req, timeout):
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def create_preview(worker_js=WORKER_JS, timeout=30):
    """Upload worker to the playground -> (preview_origin, token, opener)."""
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    base_h = {"User-Agent": BROWSER_UA, "Accept-Language": "en-US,en;q=0.9"}
    st, _, _ = _read(op, urllib.request.Request(PLAYGROUND, headers={**base_h, "Accept": "text/html"}), timeout)
    if st != 200 or not any(c.name == "user" for c in jar):
        raise RuntimeError(f"playground session cookie not issued (HTTP {st})")
    meta = {"compatibility_date": time.strftime("%Y-%m-%d", time.gmtime(time.time() - 86400)),
            "compatibility_flags": ["nodejs_compat"], "main_module": "index.js"}
    body, ctype = _multipart([("index.js", "index.js", "application/javascript+module", worker_js.encode("utf-8")),
                              ("metadata", "blob", "application/json", json.dumps(meta).encode())])
    req = urllib.request.Request(PLAYGROUND + "/api/worker", data=body, method="POST",
                                 headers={**base_h, "Content-Type": ctype, "Accept": "*/*",
                                          "Origin": "https://workers.cloudflare.com", "Referer": PLAYGROUND})
    st, _, raw = _read(op, req, timeout)
    try:
        j = json.loads(raw)
    except ValueError:
        raise RuntimeError(f"upload: HTTP {st} non-JSON: {raw[:200]!r}")
    if "preview" not in j:
        raise RuntimeError(f"upload failed: HTTP {st} {j}")
    return f"https://{uuid.uuid4()}.cloudflarepreviews.com", j["preview"], op


def call_preview(origin, token, path="/", timeout=90, tries=4):
    """Raw-http call into the preview (what the playground's HTTP tab does)."""
    last = None
    for i in range(tries):
        req = urllib.request.Request(origin + path, data=b"", method="POST", headers={
            "X-CF-Token": token, "cf-raw-http": "true", "X-CF-HTTP-Method": "GET", "User-Agent": BROWSER_UA,
            "Origin": "https://workers.cloudflare.com"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw, hdr = r.read(), dict(r.headers)
            status = hdr.get("cf-ew-raw-status") or r.status
            return json.loads(raw.decode("utf-8")), status
        except (urllib.error.URLError, ValueError, TimeoutError) as e:
            body = e.read()[:200] if isinstance(e, urllib.error.HTTPError) else b""
            last = f"{type(e).__name__}: {e} {body!r}"
            time.sleep(2 * (i + 1))        # a fresh preview can take a moment to become routable
    raise RuntimeError(f"preview call failed after {tries} tries: {last}")


def probe() -> dict:
    t0 = time.time()
    origin, token, _ = create_preview()
    t1 = time.time()
    data, _ = call_preview(origin, token)
    trace = next((r for r in data["results"] if r["name"] == "trace_cgv_zone"), {})
    kv = dict(l.split("=", 1) for l in (trace.get("head") or "").splitlines() if "=" in l)
    return {
        "workerColo": data.get("workerColo"),
        "workerCountry": data.get("workerCountry"),
        "cgvSees": {k: kv.get(k) for k in ("ip", "colo", "loc", "uag")},
        "tests": [dict({k: r.get(k) for k in ("name", "status", "server", "cfMitigated", "location", "dataLen", "len", "ms", "err")},
                       **({"head": r.get("head")} if not r.get("dataLen") else {}))
                  for r in data["results"] if r["name"] != "trace_cgv_zone"],
        "timing": {"upload_s": round(t1 - t0, 2), "call_s": round(time.time() - t1, 2)},
    }


if __name__ == "__main__":
    print(json.dumps(probe(), ensure_ascii=False, indent=1))


# ── 중계 워커(cloudflare-worker/cgv-relay.js) 배포 전 시험 — 러너에서 OIDC 토큰으로 끝까지 (2026-09-28) ──
def _raw(origin, token, path, extra=None, timeout=60, tries=4):
    """preview 에 raw-http 로 한 번 — (상태, 본문 앞부분, 데이터 수)."""
    last = None
    for i in range(tries):
        h = {"X-CF-Token": token, "cf-raw-http": "true", "X-CF-HTTP-Method": "GET", "User-Agent": BROWSER_UA,
             "Origin": "https://workers.cloudflare.com", **(extra or {})}
        req = urllib.request.Request(origin + path, data=b"", method="POST", headers=h)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw, hdr = r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code} {e.read()[:120]!r}"; time.sleep(2 * (i + 1)); continue
        except (urllib.error.URLError, TimeoutError) as e:
            last = f"{type(e).__name__}: {e}"; time.sleep(2 * (i + 1)); continue
        st = int(hdr.get("cf-ew-status") or hdr.get("cf-ew-raw-status") or 0)   # 실제 상태는 cf-ew-status 에 온다
        n = None
        try:
            d = json.loads(raw.decode("utf-8")).get("data"); n = len(d) if isinstance(d, list) else None
        except Exception:
            pass
        return {"status": st, "dataLen": n, "head": raw[:80].decode("utf-8", "replace"),
                "colo": hdr.get("cf-ew-raw-x-relay-colo")}
    return {"err": last}


def _oidc(aud):
    import os
    u, t = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL"), os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
    if not (u and t):
        return None
    req = urllib.request.Request(u + "&audience=" + aud, headers={"Authorization": "bearer " + t})
    return json.loads(urllib.request.urlopen(req, timeout=20).read())["value"]


def relay_test() -> dict:
    import os
    code = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloudflare-worker", "cgv-relay.js"),
                encoding="utf-8").read()
    origin, token, _ = create_preview(worker_js=code)
    lst = "/api/v1/booking/searchAtktTopPostrList?coCd=A420&movNm=&div=&attrCd="
    good, bad = _oidc("cgv-relay"), _oidc("someone-else")
    out = {"oidc": bool(good),
           "no_token": _raw(origin, token, lst),
           "bad_path": _raw(origin, token, "/api/v1/member/info", {"X-Relay-Token": good or "x"})}
    if good:
        out["good_bearer"] = _raw(origin, token, lst, {"Authorization": "Bearer " + good})
        out["good_xhdr"] = _raw(origin, token, lst, {"X-Relay-Token": good})
        out["wrong_aud"] = _raw(origin, token, lst, {"X-Relay-Token": bad})
    return out
