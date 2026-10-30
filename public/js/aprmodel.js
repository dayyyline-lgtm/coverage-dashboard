/* ══ 에이피알 분기 손익 — 비용 구조 모델 (2026-10-30 · APRMODEL ← fetch_aprmodel.py) ═══════════════════════════════
   사용자(3Q26 컨콜 뒤): "4Q·내년 추정치 하향을 고려해 IS 를 — 컨콜 기준으로 물류비·마케팅비가 개선된다고 보면 안 된다".
   종목 페이지 손익 탭 맨 위(#spIsm 자리 · 에이피알만). 공통 엔진(ism.js)은 매출 × 이익률이라 비용 줄이 없어 따로 뒀다.

   매출 — 해외는 '고정 환율 물량'(2025 평균 환율로 바꾼 값)과 환율로 나눠 본다.
     · 회사는 매출을 그 해 누적 평균 환율로 인식한다(컨콜) → 분기 매출 = 연초부터 누적 물량 × 누적 평균 환율 − 지난 분기까지 인식분.
       원화가 강해지면 지난 분기 몫까지 이번 분기에서 깎인다(3Q26 이 그랬다). 실적 분기의 물량도 이 식을 거꾸로 풀어 낸다.
     · 환율 바구니 = 2Q26 지역 매출 비중(북미 53 · 기타 9 → 달러 · 유럽 21 → 유로 · 아시아 17 → 엔). 앞으로의 달은 지금 환율 그대로.
     · 4Q26 물량 = 3Q26 × (1 + 기초 성장 g) × (1 + 행사 효과 e) — g·e 는 2026 1~3Q 물량에서(1Q·3Q 행사 없음 · 2Q 프라임데이).
       2027 = 2026 같은 분기 × (1 + g27). 국내 = 원화 그대로(4Q = 3Q × 작년 4Q/3Q · 2027 = 최근 4분기 전년비의 절반).
   비용 — 개선을 가정하지 않는다.
     · 광고선전비·판매수수료·운반비(달러·유로로 쓰는 비용) = 매출 × 비율. 비율 = 3Q26 컨콜 수준(20·17·9%)과 최근 같은 분기 실적 중 높은 쪽.
     · 매출원가·인건비 등(원화 비용) = 고정 환율 물량 × 3Q26 비율 — 원화가 강해지면 매출 대비 비율이 오른다(컨콜 '원가 부담 확대').
     · 기타영업손익(IFRS 18 · 외화 매출채권 평가) = 해외 매출 × 분기 말(마지막 달 평균) 환율 변화 × 3Q26 에서 잰 민감도.
   3Q26 실적 = 잠정실적 공정공시(10/30) + 실적설명회 비율. 원가·인건비 등은 역산(≈) — 3분기보고서(11월 중순)가 들어오면 DART 값으로 바뀐다. */
const APR_IR={
  "2026Q3":{ rev:773.115, op:160.640, op0:176.7, pbt:154.381, np:110.188, npp:110.188,   // op0 = 옛 기준(IFRS 18 전) 영업이익 — 차이가 기타영업손익
    seg:{"화장품":682.3, "디바이스":84.7, "기타":6.1}, reg:{"R해외":722.9, "R한국":50.2},
    r:{ad:0.20, cm:0.17, fr:0.09},        // 컨콜 '광고선전비 약 20% · 판매수수료 약 17% · 운반비 약 9%'
    fxv:-14.7,                            // 외화 매출채권 평가손 — 영업이익률 1.9%p(IFRS 18 · 영업이익 안)
    tariff:10.0,                          // 관세 환급 약 100억(일회성 · 원가에서 뺀 것으로 본다)
    src:"3Q26 잠정실적 공정공시(10/30) · 실적설명회", },
};
const APR_FXW={USD:0.62, EUR:0.21, JPY:0.17};      // 환율 바구니(2Q26 지역 매출 비중 — kbeauty/ir.json)
const APR_ASM0={e4:null, g4:null, g27:20, gD27:null, adF:20, cmF:17, frF:9, cogsB:null, usd:null, eur:null, refund:0};
function aprAsmGet(){ try{ const a=JSON.parse(localStorage.getItem("aprAsm")||"{}")||{}; return {...APR_ASM0, ...a}; }catch(e){ return {...APR_ASM0}; } }
function aprAsmSave(a){ try{ const o={}; Object.keys(a).forEach(k=>{ if(a[k]!=null&&a[k]!==APR_ASM0[k]) o[k]=a[k]; }); localStorage.setItem("aprAsm", JSON.stringify(o)); }catch(e){} }

function aprBuild(asmIn){
  if(typeof APRMODEL==="undefined"||!APRMODEL.q) return null;
  const A=asmIn||aprAsmGet(), D=APRMODEL.q, SEG=(typeof ISM!=="undefined"&&ISM.s&&ISM.s["에이피알"]&&ISM.s["에이피알"].seg)||{};
  // 환율 — 월 평균(kbFx · ECB). 앞으로의 달은 kbFx 가 마지막 달(지금) 값을 준다. 사용자가 원/달러·원/유로를 넣으면 지금 이후 달에 그 값.
  const lastYm=(()=>{ const m=(typeof KBCH!=="undefined"&&KBCH.fx&&KBCH.fx.m)?Object.keys(KBCH.fx.m).sort():[]; return m[m.length-1]||"2026-10"; })();
  const fxM=(c,ym)=>{ if(ym>lastYm){ if(c==="USD"&&A.usd) return A.usd; if(c==="EUR"&&A.eur) return A.eur; if(c==="JPY"&&A.usd){ const b=kbFx("JPY",lastYm), u=kbFx("USD",lastYm); return b&&u?b*A.usd/u:b; } }
    return typeof kbFx==="function"?kbFx(c,ym):null; };
  const ref={}; Object.keys(APR_FXW).forEach(c=>{ const v=[...Array(12)].map((_,i)=>fxM(c,`2025-${String(i+1).padStart(2,"0")}`)).filter(Boolean); ref[c]=v.reduce((t,x)=>t+x,0)/v.length; });
  const I=ym=>Object.keys(APR_FXW).reduce((t,c)=>t+APR_FXW[c]*(fxM(c,ym)||ref[c])/ref[c],0);   // 2025 평균 = 1
  const ymOf=(y,m)=>`${y}-${String(m).padStart(2,"0")}`;
  const Iavg=(y,n)=>{ let s=0; for(let m=1;m<=n*3;m++) s+=I(ymOf(y,m)); return s/(n*3); };      // 그 해 1~n 분기 누적 평균
  const Iq=q=>{ const y=+q.slice(0,4), i=+q.slice(-1); return [1,2,3].reduce((t,k)=>t+I(ymOf(y,(i-1)*3+k)),0)/3; };
  const Iend=q=>{ const y=+q.slice(0,4), i=+q.slice(-1); return I(ymOf(y,i*3)); };
  const fxAvg=(c,q)=>{ const y=+q.slice(0,4), i=+q.slice(-1); return [1,2,3].reduce((t,k)=>t+(fxM(c,ymOf(y,(i-1)*3+k))||0),0)/3; };
  // 실적 분기
  const Q={}, act=[];
  Object.keys(D).sort().filter(q=>q>="2024Q1").forEach(q=>{ const d=D[q], g=SEG[q]||{}, sg=d.sg||null;
    const o={q, act:true, rev:d.rev, cogs:d.cogs, sga:d.sga, op:d.op, pbt:d.pbt, np:d.np, npp:d.npp!=null?d.npp:d.np,
      oth:d.op-(d.rev-d.cogs-d.sga), sg:sg?{...sg}:null, seg:{}, reg:{}};
    ["화장품","디바이스","기타"].forEach(k=>{ if(g[k]&&g[k][0]!=null) o.seg[k]=g[k][0]; });
    ["R해외","R한국"].forEach(k=>{ if(g[k]&&g[k][0]!=null) o.reg[k]=g[k][0]; });
    Q[q]=o; act.push(q); });
  Object.keys(APR_IR).sort().forEach(q=>{ if(Q[q]&&Q[q].sg) return;     // DART 분기보고서가 들어오면 그게 이긴다
    const x=APR_IR[q], o={q, act:true, ir:true, rev:x.rev, op:x.op, pbt:x.pbt, np:x.np, npp:x.npp, seg:{...x.seg}, reg:{...x.reg}, src:x.src};
    const sg={ad:x.rev*x.r.ad, cm:x.rev*x.r.cm, fr:x.rev*x.r.fr};
    Q[q]=o; if(!act.includes(q)) act.push(q); o._r=x; o._sg=sg; });
  act.sort();
  const lastAct=act[act.length-1];
  // 고정 환율 물량 — 해외 원화 = 누적 물량 × 누적 평균 환율 − 지난 분기까지 인식분 → 거꾸로 풀어 분기 물량
  const fc={};
  ["2025","2026"].forEach(y=>{ let kY=0, fY=0; for(let i=1;i<=4;i++){ const q=`${y}Q${i}`; if(!Q[q]||Q[q].reg.R해외==null) break;
    kY+=Q[q].reg.R해외; const fYn=kY/Iavg(+y,i); fc[q]=fYn-fY; fY=fYn; } });
  const Rc=q=>(fc[q]!=null&&Q[q]&&Q[q].reg.R한국!=null)?fc[q]+Q[q].reg.R한국:null;     // 고정 환율 매출(해외 물량 + 국내)
  // 3Q26 — 원화 비용(원가·인건비 등)·판관비를 비율과 영업이익으로 역산
  const q3="2026Q3", q2="2026Q2";
  // 물량 추세 — 2026 1~3Q(1Q·3Q 행사 없음 · 2Q 프라임데이)
  const f1=fc["2026Q1"], f2=fc["2026Q2"], f3=fc["2026Q3"];
  const gAuto=(f1&&f3)?Math.sqrt(f3/f1)-1:0.1, eAuto=(f1&&f2)?f2/(f1*(1+gAuto))-1:0.1;
  const g4=A.g4!=null?A.g4/100:gAuto, e4=A.e4!=null?A.e4/100:eAuto;
  // 그 밖 판관비(원화 비용) — 항목마다 성격대로 (2026-10-30 사용자 "인건비·지급수수료 성격 반영해서 채워 줘")
  //   인건비·지급수수료·상각 = 고정비 — 직전 분기 × (1 + 그 항목 증가율). 증가율 = 최근 4분기 합 ÷ 그 전 4분기 합의 분기 환산(0~15%) · 물량 성장보다 빠르게는 안 늘린다
  //   포장비 = 물량 비례 — 고정 환율 매출 × 최근 4분기 비율
  //   기타(임차·소모품·세금과공과 등) = 연말에 몰리는 반고정 — [전년 동기 × (1+최근 4분기 전년비)] 와 [직전 분기 × 계절 배수] 의 평균 · 연 증가율은 물량 성장 이하
  const osgA=act.filter(q=>Q[q].sg&&!Q[q].ir).map(q=>Q[q].sga-Q[q].sg.ad-Q[q].sg.cm-Q[q].sg.fr);
  const gO=(()=>{ const v=osgA.slice(-5); if(v.length<2) return 0.03; const r=Math.pow(v[v.length-1]/v[0],1/(v.length-1))-1; return Math.max(0,Math.min(0.15,r)); })();   // 항목이 없을 때만
  const sgA=act.filter(q=>Q[q].sg&&Q[q].sg.hr!=null&&!Q[q].ir), L8=sgA.slice(-8);
  const s4=(k,qs)=>qs.reduce((t,q)=>t+Q[q].sg[k],0);
  const gK={}; ["hr","fee","dep","etc"].forEach(k=>{ const r=L8.length===8?s4(k,L8.slice(4))/s4(k,L8.slice(0,4)):null;
    gK[k]=k==="etc"?(r?Math.max(0,Math.min(0.6,r-1)):0.1):(r?Math.max(0,Math.min(0.15,Math.pow(r,0.25)-1)):0.03); });
  const L4s=sgA.slice(-4).filter(q=>Rc(q)), pkR=L4s.length?s4("pk",L4s)/L4s.reduce((t,q)=>t+Rc(q),0):0.005;
  const seaE=(()=>{ const raw={}; [1,2,3,4].forEach(i=>{ const v=sgA.filter(q=>+q.slice(-1)===i).map(q=>{ const p=c2QAdd(q,-1); return sgA.includes(p)&&Q[p].sg.etc>0?Q[q].sg.etc/Q[p].sg.etc:null; }).filter(Boolean);
      raw[i]=v.length?Math.exp(v.reduce((t,x)=>t+Math.log(x),0)/v.length):1; });
    const n=Math.pow(raw[1]*raw[2]*raw[3]*raw[4],0.25); return Object.fromEntries([1,2,3,4].map(i=>[i,raw[i]/n])); })();   // 네 분기 곱 = 1(성장은 따로)
  const sgEst=(q,rc,gq)=>{ const p=c2QAdd(q,-1), P0=Q[p]&&Q[p].sg, y4=Q[c2QAdd(q,-4)], qi=+q.slice(-1);
    if(!P0||P0.hr==null) return null;
    const o={}, w={};
    ["hr","fee","dep"].forEach(k=>{ const g=Math.min(gK[k],gq); o[k]=P0[k]*(1+g); w[k]=`직전 분기 ${fmt(P0[k],1)} × (1+${fmt(g*100,1)}%)${gq<gK[k]?` — 추세 ${fmt(gK[k]*100,1)}% 를 물량 성장으로 제한`:` — 최근 4분기 ÷ 그 전 4분기의 분기 환산`}`; });
    o.pk=rc*pkR; w.pk=`고정 환율 매출 ${fmt(rc,1)} × ${fmt(pkR*100,2)}%(최근 4분기)`;
    const gy=Math.min(gK.etc,Math.pow(1+gq,4)-1), a=y4&&y4.sg&&y4.sg.etc!=null?y4.sg.etc*(1+gy):null, b=P0.etc*seaE[qi]*Math.pow(1+gy,0.25);
    o.etc=a!=null?(a+b)/2:b;
    w.etc=a!=null?`[전년 동기 ${fmt(y4.sg.etc,1)} × (1+${fmt(gy*100,0)}%) + 직전 분기 ${fmt(P0.etc,1)} × 계절 ${fmt(seaE[qi]*Math.pow(1+gy,0.25),2)}] ÷ 2`:`직전 분기 ${fmt(P0.etc,1)} × 계절 ${fmt(seaE[qi],2)}`;
    o.osg=o.hr+o.fee+o.dep+o.pk+o.etc;
    return {sg:o, why:{hr:`인건비 = 고정비(인원·임금) · ${w.hr}`,
      o2:`지급수수료 ${fmt(o.fee,1)} = 고정 · ${w.fee}\n상각 ${fmt(o.dep,1)} = 고정 · ${w.dep}\n포장 ${fmt(o.pk,1)} = 물량 비례 · ${w.pk}\n기타 ${fmt(o.etc,1)} = 연말에 몰리는 반고정 · ${w.etc}`}}; };
  if(Q[q3]&&Q[q3].ir){ const o=Q[q3], x=o._r, p=Q[q2];
    const E=sgEst(q3, Rc(q3), gAuto);
    const osg=E?E.sg.osg:(p&&p.sg?p.sga-p.sg.ad-p.sg.cm-p.sg.fr:0.07*o.rev)*(1+gO), sga=o._sg.ad+o._sg.cm+o._sg.fr+osg;
    o.oth=x.op0!=null?x.op-x.op0:x.fxv; o.cogs=o.rev-sga+o.oth-o.op; o.sga=sga;
    o.sg={ad:o._sg.ad, cm:o._sg.cm, fr:o._sg.fr, ...(E?E.sg:{}), osg}; o.why=E?E.why:null; o.est={cogs:1, osg:1}; }
  // 비율·민감도 기준
  const sameQ=(k,qi)=>{ const qs=act.filter(q=>+q.slice(-1)===qi&&Q[q].sg&&Q[q].rev>0); const q=qs[qs.length-1]; return q?Q[q].sg[k]/Q[q].rev:null; };
  const flo={ad:A.adF/100, cm:A.cmF/100, fr:A.frF/100};
  const ratio=(k,qi)=>Math.max(flo[k], sameQ(k,qi)||0);
  const base=Q[q3]||Q[lastAct];
  const cogsAuto=(base.cogs+(base.ir&&base._r?base._r.tariff:0))/Rc(base.q);          // 관세 환급(일회성)은 빼고 잰다
  const cogsR=A.cogsB!=null?A.cogsB/100:cogsAuto;
  const h1=["2026Q1","2026Q2"].filter(q=>Q[q]&&!Q[q].ir&&Rc(q)), cogsH1=h1.length?h1.reduce((t,q)=>t+Q[q].cogs,0)/h1.reduce((t,q)=>t+Rc(q),0):null;
  const osgR=(base.sg.osg!=null?base.sg.osg:(base.sga-base.sg.ad-base.sg.cm-base.sg.fr))/Rc(base.q);
  const d3=Iend(q3)/Iend(q2)-1, expo=(base.ir&&d3<-0.005)?base._r.fxv/d3/base.reg.R해외:0;         // 외화 매출채권 평가손 민감도(해외 매출 대비)
  const dom=k=>Q[k]&&Q[k].reg.R한국;
  const dQ=["2025Q4","2026Q1","2026Q2","2026Q3"].filter(q=>dom(q)!=null&&dom(c2QAdd(q,-4))!=null);   // 국내 부문은 2025Q1 부터 — 있는 분기끼리
  const gDAuto=dQ.length?(dQ.reduce((t,q)=>t+dom(q),0)/dQ.reduce((t,q)=>t+dom(c2QAdd(q,-4)),0)-1)/2:0;
  const gD27=A.gD27!=null?A.gD27/100:gDAuto, g27=A.g27/100;
  // 영업외·세율 — 최근 4분기
  const L4=act.slice(-4).map(q=>Q[q]);
  const nonop=(()=>{ const v=L4.map(x=>x.pbt-x.op).sort((a,b)=>a-b); return (v[1]+v[2])/2; })();
  const sP=L4.reduce((t,x)=>t+x.pbt,0), sN=L4.reduce((t,x)=>t+x.np,0), tax=sP>0?Math.min(0.3,Math.max(0.15,(sP-sN)/sP)):0.24;
  // 추정 칸
  const COLS=["2025Q1","2025Q2","2025Q3","2025Q4","2026Q1","2026Q2","2026Q3","2026Q4","2027Q1","2027Q2","2027Q3","2027Q4"];
  const kYTD={}; COLS.forEach(q=>{ if(Q[q]&&Q[q].act){ const y=q.slice(0,4); kYTD[q]=(kYTD[c2QAdd(q,-1)]&&c2QAdd(q,-1).slice(0,4)===y?kYTD[c2QAdd(q,-1)]:0)+(Q[q].reg.R해외||0); } });
  let fYTD={}; COLS.forEach(q=>{ if(fc[q]!=null){ const y=q.slice(0,4), p=c2QAdd(q,-1); fYTD[q]=(p.slice(0,4)===y&&fYTD[p]!=null?fYTD[p]:0)+fc[q]; } });
  const bl={}; if(fc[lastAct]!=null) bl[lastAct]=fc[lastAct]/((+lastAct.slice(-1)===2||+lastAct.slice(-1)===4)?1+e4:1);
  COLS.filter(q=>!Q[q]&&q>lastAct).forEach(q=>{
    const y=+q.slice(0,4), qi=+q.slice(-1), p=c2QAdd(q,-1), q4=c2QAdd(q,-4), why={};
    // 해외 물량
    // 기초 물량(행사 효과 뺀 값) — 4Q26 = 3Q26 × (1+g) · 2027 = 직전 분기 기초 × (1+g27)^¼ · 행사 분기(2Q 프라임데이 · 4Q 빅딜데이·블프)는 × (1+e)
    const ev=(qi===2||qi===4)?1+e4:1, gq=y===2026?g4:Math.pow(1+g27,0.25)-1;
    bl[q]=bl[p]*(1+gq); const f=bl[q]*ev;
    why.f=y===2026?`3Q26 물량 × (1+기초 성장 ${fmt(g4*100,1)}%) × (1+행사 효과 ${fmt(e4*100,1)}%)`
      :`기초 물량 ${fmt(bl[p],1)} × (1+${fmt(g27*100,0)}%)^¼${ev>1?` × (1+행사 효과 ${fmt(e4*100,1)}%)`:""}`;
    fc[q]=f; const fy=(p.slice(0,4)===String(y)&&fYTD[p]!=null?fYTD[p]:0)+f; fYTD[q]=fy;
    const kPrev=(p.slice(0,4)===String(y)&&kYTD[p]!=null)?kYTD[p]:0;
    const ov=fy*Iavg(y,qi)-kPrev; kYTD[q]=kPrev+ov;
    const catchup=kPrev>0?(fy-f)*Iavg(y,qi)-kPrev:0;                    // 지난 분기 몫의 재환산(원화 강세면 −)
    why.ov=`물량 ${fmt(f,1)} × 누적 평균 환율 지수 ${fmt(Iavg(y,qi),3)}`+(Math.abs(catchup)>=0.05?` · 지난 분기 몫 재환산 ${catchup>=0?"+":""}${fmt(catchup,1)}`:"");
    // 국내
    const dm=y===2026?(Q[p].reg.R한국*((dom("2025Q4")&&dom("2025Q3"))?dom("2025Q4")/dom("2025Q3"):1)):Q[q4].reg.R한국*(1+gD27);
    const rev=ov+dm, rc=f+dm;
    const osgP=Q[p].sg?(Q[p].sg.osg!=null?Q[p].sg.osg:Q[p].sga-Q[p].sg.ad-Q[p].sg.cm-Q[p].sg.fr):rc*osgR;
    const E=sgEst(q, rc, gq); if(E) Object.assign(why, E.why);
    const sg={ad:rev*ratio("ad",qi), cm:rev*ratio("cm",qi), fr:rev*ratio("fr",qi), ...(E?E.sg:{osg:osgP*(1+Math.min(gO,gq))})};   // 고정비는 물량보다 빨리 늘지 않게
    const sga=sg.ad+sg.cm+sg.fr+sg.osg, cogs=rc*cogsR-(y===2026&&qi===4?A.refund:0);
    const dI=Iend(q)/Iend(p)-1, oth=expo*ov*dI;
    why.oth=`해외 매출 ${fmt(ov,1)} × 분기 마지막 달 환율 변화 ${dI>=0?"+":""}${fmt(dI*100,1)}% × 민감도 ${fmt(expo,3)}`;
    const op=rev-cogs-sga+oth, pbt=op+nonop, np=pbt>0?pbt*(1-tax):pbt;
    // 제품 — 디바이스 = 전년 동기 × (1 + 3Q26 전년비) · 기타 = 3Q26 유지 · 화장품 = 나머지(보기용)
    const dv3=Q[q3]&&Q["2025Q3"]&&Q[q3].seg.디바이스&&Q["2025Q3"].seg.디바이스?Q[q3].seg.디바이스/Q["2025Q3"].seg.디바이스-1:0;
    const dv=(Q[q4]&&Q[q4].seg.디바이스!=null)?Q[q4].seg.디바이스*(y===2026?1+dv3:1):null, et=Q[q3]?Q[q3].seg.기타:null;
    Q[q]={q, act:false, rev, cogs, sga, sg, oth, op, pbt, np, npp:np, reg:{"R해외":ov, "R한국":dm}, seg:dv!=null?{"디바이스":dv, "기타":et, "화장품":rev-dv-(et||0)}:{}, why, catchup};
  });
  // 연간
  const Y={};
  ["2025","2026","2027"].forEach(y=>{ const qs=[1,2,3,4].map(i=>Q[`${y}Q${i}`]); if(qs.some(x=>!x)) return;
    const s=k=>qs.reduce((t,x)=>t+(x[k]||0),0), ss=(g,k)=>qs.every(x=>x[g]&&x[g][k]!=null)?qs.reduce((t,x)=>t+x[g][k],0):null;
    Y[y]={q:y, yr:true, act:qs.every(x=>x.act), rev:s("rev"), cogs:s("cogs"), sga:s("sga"), oth:s("oth"), op:s("op"), pbt:s("pbt"), np:s("np"), npp:s("npp"),
      sg:qs.every(x=>x.sg)?{ad:qs.reduce((t,x)=>t+x.sg.ad,0), cm:qs.reduce((t,x)=>t+x.sg.cm,0), fr:qs.reduce((t,x)=>t+x.sg.fr,0),
        osg:qs.reduce((t,x)=>t+(x.sg.osg!=null?x.sg.osg:x.sga-x.sg.ad-x.sg.cm-x.sg.fr),0),
        ...(qs.every(x=>x.sg.hr!=null)?Object.fromEntries(["hr","fee","dep","pk","etc"].map(k=>[k,qs.reduce((t,x)=>t+x.sg[k],0)])):{})}:null,
      seg:{"화장품":ss("seg","화장품"), "디바이스":ss("seg","디바이스"), "기타":ss("seg","기타")}, reg:{"R해외":ss("reg","R해외"), "R한국":ss("reg","R한국")},
      est:qs.some(x=>x.est)}; });
  return {Q, Y, act, lastAct, fc, A, P:{gAuto, eAuto, g4, e4, g27, gD27, gDAuto, cogsR, cogsAuto, cogsH1, osgR, gO, gK, pkR, seaE, expo, nonop, tax, ratio, d3},
    fx:{usd:q=>fxAvg("USD",q), eur:q=>fxAvg("EUR",q), Iq, lastYm}, COLS};
}

let aprOpen=(()=>{ try{ return JSON.parse(localStorage.getItem("aprOpen")||"{}")||{}; }catch(e){ return {}; } })();
function renderAprModel(host){
  if(!host) return;
  let B=null; try{ B=aprBuild(); }catch(e){ console.error("에이피알 모델", e); }
  if(!B){ host.innerHTML=""; return; }
  const {Q, Y, P, A}=B, name="에이피알";
  const f1=v=>(v==null||!isFinite(v))?"—":fmt(v,1);
  const pc=v=>(v==null||!isFinite(v))?"—":`<span class="${cls(v)}">${sign(v*100,0)}%</span>`;
  const chg=(c,b)=>(c==null||b==null||!(b>0))?"—":pc(c/b-1);
  const pc1=v=>(v==null||!isFinite(v))?"—":`<span class="${cls(v)}">${sign(v*100,1)}%</span>`;
  // 컨센 — 분기 = 증권사 리포트 평균(어닝 리비전 트래커 · 종목마다 최신 리포트 · 100일) → 없으면 네이버 · 연간 = 네이버(2026)·엑셀(2027) · 트래커 연간 영업이익은 마우스에
  const LS=(typeof LIVE!=="undefined"&&LIVE.stocks&&LIVE.stocks[name])||{}, cn=LS.cons||{}, cons={};
  ((cn.quarter||{}).series||[]).forEach(x=>{ if(x.e) cons[`${x.k.slice(0,4)}Q${Math.ceil(+x.k.slice(4,6)/3)}`]={rev:x.rev, op:x.op, np:x.np, src:"네이버 컨센"}; });
  ((cn.year||{}).series||[]).forEach(x=>{ if(x.e) cons[x.k.slice(0,4)]={rev:x.rev, op:x.op, np:x.np, eps:x.eps, src:"네이버 컨센"}; });
  const R0=(typeof byName!=="undefined"&&byName[name])||{};
  if(R0.rev27!=null&&!cons["2027"]){ const c6=cons["2026"]; cons["2027"]={rev:R0.rev27, op:R0.op27, np:(c6&&c6.np&&c6.eps&&R0.eps27)?c6.np*R0.eps27/c6.eps:null, src:"엑셀 컨센(27E · 순이익 = 26E × EPS 비율)", xl:1}; }
  const RV=(typeof REVISION!=="undefined"&&REVISION.stocks&&REVISION.stocks[name])||null;
  const qk=p=>{ const m=/^([1-4])Q(\d\d)$/.exec(p||""); if(m) return `20${m[2]}Q${m[1]}`; const y=/^(\d{4})E$/.exec(p||""); return y?y[1]:null; };
  const MK={"매출":"rev","영업이익":"op","지배순이익":"np"};
  if(RV){
    const put=(p,list,seg,done)=>{ const k=qk(p); if(!k||!list) return; const c={src:`증권사 리포트 평균${done?"(발표 전)":""} · 리비전 트래커`, n:{}};
      list.forEach(s=>{ const m=MK[s.m]; if(m&&s.c!=null){ c[m]=s.c; c.n[m]=s.n; } });
      (seg||[]).forEach(s=>{ const m=s.s==="해외"?"ov":s.s==="한국"?"dm":null; if(!m||s.lv!==0) return;
        const v=done?(s.sa!=null&&s.ss!=null?s.sa/(1+s.ss):null):s.sc; if(v!=null) c[m]=v; });
      if(c.rev!=null||c.op!=null) cons[k]=c; };
    if(RV.done) put(RV.done.q, RV.done.sur, RV.done.seg, true);
    if(RV.next) put(RV.next.q, RV.next.cons, RV.next.seg, false);
    ((RV.done&&RV.done.rev)||[]).forEach(r=>{ const k=qk(r.p), v=r.post!=null?r.post:r.pre; if(!k||v==null) return;
      if(!cons[k]) cons[k]={op:v, n:{op:r.post!=null?r.n:r.np}, src:`증권사 리포트 평균 · 리비전 트래커`};
      else if(/^\d{4}$/.test(k)) cons[k].opT={v, n:r.post!=null?r.n:r.np, post:r.post!=null}; });
  }
  const cols=B.COLS.map(q=>Q[q]).filter(Boolean).concat(["2025","2026","2027"].map(y=>Y[y]).filter(Boolean));
  const nextQ=(cols.find(o=>!o.yr&&!o.act)||{}).q;
  const lab=o=>o.yr?`${o.q}${o.act?"A":"E"}`:`${c2QLab(o.q)}${o.act?(o.ir?"P":""):"E"}`;
  const prevOf=o=>o.yr?Y[String(+o.q-1)]:Q[c2QAdd(o.q,-4)];
  const mc=LS.mktcapEok?LS.mktcapEok/10:null;
  const open={rev:false, sga:true, cons:true, ...aprOpen};
  const osgOf=o=>o.sg?(o.sg.osg!=null?o.sg.osg:o.sga-o.sg.ad-o.sg.cm-o.sg.fr):null;
  const ROWS=[
    {t:"매출액", k:"rev", em:1, tg:"rev"}, {t:"YoY", r:"yoy"}, {t:"QoQ", r:"qoq"},
    {t:"화장품", g:"rev", v:o=>o.seg.화장품}, {t:"뷰티 디바이스", g:"rev", v:o=>o.seg.디바이스}, {t:"기타", g:"rev", v:o=>o.seg.기타},
    {t:"해외", g:"rev", v:o=>o.reg.R해외, tip:o=>o.why&&o.why.ov}, {t:"국내", g:"rev", v:o=>o.reg.R한국}, {t:"해외 비중", g:"rev", p:o=>o.reg.R해외!=null&&o.rev?o.reg.R해외/o.rev:null},
    {t:"해외 · 고정 환율(2025 평균)", g:"rev", v:o=>o.yr?null:B.fc[o.q], tip:o=>o.why&&o.why.f, sm:1},
    {t:"원/달러 · 원/유로(분기 평균)", g:"rev", h:o=>o.yr?"":`${fmt0(B.fx.usd(o.q))} · ${fmt0(B.fx.eur(o.q))}`, sm:1},
    {t:"매출원가", k:"cogs", est:"cogs"}, {t:"원가율", p:o=>o.cogs/o.rev, sub:1, est:"cogs"},
    {t:"매출총이익", v:o=>o.rev-o.cogs, em:1, est:"cogs"}, {t:"매출총이익률", p:o=>(o.rev-o.cogs)/o.rev, sub:1, est:"cogs"},
    {t:"판매비와관리비", k:"sga", tg:"sga"}, {t:"판관비율", p:o=>o.sga/o.rev, sub:1},
    {t:"광고선전비", g:"sga", v:o=>o.sg&&o.sg.ad, rp:"ad"}, {t:"판매수수료", g:"sga", v:o=>o.sg&&o.sg.cm, rp:"cm"}, {t:"운반비", g:"sga", v:o=>o.sg&&o.sg.fr, rp:"fr"},
    {t:"인건비", g:"sga", v:o=>o.sg&&o.sg.hr, rp:"hr", est:"osg", tip:o=>o.why&&o.why.hr},
    {t:"지급수수료·상각·포장 등", g:"sga", v:o=>o.sg&&o.sg.hr!=null?o.sg.fee+o.sg.dep+o.sg.pk+o.sg.etc:null, rp:"o2", est:"osg", tip:o=>o.why&&o.why.o2},
    {t:"원화 비용 합(인건비·지급수수료 등)", g:"sga", v:o=>osgOf(o), rp:"osg", est:"osg", tip:o=>o.why&&o.why.hr?"인건비 + 지급수수료·상각·포장 등 — 위 두 줄(항목마다 성격대로 · 칸에 마우스)":""},
    {t:"기타영업손익(외환 평가 · IFRS 18)", k:"oth"},
    {t:"영업이익", k:"op", em:1}, {t:"영업이익률", p:o=>o.op/o.rev, sub:1}, {t:"YoY", r:"opyoy"},
    {t:"세전이익", k:"pbt"}, {t:"지배주주 순이익", k:"npp", em:1}, {t:"PER(현재 시총)", r:"per"},
  ];
  const valOf=(o,r)=>{
    if(r.r==="yoy") return {h:chg(o.rev,(prevOf(o)||{}).rev)};
    if(r.r==="qoq") return {h:o.yr?"":chg(o.rev,(Q[c2QAdd(o.q,-1)]||{}).rev)};
    if(r.r==="opyoy") return {h:chg(o.op,(prevOf(o)||{}).op)};
    if(r.r==="per") return {h:(o.yr&&mc&&o.npp>0)?`${fmt(mc/o.npp,1)}배`:""};
    if(r.h) return {h:r.h(o)};
    if(r.p){ const v=r.p(o), ap=o.est&&r.est&&o.est[r.est]?"≈":""; return {h:(v==null||!isFinite(v))?"—":`${ap}${fmt(v*100,1)}%`}; }
    const v=r.v?r.v(o):o[r.k];
    if(v==null||!isFinite(v)) return {h:"—"};
    const pct=r.rp&&o.rev?`<span class="g" style="font-size:10.5px"> ${fmt(v/(r.rp==="osg"?o.rev:o.rev)*100,1)}%</span>`:"";
    const approx=(o.est&&r.est&&o.est[r.est])||(o.ir&&r.rp&&r.rp!=="osg");
    const t0=r.tip&&!o.yr?r.tip(o):"";
    const tip=t0?t0:!o.act&&!o.yr?(({cogs:`고정 환율 매출 × ${fmt(P.cogsR*100,1)}%(${A.cogsB!=null?"입력":"3Q26 역산 · 관세 환급 뺀 값"} — 원화 비용)`, sga:"", oth:(o.why&&o.why.oth)||""})[r.k]||(r.rp?({ad:`매출 × ${fmt(P.ratio("ad",+o.q.slice(-1))*100,1)}%`, cm:`매출 × ${fmt(P.ratio("cm",+o.q.slice(-1))*100,1)}%`, fr:`매출 × ${fmt(P.ratio("fr",+o.q.slice(-1))*100,1)}%`, osg:`직전 분기 × (1+${fmt(Math.min(P.gO,(o.q<"2027"?P.g4:Math.pow(1+P.g27,0.25)-1))*100,1)}%) — 고정비 성격(최근 4분기 평균 증가율 ${fmt(P.gO*100,1)}% · 물량 성장보다 빠르게는 안 늘린다)`})[r.rp]:"")||"")
      :(o.ir&&approx?(r.est?"역산 — 매출 − 영업이익 − 광고·수수료·운반(컨콜 비율) − 인건비·지급수수료 등(항목별 추정) + 외환 평가손. 3분기보고서가 나오면 바뀐다":"컨콜 비율(약)"):"");
    return {h:(approx?"≈":"")+f1(v)+pct, tip};
  };
  const yrEdge=i=>i>0&&(cols[i].yr!==cols[i-1].yr||(!cols[i].yr&&cols[i].q.slice(0,4)!==cols[i-1].q.slice(0,4)));
  const th=cols.map((o,i)=>`<th style="${yrEdge(i)?"border-left:2px solid var(--line);":""}${o.q===nextQ?"background:color-mix(in srgb, var(--accent) 14%, transparent);":""}">${lab(o)}</th>`).join("");
  const body=ROWS.filter(r=>!r.g||open[r.g]).map(r=>{
    const tog=r.tg?`<span data-aprtg="${r.tg}" style="cursor:pointer;color:var(--muted);margin-right:4px">${open[r.tg]?"▾":"▸"}</span>`:"";
    const sub=r.sub||!!r.r||!!r.g;
    return `<tr${r.em?' style="font-weight:800"':""}><td class="l" style="${r.g?"padding-left:22px;":""}${sub?"color:var(--muted);font-size:11.5px;":""}">${tog}${attr(r.t)}</td>`
      +cols.map((o,i)=>{ const v=valOf(o,r); const shade=o.q===nextQ?"background:color-mix(in srgb, var(--accent) 8%, transparent);":"";
        return `<td style="${yrEdge(i)?"border-left:2px solid var(--line);":""}${shade}${r.em?"border-top:1px solid var(--line);border-bottom:1px solid var(--line);":""}${r.sm?"font-size:11px;color:var(--muted);":""}"${v.tip?` title="${attr(v.tip)}"`:""}>${v.h}</td>`; }).join("")+`</tr>`; }).join("");
  // 컨센 대비 (2026-10-30 사용자 "밑에 각각 우리 추정이 컨센 대비 어떤지") — 우리 ÷ 컨센 − 1 · 3Q26P 는 잠정실적 ÷ 발표 전 컨센(서프라이즈)
  const cTip=(o,c,m)=>{ const n=c.n&&c.n[m]; let s=`${c.src}${n?` · ${n}곳`:""}`;
    if(o.act) s=`잠정실적 ÷ 발표 전 컨센 = 서프라이즈 · ${s}`;
    if(m==="op"&&c.opT) s+=` · 트래커 증권사 평균 ${fmt(c.opT.v,1)}(${c.opT.n}곳${c.opT.post?" · 실적 뒤 수정":" · 발표 전"})`;
    return s; };
  const dTip=(o,c)=>c.rev>0&&c.op!=null?`영업이익 차이 ${sign(o.op-c.op,1)} = 매출 차이 × 컨센 이익률 ${sign((o.rev-c.rev)*c.op/c.rev,1)} + 우리 매출 × 이익률 차이 ${sign(o.rev*(o.op/o.rev-c.op/c.rev),1)}`:"";
  const CR=[
    {t:"컨센 대비 · 영업이익", em:1, tg:"cons", m:"op", h:(o,c)=>c.op>0?pc1(o.op/c.op-1):""},
    {t:"컨센 매출", g:"cons", m:"rev", h:(o,c)=>c.rev!=null?f1(c.rev):"", mute:1},
    {t:"우리 ÷ 컨센", g:"cons", m:"rev", h:(o,c)=>c.rev>0?pc1(o.rev/c.rev-1):""},
    {t:"해외 우리 ÷ 컨센", g:"cons", m:"ov", h:(o,c)=>c.ov>0&&o.reg.R해외!=null?pc1(o.reg.R해외/c.ov-1):"", tip:(o,c)=>c.ov>0?`해외 컨센 ${fmt(c.ov,1)} · 우리 ${fmt(o.reg.R해외,1)}`:""},
    {t:"국내 우리 ÷ 컨센", g:"cons", m:"ov", h:(o,c)=>c.dm>0&&o.reg.R한국!=null?pc1(o.reg.R한국/c.dm-1):"", tip:(o,c)=>c.dm>0?`국내 컨센 ${fmt(c.dm,1)} · 우리 ${fmt(o.reg.R한국,1)}`:""},
    {t:"컨센 영업이익", g:"cons", m:"op", h:(o,c)=>c.op!=null?f1(c.op):"", mute:1},
    {t:"영업이익률 우리 − 컨센", g:"cons", m:"op", h:(o,c)=>{ if(!(c.rev>0)||c.op==null) return ""; const d=(o.op/o.rev-c.op/c.rev)*100; return `<span class="${cls(d)}">${sign(d,1)}%p</span>`; }},
    {t:"영업이익 차이 중 매출 몫", g:"cons", m:"op", h:(o,c)=>{ if(!(c.rev>0)||c.op==null) return ""; const a=(o.rev-c.rev)*c.op/c.rev; return `<span class="${cls(a)}">${sign(a,1)}</span>`; }, tip:(o,c)=>dTip(o,c)},
    {t:"영업이익 차이 중 이익률 몫", g:"cons", m:"op", h:(o,c)=>{ if(!(c.rev>0)||c.op==null) return ""; const b=o.rev*(o.op/o.rev-c.op/c.rev); return `<span class="${cls(b)}">${sign(b,1)}</span>`; }, tip:(o,c)=>dTip(o,c)},
    {t:"컨센 지배주주 순이익", g:"cons", m:"np", h:(o,c)=>c.np!=null?f1(c.np):"", mute:1},
    {t:"우리 ÷ 컨센", g:"cons", m:"np", h:(o,c)=>c.np>0&&o.npp!=null?pc1(o.npp/c.np-1):""},
  ];
  const consRow=CR.filter(r=>!r.g||open[r.g]).map(r=>{
    const tog=r.tg?`<span data-aprtg="${r.tg}" style="cursor:pointer;color:var(--muted);margin-right:4px">${open[r.tg]?"▾":"▸"}</span>`:"";
    return `<tr${r.em?' style="font-weight:800"':""}><td class="l" style="${r.g?"padding-left:22px;color:var(--muted);font-size:11.5px;":""}">${tog}${attr(r.t)}</td>`
      +cols.map((o,i)=>{ const c=cons[o.q], h=c?r.h(o,c):"", tp=c&&h?((r.tip&&r.tip(o,c))||cTip(o,c,r.m)):"";
        return `<td style="${yrEdge(i)?"border-left:2px solid var(--line);":""}${o.q===nextQ?"background:color-mix(in srgb, var(--accent) 8%, transparent);":""}${r.em?"border-top:2px solid var(--line);":""}${r.mute?"color:var(--muted);font-size:11px;":""}"${tp?` title="${attr(tp)}"`:""}>${h}</td>`; }).join("")+`</tr>`; }).join("");
  const card=(t,v,sub)=>`<div style="flex:1;min-width:170px;background:var(--panel);border:1px solid var(--line-soft);border-radius:var(--radius);padding:12px 14px">
    <div style="font-size:11.5px;color:var(--muted);font-weight:700">${t}</div><div style="font-size:19px;font-weight:800;margin-top:3px">${v}</div>
    <div style="font-size:11px;color:var(--muted2);margin-top:3px;line-height:1.45">${sub||""}</div></div>`;
  const vsC=o=>{ const c=cons[o.q]; return c&&c.rev>0?`컨센 ${f1(c.rev)} / ${f1(c.op)} 대비 ${pc1(o.rev/c.rev-1)} / ${c.op>0?pc1(o.op/c.op-1):"—"} · 이익률 ${fmt(o.op/o.rev*100,1)}%(컨센 ${fmt(c.op/c.rev*100,1)}%)`:`이익률 ${fmt(o.op/o.rev*100,1)}%`; };
  const nq=Q[nextQ], y6=Y["2026"], y7=Y["2027"];
  // 가이던스(3Q26 실적발표) — 매출 3조 이상 · 영업이익 7,300~7,500억
  const gd=y6?`가이던스 매출 3,000+ · 영업이익 730~750 대비 ${y6.rev>=3000?"매출 충족":"매출 미달"} · 영업이익 ${y6.op>=730?"충족":`${fmt(730-y6.op,1)} 모자람`}`:"";
  const head=`<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px">
    ${nq?card(`${lab(nq)} 매출 / 영업이익`, `${f1(nq.rev)} / ${f1(nq.op)}`, vsC(nq)):""}
    ${y6?card("2026E 매출 / 영업이익", `${f1(y6.rev)} / ${f1(y6.op)}`, vsC(y6)+"<br>"+gd):""}
    ${y7?card("2027E 매출 / 영업이익", `${f1(y7.rev)} / ${f1(y7.op)}`, vsC(y7)):""}
    ${(y6&&mc&&y6.npp>0)?card("PER(현재 시총)", `${fmt(mc/y6.npp,1)} / ${y7&&y7.npp>0?fmt(mc/y7.npp,1):"—"}배`, `2026 / 2027 지배주주 순이익 · 시총 ${fmt0(mc*10)}억`):""}
  </div>`;
  // 아마존 교차 확인(채널 모델 · 진행 분기) — 모델 해외 물량 QoQ 와 견준다
  let amz="";
  try{ const px=ISM_PX.kbch("에이피알",["US","CA","UK","DE","FR","IT","ES","JP"]); const a3=px["2026Q3"], a4=px["2026Q4"];
    if(a3&&a4&&a4.e&&nq) amz=`<br><b>교차 확인</b> 아마존 8개국 판매 진행 추정 4Q26 ${f1(a4.v)} = 3Q 의 ${fmt(a4.v/a3.v,2)}배(10월 30일 · 빅딜데이 포함 × 작년 11·12월 배수) — 모델 해외 물량은 ${fmt(B.fc[nextQ]/B.fc["2026Q3"],2)}배. 아마존이 맞으면 위쪽 위험`; }catch(e){}
  const method=`<div class="note" style="margin-top:6px;line-height:1.75">
    <b>해외</b> 고정 환율 물량 × 그 해 누적 평균 환율(회사 인식 방식 — 원화가 강해지면 지난 분기 몫까지 깎인다) · 앞으로 환율 = 지금(원/달러 ${fmt0(B.fx.usd(nextQ||"2026Q4"))})
    <br><b>물량</b> 4Q26 = 3Q × (1+${fmt(P.g4*100,1)}% 기초 성장) × (1+${fmt(P.e4*100,1)}% 행사 효과) — 2026 1~3Q 에서(2Q 프라임데이) · 2027 = 4Q26 기초에서 연 ${fmt(P.g27*100,0)}%(보수 · 2026 은 연 ${fmt((Math.pow(1+P.gAuto,4)-1)*100,0)}%) · 2Q·4Q 행사 효과
    <br><b>국내</b> 4Q = 3Q × 작년 4Q/3Q · 2027 = 2026 × (1${P.gD27>=0?"+":""}${fmt(P.gD27*100,1)}%)
    <br><b>광고·수수료·운반</b> 매출 × 비율 — 3Q26 컨콜 수준(${A.adF}·${A.cmF}·${A.frF}%)과 최근 같은 분기 실적 중 높은 쪽(개선 없음 · 4Q 수수료 ${fmt(P.ratio("cm",4)*100,1)}% = 4Q25)
    <br><b>매출원가</b> 고정 환율 매출 × ${fmt(P.cogsR*100,1)}%(${A.cogsB!=null?"입력":"3Q26 역산"} · 1H26 ${P.cogsH1!=null?fmt(P.cogsH1*100,1)+"%":"—"}) — 원화 비용이라 원화 강세면 매출 대비 오른다 · 관세 환급(일회성) 뺌
    <br><b>인건비·지급수수료·상각</b> 고정비 — 직전 분기 × (1+항목 증가율: 인건비 ${fmt(P.gK.hr*100,1)} · 지급수수료 ${fmt(P.gK.fee*100,1)} · 상각 ${fmt(P.gK.dep*100,1)}%/분기 = 최근 4분기 ÷ 그 전 4분기) · 물량 성장보다 빠르게는 안 늘린다(2027 분기 ${fmt((Math.pow(1+P.g27,0.25)-1)*100,1)}%)
    <br><b>포장비</b> 물량 비례 — 고정 환율 매출 × ${fmt(P.pkR*100,2)}% · <b>기타</b>(임차·소모품·세금과공과 등) 연말에 몰리는 반고정 — [전년 동기 × (1+${fmt(P.gK.etc*100,0)}%)] 와 [직전 분기 × 계절 배수(4Q ${fmt(P.seaE[4],2)})] 의 평균
    <br><b>컨센</b> 4Q26·1Q27 = 증권사 리포트 평균(리비전 트래커 · 종목별 최신 리포트 100일 — 3Q26 실적 뒤 수정한 리포트가 올라오면 바뀐다) · 2026 = 네이버 · 2027 = 엑셀 · 3Q26P 줄 = 잠정실적 ÷ 발표 전 컨센
    <br><b>기타영업손익</b> 외화 매출채권 평가(IFRS 18) = 해외 매출 × 분기 말 환율 변화 × 3Q26 민감도(평가손 ${fmt(-APR_IR["2026Q3"].fxv,1)} ÷ 환율 ${fmt(P.d3*100,1)}%) · 환율 그대로면 0
    <br><b>3Q26</b> 잠정실적(10/30) + 컨콜 비율(≈) · 원가·그 밖 판관비는 역산(≈) — 3분기보고서(11월 중순)가 들어오면 DART 값으로${amz}</div>`;
  const fv=v=>v==null?"":String(v);
  const asm=`<details class="fold" data-fold="apr_asm"${(()=>{ try{ return localStorage.getItem("fold_apr_asm")==="1"?" open":""; }catch(e){ return ""; } })()}><summary>가정 바꾸기 <span class="sub">물량 성장·행사 효과·비용률 하한·환율 — 이 브라우저에 기억</span></summary><div class="fold-b">
    <div style="display:flex;flex-wrap:wrap;gap:8px 16px;font-size:12px">
      <label>4Q26 기초 성장 <input data-apra="g4" type="number" step="1" value="${fv(A.g4)}" placeholder="${fmt(P.gAuto*100,1)}" style="width:58px"> % <span class="g">자동 ${fmt(P.gAuto*100,1)}%</span></label>
      <label>4Q26 행사 효과 <input data-apra="e4" type="number" step="1" value="${fv(A.e4)}" placeholder="${fmt(P.eAuto*100,1)}" style="width:58px"> % <span class="g">자동 ${fmt(P.eAuto*100,1)}%(2Q26 프라임데이)</span></label>
      <label>2027 해외 기초 성장(연) <input data-apra="g27" type="number" step="1" value="${fv(A.g27)}" style="width:58px"> %</label>
      <label>2027 국내 전년비 <input data-apra="gD27" type="number" step="1" value="${fv(A.gD27)}" placeholder="${fmt(P.gDAuto*100,1)}" style="width:58px"> %</label>
      <label>광고선전비 하한 <input data-apra="adF" type="number" step="0.5" value="${fv(A.adF)}" style="width:52px"> %</label>
      <label>판매수수료 하한 <input data-apra="cmF" type="number" step="0.5" value="${fv(A.cmF)}" style="width:52px"> %</label>
      <label>운반비 하한 <input data-apra="frF" type="number" step="0.5" value="${fv(A.frF)}" style="width:52px"> %</label>
      <label>원가율(고정 환율) <input data-apra="cogsB" type="number" step="0.5" value="${fv(A.cogsB)}" placeholder="${fmt(P.cogsAuto*100,1)}" style="width:58px"> % <span class="g">3Q26 역산 ${fmt(P.cogsAuto*100,1)}% · 1H26 ${P.cogsH1!=null?fmt(P.cogsH1*100,1)+"%":"—"}</span></label>
      <label>원/달러(앞으로) <input data-apra="usd" type="number" step="10" value="${fv(A.usd)}" placeholder="${fmt0(B.fx.usd(nextQ||"2026Q4"))}" style="width:66px"></label>
      <label>원/유로(앞으로) <input data-apra="eur" type="number" step="10" value="${fv(A.eur)}" placeholder="${fmt0(B.fx.eur(nextQ||"2026Q4"))}" style="width:66px"></label>
      <label>4Q26 관세 환급 <input data-apra="refund" type="number" step="1" value="${fv(A.refund)}" style="width:52px"> 십억 <span class="g">컨콜 '남은 것 100억 미만'</span></label>
      <button data-aprreset style="font-size:11.5px">기본값으로</button></div></div></details>`;
  const D=APRMODEL;
  host.innerHTML=`<div class="sub-h" style="margin:2px 0 8px">분기 손익 — 비용 구조 <span class="th-sub" style="display:inline;margin-left:6px">십억원 · P 잠정실적 · E 우리 추정 · ≈ 컨콜 비율·역산 · ▸ 세부</span></div>
    ${head}
    <div class="tbl-wrap"><table class="mini-tbl ism-t"><thead><tr><th class="l">${attr(name)}</th>${th}</tr></thead><tbody>${body}${consRow}</tbody></table></div>
    ${method}${asm}
    <p class="note">실적 DART 연결(손익 · 판관비 주석 ${(Object.keys(D.src||{}).sort().pop()||"").replace("-",".")}까지) · ${attr(APR_IR["2026Q3"].src)} · 환율 ECB 월평균 · 칸에 마우스 = 식</p>`;
  host.querySelectorAll("[data-aprtg]").forEach(el=>el.addEventListener("click",()=>{ const g=el.dataset.aprtg; aprOpen={...open}; aprOpen[g]=!open[g];
    try{ localStorage.setItem("aprOpen",JSON.stringify(aprOpen)); }catch(e){} renderAprModel(host); }));
  host.querySelectorAll("[data-apra]").forEach(i=>i.addEventListener("change",()=>{ const a={...aprAsmGet()};
    host.querySelectorAll("[data-apra]").forEach(x=>{ a[x.dataset.apra]=x.value===""?null:+x.value; });
    aprAsmSave(a); renderAprModel(host); }));
  const rb=host.querySelector("[data-aprreset]"); if(rb) rb.addEventListener("click",()=>{ try{ localStorage.removeItem("aprAsm"); }catch(e){} renderAprModel(host); });
}
