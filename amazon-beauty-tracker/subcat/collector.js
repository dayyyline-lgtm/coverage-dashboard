/* 아마존 US 뷰티 세부 카테고리 Top100 수집기 (AMZSUB) — 크롬 탭 안에서 돈다.

   무엇을 하나
     config.json 의 카테고리마다 베스트셀러 1·2쪽(각 50위)을 받고, 화면에 안 그려진 31~50위·81~100위는
     페이지가 스크롤할 때 부르는 지연 로딩 POST(/acp/.../nextPage)를 같은 방식으로 불러 **100위 전부의 제목**을 얻는다.
     제목 맨 앞을 브랜드 사전과 맞춰 한국 브랜드 자리만 덤프로 낸다. 상품 페이지(/dp/)는 한 번도 안 연다.

   왜 크롬 안에서인가
     데이터센터 IP 는 아마존이 막는다(트래커 CLAUDE.md §7). 사용자 PC 크롬은 가정용 IP + 실제 브라우저 쿠키라 통과한다.
     지연 로딩 POST 는 curl_cffi 에선 404 였지만(트래커 §3-1) 페이지와 같은 헤더·본문을 주면 200 이다(2026-10-09 실측:
     한 번에 20개 · 0.45초 · 58KB).

   어떻게 부르나 (예약 작업이 하는 일 — 전체 절차는 subcat/RUNBOOK.md)
     1) www.amazon.com/robots.txt 를 연 새 탭에서:
          const R='https://raw.githubusercontent.com/dayyyline-lgtm/coverage-dashboard/main/amazon-beauty-tracker/subcat/';
          new Function(await (await fetch(R+'collector.js')).text())();
     2) 30~60초마다 window.__AMZSUB.status() — 'done ...' 이 나올 때까지(동시 1개 기준 6~7분)
     3) window.__AMZSUB.plan() 이 '0-160,160-480' 처럼 2.5만 자 안쪽 덩어리를 알려 준다.
        덩어리마다 window.__AMZSUB.dump(a,b) → get_page_text → 파일에 그대로 적는다(줄 끝 공백까지).
     4) ingest.py 가 줄마다 CRC 를 확인한다. 틀린 줄은 ingest 가 알려 주는 window.__AMZSUB.redo('C|53|,…') 로 그 줄들만 다시 띄워 받는다.
     부트스트랩(1)의 반환값은 undefined 가 정상이다 — 이 파일은 즉시 실행 함수라 new Function 쪽으로 값이 안 나온다. status() 로 확인할 것.

   지키는 것
     - 타이머로 쉬지 않는다. 숨은 탭은 setTimeout 이 1분 단위로 묶인다(크롬 집중 절전). 요청 응답을 기다리는 것만으로 속도가 난다.
     - 동시 요청은 config 의 conc(기본 1). 차단 응답(캡차)이 연속 3번이면 멈추고 받은 데까지 덤프한다.
     - 출력에 등호·물음표·앰퍼샌드를 쓰지 않는다 — 크롬 도구가 쿠키·쿼리 문자열로 보고 결과를 가린다.
       카테고리 이름의 '&' 는 전각 '＆' 로 바꿔 내보내고 ingest.py 가 되돌린다.
     - 덤프 줄은 끝났을 때 한 번만 만든다(J.L). 머리줄 시각이 호출마다 바뀌면 END 의 CRC 가 덩어리마다 달라진다(2026-10-09 첫날 실제로 그랬다).

   덤프 줄
     AMZSUB|1|날짜|끝난 시각|성공 카테고리|전체|읽은 자리 수|제목 없는 자리|설정 출처|설정 v|마스터 수
     C|카테고리 번호|자리 수|제목 없는 자리|순위.번호(아는 ASIN) 또는 순위.브랜드.ASIN(처음 보는 것), …|crc
     F|카테고리 번호|실패 사유
     N|카테고리 번호|이름|crc          ← config 에 이름이 비어 있을 때만
     T|ASIN|브랜드 번호|제목(64자)|crc  ← 처음 보는 ASIN 만
     U|ASIN|카테고리 번호|순위|제목|crc ← 사전에 없는데 제목에 Korean·K-beauty 가 들어간 것(최대 30개, 새 브랜드 후보)
     END|줄 수|앞 줄 전체의 crc
*/
(function () {
  'use strict';
  const ROOT = 'https://raw.githubusercontent.com/dayyyline-lgtm/coverage-dashboard/main/amazon-beauty-tracker/';
  const Q = String.fromCharCode(63), E = String.fromCharCode(61), A = String.fromCharCode(38);
  if (window.__AMZSUB && window.__AMZSUB.state === 'run') return;

  const J = window.__AMZSUB = {
    state: 'init', v: 1, t0: Date.now(), done: 0, total: 0, req: 0, posN: 0, notitle: 0,
    fail: {}, blockRun: 0, blocked: false, res: {}, names: {}, newTitles: {}, unk: {}, err: null, cfgSrc: '', L: null,
  };

  /* ---------- 작은 도구 ---------- */
  const CRC_T = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1); t[n] = c >>> 0; } return t; })();
  function crc32(str) { const b = new TextEncoder().encode(str); let c = 0xFFFFFFFF; for (let i = 0; i < b.length; i++) c = CRC_T[(c ^ b[i]) & 0xFF] ^ (c >>> 8); return ((c ^ 0xFFFFFFFF) >>> 0).toString(36); }
  // 덤프에 싣는 글자 — 예약 작업이 get_page_text 결과를 손으로(모델이) 옮겨 적는다. 옮겨 적다 틀리기 쉬운 글자를 미리 평범하게 바꾼다:
  //   줄표·굽은 따옴표 → ASCII, ™®© 와 폭 없는 공백(U+200B 등 — 10/9 첫날 'BERRY UP' 뒤에 숨어 있었다) 삭제, 세로 막대류 → '/'.
  //   자른 뒤 다시 trim — 64자에서 잘려 공백으로 끝나는 줄은 옮겨 적을 때 끝 공백이 사라져 CRC 가 틀린다.
  const clean = (s, n) => String(s || '')
    .replace(/[\u2010-\u2015\u2212]/g, '-').replace(/[\u2018\u2019\u201a\u2032]/g, "'").replace(/[\u201c\u201d\u201e\u2033]/g, '"')
    .replace(/[\u2122\u00ae\u00a9\u200b-\u200f\u2060\ufeff]/g, '').replace(/[\u2502\u3163\uff5c]/g, '/')
    .replace(/[|\r\n\t=&?;]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, n || 90).trim();
  const norm = s => String(s || '').toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '').normalize('NFC')
    .replace(/^[\s\[\(\"'“”‘’【「]+/, '');
  const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

  async function getText(url, init) {
    J.req++;
    const r = await fetch(url, Object.assign({credentials: 'include'}, init || {}));
    const t = await r.text();
    return {status: r.status, text: t};
  }

  function titlesFrom(root) {
    const m = new Map();
    root.querySelectorAll('[id]').forEach(el => {
      const id = el.id;
      if (!/^[A-Z0-9]{10}$/.test(id) || m.has(id)) return;
      const box = el.closest('#gridItemRoot') || el.closest('li') || el;
      const img = box.querySelector('img[alt]');
      let t = img ? img.getAttribute('alt') : '';
      if (!t || !t.trim()) { const a = box.querySelector('a span, a div'); t = a ? a.textContent : ''; }
      if (t && t.trim()) m.set(id, t.trim());
    });
    return m;
  }

  /* ---------- 브랜드 사전 ---------- */
  let PATS = [];
  function buildPats(cfg) {
    const out = [];
    cfg.brands.forEach((b, i) => b[1].forEach(p => {
      const parts = norm(p).split(/[^a-z0-9가-힣]+/).filter(Boolean);
      if (!parts.length) return;
      out.push({i, len: p.length, re: new RegExp('^' + parts.map(esc).join('[^a-z0-9가-힣]*') + '(?![a-z0-9가-힣])')});
    }));
    out.sort((a, b) => b.len - a.len);
    PATS = out;
  }
  function brandOf(title) { const t = norm(title); for (const p of PATS) if (p.re.test(t)) return p.i; return -1; }

  /* ---------- 카테고리 하나 ---------- */
  async function page(id, pg) {
    const base = id === 'beauty' ? '/Best-Sellers/zgbs/beauty' : '/Best-Sellers/zgbs/beauty/' + id;
    const url = pg === 1 ? base : base + Q + '_encoding' + E + 'UTF8' + A + 'pg' + E + '2';
    const g = await getText(url);
    if (/validateCaptcha|api-services-support@amazon\.com/.test(g.text)) return {block: true};
    const doc = new DOMParser().parseFromString(g.text, 'text/html');
    const recsEl = doc.querySelector('[data-client-recs-list]');
    if (!recsEl) return {norecs: true, status: g.status, h1: !!doc.querySelector('h1')};
    const recs = JSON.parse(recsEl.getAttribute('data-client-recs-list'));
    const titles = titlesFrom(doc);
    // 이름: h1 이 둘이다 — 첫째는 늘 'Amazon Best Sellers'(첫날 155개가 전부 이걸로 찍혔다), 둘째가 'Best Sellers in 카테고리'.
    let name = '';
    if (pg === 1) {
      const h = [...doc.querySelectorAll('h1')].map(e => e.textContent.trim()).find(x => /^Best Sellers in /i.test(x));
      const raw = h ? h.replace(/^Best Sellers in /i, '') : (doc.title || '').replace(/^Amazon Best Sellers:\s*(Best\s+)?/i, '');
      name = clean(raw.replace(/&/g, '＆'), 60);
    }
    const miss = recs.filter(r => !titles.has(r.id));
    if (miss.length) {
      const acp = doc.querySelector('[data-acp-params]');
      if (acp) {
        const body = {
          faceoutkataname: recsEl.getAttribute('data-faceoutkataname') || 'GeneralFaceout',
          ids: miss.map(r => JSON.stringify(r)),
          indexes: miss.map(r => recs.indexOf(r)),
          linkparameters: '',
          offset: String(recs.indexOf(miss[0])),
          reftagprefix: recsEl.getAttribute('data-reftag') || ('zg_bs_g_' + id),
        };
        const url2 = acp.getAttribute('data-acp-path') + 'nextPage' + Q + 'page-type' + E + 'zeitgeist' + A + 'stamp' + E + (acp.getAttribute('data-acp-stamp') || Date.now());
        try {
          const g2 = await getText(url2, {method: 'POST', headers: {
            'x-amz-acp-params': acp.getAttribute('data-acp-params'), 'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'text/html, application/json', 'Content-Type': 'application/json', 'x-amz-amabot-click-attributes': 'disable'},
            body: JSON.stringify(body)});
          if (g2.status === 200) titlesFrom(new DOMParser().parseFromString(g2.text, 'text/html')).forEach((t, a) => { if (!titles.has(a)) titles.set(a, t); });
        } catch (e) { /* 제목 없이 남는다 — notitle 로 센다 */ }
      }
    }
    return {recs: recs.map(r => ({a: r.id, r: +r.metadataMap['render.zg.rank'], t: titles.get(r.id) || ''})), name};
  }

  async function oneCat(cfg, i) {
    const id = cfg.cats[i][0];
    const p1 = await page(id, 1);
    if (p1.block) return {fail: 'block'};
    if (p1.norecs) return {fail: 'norecs' + (p1.status || '')};
    let all = p1.recs.slice();
    if (p1.recs.length >= 50) {
      const p2 = await page(id, 2);
      if (p2.block) return {fail: 'block'};
      if (p2.recs) all = all.concat(p2.recs);
      else if (!p2.h1) return {fail: 'p2'};
    }
    return {ok: true, name: p1.name, recs: all};
  }

  function absorb(cfg, i, out, known) {
    const pos = [];
    let nt = 0;
    out.recs.forEach(x => {
      if (!x.t) { nt++; return; }
      const b = brandOf(x.t);
      if (b < 0) {
        // 사전에 없는 한국 브랜드 후보 — 같은 ASIN 은 가장 좋은 순위 하나만
        if (/\bkorean\b|\bk-?beauty\b/i.test(x.t) && (!J.unk[x.a] || J.unk[x.a][1] > x.r)) J.unk[x.a] = [i, x.r, clean(x.t, 64)];
        return;
      }
      pos.push([x.r, b, x.a]);
      if (!(x.a in known) && !J.newTitles[x.a]) J.newTitles[x.a] = [b, clean(x.t, 64)];
    });
    pos.sort((a, b) => a[0] - b[0]);
    J.res[i] = {n: out.recs.length, nt, pos};
    J.posN += out.recs.length; J.notitle += nt;
    // 이름은 config 에 비어 있을 때만 낸다(구분용으로 고쳐 둔 이름 'Face Makeup' 등을 매일 'Face' 로 되돌리지 않게)
    if (out.name && !cfg.cats[i][1]) J.names[i] = out.name;
  }

  async function run() {
    J.state = 'run';
    let cfg = window.__AMZSUB_CFG || null;
    J.cfgSrc = cfg ? 'inline' : 'raw';
    if (!cfg) cfg = await (await fetch(ROOT + 'subcat/config.json')).json();
    // skus.json = 지금까지 본 한국 브랜드 ASIN 목록(번호 = 배열 위치, 맨 뒤에만 붙는다). 아는 ASIN 은 덤프에 번호만 쓴다.
    let master = window.__AMZSUB_KNOWN || null;
    if (!master) { try { master = await (await fetch(ROOT + 'data/subcat/skus.json')).json(); } catch (e) { master = null; } }
    const known = {};
    ((master && master.list) || []).forEach((x, k) => { known[x[0]] = k; });
    J.known = known; J.masterN = Object.keys(known).length;
    J.cfg = cfg; J.total = cfg.cats.length; buildPats(cfg);
    const conc = Math.max(1, Math.min(4, cfg.conc || 1));
    const queue = cfg.cats.map((_, i) => i);
    const retry = [];
    async function worker(list, isRetry) {
      while (list.length && !J.blocked) {
        const i = list.shift();
        let out;
        try { out = await oneCat(cfg, i); } catch (e) { out = {fail: 'err ' + clean(e && e.message, 40)}; }
        if (out.ok) { absorb(cfg, i, out, known); delete J.fail[i]; J.blockRun = 0; J.done++; }
        else {
          J.fail[i] = out.fail;
          if (out.fail === 'block') { J.blockRun++; if (J.blockRun >= 3) J.blocked = true; }
          if (!isRetry) retry.push(i); else J.done++;
        }
      }
    }
    await Promise.all(Array.from({length: conc}, () => worker(queue, false)));
    if (retry.length && !J.blocked) await worker(retry, true);
    else J.done += retry.length;
    finish();
  }

  // 끝난 순간 덤프 줄을 한 번만 만든다 — 이후 dump()·line() 은 전부 이 배열을 쓴다.
  function finish() {
    J.t1 = Date.now();
    J.state = 'done';
    try { J.L = build(); } catch (e) { J.err = clean(e && e.message, 60); J.L = null; }
  }

  /* ---------- 바깥에서 부르는 것 ---------- */
  J.status = () => {
    const ok = Object.keys(J.res).length, f = Object.keys(J.fail).length;
    return [J.state, ok + '/' + J.total, 'fail ' + f, 'req ' + J.req, 'notitle ' + J.notitle,
      J.blocked ? 'BLOCKED' : '', Math.round(((J.t1 || Date.now()) - J.t0) / 1000) + 's', J.err ? 'err ' + J.err : ''].filter(Boolean).join(' · ');
  };
  function build() {
    const L = [], cfg = J.cfg;
    const ok = Object.keys(J.res).length;
    const ts = new Date(J.t1 + 9 * 3600e3).toISOString().slice(0, 19);
    L.push(['AMZSUB', 1, ts.slice(0, 10), ts, ok, J.total, J.posN, J.notitle, J.cfgSrc, cfg.v, J.masterN].join('|'));
    Object.keys(J.res).map(Number).sort((a, b) => a - b).forEach(i => {
      const R = J.res[i];
      // 아는 ASIN = '순위.번호'(번호는 36진수 소문자) · 처음 보는 ASIN = '순위.브랜드.ASIN'(ASIN 은 10자 대문자라 안 헷갈린다)
      const p = R.pos.length ? R.pos.map(x => (x[2] in J.known) ? (x[0] + '.' + J.known[x[2]].toString(36)) : (x[0] + '.' + x[1].toString(36) + '.' + x[2])).join(',') : '-';
      const s = ['C', i, R.n, R.nt, p].join('|');
      L.push(s + '|' + crc32(s));
    });
    Object.keys(J.fail).map(Number).sort((a, b) => a - b).forEach(i => L.push(['F', i, clean(J.fail[i], 30)].join('|')));
    Object.keys(J.names).map(Number).sort((a, b) => a - b).forEach(i => { const s = ['N', i, J.names[i]].join('|'); L.push(s + '|' + crc32(s)); });
    Object.keys(J.newTitles).sort().forEach(a => { const x = J.newTitles[a]; const s = ['T', a, x[0].toString(36), x[1]].join('|'); L.push(s + '|' + crc32(s)); });
    Object.keys(J.unk).sort((a, b) => J.unk[a][1] - J.unk[b][1]).slice(0, 30).forEach(a => {
      const x = J.unk[a]; const s = ['U', a, x[0], x[1], x[2]].join('|'); L.push(s + '|' + crc32(s));
    });
    L.push(['END', L.length + 1, crc32(L.join('\n'))].join('|'));
    return L;
  }
  J.lines = () => (J.state === 'done' ? J.L : null);
  // 2.5만 자 안쪽 덩어리의 줄 범위 — 'a-b,b-c' (b 는 포함 안 함). get_page_text 한 번에 읽기 좋은 크기.
  J.plan = (max) => {
    const L = J.lines();
    if (!L) return 'not done · ' + J.status();
    const lim = max || 25000, out = [];
    let a = 0, c = 0;
    L.forEach((l, i) => { if (c + l.length + 1 > lim && i > a) { out.push(a + '-' + i); a = i; c = 0; } c += l.length + 1; });
    out.push(a + '-' + L.length);
    return out.join(',') + ' · lines ' + L.length + ' · chars ' + L.join('\n').length;
  };
  // 덤프는 본문을 덤프 텍스트로 바꾼다 → get_page_text 로 읽는다. 길면 plan() 의 범위대로 나눠 읽는다.
  J.dump = (from, to) => {
    const L = J.lines();
    if (!L) return 'not done · ' + J.status();
    const a = from || 0, b = Math.min(L.length, to || L.length);
    J.text = L.slice(a, b).join('\n');
    document.title = 'amzsub dump';
    document.body.innerHTML = '';
    const pre = document.createElement('pre');
    pre.id = 'amzsub';
    pre.style.whiteSpace = 'pre-wrap';
    pre.textContent = J.text;
    document.body.appendChild(pre);
    return 'dumped · lines ' + a + '-' + (b - 1) + ' of ' + L.length + ' · chars ' + J.text.length;
  };
  J.line = n => { const L = J.lines(); return L ? (L[n] || '') : ''; };
  // ingest.py 가 CRC 틀린 줄의 키(C|53| · T|B0…|)를 알려 주면 그 줄들만 본문에 다시 띄운다 → get_page_text → 파일 하나 더
  J.redo = keys => {
    const L = J.lines();
    if (!L) return 'not done · ' + J.status();
    const ks = String(keys || '').split(',').filter(Boolean);
    const pick = L.filter(l => ks.some(k => l.startsWith(k)));
    J.text = pick.join('\n');
    document.title = 'amzsub redo';
    document.body.innerHTML = '';
    const pre = document.createElement('pre');
    pre.id = 'amzsub'; pre.style.whiteSpace = 'pre-wrap'; pre.textContent = J.text;
    document.body.appendChild(pre);
    return 'redo · lines ' + pick.length + ' of keys ' + ks.length;
  };

  run().catch(e => { J.err = clean(e && e.message, 60); if (J.cfg) finish(); else { J.state = 'done'; J.t1 = Date.now(); } });
  return 'started';
})();
