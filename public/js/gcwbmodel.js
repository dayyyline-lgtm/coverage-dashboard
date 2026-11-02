/* ══════════ GC녹십자웰빙 분기 손익 모델 (2026-11-02 신설 · 11-03 개편 · GCWBMODEL ← gcwb_block.py · renderGcwbModel) ══════════
   사용자: "25년부터 DART 뜯어서 자세히 모델링 — 대시보드에도" → 11-03 "라이넥은 75% 수준으로 이해하는 게 맞아 보이네 · IS 자세히 · 제품·트렌드도".
   매출 = 라이넥(물량 × 공급가 · 9월부터 +20%) + IV 고용량(27년 하반기 가정) + 기타 제품(영양주사제 등) + 상품 + 자회사·조정(연결 − 별도)
   매출총이익 = 라이넥 물량 × 75% + 판가 인상분(원가 없음 · 100%) + 기타 제품 × 61% + (상품 + 자회사) × 22% + 4Q 연말 조정
     — 이익률은 평범한 네 분기(1Q25·2Q25·3Q25·1Q26)로 맞춘 값(오차 ±0.1십억). 라이넥 75% 는 원가 구조(원료 태반 = 폐기물 · 원가 = 공장 고정비)로 고정하고
       기타·상품을 맞췄다. 4Q25(−1.9)·2Q26(−2.5)는 이 식보다 덜 남았다 — 4Q = 연말 상여(원가 인건비 4Q +1.2) · 2Q26 = 가동률 44%(1H26 누적 53~55%)·재고 +10.8 시기 일회성으로 본다.
       여섯 분기 전부로 자유 회귀하면 라이넥 49%·기타 86% 가 나오는데 그건 2Q26 한 분기가 끌어낸 값이다(6점이라 구분 불가).
   판관비 = 성격별: 고정비(인건비·광고·연구개발·임차·판촉·그 밖) = 지금 수준 × 4Q 계절 배수(연말 상여 등) · 변동비 = 지급수수료(상품 × 8.8% 중앙값 · 2Q 11.1%) + 운반비(매출 × 1.29%)
   3Q26 = 잠정실적(매출·영업이익·순이익) — 판관비는 위 식 추정(≈), 매출총이익은 영업이익 + 판관비 역산(≈), 라이넥 물량은 그 매출총이익에 맞춘 역산. */
const GCWB_DEF={Lm:75, Om:60.8, Gm:22.2, q4:-1.2, price:20, L4g:5, Lg:11, iv2:0.5, iv3:1.5, iv4:2.5, oth3:-15, oth4:-12, gd4:-2, oth27:-5, gd27:12, sub27:4.2,
  feeR:8.8, feeR2:11.1, frR:1.29, bor:30, hrQ4:1.40, adQ4:1.31, rndQ4:1.55, rent:0.68, hr27:8, ad27:10, ot27:5, pe:12, ini:3.0};
// 2027 다듬기(11-03 · 사용자 "NH 추정치 기반으로 다듬고 확인 · 신한도 참고" — NH 9/30 27F 242.2/31.9 · 라이넥 70.0 / 신한 9/30 27F 256.6/38.8 · 라이넥 101.9):
//   라이넥 물량 = 2025 같은 분기 × (1+Lg)² — 2026 2Q·3Q 급증은 인상 전 선매입과 GLP-1 칵테일 처방이 섞여 못 가른다 → 2026 을 건너뛰고 2025 에서 2년 추세(2022~25 연 13% · 2025 +8% 의 가운데 11%)
//   IV 고용량(10ml) = 허가 1Q 말~2Q 초 · 출시 2Q 후반(NH) → 2Q 0.5 · 3Q 1.5 · 4Q 2.5 (전환된 정맥투여 회당 단가 +60%)
//   보령 공동판매 수수료 = 2차 병원 라이넥(분기 0.5 + IV) × 30% · 상품 +12%(마운자로 1년 차 뒤 둔화 + 리본느·지셀르) · 판관비 인건비 +8%(1H26 인원 +8%) · 광고 +10%(IV·에스테틱 출시)
// 3Q26 판관비 고정비 추정(십억) — 3Q25 수준에 인원 +4%(3Q25 322명 → 2Q26 335명) · 광고·연구개발은 1H26 흐름 · 임차는 내려오는 중(4Q25 0.86 → 1Q26 0.77 → 2Q26 0.72)
const GCWB_SG3={hr:4.69, ad:2.34, rnd:0.97, rent:0.70, promo:0.90, misc:1.85};
let gcwbOpen; try{ gcwbOpen=JSON.parse(localStorage.getItem("gcwbOpen")||"{}"); }catch(e){ gcwbOpen={}; }
function gcwbAsmGet(){ try{ const a=JSON.parse(localStorage.getItem("gcwbAsm")||"{}")||{}; return a.v===3?a:{v:3}; }catch(e){ return {v:3}; } }   // v3 = 11-03 개편 — 옛 저장값(이익률 65/78/17 등)은 버린다
function gcwbAsmSave(a){ try{ localStorage.setItem("gcwbAsm",JSON.stringify({...a, v:3})); }catch(e){} }
const GCWB_SGL=[["hr","인건비(급여·퇴직·복리·교육)","고정"],["ad","광고선전비","고정"],["rnd","경상연구개발비","고정"],["rent","임차료","고정"],
  ["promo","판촉(업무촉진·견본·접대·회의)","고정"],["misc","그 밖(여비·상각·외주용역·대손 등)","고정"],["fee","지급수수료","변동 · 상품"],["fr","운반비","변동 · 매출"]];
function gcwbBuild(){
  const G=typeof GCWBMODEL!=="undefined"?GCWBMODEL:null; if(!G||!G.q) return null;
  const U=gcwbAsmGet(), A={...GCWB_DEF}; Object.keys(U).forEach(k=>{ if(k!=="v"&&U[k]!=null&&isFinite(U[k])) A[k]=+U[k]; });
  const pc=k=>A[k]/100, Q={}, COLS=["2025Q1","2025Q2","2025Q3","2025Q4","2026Q1","2026Q2","2026Q3","2026Q4","2027Q1","2027Q2","2027Q3","2027Q4"];
  const sgOf=s=>{ if(!s) return null; const o={hr:s.hr,ad:s.ad,fee:s.fee,fr:s.fr,rent:s.rent,rnd:s.rnd,promo:s.promo,misc:(s.trv||0)+(s.etc||0)+(s.dep||0)+(s.out||0)+(s.bad||0)}; o.tot=s.tot; return o; };
  const gpOf=o=>o.Lv*pc("Lm")+(o.Lp||0)+(o.iv||0)*pc("Lm")+o.oth*pc("Om")+(o.goods+o.sub)*pc("Gm");   // 이익률 식(4Q 조정 전)
  Object.keys(G.q).forEach(k=>{ const d=G.q[k]; const o={q:k, act:true, rev:d.rev, gp:d.gp, sga:d.sga, op:d.op, nonop:d.oi-d.oe, fin:d.fi-d.fc, eq:d.eq, pbt:d.pbt, tax:d.tax, np:d.np,
      L:d.L, Lv:d.L, Lp:0, iv:0, oth:d.prod!=null?d.prod-d.L:null, goods:d.goods, gq:d.gq, sub:d.sep!=null?d.rev-d.sep:null, sg:sgOf(d.sg), ut:d.ut, inv:d.inv};
    if(o.oth!=null&&o.goods!=null&&o.sub!=null){ if(k==="2026Q2") o.goods=o.rev-o.L-o.oth-o.sub;   // 2Q26 별도 항목 합이 합계보다 0.42 많다(원문) — 연결 매출에 맞춘다
      o.gpRes=o.gp-gpOf(o); }
    Q[k]=o; });
  const fixOf=(sg)=>GCWB_SGL.filter(r=>r[2]==="고정").reduce((s,[kk])=>s+sg[kk],0);
  // 3Q26 — 잠정실적. 판관비 = 고정비(GCWB_SG3) + 변동비 → 매출총이익 = 영업이익 + 판관비 → 라이넥 물량 = 그 매출총이익을 이익률 식에 맞춘 값(닫힌 식)
  { const P3=G.p&&G.p["2026Q3"], R=P3.rev, OP=P3.op, O=Q["2025Q3"].oth*(1+pc("oth3")), S=3.5, p3=pc("price")/3, F=fixOf(GCWB_SG3), fee=pc("feeR"), fr=pc("frR");
    const Lv=(OP-O*pc("Om")-(R-O)*pc("Gm")+F+(R-O-S)*fee+R*fr)/(pc("Lm")+p3-(1+p3)*(pc("Gm")-fee));
    const Lp=Lv*p3, goods=R-Lv-Lp-O-S, sg={...GCWB_SG3, fee:goods*fee, fr:R*fr};
    sg.tot=GCWB_SGL.reduce((s,[kk])=>s+sg[kk],0);
    Q["2026Q3"]={q:"2026Q3", act:false, ir:true, rev:R, op:OP, np:P3.np, Lv, Lp, iv:0, L:Lv+Lp, oth:O, sub:S, goods, sg, sga:sg.tot, gp:OP+sg.tot, est:{gp:1,sga:1,mix:1}}; }
  // 4Q26 — 라이넥 물량 4Q25 × (1+L4g) · 판가 3개월 · 기타 제품 4Q25 × (1+oth4) · 상품 3Q26 × (1+gd4) · 자회사 3.3
  { const b=Q["2025Q4"], Lv=b.L*(1+pc("L4g")), Lp=Lv*pc("price"), oth=b.oth*(1+pc("oth4")), goods=Q["2026Q3"].goods*(1+pc("gd4")), sub=3.3;
    Q["2026Q4"]={q:"2026Q4", act:false, Lv, Lp, iv:0, L:Lv+Lp, oth, goods, sub, rev:Lv+Lp+oth+goods+sub}; }
  // 2027 — 라이넥 물량 = 2025 같은 분기 × (1+Lg)² (2026 선매입은 시점만 당긴 것으로 보고 2025 기준 2년 추세) · IV 는 분기 입력
  const vol26=["2026Q1","2026Q2","2026Q3","2026Q4"].reduce((s,k)=>s+Q[k].Lv,0);
  const excess=Math.max(0,Q["2026Q2"].Lv+Q["2026Q3"].Lv-(Q["2025Q2"].L+Q["2025Q3"].L)*1.08), v27=[1,2,3,4].reduce((s,i)=>s+Q[`2025Q${i}`].L,0)*Math.pow(1+pc("Lg"),2);
  const sh=["2025Q1","2025Q2","2025Q3","2025Q4"].map(k=>Q[k].L), t25=sh.reduce((a,b)=>a+b,0);
  ["2027Q1","2027Q2","2027Q3","2027Q4"].forEach((k,i)=>{ const b=Q[`2026Q${i+1}`], Lv=sh[i]*Math.pow(1+pc("Lg"),2), Lp=Lv*pc("price"), iv=[0,A.iv2,A.iv3,A.iv4][i];
    const oth=b.oth*(1+pc("oth27")), goods=b.goods*(1+pc("gd27")), sub=A.sub27;
    Q[k]={q:k, act:false, Lv, Lp, iv, L:Lv+Lp+iv, oth, goods, sub, rev:Lv+Lp+iv+oth+goods+sub}; });
  // 매출총이익·판관비 — 4Q26·2027
  COLS.slice(7).forEach(k=>{ const o=Q[k], n=+k.slice(5), q4=n===4;
    o.gpM=gpOf(o)+(q4?A.q4:0); o.gp=o.gpM;
    let sg;
    if(k==="2026Q4"){ const b=Q["2026Q3"].sg; sg={hr:b.hr*A.hrQ4, ad:b.ad*A.adQ4, rnd:b.rnd*A.rndQ4, rent:A.rent, promo:b.promo, misc:b.misc}; }
    else { const b=Q[`2026Q${n}`].sg, g=x=>1+pc(x); sg={hr:b.hr*g("hr27"), ad:b.ad*g("ad27"), rnd:b.rnd, rent:A.rent, promo:b.promo*g("ot27"), misc:b.misc*g("ot27")}; }
    o.bor=(0.5+(o.iv||0))*pc("bor"); sg.fee=o.goods*pc(n===2?"feeR2":"feeR")+o.bor; sg.fr=o.rev*pc("frR");   // 보령 공동판매(9/11 계약 · 2차 병원) 수수료
    sg.tot=GCWB_SGL.reduce((s,[kk])=>s+sg[kk],0); o.sg=sg; o.sga=sg.tot; o.op=o.gp-o.sga; });
  // 영업 밖 — 이자 분기 −1.15 · 기타손익 −0.15(4Q −0.5) · 지분법(이니바이오) 2026 분기 −1.1 · 2027 −1.0 → −0.6(중국 허가 10/27 뒤 판매) · 세율 22%
  COLS.slice(6).forEach(k=>{ const o=Q[k], y=k.slice(0,4);
    o.nonop=k.endsWith("Q4")?-0.5:-0.15; o.fin=-1.15; o.eq=y==="2026"?-1.1:[-1.0,-0.9,-0.7,-0.6][+k.slice(5)-1];   // 2027 = 이니보 중국 허가(10/27) 뒤 판매 시작 · 손실 축소
    if(!o.ir){ const pre=o.op+o.nonop+o.fin; o.tax=pre*0.22; o.pbt=pre+o.eq; o.np=pre-o.tax+o.eq; } });
  // 지분법·파생 제외 순이익 — 실적 분기는 금융손익 대신 이자만(2025 분기 0.78 · 2026 1.13): 1Q26 CB 파생 평가손 9.8 같은 출렁임을 뺀다
  COLS.forEach(k=>{ const o=Q[k], fc=o.act?(k.startsWith("2025")?-0.78:-1.13):o.fin; o.core=(o.op+o.nonop+fc)*(1-0.22); });
  const Y={};
  { const q4=["2024Q1","2024Q2","2024Q3","2024Q4"].map(k=>Q[k]).filter(Boolean);   // 2025A YoY 용(표에는 안 보인다)
    if(q4.length===4) Y["2024"]={q:"2024", yr:true, act:true, rev:q4.reduce((a,o)=>a+o.rev,0), op:q4.reduce((a,o)=>a+o.op,0), gp:q4.reduce((a,o)=>a+o.gp,0), sga:q4.reduce((a,o)=>a+o.sga,0), np:q4.reduce((a,o)=>a+o.np,0)}; }
  ["2025","2026","2027"].forEach(y=>{ const qs=COLS.filter(k=>k.startsWith(y)).map(k=>Q[k]), s=key=>qs.reduce((a,o)=>a+(o[key]||0),0);
    const sg={}; GCWB_SGL.forEach(([kk])=>{ sg[kk]=qs.reduce((a,o)=>a+((o.sg||{})[kk]||0),0); });
    Y[y]={q:y, yr:true, act:y==="2025", rev:s("rev"), L:s("L"), Lv:s("Lv"), Lp:s("Lp"), iv:s("iv"), oth:s("oth"), goods:s("goods"), sub:s("sub"), gp:s("gp"), sga:s("sga"), op:s("op"),
      nonop:s("nonop"), fin:s("fin"), eq:s("eq"), pbt:s("pbt"), tax:s("tax"), np:s("np"), core:s("core"), sg}; });
  return {Q, Y, COLS, A, G, vol26, excess, v27};
}
/* 제품 구성 — 무엇을 파나(2025 사업보고서 · 2026 반기보고서 · 11-02 정리). 숫자는 별도 매출실적(DART). */
const GCWB_CAT=[
  {g:"제품 · 자체 제조(음성 혁신공장)", it:"라이넥", d:"사람 태반 가수분해물 주사(전문의약품). 허가 효능은 간기능 개선, 실제 수요는 의원 비급여(피로·미용). 원료 태반은 분만 후 폐기물이라 원가 대부분이 공장 고정비. 2026-09 공급가 +20%. 2차 병원은 보령 공동판매.", k:"L"},
  {g:"", it:"영양주사제 등 기타 제품", d:"비타민·아미노산 등 영양 주사 · PDRN · 원프렙(장정결제). 일부는 외주 가공이라 라이넥보다 덜 남는다.", k:"oth"},
  {g:"상품 · 사 와서 파는 것", it:"전문의약품 상품", d:"마운자로(2025-08~ 영업) · 이니보(이니바이오 톡신, 2H25~) · 에스테틱(유스필 필러 · 필로드 · 듀라겐 · 지셀르 리본느) · 하프키트 · 히시파겐씨. 매출총이익률 약 22%, 지급수수료(8.8%)를 빼면 남는 게 얇다.", k:"g0"},
  {g:"", it:"건기식 상품", d:"병의원 채널 건강기능식품(Dr.PNT 등).", k:"g1"},
  {g:"자회사·조정", it:"어니스트리 · 연결 조정", d:"어니스트리(B2C 건기식) = 연결 − 별도. 이니바이오(톡신 제조)는 지분법이라 매출에 없다.", k:"sub"},
];
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
  const open={rev:true, sga:true, gp:false, ...gcwbOpen};
  const sgTip=(o,k)=>{ if(o.act||o.yr) return "";
    const n=+o.q.slice(5);
    if(k==="fee") return `상품 ${f2(o.goods)} × ${n===2?A.feeR2:A.feeR}%${n===2?"(2Q 계절)":"(1Q25~2Q26 중앙값)"}`;
    if(k==="fr") return `매출 × ${A.frR}%`;
    if(k==="rent") return o.ir?"2Q26 0.72 에서 조금 더":`${A.rent} — 4Q25 0.86 → 1Q26 0.77 → 2Q26 0.72 내려오는 중`;
    if(o.ir) return "3Q25 수준 + 인원 +4% · 1H26 흐름(추정)";
    if(o.q==="2026Q4") return k==="hr"?`3Q26 × ${A.hrQ4} — 연말 상여(판관 인건비 4Q/3Q 2022~25 1.41~1.54)`:k==="ad"?`3Q26 × ${A.adQ4}(4Q25/3Q25)`:k==="rnd"?`3Q26 × ${A.rndQ4}(4Q/3Q 2024·2025 평균)`:"3Q26 수준";
    return k==="hr"?`2026 같은 분기 × (1+${A.hr27}%)`:k==="ad"?`× (1+${A.ad27}%)`:k==="rnd"?"2026 같은 분기 그대로":`× (1+${A.ot27}%)`; };
  const ROWS=[
    {t:"매출액", k:"rev", em:1, tg:"rev"}, {t:"YoY", r:"yoy"},
    {t:"라이넥", g:"rev", k:"L", tip:o=>o.act?"DART '주요 제품 등에 관한 사항' 라이넥주 매출(누적 차분)":o.ir?`영업이익 ${f1(o.op)}에 맞춘 역산 — 물량 ${f2(o.Lv)} + 9월 인상분 ${f2(o.Lp)}`:""},
    {t:"· 물량(판가 제외)", g:"rev", k:"Lv", sm:1, tip:o=>o.act||o.yr?"":o.q==="2026Q4"?`4Q25 × (1${A.L4g>=0?"+":""}${A.L4g}%) — 2Q·3Q 선매입 뒤라 크게 안 늘린다`:o.q.startsWith("2027")?`2025 같은 분기 × (1+${A.Lg}%)² — 2026 선매입(2Q·3Q 초과 ${f1(B.excess)})은 시점만 당긴 것으로 보고 2025 기준 2년 추세`:""},
    {t:`· 판가 인상분(+${A.price}%)`, g:"rev", k:"Lp", sm:1, tip:o=>o.act||o.yr?"":`물량 × ${A.price}%${o.ir?" × 1/3(9월 한 달)":""} — 원가 없음(전액 매출총이익)`},
    {t:"· IV 고용량", g:"rev", k:"iv", sm:1},
    {t:"기타 제품(영양주사제 등)", g:"rev", k:"oth", tip:o=>o.yr?"":o.act?"별도 매출실적 제품(전문의약품+기타) − 라이넥":o.ir?`3Q25 × (1${A.oth3>=0?"+":""}${A.oth3}%)`:o.q==="2026Q4"?`4Q25 × (1${A.oth4>=0?"+":""}${A.oth4}%) — 1H26 −13%`:`2026 같은 분기 × (1${A.oth27>=0?"+":""}${A.oth27}%)`},
    {t:"상품", g:"rev", k:"goods", tip:o=>o.yr?"":o.act?"별도 매출실적 상품(전문의약품·건기식·기타)":o.ir?"잠정 매출 − 라이넥 − 기타 제품 − 자회사(역산)":o.q==="2026Q4"?`3Q26 × (1${A.gd4>=0?"+":""}${A.gd4}%)`:`2026 같은 분기 × (1+${A.gd27}%)`},
    {t:"자회사·조정(연결 − 별도)", g:"rev", k:"sub", sm:1},
    {t:"매출총이익", k:"gp", em:1, est:"gp", tg:"gp"}, {t:"매출총이익률", p:o=>o.gp/o.rev, sub:1, est:"gp"},
    {t:`라이넥 몫(물량 × ${A.Lm}% + 판가)`, g:"gp", v:o=>o.Lv!=null?o.Lv*A.Lm/100+(o.Lp||0)+(o.iv||0)*A.Lm/100:null, rp:1},
    {t:`기타 제품 몫(× ${A.Om}%)`, g:"gp", v:o=>o.oth!=null?o.oth*A.Om/100:null, rp:1},
    {t:`상품·자회사 몫(× ${A.Gm}%)`, g:"gp", v:o=>o.goods!=null&&o.sub!=null?(o.goods+o.sub)*A.Gm/100:null, rp:1},
    {t:"식 대비(실제 − 식 · 4Q 연말 조정)", g:"gp", v:o=>o.yr?null:o.act?o.gpRes:o.ir?0:o.q.endsWith("Q4")?A.q4:0,
      tip:o=>o.q==="2025Q4"?"연말: 원가 인건비 4Q 급증(2024 +0.5 · 2025 +1.2) + 재고 정리":o.q==="2026Q2"?"2Q26 가동률 44%(앰플·바이알) · 재고 +10.8 시기 — 고정비 덜 흡수·재고 관련 비용·인상 전 선매입 할인 중 무엇인지는 3분기보고서 성격별 비용으로":o.ir?"3Q26P 는 라이넥 물량을 역산해 0 으로 맞춘다":o.act||o.yr?"":o.q.endsWith("Q4")?"연말 상여(원가 쪽 2025 +1.2)":""},
    {t:"판매비와관리비", k:"sga", tg:"sga", est:"sga"}, {t:"판관비율", p:o=>o.sga/o.rev, sub:1, est:"sga"},
    ...GCWB_SGL.map(([k,t,ty])=>({t:`${t} · ${ty}`, g:"sga", v:o=>o.sg?o.sg[k]:null, rp:1, tip:o=>sgTip(o,k)})),
    {t:"영업이익", k:"op", em:1}, {t:"영업이익률", p:o=>o.op/o.rev, sub:1}, {t:"YoY", r:"opyoy"},
    {t:"기타손익 + 금융손익", v:o=>o.nonop+o.fin, tip:o=>o.yr?"":o.act?"1Q26 금융비용 9.8 = CB 전환권 파생상품 평가손 · 2Q26 되돌림":o.ir?"":"이자 분기 1.15(2Q26 이자비용 1.18) · 파생 평가손익 0 · 4Q 기타손익 −0.5"},
    {t:"지분법손익(이니바이오)", k:"eq", tip:o=>o.act||o.yr?"":"이니바이오 손실 × 지분율 — 2026 분기 −1.1(1H26 실적) · 2027 −0.9"},
    {t:"법인세", k:"tax", sm:1},
    {t:"순이익", k:"np", em:1},
    {t:"지분법·파생 제외 순이익", k:"core", sub:1, tip:()=>"(영업이익 + 기타손익 + 이자) × (1 − 22%) — 밸류에이션 기준"},
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
  // 제품 구성 — 분기 매출(별도 매출실적 · 십억)
  const AQ=COLS.slice(0,6), y25=fn=>AQ.slice(0,4).reduce((s,q)=>s+(fn(Q[q])||0),0);
  const catV={L:o=>o.L, oth:o=>o.oth, g0:o=>o.gq?o.gq[0]+o.gq[2]:null, g1:o=>o.gq?o.gq[1]:null, sub:o=>o.sub};
  const cat=`<div class="sub-h" style="margin:14px 0 6px">무엇을 파나 <span class="th-sub" style="display:inline;margin-left:6px">별도 매출실적 · 십억원 · 1H26 부문: 전문의약품 84.7 / 영업이익 10.5(12.3% · 1H25 16.1%) · 건기식 17.3 / −1.3</span></div>
    <div class="tbl-wrap"><table class="mini-tbl ism-t"><thead><tr><th class="l">구분</th><th class="l">무엇</th>${AQ.map(k=>`<th>${c2QLab(k)}</th>`).join("")}<th style="border-left:2px solid var(--line)">2025</th><th>1H26 YoY</th></tr></thead><tbody>
    ${GCWB_CAT.map(c=>{ const fn=catV[c.k], h1=(fn(Q["2026Q1"])||0)+(fn(Q["2026Q2"])||0), h0=(fn(Q["2025Q1"])||0)+(fn(Q["2025Q2"])||0);
      return `<tr><td class="l" style="color:var(--muted);font-size:11.5px;white-space:nowrap">${attr(c.g)}</td><td class="l" style="min-width:260px;max-width:380px;white-space:normal"><b>${attr(c.it)}</b><div style="font-size:11px;color:var(--muted);line-height:1.45;margin-top:2px">${attr(c.d)}</div></td>`
        +AQ.map(k=>`<td>${f1(fn(Q[k]))}</td>`).join("")+`<td style="border-left:2px solid var(--line)">${f1(y25(fn))}</td><td>${chg(h1,h0)}</td></tr>`; }).join("")}
    </tbody></table></div>`;
  // 공장·재고 — 공시 가동률(시간 기준)과 생산 수량은 방향이 다를 수 있다(1H26 시간당 생산량 1.5배)
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
    ${card("4Q26E 매출 / 영업이익", `${f1(q4.rev)} / ${f1(q4.op)}`, `${vs(q4,cq["2026Q4"])}<br>라이넥 물량 ${pc(q4.Lv/Q["2025Q4"].L-1)} + 판가 ${f2(q4.Lp)} · 판관비 ${f1(q4.sga)}(4Q25 ${f1(Q["2025Q4"].sga)})`)}
    ${card("2026E 매출 / 영업이익", `${f1(y6.rev)} / ${f1(y6.op)}`, vs(y6,cy["2026"]))}
    ${card("2027E 매출 / 영업이익", `${f1(y7.rev)} / ${f1(y7.op)}`, `이익률 ${fmt(y7.op/y7.rev*100,1)}% · 라이넥 ${f1(y7.L)}(판가 ${f1(y7.Lp)} · IV ${f1(y7.iv)})<br>증권사(9/30) NH 242.2 / 31.9 · 라이넥 70.0 · 신한 256.6 / 38.8 · 라이넥 101.9`)}
    ${card(`적정 시총(27E × ${A.pe}배)`, `${fmt0(fair*10)}억`, `지분법·파생 제외 순이익 ${f1(y7.core)} × ${A.pe} + 이니바이오 ${f1(A.ini)} · 주당 ${fmt0(perSh)}원(CB ${fmt(cb.left,0)}십억 전환 시 ${fmt0(perShD)}원)${px?` · 현재가 ${fmt0(px)}원 대비 ${pc(perShD/px-1)}(희석)`:""}`)}
  </div>`;
  const r3=Q["2026Q3"];
  const method=`<div class="note" style="margin-top:6px;line-height:1.75">
    <b>매출총이익</b> 라이넥 물량 × ${A.Lm}% + 판가 인상분 100% + 기타 제품 × ${A.Om}% + (상품 + 자회사) × ${A.Gm}% + 4Q ${f1(A.q4)}(연말 상여) — 기타·상품 이익률은 평범한 네 분기(1Q25·2Q25·3Q25·1Q26)로 맞춤(오차 ±0.1). 라이넥 75% 는 원가 구조로 고정(원료 태반 = 폐기물)
    <br><b>식보다 덜 남은 분기</b> 4Q25 ${f1(Q["2025Q4"].gpRes)}(연말) · 2Q26 ${f1(Q["2026Q2"].gpRes)}(라이넥 최대 분기인데 이익률 40.6% — 가동률 44% · 재고 +10.8 시기라 일회성으로 봄). 여섯 분기 자유 회귀는 라이넥 49% · 기타 86% 를 주지만 그건 2Q26 한 점이 끌어낸 값
    <br><b>왜 회사 이익률이 떨어졌나</b> 상품 매출이 1Q26 +92% · 2Q26 +62% — 상품은 22% 남기고 지급수수료 8.8% 를 내서 매출 1억당 영업이익 약 0.12억(라이넥은 약 0.7억)
    <br><b>라이넥</b> 1Q26 +1% · 2Q26 +45% · 3Q26P 역산 ${f1(r3.L)}(물량 ${pc(r3.Lv/Q["2025Q3"].L-1)} YoY) — 9월 인상 전 선매입 → 4Q26 물량 4Q25 × (1${A.L4g>=0?"+":""}${A.L4g}%) · 2027 물량 = 2025 × (1+${A.Lg}%)²(2022~25 연 13% · 2025 +8% 의 가운데 · 2026 은 선매입·GLP-1 칵테일 처방이 섞여 건너뜀) + 판가 +${A.price}% 온기 + IV ${f1(Y["2027"].iv)}(2Q 후반 출시 · 회당 단가 +60%)
    <br><b>판관비</b> 고정비 = 3Q26 수준 × 4Q 배수(인건비 ${A.hrQ4} · 광고 ${A.adQ4} · 연구개발 ${A.rndQ4}) · 임차 ${A.rent}(내려오는 중) · 2027 = 2026 같은 분기 × (인건비 +${A.hr27}% · 광고 +${A.ad27}% · 판촉·그 밖 +${A.ot27}%) · 변동비 = 지급수수료 상품 × ${A.feeR}%(2Q ${A.feeR2}%) + 보령 공동판매(2차 병원 라이넥 분기 0.5 + IV) × ${A.bor}% + 운반비 매출 × ${A.frR}%
    <br><b>3Q26P</b> 매출·영업이익·순이익 = 잠정실적(11/2) · 판관비 ${f1(r3.sga)}(≈ 위 식) · 매출총이익 = 영업이익 + 판관비(≈ ${fmt(r3.gp/r3.rev*100,1)}%) · 라이넥 물량 = 그 매출총이익에 맞춘 역산 — 3분기보고서(11월 중순)가 들어오면 실제 값으로
    <br><b>영업 밖</b> 이자 분기 −1.15 · 지분법(이니바이오) 2026 −1.1 · 2027 −0.9 · CB 파생 평가손익 0 · 세율 22% · CB 잔여 ${fmt(cb.left,0)}십억(전환가 ${fmt0(cb.px)}원 · ${fmt(cb.left/cb.px*1000,2)}백만주)</div>`;
  const fv=v=>v==null?"":String(v), U=gcwbAsmGet();
  const inp=(k,t,st,unit,w)=>`<label>${t} <input data-gcwba="${k}" type="number" step="${st}" value="${fv(U[k])}" placeholder="${fv(GCWB_DEF[k])}" style="width:${w||56}px"> ${unit||"%"}</label>`;
  const asm=`<details class="fold" data-fold="gcwb_asm"${(()=>{ try{ return localStorage.getItem("fold_gcwb_asm")==="1"?" open":""; }catch(e){ return ""; } })()}><summary>가정 바꾸기 <span class="sub">라이넥 물량·판가·이익률·판관비 배수·Target P/E — 이 브라우저에 기억</span></summary><div style="padding:8px 0">
    <div style="display:flex;flex-wrap:wrap;gap:8px 16px;font-size:12px">
      ${inp("L4g","4Q26 라이넥 물량 YoY",1)}${inp("Lg","라이넥 물량 연 추세(2025 기준)",1)}${inp("price","공급가 인상률",1)}${inp("iv2","IV 2Q27",0.1,"십억")}${inp("iv3","IV 3Q27",0.1,"십억")}${inp("iv4","IV 4Q27",0.1,"십억")}
      ${inp("oth3","3Q26 기타 제품 YoY",1)}${inp("oth4","4Q26 기타 제품 YoY",1)}${inp("gd4","4Q26 상품(3Q26 대비)",1)}${inp("gd27","2027 상품 성장",1)}${inp("oth27","2027 기타 제품",1)}
      ${inp("Lm","라이넥 이익률",1)}${inp("Om","기타 제품 이익률",0.5)}${inp("Gm","상품·자회사 이익률",0.5)}${inp("q4","4Q 연말 원가 조정",0.1,"십억")}
      ${inp("hrQ4","4Q 인건비 배수",0.01,"배")}${inp("adQ4","4Q 광고 배수",0.01,"배")}${inp("feeR","지급수수료(상품 대비)",0.1)}${inp("hr27","2027 인건비",1)}${inp("ad27","2027 광고",1)}${inp("bor","보령 수수료율",1)}${inp("pe","Target P/E",0.5,"배")}
      <button data-gcwbreset style="font-size:11.5px">기본값으로</button></div></div></details>`;
  host.innerHTML=`<div class="sub-h" style="margin:2px 0 8px">분기 손익 — 라이넥·상품·판관비 <span class="th-sub" style="display:inline;margin-left:6px">십억원 · P 잠정실적 · E 우리 추정 · ≈ 역산·추정 · ▸ 세부 · 칸에 마우스 = 식</span></div>
    ${head}
    <div class="tbl-wrap"><table class="mini-tbl ism-t"><thead><tr><th class="l">${attr(name)}</th>${th}</tr></thead><tbody>${body}</tbody></table></div>
    ${method}${asm}${cat}${plant}
    <p class="note">실적 DART 연결 손익·판관비 주석·매출실적(별도)·주요 제품(라이넥)·생산 및 설비(2Q26 반기보고서까지 · 크롬 수집 ${attr(G.asOf)}) · 3Q26 ${attr((G.p["2026Q3"]||{}).src||"")} · 검색 추이는 트렌드 탭 '녹십자웰빙'</p>`;
  host.querySelectorAll("[data-gcwbtg]").forEach(el=>el.addEventListener("click",()=>{ const g=el.dataset.gcwbtg; gcwbOpen={...open}; gcwbOpen[g]=!open[g];
    try{ localStorage.setItem("gcwbOpen",JSON.stringify(gcwbOpen)); }catch(e){} renderGcwbModel(host); }));
  host.querySelectorAll("[data-gcwba]").forEach(i=>i.addEventListener("change",()=>{ const a={};
    host.querySelectorAll("[data-gcwba]").forEach(x=>{ if(x.value!=="") a[x.dataset.gcwba]=+x.value; });
    gcwbAsmSave(a); renderGcwbModel(host); }));
  const rb=host.querySelector("[data-gcwbreset]"); if(rb) rb.addEventListener("click",()=>{ try{ localStorage.removeItem("gcwbAsm"); }catch(e){} renderGcwbModel(host); });
}
