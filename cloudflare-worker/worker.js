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
 *   0 22,23 * * 0-4          → 한국시간 평일 07,08시
 *   0 0-9 * * 1-5            → 한국시간 평일 09~18시
 *   0 3,7,11,15,19,23 * * 6  → 한국시간 주말
 *   30 22 * * 0-4            → 한국시간 평일 07:30 (DART 이벤트)
 */

const OWNER = "dayyyline-lgtm";
const REPO  = "coverage-dashboard";

async function dispatch(workflow, token) {
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${workflow}/dispatches`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "coverage-dashboard-cron",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  // 성공 시 204 No Content
  return { workflow, status: res.status, ok: res.status === 204,
           body: res.status === 204 ? "" : (await res.text()).slice(0, 200) };
}

export default {
  // 예약 실행
  async scheduled(event, env, ctx) {
    const token = env.GH_TOKEN;
    if (!token) { console.log("GH_TOKEN 시크릿이 없습니다"); return; }

    // 07:30 KST(=22:30 UTC) 슬롯 → DART 이벤트.
    // 그중 일요일 22:30 UTC = 한국시간 월요일 07:30 이므로 트렌드도 같이 돌린다.
    // (트렌드 전용 Cron Trigger를 따로 추가하지 않아도 되게 하기 위함)
    const isEventSlot = event.cron.startsWith("30 22");
    const jobs = isEventSlot ? ["events.yml"] : ["refresh.yml"];
    if (isEventSlot && new Date(event.scheduledTime).getUTCDay() === 0) {
      jobs.push("trends.yml");
    }

    for (const wf of jobs) {
      const r = await dispatch(wf, token);
      console.log(JSON.stringify({ cron: event.cron, ...r }));
    }
  },

  // 브라우저로 열면 수동 실행 + 상태 확인
  async fetch(req, env) {
    const token = env.GH_TOKEN;
    if (!token) return new Response("GH_TOKEN 시크릿이 설정되지 않았습니다.", { status: 500 });

    const u = new URL(req.url);
    const wf = u.searchParams.get("wf");
    if (!wf) {
      return new Response(
        "커버리지 대시보드 자동 갱신 트리거\n\n" +
        "수동 실행:\n" +
        "  ?wf=refresh.yml   시세·리포트 갱신\n" +
        "  ?wf=events.yml    DART 이벤트 갱신\n" +
        "  ?wf=trends.yml    트렌드 갱신\n",
        { headers: { "content-type": "text/plain; charset=utf-8" } });
    }
    const r = await dispatch(wf, token);
    return new Response(JSON.stringify(r, null, 1),
      { status: r.ok ? 200 : 500, headers: { "content-type": "application/json; charset=utf-8" } });
  },
};
