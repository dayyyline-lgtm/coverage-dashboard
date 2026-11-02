/* ══════════ GC녹십자웰빙 분기 손익 모델 (2026-11-02 · GCWBMODEL ← gcwb_block.py · renderGcwbModel) ══════════
   사용자: "25년부터 DART 뜯어서 자세히 모델링 — 대시보드에도". 종목 페이지 손익 탭(#spIsm 자리).
   매출 = 라이넥(물량 × 공급가 · 9월부터 +20%) + IV 고용량(27년 2Q 허가 가정) + 기타 제품(영양주사제 등) + 상품 + 자회사·조정(연결 − 별도)
   매출총이익 = 라이넥 물량 × Lm + 판가 인상분(원가 없음) + 기타 제품 × Om + (상품 + 자회사) × Gm + 4Q 조정
     — Lm·Om·Gm 은 1Q25~2Q26 여섯 분기 회귀(라이넥 65% 고정 · 기타 제품 78% · 상품·자회사 17%). 오차 ±10억 안쪽.
   판관비 = 성격별: 인건비·임차·연구개발·판촉 = 전년 동기 × 증가율(고정비) · 지급수수료 = 상품 × 9.5% + 보령 코프로모션 · 운반비 = 매출 × 1.25%
   3Q26 = 잠정실적(매출·영업이익·순이익) — 판관비는 위 식 추정(≈), 매출총이익은 영업이익 + 판관비 역산(≈), 라이넥은 영업이익에 맞춘 역산(가정 칸 L3). */
const GCWB_DEF={Lm:65, Om:78.4, Gm:17.1, q4:-0.8, price:20, L3:14.5, L4g:5, L27g:8, iv3:0.8, iv4:1.7, oth26:-15, oth27:0, gd4:30, gd27:12, sb27:10,
  feeR:9.5, frR:1.25, hr26:6, hr27:8, ad26:22, ad27:10, rnd27:10, pe:12, ini:3.0};
let gcwbOpen; try{ gcwbOpen=JSON.parse(localStorage.getItem("gcwbOpen")||"{}"); }catch(e){ gcwbOpen={}; }
function gcwbAsmGet(){ try{ return JSON.parse(localStorage.getItem("gcwbAsm")||"{}")||{}; }catch(e){ return {}; } }
function gcwbAsmSave(a){ try{ localStorage.setItem("gcwbAsm",JSON.stringify(a)); }catch(e){} }
const GCWB_SGL=[["hr","인건비(급여·퇴직·복리·교육)"],["ad","광고선전비"],["fee","지급수수료"],["fr","운반비"],["rent","임차료"],["rnd","경상연구개발비"],
  ["promo","판촉(업무촉진·견본·접대·회의)"],["misc","그 밖(여비·상각·외주용역·대손 등)"]];
function gcwbBuild(){
  const G=typeof GCWBMODEL!=="undefined"?GCWBMODEL:null; if(!G||!G.q) return null;
  const U=gcwbAsmGet(), A={...GCWB_DEF}; Object.keys(U).forEach(k=>{ if(U[k]!=null&&isFinite(U[k])) A[k]=+U[k]; });
  const pc=k=>A[k]/100, Q={}, COLS=["2025Q1","2025Q2","2025Q3","2025Q4","2026Q1","2026Q2","2026Q3","2026Q4","2027Q1","2027Q2","2027Q3","2027Q4"];
  const sgOf=s=>{ if(!s) return null; const o={hr:s.hr,ad:s.ad,fee:s.fee,fr:s.fr,rent:s.rent,rnd:s.rnd,promo:s.promo,misc:(s.trv||0)+(s.etc||0)+(s.dep||0)+(s.out||0)+(s.bad||0)}; o.tot=s.tot; return o; };
  Object.keys(G.q).forEach(k=>{ const d=G.q[k]; const o={q:k, act:true, rev:d.rev, gp:d.gp, sga:d.sga, op:d.op, nonop:d.oi-d.oe, fin:d.fi-d.fc, eq:d.eq, pbt:d.pbt, tax:d.tax, np:d.np,
      L:d.L, Lv:d.L, Lp:0, iv:0, oth:d.prod!=null?d.prod-d.L:null, goods:d.goods, sub:d.sep!=null?d.rev-d.sep:null, sg:sgOf(d.sg), ut:d.ut, inv:d.inv};
    Q[k]=o; });
  const P3=G.p&&G.p["2026Q3"], boryung={"2026Q4":0.15,"2027Q1":0.3,"2027Q2":0.36,"2027Q3":0.45,"2027Q4":0.54};
  // 3Q26 — 잠정실적 + 구성 추정
  { const Lv=A.L3, Lp=Lv/3*pc("price"), oth=Q["2025Q3"].oth*(1+pc("oth26")), sub=3.5;
    Q["2026Q3"]={q:"2026Q3", act:false, ir:true, rev:P3.rev, op:P3.op, np:P3.np, Lv, Lp, iv:0, L:Lv+Lp, oth, sub, goods:P3.rev-Lv-Lp-oth-sub, est:{gp:1,sga:1,mix:1}}; }
  { const b=Q["2025Q4"], Lv=b.L*(1+pc("L4g")), Lp=Lv*pc("price");
    Q["2026Q4"]={q:"2026Q4", act:false, Lv, Lp, iv:0, L:Lv+Lp, oth:b.oth*(1+pc("oth26")), goods:b.goods*(1+pc("gd4")), sub:3.19}; }
  const v26=["2026Q1","2026Q2","2026Q3","2026Q4"].reduce((s,k)=>s+Q[k].Lv,0), sh=["2025Q1","2025Q2","2025Q3","2025Q4"].map(k=>Q[k].L), t25=sh.reduce((a,b)=>a+b,0);
  ["2027Q1","2027Q2","2027Q3","2027Q4"].forEach((k,i)=>{ const b=Q[`2026Q${i+1}`], Lv=v26*(1+pc("L27g"))*sh[i]/t25, Lp=Lv*pc("price"), iv=i===2?A.iv3:i===3?A.iv4:0;
    Q[k]={q:k, act:false, Lv, Lp, iv, L:Lv+Lp+iv, oth:b.oth*(1+pc("oth27")), goods:b.goods*(1+pc("gd27")), sub:b.sub*(1+pc("sb27"))}; });
  COLS.slice(6).forEach((k,j)=>{ const o=Q[k], y=k.slice(0,4), b=Q[`${+y-1}${k.slice(4)}`].sg, f=y==="2026";
    if(o.rev==null) o.rev=o.L+o.oth+o.goods+o.sub;
    o.gpM=o.Lv*pc("Lm")+o.Lp+o.iv*pc("Lm")+o.oth*pc("Om")+(o.goods+o.sub)*pc("Gm")+(k.endsWith("Q4")?A.q4:0);
    const sg={hr:b.hr*(1+pc(f?"hr26":"hr27")), ad:b.ad*(1+pc(f?"ad26":"ad27")), rent:b.rent*(f?1.2:1.05), rnd:b.rnd*(f?1:1+pc("rnd27")), promo:b.promo*1.05, misc:b.misc*(f?1.1:1.05),
      fee:o.goods*pc("feeR")+(boryung[k]||0), fr:o.rev*pc("frR")};
    sg.tot=GCWB_SGL.reduce((s,[kk])=>s+sg[kk],0); o.sg=sg; o.sga=sg.tot;
    if(o.ir){ o.gp=o.op+o.sga; o.gpRes=o.gp-o.gpM; } else { o.gp=o.gpM; o.op=o.gp-o.sga; }
    o.nonop=k.endsWith("Q4")?-0.5:-0.15; o.fin=-1.15; o.eq=y==="2026"?-1.1:-0.9;
    if(!o.ir){ const pre=o.op+o.nonop+o.fin; o.tax=pre*0.22; o.pbt=pre+o.eq; o.np=pre-o.tax+o.eq; } });
  // 지분법·파생 제외 순이익 — 실적 분기는 금융손익 대신 이자만(2025 분기 0.78 · 2026 1.13 = 반기 이자비용 ÷ 2): 1Q26 CB 파생 평가손 98억 같은 출렁임을 뺀다
  COLS.forEach(k=>{ const o=Q[k], fc=o.act?(k.startsWith("2025")?-0.78:-1.13):o.fin; o.core=(o.op+o.nonop+fc)*(1-0.22); });
  const Y={};
  { const q4=["2024Q1","2024Q2","2024Q3","2024Q4"].map(k=>Q[k]).filter(Boolean);   // 2025A YoY 용(표에는 안 보인다)
    if(q4.length===4) Y["2024"]={q:"2024", yr:true, act:true, rev:q4.reduce((a,o)=>a+o.rev,0), op:q4.reduce((a,o)=>a+o.op,0)}; }
  ["2025","2026","2027"].forEach(y=>{ const qs=COLS.filter(k=>k.startsWith(y)).map(k=>Q[k]), s=key=>qs.reduce((a,o)=>a+(o[key]||0),0);
    const sg={}; GCWB_SGL.forEach(([kk])=>{ sg[kk]=qs.reduce((a,o)=>a+((o.sg||{})[kk]||0),0); });
    Y[y]={q:y, yr:true, act:y==="2025", rev:s("rev"), L:s("L"), Lv:s("Lv"), Lp:s("Lp"), iv:s("iv"), oth:s("oth"), goods:s("goods"), sub:s("sub"), gp:s("gp"), sga:s("sga"), op:s("op"),
      nonop:s("nonop"), fin:s("fin"), eq:s("eq"), np:s("np"), core:s("core"), sg}; });
  return {Q, Y, COLS, A, G};
}
function renderGcwbModel(host){
  if(!host) return;
  let B=null; try{ B=gcwbBuild(); }catch(e){ console.error("녹십자웰빙 모델", e); }
  if(!B){ host.innerHTML=""; return; }
  const {Q, Y, COLS, A, G}=B, name="녹십자웰빙";
  const f1=v=>(v==null||!isFinite(v))?"—":fmt(v,1), f2=v=>(v==null||!isFinite(v))?"—":fmt(v,2);
  const pc=v=>(v==null||!isFinite(v))?"—":`<span class="${cls(v)}">${sign(v*100,0)}%</span>`;
  const chg=(c,b)=>(c==null||b==null||!(b>0))?"—":pc(c/b-1);
  const cols=COLS.map(k=>Q[k]).concat(["2025","2026","2027"].map(y=>Y[y]));
  const nextQ="2026Q4";
  const lab=o=>o.yr?`${o.q}${o.act?"A":"E"}`:`${c2QLab(o.q)}${o.act?"":o.ir?"P":"E"}`;
  const prevOf=o=>o.yr?Y[String(+o.q-1)]:Q[`${+o.q.slice(0,4)-1}${o.q.slice(4)}`];
  const LS=(typeof LIVE!=="undefined"&&LIVE.stocks&&LIVE.stocks[name])||{}, mc=LS.mktcapEok?LS.mktcapEok/10:null;
  const open={rev:true, sga:false, ...gcwbOpen};
  const ROWS=[
    {t:"매출액", k:"rev", em:1, tg:"rev"}, {t:"YoY", r:"yoy"},
    {t:"라이넥", g:"rev", k:"L", tip:o=>o.act?"DART '주요 제품 등에 관한 사항' 라이넥주 매출(누적 차분)":o.ir?`영업이익 ${f1(o.op)}에 맞춘 역산 — 물량 ${f2(o.Lv)} + 9월 인상분 ${f2(o.Lp)}`:""},
    {t:"· 물량(판가 제외)", g:"rev", k:"Lv", sm:1, tip:o=>o.act?"":o.q==="2026Q4"?`4Q25 × (1${A.L4g>=0?"+":""}${A.L4g}%) — 2Q·3Q 급증분 일부 되돌림 가정`:o.q.startsWith("2027")?`2026 물량 합 × (1+${A.L27g}%) × 2025 분기 비중`:""},
    {t:"· 판가 인상분", g:"rev", k:"Lp", sm:1, tip:o=>o.act?"":`물량 × ${A.price}% — 원가 없음(전액 매출총이익)`},
    {t:"· IV 고용량", g:"rev", k:"iv", sm:1},
    {t:"기타 제품(영양주사제 등)", g:"rev", k:"oth", tip:o=>o.act?"별도 매출실적 제품(전문의약품+기타) − 라이넥":""},
    {t:"상품", g:"rev", k:"goods", tip:o=>o.act?"별도 매출실적 상품(전문의약품·건기식·기타)":o.ir?"잠정 매출 − 라이넥 − 기타 제품 − 자회사(역산)":""},
    {t:"자회사·조정(연결 − 별도)", g:"rev", k:"sub", sm:1},
    {t:"매출총이익", k:"gp", em:1, est:"gp"}, {t:"매출총이익률", p:o=>o.gp/o.rev, sub:1, est:"gp"},
    {t:"판매비와관리비", k:"sga", tg:"sga", est:"sga"}, {t:"판관비율", p:o=>o.sga/o.rev, sub:1, est:"sga"},
    ...GCWB_SGL.map(([k,t])=>({t, g:"sga", v:o=>o.sg?o.sg[k]:null, rp:1})),
    {t:"영업이익", k:"op", em:1}, {t:"영업이익률", p:o=>o.op/o.rev, sub:1}, {t:"YoY", r:"opyoy"},
    {t:"기타손익 + 금융손익", v:o=>o.nonop+o.fin, tip:o=>o.act?"1Q26 금융비용 98억 = CB 전환권 파생상품 평가손 · 2Q26 되돌림":o.ir?"":"이자 분기 11.5억(2Q26 이자비용 11.8억) · 파생 평가손익 0"},
    {t:"지분법손익(이니바이오)", k:"eq", tip:o=>o.act?"":"이니바이오 손실 × 지분율 — 2026 분기 −11억(1H26 실적) · 2027 −9억"},
    {t:"순이익", k:"np", em:1},
    {t:"지분법·파생 제외 순이익", k:"core", sub:1, tip:()=>"(영업이익 + 기타손익 + 금융손익) × (1 − 22%) — 밸류에이션 기준"},
    {t:"PER(현재 시총 · 지분법·파생 제외)", r:"per"},
  ];
  const valOf=(o,r)=>{
    if(r.r==="yoy") return {h:chg(o.rev,(prevOf(o)||{}).rev)};
    if(r.r==="opyoy") return {h:chg(o.op,(prevOf(o)||{}).op)};
    if(r.r==="per") return {h:(o.yr&&mc&&o.core>0)?`${fmt(mc/o.core,1)}배`:""};
    if(r.p){ const v=r.p(o), ap=o.est&&r.est&&o.est[r.est]?"≈":""; return {h:(v==null||!isFinite(v))?"—":`${ap}${fmt(v*100,1)}%`}; }
    const v=r.v?r.v(o):o[r.k];
    if(v==null||!isFinite(v)) return {h:"—"};
    const pct=r.rp&&o.rev?`<span class="g" style="font-size:10.5px"> ${fmt(v/o.rev*100,1)}%</span>`:"";
    const ap=(o.est&&r.est&&o.est[r.est])||(o.ir&&(r.rp||(r.g==="rev"&&r.k!=="rev")))?"≈":"";
    const tip=r.tip?r.tip(o):"";
    return {h:ap+(r.sm||r.rp?f2(v):f1(v))+pct, tip};
  };
  const yrEdge=i=>i>0&&(cols[i].yr!==cols[i-1].yr||(!cols[i].yr&&cols[i].q.slice(0,4)!==cols[i-1].q.slice(0,4)));
  const th=cols.map((o,i)=>`<th style="${yrEdge(i)?"border-left:2px solid var(--line);":""}${o.q===nextQ?"background:color-mix(in srgb, var(--accent) 14%, transparent);":""}">${lab(o)}</th>`).join("");
  const body=ROWS.filter(r=>!r.g||open[r.g]).map(r=>{
    const tog=r.tg?`<span data-gcwbtg="${r.tg}" style="cursor:pointer;color:var(--muted);margin-right:4px">${open[r.tg]?"▾":"▸"}</span>`:"";
    const sub=r.sub||!!r.r||!!r.g;
    return `<tr${r.em?' style="font-weight:800"':""}><td class="l" style="${r.g?"padding-left:22px;":""}${sub?"color:var(--muted);font-size:11.5px;":""}">${tog}${attr(r.t)}</td>`
      +cols.map((o,i)=>{ const v=valOf(o,r), shade=o.q===nextQ?"background:color-mix(in srgb, var(--accent) 8%, transparent);":"";
        return `<td style="${yrEdge(i)?"border-left:2px solid var(--line);":""}${shade}${r.em?"border-top:1px solid var(--line);border-bottom:1px solid var(--line);":""}${r.sm?"font-size:11px;color:var(--muted);":""}"${v.tip?` title="${attr(v.tip)}"`:""}>${v.h}</td>`; }).join("")+`</tr>`; }).join("");
  // 공장·재고 — 공시 가동률(시간 기준)과 생산 수량은 방향이 다를 수 있다(1H26 시간당 생산량 1.5배)
  const AQ=COLS.slice(0,6);
  const plant=`<div class="tbl-wrap" style="margin-top:10px"><table class="mini-tbl ism-t"><thead><tr><th class="l">공장·재고</th>${AQ.map(k=>`<th>${c2QLab(k)}</th>`).join("")}</tr></thead><tbody>
    <tr><td class="l">라이넥 YoY</td>${AQ.map(k=>{ const p=G.q[`${+k.slice(0,4)-1}${k.slice(4)}`]; return `<td>${p&&p.L?chg(G.q[k].L,p.L):"—"}</td>`; }).join("")}</tr>
    <tr><td class="l">앰플 가동률(시간)</td>${AQ.map(k=>`<td>${Q[k].ut?fmt(Q[k].ut.amp*100,1)+"%":"—"}</td>`).join("")}</tr>
    <tr><td class="l">바이알 가동률(시간)</td>${AQ.map(k=>`<td>${Q[k].ut?fmt(Q[k].ut.vial*100,1)+"%":"—"}</td>`).join("")}</tr>
    <tr><td class="l">재고자산(십억)</td>${AQ.map(k=>`<td>${Q[k].inv!=null?f1(Q[k].inv):"—"}</td>`).join("")}</tr>
    <tr><td class="l">재고 YoY</td>${AQ.map(k=>{ const p=G.q[`${+k.slice(0,4)-1}${k.slice(4)}`]; return `<td>${p&&p.inv!=null&&Q[k].inv!=null?chg(Q[k].inv,p.inv):"—"}</td>`; }).join("")}</tr>
  </tbody></table></div>
  <p class="note" style="margin-top:4px">가동률 = 충전 부문 실제 ÷ 가동 가능 시간(누적 공시 → 분기 차분 · 허가용 생산 제외) — 1H26 앰플 생산 수량은 +16% 인데 시간은 −28%(시간당 생산량 9.7 → 15.6천개) · 생산능력(연 앰플 37.8백만·바이알 27.7백만개)은 24~26년 그대로</p>`;
  const card=(t,v,sub)=>`<div style="flex:1;min-width:170px;background:var(--panel);border:1px solid var(--line-soft);border-radius:var(--radius);padding:12px 14px">
    <div style="font-size:11.5px;color:var(--muted);font-weight:700">${t}</div><div style="font-size:19px;font-weight:800;margin-top:3px">${v}</div>
    <div style="font-size:11px;color:var(--muted2);margin-top:3px;line-height:1.45">${sub||""}</div></div>`;
  const cn=LS.cons||{}, cy={}, cq={};
  ((cn.year||{}).series||[]).forEach(x=>{ if(x.e) cy[x.k.slice(0,4)]=x; });
  ((cn.quarter||{}).series||[]).forEach(x=>{ if(x.e) cq[`${x.k.slice(0,4)}Q${Math.ceil(+x.k.slice(4,6)/3)}`]=x; });
  const vs=(o,c)=>c&&c.op>0?`네이버 컨센 ${f1(c.rev)} / ${f1(c.op)} 대비 영업이익 ${pc(o.op/c.op-1)}`:`이익률 ${fmt(o.op/o.rev*100,1)}%`;
  const q4=Q[nextQ], y6=Y["2026"], y7=Y["2027"], cb=G.cb, sh=cb.shares, shD=sh+cb.left/cb.px*1000;   // 백만주 · CB 잔여 ÷ 전환가
  const fair=y7.core*A.pe+A.ini, perSh=fair/sh*1000, perShD=fair/shD*1000;   // 십억 · 원
  const px=LS.price||null;
  const head=`<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px">
    ${card("4Q26E 매출 / 영업이익", `${f1(q4.rev)} / ${f1(q4.op)}`, `${vs(q4,cq["2026Q4"])}<br>판가 3개월 ${f2(q4.Lp)} · 4Q 판관비 ${f1(q4.sga)}(4Q25 ${f1(Q["2025Q4"].sga)})`)}
    ${card("2026E 매출 / 영업이익", `${f1(y6.rev)} / ${f1(y6.op)}`, vs(y6,cy["2026"]))}
    ${card("2027E 매출 / 영업이익", `${f1(y7.rev)} / ${f1(y7.op)}`, `이익률 ${fmt(y7.op/y7.rev*100,1)}% · 판가 연중 ${f1(y7.Lp)} · IV ${f1(y7.iv)}`)}
    ${card(`적정 시총(27E × ${A.pe}배)`, `${fmt0(fair*10)}억`, `지분법·파생 제외 순이익 ${f1(y7.core)} × ${A.pe} + 이니바이오 ${f1(A.ini)} · 주당 ${fmt0(perSh)}원(CB ${fmt(cb.left,0)}십억 전환 시 ${fmt0(perShD)}원)${px?` · 현재가 ${fmt0(px)}원 대비 ${pc(perSh/px-1)}`:""}`)}
  </div>`;
  const r3=Q["2026Q3"];
  const method=`<div class="note" style="margin-top:6px;line-height:1.75">
    <b>매출총이익</b> 라이넥 물량 × ${A.Lm}% + 판가 인상분 100% + 기타 제품 × ${A.Om}% + (상품 + 자회사) × ${A.Gm}% + 4Q ${f1(A.q4)} — 1Q25~2Q26 회귀(4Q 조정은 4Q25 −1.6 의 절반 · 4Q24 는 오히려 이익률이 높았다)
    <br><b>왜 이익률이 떨어졌나</b> 상품 매출이 1Q26 +92% · 2Q26 +62%(이익률 약 17% · 지급수수료 9.5% 를 빼면 남는 게 거의 없다) → 매출 +37%(1H26)인데 매출총이익 +17%
    <br><b>라이넥</b> 1Q26 +1% · 2Q26 +45% · 3Q26P 역산 ${f1(r3.L)}(물량 ${pc(r3.Lv/Q["2025Q3"].L-1)} YoY) — 9월 인상 전 선매입일 수 있어 4Q26 물량은 4Q25 × (1${A.L4g>=0?"+":""}${A.L4g}%)
    <br><b>판관비</b> 전년 동기 × 증가율(인건비 +${A.hr26}·${A.hr27}% · 광고 +${A.ad26}·${A.ad27}% · 임차 +20·5% · 연구개발 0·+${A.rnd27}%) · 지급수수료 = 상품 × ${A.feeR}% + 보령 코프로모션(라이넥 2차 병원 매출 × 30%) · 운반비 = 매출 × ${A.frR}%
    <br><b>3Q26P</b> 매출·영업이익·순이익 = 잠정실적(11/2) · 판관비 ${f1(r3.sga)}(≈ 위 식) · 매출총이익 = 영업이익 + 판관비(≈ ${fmt(r3.gp/r3.rev*100,1)}% · 회귀식보다 ${sign(r3.gpRes,1)}) — 3분기보고서(11월 중순)가 들어오면 실제 값으로
    <br><b>영업 밖</b> 이자 분기 −1.15 · 지분법(이니바이오) 2026 −1.1 · 2027 −0.9 · CB 파생 평가손익 0 · 세율 22% · CB 잔여 ${fmt(cb.left,0)}십억(전환가 ${fmt0(cb.px)}원 · ${fmt(cb.left/cb.px*1000,2)}백만주)</div>`;
  const fv=v=>v==null?"":String(v), U=gcwbAsmGet();
  const inp=(k,t,st,unit,w)=>`<label>${t} <input data-gcwba="${k}" type="number" step="${st}" value="${fv(U[k])}" placeholder="${fv(GCWB_DEF[k])}" style="width:${w||56}px"> ${unit||"%"}</label>`;
  const asm=`<details class="fold" data-fold="gcwb_asm"${(()=>{ try{ return localStorage.getItem("fold_gcwb_asm")==="1"?" open":""; }catch(e){ return ""; } })()}><summary>가정 바꾸기 <span class="sub">라이넥 물량·판가·상품 성장·이익률·판관비·배수 — 이 브라우저에 기억</span></summary><div style="padding:8px 0">
    <div style="display:flex;flex-wrap:wrap;gap:8px 16px;font-size:12px">
      ${inp("L3","3Q26 라이넥 물량",0.5,"십억")}${inp("L4g","4Q26 라이넥 물량 YoY",1)}${inp("L27g","2027 라이넥 물량 성장",1)}${inp("price","공급가 인상률",1)}
      ${inp("iv3","IV 3Q27",0.1,"십억")}${inp("iv4","IV 4Q27",0.1,"십억")}${inp("gd4","4Q26 상품 YoY",1)}${inp("gd27","2027 상품 성장",1)}${inp("oth26","2026 기타 제품 YoY",1)}
      ${inp("Lm","라이넥 이익률",1)}${inp("Om","기타 제품 이익률",1)}${inp("Gm","상품·자회사 이익률",0.5)}${inp("q4","4Q 원가 조정",0.1,"십억")}
      ${inp("feeR","지급수수료(상품 대비)",0.5)}${inp("hr26","인건비 2026H2",1)}${inp("ad26","광고 2026H2",1)}${inp("pe","Target P/E",0.5,"배")}
      <button data-gcwbreset style="font-size:11.5px">기본값으로</button></div></div></details>`;
  host.innerHTML=`<div class="sub-h" style="margin:2px 0 8px">분기 손익 — 라이넥·상품·판관비 <span class="th-sub" style="display:inline;margin-left:6px">십억원 · P 잠정실적 · E 우리 추정 · ≈ 역산·추정 · ▸ 세부 · 칸에 마우스 = 식</span></div>
    ${head}
    <div class="tbl-wrap"><table class="mini-tbl ism-t"><thead><tr><th class="l">${attr(name)}</th>${th}</tr></thead><tbody>${body}</tbody></table></div>
    ${plant}${method}${asm}
    <p class="note">실적 DART 연결 손익·판관비 주석·매출실적(별도)·주요 제품(라이넥)·생산 및 설비(2Q26 반기보고서까지 · 크롬 수집 ${attr(G.asOf)}) · 3Q26 ${attr((G.p["2026Q3"]||{}).src||"")}</p>`;
  host.querySelectorAll("[data-gcwbtg]").forEach(el=>el.addEventListener("click",()=>{ const g=el.dataset.gcwbtg; gcwbOpen={...open}; gcwbOpen[g]=!open[g];
    try{ localStorage.setItem("gcwbOpen",JSON.stringify(gcwbOpen)); }catch(e){} renderGcwbModel(host); }));
  host.querySelectorAll("[data-gcwba]").forEach(i=>i.addEventListener("change",()=>{ const a={...gcwbAsmGet()};
    host.querySelectorAll("[data-gcwba]").forEach(x=>{ a[x.dataset.gcwba]=x.value===""?null:+x.value; });
    gcwbAsmSave(a); renderGcwbModel(host); }));
  const rb=host.querySelector("[data-gcwbreset]"); if(rb) rb.addEventListener("click",()=>{ try{ localStorage.removeItem("gcwbAsm"); }catch(e){} renderGcwbModel(host); });
}
