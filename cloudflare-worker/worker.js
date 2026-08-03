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

    // 어느 슬롯이 '아침 전체수집 + 데일리 레터'인가.
    //
    // ⚠ 이 판정이 두 번 틀렸다. 처음엔 cron 문자열 전체를 비교했는데 Cloudflare 가
    //   요일 숫자("0-4")를 거부해 "SUN-THU"로 저장되는 바람에 안 맞았고,
    //   그다음엔 '분 0 · 시 22'로 고쳤는데 실제 저장값이 "30 22 * * SUN-THU"(분 30)라
    //   또 안 맞았다. 그 결과 워커는 매일 아침 레터 대신 refresh.yml 만 돌렸고
    //   레터는 자동으로 나간 적이 없었다(2026-08-04 확인).
    //
    // 그래서 값 하나에 기대지 않게 폭을 넓혔다:
    //   - 시가 20 이면 레터 (KST 05:45 — 6시 도착용 새 슬롯)
    //   - 시가 22 인데 분이 0 이 아니면 레터 (옛 07:30 슬롯)
    //   - 시가 22 이고 분이 0 이면 시세 ("0 22,23" 슬롯과 겹치지 않게)
    // 시 칸에 "20,23" 처럼 여러 값이 들어와도 잡히도록 쉼표로 쪼개 본다.
    const [mi, hh] = String(event.cron || "").trim().split(/\s+/);
    const hours = String(hh || "").split(",");
    const isEventSlot = hours.includes("20") || (hours.includes("22") && mi !== "0");
    // 일요일 22:00 UTC = 한국시간 월요일 07:00 이므로 트렌드도 같이 돌린다.
    const jobs = isEventSlot ? ["events.yml"] : ["refresh.yml"];
    if (isEventSlot && new Date(event.scheduledTime).getUTCDay() === 0) {
      jobs.push("trends.yml");
    }

    for (const wf of jobs) {
      const r = await dispatch(wf, token);
      console.log(JSON.stringify({ cron: event.cron, ...r }));
    }

    // 뉴스봇(별도 저장소)도 같은 슬롯에 부른다.
    // 그쪽 GitHub 예약은 이 계정에서 한 번도 뜬 적이 없다(2026-08-04 확인: 실행 기록이 전부 수동).
    // 브랜치가 master 다. 토큰 권한이 그 저장소에 없으면 404 가 찍히고 넘어간다 —
    // 여기서 실패해도 대시보드 쪽 작업은 이미 위에서 끝났으므로 영향이 없다.
    if (isEventSlot) {
      try {
        const r = await dispatch("daily-briefing.yml", token, "news-bot", "master");
        console.log(JSON.stringify({ cron: event.cron, ...r }));
      } catch (e) {
        console.log("news-bot 트리거 실패: " + e);
      }
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
