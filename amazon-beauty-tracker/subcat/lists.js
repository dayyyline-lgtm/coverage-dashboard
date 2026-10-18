/* 아마존 7개국 뷰티 Top100 수집기 (AMZL) — 크롬 탭 안에서 돈다 (2026-10-18 · PC 트래커를 대신한다).

   무엇을 하나
     지금 탭이 열려 있는 나라 아마존(미·영·독·프·이·스·일)의 'Best Sellers in Beauty' 1·2쪽을 받고, 화면에 안 그려진
     31~50위·81~100위 제목은 지연 로딩 POST 로 받아 100위 전부의 제목을 얻는다(collector.js 와 같은 방법).
     제목 맨 앞을 브랜드 사전(config.json brands — 미국 세부 카테고리와 같은 사전)과 맞춰 한국 브랜드 자리만 덤프로 낸다.
     나라당 요청 4건(1쪽 · POST · 2쪽 · POST). 상품 페이지(/dp/)는 열지 않는다.

   왜 이걸로 바꿨나
     PC 트래커(curl_cffi)는 매일·나라마다 쿠키 없이 새로 접속해 첫 요청에서 로봇 확인을 자주 맞았다(9/19~10/18 30일 중 7개국 다
     받은 날 6일). 사용자 결정(2026-10-18): 고치지 말고 아침 예약 작업(크롬)으로 옮긴다. 크롬은 쿠키가 남아 다음 날부터는 이어서 들어간다.
     10/18 시험: 영·독·스·일은 첫 요청에 통과, 처음 가 본 프랑스·이탈리아는 첫 요청이 막혔고 몇 분 뒤 다시 치니 통과.

   부르는 법 (아침 예약 작업 — subcat/RUNBOOK.md '1-b')
     그 나라 아마존의 robots.txt 를 연 탭에서(미국은 세부 카테고리 수집을 마친 같은 탭):
       const R='https://raw.githubusercontent.com/dayyyline-lgtm/coverage-dashboard/main/amazon-beauty-tracker/subcat/';
       new Function(await (await fetch(R+'lists.js')).text())(); await window.__AMZL.run()
     → 덤프 글이 그대로 돌아온다(처음 보는 ASIN 이 없으면 수백 자). 파일 /tmp/amzl/<나라>.txt 에 한 글자도 바꾸지 말고 적는다.
     머리줄 상태가 block 이면 다른 나라를 다 돈 뒤 같은 줄로 한 번 더(결과는 <나라>_2.txt). 옮겨 적다 틀렸으면(lists.py 가 CRC 로 알려 준다)
     그 나라 탭에서 window.__AMZL.again() — 다시 받지 않고 탭 세션에 남겨 둔 글을 다시 준다.

   지키는 것
     - 1쪽이 막히면 2쪽은 안 친다(차단을 키우지 않게). 재시도는 바깥(아침 절차)이 모든 나라를 돈 뒤 한 번만.
     - 출력에 등호·물음표·앰퍼샌드·세미콜론을 쓰지 않는다 — 크롬 도구가 쿼리 문자열로 보고 결과를 가린다.
     - 가격은 안 받는다(순위만). 통화 쿠키도 안 건드린다.

   덤프 줄 (CRC = CRC32(마지막 '|crc' 앞까지, UTF-8) 36진수)
     AMZL|1|날짜|끝난 시각|나라|상태|읽은 자리|제목 있는 자리|끝 순위|config v|마스터 수|crc
          상태 ok(100위까지 제목 거의 다) · part(2쪽이 막혔거나 제목 빠진 자리가 많음) · block(1쪽 로봇 확인) · norecs(페이지 모양이 바뀜)
     K|나라|순위.번호(아는 ASIN) 또는 순위.브랜드.ASIN(처음 보는 것),…|crc     ('-' = 한국 브랜드 없음 · 번호·브랜드는 36진수)
     T|ASIN|브랜드 번호|제목 64자|crc            ← 처음 보는 ASIN 만(마스터 = data/lists/skus.json)
     U|나라|ASIN|순위|제목 64자|crc             ← 사전에 없는데 제목에 Korean·K-beauty 류가 들어간 것(최대 10, 새 브랜드 후보)
     END|줄 수|앞 줄 전체 crc
*/
(function () {
  'use strict';
  const ROOT = 'https://raw.githubusercontent.com/dayyyline-lgtm/coverage-dashboard/main/amazon-beauty-tracker/';
  const Q = String.fromCharCode(63), E = String.fromCharCode(61), A = String.fromCharCode(38);
  const HOST = {'www.amazon.com': 'US', 'www.amazon.co.uk': 'UK', 'www.amazon.de': 'DE', 'www.amazon.fr': 'FR',
    'www.amazon.it': 'IT', 'www.amazon.es': 'ES', 'www.amazon.co.jp': 'JP'};
  // 일본 표기(트래커 scraper.BRAND_ALIASES 에서 옮김) — 이 브라우저는 일본 아마존 제목을 영어로 주지만 설정이 바뀌면 가나로 온다
  const JP_ALIAS = {
    'medicube': ['メディキューブ'], 'biodance': ['バイオダンス'], "d'alba": ['ダルバ'], 'beauty of joseon': ['ビューティーオブジョソン'],
    'anua': ['アヌア'], 'melaxin': ['メラキシン'], 'purito': ['ピュリト', 'プリト'], 'coreana': ['コリアナ'], 'cosrx': ['コスアールエックス'],
    'laneige': ['ラネージュ'], 'innisfree': ['イニスフリー'], 'tirtir': ['ティルティル'], 'laka': ['ラカ'], 'round lab': ['ラウンドラボ'],
    'torriden': ['トリデン'], 'numbuzin': ['ナンバーズイン'], 'abib': ['アビブ'], 'celimax': ['セリマックス'], 'manyo': ['魔女工場', 'マニョ'],
    'clio': ['クリオ'], 'goodal': ['グーダル'], 'missha': ['ミシャ'], 'vt': ['ブイティコスメティックス', 'ブイティコスメテックス', 'ブイティー'],
    'mediheal': ['メディヒール'], 'mixsoon': ['ミクスーン'], 'tocobo': ['トコボ'], 'isntree': ['イズントゥリー'],
    'some by mi': ['サムバイミー'], 'rom&nd': ['ロムアンド'],
  };
  const J = window.__AMZL = window.__AMZL || {};
  J.v = 1;

  /* ---------- 작은 도구 (collector.js 와 같다) ---------- */
  const CRC_T = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1); t[n] = c >>> 0; } return t; })();
  function crc32(str) { const b = new TextEncoder().encode(str); let c = 0xFFFFFFFF; for (let i = 0; i < b.length; i++) c = CRC_T[(c ^ b[i]) & 0xFF] ^ (c >>> 8); return ((c ^ 0xFFFFFFFF) >>> 0).toString(36); }
  const clean = (s, n) => String(s || '')
    .replace(/[‐-―−]/g, '-').replace(/[‘’‚′]/g, "'").replace(/[“”„″]/g, '"')
    .replace(/[™®©​-‏⁠﻿]/g, '').replace(/[│ㅣ｜]/g, '/')
    .replace(/[|\r\n\t=&?;]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, n || 90).trim();
  // 영문·숫자·한글·가나·한자 — 일본 제목의 브랜드 표기까지 낱말로 본다
  const W = 'a-z0-9ㄱ-ㆎ가-힣ぁ-ゖァ-ヺー一-鿿';
  const CJK = /[ぁ-ゖァ-ヺー一-鿿]$/;
  // 맞추기 전 제목 다듬기 — 악센트 제거. 맨 앞 꼬리표는 두 가지로 본다: ① 괄호만 떼고 안은 남김([Mizon] → mizon]…, 미국 수집기와 같다)
  // ② 꼬리표째 뗌(【公式】·[2 Pack]·(Official) → 그 뒤). 브랜드가 꼬리표 안에 있기도 밖에 있기도 해서 둘 다 맞춰 본다.
  const base = s => String(s || '').toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '').normalize('NFC');
  const normT = s => base(s).replace(/^[\s"'“”‘’\[【「(（〔]+/, '');
  const normX = s => base(s).replace(/^(?:\s*[\[【「(（〔][^\]】」)）〕]{0,24}[\]】」)）〕])+/, '')
    .replace(/^[\s"'“”‘’]+/, '');
  const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

  let PATS = [];
  function buildPats(cfg) {
    const out = [];
    cfg.brands.forEach((b, i) => {
      b[1].concat(JP_ALIAS[String(b[0]).toLowerCase()] || []).forEach(p => {
        const n = normT(p);
        const parts = n.split(new RegExp('[^' + W + ']+')).filter(Boolean);
        if (!parts.length) return;
        // 가나·한자로 끝나는 표기는 뒤에 띄어쓰기가 없다(メディキューブゼロ毛穴…) — 낱말 경계를 안 본다
        const tail = CJK.test(parts[parts.length - 1]) ? '' : '(?![' + W + '])';
        out.push({i, len: p.length, re: new RegExp('^' + parts.map(esc).join('[^' + W + ']*') + tail)});
      });
    });
    out.sort((a, b) => b.len - a.len);
    PATS = out;
  }
  const brandOf = t => { for (const n of [normT(t), normX(t)]) for (const p of PATS) if (p.re.test(n)) return p.i; return -1; };
  const HINT = /korea|corea|coreen|k-?beauty|韓国|한국/;   // korean·koreanisch·coreano·coréen·k-beauty·韓国·한국

  async function getText(url, init) {
    const r = await fetch(url, Object.assign({credentials: 'include'}, init || {}));
    return {status: r.status, text: await r.text()};
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

  /* ---------- 한 쪽 (50자리) ---------- */
  async function page(pg) {
    const base = '/gp/bestsellers/beauty';
    const url = pg === 1 ? base : base + Q + '_encoding' + E + 'UTF8' + A + 'pg' + E + '2';
    const g = await getText(url);
    if (/validateCaptcha|api-services-support@amazon/.test(g.text)) return {block: true};
    const doc = new DOMParser().parseFromString(g.text, 'text/html');
    const recsEl = doc.querySelector('[data-client-recs-list]');
    if (!recsEl) return {norecs: true, status: g.status};
    const recs = JSON.parse(recsEl.getAttribute('data-client-recs-list'));
    const titles = titlesFrom(doc);
    const miss = recs.filter(r => !titles.has(r.id));
    if (miss.length) {
      const acp = doc.querySelector('[data-acp-params]');
      if (acp) {
        const body = {
          faceoutkataname: recsEl.getAttribute('data-faceoutkataname') || 'GeneralFaceout',
          ids: miss.map(r => JSON.stringify(r)), indexes: miss.map(r => recs.indexOf(r)), linkparameters: '',
          offset: String(recs.indexOf(miss[0])), reftagprefix: recsEl.getAttribute('data-reftag') || 'zg_bs_g_beauty',
        };
        const url2 = acp.getAttribute('data-acp-path') + 'nextPage' + Q + 'page-type' + E + 'zeitgeist' + A + 'stamp' + E + (acp.getAttribute('data-acp-stamp') || Date.now());
        try {
          const g2 = await getText(url2, {method: 'POST', headers: {
            'x-amz-acp-params': acp.getAttribute('data-acp-params'), 'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'text/html, application/json', 'Content-Type': 'application/json', 'x-amz-amabot-click-attributes': 'disable'},
            body: JSON.stringify(body)});
          if (g2.status === 200) titlesFrom(new DOMParser().parseFromString(g2.text, 'text/html')).forEach((t, a) => { if (!titles.has(a)) titles.set(a, t); });
        } catch (e) { /* 제목 없이 남는다 — 상태 part 로 잡힌다 */ }
      }
    }
    return {recs: recs.map(r => ({a: r.id, r: +r.metadataMap['render.zg.rank'], t: titles.get(r.id) || ''}))};
  }

  /* ---------- 한 나라 ---------- */
  J.run = async function (mkArg) {
    const t0 = Date.now();
    const mk = mkArg || HOST[location.host];
    if (!mk || HOST[location.host] !== mk) return 'error · 이 탭(' + location.host + ')은 ' + (mkArg || '?') + ' 아마존이 아니다';
    let cfg = window.__AMZSUB_CFG || null;
    if (!cfg) cfg = await (await fetch(ROOT + 'subcat/config.json')).json();
    let master = null;
    // 마스터는 아침마다 바뀐다 — CDN 이 옛것(또는 없던 때의 404)을 주지 않게 매번 새 주소로
    try { master = await (await fetch(ROOT + 'data/lists/skus.json' + Q + 'v' + E + Date.now(), {cache: 'no-store'})).json(); } catch (e) { master = null; }
    const known = {};
    ((master && master.list) || []).forEach((x, k) => { known[x[0]] = k; });
    const masterN = Object.keys(known).length;
    buildPats(cfg);

    let status = 'ok', all = [];
    const p1 = await page(1);
    if (p1.block) status = 'block';
    else if (p1.norecs) status = 'norecs';
    else {
      all = p1.recs.slice();
      const max1 = all.reduce((m, x) => Math.max(m, x.r || 0), 0);
      if (all.length >= 45 || max1 >= 45) {
        const p2 = await page(2);
        if (p2.recs) {
          const seen = new Set(all.map(x => x.a));
          all = all.concat(p2.recs.filter(x => !seen.has(x.a) && x.r > max1));
        } else status = 'part';
      }
    }
    const titled = all.filter(x => x.t).length;
    const maxr = all.reduce((m, x) => Math.max(m, x.r || 0), 0);
    if (status === 'ok' && (maxr < 95 || titled < all.length - 5)) status = 'part';

    const pos = [], newT = {}, unk = [];
    all.sort((a, b) => a.r - b.r).forEach(x => {
      if (!x.t) return;
      const b = brandOf(x.t);
      if (b < 0) { if (HINT.test(normT(x.t)) && unk.length < 10) unk.push([x.a, x.r, clean(x.t, 64)]); return; }
      pos.push(x.r + '.' + ((x.a in known) ? known[x.a].toString(36) : (b.toString(36) + '.' + x.a)));
      if (!(x.a in known) && !newT[x.a]) newT[x.a] = [b, clean(x.t, 64)];
    });

    const ts = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 19);
    const L = [];
    const add = s => L.push(s + '|' + crc32(s));
    add(['AMZL', 1, ts.slice(0, 10), ts.slice(11, 16), mk, status, all.length, titled, maxr, cfg.v, masterN].join('|'));
    if (status === 'ok' || status === 'part') {
      add(['K', mk, pos.length ? pos.join(',') : '-'].join('|'));
      Object.keys(newT).sort().forEach(a => add(['T', a, newT[a][0].toString(36), newT[a][1]].join('|')));
      unk.forEach(u => add(['U', mk, u[0], u[1], u[2]].join('|')));
    }
    L.push(['END', L.length + 1, crc32(L.join('\n'))].join('|'));
    const text = L.join('\n');
    const sum = [mk, status, 'read ' + all.length, 'titled ' + titled, 'kpos ' + pos.length, 'new ' + Object.keys(newT).length,
      'lines ' + L.length, 'chars ' + text.length, Math.round((Date.now() - t0) / 100) / 10 + 's'].join(' · ');
    J.last = {mk, text, sum};
    try { sessionStorage.setItem('amzl_last', JSON.stringify(J.last)); } catch (e) { /* 저장이 막혀도 결과는 그대로 보여 준다 */ }
    show(text);
    return sum;
  };
  // 결과를 본문에 띄운다 → get_page_text 로 읽는다. javascript_tool 의 반환값은 1천 자 남짓에서 잘린다(10/18 실측).
  function show(text) {
    document.title = 'amzl dump';
    document.body.innerHTML = '';
    const pre = document.createElement('pre');
    pre.id = 'amzl'; pre.style.whiteSpace = 'pre-wrap'; pre.textContent = text;
    document.body.appendChild(pre);
  }
  // 옮겨 적다 틀렸을 때 — 다시 받지 않고 이 탭 세션에 남겨 둔 마지막 결과를 본문에 다시 띄운다(같은 나라 탭이어야 한다)
  J.again = function () {
    let x = J.last;
    if (!x) { try { x = JSON.parse(sessionStorage.getItem('amzl_last') || 'null'); } catch (e) { x = null; } }
    if (!x || !x.text) return 'none';
    show(x.text);
    return x.sum || 'shown';
  };
  J._t = {normT, buildPats, brandOf: t => brandOf(t), crc32, clean};    // 시험용(node 로 사전 매칭을 돌려 본다)
})();
