/**
 * CGV 예매 API 중계 워커 — cgv-relay (2026-09-28)
 * ------------------------------------------------------
 * 왜: GitHub 러너(미국 마이크로소프트 IP)는 CGV 가 403 이다(2026-09-13~). 예매 API 뿐 아니라 차단 페이지가
 *     "비정상적으로 CGV에 접속한 것이 확인되어 이용이 제한되었어요" 로 뜬다. 이 PC(한국 가정용 IP)에선 200.
 *     Cloudflare 워커를 거치면 **러너 근처 미국 데이터센터(ORD)에서 돌아도 200** 이다(diag 2026-09-28 실측 —
 *     diag/net_probe.json 의 cgv_via_worker). 그래서 좌석 수집(boxseats.yml)의 CGV 요청만 여기를 거친다.
 *
 * 열린 중계기가 되지 않게 — 둘 다 통과해야 CGV 를 부른다.
 *   ① GitHub Actions OIDC 토큰: 이 저장소(dayyyline-lgtm/coverage-dashboard)의 워크플로가 발급받은 서명 토큰만.
 *      GitHub 공개키(JWKS)로 서명을 검증하므로 **따로 넣을 비밀값이 없다**(워커 설정에 시크릿 불필요).
 *   ② 경로: cgv.co.kr 의 /api/v1/booking/<이름> 조회(GET)만.
 *
 * 설치: Cloudflare > Workers & Pages > Create > Worker > 이름 cgv-relay > Deploy > Edit code >
 *       이 파일 내용 전체 붙여넣기 > Deploy. 주소는 https://cgv-relay.dayyyline.workers.dev
 *       (cloudflare-worker/설정방법.md 참고)
 *
 * ⚠ 요청 간격은 수집기 쪽에서 지킨다(순차 · 0.12초). CGV 는 병렬로 몰면 429 를 준다 — 이 워커가 속도를 올려 주는
 *   도구가 아니다. 수집 주기도 그대로(약 3시간, 전수 하루 2번)다.
 * ⚠ 모듈 전역에서 Date.now() 는 0 으로 얼어 있다 — 시간 계산은 fetch() 안에서만.
 */

const REPO = "dayyyline-lgtm/coverage-dashboard";
const AUD  = "cgv-relay";
const ISS  = "https://token.actions.githubusercontent.com";
const UA   = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36";

let JWKS = null, JWKS_AT = 0;          // 공개키 — 한 시간 캐시(같은 isolate 안에서)
async function jwks(now) {
  if (JWKS && now - JWKS_AT < 3600e3) return JWKS;
  const r = await fetch(ISS + "/.well-known/jwks", { headers: { "User-Agent": "cgv-relay" } });
  JWKS = (await r.json()).keys || []; JWKS_AT = now;
  return JWKS;
}
const b64u = s => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4)), c => c.charCodeAt(0));
const js = s => JSON.parse(new TextDecoder().decode(b64u(s)));

/* 서명·발급자·대상·저장소·만료를 전부 본다. 하나라도 틀리면 null. */
async function verify(tok, now) {
  const parts = (tok || "").split(".");
  if (parts.length !== 3) return null;
  const [h, p, s] = parts, hd = js(h), pl = js(p);
  if (hd.alg !== "RS256") return null;
  let key = (await jwks(now)).find(k => k.kid === hd.kid);
  if (!key) { JWKS = null; key = (await jwks(now)).find(k => k.kid === hd.kid); }   // 키 교체 직후
  if (!key) return null;
  const ck = await crypto.subtle.importKey("jwk", { kty: "RSA", n: key.n, e: key.e, alg: "RS256", ext: true },
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
  const ok = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", ck, b64u(s), new TextEncoder().encode(h + "." + p));
  const t = now / 1000;
  if (!ok || pl.iss !== ISS || pl.aud !== AUD || pl.repository !== REPO) return null;
  if (!(pl.exp > t) || (pl.nbf && pl.nbf > t + 60)) return null;
  return pl;
}

export default {
  async fetch(req) {
    const now = Date.now(), u = new URL(req.url);
    if (req.method !== "GET") return new Response("method not allowed\n", { status: 405 });
    if (!/^\/api\/v1\/booking\/[A-Za-z]+$/.test(u.pathname)) return new Response("Not found\n", { status: 404 });
    const auth = req.headers.get("Authorization") || "";
    const tok = auth.startsWith("Bearer ") ? auth.slice(7) : (req.headers.get("X-Relay-Token") || "");
    let pl = null;
    try { pl = await verify(tok, now); } catch (e) { pl = null; }
    if (!pl) return new Response("unauthorized\n", { status: 401 });
    const r = await fetch("https://cgv.co.kr" + u.pathname + u.search, { headers: {
      "User-Agent": UA, "Accept": "application/json, text/plain, */*",
      "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7", "Referer": "https://cgv.co.kr/ticket/" } });
    return new Response(r.body, { status: r.status, headers: {
      "content-type": r.headers.get("content-type") || "application/json; charset=utf-8",
      "x-relay-colo": (req.cf && req.cf.colo) || "" } });
  },
};
