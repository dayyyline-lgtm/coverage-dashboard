/**
 * 커버리지 대시보드 자동 갱신 트리거 (Cloudflare Worker)
 * ------------------------------------------------------
 * GitHub 자체 예약 스케줄러가 불안정해서, Cloudflare Cron Trigger가
 * 정해진 시각에 GitHub Actions 를 대신 실행시킵니다.
 *
 * 필요한 시크릿 (Worker > Settings > Variables and Secrets)
 *   GH_TOKEN : GitHub Personal Access Token (repo + workflow 권한)
 *
 * Cron Triggers (Worker > Settings > Trigger Events) — 모두 UTC 기준
 *   0 20 * * SUN-THU         → 한국시간 평일 05:00 (아침 전체수집: events.yml, 트렌드 포함)
 *   0 21 * * SUN-THU         → 한국시간 평일 06:00 (데일리 레터: letter.yml + 뉴스봇)
 *                             ↑ 2026-08-07: '05시 수집 → 06시 레터' 분리. 옛 값은
 *                               `45 20 * * SUN-THU`(05:45 수집+레터 한 번에) 였다.
 *   0 22,23 * * 0-4          → 한국시간 평일 07,08시 (시세)
 *   0 0-9 * * 1-5            → 한국시간 평일 09~18시 (시세)
 *   0 3,7,11,15,19,23 * * 6  → 한국시간 주말 (시세)
 *   0 3,7,11 * * 0           → 한국시간 일요일 (시세)
 */

const OWNER = "dayyyline-lgtm";
const REPO  = "coverage-dashboard";

// 뉴스봇은 별도 저장소라 repo 를 넘길 수 있게 해 둔다.
async function dispatch(workflow, token, repo = REPO, ref = "main") {
  const url = `https://api.github.com/repos/${OWNER}/${repo}/actions/workflows/${workflow}/dispatches`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "coverage-dashboard-cron",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ ref }),
  });
  // 성공 시 204 No Content
  return { repo, workflow, status: res.status, ok: res.status === 204,
           body: res.status === 204 ? "" : (await res.text()).slice(0, 200) };
}

export default {
  // 예약 실행
  async scheduled(event, env, ctx) {
    const token = env.GH_TOKEN;
    if (!token) { console.log("GH_TOKEN 시크릿이 없습니다"); return; }

    // 어느 슬롯인가 — cron 의 '시(hour)' 로 가른다 (2026-08-07 '05시 수집→06시 레터' 분리).
    //   시 20(UTC) = KST 05:00 → 아침 전체수집 (events.yml, 트렌드 포함)
    //   시 21(UTC) = KST 06:00 → 데일리 레터 (letter.yml) + 뉴스봇
    //   그 외        = 시세 (refresh.yml)
    // 시 칸에 "20,23" 처럼 여러 값이 와도 잡히게 쉼표로 쪼개 본다.
    // ⚠ Cloudflare Cron Trigger 를 "0 20 * * SUN-THU"(수집)·"0 21 * * SUN-THU"(레터)로 설정할 것.
    //   시세 슬롯(22,23,0-9…)엔 20·21 이 없으므로 겹치지 않는다.
    const [mi, hh] = String(event.cron || "").trim().split(/\s+/);
    const hours = String(hh || "").split(",");
    const isCollect = hours.includes("20");   // KST 05:00 — 아침 전체수집
    const isLetter  = hours.includes("21");   // KST 06:00 — 데일리 레터

    const jobs = isCollect ? ["events.yml"] : isLetter ? ["letter.yml"] : ["refresh.yml"];
    for (const wf of jobs) {
      const r = await dispatch(wf, token);
      console.log(JSON.stringify({ cron: event.cron, ...r }));
    }

    // 뉴스봇(별도 저장소)은 레터 슬롯(06:00)에 부른다 — 05시 수집분 기반 브리핑.
    // 브랜치가 master 다. 토큰 권한이 없으면 404 가 찍히고 넘어간다(대시보드 쪽엔 영향 없음).
    if (isLetter) {
      try {
        const r = await dispatch("daily-briefing.yml", token, "news-bot", "master");
        console.log(JSON.stringify({ cron: event.cron, ...r }));
      } catch (e) {
        console.log("news-bot 트리거 실패: " + e);
      }
    }
  },

  // 브라우저로 열면 수동 실행 + 상태 확인
  //
  // ⚠ 인증 필수 (2026-08-04 추가)
  //   예전엔 아무 검사가 없어서, 이 주소를 아는 사람은 누구나 워크플로를 무한히
  //   돌릴 수 있었다. 주소를 아무도 모른다는 것 하나에 기대고 있었는데, 그 주소는
  //   CLAUDE.md·설정방법.md 에 적혀 있다 — 저장소를 공개하는 순간 그대로 노출된다.
  //   Actions 분은 한 달 2,000분뿐이라 몇 분이면 통째로 태울 수 있다.
  //
  //   TRIGGER_KEY 는 Cloudflare > Workers > coverage-cron > Settings >
  //   Variables and Secrets 에 Secret 으로 넣는다(아무 긴 문자열).
  //   호출: ?wf=refresh.yml&key=<TRIGGER_KEY>   또는 헤더 X-Trigger-Key
  //   ⚠ 키가 없으면 전부 거절한다(fail closed). 열어 두는 쪽으로 되돌리지 말 것.
  //   cron 실행은 scheduled() 로 들어오므로 이 검사와 무관하다.
  async fetch(req, env) {
    const u = new URL(req.url);
    const given = u.searchParams.get("key") || req.headers.get("X-Trigger-Key") || "";
    const want = env.TRIGGER_KEY || "";
    // 길이가 다르면 즉시 실패. 같으면 전 바이트를 비교해 응답 시간으로 키를 못 캐게 한다.
    let ok = want.length > 0 && given.length === want.length;
    if (ok) { let diff = 0; for (let i = 0; i < want.length; i++) diff |= want.charCodeAt(i) ^ given.charCodeAt(i); ok = diff === 0; }
    if (!ok) return new Response("Not found\n", { status: 404 });

    const token = env.GH_TOKEN;
    if (!token) return new Response("GH_TOKEN 시크릿이 설정되지 않았습니다.", { status: 500 });

    const wf = u.searchParams.get("wf");
    if (!wf) {
      return new Response(
        "커버리지 대시보드 자동 갱신 트리거\n\n" +
        "수동 실행 (뒤에 &key=<TRIGGER_KEY> 를 붙일 것):\n" +
        "  ?wf=refresh.yml   시세·리포트 갱신\n" +
        "  ?wf=events.yml    DART 이벤트 갱신 + 데일리 레터\n" +
        "  ?wf=trends.yml    트렌드 갱신\n",
        { headers: { "content-type": "text/plain; charset=utf-8" } });
    }
    const r = await dispatch(wf, token);
    return new Response(JSON.stringify(r, null, 1),
      { status: r.ok ? 200 : 500, headers: { "content-type": "application/json; charset=utf-8" } });
  },
};
