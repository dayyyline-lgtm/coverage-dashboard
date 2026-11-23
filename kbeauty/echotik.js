// EchoTik 틱톡샵 미국 공식 샵 일별 수집기 (2026-11-23 · FastMoss 대신 · Pro 요금제)
//
// 쓰는 법 — echotik.live 에 로그인된 크롬 탭(아무 페이지)에서 이 파일을 붙여 넣고:
//   await __ET.run('<샵ID> <샵ID> …')   // 샵 하나에 요청 4건 · 1.5초 간격 · 샵당 약 15초(서버가 느리다)
//   __send('et_'+오늘, __ET.text())      // 받기 서버로(RUNBOOK 1-e 4번) · 없으면 아래 plan/dump
//   __ET.plan()                          // 덤프 덩어리 나누기 → "0-15,15-30,…"
//   __ET.dump(a,b)                       // 본문 <pre> 에 띄운다 → get_page_text → 파일
//   python3 kbeauty/echotik_recv.py <파일들> [--date D]
//
// API(화면이 부르는 것과 같은 주소 · 로그인 토큰 = localStorage 'token'):
//   /api/v1/data/sellers/<ID>/analysis?tag=basic.sales.trending&dateRange=90                         → 'Daily Sales'(판매량) · 'Total Sales'(누적)
//   …&indicator=total_sale_gmv_amt&start_time=&end_time=                                              → 'Daily GMV'(USD)
//   …?tag=basic.video.trending&dateRange=90      → 'Videos'(그날 새 영상) · 'Live Streaming'(그날 라이브)
//   …?tag=basic.influencer.trending&dateRange=90 → 'Video Influencers' · 'Live Influencers'(둘 다 누적 — 하루 차이가 새 크리에이터)
//   ⚠ dateRange 180 은 Pro 도 100004(N/A)다 — 90일이 끝. 매주 받아 이어 붙인다.
//
// 덤프 줄(줄 끝 = CRC32 36진수 · fastmoss.js 와 같은 방식):
//   EH|1|<받은 날 UTC>|<샵 수>
//   T|샵ID|첫날|판매량…|판매액(USD 정수)…|새 영상…|영상 크리에이터 누적…|라이브…|라이브 크리에이터 누적…   (값은 36진수)
//   E|샵ID|사유
//   END|줄 수|앞 줄 전체 CRC
(() => {
  const KEY = '__ET';
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const b36 = n => Math.max(0, Math.round(+n || 0)).toString(36);
  const crc32 = s => { let c, t = crc32.t; if (!t) { t = crc32.t = []; for (let n = 0; n < 256; n++) { c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } }
    c = ~0; const b = new TextEncoder().encode(s); for (let i = 0; i < b.length; i++) c = (c >>> 8) ^ t[(c ^ b[i]) & 0xFF]; return ((~c) >>> 0).toString(36); };
  const load = () => { try { return JSON.parse(sessionStorage.getItem(KEY) || '{}'); } catch (e) { return {}; } };
  const save = b => { try { sessionStorage.setItem(KEY, JSON.stringify(b)); } catch (e) { /* 꽉 참 */ } };
  const tok = () => { const t = localStorage.getItem('token') || ''; return t.startsWith('"') ? JSON.parse(t) : t; };
  const get = async (sid, q) => {
    const r = await fetch('/api/v1/data/sellers/' + sid + '/analysis?' + q, {credentials: 'include', headers: {Accept: 'application/json', Authorization: 'Bearer ' + tok()}});
    return r.json();
  };
  const pick = (j, leg) => (j.data || []).filter(x => x.legend === leg).map(x => [x.axis_x, x.axis_y]);
  const E = window.__ET = {log: []};
  E.grab = async sid => {
    const buf = load(); buf.s = buf.s || {}; buf.err = buf.err || {};
    const a = await get(sid, 'tag=basic.sales.trending&dateRange=90'); await sleep(900);
    const b = await get(sid, 'tag=basic.sales.trending&dateRange=90&indicator=total_sale_gmv_amt&start_time=&end_time='); await sleep(900);
    const c = await get(sid, 'tag=basic.video.trending&dateRange=90'); await sleep(900);
    const d = await get(sid, 'tag=basic.influencer.trending&dateRange=90');
    const codes = [a.code, b.code, c.code, d.code].join('/');
    const S = {u: pick(a, 'Daily Sales'), v: pick(b, 'Daily GMV'), a: pick(c, 'Videos'), l: pick(c, 'Live Streaming'), vi: pick(d, 'Video Influencers'), li: pick(d, 'Live Influencers')};
    if (codes !== '0/0/0/0' || !S.u.length) { buf.err[sid] = 'code ' + codes; save(buf); return sid + ' ERR ' + codes; }
    // 날짜 축을 판매량에 맞춘다(계열마다 날짜가 같다 — 다르면 0)
    const d0 = S.u[0][0], idx = {}; S.u.forEach((x, i) => { idx[x[0]] = i; });
    const col = k => { const o = S.u.map(() => 0); for (const [t, y] of S[k]) if (t in idx && y != null && y !== 'N/A') o[idx[t]] = +y; return o; };
    buf.s[sid] = {d0, u: col('u'), v: col('v'), a: col('a'), vi: col('vi'), l: col('l'), li: col('li')};
    delete buf.err[sid];
    buf.date = new Date().toISOString().slice(0, 10);
    save(buf);
    return sid + ' ok ' + d0 + ' n' + S.u.length;
  };
  E.run = async ids => {
    const L = String(ids).trim().split(/[\s,]+/), have = load().s || {};
    for (const s of L) { if (have[s]) continue; try { E.log.push(await E.grab(s)); } catch (e) { E.log.push(s + ' ERR ' + e.message); } await sleep(1500); }
    E.log.push('DONE'); return E.log.filter(x => /ERR/.test(x)).join(' ; ') || 'all ok ' + L.length;
  };
  E.reset = () => { sessionStorage.removeItem(KEY); return 'cleared'; };
  E.status = () => { const b = load(); return 'shops ' + Object.keys(b.s || {}).length + ' · err ' + Object.keys(b.err || {}).length + ' · ' + (b.date || '-') + ' · login ' + (tok() ? 'yes' : 'no'); };
  E.text = () => E.lines().join('\n') + '\n';
  E.lines = () => {
    const buf = load(), L = [], push = a => { const s = a.join('|'); L.push(s + '|' + crc32(s)); };
    const ids = Object.keys(buf.s || {}).sort();
    push(['EH', 1, buf.date || new Date().toISOString().slice(0, 10), ids.length]);
    for (const id of ids) { const x = buf.s[id]; push(['T', id, x.d0, ...['u', 'v', 'a', 'vi', 'l', 'li'].map(k => x[k].map(b36).join(','))]); }
    for (const id of Object.keys(buf.err || {}).sort()) push(['E', id, String(buf.err[id]).slice(0, 20)]);
    L.push(['END', L.length + 1, crc32(L.join('\n'))].join('|'));
    return L;
  };
  E.plan = max => {
    const L = E.lines(), lim = max || 24000, out = []; let a = 0, c = 0;
    L.forEach((l, i) => { if (c + l.length + 1 > lim && i > a) { out.push(a + '-' + i); a = i; c = 0; } c += l.length + 1; });
    out.push(a + '-' + L.length);
    return out.join(',') + ' · lines ' + L.length + ' · chars ' + L.join('\n').length;
  };
  E.dump = (from, to) => {
    const L = E.lines().slice(from || 0, to);
    document.body.innerHTML = ''; const p = document.createElement('pre'); p.style.whiteSpace = 'pre-wrap'; p.textContent = L.join('\n'); document.body.appendChild(p);
    return 'shown ' + L.length + ' lines';
  };
})();
