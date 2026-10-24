/* ══ 종목별 분기 손익 모델 — 공통 엔진 (2026-10-24 · ISM) ═════════════════════════════════════
   사용자 "종목마다 다 IS 모델링 — 컴투스·대원처럼 열심히 된 애들 참고해서, 지표를 어디서 끌어올지 고민해 종목 하나하나 딥다이브".
   전용 모델(컴투스 C2 · 대원 DW · 카카오게임즈 KG · 디어유 DY)이 없는 종목은 이 엔진이 종목 페이지 손익 탭에 그린다.

   실적 칸 = ISM 블록(fetch_ism.py) — DART 연결 분기 손익(q) + 종목별 부문 파서가 읽은 부문 매출·영업이익(seg).
   추정 칸 = ISM_SPEC[종목] — 부문마다 동인(drv):
     "px"   지표 × 계수 — 계수 = 최근 fit 개 실적 분기의 (부문 매출 ÷ 지표) 평균. 지표가 그 분기를 다 덮지 못하면(1~2개월) 관측 월로 일할,
            하나도 없으면 전년 동기 × (1+g) 로 넘어간다(넘어간 칸은 툴팁에 적는다).
     "yoy"  전년 동기 × (1+g) — g 기본 = 최근 2개 실적 분기 전년비 평균(−30~+60% 로 자름) · 가정 칸에서 바꾼다.
     "seas" 직전 분기 × 계절 배수(그 분기의 과거 전분기비 평균) × (1+g)^(1/4).
   비용 = 부문 영업이익이 공시되면 부문 이익률(최근 4분기) · 아니면 회사 이익률(최근 4분기). 영업외 = 최근 6분기 (세전 − 영업이익) 중앙값.
   세율 = 최근 4분기 실효(10~30% 로 자름 · 적자면 0) · 지배 몫 = 최근 4분기 Σ지배 ÷ Σ순이익.
   설계(ISM_SPEC)가 없는 종목은 실적 칸 + 네이버 컨센(C 표시)만 — 우리 추정이 없는데 숫자를 지어내지 않는다.

   단위는 전부 십억원(DART · 네이버 컨센 series 와 같다). 지표의 달러는 그달 ECB 평균 환율(kbFx)로 원화. */
const ISM_SPEC={};
const ISM_COLS=["2025Q1","2025Q2","2025Q3","2025Q4","2026Q1","2026Q2","2026Q3","2026Q4","2027Q1","2027Q2","2027Q3","2027Q4"];
const ismQ=ym=>`${ym.slice(0,4)}Q${Math.floor((+ym.slice(5,7)-1)/3)+1}`;     // "2026-08" → "2026Q3"
const ismMid=q=>[1,2,3].map(i=>`${q.slice(0,4)}-${String((+q.slice(-1)-1)*3+i).padStart(2,"0")}`);   // 분기의 세 달

/* ── 지표 → 분기 합 {q:{v, n(달 수)}} ─────────────────────────────────── */
function ismAgg(pairs){        // [[ym, 값], …] → 분기 합
  const o={}; pairs.forEach(([ym,v])=>{ if(v==null||!isFinite(v)) return; const q=ismQ(ym); const x=o[q]||(o[q]={v:0,n:0}); x.v+=v; x.n++; });
  return o;
}
const ISM_PX={
  // 관세청 수출(TRADE · 품목 라벨 · 나라 코드 ""=전체) → 원화 십억
  trade(label, code){ if(typeof TRADE==="undefined") return {};
    const it=(TRADE.items||[]).find(x=>x.label===label); if(!it) return {};
    const c=(it.byCountry||[]).find(x=>x.code===(code||""))||(it.byCountry||[])[0]; if(!c) return {};
    return ismAgg(TRADE.months.map((m,i)=>{ const ym=`${m.slice(0,4)}-${m.slice(4,6)}`; const v=c.exp[i];
      return [ym, v==null?null:v*(kbFx("USD",ym)||1400)/1e9]; })); },
  // 미국 B/L 선적(BL · 페이지 id) → 톤
  bl(id){ if(typeof BL==="undefined") return {}; const s=(BL.s||[]).find(x=>x.id===id); if(!s) return {};
    const upd=s.upd||"", cur=upd.slice(0,7);
    return ismAgg(BL.months.map((ym,i)=>[ym, ym===cur?null:s.w[i]])); },     // 진행 중인 달은 빼고(일할은 엔진이)
  // 써클차트 월간 앨범 판매량(CIRCLE · 종목) → 만 장
  circle(stock){ if(typeof CIRCLE==="undefined"||!CIRCLE.month) return {}; const m=CIRCLE.month, a=(m.byStock||{})[stock]; if(!a) return {};
    return ismAgg(m.periods.map((p,i)=>[`20${p.slice(0,2)}-${p.slice(3,5)}`, a[i]==null?null:a[i]/1e4])); },
  // 방한 외래관광객(TOURISM) → 만 명
  tour(){ if(typeof TOURISM==="undefined") return {};
    return ismAgg(TOURISM.months.map((m,i)=>[`${m.slice(0,4)}-${m.slice(4,6)}`, TOURISM.total[i]==null?null:TOURISM.total[i]/1e4])); },
  // 게임 한국 매출순위(GRANK · gamerscroll) → 컴투스 곡선(c2Rev · 결제액 억/일) ÷ 1.1 → 회사 매출 십억/달.
  //   달마다: 일별이 그 달을 거의 덮으면(빠진 날 3일 이하) 일별 합을 일수로 늘리고, 아니면 월평균 순위 × 일수(볼록성 때문에 조금 낮다).
  app(slugs){ if(typeof GRANK==="undefined"||typeof c2Rev!=="function") return {};
    const P=C2_ASM0, yms=new Set();
    slugs.forEach(sl=>{ const g=GRANK.g[sl]; if(!g) return; Object.keys(g.d||{}).forEach(d=>yms.add(d.slice(0,7))); Object.keys(g.m||{}).forEach(m=>yms.add(m)); });
    const pairs=[...yms].sort().map(ym=>{ const dim=new Date(+ym.slice(0,4), +ym.slice(5,7), 0).getDate(); let tot=0, ok=true;
      slugs.forEach(sl=>{ const g=GRANK.g[sl]; if(!g){ return; }
        const ds=Object.keys(g.d||{}).filter(d=>d.startsWith(ym));
        if(ds.length>=dim-3){ tot+=ds.reduce((t,d)=>t+c2Rev(P,g.d[d][0],g.d[d][1]),0)*dim/ds.length; }
        else if(g.m&&g.m[ym]){ tot+=c2Rev(P,g.m[ym][0],g.m[ym][1])*dim; }
        else ok=false; });
      return [ym, ok?tot/(P.vat||1.1)/10:null]; });
    return ismAgg(pairs); },
  // 카지노 월간 공시(CASINO · fetch_casino.py) — key: c 카지노 · h 호텔 · d 드롭 → 십억원
  casino(nm, key){ if(typeof CASINO==="undefined"||!CASINO.m||!CASINO.m[nm]) return {}; const M=CASINO.m[nm];
    return ismAgg(Object.keys(M).map(ym=>[ym, M[ym][key||"c"]])); },
  // 아마존(Keepa 전 지역) + 틱톡샵 브랜드 판매액(KBPH) → 원화 십억
  kb(keys){ if(typeof KBPH==="undefined"||!KBPH.b) return {};
    const mk0=typeof cosMk!=="undefined"?cosMk:"us"; let A; try{ cosMk="all"; A=KBB(); } finally{ cosMk=mk0; }
    const M=KBPH.months, part=KBPH.partial, TT=KBPH.tt&&KBPH.tt.b?KBPH.tt:null, pairs=[];
    M.forEach((ym,j)=>{ if(ym===part) return; let s=0, any=false;
      keys.forEach(k=>{ const b=A.b[k]; if(b&&b.v&&b.v[j]!=null){ s+=b.v[j]; any=true; }
        const t=TT&&TT.b[k], ti=TT?(TT.months||[]).indexOf(ym):-1; if(t&&ti>=0&&t.mv&&t.mv[ti]!=null&&ym!==TT.partial){ s+=t.mv[ti]; any=true; } });
      pairs.push([ym, any?s*(kbFx("USD",ym)||1400)/1e9:null]); });
    return ismAgg(pairs); },
};

/* ── 엔진 ─────────────────────────────────────────────────────────────── */
function ismAsmGet(name){ try{ return JSON.parse(localStorage.getItem("ism_"+name)||"{}")||{}; }catch(e){ return {}; } }
function ismAsmSave(name, a){ try{ localStorage.setItem("ism_"+name, JSON.stringify(a)); }catch(e){} }
const ismMed=a=>{ const s=a.filter(v=>v!=null&&isFinite(v)).sort((x,y)=>x-y); if(!s.length) return null; const m=s.length>>1; return s.length%2?s[m]:(s[m-1]+s[m])/2; };
const ismClip=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));

function ismBuild(name){
  const D=(typeof ISM!=="undefined"&&ISM.s&&ISM.s[name])||null; if(!D||!D.q) return null;
  const S=ISM_SPEC[name]||null, A=ismAsmGet(name);
  const act=Object.keys(D.q).filter(q=>D.q[q].rev!=null).sort(), lastAct=act[act.length-1];
  const segsAll=S&&S.segs?S.segs:[];
  const segAct=(q,k)=>{ const g=(D.seg||{})[q]; if(!g) return null; const v=g[k]; return v?v:null; };
  const Q={};
  // 실적 칸
  act.forEach(q=>{ const d=D.q[q], o={q, act:true, rev:d.rev, op:d.op, pbt:d.pbt, np:d.np, npp:d.npp!=null?d.npp:d.np, seg:{}};
    let sum=0, have=0;
    segsAll.forEach(s=>{ const v=s.of?(Array.isArray(s.of)?s.of.reduce((t,k)=>{ const x=segAct(q,k); return x?[t[0]+(x[0]||0),(t[1]==null||x[1]==null)?null:t[1]+x[1]]:t; },[0,0]):segAct(q,s.of)):null;
      if(v&&v[0]!=null){ o.seg[s.k]={rev:v[0], op:v[1]}; sum+=v[0]; have++; } });
    if(segsAll.length&&have) o.seg._rest={rev:d.rev-sum, op:null};
    Q[q]=o; });
  // 최근 실적 기준값들
  const lastN=(n)=>act.slice(-n).map(q=>Q[q]);
  const L4=lastN(4), L6=lastN(6);
  const opm=L4.reduce((t,x)=>t+(x.op||0),0)/Math.max(1e-9,L4.reduce((t,x)=>t+(x.rev||0),0));
  const nonop=A.nonop!=null?A.nonop:ismMed(L6.map(x=>(x.pbt!=null&&x.op!=null)?x.pbt-x.op:null))||0;
  const sPbt=L4.reduce((t,x)=>t+(x.pbt||0),0), sNp=L4.reduce((t,x)=>t+(x.np||0),0);
  const tax=A.tax!=null?A.tax/100:(sPbt>0?ismClip((sPbt-sNp)/sPbt,0.1,0.3):0.22);
  const share=A.share!=null?A.share/100:(sNp!==0?ismClip(L4.reduce((t,x)=>t+(x.npp||0),0)/sNp,0,1.2):1);
  const P={opm:A.opm!=null?A.opm/100:opm, nonop, tax, share, segs:{}};
  // 부문 기본값 — 성장률·이익률·지표 계수
  const segRev=(q,k)=>Q[q]&&Q[q].seg[k]?Q[q].seg[k].rev:null;
  // 재분류(옛 분류 그대로인 분기 = D.segBasis[q]==="old") — 재작성된 분기의 새/옛 비율로 옛 분기를 새 분류에 맞춘다
  const OLD=D.segOld||{}, fac={};
  segsAll.forEach(s=>{ let n=0, o=0; Object.keys(OLD).forEach(q=>{ const v=OLD[q][s.k], w=segRev(q,s.k); if(v&&v[0]>0&&w!=null){ n+=w; o+=v[0]; } }); fac[s.k]=o>0?n/o:1; });
  const isOld=q=>(D.segBasis||{})[q]==="old";
  const baseRev=(q,k)=>{ const v=segRev(q,k); return v==null?null:(isOld(q)?v*fac[k]:v); };
  segsAll.forEach(s=>{
    const ys=act.slice(-2).map(q=>{ const a=baseRev(q,s.k), b=baseRev(c2QAdd(q,-4),s.k); return (a!=null&&b>0)?a/b-1:null; }).filter(v=>v!=null);
    const gAuto=ys.length?ismClip(ys.reduce((t,v)=>t+v,0)/ys.length,-0.3,0.6):0;
    const ops=act.slice(-4).map(q=>Q[q].seg[s.k]).filter(x=>x&&x.op!=null&&x.rev>0);
    const mAuto=ops.length>=2?ops.reduce((t,x)=>t+x.op,0)/ops.reduce((t,x)=>t+x.rev,0):null;
    let px=null, k=null, kN=0, ia=null, ib=null, r2=null;
    if((s.drv==="px"||s.drv==="pxa")&&s.px){ try{ px=s.px(); }catch(e){ px=null; }
      if(px){ const pr=act.slice(-(s.fit||(s.drv==="pxa"?8:4))).map(q=>{ const a=baseRev(q,s.k), p=px[q]; return (a!=null&&p&&p.n===3&&p.v>0)?[p.v,a]:null; }).filter(Boolean);
        if(s.drv==="px"&&pr.length){ k=pr.reduce((t,x)=>t+x[1]/x[0],0)/pr.length; kN=pr.length; }
        if(s.drv==="pxa"&&pr.length>=3){ const n=pr.length, mx=pr.reduce((t,x)=>t+x[0],0)/n, my=pr.reduce((t,x)=>t+x[1],0)/n;
          const sxx=pr.reduce((t,x)=>t+(x[0]-mx)**2,0), sxy=pr.reduce((t,x)=>t+(x[0]-mx)*(x[1]-my),0), syy=pr.reduce((t,x)=>t+(x[1]-my)**2,0);
          if(sxx>0){ ib=sxy/sxx; ia=my-ib*mx; r2=syy>0?(sxy*sxy)/(sxx*syy):null; kN=n; } } } }
    const a=(A.seg||{})[s.k]||{};
    P.segs[s.k]={g:a.g!=null?a.g/100:(s.g!=null?s.g:gAuto), gAuto, m:a.m!=null?a.m/100:(s.m!=null?s.m:mAuto), mAuto, px, k, kN, ia, ib, r2, fac:fac[s.k]};
  });
  // 추정 칸
  const est=S?ISM_COLS.filter(q=>!Q[q]&&q>lastAct):[];                    // 설계가 없으면 추정 칸을 만들지 않는다
  est.forEach(q=>{
    const o={q, act:false, seg:{}, why:{}};
    if(segsAll.length){
      let sum=0;
      segsAll.forEach(s=>{ const p=P.segs[s.k], q4=c2QAdd(q,-4), base=Q[q4]&&Q[q4].seg[s.k]?baseRev(q4,s.k):null;
        let v=null, why="";
        const x=p.px&&p.px[q], xv=x&&x.n>=1?x.v*3/x.n:null, xl=x?(x.n===3?`${s.pxLab||"지표"} ${fmt(x.v,1)}`:`${s.pxLab||"지표"} ${x.n}개월 ${fmt(x.v,1)}×3/${x.n}`):"";
        if(s.drv==="px"&&p.k!=null&&xv!=null){ v=p.k*xv; why=`${xl} × ${fmt(p.k,3)}(최근 ${p.kN}분기 비율)`; }
        if(s.drv==="pxa"&&p.ib!=null&&xv!=null){ v=p.ia+p.ib*xv; why=`${fmt(p.ia,1)} + ${fmt(p.ib,3)} × ${xl}(최근 ${p.kN}분기 적합${p.r2!=null?` · R² ${fmt(p.r2,2)}`:""})`; }
        if(v==null&&s.drv==="seas"){ const pq=Q[c2QAdd(q,-1)]; const prev=pq&&pq.seg[s.k]?pq.seg[s.k].rev:null; const sf=ismSeas(Q,s.k,+q.slice(-1),act);
          if(prev!=null&&sf){ v=prev*sf*Math.pow(1+p.g,0.25); why=`직전 분기 ${fmt(prev,1)} × 계절 ${fmt(sf,3)} × (1${p.g>=0?"+":""}${fmt(p.g*100,0)}%)^¼`; } }
        if(v==null&&base!=null){ v=base*(1+p.g); why=(s.drv==="px"||s.drv==="pxa"?"지표 없음 → ":"")+`전년 동기 ${fmt(base,1)}${isOld(q4)&&fac[s.k]!==1?`(옛 분류 × ${fmt(fac[s.k],2)})`:""} × (1${p.g>=0?"+":""}${fmt(p.g*100,0)}%)`; }
        if(v==null) v=0;
        const op=p.m!=null?v*p.m:null;
        o.seg[s.k]={rev:v, op}; o.why[s.k]=why; sum+=v; });
      // 나머지(부문 밖 · 조정) = 최근 4분기 비중
      const rr=act.slice(-4).map(x=>Q[x].seg._rest&&Q[x].rev?Q[x].seg._rest.rev/Q[x].rev:null).filter(v=>v!=null);
      const rest=rr.length?ismClip(rr.reduce((t,v)=>t+v,0)/rr.length,-0.5,0.5):0;
      o.rev=sum/(1-rest); o.seg._rest={rev:o.rev-sum, op:null};
      const segOp=segsAll.every(s=>o.seg[s.k].op!=null);
      o.op=segOp?segsAll.reduce((t,s)=>t+o.seg[s.k].op,0)+(o.seg._rest.rev*P.opm):o.rev*P.opm;
      o.why.op=segOp?`부문 영업이익 합(부문 이익률 × 매출) + 나머지 × 회사 이익률 ${fmt(P.opm*100,1)}%`:`매출 × 회사 영업이익률 ${fmt(P.opm*100,1)}%(최근 4분기)`;
    }
    o.pbt=o.op+P.nonop; o.np=o.pbt>0?o.pbt*(1-P.tax):o.pbt; o.npp=o.np*P.share;
    Q[q]=o;
  });
  // 연간
  const Y={};
  ["2024","2025","2026","2027"].forEach(y=>{ const qs=[1,2,3,4].map(i=>Q[`${y}Q${i}`]); if(qs.some(x=>!x)) return;
    const sum=k=>qs.reduce((t,x)=>t+(x[k]||0),0);
    const o={q:y, yr:true, act:qs.every(x=>x.act), rev:sum("rev"), op:sum("op"), pbt:sum("pbt"), np:sum("np"), npp:sum("npp"), seg:{}};
    segsAll.concat([{k:"_rest"}]).forEach(s=>{ if(qs.every(x=>x.seg[s.k])) o.seg[s.k]={rev:qs.reduce((t,x)=>t+x.seg[s.k].rev,0),
      op:qs.every(x=>x.seg[s.k].op!=null)?qs.reduce((t,x)=>t+x.seg[s.k].op,0):null}; });
    Y[y]=o; });
  return {D, S, A, P, Q, Y, act, lastAct, est};
}
function ismSeas(Q, k, qi, act){
  const r=act.filter(q=>+q.slice(-1)===qi).map(q=>{ const a=Q[q].seg[k], b=Q[c2QAdd(q,-1)]&&Q[c2QAdd(q,-1)].seg[k]; return (a&&b&&b.rev>0)?a.rev/b.rev:null; }).filter(v=>v!=null);
  return r.length?Math.exp(r.reduce((t,v)=>t+Math.log(v),0)/r.length):null;
}

/* ── 화면 ─────────────────────────────────────────────────────────────── */
let ismOpen=(()=>{ try{ return JSON.parse(localStorage.getItem("ismOpen")||"{}")||{}; }catch(e){ return {}; } })();
function renderIsm(name, host){
  if(!host) return;
  const B=ismBuild(name);
  if(!B){ host.innerHTML=""; return; }
  const {S, P, Q, Y, A}=B;
  const f1=v=>(v==null||!isFinite(v))?"—":fmt(v,1);
  const pc=v=>(v==null||!isFinite(v))?"—":`<span class="${cls(v)}">${sign(v*100,0)}%</span>`;
  const chg=(c,b)=>{ if(c==null||b==null) return "—"; if(b>0) return c>0||c===0?pc(c/b-1):`<span class="down">적전</span>`; return c>0?`<span class="up">흑전</span>`:`<span class="g">적지</span>`; };
  const LS=(typeof LIVE!=="undefined"&&LIVE.stocks&&LIVE.stocks[name])||{}, cn=LS.cons||{}, cons={};
  ((cn.quarter||{}).series||[]).forEach(x=>{ cons[`${x.k.slice(0,4)}Q${Math.ceil(+x.k.slice(4,6)/3)}`]=x; });
  ((cn.year||{}).series||[]).forEach(x=>{ cons[x.k.slice(0,4)]=x; });
  const segs=S&&S.segs?S.segs:[], hasSpec=!!S;
  // 설계가 없으면 추정 칸 = 네이버 컨센(분기는 컨센이 있는 것만 · 2027 은 엑셀 컨센 DATA.rev27/op27)
  const R0=(typeof byName!=="undefined"&&byName[name])||{};
  if(R0.rev27!=null&&!cons["2027"]) cons["2027"]={rev:R0.rev27, op:R0.op27, np:null, xl:1};
  const cOf=q=>{ const c=cons[q]; return c?{q, yr:q.length===4, act:false, cOnly:true, seg:{}, rev:c.rev, op:c.op, npp:c.np}:null; };
  const cols=ISM_COLS.map(q=>Q[q]||(!hasSpec&&q>B.lastAct?cOf(q):null)).filter(Boolean)
    .concat(["2025","2026","2027"].map(y=>(Y[y]&&(Y[y].act||hasSpec))?Y[y]:cOf(y)).filter(Boolean));
  const nextQ=(cols.find(o=>!o.yr&&!o.act)||{}).q;
  const lab=o=>o.yr?`${o.q}${o.act?"A":o.cOnly?"C":"E"}`:`${c2QLab(o.q)}${o.act?"":o.cOnly?"C":"E"}`;
  const prevOf=o=>o.yr?(Y[String(+o.q-1)]||null):(Q[c2QAdd(o.q,-4)]||null);
  const mc=LS.mktcapEok?LS.mktcapEok/10:null;
  const open=ismOpen[name]||{};
  const ROWS=[{k:"rev", t:"매출액", em:1, tg:segs.length?"rev":null}, {k:"rev", t:"YoY", r:"yoy"}, {k:"rev", t:"QoQ", r:"qoq"}]
    .concat(segs.map(s=>({k:s.k, t:s.t, seg:1, g:"rev"})))
    .concat(segs.length?[{k:"_rest", t:"그 밖·조정", seg:1, g:"rev", sm:1}]:[])
    .concat([{k:"op", t:"영업이익", em:1, tg:segs.some(s=>s.m!=null||(P.segs[s.k]||{}).m!=null)?"op":null}, {k:"op", t:"영업이익률", r:"opm"}, {k:"op", t:"YoY", r:"opyoy"}])
    .concat(segs.filter(s=>(P.segs[s.k]||{}).m!=null).map(s=>({k:s.k, t:s.t+" 영업이익", seg:1, sop:1, g:"op"})))
    .concat([{k:"pbt", t:"세전이익", tg:"np"}, {k:"np", t:"당기순이익", g:"np"}, {k:"npp", t:"지배주주 순이익", em:1}, {k:"per", t:"PER(현재 시총)", r:"per"}]);
  const valOf=(o,r)=>{
    if(r.r==="yoy"){ const p=prevOf(o)||cols.find(x=>x.q===(o.yr?String(+o.q-1):c2QAdd(o.q,-4))); return {h:chg(o.rev,p&&p.rev)}; }
    if(r.r==="qoq"){ if(o.yr) return {h:""}; const p=Q[c2QAdd(o.q,-1)]; return {h:chg(o.rev,p&&p.rev)}; }
    if(r.r==="opm") return {h:(o.rev&&o.op!=null)?`${fmt(o.op/o.rev*100,1)}%`:"—"};
    if(r.r==="opyoy"){ const p=prevOf(o)||cols.find(x=>x.q===(o.yr?String(+o.q-1):c2QAdd(o.q,-4))); return {h:chg(o.op,p&&p.op)}; }
    if(r.r==="per") return {h:(o.yr&&mc&&o.npp>0)?`${fmt(mc/o.npp,1)}배`:""};
    if(r.seg){ const x=o.seg&&o.seg[r.k]; if(!x) return {h:"—"}; const v=r.sop?x.op:x.rev;
      if(o.act&&!o.yr&&(B.D.segBasis||{})[o.q]==="old") return {h:f1(v)+"*", tip:"옛 분류(재분류 전) — 전년비는 새 분류로 맞춰 계산"};
      return {h:f1(v), tip:(!o.act&&o.why&&!r.sop)?o.why[r.k]:""}; }
    return {h:f1(o[r.k]), tip:(r.k==="op"&&o.why&&o.why.op)?o.why.op:""};
  };
  const yrEdge=i=>i>0&&(cols[i].yr!==cols[i-1].yr||(!cols[i].yr&&cols[i].q.slice(0,4)!==cols[i-1].q.slice(0,4)));
  const th=cols.map((o,i)=>`<th style="${yrEdge(i)?"border-left:2px solid var(--line);":""}${o.q===nextQ?"background:color-mix(in srgb, var(--accent) 14%, transparent);":""}">${lab(o)}</th>`).join("");
  const body=ROWS.filter(r=>!r.g||open[r.g]).map(r=>{
    const tog=r.tg?`<span class="ism-tg" data-ismtg="${r.tg}" style="cursor:pointer;color:var(--muted);margin-right:4px">${open[r.tg]?"▾":"▸"}</span>`:"";
    const sub=!!r.r||r.seg;
    return `<tr${r.em?' style="font-weight:800"':""}><td class="l" style="${r.seg?"padding-left:22px;":""}${sub?"color:var(--muted);font-size:11.5px;":""}">${tog}${attr(r.t)}</td>`
      +cols.map((o,i)=>{ const v=valOf(o,r); const shade=o.q===nextQ?"background:color-mix(in srgb, var(--accent) 8%, transparent);":"";
        const est=!o.act&&!o.cOnly?"":o.cOnly?"color:var(--muted);":"";
        return `<td style="${yrEdge(i)?"border-left:2px solid var(--line);":""}${shade}${est}${r.em?"border-top:1px solid var(--line);border-bottom:1px solid var(--line);":""}"${v.tip?` title="${attr(v.tip)}"`:""}>${v.h}</td>`; }).join("")+`</tr>`; }).join("");
  // 컨센 줄
  const consRow=!hasSpec?"":`<tr><td class="l" style="color:var(--muted);font-size:11.5px">참고: 네이버 컨센 매출 / 영업이익</td>`+cols.map((o,i)=>{ const c=cons[o.q];
    return `<td style="color:var(--muted);font-size:11px;${yrEdge(i)?"border-left:2px solid var(--line);":""}">${c&&!o.act&&!o.cOnly?`${f1(c.rev)} / ${f1(c.op)}`:""}</td>`; }).join("")+`</tr>`;
  // 머리 카드
  const card=(t,v,sub)=>`<div style="flex:1;min-width:170px;background:var(--panel);border:1px solid var(--line-soft);border-radius:var(--radius);padding:12px 14px">
    <div style="font-size:11.5px;color:var(--muted);font-weight:700">${t}</div><div style="font-size:19px;font-weight:800;margin-top:3px">${v}</div>
    <div style="font-size:11px;color:var(--muted2);margin-top:3px;line-height:1.45">${sub||""}</div></div>`;
  const vsC=(o)=>{ const c=cons[o.q]; if(!c||o.cOnly) return o.cOnly?"컨센":""; return `컨센 대비 ${pc(o.rev/c.rev-1)} / ${c.op>0?pc(o.op/c.op-1):"—"}`; };
  const nq=Q[nextQ]||cols.find(o=>o.q===nextQ), y6=cols.find(o=>o.q==="2026"), y7=cols.find(o=>o.q==="2027");
  const head=`<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px">
    ${nq?card(`${lab(nq)} 매출 / 영업이익`, `${f1(nq.rev)} / ${f1(nq.op)}`, vsC(nq)):""}
    ${y6?card(`${lab(y6)} 매출 / 영업이익`, `${f1(y6.rev)} / ${f1(y6.op)}`, vsC(y6)):""}
    ${y7?card(`${lab(y7)} 매출 / 영업이익`, `${f1(y7.rev)} / ${f1(y7.op)}`, vsC(y7)):""}
    ${(y6&&mc&&y6.npp>0)?card("PER(현재 시총)", `${fmt(mc/y6.npp,1)} / ${y7&&y7.npp>0?fmt(mc/y7.npp,1):"—"}배`, `2026 / 2027 지배주주 순이익 · 시총 ${fmt0(mc*10)}억`):""}
  </div>`;
  // 가정 칸
  const asm=hasSpec?`<details class="fold" data-fold="ism_asm"${(()=>{ try{ return localStorage.getItem("fold_ism_asm")==="1"?" open":""; }catch(e){ return ""; } })()}><summary>가정 바꾸기 <span class="sub">부문 성장률·이익률 · 영업외·세율 — 이 브라우저에 기억</span></summary><div class="fold-b">
    <div style="display:flex;flex-wrap:wrap;gap:8px 16px;font-size:12px">`
    +segs.map(s=>{ const p=P.segs[s.k];
      return `<label>${attr(s.t)} 성장률(전년비) <input data-ismg="${attr(s.k)}" type="number" step="1" value="${Math.round(p.g*100)}" style="width:62px"> % <span class="g">자동 ${fmt(p.gAuto*100,0)}%</span></label>`
        +(p.m!=null?`<label>이익률 <input data-ismm="${attr(s.k)}" type="number" step="0.5" value="${fmt(p.m*100,1).replace(/,/g,"")}" style="width:62px"> % <span class="g">자동 ${p.mAuto!=null?fmt(p.mAuto*100,1)+"%":"—"}</span></label>`:""); }).join("")
    +`<label>회사 이익률 <input data-isma="opm" type="number" step="0.5" value="${fmt(P.opm*100,1).replace(/,/g,"")}" style="width:62px"> %</label>
      <label>영업외 <input data-isma="nonop" type="number" step="0.5" value="${fmt(P.nonop,1).replace(/,/g,"")}" style="width:62px"> 십억/분기</label>
      <label>세율 <input data-isma="tax" type="number" step="1" value="${Math.round(P.tax*100)}" style="width:52px"> %</label>
      <button data-ismreset style="font-size:11.5px">기본값으로</button></div></div></details>`:"";
  const method=hasSpec?`<div class="note" style="margin-top:6px">${segs.map(s=>{ const p=P.segs[s.k];
      const how=s.drv==="px"?(p.k!=null?`${attr(s.pxLab||"지표")} × ${fmt(p.k,3)}`:"전년 동기 × 성장률(지표 없음)")
        :s.drv==="pxa"?(p.ib!=null?`${fmt(p.ia,1)} + ${fmt(p.ib,3)} × ${attr(s.pxLab||"지표")}${p.r2!=null?` (R² ${fmt(p.r2,2)})`:""}`:"전년 동기 × 성장률(지표 없음)")
        :s.drv==="seas"?"직전 분기 × 계절":"전년 동기 × 성장률";
      return `<b>${attr(s.t)}</b> ${how}${s.note?` · ${attr(s.note)}`:""}`; }).join("<br>")}
      ${S.note?`<br>${S.note}`:""}</div>`
    :`<div class="note" style="margin-top:6px">아직 추정 전 — 실적(DART)과 컨센(C)만.</div>`;
  const D=B.D;
  host.innerHTML=`<div class="sub-h" style="margin:2px 0 8px">분기 손익 모델 <span class="th-sub" style="display:inline;margin-left:6px">십억원 · E 우리 추정 · C 컨센 · ▸ 세부</span></div>
    ${head}
    <div class="tbl-wrap"><table class="mini-tbl ism-t"><thead><tr><th class="l">${attr(name)}</th>${th}</tr></thead><tbody>${body}${consRow}</tbody></table></div>
    ${method}${asm}
    <p class="note">실적 DART ${D.fs==="OFS"?"별도":"연결"}(${(Object.keys(D.src||{}).sort().pop()||"").replace("-",".")}까지)${D.segHow?` · 부문 ${attr(D.segHow)}`:""} · 칸에 마우스 = 추정 식</p>`;
  host.querySelectorAll("[data-ismtg]").forEach(el=>el.addEventListener("click",()=>{ const g=el.dataset.ismtg, o=ismOpen[name]=ismOpen[name]||{}; o[g]=!o[g];
    try{ localStorage.setItem("ismOpen",JSON.stringify(ismOpen)); }catch(e){} renderIsm(name, host); }));
  const upd=()=>{ const a={seg:{}};
    host.querySelectorAll("[data-ismg]").forEach(i=>{ const s=(a.seg[i.dataset.ismg]=a.seg[i.dataset.ismg]||{}); s.g=+i.value; });
    host.querySelectorAll("[data-ismm]").forEach(i=>{ const s=(a.seg[i.dataset.ismm]=a.seg[i.dataset.ismm]||{}); s.m=+i.value; });
    // 자동값과 같은 칸은 저장하지 않는다(나중에 자동값이 바뀌면 따라가게)
    Object.keys(a.seg).forEach(k=>{ const p=P.segs[k]; if(!p) return; const s=a.seg[k];
      if(s.g!=null&&Math.round(p.gAuto*100)===s.g) delete s.g; if(s.m!=null&&p.mAuto!=null&&Math.abs(p.mAuto*100-s.m)<0.05) delete s.m; });
    host.querySelectorAll("[data-isma]").forEach(i=>{ a[i.dataset.isma]=+i.value; });
    ismAsmSave(name, a); renderIsm(name, host); };
  host.querySelectorAll("[data-ismg],[data-ismm],[data-isma]").forEach(i=>i.addEventListener("change",upd));
  const rb=host.querySelector("[data-ismreset]"); if(rb) rb.addEventListener("click",()=>{ ismAsmSave(name,{}); renderIsm(name, host); });
}
