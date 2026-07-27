/*
 * 커버리지 대시보드 — 텔레그램 조회 봇 (Cloudflare Worker)
 * ------------------------------------------------------------
 * 텔레그램에서 명령어를 보내면 배포된 대시보드 데이터를 읽어 답한다.
 *   /시세 에이피알      · 가격·등락·PER
 *   /트렌드 티니핑      · 검색 트렌드 최근값
 *   /수출 티앤엘        · (안성 창상피복재 등) 최근 수출액
 *   /일정              · 임박한 실적발표·IR
 *   /help              · 도움말
 * 종목명만 보내도 시세를 답한다.
 *
 * 설정(자세히는 telegram-bot/설정방법.md):
 *   1) Cloudflare Workers 에 이 코드 배포
 *   2) 환경변수(Secret): BOT_TOKEN (BotFather 토큰), WEBHOOK_SECRET (아무 문자열)
 *   3) 웹훅 등록:
 *      https://api.telegram.org/bot<토큰>/setWebhook?url=<워커주소>&secret_token=<WEBHOOK_SECRET>
 */
const SITE = "https://coverage-dashboard.pages.dev";
const TTL = 300;   // 데이터 캐시(초)

export default {
  async fetch(req, env, ctx) {
    if (req.method !== "POST") return new Response("ok");     // 헬스체크
    // 웹훅 위조 방지 — 텔레그램이 보내는 secret 헤더 검증
    if (env.WEBHOOK_SECRET &&
        req.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.WEBHOOK_SECRET) {
      return new Response("forbidden", { status: 403 });
    }
    let upd;
    try { upd = await req.json(); } catch { return new Response("ok"); }
    const msg = upd.message || upd.edited_message;
    const text = (msg && msg.text || "").trim();
    if (!msg || !text) return new Response("ok");

    let reply;
    try { reply = await answer(text, env, ctx); }
    catch (e) { reply = "⚠️ 처리 중 오류: " + String(e).slice(0, 120); }
    await send(env, msg.chat.id, reply);
    return new Response("ok");
  },
};

/* ── 명령 처리 ── */
async function answer(text, env, ctx) {
  const [cmdRaw, ...rest] = text.split(/\s+/);
  const cmd = cmdRaw.replace(/^\//, "").replace(/@\w+$/, "");   // /시세@bot -> 시세
  const arg = rest.join(" ").trim();
  const D = await data(env, ctx);

  if (["help", "start", "도움말"].includes(cmd))
    return "🤖 <b>커버리지 봇</b>\n/시세 에이피알\n/트렌드 티니핑\n/수출 티앤엘\n/일정\n\n종목명만 보내도 시세를 알려줍니다.";
  if (["시세", "주가"].includes(cmd)) return price(D, arg);
  if (["트렌드", "trend"].includes(cmd)) return trend(D, arg);
  if (["수출", "무역"].includes(cmd)) return trade(D, arg);
  if (["일정", "캘린더", "이벤트"].includes(cmd)) return schedule(D);
  // 명령 없이 종목명만 보낸 경우
  const p = price(D, text);
  return p.startsWith("❓") ? "명령을 인식 못했어요. /help 를 보내보세요." : p;
}

function price(D, name) {
  const st = D.LIVE && D.LIVE.stocks || {};
  const key = match(Object.keys(st), name);
  if (!key) return "❓ 종목을 찾지 못했어요: " + name;
  const s = st[key], up = s.chgPct >= 0;
  const per = s.cnsPer > 0 ? s.cnsPer.toFixed(1) + "x" : (s.per > 0 ? s.per.toFixed(1) + "x" : "—");
  return `<b>${key}</b>\n`
    + `${fmt(s.price)}원  ${up ? "🔴+" : "🔵"}${(s.chgPct ?? 0).toFixed(2)}%\n`
    + `시총 ${fmt(Math.round(s.mktcapEok))}억 · 12MF PER ${per} · 외국인 ${s.foreign ?? "—"}%\n`
    + `<i>${(D.LIVE.asOf || "").slice(0, 16)} 기준</i>`;
}

function trend(D, kw) {
  const T = D.TREND && D.TREND.groups || {};
  if (!kw) return "예: /트렌드 티니핑";
  let hit = null, hitName = "";
  for (const [g, obj] of Object.entries(T)) {
    if (g.includes(kw) || (obj.products || []).some(p => p.includes(kw))) { hit = obj; hitName = g; break; }
  }
  if (!hit) return "❓ 트렌드 그룹을 못 찾았어요: " + kw;
  const ser = hit.naver || hit.google || [];
  const rows = (hit.products || []).map((p, i) => {
    const s = (ser[i] || []).filter(v => v != null);
    const last = s.length ? s[s.length - 1] : null;
    const w = s.length > 1 && s[s.length - 2] ? Math.round((s[s.length - 1] / s[s.length - 2] - 1) * 100) : null;
    return { p, last, w };
  }).filter(r => r.last != null).sort((a, b) => b.last - a.last);
  return `<b>📊 ${hitName}</b> <i>(최근값·전주비)</i>\n`
    + rows.map(r => `· ${r.p} <b>${r.last}</b>${r.w == null ? "" : ` (${r.w >= 0 ? "+" : ""}${r.w}%)`}`).join("\n");
}

function trade(D, kw) {
  const items = (D.TRADE && D.TRADE.items) || [];
  if (!kw) return "예: /수출 화장품  |  /수출 창상피복재";
  const it = items.find(i => i.label.includes(kw)) ||
             items.find(i => (i.note || "").includes(kw));
  if (!it) return "❓ 수출 품목을 못 찾았어요: " + kw + "\n(" + items.map(i => i.label).join(", ") + ")";
  const bc = (it.byCountry || [])[0] || { exp: [] };
  const vals = bc.exp.filter(v => v);
  const last = vals.length ? vals[vals.length - 1] : null;
  return `<b>📦 ${it.label}</b> (${bc.name})\n`
    + `최근월 <b>${last ? (last / 1e6).toFixed(1) : "—"}</b> 백만달러\n<i>${it.note || ""}</i>`;
}

function schedule(D) {
  const evs = (D.DART_EVENTS || []).filter(e => ["earn", "ir"].includes(e.type));
  const today = new Date().toISOString().slice(0, 10);
  const soon = evs.filter(e => e.date >= today).sort((a, b) => a.date.localeCompare(b.date)).slice(0, 10);
  if (!soon.length) return "임박한 실적발표·IR 일정이 없어요.";
  return "<b>📅 임박 일정</b>\n" + soon.map(e =>
    `· ${e.date.slice(5)} ${e.type === "earn" ? "📊실적" : "🎤IR"} <b>${e.co}</b>`).join("\n");
}

/* ── 유틸 ── */
function match(names, q) {
  q = (q || "").replace(/\s/g, "");
  if (!q) return null;
  return names.find(n => n.replace(/\s/g, "") === q)
      || names.find(n => n.replace(/\s/g, "").includes(q))
      || names.find(n => q.includes(n.replace(/\s/g, "")));
}
const fmt = v => (v == null || isNaN(v)) ? "—" : Math.round(v).toLocaleString("ko-KR");

let _cache = null, _at = 0;
async function data(env, ctx) {
  if (_cache && Date.now() - _at < TTL * 1000) return _cache;
  const html = await (await fetch(SITE + "/index.html?ts=" + Date.now())).text();
  _cache = {
    LIVE: pick(html, "LIVE", "{"), TREND: pick(html, "TREND", "{"),
    TRADE: pick(html, "TRADE", "{"), DART_EVENTS: pick(html, "DART_EVENTS", "["),
  };
  _at = Date.now();
  return _cache;
}
function pick(html, name, open) {
  const close = open === "{" ? "}" : "]";
  const re = new RegExp("const\\s+" + name + "\\s*=\\s*(\\" + open + "[\\s\\S]*?\\" + close + ");\\n");
  const m = html.match(re);
  if (!m) return null;
  try { return JSON.parse(m[1]); } catch { return null; }
}

async function send(env, chatId, text) {
  await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendMessage`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text: text.slice(0, 4096),
      parse_mode: "HTML", disable_web_page_preview: true }),
  });
}
