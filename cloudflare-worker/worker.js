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
 *   45 20 * * SUN-THU        → 한국시간 평일 05:45 (아침 전체수집 + 데일리 레터)  ← 이 슬롯이 events.yml
 *                             레터가 6시에 도착하도록 시작을 앞당긴 값이다(수집에 4~5분 걸린다).
 *                             옛 값 `0 22 * * SUN-THU`(KST 07:00)도 코드가 계속 인정한다.
 *   0 22,23 * * 0-4          → 한국시간 평일 07,08시 (시세)
 *   0 0-9 * * 1-5            → 한국시간 평일 09~18시 (시세)
 *   0 3,7,11,15,19,23 * * 6  → 한국시간 주말 (시세)
 *   0 3,7,11 * * 0           → 한국시간 일요일 (시세)
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

    // 07:00 KST(=22:00 UTC) 전용 슬롯 → 아침 전체수집 + 데일리 레터(events.yml).
    //
    // 전체 문자열을 비교하면 안 된다. Cloudflare 는 요일을 숫자("0-4")로 쓰면 거부해서
    // 실제 저장값은 "0 22 * * SUN-THU" 인데, 코드가 "0 22 * * 0-4" 를 기다리고 있었다.
    // 그래서 이 슬롯이 한 번도 참이 되지 않았고 매번 refresh.yml 만 돌아
    // 데일리 레터가 통째로 발송되지 않았다.
    // 요일 표기와 무관하게 '분 0 · 시 22' 만 본다. 시세 슬롯은 시가 "22,23" 이라 안 겹친다.
    const [mi, hh] = String(event.cron || "").trim().split(/\s+/);
    // 레터를 아침 6시에 받으려고 이 슬롯을 UTC 20:45(=KST 05:45)로 옮겼다.
    // 옛 슬롯(UTC 22:00 = KST 07:00)도 계속 인정한다 — 이 코드를 배포했는데
    // Cloudflare 쪽 Cron Trigger 를 아직 안 고쳤다면 레터가 통째로 안 나가기 때문이다.
    // 둘 다 걸려 있어도 digest.py --once 가 하루 한 통만 보낸다.
    const isEventSlot = hh === "20" || (mi === "0" && hh === "22");
    // 일요일 22:00 UTC = 한국시간 월요일 07:00 이므로 트렌드도 같이 돌린다.
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
