/* ══ 삼립 해외(코스트코) 추적 — 종목 페이지 손익 탭 `#spSamlip` (2026-11-17) ════════════════════════════════
   사용자 "삼립 좀더 데이터 자세하게 따보고 대시보드에도". 재료는 셋이다.
     ① TRADE  관세청 케이크(1905901030) 나라별 · 시흥 190590 — fetch_trade.py 가 매달 저절로 갱신(이 칸도 따라 바뀐다)
     ② SAMLIP 크롬으로 모은 것 — 코스트코 매장(Warehouse Runner·WarehouseHawk) · DART 판관비 주석 · 회사 발표. 손으로 갱신
     ③ 분기 손익은 ISM(공통 엔진 · 부문 BAKERY·FOOD·유통·기타)이 이 칸 위에서 따로 그린다
   컨테이너 환산 = (미국+캐나다 케이크 중량 − 코스트코 전 기준선) ÷ 1대 중량(캐나다향 선하증권 11.6t).
   회사가 말한 '월 25컨테이너'와 3~10월 평균 23대가 맞아 이 환산을 쓴다 — 중량은 TRADE 의 금액 ÷ 단가(달러/kg).
   ⚠ 케이크 국가별은 다른 한국 업체 물량이 섞인 업계 합계다. 시흥은 6자리라 비스킷류가 섞이고 나라 구분이 없다. */
function renderSamlip(host){
  if(!host||typeof SAMLIP==="undefined") return;
  const S=SAMLIP, T=(typeof TRADE!=="undefined"&&TRADE.items)?TRADE:null;
  const css=k=>getComputedStyle(document.documentElement).getPropertyValue(k).trim();
  const C={ink:css("--text"), mut:css("--muted"), line:css("--line"), acc:css("--accent")||"#d8b46a", sky:"#6fa8dc", ter:"#e07a5f", sage:"#81b29a", slate:"#9aa5b1", up:css("--up"), down:css("--down")};
  const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  const pc=v=>v==null||!isFinite(v)?"—":`<span class="${v>0?"up":v<0?"down":"flat"}">${v>0?"+":""}${Math.round(v)}%</span>`;
  const usd=v=>v==null?"—":"$"+(v/1e6).toFixed(2)+"M";
  const ym=m=>`${m.slice(2,4)}.${m.slice(4,6)}`;
  const M=T?T.months:[];
  const item=lbl=>T?T.items.find(i=>i.label===lbl):null;
  const cake=item("케이크"), shg=item("케이크·빵(시흥)");
  const bc=(it,code)=>it?(it.byCountry.find(b=>b.code===code)||null):null;
  const US=bc(cake,"US"), CA=bc(cake,"CA"), SH=shg?shg.byCountry[0]:null;
  const ex=(c,i)=>c&&c.exp?c.exp[i]:null;
  // 중량(t) = 금액 ÷ 단가 — 단가가 비면 그 달은 모름(0 달러면 0t)
  const wt=(c,i)=>{ const e=ex(c,i); if(e==null) return null; if(e===0) return 0; const a=c.asp&&c.asp[i]; return a?e/a/1000:null; };
  const B=S.cont.base, baseUsd=(B.usK+B.caK)*1000, baseT=B.usT+B.caT, kgC=S.cont.kg;
  const contOf=i=>{ const a=wt(US,i), b=wt(CA,i); if(a==null&&b==null) return null; return ((a||0)+(b||0)-baseT)*1000/kgC; };
  const yoyAt=(c,i)=>{ const a=ex(c,i), b=i>=12?ex(c,i-12):null; return a!=null&&b?(a/b-1)*100:null; };
  const lastI=(()=>{ for(let i=M.length-1;i>=0;i--) if(ex(US,i)!=null) return i; return -1; })();
  const fx=(typeof amzFx==="function"?amzFx():1380);

  let h=`<div class="sub-h" style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">삼립 해외(코스트코) 추적 <span class="th-sub" style="display:inline">관세청 ${lastI>=0?ym(M[lastI])+"까지":"—"} · 코스트코 매장 ${esc(S.costco.asOf.slice(5).replace("-","/"))} · 회사 발표</span></div>`;

  // ── KPI 4칸 ──────────────────────────────────────────────
  if(lastI>=0){
    const c3=[lastI-2,lastI-1,lastI].map(contOf).filter(v=>v!=null), c3a=c3.length?c3.reduce((a,b)=>a+b,0)/c3.length:null;
    const ytd=(c,y)=>{ let s=0,n=0; M.forEach((m,i)=>{ if(m.slice(0,4)===y&&+m.slice(4)<=+M[lastI].slice(4)&&ex(c,i)!=null){ s+=ex(c,i); n++; } }); return n?s:null; };
    const yy=M[lastI].slice(0,4), py=String(+yy-1), u1=ytd(US,yy), u0=ytd(US,py);
    const it=S.costco.items[0], g=S.glob.q[S.glob.q.length-1];
    h+=`<div class="kpis" style="margin:4px 0 10px">
      <div class="kpi"><div class="k">미국 케이크 수출 · ${ym(M[lastI])}</div><div class="v">${usd(ex(US,lastI))}</div><div class="g" style="font-size:11.5px">전년 ${pc(yoyAt(US,lastI))} · 1~${+M[lastI].slice(4)}월 ${usd(u1)} (${pc(u0?(u1/u0-1)*100:null)})</div></div>
      <div class="kpi"><div class="k">기준선 초과 · 컨테이너 환산</div><div class="v">${contOf(lastI)==null?"—":Math.round(contOf(lastI))}<small>대/월</small></div><div class="g" style="font-size:11.5px">최근 3개월 평균 ${c3a==null?"—":Math.round(c3a)}대 · 회사 '25 → 50대'</div></div>
      <div class="kpi"><div class="k">시흥 빵·케이크(190590) · ${ym(M[lastI])}</div><div class="v">${usd(ex(SH,lastI))}</div><div class="g" style="font-size:11.5px">전년 ${pc(yoyAt(SH,lastI))} · 삼립 제조지 프록시</div></div>
      <div class="kpi"><div class="k">코스트코 치즈케이크 판매 중</div><div class="v">${it.act}<small>곳</small></div><div class="g" style="font-size:11.5px">재고 있음 ${it.in} · 판매 이력 ${it.ever}곳 · 글로벌 매출 ${g[0].slice(2).replace("Q","년 ")}Q ${g[1]}억</div></div>
    </div>`;
  }

  // ── ① 월별 수출 막대(미국·캐나다) + 기준선 · ② 컨테이너 환산 ─────────────
  h+=`<div class="sub-h" style="margin-top:8px">케이크(1905901030) 미국·캐나다 월별 수출 <span class="th-sub" style="display:inline">백만 달러 · 점선 = 코스트코 전 기준선(25년 1~8월 평균 $${(baseUsd/1e6).toFixed(2)}M) · 업계 합계</span></div>
    <div style="display:flex;gap:14px;flex-wrap:wrap;font-size:11.5px;color:var(--muted2);margin:0 0 4px"><span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${C.acc};margin-right:4px"></span>미국</span><span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${C.sky};margin-right:4px"></span>캐나다</span><span><span style="display:inline-block;width:14px;border-top:2px dashed ${C.mut};margin-right:4px;vertical-align:middle"></span>기준선</span></div>
    <div id="slExp"></div>
    <div class="sub-h" style="margin-top:14px">기준선 초과 물량 · 컨테이너 환산 <span class="th-sub" style="display:inline">대/월 · (미국+캐나다 중량 − 기준선 ${baseT}t) ÷ ${(kgC/1000).toFixed(1)}t · 붉은 점선 = 회사 '기존 25대' · 주황 = '50대'</span></div>
    <div id="slCont"></div>
    <p class="note" style="margin-top:4px">1대 중량 = ${esc(S.cont.bl)}. 회사가 말한 '월 25컨테이너'(17일 보도)와 3~10월 환산 평균이 맞는다. 50대가 되면 미국+캐나다 케이크 수출이 기준선 위로 월 약 $${(50*kgC/1000*7.2/1e3).toFixed(1)}M(kg당 $7.2) 더해진다 — 원화 약 ${Math.round(50*kgC*7.2*fx/1e8)}억/월(오늘 환율).</p>`;

  // ── ③ 분기 — 회사 글로벌 매출 vs 관세청 ─────────────────────
  const qOf=m=>`${m.slice(0,4)}Q${Math.floor((+m.slice(4)-1)/3)+1}`;
  const qAgg=(c)=>{ const o={}; M.forEach((m,i)=>{ const v=ex(c,i); if(v==null) return; const q=qOf(m); o[q]=o[q]||{s:0,n:0}; o[q].s+=v; o[q].n++; }); return o; };
  const qU=qAgg(US), qC=qAgg(CA), qS=qAgg(SH), G={}; S.glob.q.forEach(([q,v])=>G[q]=v);
  const qAll=[...new Set([...Object.keys(qU),...Object.keys(G)])].filter(q=>q>="2025Q1").sort();
  const showQ=qAll.filter(q=>(typeof is25Get==="function"&&is25Get())||!q.startsWith("2025"));
  const qPrev=q=>`${+q.slice(0,4)-1}Q${q.slice(-1)}`;
  const qv=(o,q)=>o[q]?o[q].s:null, part=(o,q)=>o[q]&&o[q].n<3;
  const cellQ=(o,q,f)=>{ const v=qv(o,q); return v==null?`<td class="g">—</td>`:`<td>${f(v)}${part(o,q)?` <span class="g">(${o[q].n}개월)</span>`:""}</td>`; };
  const yoyQ=(o,q)=>{ const a=qv(o,q), b=qv(o,qPrev(q)); return (a!=null&&b&&!part(o,q))?(a/b-1)*100:null; };
  const usca=q=>({s:(qv(qU,q)||0)+(qv(qC,q)||0), n:Math.max((qU[q]||{}).n||0,(qC[q]||{}).n||0)});
  const qUC={}; qAll.forEach(q=>{ if(qU[q]||qC[q]) qUC[q]=usca(q); });
  h+=`<div class="sub-h" style="margin-top:14px;display:flex;align-items:center;gap:10px">분기 — 회사 글로벌 매출 vs 관세청 수출 <span class="th-sub" style="display:inline">글로벌 = 회사 발표(억원) · 관세청 = 백만 달러 · 진행 중 분기는 (n개월)</span>${typeof is25Btn==="function"?`<span style="margin-left:auto">${is25Btn()}</span>`:""}</div>
    <div class="tbl-wrap"><table class="mini-tbl"><thead><tr><th class="l">구분</th>${showQ.map(q=>`<th class="ye">${q.slice(-1)}Q${q.slice(2,4)}</th>`).join("")}</tr></thead><tbody>
    <tr><td class="l">글로벌 매출(회사 · 억원)</td>${showQ.map(q=>G[q]!=null?`<td><b>${G[q]}</b></td>`:`<td class="g">${q==="2025Q4"||q<"2025Q3"?"미공개":"—"}</td>`).join("")}</tr>
    <tr class="sub-row"><td class="l">└ 전년비</td>${showQ.map(q=>`<td>${G[q]!=null&&G[qPrev(q)]?pc((G[q]/G[qPrev(q)]-1)*100):"—"}</td>`).join("")}</tr>
    <tr><td class="l">시흥 190590 ($M)</td>${showQ.map(q=>cellQ(qS,q,v=>(v/1e6).toFixed(1))).join("")}</tr>
    <tr class="sub-row"><td class="l">└ 전년비</td>${showQ.map(q=>`<td>${pc(yoyQ(qS,q))}</td>`).join("")}</tr>
    <tr><td class="l">케이크 미국+캐나다 ($M)</td>${showQ.map(q=>cellQ(qUC,q,v=>(v/1e6).toFixed(1))).join("")}</tr>
    <tr class="sub-row"><td class="l">└ 전년비</td>${showQ.map(q=>`<td>${pc(yoyQ(qUC,q))}</td>`).join("")}</tr>
    </tbody></table></div>
    <p class="note">회사 글로벌 매출(1~9월 ${S.glob.m9_2026}억 · 전년 +${S.glob.yoy9}%)은 시흥 수출(원화)의 약 1.7~2배다 — 다른 사업장 물량·운임 포함 판매가·미국 외 나라가 더해진다. 방향은 같이 본다(25년 상반기는 합계 ${S.glob.h1_2025}억만 공개 · 목표 ${esc(S.glob.target)}).</p>`;

  // ── ④ 코스트코 매장 ─────────────────────────────────────
  const CO=S.costco, R=CO.reg, RC=[C.acc, C.sky, "#eda100", C.slate, C.ter];
  h+=`<div class="sub-h" style="margin-top:14px">미국 코스트코 매장 — 삼립 품목 <span class="th-sub" style="display:inline">${esc(CO.asOf)} 크롬 수집 · 손으로 갱신</span></div>
    <div class="tbl-wrap"><table class="mini-tbl"><thead><tr><th class="l">품목(코스트코 번호)</th><th>판매 중</th><th>재고 있음</th><th>판매 이력</th><th>최저가</th><th class="l">첫 관측</th><th class="l">가격</th></tr></thead><tbody>
    ${CO.items.map(x=>`<tr><td class="l">${esc(x.n)} <span class="g">#${esc(x.id)}</span></td><td><b>${x.act}</b>곳</td><td>${x.in!=null?x.in+"곳":"—"}</td><td>${x.ever?x.ever+"곳":"—"}</td><td>${x.min?`<span class="down">${esc(x.min)}</span>`:"—"}</td><td class="l">${esc(x.first)}</td><td class="l g">${esc(x.price)}</td></tr>`).join("")}
    </tbody></table></div>
    <p class="note" style="margin-top:2px">${esc(CO.src)}</p>
    <div style="display:flex;gap:12px;flex-wrap:wrap;font-size:11.5px;color:var(--muted2);margin:10px 0 6px">${R.cols.map((c,i)=>`<span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${RC[i]};margin-right:4px"></span>${esc(c)}</span>`).join("")}</div>
    <div style="display:grid;grid-template-columns:auto 1fr auto;gap:6px 10px;align-items:center;font-size:12px">
    ${R.rows.map(([nm,v])=>{ const n=v.reduce((a,b)=>a+b,0); return `<div style="color:var(--text);white-space:nowrap">${esc(nm)}</div>
      <div style="display:flex;height:18px;border-radius:4px;overflow:hidden;background:var(--panel2)">${v.map((x,i)=>x?`<div title="${esc(nm)} · ${esc(R.cols[i])} ${x}곳" style="width:${(x/n*100).toFixed(2)}%;background:${RC[i]};display:flex;align-items:center;justify-content:center;color:${i===0?"var(--onacc)":"#1b1c1f"};font-size:10.5px;font-weight:600;border-right:1px solid var(--panel)">${x>=6?x:""}</div>`:"").join("")}</div>
      <div class="g" style="white-space:nowrap">${n}곳</div>`; }).join("")}
    </div>
    <p class="note" style="margin-top:6px">${esc(R.src)}</p>
    <div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.4fr);gap:18px;align-items:start;margin-top:6px">
      <div><div style="font-size:12.5px;font-weight:700;margin:4px 0 6px">.97 할인 관측 매장 · 월별</div><div id="slMd"></div><p class="note" style="margin-top:2px">${esc(CO.md.note)}</p></div>
      <div><div style="font-size:12.5px;font-weight:700;margin:4px 0 6px">읽는 법</div><ul style="margin:0;padding-left:18px;font-size:12.5px;line-height:1.6;color:var(--text)">${CO.read.map(t=>`<li>${esc(t)}</li>`).join("")}</ul></div>
    </div>`;

  // ── ⑤ 판관비 세부(DART 주석) ─────────────────────────────
  const SG=S.sga, sgCols=SG.q.map((q,i)=>[q,i]).filter(([q])=>q>="2024Q3"&&((typeof is25Get==="function"&&is25Get())||!q.startsWith("2025")));
  const sgYoY=(row,i)=>{ const j=SG.q.indexOf(qPrev(SG.q[i])); return j>=0&&row[j]?(row[i]/row[j]-1)*100:null; };
  h+=`<div class="sub-h" style="margin-top:14px;display:flex;align-items:center;gap:10px">판관비 세부 — 수출·유통 비용 <span class="th-sub" style="display:inline">DART 연결 주석 · 억원 · 분기(4Q = 연간 − 3Q 누적)</span>${typeof is25Btn==="function"?`<span style="margin-left:auto">${is25Btn()}</span>`:""}</div>
    <div class="tbl-wrap"><table class="mini-tbl"><thead><tr><th class="l">항목</th>${sgCols.map(([q])=>`<th class="ye">${q.slice(-1)}Q${q.slice(2,4)}</th>`).join("")}</tr></thead><tbody>
    ${SG.rows.map(([nm,row])=>`<tr><td class="l">${esc(nm)}</td>${sgCols.map(([q,i])=>`<td>${row[i]==null?"—":row[i]}</td>`).join("")}</tr>
      <tr class="sub-row"><td class="l">└ 전년비</td>${sgCols.map(([q,i])=>`<td>${pc(sgYoY(row,i))}</td>`).join("")}</tr>`).join("")}
    </tbody></table></div>
    <p class="note">${esc(SG.note)}</p>`;

  // ── ⑥ 연표 ────────────────────────────────────────────
  h+=`<details class="fold" style="margin-top:10px"><summary>회사 발표 연표 · 출처</summary><div style="padding:6px 2px 2px">
      <ul style="margin:0;padding-left:18px;font-size:12.5px;line-height:1.7">${S.facts.map(([d,t])=>`<li><b>${esc(d)}</b> ${esc(t)}</li>`).join("")}</ul>
      <p class="note">${esc(S.note)} 케이크 국가별은 다른 한국 업체도 섞인 업계 합계다(2026 증가분의 97%가 미국·캐나다). 시흥은 수출 화주 소재지 기준 6자리(190590)라 비스킷 등이 섞이고 나라 구분이 없다.</p></div></details>`;

  host.innerHTML=h;
  if(typeof is25Bind==="function") is25Bind(host, ()=>renderSamlip(host));
  if(lastI<0) return;

  // ── 차트: 월별 수출(쌓은 막대) ─────────────────────────────
  const n=M.length, box1=host.querySelector("#slExp");
  const W=Math.max(320, box1.clientWidth||860), H=230, P={l:44,r:14,t:16,b:26};
  const tot=i=>(ex(US,i)||0)+(ex(CA,i)||0);
  const ymax=Math.max(baseUsd*1.2, ...M.map((m,i)=>tot(i)))/1e6;
  const st=[0.5,1,2,5].find(v=>ymax/v<=6)||5, top=Math.ceil(ymax/st)*st;
  const sx=i=>P.l+(i+0.5)*(W-P.l-P.r)/n, bw=Math.max(4,(W-P.l-P.r)/n*0.68), sy=v=>H-P.b-v/top*(H-P.t-P.b);
  let s=`<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" font-family="inherit" role="img" aria-label="케이크 미국·캐나다 월별 수출">`;
  for(let v=0; v<=top+1e-9; v+=st){ const y=sy(v).toFixed(1); s+=`<line x1="${P.l}" y1="${y}" x2="${W-P.r}" y2="${y}" stroke="${C.line}"/><text x="${P.l-6}" y="${(+y+3).toFixed(1)}" text-anchor="end" font-size="10" fill="${C.mut}">$${v}M</text>`; }
  M.forEach((m,i)=>{ const u=(ex(US,i)||0)/1e6, c=(ex(CA,i)||0)/1e6, x=(sx(i)-bw/2).toFixed(1);
    if(u) s+=`<rect x="${x}" y="${sy(u).toFixed(1)}" width="${bw.toFixed(1)}" height="${(sy(0)-sy(u)).toFixed(1)}" fill="${C.acc}"/>`;
    if(c) s+=`<rect x="${x}" y="${sy(u+c).toFixed(1)}" width="${bw.toFixed(1)}" height="${(sy(u)-sy(u+c)).toFixed(1)}" fill="${C.sky}"/>`;
    if(+m.slice(4)===1||i===0||i===n-1) s+=`<text x="${sx(i).toFixed(1)}" y="${H-P.b+14}" text-anchor="middle" font-size="10" fill="${C.mut}">${ym(m)}</text>`;
    if(+m.slice(4)===1&&i>0) s+=`<line x1="${(sx(i)-(W-P.l-P.r)/n/2).toFixed(1)}" y1="${P.t}" x2="${(sx(i)-(W-P.l-P.r)/n/2).toFixed(1)}" y2="${H-P.b}" stroke="${C.line}" stroke-dasharray="2 3"/>`; });
  const by=sy(baseUsd/1e6).toFixed(1);
  s+=`<line x1="${P.l}" y1="${by}" x2="${W-P.r}" y2="${by}" stroke="${C.mut}" stroke-dasharray="5 4" stroke-width="1.4"/>`;
  // 고점 하나에만 값
  let pk=0; M.forEach((m,i)=>{ if(tot(i)>tot(pk)) pk=i; });
  s+=`<text x="${sx(pk).toFixed(1)}" y="${(sy(tot(pk)/1e6)-4).toFixed(1)}" text-anchor="middle" font-size="10.5" font-weight="700" fill="${C.ink}">$${(tot(pk)/1e6).toFixed(1)}M</text></svg>`;
  box1.innerHTML=s;
  if(typeof attachChartTip==="function") attachChartTip(box1,{W,H,pad:P,n,xOf:sx,
    xLab:i=>ym(M[i]), yLab:Y=>"$"+(invLin(sy,Y)).toFixed(2)+"M",
    pts:i=>[{y:sy(tot(i)/1e6),c:C.ink}],
    html:i=>`<b>${M[i].slice(0,4)}년 ${+M[i].slice(4)}월</b><br>미국 ${usd(ex(US,i))} <span class="g">(전년 ${pc(yoyAt(US,i))})</span><br>캐나다 ${usd(ex(CA,i))}<br>합계 ${usd(tot(i))} · 기준선 대비 ${tot(i)-baseUsd>=0?"+":"−"}$${(Math.abs(tot(i)-baseUsd)/1e6).toFixed(2)}M<br><span class="g">시흥 190590 ${usd(ex(SH,i))}</span>`});

  // ── 차트: 컨테이너 환산 ─────────────────────────────────
  const box2=host.querySelector("#slCont"), i0=Math.max(0,M.indexOf("202509"));
  const idx=M.map((m,i)=>i).filter(i=>i>=i0), cv=idx.map(contOf);
  const W2=Math.max(320, box2.clientWidth||860), H2=190, P2={l:44,r:14,t:12,b:26}, n2=idx.length;
  const lo=Math.min(-15,...cv.filter(v=>v!=null)), hi=Math.max(55,...cv.filter(v=>v!=null));
  const sx2=k=>P2.l+(k+0.5)*(W2-P2.l-P2.r)/n2, bw2=Math.max(6,(W2-P2.l-P2.r)/n2*0.62), sy2=v=>P2.t+(hi-v)/(hi-lo)*(H2-P2.t-P2.b);
  let s2=`<svg viewBox="0 0 ${W2} ${H2}" width="100%" height="${H2}" font-family="inherit" role="img" aria-label="기준선 초과 물량 컨테이너 환산">`;
  [-10,0,10,20,30,40,50].filter(v=>v>=lo&&v<=hi).forEach(v=>{ const y=sy2(v).toFixed(1); s2+=`<line x1="${P2.l}" y1="${y}" x2="${W2-P2.r}" y2="${y}" stroke="${C.line}"${v===0?' stroke-width="1.4"':""}/><text x="${P2.l-6}" y="${(+y+3).toFixed(1)}" text-anchor="end" font-size="10" fill="${C.mut}">${v}대</text>`; });
  cv.forEach((v,k)=>{ if(v==null) return; const y0=sy2(0), y1=sy2(v), x=(sx2(k)-bw2/2).toFixed(1);
    s2+=`<rect x="${x}" y="${Math.min(y0,y1).toFixed(1)}" width="${bw2.toFixed(1)}" height="${Math.abs(y0-y1).toFixed(1)}" fill="${v<0?C.slate:C.acc}" fill-opacity="${v<0?0.55:1}"/>`;
    s2+=`<text x="${sx2(k).toFixed(1)}" y="${H2-P2.b+14}" text-anchor="middle" font-size="10" fill="${C.mut}">${ym(M[idx[k]])}</text>`; });
  [[25,"#e34948"],[50,"#eb6834"]].forEach(([v,c])=>{ if(v>hi) return; const y=sy2(v).toFixed(1); s2+=`<line x1="${P2.l}" y1="${y}" x2="${W2-P2.r}" y2="${y}" stroke="${c}" stroke-dasharray="5 4" stroke-width="1.4"/><text x="${W2-P2.r-2}" y="${(+y-4).toFixed(1)}" text-anchor="end" font-size="10" fill="${c}">${v}대</text>`; });
  s2+=`</svg>`; box2.innerHTML=s2;
  if(typeof attachChartTip==="function") attachChartTip(box2,{W:W2,H:H2,pad:P2,n:n2,xOf:sx2,
    xLab:k=>ym(M[idx[k]]), yLab:Y=>Math.round(invLin(sy2,Y))+"대",
    pts:k=>cv[k]==null?[]:[{y:sy2(cv[k]),c:C.ink}],
    html:k=>{ const i=idx[k], a=wt(US,i), b=wt(CA,i); return `<b>${M[i].slice(0,4)}년 ${+M[i].slice(4)}월</b><br>환산 <b>${cv[k]==null?"—":Math.round(cv[k])+"대"}</b><br><span class="g">미국 ${a==null?"—":Math.round(a)+"t"} · 캐나다 ${b==null?"—":Math.round(b)+"t"} · 기준선 ${baseT}t</span>`; }});

  // ── 차트: 할인 관측 월별(작은 막대 · 진행 중 달은 옅게) ───────────────
  const box3=host.querySelector("#slMd"), MD=CO.md.m;
  const W3=Math.max(220, box3.clientWidth||360), H3=150, P3={l:30,r:8,t:16,b:24}, n3=MD.length, mx=Math.max(...MD.map(x=>x[1]));
  const sx3=k=>P3.l+(k+0.5)*(W3-P3.l-P3.r)/n3, bw3=Math.min(34,(W3-P3.l-P3.r)/n3*0.6), sy3=v=>H3-P3.b-v/mx*(H3-P3.t-P3.b);
  let s3=`<svg viewBox="0 0 ${W3} ${H3}" width="100%" height="${H3}" font-family="inherit" role="img" aria-label="월별 할인 관측 매장 수">`;
  MD.forEach(([m,v],k)=>{ const part=m===CO.md.partial;
    s3+=`<rect x="${(sx3(k)-bw3/2).toFixed(1)}" y="${sy3(v).toFixed(1)}" width="${bw3.toFixed(1)}" height="${(sy3(0)-sy3(v)).toFixed(1)}" fill="${C.ter}" fill-opacity="${part?0.4:1}"${part?` stroke="${C.ter}" stroke-dasharray="3 2"`:""}/>`
      +`<text x="${sx3(k).toFixed(1)}" y="${(sy3(v)-4).toFixed(1)}" text-anchor="middle" font-size="10.5" fill="${C.ink}">${v}곳</text>`
      +`<text x="${sx3(k).toFixed(1)}" y="${H3-P3.b+14}" text-anchor="middle" font-size="10" fill="${C.mut}">${m.slice(2).replace("-",".")}${part?"(진행)":""}</text>`; });
  s3+=`<line x1="${P3.l}" y1="${sy3(0)}" x2="${W3-P3.r}" y2="${sy3(0)}" stroke="${C.line}"/></svg>`;
  box3.innerHTML=s3;
}
