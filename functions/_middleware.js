/**
 * 자동 수집(봇) 억제 — Cloudflare Pages Function
 * ------------------------------------------------
 * 왜 필요한가
 *   대시보드는 팀이 같이 쓰므로 로그인을 걸 수 없다. 그런데 주소만 알면
 *   `curl https://coverage-dashboard.pages.dev/` 한 줄로 798KB 를 통째로
 *   가져갈 수 있었다(2026-08-06 실측: HTTP 200, 견적·점수·투자논거 전부 포함).
 *
 *   사람이 한 번 저장해 가는 건 어차피 값어치가 없다 — 데이터가 2시간마다
 *   바뀌어서 하루면 못 쓴다. 진짜 문제는 계속 자동으로 긁어 가는 쪽이고,
 *   그건 도구의 정체가 User-Agent 에 그대로 드러난다.
 *
 * ⚠ 이건 '억제'지 '차단'이 아니다.
 *   헤더를 브라우저처럼 흉내 내면 통과한다. 진짜로 막으려면 본인 도메인을
 *   Cloudflare 에 붙이고 Bot Fight Mode 를 켜야 한다 — pages.dev 주소에는
 *   WAF·봇 설정을 걸 수 없다(그 도메인은 Cloudflare 소유라서).
 *   여기서 막는 건 '한 줄 curl' 수준이고, 실제로 그게 가장 흔하다.
 *
 * 사람은 아무 영향이 없다
 *   판정은 User-Agent 하나만 본다. Sec-Fetch-* 헤더로도 걸러 봤지만 그건
 *   구형·인앱 브라우저에서 안 붙는 경우가 있어 팀원을 잘못 막을 수 있다.
 *   같이 쓰는 물건이라 '오탐 0' 이 '조금 더 촘촘함' 보다 중요하다.
 */

// 정체가 이름에 드러나는 것들. 소문자로 비교한다.
const TOOLS = [
  "curl", "wget", "python-requests", "python-urllib", "httpx", "aiohttp",
  "scrapy", "go-http-client", "okhttp", "java/", "libwww", "lwp::",
  "node-fetch", "axios", "undici", "postman", "insomnia",
  "headlesschrome", "phantomjs", "puppeteer", "playwright",
  "httpclient", "restsharp", "guzzle", "mechanize", "wpscan",
];

// 링크 미리보기 봇은 통과시킨다. 색인은 robots.txt 가 이미 막고 있고,
// 텔레그램 레터의 '대시보드 열기' 미리보기가 깨지면 그게 더 불편하다.
const ALLOW = [
  "telegrambot", "slackbot", "discordbot", "twitterbot", "facebookexternalhit",
];

function looksLikeTool(ua) {
  const s = (ua || "").toLowerCase();
  if (!s) return true;                       // UA 를 아예 안 보내는 건 사람이 아니다
  if (ALLOW.some((k) => s.includes(k))) return false;
  return TOOLS.some((k) => s.includes(k));
}

const DENY_BODY =
  "자동 수집은 허용하지 않습니다.\n" +
  "This dashboard does not allow automated collection.\n";

export async function onRequest(context) {
  const { request, next } = context;
  const url = new URL(request.url);

  // robots.txt 는 누구에게나 열어 둔다 — 막으면 크롤러가 규칙을 못 읽는다.
  if (url.pathname === "/robots.txt") return next();

  if (!looksLikeTool(request.headers.get("user-agent"))) return next();

  return new Response(DENY_BODY, {
    status: 403,
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}
