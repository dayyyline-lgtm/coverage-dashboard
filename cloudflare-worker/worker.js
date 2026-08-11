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
 *
 * ⚠ **무료 플랜은 Cron Trigger 가 계정당 5개다.** 그래서 시각마다 하나씩 만들면 모자란다.
 *   이 워커는 **실제 발화 시각**으로 분기하므로 한 트리거에 여러 시각을 묶어도 된다.
 *
 *   0 20,21 * * SUN-THU      → 한국시간 평일 05:00 수집(events) + 06:00 레터(letter)+뉴스봇
 *                              ↑ 하나로 묶은 것. 옛 값 `45 20 * * SUN-THU`(05:45) 을 이걸로 교체.
 *   0 22,23 * * SUN-THU      → 한국시간 평일 07,08시 (시세)
 *   0 0-9 * * MON-FRI        → 한국시간 평일 09~18시 (시세)
 *   0 3,7,11,15,19,23 * * SAT→ 한국시간 토요일 (시세)
 *   0 3,7,11 * * SUN         → 한국시간 일요일 (시세)
 *
 *   요일은 이름(SUN-THU)으로 쓸 것 — Cloudflare 가 숫자(0-4)를 거부한다.
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

    // 어느 슬롯인가 — **실제 발화 시각(UTC)** 으로 가른다.
    //   20시(UTC) = KST 05:00 → 아침 전체수집 (events.yml, 트렌드 포함)
    //   21시(UTC) = KST 06:00 → 데일리 레터 (letter.yml) + 뉴스봇
    //   그 외      = 시세 (refresh.yml)
    //
    // ⚠ 2026-08-11 변경: 예전엔 **cron 문자열의 '시' 칸**을 파싱했다. 그 방식은
    //   한 트리거에 여러 시각을 묶을 수 없다 — `0 20,21 * * SUN-THU` 로 묶으면
    //   hours 에 "20" 이 있으니 21시에도 수집이 돌고 레터·뉴스봇은 영영 안 불린다.
    //   그래서 시각마다 트리거를 따로 만들어야 했는데, **무료 플랜은 Cron Trigger 가
    //   계정당 5개**라 자리가 없어 `0 21` 을 추가하지 못했다(실제로 Add 가 막혔다).
    //
    //   실제 발화 시각을 보면 트리거를 어떻게 묶든 분기가 정확해진다.
    //   → `45 20 * * SUN-THU` 하나를 `0 20,21 * * SUN-THU` 로 고치면
    //     05:00 수집 + 06:00 레터·뉴스봇이 **트리거 한 개**로 둘 다 된다.
    //
    //   scheduledTime 은 '예정된' 시각이라 발화가 조금 늦어도 값이 흔들리지 않는다.
    //   혹시 없으면 옛 방식(cron 문자열)으로 떨어진다.
    let h = -1;
    if (event.scheduledTime) {
      h = new Date(event.scheduledTime).getUTCHours();
    } else {
      const hh = String(event.cron || "").trim().split(/\s+/)[1] || "";
      h = parseInt(hh.split(",")[0], 10);
    }
    const isCollect = h === 20;   // KST 05:00 — 아침 전체수집
    const isLetter  = h === 21;   // KST 06:00 — 데일리 레터

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
