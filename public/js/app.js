/* 화면 코드. 데이터 상수는 index.html 에 남아 있고 여기서 전역으로 읽는다.
   (보통 스크립트끼리라 그냥 보인다 — 실측 확인함)
   ⚠ 이 파일은 봇이 안 건드린다. 화면 수정은 여기서 할 것. */

/* ==== DATA (유니버스 엑셀에서 추출) ==== */

/* ⚠ 에이피알 base 는 시장가가 아니라 '체이닝 기준가'다.
   7/31 종가에 제닉(22,900 편입 -> 24,500 매도, +6.99%)을 에이피알(320,000)로 교체했다.
   화면은 cur/base 로 누적수익률을 그리므로, 제닉 구간을 살리려면
   base = 에이피알 매수가 x 제닉 편입가 / 제닉 매도가 = 320,000 x 22,900 / 24,500 이어야 한다.
   이 값을 그냥 320,000 으로 바꾸면 제닉이 벌어 둔 +6.99% 가 통째로 사라진다. */














/* ==== helpers ==== */
const R = DATA.records;

/* 섹터·카테고리 색은 다크/라이트 양쪽 배경에서 다 읽히도록 '중간 톤'으로 잡는다.
   (예전 로제파인 파스텔은 라이트 크림 배경에서 흐릿했다. 밴드 텍스트가 로드 시 1회
   렌더라 테마 토글로 안 바뀌므로, 테마 무관하게 대비가 나오는 톤이어야 한다.) */

/* 카테고리 = 소분류가 여럿인 대섹터(소비재)는 소분류로 쪼개고, 나머지는 대섹터 그대로.
   뉴스·리포트 필터, 스캐터 색 구분에 공용으로 쓴다. */

R.forEach(r=>{ (_subsBySec[r.sector]=_subsBySec[r.sector]||new Set()).add(r.sub); });

R.forEach(r=>{ CAT_OF[r.name]= _subsBySec[r.sector].size>1 ? r.sub : r.sector; });

SECTORS.forEach(sec=>{ const subs=[..._subsBySec[sec]];
  if(subs.length>1) subs.forEach(s=>CATS.push(s)); else CATS.push(sec); });
/* 대섹터에 소섹터가 하나뿐이면 카테고리 = 대섹터명("엔터"), 여럿이면 소섹터명("기획"·"IP").
   지금 엔터는 기획 하나라 "엔터"가 쓰이지만, 소섹터를 늘리면 즉시 갈리므로 양쪽 다 넣어둔다. */
const CAT_COLORS={"화장품":"#9370c6","유통":"#3f93a8","미용":"#c56f83","음식료":"#bd872c",
  "엔터/미디어":"#c85b86","엔터":"#c85b86","기획":"#c85b86","IP":"#b0507e","게임":"#3e8fb0","호텔":"#5f9e4a",
  "레져":"#5f9e4a"};   // 레져 = 네이버 업종명(호텔,레스토랑,레저) — 섹터 지수 차트용
const catColor=c=>CAT_COLORS[c]||SECTOR_COLORS[c]||"#908caa";
const fmt = (v,d=1)=> (v===null||v===undefined||v==="")?"—":Number(v).toLocaleString("ko-KR",{minimumFractionDigits:d,maximumFractionDigits:d});
const fmt0 = v=> (v===null||v===undefined||v==="")?"—":Math.round(v).toLocaleString("ko-KR");
const won = v=> (v===null||v===undefined||v===""||v===0)?"—":Math.round(v).toLocaleString("ko-KR");
const cls = v=> (v>0?"up":v<0?"down":"flat");
/* 모든 금액 단위를 억으로 통일 · m=배율(십억→억은 10, 조→억은 10000) */
const eok = (v,m=10)=> (v===null||v===undefined||v===""||Number.isNaN(+v))?"—":Math.round(v*m).toLocaleString("ko-KR");

/* EPS 성장률: 전년이 적자면 흑전/적전/적지로 (숫자 대신 라벨) */
function epsGrowth(prev,cur){
  if(prev==null||cur==null) return {n:null,t:null};
  if(prev>0&&cur>0) return {n:(cur/prev-1)*100,t:null};
  if(prev<0&&cur>0) return {n:null,t:"흑전"};
  if(prev>0&&cur<0) return {n:null,t:"적전"};
  if(prev<0&&cur<0) return {n:null,t:"적지"};
  return {n:null,t:null};
}

/* merge live market data (네이버 금융 수집) into records */
R.forEach(r=>{
  const L=LIVE.stocks[r.name]; if(!L) return;
  r.code=L.code; r.mkt=L.market;
  r.price=L.price ?? r.price;                       // 실시간 종가
  r.chgPct=L.chgPct;                                // 전일 대비 %
  r.mktcapJo=L.mktcapEok!=null?L.mktcapEok/10000:(r.mktcap/1000);
  r.perLive=L.per; r.pbr=L.pbr; r.divYield=L.divYield;
  r.cnsPer=L.cnsPer; r.cnsEps=L.cnsEps;
  r.w52h=L.w52h; r.w52l=L.w52l; r.foreign=L.foreign;
  r.recommMean=L.recommMean;
  // 수익률: 실시간 계산값이 있으면 엑셀 고정값을 덮어씀
  if(L.ret1w!=null) r.ret1w=L.ret1w;
  if(L.ret1m!=null) r.ret1m=L.ret1m;
  if(L.ret3m!=null) r.ret3m=L.ret3m;
  r.ret6m=L.ret6m; r.ret1y=L.ret1y;
  r.retYtd=L.retYtd;

  /* 엑셀에서 넘어온 27E 중 0 은 '값이 0'이 아니라 '빈칸'이다.
     0 을 그대로 두면 PER 27E 가 무한대, 순이익 27E 가 0, 성장률이 -100% 로 찍힌다.
     (제닉이 실제로 그랬다.) 계산 전에 결측으로 되돌린다. */
  ["rev27","op27","eps27"].forEach(k=>{ if(r[k]===0) r[k]=null; });

  /* ===== 26E = 컨센서스(API) ===== */
  const cy=(L.cons||{}).year, pv=cy?cy.prev:null;
  r.pbr=L.pbr;                                      // TTM PBR (실시간)
  if(cy&&cy.est){
    const e=cy.est;
    if(e.rev!=null) r.rev26=e.rev;                  // 십억 원 (fetch에서 억→십억 변환됨)
    if(e.op!=null)  r.op26 =e.op;
    if(e.eps!=null) r.eps26=e.eps;                  // 원
    r.np26 = e.np!=null? e.np : null;               // 컨센 순이익
    r.per26=(e.eps>0&&r.price)? r.price/e.eps : null;   // 컨센 EPS 기준 PER
    r.pbr26=(e.bps>0&&r.price)? r.price/e.bps : null;   // 컨센 BPS 기준 26E PBR
    const go=epsGrowth(pv?pv.op:null, e.op);        // 영업익 25(실적)→26(컨센) = 어닝 그로스
    r.opg26=go.n; r.opg26t=go.t;
    const g=epsGrowth(pv?pv.eps:null, e.eps);       // 25(실적)→26(컨센)
    r.epsg26=g.n; r.epsg26t=g.t;
    r.revYoY26=(pv&&pv.rev>0&&e.rev!=null)? (e.rev/pv.rev-1)*100 : null;   // 25실적→26컨센
  } else { r.np26=null; }
  /* ===== 27E = 엑셀 컨센 =====
     무료 API 는 26E 1개년까지만 준다(네이버·FnGuide 공통). 27E 컨센은 엑셀이 유일한 출처다.
     단 엑셀에서 받는 건 원본 3개(rev27·op27·eps27)뿐이고,
     PER·순익·YoY·성장률 같은 파생값은 엑셀 값을 쓰지 않고 전부 여기서 계산한다.
     (엑셀의 파생값은 작성 시점 주가·컨센에 고정돼 있어 시간이 지나면 틀린다) */
  r.per27=(r.eps27>0&&r.price)? r.price/r.eps27 : null;                 // 27E EPS · 라이브 주가
  r.np27=(r.np26&&r.eps26>0&&r.eps27)? r.np26*(r.eps27/r.eps26) : null; // 26 순익 x EPS 배율
  r.revYoY27=(r.rev26>0&&r.rev27>0)? (r.rev27/r.rev26-1)*100 : null;    // 26컨센 → 27엑셀
  const g27=epsGrowth(r.eps26, r.eps27);           // EPS 26(컨센) → 27(엑셀)
  r.epsg27=g27.n; r.epsg27t=g27.t;
  const go27=epsGrowth(r.op26, r.op27);            // 영업익 26(컨센) → 27(엑셀)
  r.opg27=go27.n; r.opg27t=go27.t;
  // 커버리지 표의 영업익 성장 = 26·27 평균 (둘 다 숫자일 때만, 흑전 등은 라벨 유지)
  r.opgAvg=(r.opg26!=null&&r.opg27!=null)? (r.opg26+r.opg27)/2 : null;
  r.opgAvgT=(r.opgAvg==null)? (r.opg26t||r.opg27t||null) : null;
  r.per12mf=(L.cnsPer>0)? L.cnsPer : null;         // 12MF PER = 컨센(API). 없으면 미표시

  if(L.consTarget){ r.target=L.consTarget; }        // 컨센 목표주가(실시간)
  r.upsideCons=(r.target&&r.price)?(r.target/r.price-1)*100:r.upsideCons;
  r.w52pos=(L.w52h&&L.w52l&&L.price)?((L.price-L.w52l)/(L.w52h-L.w52l)*100):null;
  r.mdd=(L.w52h&&L.price)?((L.price/L.w52h-1)*100):null;        // 52주 고점 대비 낙폭
  r.rebound=(L.w52l&&L.price)?((L.price/L.w52l-1)*100):null;    // 52주 저점 대비 반등
  /* 당사 상승여력 = 견적시총 / 실시간 시총 − 1.
     엑셀의 upsideOwn·mktcap은 작성 시점에 고정된 값이라 쓰지 않는다.
     단위: fairMktcap 십억원, mktcapEok 억원 → /10 으로 맞춤 */
  if(r.fairMktcap>0&&L.mktcapEok>0) r.upsideOwn=(r.fairMktcap/(L.mktcapEok/10)-1)*100;
});
const mcJo = r=> r.mktcapJo!=null?r.mktcapJo:r.mktcap/1000;
const sign = (v,d=1)=> (v===null||v===undefined||v==="")?"—":(v>0?"+":"")+fmt(v,d);
/* EPS 성장률 셀: 숫자면 색+%, 전년 적자면 흑전/적전/적지 배지 */
function growthCell(n,t){
  if(t){ const c=t==="흑전"?"up":"down"; return `<span class="${c}" title="전년 적자 기준">${t}</span>`; }
  if(n==null) return "—";
  return `<span class="${cls(n)}">${sign(n,0)}%</span>`;
}
const opm = r=> (r.rev26>0? r.op26/r.rev26*100 : null);
function ratingBadge(s){
  if(s>=7.5) return '<span class="badge b-strong">적극매수</span>';
  if(s>=6.5) return '<span class="badge b-buy">매수</span>';
  if(s>=6)   return '<span class="badge b-buy">비중확대</span>';
  return '<span class="badge b-hold">중립</span>';
}
/* ===== Pick 라벨 =====
   pick2 = 소섹터별 픽 (Top pick / 2nd pick / Beta pick).
   특정 종목만 손으로 바꾸려면 PICK_OVERRIDE 에 추가 (예: {"한국콜마":"Top"}) */

const shortPick = s=> s==="Top pick"?"Top":s==="2nd pick"?"2nd":s==="Beta pick"?"Beta":"";
const sectorPickOf   = r=> PICK_OVERRIDE[r.name] || shortPick(r.pick2||"");
function pill(p,star){
  const t=p==="Beta"?"β":p;
  if(!p) return "";
  const c=p==="Top"?"p-top":p==="2nd"?"p-2nd":"p-beta";
  return `<span class="pill ${c}" title="${star?'유니버스 대표픽':'섹터 픽'} — ${p}">${star?"★":""}${t}</span>`;
}
// 소섹터별 픽만 표시 (엑셀 A열의 유니버스 대표픽은 화장품에만 있어 혼동 -> 미표시)
function pickPill(r){ return pill(sectorPickOf(r),false); }

/* ==== tabs / routing ==== */

const tabsEl = document.getElementById("tabs");
tabsEl.innerHTML = TABS.map(([k,l],i)=>`<button data-k="${k}" class="${i===0?'active':''}">${l}</button>`).join("");

/* 탭 전환의 실체. 클릭·주소창·뒤로가기가 전부 여기로 모인다.
   scroll=false 는 '첫 로드에 주소의 탭을 여는' 경우 — 그때는 이미 맨 위다. */
function activateTab(k, scroll){
  if(!TABS.some(([t])=>t===k)) return false;         // 주소에 엉뚱한 값이 와도 무시
  document.querySelectorAll("nav.tabs button").forEach(x=>x.classList.toggle("active",x.dataset.k===k));
  document.querySelectorAll("section.view").forEach(v=>v.classList.toggle("active",v.dataset.view===k));
  if(k==="overview"){ drawSectorTrend(); renderHeatmap(); }
  if(k==="valuation") drawScatter();
  if(k==="amazon") renderAmazon();
  if(k==="trends"){ const _t=renderTrendHighlights(); if(!trendGroup && _t && _t[0]){ trendStock=_t[0].stock; trendGroup=_t[0].gname; renderTrendSegs(); } drawTrend(); setTrendFoot(); }
  if(k==="boxoffice") renderMovie();
  if(k==="toptoon") renderToptoon();
  // 넘치는 탭 줄에서 지금 탭이 화면 밖이면 끌어온다(폰에서 11개 중 4개만 보인다)
  const btn = tabsEl.querySelector(`button[data-k="${k}"]`);
  if(btn && btn.scrollIntoView) btn.scrollIntoView({block:"nearest",inline:"nearest"});
  if(scroll!==false){
    // 움직임을 줄여 달라는 설정이면 부드러운 스크롤을 쓰지 않는다
    const calm = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({top:0,behavior:calm?"auto":"smooth"});
  }
  return true;
}

/* 주소에 탭을 남긴다 — 애널리스트의 실제 사용 장면은 "이거 봐" 하고 링크를 던지는 것이다.
   예전엔 어느 탭도 주소가 없어서 새로고침하면 개요로 돌아갔다.
   hash 를 바꾸면 hashchange 가 뜨고 거기서 화면을 바꾼다(경로가 하나로 모인다). */
tabsEl.addEventListener("click",e=>{
  const b=e.target.closest("button"); if(!b) return;
  if(location.hash.slice(1)===b.dataset.k) activateTab(b.dataset.k);   // 같은 탭 재클릭
  else location.hash = b.dataset.k;
});
/* 해시가 비면 첫 탭으로 — '#news 에서 뒤로가기' 는 주소가 빈 상태로 돌아오는데,
   그때 아무것도 안 하면 화면은 뉴스에 멈춘 채 주소만 바뀌어 둘이 어긋난다. */
addEventListener("hashchange",()=>{ activateTab(location.hash.slice(1) || TABS[0][0]); });

/* 가로로 넘치는 줄에 페이드를 붙인다(CSS 는 넘침을 알 수 없다).
   탭 줄과 시세 스트립 둘 다 스크롤바를 숨겨 놔서, 페이드가 없으면 더 있다는 신호가 없다.
   폰트가 늦게 로드되면 폭이 달라지므로 로드 후에도 한 번 더 잰다. */
function syncTabOverflow(){
  [tabsEl, document.querySelector(".mkt-strip")].forEach(el=>{
    if(el) el.classList.toggle("overflowing", el.scrollWidth > el.clientWidth + 2);
  });
}
addEventListener("resize", syncTabOverflow);
addEventListener("load", syncTabOverflow);
if(document.fonts && document.fonts.ready) document.fonts.ready.then(syncTabOverflow);
syncTabOverflow();

/* 주소에 탭이 적혀 있으면 그 탭으로 연다(공유 링크·새로고침·뒤로가기).
   ⚠ **여기서 바로 부르면 안 된다.** 렌더 함수들은 이 파일 아래쪽의 const 를 쓰는데
   (MOVIE_UPCOMING 2021줄·TREND_STOCK·secView·amzMetric …), 스크립트가 아직 그 줄까지
   못 갔으므로 TDZ 에 걸려 ReferenceError 로 죽는다 — 페이지가 통째로 백지가 된다.
   `(MOVIE_UPCOMING||[])` 같은 방어는 TDZ 에는 안 먹는다(선언 전 '접근' 자체가 예외).
   스크립트가 다 돈 뒤(DOMContentLoaded)에 연다.

   2026-08-08 실제로 배포까지 나간 버그다. 해시 없이 열면 이 경로를 안 타서
   점검이 통과했고, 배포본 콘솔에서야 잡혔다. check_render.py 가 이제 탭마다
   **새 페이지로** #해시를 열어 본다(같은 페이지에서 해시만 바꾸면 재평가가 안 일어나
   이 버그가 안 보인다 — 그게 처음 놓친 이유다). */
function openHashTab(){ if(location.hash) activateTab(location.hash.slice(1), false); }
if(document.readyState === "loading") addEventListener("DOMContentLoaded", openHashTab);
else openHashTab();

/* 섹션 헤더 오른쪽에 '업데이트 MM/DD HH:MM' — 데이터가 언제 갱신됐는지 항상 표시 */
function fmtUpd(a){const m=String(a||"").match(/(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);return m?`${+m[2]}/${+m[3]} ${m[4]}:${m[5]}`:"";}

/* 블록별 허용 지연(시간). **원본은 watchdog.py 의 LIMITS 다** — 여기 값이 그것과
   어긋나면 precheck.py 가 실패시킨다(등록처를 둘로 쪼개면 반드시 갈라지기 때문).
   새 데이터 블록을 넣을 때는 watchdog.LIMITS 와 여기를 같이 고칠 것. */
const STALE_H = {LIVE:30, NEWS:30, MOVIE:10, TRADE:960, AMAZON:72};

function ageHours(a){
  const m=String(a||"").match(/(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);
  if(!m) return null;
  // asOf 는 KST 로 적힌다. 보는 사람이 어느 시간대에 있든 같은 판정이 나오게 KST 로 맞춘다.
  const t=Date.UTC(+m[1],+m[2]-1,+m[3],+m[4],+m[5]) - 9*3600e3;
  return (Date.now()-t)/3600e3;
}

/* '데이터 없음'과 '못 받았음'은 다른 말이다.
   app.js 가 곳곳을 typeof 로 방어하고 있어서, 수집이 막히면 예외 없이 화면만 빈다 —
   CGV 403 이 '미편성'으로 둔갑해 29시간 갔던 사고가 이 형태였다.
   그래서 비어 보이는 이유를 화면이 직접 말하게 한다. 정상일 땐 아무것도 안 붙는다. */
function staleNote(key, asOf){
  const lim=STALE_H[key]; if(!lim) return "";
  const age=ageHours(asOf); if(age==null) return "";
  // 주말엔 장이 안 서니 시세는 늦어도 정상이다(watchdog 과 같은 보정).
  const d=new Date(), wknd=(d.getDay()===0||d.getDay()===6);
  const eff=(key==="LIVE"&&wknd)?Math.max(lim,72):lim;
  if(age<=eff) return "";
  return age>=48 ? `${Math.round(age/24)}일째 갱신 없음` : `${Math.round(age)}시간째 갱신 없음`;
}

function setSecUpdates(){
  const L=(typeof LIVE!=="undefined"&&LIVE.asOf)||"";
  // [asOf, 신선도를 판정할 블록] — 블록이 null 이면 시각만 표시하고 판정은 안 한다.
  const M={overview:[L,"LIVE"],coverage:[L,"LIVE"],valuation:[L,"LIVE"],
    reports:[L,"LIVE"],calendar:[L,"LIVE"],preview:[L,"LIVE"],
    news:[(typeof NEWS!=="undefined"&&NEWS.asOf)||L,"NEWS"],
    trends:["",null],   // 트렌드는 소스마다 주기가 달라 맨 위 하나로 안 뭉치고, 계열별로 trendTopicNow 에 표시
    boxoffice:[(typeof MOVIE!=="undefined"&&MOVIE.asOf)||"","MOVIE"],
    toptoon:[(typeof TOPTOON!=="undefined"&&TOPTOON.asOf)||"","TOPTOON"],
    altdata:[(typeof TRADE!=="undefined"&&TRADE.asOf)||"","TRADE"],
    amazon:[(typeof AMAZON!=="undefined"&&AMAZON.asOf)||"","AMAZON"]};
  document.querySelectorAll("section.view").forEach(s=>{
    const [asOf,key]=M[s.dataset.view]||["",null];
    const h=s.querySelector("h2.sec"),t=fmtUpd(asOf);if(!h||!t)return;
    let u=h.querySelector(".sec-upd");if(!u){u=document.createElement("span");u.className="sec-upd";h.appendChild(u);}
    u.textContent="업데이트 "+t;
    const warn=key?staleNote(key,asOf):"";
    let w=h.querySelector(".sec-stale");
    if(warn){
      if(!w){w=document.createElement("span");w.className="sec-stale";h.appendChild(w);}
      // 글리프를 앞에 붙이지 않는다 — 색·테두리가 이미 경고를 말하고 있고,
      // 이모지를 아이콘 자리에 쓰는 것이 이 화면의 지적 사항 중 하나다.
      w.textContent=warn;
      w.title="수집이 멈춰 있습니다. 아래 숫자는 이 시각의 값입니다 — 비어 보이는 칸은 '없는 것'이 아니라 '못 받은 것'일 수 있습니다.";
    } else if(w) w.remove();
  });
}

/* ==== 커버리지 유니버스 히트맵 — 시총 트리맵, 색=당일 등락률, 라벨=등락률·점수 ==== */
/* 색은 단계형(bin)으로 나눠 구분이 뚜렷하게. 근중립은 회색, 이후 강도 4단계. 한국 관행 빨강=강세. */
/* 타일 배경 = (등락색 pct%) + (패널 나머지). 배경과 글씨가 같은 식을 봐야
   글씨색을 배경 밝기로 정할 수 있어서 한 곳에 모아 둔다. */
function heatMix(v){
  if(v==null) return {tok:"--muted", pct:12};
  const av=Math.abs(v);
  if(av<0.4) return {tok:"--muted", pct:22};                 // 보합 회색
  return {tok:v>=0?"--up":"--down", pct: av<1.5?56 : av<3?74 : av<6?90 : 100};
}
function heatBg(v){ const m=heatMix(v); return `color-mix(in srgb, var(${m.tok}) ${m.pct}%, var(--panel))`; }
/* 글씨색은 '등락이 크면 흰색'이 아니라 '배경이 밝으면 검정'이어야 한다.
   전자로 두었더니 다크 테마의 밝은 분홍(#f0637f) 타일 위 흰 글씨가 2.05:1 이었다.
   같은 규칙이 라이트 테마에선 반대로 틀린다(거기선 등락색이 어두워 흰 글씨가 맞다).
   그래서 실제로 섞인 색의 밝기를 계산해 흰색·검정 중 대비가 큰 쪽을 고른다 —
   테마가 바뀌든 토큰을 손보든 알아서 따라온다. */
function heatTx(v){
  const cs=getComputedStyle(document.documentElement);
  const hex=n=>{ const s=cs.getPropertyValue(n).trim().replace("#","");
    const t=s.length===3?s.split("").map(c=>c+c).join(""):s;
    return [0,2,4].map(i=>parseInt(t.substr(i,2),16)); };
  const m=heatMix(v), a=hex(m.tok), p=hex("--panel"), k=m.pct/100;
  const c=[0,1,2].map(i=>a[i]*k+p[i]*(1-k));
  const f=x=>{ x/=255; return x<=0.03928?x/12.92:Math.pow((x+0.055)/1.055,2.4); };
  const L=0.2126*f(c[0])+0.7152*f(c[1])+0.0722*f(c[2]);
  return (1.05/(L+0.05)) >= ((L+0.05)/0.05) ? "#fff" : "#12101a";
}
/* 스쿼리파이 트리맵 — items[{value,...}] 를 (X,Y,W,H) 에 채워 {..,x,y,w,h} 반환 */
function squarify(items, X, Y, W, H){
  items=items.map(d=>({...d})).filter(d=>d.value>0).sort((a,b)=>b.value-a.value);
  const tot=items.reduce((s,d)=>s+d.value,0)||1, sc=(W*H)/tot;
  items.forEach(d=>d.a=d.value*sc);
  const out=[]; let x=X,y=Y,w=W,h=H,i=0;
  const worst=(r,side)=>{ const s=r.reduce((a,k)=>a+k.a,0);
    const mx=Math.max(...r.map(k=>k.a)), mn=Math.min(...r.map(k=>k.a));
    return Math.max(side*side*mx/(s*s), s*s/(side*side*mn)); };
  while(i<items.length){
    const side=Math.min(w,h); let row=[items[i]], j=i+1;
    while(j<items.length && worst(row.concat(items[j]),side)<=worst(row,side)){ row.push(items[j]); j++; }
    const s=row.reduce((a,k)=>a+k.a,0), thick=s/side;
    if(w<=h){ let cx=x; row.forEach(k=>{ const kw=k.a/thick; out.push({...k,x:cx,y:y,w:kw,h:thick}); cx+=kw; }); y+=thick; h-=thick; }
    else    { let cy=y; row.forEach(k=>{ const kh=k.a/thick; out.push({...k,x:x,y:cy,w:thick,h:kh}); cy+=kh; }); x+=thick; w-=thick; }
    i=j;
  }
  return out;
}
const fmtMc=eok=> eok>=10000? (eok/10000).toFixed(1)+"조" : Math.round(eok).toLocaleString()+"억";
function renderHeatmap(){
  const host=document.getElementById("heatmapBox"); if(!host) return;
  const stk=n=>LIVE.stocks[n]||{};
  const order=[]; R.forEach(r=>{ if(!order.includes(r.sub)) order.push(r.sub); });
  const sectors=order.map(sec=>{
    const rows=R.filter(r=>r.sub===sec)
      .map(r=>({name:r.name, value:(stk(r.name).mktcapEok||0), chg:stk(r.name).chgPct, score:r.score}))
      .filter(d=>d.value>0);
    return {sec, rows, value:rows.reduce((s,d)=>s+d.value,0)};
  }).filter(s=>s.value>0 && s.rows.length);
  const W=host.clientWidth||900, H=Math.max(440,Math.min(760,Math.round(W*0.6)));
  host.style.position="relative"; host.style.height=H+"px"; host.style.display="block";
  const GAP=3, HEAD=15;
  let html="";
  squarify(sectors,0,0,W,H).forEach(sr=>{
    html+=`<div class="ht-secbox" style="left:${sr.x}px;top:${sr.y}px;width:${Math.max(0,sr.w-1)}px;height:${Math.max(0,sr.h-1)}px">
       <div class="ht-seclabel">${sr.sec}</div></div>`;
    const ix=sr.x+GAP, iy=sr.y+HEAD, iw=Math.max(1,sr.w-GAP*2), ih=Math.max(1,sr.h-HEAD-GAP);
    squarify(sr.rows,ix,iy,iw,ih).forEach(t=>{
      const big=t.w>52&&t.h>40, mid=t.w>40&&t.h>22;
      const cg=t.chg==null?"—":sign(t.chg,2)+"%";
      html+=`<div class="ht-tile2" data-stock="${attr(t.name)}" title="${t.name} · 등락 ${cg} · 점수 ${t.score!=null?fmt(t.score,1):'—'} · 시총 ${fmtMc(t.value)}"
        style="left:${t.x}px;top:${t.y}px;width:${Math.max(0,t.w-1)}px;height:${Math.max(0,t.h-1)}px;background:${heatBg(t.chg)};color:${heatTx(t.chg)}">
        ${big?`<span class="ht-nm2">${t.name}</span><span class="ht-v2">${cg}</span>${t.score!=null?`<span class="ht-sc">점수 ${fmt(t.score,1)}</span>`:''}`
          :mid?`<span class="ht-v2" style="font-size:10px">${cg}</span>`:''}</div>`;
    });
  });
  host.innerHTML=html;
  const note=document.getElementById("heatNote");
  if(note) note.textContent=`타일 크기 = 시가총액 · 색 = 당일 등락률(빨강 강세·파랑 약세, 보합 회색) · 라벨 = 등락률·점수 · 라이브 ${(LIVE||{}).asOf||''} 기준.`;
}

/* ==== theme ==== */
const themeBtn=document.getElementById("themeBtn");
themeBtn.addEventListener("click",()=>{
  const cur=document.documentElement.getAttribute("data-theme");
  const next=cur==="light"?"":"light";
  document.documentElement.setAttribute("data-theme",next);
  if(document.querySelector('section[data-view="valuation"]').classList.contains("active")) drawScatter();
});

/* ==== Market strip (지수·환율) ==== */
(function(){
  const M=LIVE.market||{}, el=document.getElementById("mktStrip");
  // 지수 산출 원본(네이버 금융) 링크
  const SEC_NO={화장품:266,유통:264,미용:281,음식료:268,엔터:285,게임:263,레져:317};
  const A=(href,cls,title,inner)=>`<a class="${cls}" href="${href}" target="_blank" rel="noopener" title="${title}" style="text-decoration:none;color:inherit">${inner}</a>`;
  const idx=(n,o)=> o?A(`https://finance.naver.com/sise/sise_index.naver?code=${n}`,"mkt mkt-ref",`${n} 지수 (네이버 금융)`,
      `<span class="n">${n}</span><span class="v">${fmt(o.close,2)}</span><span class="c ${cls(o.chgPct)}">${sign(o.chgPct,2)}%</span>`):"";
  const fx=(n,v)=> v?A(`https://finance.naver.com/marketindex/`,"mkt mkt-ref",`${n} 환율 (네이버 금융)`,
      `<span class="n">${n}</span><span class="v">${fmt(v,1)}</span>`):"";
  // 표시는 짧은 이름(sub), 풀 업종명은 툴팁에
  const sec=s=>A(`https://finance.naver.com/sise/sise_group_detail.naver?type=upjong&no=${s.no||SEC_NO[s.sub]||''}`,
      "mkt mkt-sec",`${s.name} 업종 · 상승 ${s.rise} / 하락 ${s.fall} (${s.n}종목) · 네이버 금융`,
      `<span class="n">${s.sub}</span><span class="c ${cls(s.chgPct)}" style="font-weight:800">${sign(s.chgPct,1)}%</span>`);
  const F=M.FX||{};
  el.innerHTML =
    (M.sectors||[]).map(sec).join("")+
    `<span class="strip-divider"></span>`+
    idx("KOSPI",M.KOSPI)+idx("KOSDAQ",M.KOSDAQ)+fx("USD/KRW",F.USDKRW)+
    `<span class="live-badge" title="네이버 금융 실시간 수집 · ${LIVE.asOf}"><span class="live-dot"></span></span>`;
  document.getElementById("metaPill").textContent=`신주현 · 시세 ${LIVE.asOf}`;
  // 칩을 채운 지금이라야 넘치는지 알 수 있다(이 블록은 라우팅 설정보다 뒤에 돈다)
  syncTabOverflow();
})();

/* ==== KPIs ==== */
(function(){
  const n=R.length;
  const avgUp = R.filter(r=>r.upsideOwn!=null).reduce((a,r)=>a+r.upsideOwn,0)/R.filter(r=>r.upsideOwn!=null).length;
  const topN = R.filter(r=>sectorPickOf(r)==="Top").length;
  const avgPer = R.filter(r=>r.per12mf>0).reduce((a,r)=>a+r.per12mf,0)/R.filter(r=>r.per12mf>0).length;
  const k=[
    ["커버리지 종목","<b>"+n+"</b>",
      new Set(R.map(r=>r.sector)).size+"개 대섹터 · "+new Set(R.map(r=>r.sector+">"+r.sub)).size+"개 소섹터"],
    ["평균 상승여력","<b class='up'>+"+fmt(avgUp)+"</b><small>%</small>","당사 견적시총 기준"],
    ["Top Pick","<b>"+topN+"</b>","섹터별 최선호 종목"],
    ["평균 12MF PER","<b>"+fmt(avgPer)+"</b><small>x</small>","적자·이상치 제외"]
  ];
  document.getElementById("kpis").innerHTML = k.map(([a,b,c])=>
    `<div class="kpi"><div class="k">${a}</div><div class="v">${b}</div><div class="d">${c}</div></div>`).join("");
})();

/* ==== Sector Top Pick cards ==== */
(function(){
  /* 카드 = 현재 Top pick(pick2)만. 예전엔 별도 배열(sectorPicks)이라 픽을 바꿔도 안 따라와
     탈락 종목이 남았다 — 이제 pick2 에서 자동 파생한다. thesis(코멘트)는 종목 레코드에 있다.
     순서 = 점수 내림차순, 동점이면 당사 상승여력 내림차순(여력은 시세따라 매번 다시 매긴다). */
  const ranked = R.filter(r=>sectorPickOf(r)==="Top").sort((a,b)=>
    (b.score||0)-(a.score||0)
    || (b.upsideOwn==null?-1e9:b.upsideOwn)-(a.upsideOwn==null?-1e9:a.upsideOwn));
  document.getElementById("pickCards").innerHTML = ranked.map((r,i)=>{
    const thesis=r.thesis;
    return `<div class="card">
      <div class="rk">${i+1}</div>
      <div class="sect">${r.sector} · ${r.sub}</div>
      <div class="nm">${stockLogo(r.name)}<span>${r.name}</span>${ratingBadge(r.score||0)}</div>
      ${thesis?`<div class="th">${thesis}</div>`:''}
      <div class="row">
        <div class="c"><div class="lbl">시총 / 견적</div><div class="val">${eok(mcJo(r),10000)} → ${eok(r.fairMktcap,10)}억</div></div>
        <div class="c"><div class="lbl">당사 상승여력</div><div class="val ${cls(r.upsideOwn)}">${sign(r.upsideOwn)}%</div></div>
      </div>
    </div>`;
  }).join("");
})();

/* ==== 개요: 지수 추이 ====
   refresh_live.py 가 시총가중 지수 '레벨'(기준일=100)로 담아둔 값(LIVE.sectorTrend.idx).
   초과수익률로 굳혀 저장하면 기간을 못 바꾸므로, 레벨로 받아 여기서 구간 시작일에
   다시 기준을 잡고 누적수익률(%)로 환산한다.
     종합   = 코스피 · 코스닥 · 소비재(커버리지 7개 업종 합산)
     업종별 = 7개 업종 + 코스피(점선, 비교 기준) */
let secView="port", secDays=22;

function secColor(k){ return SEC_LINE_COLORS[k] || catColor(CAT_COLORS[k]?k:k); }
function drawSectorTrend(){
  const box=document.getElementById("secTrendChart"); if(!box) return;
  const leg=document.getElementById("secTrendLegend"), note=document.getElementById("secTrendNote");
  const ST=LIVE.sectorTrend;
  if(!ST||!ST.idx||!Object.keys(ST.idx).length){
    box.innerHTML=`<div class="ov-empty">지수 추이 데이터가 아직 없습니다. 다음 시세 갱신 후 표시됩니다.</div>`;
    leg.innerHTML=""; note.textContent=""; return;
  }
  const isPort = secView==="port" && typeof PORTFOLIO!=="undefined" && ST.idx["탑픽"];
  // 시간별 실시간 누적(refresh_live 가 매시간 라이브 호가로 적립). 탑픽 포트에서만·있을 때만.
  const intr = LIVE.intraday;
  const usingIntraday = isPort && intr && Array.isArray(intr.points) && intr.points.length>=1;
  // 기간 버튼은 탑픽(매수후 고정)에선 의미 없어 숨긴다
  const prow=document.getElementById("secPeriodSeg"); if(prow&&prow.closest(".ctl-row")) prow.closest(".ctl-row").style.display=isPort?"none":"";
  let D, keys, ref=null; const S={};
  if(usingIntraday){
    // 과거는 daily 지수(ST.idx, 매수일부터 rebase)로, 오늘만 intraday(intr.points)로 그린다.
    // ⚠ intr.points 는 그날치만 담기고 주말·재시작에 리셋될 수 있어(2026-08-10: 1점만 남아
    //   일별 추이가 통째로 사라졌다), 일별 히스토리를 여기 기대면 안 된다. 일별은 늘 온전한
    //   ST.idx 에서 가져오고, intr.points 는 '오늘 장중'에만 쓴다.
    const bd=intr.buy||PORTFOLIO.date;
    const bi=ST.dates.indexOf(bd); const from=bi>=0?bi:0;
    const allKeys=["탑픽","소비재","코스피","코스닥"].filter(k=>ST.idx[k]);
    const reb={}; allKeys.forEach(k=>{ const b=ST.idx[k][from];
      reb[k]=b?ST.idx[k].map(x=>x==null?null:(x/b-1)*100):ST.idx[k].map(()=>null); });
    const raw=intr.points||[];
    const todayMD = raw.length ? (raw[raw.length-1].t||"").slice(0,5) : "";   // 오늘 날짜(MM-DD)
    const pts=[];
    // 매수일(=0%) ~ 어제: daily 종가, 날짜(MM/DD) 라벨. 오늘 날짜는 intraday 로 대체하므로 제외.
    for(let i=from;i<ST.dates.length;i++){
      const md2=ST.dates[i].slice(4,6)+"-"+ST.dates[i].slice(6,8);
      if(md2===todayMD) continue;
      const o={_lbl:`${+ST.dates[i].slice(4,6)}/${+ST.dates[i].slice(6,8)}`};
      allKeys.forEach(k=>o[k]=reb[k][i]); pts.push(o);
    }
    // 오늘 장중(intr.points 는 이미 '매수일 대비 %'), 시각(HH:MM) 라벨
    raw.forEach(p=>{ const o={_lbl:(p.t||"").slice(-5)};
      allKeys.forEach(k=>o[k]=(p[k]==null?null:p[k])); pts.push(o); });
    keys=allKeys.filter(k=>pts.some(p=>p[k]!=null));
    D=pts.map(p=>p._lbl);
    keys.forEach(k=>{ S[k]=pts.map(p=>p[k]==null?null:p[k]); });
  } else {
    let from;
    if(isPort){ const bi=ST.dates.indexOf(PORTFOLIO.date); from = bi>=0?bi:0; }  // 매수일부터 rebase
    else { from = secDays>0? Math.max(0, ST.dates.length-secDays) : 0; }
    D=ST.dates.slice(from);
    const sectorKeys=((LIVE.market||{}).sectors||[]).map(s=>s.sub).filter(s=>ST.idx[s]);
    keys = isPort ? ["탑픽","소비재","코스피","코스닥"].filter(k=>ST.idx[k])
         : secView==="sum" ? ["코스피","코스닥","소비재"].filter(k=>ST.idx[k])
         : sectorKeys;
    ref  = secView==="detail" && ST.idx["코스피"] ? "코스피" : null;
    /* 구간 시작일을 100 으로 다시 잡아 누적수익률(%) 로 */
    const rebase=k=>{ const v=ST.idx[k].slice(from); const b=v.find(x=>x!=null);
      return b? v.map(x=>x==null?null:(x/b-1)*100) : v.map(()=>null); };
    keys.concat(ref?[ref]:[]).forEach(k=>{ S[k]=rebase(k); });
  }

  const W=box.clientWidth||1000, H=340, pad={l:50,r:14,t:14,b:28};
  const all=[0]; Object.values(S).forEach(a=>a.forEach(v=>{ if(v!=null) all.push(v); }));
  const lo=Math.min(...all), hi=Math.max(...all), gap=(hi-lo)*0.12||1;
  const yMin=lo-gap, yMax=hi+gap;
  const sx=i=>pad.l+i/Math.max(1,D.length-1)*(W-pad.l-pad.r);
  const sy=v=>H-pad.b-(v-yMin)/(yMax-yMin)*(H-pad.t-pad.b);
  const gc=getComputedStyle(document.documentElement).getPropertyValue('--line');
  const mut=getComputedStyle(document.documentElement).getPropertyValue('--muted');
  // intraday 는 위에서 이미 라벨(_lbl: 지난날=MM/DD, 오늘=HH:MM)을 D 에 담았으므로 그대로 쓴다.
  const md=d=> usingIntraday ? d : `${+d.slice(4,6)}/${+d.slice(6,8)}`;
  const line=(a)=>{ let d="",pen=false;
    a.forEach((y,i)=>{ if(y==null){pen=false;return;}
      d+=(pen?"L":"M")+sx(i).toFixed(1)+","+sy(y).toFixed(1)+" "; pen=true; }); return d; };

  let s=`<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" font-family="inherit">`;
  for(let i=0;i<=4;i++){ const v=yMin+(yMax-yMin)*i/4, y=sy(v);
    s+=`<line x1="${pad.l}" y1="${y}" x2="${W-pad.r}" y2="${y}" stroke="${gc}"/>`;
    s+=`<text x="${pad.l-7}" y="${y+4}" text-anchor="end" font-size="11" fill="${mut}">${sign(v,0)}%</text>`; }
  s+=`<line x1="${pad.l}" y1="${sy(0)}" x2="${W-pad.r}" y2="${sy(0)}" stroke="${mut}" stroke-dasharray="4 4"/>`;
  const ticks=Math.min(6,D.length);
  for(let t=0;t<ticks;t++){ const i=Math.round(t*(D.length-1)/(ticks-1||1));
    s+=`<text x="${sx(i)}" y="${H-pad.b+16}" text-anchor="middle" font-size="10.5" fill="${mut}">${md(D[i])}</text>`; }
  if(ref) s+=`<path d="${line(S[ref])}" fill="none" stroke="${mut}" stroke-width="1.6" stroke-dasharray="5 4"/>`;
  keys.forEach(k=>{ s+=`<path d="${line(S[k])}" fill="none" stroke="${secColor(k)}" stroke-width="2.2" stroke-linejoin="round"/>`; });
  s+="</svg>";
  box.innerHTML=s;

  const last=a=>{ for(let i=a.length-1;i>=0;i--) if(a[i]!=null) return a[i]; return null; };
  leg.innerHTML=keys.map(k=>`<div class="li"><span class="dot" style="background:${secColor(k)}"></span>${k}
      <b class="${cls(last(S[k]))}" style="margin-left:4px">${sign(last(S[k]),1)}%</b></div>`).join("")
    +(ref?`<div class="li" style="opacity:.75"><span class="dot" style="background:${mut}"></span>코스피(기준)
      <b class="${cls(last(S[ref]))}" style="margin-left:4px">${sign(last(S[ref]),1)}%</b></div>`:"");

  const b=D[0], mt=ST.meta||{};
  const bd=(PORTFOLIO&&PORTFOLIO.date)||"";
  note.textContent = isPort
    ? `${bd.slice(2,4)}/${bd.slice(4,6)}/${bd.slice(6,8)} 매수 가정 · 매수일=0% 누적수익률(%)`
    : `${b.slice(0,4)}-${b.slice(4,6)}-${b.slice(6,8)} 대비 누적수익률(%) · `
    +(secView==="sum"
      ? `소비재 = 커버리지 7개 업종(${(mt["소비재"]||{}).n||0}종목) 시총가중 합산`
      : `네이버 업종 시총 상위 ${ST.topN||20}종목 시총가중 · `
        +keys.map(k=>{const t=mt[k]||{};
           return `${k}${t.name&&t.name!==k?`(${t.name})`:""}${t.cov!=null?` ${t.cov}%`:""}`;}).join(" · "));
  if(isPort) renderPortfolio(S); else { const pb=document.getElementById("portBox"); if(pb) pb.style.display="none"; }
}

/* 탑픽 포트폴리오: 원그래프(현재 비중=매수 후 가격변동 반영) + 보유표 + 매수일 대비 수익률 타일 */
function renderPortfolio(S){
  const box=document.getElementById("portBox"); if(!box||typeof PORTFOLIO==="undefined") return;
  box.style.display="";
  const rows=(PORTFOLIO.picks||[]).map((p,i)=>{
    const st=LIVE.stocks[p.name]||{};
    const cur=st.price, ret=(cur&&p.base)?(cur/p.base-1):0;
    return {name:p.name, w0:p.w, ret, chg:(st.chgPct==null?null:st.chgPct),
            sub:(typeof CAT_OF!=="undefined"?CAT_OF[p.name]:"")||"",
            val:p.w*((cur&&p.base)?cur/p.base:1), color:PORT_PAL[i%PORT_PAL.length]};
  });
  const tot=rows.reduce((s,r)=>s+r.val,0)||1;
  rows.forEach(r=>r.cw=r.val/tot);
  const portRet=(tot-1)*100;               // 누적(매수일 대비)
  // 당일 = 현재 평가금액 ÷ 전일 종가 평가금액 − 1 (전일종가 = 현재가/(1+오늘등락)). 레터와 동일식.
  let _totY=0; rows.forEach(r=>{ _totY += (r.chg!=null)? r.val/(1+r.chg/100) : r.val; });
  const portDay = _totY? (tot/_totY-1)*100 : null;
  const sorted=rows.slice().sort((a,b)=>b.cw-a.cw);
  // 도넛
  const Rr=78, r0=46, cx=90, cy=90; let ang=-Math.PI/2, arcs="";
  sorted.forEach(r=>{ const a1=ang+r.cw*2*Math.PI;
    const x0=cx+Rr*Math.cos(ang),y0=cy+Rr*Math.sin(ang),x1=cx+Rr*Math.cos(a1),y1=cy+Rr*Math.sin(a1);
    const ix0=cx+r0*Math.cos(a1),iy0=cy+r0*Math.sin(a1),ix1=cx+r0*Math.cos(ang),iy1=cy+r0*Math.sin(ang);
    const lg=(a1-ang)>Math.PI?1:0;
    arcs+=`<path d="M${x0.toFixed(1)},${y0.toFixed(1)} A${Rr},${Rr} 0 ${lg} 1 ${x1.toFixed(1)},${y1.toFixed(1)} L${ix0.toFixed(1)},${iy0.toFixed(1)} A${r0},${r0} 0 ${lg} 0 ${ix1.toFixed(1)},${iy1.toFixed(1)} Z" fill="${r.color}"><title>${r.name} ${(r.cw*100).toFixed(1)}%</title></path>`;
    ang=a1; });
  const dcol=v=> v==null?'var(--muted)':(v>=0?'var(--up)':'var(--down)');
  document.getElementById("portPie").innerHTML=
    `<svg viewBox="0 0 180 180" width="176" height="176">${arcs}
      <text x="90" y="78" text-anchor="middle" font-size="11.5" fill="var(--muted)">누적수익률</text>
      <text x="90" y="99" text-anchor="middle" font-size="19" font-weight="800" fill="${dcol(portRet)}">${sign(portRet,1)}%</text>
      <text x="90" y="118" text-anchor="middle" font-size="11" fill="var(--muted)">오늘 <tspan font-weight="800" fill="${dcol(portDay)}">${portDay==null?'—':sign(portDay,1)+'%'}</tspan></text></svg>`;
  // 보유표 — 기초 100억 가정 → 섹터별 현재 금액 + 섹터 누적수익률
  const baseEok=100, totEok=tot*baseEok;
  document.getElementById("portHoldings").innerHTML=
    `<div style="font-size:11.5px;color:var(--muted);margin-bottom:6px">기초 <b style="color:var(--text)">${baseEok}억</b> 가정 → 현재 <b class="${cls(portRet)}">${totEok.toFixed(1)}억</b> · 오늘 <b class="${cls(portDay)}">${portDay==null?'—':sign(portDay,1)+'%'}</b></div>
     <table style="width:100%;border-collapse:collapse;font-size:13px">
     <thead><tr style="color:var(--muted);font-size:11px"><th style="text-align:left;padding:3px 6px">섹터 · 종목</th><th style="text-align:right;padding:3px 6px">현재 금액</th><th style="text-align:right;padding:3px 6px">당일</th><th style="text-align:right;padding:3px 6px">누적</th></tr></thead><tbody>`
    +sorted.map(r=>`<tr style="border-top:1px solid var(--line)">
      <td style="text-align:left;padding:4px 6px"><span style="display:inline-block;width:9px;height:9px;border-radius:2px;background:${r.color};margin-right:6px;vertical-align:middle"></span><span style="font-weight:700">${r.sub}</span><span style="color:var(--muted)"> · </span><span class="nm-cell clickable" data-stock="${r.name}" style="font-size:11.5px">${r.name}</span></td>
      <td style="text-align:right;padding:4px 6px;font-weight:700">${(r.val*baseEok).toFixed(1)}억</td>
      <td style="text-align:right;padding:4px 6px" class="${cls(r.chg)}">${r.chg==null?'—':sign(r.chg,1)+'%'}</td>
      <td style="text-align:right;padding:4px 6px" class="${cls(r.ret*100)}">${sign(r.ret*100,1)}%</td></tr>`).join("")
    +`<tr style="border-top:2px solid var(--line);font-weight:800"><td style="text-align:left;padding:5px 6px">합계</td><td style="text-align:right;padding:5px 6px">${totEok.toFixed(1)}억</td><td style="text-align:right;padding:5px 6px" class="${cls(portDay)}">${portDay==null?'—':sign(portDay,1)+'%'}</td><td style="text-align:right;padding:5px 6px" class="${cls(portRet)}">${sign(portRet,1)}%</td></tr>`
    +`</tbody></table>`;
  // 타일 (매수일 대비)
  const last=a=>{ if(!a) return null; for(let i=a.length-1;i>=0;i--) if(a[i]!=null) return a[i]; return null; };
  const tiles=[["⭐ 탑픽",portRet],["소비재",last(S["소비재"])],["코스피",last(S["코스피"])],["코스닥",last(S["코스닥"])]];
  document.getElementById("portTiles").innerHTML=tiles.filter(t=>t[1]!=null).map(([k,v])=>
    `<div style="background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:7px 15px;min-width:92px">
      <div style="font-size:11px;color:var(--muted)">${k}</div>
      <div style="font-size:17px;font-weight:800" class="${cls(v)}">${sign(v,1)}%</div></div>`).join("");
}
document.getElementById("secViewSeg").addEventListener("click",e=>{
  const b=e.target.closest("button"); if(!b) return;
  secView=b.dataset.view;
  document.querySelectorAll("#secViewSeg button").forEach(x=>x.classList.toggle("active",x===b));
  drawSectorTrend();
});
/* 탑픽 변동 이력 — 버튼 누르면 패널 토글 */
(function(){
  const btn=document.getElementById("pickHistBtn"), panel=document.getElementById("pickHistPanel");
  if(!btn||!panel||typeof PICK_HISTORY==="undefined") return;
  panel.innerHTML=`<div style="font-size:12.5px;font-weight:800;margin-bottom:8px">📜 탑픽 변동 이력</div>`
    +PICK_HISTORY.map(e=>`<div style="border-left:2px solid var(--accent);padding:1px 0 9px 11px;margin-bottom:4px">
        <div style="font-size:12.5px"><b>${e.d}</b> · ${e.title}</div>
        <div style="font-size:12px;color:var(--muted);margin-top:2px">${e.detail}</div>
        ${e.prev?`<div style="font-size:11px;color:var(--muted);margin-top:2px">↳ ${e.prev}</div>`:""}</div>`).join("");
  btn.addEventListener("click",()=>{ panel.style.display = panel.style.display==="none"?"":"none"; });
})();
document.getElementById("secPeriodSeg").addEventListener("click",e=>{
  const b=e.target.closest("button"); if(!b) return;
  secDays=+b.dataset.days;
  document.querySelectorAll("#secPeriodSeg button").forEach(x=>x.classList.toggle("active",x===b));
  drawSectorTrend();
});
drawSectorTrend();   // renderHeatmap 은 attr 정의 이후(하단)에서 최초 호출
window.addEventListener("resize",()=>{
  if(document.querySelector('section[data-view="overview"]').classList.contains("active")){ drawSectorTrend(); renderHeatmap(); }
});

/* ==== sortable table factory ==== */
function makeTable(el, cols, rows, initSort){
  let sortKey=initSort.key, sortDir=initSort.dir;
  /* tie: 값이 같을 때 갈라 줄 두 번째 기준.
     점수는 0.5 단위라 동점이 흔한데, 동점을 원래 배열 순서로 두면
     '점수순'인지 '입력순'인지 알 수 없는 줄 세우기가 된다. */
  const tie=initSort.tie;
  function render(){
    const val=(r,k)=>{
      const v=r[k];
      return (v===null||v===undefined||v==="") ? -Infinity : v;
    };
    const sorted=[...rows].sort((a,b)=>{
      let x=val(a,sortKey), y=val(b,sortKey);
      if(typeof x==="string") return sortDir*x.localeCompare(y,"ko");
      if(x!==y) return sortDir*(x-y);
      if(tie && sortKey!==tie.key){
        const p=val(a,tie.key), q=val(b,tie.key);
        if(p!==q) return tie.dir*(p-q);
      }
      return 0;
    });
    // c.hm = 모바일에서 숨길 컬럼(핵심만 남겨 폰에서 읽기 쉽게)
    // 정렬 화살표는 라벨 **첫 줄** 에 붙인다. th-sub 은 display:block 이라, 라벨 뒤에
    // 그냥 이어 붙이면 화살표가 보조설명 아래로 밀려 3줄이 된다 — 표의 행 높이는
    // 가장 큰 칸을 따르므로 'OP성장/26·27평균' 한 칸 때문에 헤더 13칸이 전부 76px 이 됐다.
    const headCell = (c) => {
      const ar = `<span class="ar">${c.key===sortKey?(sortDir>0?'▲':'▼'):'↕'}</span>`;
      const i = String(c.label).indexOf('<span class="th-sub"');
      return i < 0 ? c.label + ar
                   : c.label.slice(0, i) + ar + c.label.slice(i);
    };
    el.innerHTML =
      "<thead><tr>"+cols.map(c=>
        // 정렬 헤더는 키보드로도 눌러야 한다 — 마우스 없이는 표를 정렬할 방법이 없었다.
        // tabindex 로 Tab 순서에 넣고, role/aria-sort 로 스크린리더가 '정렬 가능·현재 방향' 을 읽게 한다.
        `<th class="${c.l?'l':''} ${c.hm?'hide-m':''} ${c.key===sortKey?'sorted':''}" data-k="${c.key}"`
        + ` tabindex="0" role="button"`
        + ` aria-sort="${c.key===sortKey?(sortDir>0?'ascending':'descending'):'none'}"`
        + ` title="${c.key===sortKey?'정렬 방향 바꾸기':'이 열로 정렬'}">${headCell(c)}</th>`
      ).join("")+"</tr></thead><tbody>"+
      sorted.map(r=>"<tr>"+cols.map(c=>`<td class="${c.l?'l':''} ${c.hm?'hide-m':''}">${c.render(r)}</td>`).join("")+"</tr>").join("")+
      "</tbody>";
    const doSort=(th,e)=>{
      if(e && e.target && e.target.closest("[data-w52toggle]")) return;  // 지표 전환 아이콘은 정렬 제외
      const k=th.dataset.k;
      if(k===sortKey) sortDir*=-1; else {sortKey=k; sortDir=(typeof rows[0][k]==="string")?1:-1;}
      render();
      // 다시 그리면 포커스가 날아간다 — 방금 누른 열로 되돌려 놔야 연속으로 정렬할 수 있다
      const back=el.querySelector(`th[data-k="${k}"]`); if(back) back.focus();
    };
    el.querySelectorAll("th").forEach(th=>{
      th.onclick=(e)=>doSort(th,e);
      th.onkeydown=(e)=>{ if(e.key==="Enter"||e.key===" "){ e.preventDefault(); doSort(th,e); } };
    });
  }
  render();
}
/* 운영사 로고 — 비상장이라 토스 CDN 에 없는 회사들. 회사 이름으로 찾는다.
   stockLogo 가 종목코드를 못 찾을 때만 본다(상장사는 종목 로고가 우선).
   여기 없는 회사는 지금까지대로 이니셜 배지로 떨어진다. */

/* 종목 로고(토스 CDN, 종목코드 기준). 실패하면 이니셜 배지로. name 만 있으면 코드는 LIVE 에서 찾는다. */
function stockLogo(name){
  const code=((typeof LIVE!=="undefined"&&LIVE.stocks&&LIVE.stocks[name])||{}).code;
  // 상장사가 아니면 직접 넣어 둔 회사 로고를 먼저 본다(구다이글로벌 등)
  if(!code && typeof NAME_LOGO!=="undefined" && NAME_LOGO[name])
    return `<span class="nm-logo plate"><img src="${NAME_LOGO[name]}" alt=""></span>`;
  const init=(name||"?").trim().slice(0,1);
  const hue=[...(name||"?")].reduce((a,c)=>a+c.charCodeAt(0),0)%360;
  /* 밝기 50% 에 흰 글씨였는데 색상에 따라 대비가 2.2~4.5 로 널뛰었다(노랑 계열이 최악).
     72% 파스텔 + 어두운 글씨로 뒤집으면 360개 색상 전부 4.5 를 넘긴다(최악 6.67).
     강조색 위 글씨에 흰색을 쓰지 않는 이 프로젝트 규칙과도 맞는다. */
  const bg=`hsl(${hue},42%,72%)`;
  // 코드(로고)가 있으면 래퍼 배경은 투명 — 밝은 hsl 이 둥근 모서리 안티앨리어싱 틈으로 비쳐 어두운 아이콘 테두리가 밝은 링으로 깨져 보이던 문제 차단. 이미지 없음/로드실패 때만 hsl 타일(이니셜용)을 깐다(remove 전에 배경부터 세팅해야 parentNode 가 살아 있다).
  return `<span class="nm-logo" style="background:${code?'transparent':bg}">`
    +(code?`<img src="https://static.toss.im/png-icons/securities/icn-sec-fill-${code}.png" loading="lazy" alt="" onerror="this.parentNode.style.background='${bg}';this.remove()">`:'')
    +`<span class="ini">${init}</span></span>`;
}
const nmCell = r=>`<span class="nm-cell clickable" data-stock="${r.name}">${stockLogo(r.name)}${pickPill(r)} <span class="nm">${r.name}</span><span class="sub">${r.sub}</span></span>`;
/* 분류 컬럼이 따로 있는 표(커버리지)에서는 픽 배지를 빼서 중복을 없앤다 */
const nmCellPlain = r=>`<span class="nm-cell clickable" data-stock="${r.name}">${stockLogo(r.name)}<span class="nm">${r.name}</span><span class="sub">${r.sub}</span></span>`;

/* ==== Coverage summary — grouped by sector ==== */
const avg = arr=> arr.length? arr.reduce((a,b)=>a+b,0)/arr.length : null;
/* 리포트/뉴스 셀 — 리포트는 최근 1개월 조회수 1위, 뉴스는 최근 3일 최신 기사.
   (네이버 금융 뉴스는 조회수를 제공하지 않아 뉴스는 조회수 대신 최신순) */
/* ==== 오늘 ====
   화면의 모든 "지났나/다가오나" 판정은 여기 하나를 본다.

   ⚠ LIVE.asOf 를 오늘로 쓰면 안 된다.
     시세는 장이 열려야 갱신되므로 주말·공휴일엔 며칠 전에 멈춰 있다.
     2026-08-08(토) 실측: asOf 가 08-07 이라 8/7 실적발표가 아직 '다가오는 일정'으로 떴다.

   ⚠ toISOString() 도 쓰면 안 된다 — UTC 라 한국 아침 9시 이전엔 어제가 나온다.
     아침 레터 보고 들어오는 시간대가 정확히 거기다.
   그래서 브라우저 로컬 날짜를 직접 조립한다. */
const TODAY=(()=>{const d=new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;})();
const TODAY_C=TODAY.replace(/-/g,"");            // 20260808 형식
const _asOf=(LIVE.asOf||"").slice(0,10)||new Date().toISOString().slice(0,10);
const _ago=d=>{const t=new Date(_asOf); t.setDate(t.getDate()-d); return t.toISOString().slice(0,10);};
const attr=s=>String(s||"").replace(/&/g,"&amp;").replace(/"/g,"&quot;").replace(/</g,"&lt;");
renderHeatmap();   // 개요 히트맵 최초 렌더(attr 정의 이후라야 안전)

/* 리포트·뉴스 셀 링크 — 오늘 안에 기준에 맞는 게 없으면 창을 단계적으로 넓힌다.
   오늘 → 3일 → 1주일 → 1개월. 그래도 없으면 링크하지 않는다(—).
   창을 넓히는 순서라 항상 "가능한 가장 최근 구간" 안에서 고르게 된다. */
const LINK_WINDOWS=[{d:0,label:"오늘"},{d:2,label:"3일"},{d:6,label:"1주일"},{d:29,label:"1개월"}];
/* items 를 창 안으로 좁혀가며 best() 로 1건 고른다.
   dateOf: 비교용 날짜 문자열, ymd8: true 면 YYYYMMDD 형식(리포트)  */
function pickRecent(items, dateOf, best, ymd8){
  for(const w of LINK_WINDOWS){
    const cut = ymd8 ? _ago(w.d).replace(/-/g,"") : _ago(w.d);
    const hit = items.filter(x=>(dateOf(x)||"")>=cut);
    if(hit.length) return {item:best(hit), window:w.label};
  }
  return {item:null, window:null};
}

/* 커버리지 요약 뉴스 링크용 — 제목에 종목명(또는 대표 브랜드)이 들어간 기사만 연결.
   범용 시황기사(그 종목 피드에 뜨지만 제목엔 종목명이 없는)를 걸러낸다. */
const NEWS_ALIAS={
  "에이피알":["에이피알","APR","메디큐브"], "아모레퍼시픽":["아모레퍼시픽","아모레"],
  "LG생활건강":["LG생활건강","LG생건","엘지생활건강","엘지생건"],
  "달바글로벌":["달바글로벌","달바","dalba"], "한국콜마":["한국콜마","콜마"],
  "실리콘투":["실리콘투"], "코스맥스":["코스맥스"], "제닉":["제닉"],
  "제이투케이바이오":["제이투케이바이오","제이투케이","J2K","J2KBIO"],
  "신세계":["신세계"], "롯데쇼핑":["롯데쇼핑","롯데백화점","롯데마트"], "현대백화점":["현대백화점"],
  "파마리서치":["파마리서치","리쥬란","콘쥬란"],
  "앨엔씨바이오":["앨엔씨바이오","엘앤씨바이오","엘앤씨","앨엔씨","메가덤"], "그래피":["그래피"],
  "리센스메디컬":["리센스메디컬","리센스","쿨로아","Recens"],
  "삼양식품":["삼양식품","불닭"], "CJ제일제당":["CJ제일제당","씨제이제일제당","비비고","햇반","고메"],
  "농심":["농심","신라면","새우깡"],
  "하이브":["하이브","HYBE","BTS","방탄"], "JYP Ent.":["JYP","제이와이피"],
  "에스엠":["에스엠","SM엔터"], "와이지엔터":["와이지엔터","와이지","YG엔터"],
  "SAMG엔터":["SAMG엔터","SAMG","삼지","캐치티니핑","티니핑","미니특공대"],
  "크래프톤":["크래프톤","배틀그라운드","배그","PUBG","펍지"],
  "NC":["엔씨소프트","엔씨","리니지"], "펄어비스":["펄어비스","검은사막","붉은사막"],
  "시프트업":["시프트업","니케","스텔라블레이드"],
  "롯데관광개발":["롯데관광개발","롯데관광"], "파라다이스":["파라다이스"],
  "GS피앤엘":["GS피앤엘","지에스피앤엘"], "서부T&D":["서부T&D","서부티앤디","서부티엔디"],
  "티앤엘":["티앤엘","T&L"],
};
const _newsTitleHit=(title,name)=>{
  const al=NEWS_ALIAS[name]||[name], t=String(title||"").toLowerCase();
  return al.some(a=>t.includes(a.toLowerCase()));
};

/* 커버리지 요약 = 당사 뷰 vs 시장 뷰 + 밸류·성장·모멘텀 핵심.
   PER/PBR 전체, 매출·영업익·순익·EPS 상세는 밸류에이션 탭에 있음. */
const covCols = [
  {key:"pickSort",label:"분류",l:true,render:r=>pickPill(r)||`<span style="color:var(--muted2)">—</span>`},
  {key:"name",label:"종목",l:true,render:nmCellPlain},
  {key:"score",label:"점수",render:r=>r.score==null?"—":`<b>${fmt(r.score,1)}</b>`},
  {key:"mktcapJo",label:"시총(억)",render:r=>`<b>${eok(mcJo(r),10000)}</b>`},
  {key:"fairMktcap",label:"견적(억)",render:r=>eok(r.fairMktcap,10)},
  // 개요 KPI 는 '평균 상승여력' 인데 여기만 '당사 여력' 이라 같은 값이 두 이름으로 불렸다.
  // 이름을 맞추고, 컨센이 아니라 당사 견적 기준이라는 단서는 보조설명으로 남긴다.
  {key:"upsideOwn",label:`상승여력<span class="th-sub">당사 견적</span>`,render:r=>r.upsideOwn==null?"—":`<span class="${cls(r.upsideOwn)}">${sign(r.upsideOwn,1)}%</span>`},
  {key:"per12mf",label:"12MF PER",render:r=>r.per12mf>0?fmt(r.per12mf)+"x":"—"},
  {key:"per26",label:"26E PER",render:r=>r.per26>0?fmt(r.per26)+"x":"—"},
  {key:"per27",label:"27E PER",hm:1,render:r=>r.per27>0?fmt(r.per27)+"x":"—"},
  {key:"opgAvg",label:`OP성장<span class="th-sub">26·27평균</span>`,render:r=>growthCell(r.opgAvg,r.opgAvgT)},
  {key:"foreign",label:"외국인",hm:1,render:r=>r.foreign>0?fmt(r.foreign,1)+"%":"—"},
  {key:"ret1m",label:"1M",render:r=>r.ret1m==null?"—":`<span class="${cls(r.ret1m)}">${sign(r.ret1m,1)}%</span>`},
  {key:"retYtd",label:"YTD",hm:1,render:r=>r.retYtd==null?"—":`<span class="${cls(r.retYtd)}">${sign(r.retYtd,1)}%</span>`},
  {key:"repViews",label:"리포트",hm:1,render:r=>r.repUrl
    ? `<a class="cell-link" href="${r.repUrl}" target="_blank" rel="noopener" title="${attr(r.repTip)}">보기</a>` : "—"},
  {key:"newsD",label:"뉴스",hm:1,render:r=>r.newsUrl
    ? `<a class="cell-link" href="${r.newsUrl}" target="_blank" rel="noopener" title="${attr(r.newsTip)}">보기</a>` : "—"},
];
// 분류 정렬용 가중치 (Top > 2nd > Beta > 없음)
const PICK_ORDER={Top:3,"2nd":2,Beta:1,"":0};
(function renderCoverageBySector(){
  const host=document.getElementById("covGroups");
  host.innerHTML="";
  SECTORS.forEach(sec=>{
    const secRows=R.filter(r=>r.sector===sec);
    const subs=[...new Set(secRows.map(r=>r.sub))];
    subs.forEach(sub=>{
      const rows=secRows.filter(r=>r.sub===sub)
        .map(r=>{
          // 리포트: 창(오늘→3일→1주일→1개월)을 넓혀가며 그 창 안 조회수 1위
          const rpPick=pickRecent(
            (LIVE.researches||[]).filter(x=>x.co===r.name),
            x=>x.date, a=>a.slice().sort((x,y)=>(y.views||0)-(x.views||0))[0], true);
          const tRep=rpPick.item;
          // 뉴스: 같은 창 규칙 + 제목에 종목명/대표브랜드가 든 기사만 그 창 안 최신
          //       (범용 시황기사 배제 — 종목명이 제목에 없으면 연결 안 함)
          const nwPick=pickRecent(
            ((typeof NEWS!=="undefined"&&NEWS.items)?NEWS.items:[])
              .filter(x=>x.co.includes(r.name) && _newsTitleHit(x.t,r.name)),
            x=>x.d, a=>a.slice().sort((x,y)=>y.d.localeCompare(x.d))[0], false);
          const tNews=nwPick.item;
          return {...r, opmv:opm(r), pickSort:PICK_ORDER[sectorPickOf(r)]||0, mcap:mcJo(r),
            repViews:tRep?(tRep.views||0):null,
            repUrl:tRep?`https://m.stock.naver.com/domestic/stock/${tRep.code}/research`:null,
            repTip:tRep?`${rpPick.window} 내 조회수 1위 · 조회 ${fmt0(tRep.views)}\n${tRep.title} (${tRep.broker}, ${tRep.date.slice(4,6)}/${tRep.date.slice(6,8)})`:"",
            newsD:tNews?tNews.d.slice(5,10).replace("-","/"):null,
            newsUrl:tNews?tNews.u:null,
            newsTip:tNews?`${nwPick.window} 내 최신 · 제목에 종목명 포함\n${tNews.t} (${tNews.s})`:""};
        });
      if(!rows.length) return;
      const aUp=avg(rows.map(r=>r.upsideOwn).filter(v=>v!=null));
      const aScore=avg(rows.map(r=>r.score).filter(v=>v!=null));
      const aPer=avg(rows.map(r=>r.per12mf).filter(v=>v>0));
      const c=SECTOR_COLORS[sec];
      const block=document.createElement("div");
      block.className="sector-block";
      block.innerHTML=
        `<div class="sector-band" style="border-left-color:${c}">
          <span class="s-name" style="color:${c}">${sec} · ${sub}</span>
          <span class="s-tag">${rows.length}종목</span>
          <span class="s-stat" style="margin-left:auto">평균 점수 <b>${fmt(aScore,1)}</b></span>
          <span class="s-stat">평균 12MF PER <b>${fmt(aPer)}x</b></span>
          <span class="s-stat">평균 상승여력 <b class="${cls(aUp)}">${sign(aUp)}%</b></span>
        </div>
        <div class="tbl-wrap"><table></table></div>`;
      host.appendChild(block);
      // 시총 큰 순(요청) — 동점/결측이면 점수순. 요약은 시총 정렬이 깔끔하다.
      makeTable(block.querySelector("table"), covCols, rows,
                {key:"mcap", dir:-1, tie:{key:"score", dir:-1}});
    });
  });
})();

/* ==== Valuation table ==== */
/* 52주 컬럼: 낙폭(MDD) ↔ 52주 위치 ↔ 저점대비 반등 토글 */
const W52_MODES=[
  {k:"mdd",     label:"고점대비 낙폭", sort:"mdd",
   render:r=> r.mdd==null?"—":
     `<div class="w52"><div class="bar"><i style="left:0;width:${Math.min(100,Math.abs(r.mdd)).toFixed(0)}%;height:5px;top:0;border-radius:3px;background:var(--down);opacity:.5"></i></div>`+
     `<span class="lbl ${cls(r.mdd)}" style="font-weight:700">${fmt(r.mdd,1)}%</span></div>`},
  {k:"w52pos",  label:"52주 위치", sort:"w52pos",
   render:r=> r.w52pos==null?"—":
     `<div class="w52"><div class="bar"><i style="left:${Math.max(0,Math.min(100,r.w52pos)).toFixed(0)}%"></i></div><span class="lbl">${fmt(r.w52pos,0)}%</span></div>`},
  {k:"rebound", label:"저점대비 반등", sort:"rebound",
   render:r=> r.rebound==null?"—":`<span class="up" style="font-weight:700">${sign(r.rebound,0)}%</span>`},
];
let w52Mode=0;
function renderValTable(){
  const M=W52_MODES[w52Mode];
  const cols=[
    {key:"name",label:"종목",l:true,render:nmCell},
    {key:"mktcapJo",label:"시총(억)",render:r=>`<b>${eok(mcJo(r),10000)}</b>`},
    {key:"per12mf",label:"12MF PER",render:r=>r.per12mf>0?fmt(r.per12mf)+"x":"—"},
    {key:"per26",label:"26E PER",render:r=> r.per26>0?fmt(r.per26)+"x":"—"},
    {key:"per27",label:"27E PER",render:r=> r.per27>0?fmt(r.per27)+"x":"—"},
    {key:"pbr",label:"TTM PBR",render:r=>r.pbr>0?fmt(r.pbr)+"x":"—"},
    {key:"pbr26",label:"26E PBR",render:r=>r.pbr26>0?fmt(r.pbr26)+"x":"—"},
    {key:"rev26",label:"26E 매출",render:r=>eok(r.rev26)},
    {key:"rev27",label:"27E 매출",render:r=>eok(r.rev27)},
    {key:"revYoY26",label:"26E 매출YoY",render:r=>r.revYoY26==null?"—":`<span class="${cls(r.revYoY26)}">${sign(r.revYoY26,0)}%</span>`},
    {key:"revYoY27",label:"27E 매출YoY",render:r=>r.revYoY27==null?"—":`<span class="${cls(r.revYoY27)}">${sign(r.revYoY27,0)}%</span>`},
    {key:"op26",label:"26E 영업익",render:r=>eok(r.op26)},
    {key:"op27",label:"27E 영업익",render:r=>eok(r.op27)},
    {key:"np26",label:"26E 순익",render:r=>eok(r.np26)},
    {key:"np27",label:"27E 순익",render:r=>eok(r.np27)},
    {key:"eps26",label:"26E EPS",render:r=>fmt0(r.eps26)},
    {key:"eps27",label:"27E EPS",render:r=>fmt0(r.eps27)},
    {key:"epsg26",label:"EPS성장 25→26",render:r=>growthCell(r.epsg26,r.epsg26t)},
    {key:"epsg27",label:"EPS성장 26→27",render:r=>growthCell(r.epsg27,r.epsg27t)},
    {key:"target",label:"목표주가",render:r=>won(r.target)},
    {key:"upsideCons",label:"컨센 상승여력",render:r=>`<span class="${cls(r.upsideCons)}">${sign(r.upsideCons)}%</span>`},
    {key:M.sort,label:`${M.label} <span class="w52-swap" data-w52toggle title="클릭하면 지표 전환">⇄</span>`,render:M.render},
  ];
  // 커버리지 요약과 동일하게 대섹터 → 소분류(구획) 밴드로 나눠 표시
  const host=document.getElementById("valGroups"); host.innerHTML="";
  SECTORS.forEach(sec=>{
    const secRows=R.filter(r=>r.sector===sec);
    [...new Set(secRows.map(r=>r.sub))].forEach(sub=>{
      const rows=secRows.filter(r=>r.sub===sub);
      if(!rows.length) return;
      const aPer=avg(rows.map(r=>r.per12mf).filter(v=>v>0));
      const c=SECTOR_COLORS[sec];
      const block=document.createElement("div"); block.className="sector-block";
      block.innerHTML=`<div class="sector-band" style="border-left-color:${c}">
          <span class="s-name" style="color:${c}">${sec} · ${sub}</span>
          <span class="s-tag">${rows.length}종목</span>
          <span class="s-stat" style="margin-left:auto">평균 12MF PER <b>${fmt(aPer)}x</b></span>
        </div><div class="tbl-wrap" style="border-radius:0 0 12px 12px;border-top:none"><table></table></div>`;
      host.appendChild(block);
      makeTable(block.querySelector("table"), cols, rows, {key:"mktcapJo",dir:-1});
    });
  });
}
renderValTable();
// ⇄ 아이콘으로 지표 전환. 캡처 단계에서 가로채므로 정렬로 테이블이 다시 그려져도 계속 동작한다.
document.getElementById("valGroups").addEventListener("click",(e)=>{
  if(!e.target.closest("[data-w52toggle]")) return;
  e.stopPropagation();
  w52Mode=(w52Mode+1)%W52_MODES.length;
  renderValTable();
}, true);

/* ==== Earnings preview ====
   다가오는 분기 컨센 + 연간 26E 컨센 (네이버 재무 API).
   예전엔 '당사(엑셀) vs 컨센 괴리' 컬럼이 있었으나, 엑셀 재무데이터를 걷어내며 제거했다.
   애초에 제닉·그래피는 당사 추정이 컨센과 동일해 괴리가 항상 0이었다. */
R.forEach(r=>{
  const c=(LIVE.stocks[r.name]||{}).cons||{};
  r.cy=c.year||null; r.cq=c.quarter||null;
  r.consOp26=r.cy&&r.cy.est?r.cy.est.op:null;
  r.consRev26=r.cy&&r.cy.est?r.cy.est.rev:null;
  // 다가오는 분기 컨센
  r.qTitle=r.cq?r.cq.title.replace(/\.$/,''):null;
  r.qRev=r.cq&&r.cq.est?r.cq.est.rev:null;
  r.qOp=r.cq&&r.cq.est?r.cq.est.op:null;
  r.qOpm=r.cq&&r.cq.est?r.cq.est.opm:null;
  const pq=r.cq&&r.cq.prev?r.cq.prev:null;
  r.qRevYoY=(pq&&pq.rev&&r.qRev)?((r.qRev/pq.rev-1)*100):null;
  r.qOpYoY=(pq&&pq.op&&r.qOp)?((r.qOp/pq.op-1)*100):null;
});

/* ==== Scatter (SVG) ==== */
function drawScatter(){
  const box=document.getElementById("scatter");
  const W=box.clientWidth||1000, H=420, pad={l:52,r:20,t:16,b:44};
  const pts=R.filter(r=>r.per12mf>0 && r.per12mf<60 && r.upsideOwn!=null);
  const xs=pts.map(p=>p.per12mf), ys=pts.map(p=>p.upsideOwn);
  const xMin=0, xMax=Math.max(...xs)*1.05, yMin=Math.min(0,...ys)-5, yMax=Math.max(...ys)*1.08;
  const sx=v=>pad.l+(v-xMin)/(xMax-xMin)*(W-pad.l-pad.r);
  const sy=v=>H-pad.b-(v-yMin)/(yMax-yMin)*(H-pad.t-pad.b);
  const maxCap=Math.max(...pts.map(p=>mcJo(p)));
  const rad=p=>6+Math.sqrt(mcJo(p)/maxCap)*22;
  const gc=getComputedStyle(document.documentElement).getPropertyValue('--line');
  const mut=getComputedStyle(document.documentElement).getPropertyValue('--muted');
  let s=`<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" font-family="inherit">`;
  // grid + y ticks
  for(let i=0;i<=5;i++){const v=yMin+(yMax-yMin)*i/5;const y=sy(v);
    s+=`<line x1="${pad.l}" y1="${y}" x2="${W-pad.r}" y2="${y}" stroke="${gc}" stroke-width="1"/>`;
    s+=`<text x="${pad.l-8}" y="${y+4}" text-anchor="end" font-size="11" fill="${mut}">${Math.round(v)}%</text>`;}
  for(let i=0;i<=6;i++){const v=xMin+(xMax-xMin)*i/6;const x=sx(v);
    s+=`<text x="${x}" y="${H-pad.b+18}" text-anchor="middle" font-size="11" fill="${mut}">${Math.round(v)}x</text>`;}
  s+=`<text x="${(W)/2}" y="${H-6}" text-anchor="middle" font-size="12" fill="${mut}">12MF PER (배)</text>`;
  s+=`<text x="14" y="${H/2}" text-anchor="middle" font-size="12" fill="${mut}" transform="rotate(-90 14 ${H/2})">당사 상승여력 (%)</text>`;
  // zero line
  s+=`<line x1="${pad.l}" y1="${sy(0)}" x2="${W-pad.r}" y2="${sy(0)}" stroke="${mut}" stroke-dasharray="4 4" stroke-width="1"/>`;
  pts.forEach(p=>{
    const c=catColor(CAT_OF[p.name]);
    s+=`<circle cx="${sx(p.per12mf)}" cy="${sy(p.upsideOwn)}" r="${rad(p)}" fill="${c}33" stroke="${c}" stroke-width="1.5"><title>${p.name} · 12MF PER ${fmt(p.per12mf)}x · 상승여력(당사 견적) ${sign(p.upsideOwn)}% · 시총 ${eok(mcJo(p),10000)}억 → 견적 ${eok(p.fairMktcap,10)}억</title></circle>`;
    s+=`<text x="${sx(p.per12mf)}" y="${sy(p.upsideOwn)-rad(p)-3}" text-anchor="middle" font-size="10.5" fill="var(--text)" font-weight="600">${p.name}</text>`;
  });
  s+="</svg>";
  box.innerHTML=s;
  document.getElementById("scatterLegend").innerHTML =
    CATS.map(k=>`<div class="li"><span class="dot" style="background:${catColor(k)}"></span>${k}</div>`).join("")+
    `<div class="li" style="margin-left:auto">버블 크기 = 시가총액 · PER 60x 초과·적자 종목 제외</div>`;
}
window.addEventListener("resize",()=>{
  if(document.querySelector('section[data-view="valuation"]').classList.contains("active")) drawScatter();
});

/* ==== Calendar — month grid ====
   LIVE.events = 네이버 IR 일정 실시간 수집 (refresh_live.py)
   MANUAL_EVENTS = 직접 추가하는 일정 (규제/기업 이벤트 등) — 여기만 편집하면 됩니다 */
const MANUAL_EVENTS=[
  // DART에 안 잡히는 일정을 여기에 직접 적으면 캘린더·개요 "다가오는 일정"에 자동 반영.
  // ty: earn=실적발표 / ir=IR·컨퍼런스 / reg=규제·승인 / corp=기업행동 / div=배당
  {d:"2026-09-01", co:"NC", t:"아이온2 글로벌 출시 예정 (북미·남미·유럽·일본, 9월 중 · PC/Steam)", ty:"corp"},
  // {d:"2026-08-12", co:"엘앤씨바이오", t:"품목허가 심사", ty:"reg"},
];
const CAL=(function(){
  const all=[
    ...(typeof DART_EVENTS!=="undefined"?DART_EVENTS:[]).map(e=>({d:e.date,co:e.co,t:e.title,ty:e.type,src:"DART 공시",rcp:e.rcp,time:e.time})),
    ...(LIVE.events||[]).map(e=>({d:e.date,co:e.co,t:e.title,ty:e.type,src:"네이버 IR"})),
    ...MANUAL_EVENTS.map(e=>({...e,src:"직접 입력"})),
  ].filter(e=>e.d);
  // 같은 날 같은 종목 중복 제거 (DART 우선)
  const seen=new Set(), out=[];
  all.forEach(e=>{const k=e.co+"|"+e.d; if(seen.has(k))return; seen.add(k); out.push(e);});
  return out.sort((a,b)=>a.d.localeCompare(b.d));
})();

/* ================= 당사 분기 추정 — 여기만 편집하면 된다 =================
   키:  종목명 -> "YYYY.MM"(분기 말월) -> {rev, op}      단위: 십억원
   컨센과 실제는 API 가 채우므로 손대지 않는다.
   예)  "달바글로벌": { "2026.06": {rev: 190.0, op: 43.0} },
        "하이브":     { "2026.06": {rev: 1250,  op: 130 } },
   분기가 발표되면 그 분기는 자동으로 '발표완료' 보기로 넘어가고,
   당사·컨센 중 실제에 더 가까웠던 쪽이 승자로 집계된다.               */

/* 잠정실적 — fetch_prelim.py 가 DART '영업(잠정)실적(공정공시)'에서 자동 수집(단위 십억원).
   정식 실적이 네이버 API 에 잡히면 화면이 자동으로 그쪽(apiAct)을 우선하므로 잠정은 물러난다.
   단위·양식이 회사마다 달라, 컨센 스냅샷 대비 0.4~2.6배 범위만 채택(오파싱 방지). */

/* ==== 실적 프리뷰 — 당사 추정 vs 컨센, 발표 후엔 실제까지 3자 비교 ====
   CAL 이 여기서야 만들어지므로 표 렌더링도 여기서 한다(앞의 R.forEach 는 값 계산만). */
(function renderPreview(){
  const today=TODAY;
  const nextEarn={};
  CAL.filter(e=>e.ty==="earn" && e.d>=today).forEach(e=>{
    if(!nextEarn[e.co] || e.d<nextEarn[e.co]) nextEarn[e.co]=e.d;
  });
  const toKey=k=>k.slice(0,4)+"."+k.slice(4,6);                 // 202606 -> 2026.06
  const qLab =k=>`${Math.ceil(+k.slice(4,6)/3)}Q${k.slice(2,4)}`;
  const gap=(a,b)=> (a!=null&&b)? (a/b-1)*100 : null;           // a 가 b 대비 몇 %
  // 서프라이즈는 부호 안전판: 적자(컨센 음수)일 때 a/b-1 은 방향이 뒤집히므로
  // (실제−컨센)/|컨센| 로 계산해야 '실제>컨센 = 상회(+)' 가 항상 맞다.
  const surp=(a,b)=> (a!=null&&b!=null&&b!==0)? (a-b)/Math.abs(b)*100 : null;
  const pctCell=v=> v==null?"—":`<span class="${cls(v)}">${sign(v,1)}%</span>`;
  const absCell=v=> v==null?"—":`<span class="${Math.abs(v)<=3?'up':''}">${sign(v,1)}%</span>`;

  /* ---- 예정: 다가오는 컨센 분기에 대해 당사 vs 컨센 ---- */
  R.forEach(r=>{
    const q=((LIVE.stocks[r.name]||{}).cons||{}).quarter||{};
    const est=(MY_EST[r.name]||{})[q.key?toKey(q.key):""]||null;
    r.earnD=nextEarn[r.name]||null;
    r.earnSort=r.earnD||"9999-99-99";        // 발표일 미정은 항상 뒤로
    r.earnDday=r.earnD? Math.round((new Date(r.earnD)-new Date(today))/864e5) : null;
    r.myRev=est?est.rev:null; r.myOp=est?est.op:null;
    r.myRevGap=gap(r.myRev,r.qRev); r.myOpGap=gap(r.myOp,r.qOp);
  });
  const verdict=r=> r.myOpGap==null? '<span class="tag-inline">추정 없음</span>'
    : r.myOpGap>5 ? '<span class="tag-beat">당사 상회</span>'
    : r.myOpGap<-5? '<span class="tag-miss">당사 하회</span>'
    : '<span class="tag-inline">In-line</span>';
  // 발표완료 판정(영업익 서프라이즈 ±5%) — 실제 대비 컨센 부합 여부.
  // 발표 전 컨센 스냅샷이 없으면(스냅샷 도입 전 발표) 판정 불가 → '컨센 미수집' 으로 구분.
  const verdictDone=r=> r.surpOp!=null
    ? (r.surpOp>5 ? '<span class="tag-beat">어닝 서프라이즈</span>'
      : r.surpOp<-5? '<span class="tag-miss">어닝 쇼크</span>'
      : '<span class="tag-inline">부합</span>')
    : (r.hasCons ? '<span class="tag-inline">판정 보류</span>'
      : '<span class="tag-inline" title="발표 전 컨센 스냅샷이 없어 서프라이즈 판정 불가. 2026 2분기 발표부터 자동 판정됩니다.">컨센 미수집</span>');
  // 간단 코멘트 — 규칙 기반(무API). 영업익 서프라이즈를 축으로, 매출 방향·당사 승자를 덧붙인다.
  const earnComment=r=>{
    const so=r.surpOp, sr=r.surpRev;
    const head = so==null ? (!r.hasCons?"발표 전 컨센 미수집 · 2Q26~ 자동판정":sr==null?"컨센 없어 판정 보류":`매출 컨센 ${sign(sr,0)}%`)
      : so>5 ? `영업익 컨센 ${sign(so,0)}% 상회`
      : so<-5? `영업익 컨센 ${sign(so,0)}% 하회`
      : "영업익 컨센 부합";
    const sub = (so!=null && sr!=null && Math.abs(sr)>=5) ? ` · 매출 ${sign(sr,0)}%` : "";
    const win = r.win==="당사" ? " · 당사추정이 더 근접" : (r.win==="컨센"? " · 컨센이 더 근접":"");
    return `<span class="th-sub">${head}${sub}${win}</span>`;
  };

  /* ---- 발표완료 ----
     기준은 '발표 전 컨센 스냅샷(LIVE.consSnap)이 있고 그 분기가 실적으로 확정된 것'.
     컨센은 발표되면 API 에서 사라지므로 스냅샷이 유일한 비교 대상이다.
     당사 추정(MY_EST)은 있으면 오차·승자까지 얹고, 없어도 서프라이즈는 나온다. */
  const done=[];
  R.forEach(r=>{
    const series=(((LIVE.stocks[r.name]||{}).cons||{}).quarter||{}).series||[];
    const snap=(LIVE.consSnap||{})[r.name]||{};
    const myAll=MY_EST[r.name]||{};
    const pre=(typeof PRELIM!=="undefined"&&PRELIM[r.name])||{};
    // 발표완료 = 컨센 스냅샷을 잡아 둔 분기(=현재 실적시즌) 중 '실적이 나온' 것.
    // 실적 = API 확정치 우선, 없으면 잠정(PRELIM). 아직 안 나왔으면(둘 다 없음) 제외.
    const quarters=new Set([...Object.keys(snap),
                            ...Object.keys(myAll).map(k=>k.replace(".",""))]);
    quarters.forEach(raw=>{
      const apiAct=series.find(s=>s.k===raw && !s.e);
      const prelim=pre[raw]||null;
      const act = apiAct || prelim;
      if(!act) return;
      const isPrelim=!apiAct && !!prelim;
      const cons=snap[raw]||null;
      const est=myAll[`${raw.slice(0,4)}.${raw.slice(4,6)}`]||null;
      const myErr=est?gap(est.op,act.op):null;
      const csErr=cons?gap(cons.op,act.op):null;
      done.push({...r, dqRaw:raw, dq:qLab(raw), hasCons:!!cons, isPrelim,
        actRev:act.rev, actOp:act.op,
        myRev:est?est.rev:null, myOp:est?est.op:null,
        consRev:cons?cons.rev:null, consOp:cons?cons.op:null,
        myErrRev:est?gap(est.rev,act.rev):null, myErrOp:myErr,
        surpRev:cons?surp(act.rev,cons.rev):null,
        surpOp:cons?surp(act.op,cons.op):null,
        win:(myErr==null||csErr==null)?null:(Math.abs(myErr)<Math.abs(csErr)?"당사":"컨센")});
    });
  });
  done.sort((a,b)=>b.dqRaw.localeCompare(a.dqRaw));

  // 당사 추정(MY_EST)이 하나라도 있을 때만 '당사' 컬럼을 붙인다. 비어 있으면
  // 실제 vs 컨센만 깔끔히 — '—' 와 '추정 없음' 으로 표를 채우지 않는다.
  const hasMyEst = Object.keys(MY_EST).length>0;
  const C={
    nm:{key:"name",label:"종목",l:true,render:nmCell},
    earn:{key:"earnSort",label:"실적발표",l:true,render:r=>r.earnD
      ? `<span class="ye">${r.earnD.slice(5).replace("-","/")}</span>`
        +`<span class="th-sub" style="margin-left:5px">${r.earnDday===0?"D-DAY":"D-"+r.earnDday}</span>`
      : "—"},
    q:{key:"qTitle",label:"분기",l:true,render:r=>r.qTitle?`<span class="ye">${r.qTitle}E</span>`:"—"},
    myRev:{key:"myRev",label:"당사 매출",render:r=>eok(r.myRev)},
    qRev:{key:"qRev",label:"컨센 매출",render:r=>eok(r.qRev)},
    myRevGap:{key:"myRevGap",label:"괴리",render:r=>pctCell(r.myRevGap)},
    myOp:{key:"myOp",label:"당사 영업익",render:r=>eok(r.myOp)},
    qOp:{key:"qOp",label:"컨센 영업익",render:r=>eok(r.qOp)},
    myOpGap:{key:"myOpGap",label:"괴리",render:r=>pctCell(r.myOpGap)},
    verdict:{key:"verdict",label:"판정",render:verdict},
    dq:{key:"dqRaw",label:"분기",l:true,render:r=>`<span class="ye">${r.dq}</span>`+(r.isPrelim?` <span class="tag-inline" title="공시 잠정실적(정식 재무제표 반영 전)">잠정</span>`:``)},
    actRev:{key:"actRev",label:"실제 매출",render:r=>`<b>${eok(r.actRev)}</b>`},
    consRev:{key:"consRev",label:"컨센",render:r=>eok(r.consRev)},
    surpRev:{key:"surpRev",label:"서프라이즈",render:r=>pctCell(r.surpRev)},
    actOp:{key:"actOp",label:"실제 영업익",render:r=>`<b>${eok(r.actOp)}</b>`},
    consOp:{key:"consOp",label:"컨센",render:r=>eok(r.consOp)},
    surpOp:{key:"surpOp",label:"서프라이즈",render:r=>pctCell(r.surpOp)},
    myOpD:{key:"myOp",label:"당사 영업익",render:r=>eok(r.myOp)},
    myErrOp:{key:"myErrOp",label:"내 오차",render:r=>absCell(r.myErrOp)},
    win:{key:"win",label:"승자",render:r=>r.win==null?"—"
      :r.win==="당사"?'<span class="tag-beat">당사 ✓</span>':'<span class="tag-inline">컨센</span>'},
    verdictDone:{key:"surpOp",label:"판정",render:verdictDone},
    cmt:{key:"dqRaw",label:"코멘트",l:true,render:earnComment},
  };
  /* ---- 발표완료 + 예정을 한 표로 묶고, 분기로만 가른다 ----
     예전엔 '예정' 과 '발표완료' 두 보기였다. 그런데 실적시즌 중에는 같은 분기 안에서
     이미 나온 종목과 아직인 종목이 섞여 있고, 그 둘을 나란히 놔야 시즌이 어디까지
     왔는지 읽힌다. 보기를 오가며 맞춰 보게 할 이유가 없다.

     상태 칸이 그 구분을 대신한다: 발표완료(잠정 포함) / D-N / 일정 미정. */
  const uni=[];
  const doneKey=new Set(done.map(x=>x.name+"|"+x.dqRaw));
  done.forEach(x=>uni.push({...x, q:x.dqRaw, announced:true}));
  R.forEach(r=>{
    const qk=(((LIVE.stocks[r.name]||{}).cons||{}).quarter||{}).key||null;
    if(!qk || doneKey.has(r.name+"|"+qk)) return;
    uni.push({...r, q:qk, dqRaw:qk, dq:qLab(qk), announced:false,
      actRev:null, actOp:null, consRev:r.qRev, consOp:r.qOp,
      surpRev:null, surpOp:null, myErrRev:null, myErrOp:null, win:null, isPrelim:false});
  });

  const QS=[...new Set(uni.map(x=>x.q))].sort().reverse();      // 최신 분기가 앞
  const seg=document.getElementById("prevQSeg");

  const C2={
    state:{key:"stateSort",label:"상태",l:true,render:r=> r.announced
      ? `<span class="tag-beat">발표완료</span>`+(r.isPrelim?` <span class="tag-inline" title="공시 잠정실적(정식 재무제표 반영 전)">잠정</span>`:``)
      : (r.earnD
          ? `<span class="ye">${r.earnD.slice(5).replace("-","/")}</span>`
            +`<span class="th-sub" style="margin-left:5px">${r.earnDday===0?"D-DAY":(r.earnDday>0?"D-"+r.earnDday:"발표 대기")}</span>`
          : `<span class="th-sub">일정 미정</span>`)},
  };
  uni.forEach(x=>{ x.stateSort = x.announced ? "0" : (x.earnD||"9999-99-99"); });

  const COLS = hasMyEst
    ? [C.nm,C2.state,C.actRev,C.consRev,C.surpRev,C.actOp,C.consOp,C.surpOp,C.verdictDone,C.myOpD,C.myErrOp,C.win,C.cmt]
    : [C.nm,C2.state,C.actRev,C.consRev,C.surpRev,C.actOp,C.consOp,C.surpOp,C.verdictDone,C.cmt];

  const note=document.getElementById("prevNote");
  function render(q){
    const rows=uni.filter(x=>x.q===q);
    makeTable(document.getElementById("prevTable"), COLS, rows, {key:"stateSort",dir:1});
    const dn=rows.filter(x=>x.announced), preN=dn.filter(x=>x.isPrelim).length;
    note.textContent = `단위 억 원 · ${qLab(q)} — 발표 ${dn.length}/${rows.length}종목`
      + (preN?` (잠정 ${preN}개 — 정식 재무제표 반영 전)`:``)
      + ` · 서프라이즈 = 실제 ÷ 컨센 − 1(발표 전 저장한 컨센 스냅샷 대비)`
      + (dn.length?``:` · 아직 발표된 종목이 없어 컨센 기대치만 보입니다`)
      + (hasMyEst?` · 당사 오차 = 당사 ÷ 실제 − 1(±3% 초록)`:``);
  }
  seg.innerHTML=QS.map((q,i)=>`<button data-q="${q}"${i===0?' class="active"':''}>${qLab(q)}</button>`).join("");
  seg.addEventListener("click",e=>{
    const b=e.target.closest("button"); if(!b) return;
    seg.querySelectorAll("button").forEach(x=>x.classList.toggle("active",x===b));
    render(b.dataset.q);
  });
  if(QS.length) render(QS[0]);
})();

const CTYPE={earn:"ev-earn",ir:"ev-ir",reg:"ev-reg",corp:"ev-corp",div:"ev-div"};
const CTYPE_LABEL={earn:"실적발표",ir:"IR·컨퍼런스",reg:"규제·승인",corp:"기업행동",div:"배당"};

/* ==== 임박 이벤트 보드 — 실적/잠정실적을 따로, 그 외 다가오는 일정을 따로 ==== */
(function renderUpcoming(){
  const host=document.getElementById("upcoming"); if(!host) return;
  const today=new Date(TODAY);
  today.setHours(0,0,0,0);
  const dday=d=>Math.round((new Date(d)-today)/86400000);
  const isPrelim=t=>/잠정|공정공시/.test(t||"");           // 잠정실적 판별
  const ddCls=n=>n<=3?"soon":n<=7?"near":"far";
  const ddText=n=>n===0?"D-DAY":n>0?"D-"+n:"D+"+(-n);

  const upc=CAL.filter(e=>dday(e.d)>=0).sort((a,b)=>a.d.localeCompare(b.d));
  const row=e=>{
    const n=dday(e.d), md=e.d.slice(5).split("-");
    const u=e.rcp?`https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${e.rcp}`:null;
    const tm=e.time?`<span style="color:var(--muted);font-size:11px;margin-left:6px">🕑 ${e.time}</span>`:"";
    const inner=`
      <div class="dd"><div class="dm">${Number(md[0])}월</div><div class="din">${Number(md[1])}</div></div>
      <div class="info"><div class="co">${e.co}${tm}${isPrelim(e.t)?'<span class="up-tag">잠정</span>':''}</div>
        <div class="tt">${e.t}</div></div>
      <div class="dcount ${ddCls(n)}">${ddText(n)}</div>`;
    return u
      ? `<a class="up-row" href="${u}" target="_blank" rel="noopener"
           style="display:flex;align-items:center;text-decoration:none;color:inherit"
           title="${e.t} · DART 원문 열기 ↗">${inner}</a>`
      : `<div class="up-row" data-stock="${e.co}" title="${e.t} (${e.src})">${inner}</div>`;
  };

  // ① 실적발표(잠정 포함) — 임박순(날짜 오름차순). 잠정은 배지로 표시
  const earn=upc.filter(e=>e.ty==="earn").slice(0,8);
  // ② 그 외 다가오는 일정 (IR·배당·기업행동·규제)
  const others=upc.filter(e=>e.ty!=="earn").slice(0,8);

  const box=(cls,ic,title,rows)=>
    `<div class="up-box ${cls}"><div class="up-head"><span class="ic"></span>${title}
       <span class="cnt">${rows.length}건</span></div>`+
    (rows.length? rows.map(row).join("") : `<div class="up-empty">예정된 일정이 없습니다.</div>`)+`</div>`;

  host.innerHTML =
    box("key","","🔔 임박 실적발표 · 잠정실적", earn)+
    box("", "", "다가오는 일정 (IR · 배당 · 기타)", others);
})();

(function renderCalendar(){
  const host=document.getElementById("calendar");
  const dow=["일","월","화","수","목","금","토"];
  const byMonth={};
  CAL.forEach(e=>{const k=e.d.slice(0,7);(byMonth[k]=byMonth[k]||[]).push(e);});
  let html="";
  Object.keys(byMonth).sort().forEach(k=>{
    const [y,m]=k.split("-").map(Number);
    const first=new Date(y,m-1,1).getDay();
    const days=new Date(y,m,0).getDate();
    html+=`<div class="cal-month"><div class="cal-title">${y}년 ${m}월</div><div class="cal-scroll"><div class="cal-grid">`;
    html+=dow.map((d,i)=>`<div class="cal-dow ${i===0?'sun':i===6?'sat':''}">${d}</div>`).join("");
    for(let i=0;i<first;i++) html+=`<div class="cal-cell empty"></div>`;
    for(let day=1;day<=days;day++){
      const wd=(first+day-1)%7;
      const evs=byMonth[k].filter(e=>Number(e.d.slice(8,10))===day);
      html+=`<div class="cal-cell ${wd===0?'sun':wd===6?'sat':''} ${evs.length?'has':''}"><div class="dnum">${day}</div>`+
        evs.map(e=>{
          const u=e.rcp?`https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${e.rcp}`:null;
          const tt=`[${CTYPE_LABEL[e.ty]||'기타'}] ${e.co}${e.time?" "+e.time:""} · ${e.t} (${e.src})`;
          return u
            ? `<a class="cal-ev ${CTYPE[e.ty]||'ev-earn'}" href="${u}" target="_blank" rel="noopener" style="cursor:pointer;text-decoration:none;color:inherit" title="${tt} ↗">${e.co}</a>`
            : `<div class="cal-ev ${CTYPE[e.ty]||'ev-earn'}" data-stock="${e.co}" style="cursor:pointer" title="${tt}">${e.co}</div>`;
        }).join("")+
      `</div>`;
    }
    html+=`</div></div></div>`;
  });
  host.innerHTML=html;
})();

/* ==== 개요 "한눈에 보기" 패널 — 상승여력 / 낙폭 / 다가오는 일정 ====
   CAL 이 위에서 정의된 뒤에 실행되어야 하므로 캘린더 다음에 둔다. */
(function(){
  const host=document.getElementById("ovPanels"); if(!host) return;
  const top=(key,dir,n=6)=>R.filter(r=>r[key]!=null&&isFinite(r[key]))
    .sort((a,b)=>(a[key]-b[key])*dir).slice(0,n);
  const rows=(list,val)=> list.length
    ? list.map((r,i)=>`<div class="ov-row" data-stock="${r.name}" title="${r.name} 상세">
         <span class="rk">${i+1}</span><span class="nm">${r.name}</span>${val(r)}</div>`).join("")
    : `<div class="ov-empty">데이터 없음</div>`;
  const panel=(title,note,body)=>`<div class="ov-panel"><div class="h">${title}<small>${note}</small></div>${body}</div>`;

  // 1) 당사 상승여력 상위 (견적시총 ÷ 현재시총)
  const p1=panel("상승여력 상위","당사 견적시총",
    rows(top("upsideOwn",-1), r=>`<span class="v ${cls(r.upsideOwn)}">${sign(r.upsideOwn,0)}%</span>`));
  // 2) 52주 고점대비 낙폭 상위(가장 많이 빠진 순)
  const p2=panel("52주 낙폭 상위","저가 매수 후보",
    rows(top("mdd",1), r=>`<span class="v down">${fmt(r.mdd,0)}%</span>`));
  // 3) 다가오는 일정 (실적발표 우선)
  const today=TODAY;
  const up=CAL.filter(e=>e.d>=today).sort((a,b)=>a.d.localeCompare(b.d)).slice(0,6);
  const p3=panel("다가오는 일정","DART · IR",
    up.length? up.map(e=>{
      const dd=Math.round((new Date(e.d)-new Date(today))/86400000);
      const u=e.rcp?`https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${e.rcp}`:null;
      const inner=`<span class="dt">${e.d.slice(5).replace("-","/")}${e.time?" "+e.time:""}</span>
        <span class="nm">${e.co}</span>
        <span class="v" style="color:var(--muted)">${dd===0?"D-DAY":"D-"+dd}</span>`;
      return u
        ? `<a class="ov-row" href="${u}" target="_blank" rel="noopener" style="text-decoration:none;color:inherit" title="${e.t} · DART ↗">${inner}</a>`
        : `<div class="ov-row" data-stock="${e.co}" title="${e.t}">${inner}</div>`;
    }).join("") : `<div class="ov-empty">예정된 일정이 없습니다</div>`);

  host.innerHTML=p1+p2+p3;
})();

/* ==== Reports — 네이버 금융 실수집 ==== */
const REP=(LIVE.researches||[]);
/* 리포트 — 뉴스와 동일: 종목별 2열 그리드, 종목당 최신 3건, 카테고리(소비재 세분) 세그먼트 */
(function(){
  const host=document.getElementById("repGroups"); if(!host) return;
  const PER=3;
  const repItem=x=>{
    const m=x.date?x.date.slice(4,6):"", d=x.date?x.date.slice(6,8):"";
    return `<div class="item">
      <div class="date-chip"><div class="m">${m}월</div><div class="d">${d}</div></div>
      <div class="body">
        <div class="t">${x.title}</div>
        <div class="s"><span class="nm-cell clickable" data-stock="${x.co}">${stockLogo(x.co)}${x.co}</span> · ${x.broker}${x.views?` · 조회 ${fmt0(x.views)}`:""}</div>
      </div>
      <a class="ev-type ev-earn" href="https://m.stock.naver.com/domestic/stock/${x.code}/research" target="_blank" rel="noopener">보기</a>
    </div>`;
  };
  let curCat="", curCo="";
  function render(){
    host.innerHTML=""; host.classList.remove("news-grid");
    if(curCo){
      const list=REP.filter(x=>x.co===curCo);
      host.innerHTML=list.length?`<div class="list">${list.map(repItem).join("")}</div>`
        :`<div class="list"><div class="item"><div class="body"><div class="s">해당 종목의 리포트가 없습니다.</div></div></div></div>`;
      return;
    }
    host.classList.add("news-grid");
    let any=false;
    R.filter(r=> !curCat || CAT_OF[r.name]===curCat).forEach(r=>{
      const rows=REP.filter(x=>x.co===r.name).slice(0,PER);
      if(!rows.length) return;
      any=true;
      const c=catColor(CAT_OF[r.name]);
      const block=document.createElement("div"); block.className="sector-block";
      block.innerHTML=
        `<div class="sector-band" style="border-left-color:${c}">
           <span class="s-name clickable" data-stock="${r.name}" style="color:${c};cursor:pointer">${stockLogo(r.name)}${r.name}</span>
           <span class="s-tag">${r.sector} · ${r.sub}</span>
           <span class="s-tag" style="margin-left:auto">${rows.length}건</span>
         </div>
         <div class="list" style="border-radius:0 0 12px 12px;border-top:none">${rows.map(repItem).join("")}</div>`;
      host.appendChild(block);
    });
    if(!any) host.innerHTML=`<div class="list"><div class="item"><div class="body"><div class="s">해당하는 리포트가 없습니다.</div></div></div></div>`;
  }
  // 카테고리 세그먼트
  const seg=document.getElementById("repSeg");
  const catCount=Object.fromEntries(CATS.map(s=>[s, REP.filter(x=>CAT_OF[x.co]===s).length]));
  seg.innerHTML=`<button data-cat="" class="active">전체 ${REP.length}</button>`
    +CATS.map(s=>`<button data-cat="${s}">${s} ${catCount[s]||0}</button>`).join("");
  seg.addEventListener("click",e=>{
    const b=e.target.closest("button"); if(!b) return;
    curCat=b.dataset.cat; curCo="";
    seg.querySelectorAll("button").forEach(x=>x.classList.toggle("active",x===b));
    fillStocks(); sel.value=""; render();
  });
  // 종목 드롭다운
  const sel=document.getElementById("repFilter");
  function fillStocks(){
    const pool = curCat? R.filter(r=>CAT_OF[r.name]===curCat).map(r=>r.name) : R.map(r=>r.name);
    const cos=[...new Set(REP.map(x=>x.co).filter(c=>pool.includes(c)))].sort((a,b)=>a.localeCompare(b,"ko"));
    sel.innerHTML=`<option value="">${curCat||"전체"} · 종목 전체</option>`+cos.map(c=>`<option value="${c}">${c}</option>`).join("");
  }
  sel.addEventListener("change",e=>{ curCo=e.target.value; render(); });
  fillStocks(); render();
})();

/* ==== 뉴스 — 대분류 섹터로 나누고 소분류별로 묶어 표시 ==== */
(function(){
  const host=document.getElementById("newsGroups"); if(!host) return;
  const ALL=(typeof NEWS!=="undefined" && NEWS.items)?NEWS.items:[];
  /* 표시는 종목당 최신 3건까지.
     수집(fetch_news.py PER_STOCK)은 넉넉히 하지만 그건 커버리지 표의 뉴스 링크
     — 제목에 종목명이 든 기사를 찾아내는 용도 — 이고, 뉴스 탭은 3건만 보여준다.
     세그먼트 건수도 이 걸러진 집합 기준이라 화면과 숫자가 어긋나지 않는다. */
  const NEWS_PER=3;
  const byDateDesc=(a,b)=>String(b.d).localeCompare(String(a.d));
  const keep=new Set();
  R.forEach(r=>ALL.filter(x=>x.co.includes(r.name)).sort(byDateDesc)
                  .slice(0,NEWS_PER).forEach(x=>keep.add(x)));
  const NW=ALL.filter(x=>keep.has(x));   // 원본 정렬(최신순) 유지

  // 종목명 → 섹터/소분류 (한 기사가 여러 종목·섹터에 걸릴 수 있음)
  const SEC_OF={}, SUB_OF={};
  R.forEach(r=>{ SEC_OF[r.name]=r.sector; SUB_OF[r.name]=r.sub; });
  const secsOf=x=>[...new Set(x.co.map(c=>SEC_OF[c]).filter(Boolean))];
  const catsOf=x=>[...new Set(x.co.map(c=>CAT_OF[c]).filter(Boolean))];  // 공용 CAT_OF 사용

  const label=d=>{ const m=/(\d{4})-(\d{2})-(\d{2})/.exec(d||""); return m?`${m[2]}/${m[3]}`:""; };
  const itemHtml=x=>
    `<div class="item">
      <div class="date-chip" style="display:flex;align-items:center;justify-content:center"><div class="d" style="font-size:13px">${label(x.d)}</div></div>
      <div class="body">
        <div class="t"><a href="${x.u}" target="_blank" rel="noopener" style="color:inherit">${x.t}</a></div>
        <div class="s">${x.s}</div>
      </div>
      <a class="ev-type ev-earn" href="${x.u}" target="_blank" rel="noopener">보기</a>
    </div>`;

  let curCat="", curCo="";           // 카테고리 세그먼트 · 종목 드롭다운
  function render(){
    // 필터 적용
    let list=NW;
    if(curCo)       list=list.filter(x=>x.co.includes(curCo));
    else if(curCat) list=list.filter(x=>catsOf(x).includes(curCat));

    host.innerHTML=""; host.classList.remove("news-grid");
    if(!list.length){ host.innerHTML=`<div class="list"><div class="item"><div class="body"><div class="s">해당하는 뉴스가 없습니다.</div></div></div></div>`; return; }

    // 종목이 지정되면 그냥 목록, 아니면 종목별로 2열 그리드
    if(curCo){
      host.innerHTML=`<div class="list">${list.slice().sort(byDateDesc).slice(0,NEWS_PER).map(itemHtml).join("")}</div>`;
      return;
    }
    host.classList.add("news-grid");   // 종목 블록을 한 줄에 둘씩
    // 커버리지 순서대로 종목마다 한 블록 (선택 카테고리로 좁힘). 한 기사가 여러 종목이면 각 종목 밑에 표시.
    R.filter(r=> !curCat || CAT_OF[r.name]===curCat).forEach(r=>{
      // 한 기사가 여러 종목에 걸리면 다른 종목 몫으로 남은 게 섞일 수 있어 여기서도 3건으로 자른다
      const rows=list.filter(x=> x.co.includes(r.name)).sort(byDateDesc).slice(0,NEWS_PER);
      if(!rows.length) return;
      const c=SECTOR_COLORS[r.sector];
      const block=document.createElement("div");
      block.className="sector-block";
      block.innerHTML=
        `<div class="sector-band" style="border-left-color:${c}">
           <span class="s-name clickable" data-stock="${r.name}" style="color:${c};cursor:pointer">${stockLogo(r.name)}${r.name}</span>
           <span class="s-tag">${r.sector} · ${r.sub}</span>
           <span class="s-tag" style="margin-left:auto">${rows.length}건</span>
         </div>
         <div class="list" style="border-radius:0 0 12px 12px;border-top:none">${rows.map(itemHtml).join("")}</div>`;
      host.appendChild(block);
    });
  }

  // 카테고리 세그먼트: 전체 + 소분류(소비재)·대섹터(그 외). 카테고리별 건수 표기
  const seg=document.getElementById("newsSeg");
  const catCount=Object.fromEntries(CATS.map(s=>[s, NW.filter(x=>catsOf(x).includes(s)).length]));
  seg.innerHTML=`<button data-cat="" class="active">전체 ${NW.length}</button>`
    +CATS.map(s=>`<button data-cat="${s}">${s} ${catCount[s]||0}</button>`).join("");
  seg.addEventListener("click",e=>{
    const b=e.target.closest("button"); if(!b) return;
    curCat=b.dataset.cat; curCo="";
    seg.querySelectorAll("button").forEach(x=>x.classList.toggle("active",x===b));
    // 종목 드롭다운을 선택 카테고리에 맞춰 다시 채운다
    fillStocks(); document.getElementById("newsFilter").value="";
    render();
  });

  // 종목 드롭다운(보조 필터) — 선택된 카테고리 범위 안에서
  const sel=document.getElementById("newsFilter");
  function fillStocks(){
    const pool = curCat? R.filter(r=>CAT_OF[r.name]===curCat).map(r=>r.name) : R.map(r=>r.name);
    const cos=[...new Set(NW.flatMap(x=>x.co).filter(c=>pool.includes(c)))].sort((a,b)=>a.localeCompare(b,"ko"));
    sel.innerHTML=`<option value="">${curCat||"전체"} · 종목 전체</option>`
      +cos.map(c=>`<option value="${c}">${c}</option>`).join("");
  }
  sel.addEventListener("change",e=>{ curCo=e.target.value; render(); });

  fillStocks();
  render();
})();

/* ==== Trend comparison — skinboosters (SEED) ==== */




let trendSrc="naver";
/* 트렌드 ↔ 종목 매핑 — 주제를 전부 펼치지 않고 종목 버튼으로 고른다.
   한 종목이 주제를 여럿 가지면(SAMG엔터) 아래에 주제 버튼 줄이 하나 더 생긴다.
   키워드 자체는 fetch_trends.py 의 GROUPS 에 있고, 여기는 '어느 종목 이야기냐'만 잇는다. */
const TREND_STOCK={
  "에이피알":["K-뷰티 브랜드"],        // 메디큐브
  "달바글로벌":["K-뷰티 브랜드"],      // 달바
  "파마리서치":["스킨부스터"],         // 리쥬란
  "리센스메디컬":["쿨로아600"],        // 쿨로아
  "SAMG엔터":["티니핑 국가별","변신로봇 IP","변신로봇 IP 러시아"],
  "NC":["아이온2 국가별","아스트라에 오라티오"],   // 아스오라 = 2026 하반기 서브컬처 신작
  "크래프톤":["배틀그라운드(크래프톤)"],
  "펄어비스":["펄어비스 IP"],
  "시프트업":["시프트업 IP"],
  "탑코미디어":["웹툰 플랫폼","탑툰챗","AI 챗봇 경쟁","제타(경쟁)","네오나(경쟁)"],   // 본업 경쟁 · 신사업 추이 · 상대위치 · 경쟁사 단독
};
/* Steam 동접을 트렌드 비교 탭에 편입 — 게임사는 검색보다 동접·리뷰가 실측 신호라
   같은 탭에서 검색트렌드와 나란히 고르게 한다. 별도 탭을 두면 헷갈리고 과하다.
   차트가 0–100 상대값이라 동접(명)도 자기 최고=100 으로 정규화하고, peak 로 실제 명수를
   밝힌다(얀덱스 절대검색수와 같은 방식). 리뷰 긍정%는 범례 각주로 붙인다. */
(function injectSteamTrends(){
  if(typeof STEAM==="undefined"||!STEAM.games) return;
  STEAM.games.forEach(g=>{
    const raw=g.players||[]; const vals=raw.filter(x=>x!=null);
    if(vals.length<2) return;
    const peak=Math.max(...vals)||1;
    const norm=raw.map(v=>v==null?0:Math.round(v/peak*100));
    const lr=(g.reviews||[]).slice(-1)[0];
    const name=g.title+" 동접";
    TREND.groups[name]={
      products:[g.title], productsGoogle:[g.title],
      months:g.dates||[], naver:[norm], google:[norm],
      only:"naver", freq:"date", peak:peak,
      unit:"명(일 최고동접)", srcName:"SteamCharts · 일별 최고동접",
      reviewNote:(lr&&lr.pos!=null)?`리뷰 긍정 ${lr.pos.toFixed(0)}% · ${lr.t>=1e4?(lr.t/1e4).toFixed(0)+"만":lr.t}개`:""
    };
    (TREND_STOCK[g.stock]=TREND_STOCK[g.stock]||[]).push(name);
  });
})();
/* 탑툰챗(탑코미디어) — 웹툰 캐릭터 AI 채팅의 '일별 신규 대화수'.
   ⚠ DAU 는 공개되지 않는다. 사이트가 공개하는 건 캐릭터별 **누적** 대화수라,
   fetch_toptoonchat.py 가 매일 한 번 찍어 두고 여기서 **일별 증분**으로 바꾼다
   (유튜브 조회수를 일일 증분으로 쌓는 방식과 같다). 대리지표이지 DAU 가 아니다.
   한국·일본을 따로 둔다 — 2026년 일본(5월)·북미(7월) 진출이라 지역별 성장이 핵심이다.
   ⚠ 여기서 합계끼리 빼지 말 것. 합계는 '그날 홈에 노출된 캐릭터들의 합' 이라
   한 명이 홈에서 빠지면 그 사람 누적치가 통째로 사라져 증분이 음수가 된다
   (2026-09-01 실측: 개별은 전부 늘었는데 KR 합계는 대화 -3,284 · 조회 -144,392).
   그래서 증분은 fetch_toptoonchat.py 가 '어제·오늘 둘 다 있는 캐릭터'로 계산해
   hist[].dchat 에 넣어 둔다. 누적도 같은 이유로 조정누적(cchat)을 쓴다.
   증분은 점이 2개 이상 쌓여야 나오므로 수집 이튿날부터 그려진다. */
(function injectToptoonChat(){
  if(typeof TOPTOON==="undefined"||!TOPTOON.sites) return;
  const NM={KR:"한국", JP:"일본"};
  const md=d=>{const p=(d||"").slice(5).split("-"); return p.length===2?`${+p[0]}/${+p[1]}`:d;};
  TOPTOON.sites.forEach(st=>{
    const h=st.hist||[];
    const add=(nm,obj)=>{ TREND.groups[nm]=obj;
      (TREND_STOCK["탑코미디어"]=TREND_STOCK["탑코미디어"]||[]).push(nm); };

    // ① 일별 증분 — 교집합 기준. dchat 이 없는 옛 점(구조 변경 전)은 그냥 건너뛴다.
    const dr=h.filter(x=>x.dchat!=null);
    if(dr.length && dr.some(x=>x.dchat>0)){
      const inc=dr.map(x=>x.dchat), peak=Math.max(...inc)||1;
      const nc=dr[dr.length-1].nc;
      add(`탑툰챗 대화(${NM[st.code]||st.code})`,{
        products:["탑툰챗"], productsGoogle:["탑툰챗"],
        months:dr.map(x=>md(x.d)),
        naver:[inc.map(v=>Math.round(v/peak*100))],
        google:[inc.map(v=>Math.round(v/peak*100))],
        only:"naver", freq:"date", peak:peak,
        unit:"건(일 신규 대화)",
        srcName:`탑툰챗 · 전일 대비 신규 대화(공통 캐릭터 ${nc}명 기준)`
      });
    }

    // ② 조정 누적 — 원합계(chat)는 명단이 바뀌면 꺾이므로 증분을 더해 올린 cchat 을 쓴다.
    const cr=h.filter(x=>x.cchat!=null);
    if(cr.length>=2){
      const cum=cr.map(x=>x.cchat), cpk=Math.max(...cum)||1;
      add(`탑툰챗 누적대화(${NM[st.code]||st.code})`,{
        products:["탑툰챗 누적"], productsGoogle:["탑툰챗 누적"],
        months:cr.map(x=>md(x.d)),
        naver:[cum.map(v=>Math.round(v/cpk*100))],
        google:[cum.map(v=>Math.round(v/cpk*100))],
        only:"naver", freq:"date", peak:cpk,
        unit:"건(누적 대화)", srcName:"탑툰챗 · 조정 누적(증분 합산)"
      });
    }

    // ③ 캐릭터별 — 어느 캐릭터가 끌고 있나. 상위 6명만(계열이 많으면 선이 엉킨다).
    const top=(st.chars||[]).slice(0,6).filter(c=>(c.hist||[]).length>=2);
    if(top.length){
      const days=[...new Set(top.flatMap(c=>(c.hist||[]).map(x=>x.d)))].sort();
      const ser=top.map(c=>{const m={}; (c.hist||[]).forEach(x=>m[x.d]=x.chat||0);
        return days.map(d=>m[d]==null?null:m[d]);});
      const pk=Math.max(...ser.flat().filter(v=>v!=null),1);
      add(`탑툰챗 캐릭터별(${NM[st.code]||st.code})`,{
        products:top.map(c=>c.name), productsGoogle:top.map(c=>c.name),
        months:days.map(md),
        naver:ser.map(a=>a.map(v=>v==null?null:Math.round(v/pk*100))),
        google:ser.map(a=>a.map(v=>v==null?null:Math.round(v/pk*100))),
        only:"naver", freq:"date", peak:pk,
        unit:"건(누적 대화)", srcName:"탑툰챗 · 캐릭터별 누적 대화수"
      });
    }
  });
})();
/* AI 캐릭터 챗봇 앱 순위 — 탑툰챗의 경쟁 지형을 '검색'이 아니라 '돈'으로 본다.
   ⚠ 탑툰챗은 앱이 없다(웹 전용) → 이 순위에 안 잡힌다. 탑툰챗 자체 사용량은 위
   injectToptoonChat(홈페이지 실측)이 담당하고, 여기서는 경쟁자 위치와 탑툰 본체 앱을 본다.
   왜 앱순위인가: '크랙'은 소프트웨어 크랙과 동음이의어라 검색량이 통째로 오염되고,
   이 시장은 이미 유료 구독으로 돈을 벌고 있어 매출순위가 훨씬 직접적이다.
   순위는 작을수록 상위라 그대로 그리면 거꾸로 보인다 → 101-순위 로 뒤집어 그리고,
   실제 순위는 rawSer 로 넘겨 툴팁에 '10위' 로 찍는다. Top100 밖은 null(선이 끊긴다). */
(function injectAiChatRank(){
  if(typeof AICHAT==="undefined"||!AICHAT.apps) return;
  const days=[...new Set(AICHAT.apps.flatMap(a=>(a.hist||[]).map(x=>x.d)))].sort();
  if(days.length<1) return;
  const mm=d=>{const p=(d||"").slice(5).split("-"); return p.length===2?`${+p[0]}/${+p[1]}`:d;};
  const add=(name, apps, key, note)=>{
    const rows=apps.map(a=>{
      const m={}; (a.hist||[]).forEach(x=>{ if(x[key]!=null) m[x.d]=x[key]; });
      return {a, raw:days.map(d=>m[d]==null?null:m[d])};
    }).filter(r=>r.raw.some(v=>v!=null))
      // 지금 순위가 높은(작은) 것부터 — 범례·색 순서가 차트 위아래와 맞는다
      .sort((x,y)=>{const lx=[...x.raw].reverse().find(v=>v!=null)||999,
                          ly=[...y.raw].reverse().find(v=>v!=null)||999; return lx-ly;})
      .slice(0,6);
    if(!rows.length) return;
    const lbl=rows.map(r=>r.a.co&&r.a.co!=="—"?`${r.a.n}(${r.a.co})`:r.a.n);
    const ser=rows.map(r=>r.raw.map(v=>v==null?null:101-v));
    TREND.groups[name]={
      products:lbl, productsGoogle:lbl,
      months:days.map(mm), naver:ser, google:ser, rawSer:rows.map(r=>r.raw),
      only:"naver", freq:"date", unitShort:"위", srcName:note,
      // 차트는 101-순위 로 뒤집어 그리지만, 범례·표에는 실제 순위를 적는다.
      fmt:v=>(v==null?"—":(101-v)+"위")
    };
    (TREND_STOCK["탑코미디어"]=TREND_STOCK["탑코미디어"]||[]).push(name);
  };
  const ent=AICHAT.apps.filter(a=>a.g===6016), book=AICHAT.apps.filter(a=>a.g===6018);
  add("AI챗 앱 매출순위", ent, "gr",
      "애플 앱스토어(한국) 엔터테인먼트 매출 Top100 · 위로 갈수록 상위 · 100위권 밖은 끊김");
  add("AI챗 앱 무료순위", ent, "fr",
      "애플 앱스토어(한국) 엔터테인먼트 무료 Top100 · 위로 갈수록 상위 · 신규 유입/화제성");
  add("웹툰앱 순위(도서)", book, "fr",
      "애플 앱스토어(한국) 도서 무료 Top100 · 위로 갈수록 상위 · 탑툰 본체 앱");
})();
/* 치지직(CHZZK) 게임 시청자도 트렌드 비교 탭에 편입. 트위치가 한국을 떠나 국내 시청은
   치지직이 메인이라, Steam 동접(플레이)과 짝을 이룬다. 과거 시계열이 없어 며칠 쌓여야 뜬다. */
(function injectChzzkTrends(){
  if(typeof CHZZK==="undefined"||!CHZZK.games) return;
  CHZZK.games.forEach(g=>{
    const raw=(g.hist||[]).map(h=>h.v); const vals=raw.filter(x=>x!=null);
    if(vals.length<2) return;                      // 1점뿐이면 아직 안 뜬다(며칠 쌓이면)
    const peak=Math.max(...vals)||1;
    const norm=raw.map(v=>v==null?0:Math.round(v/peak*100));
    const dates=(g.hist||[]).map(h=>{const p=(h.d||"").slice(5).split("-");
      return p.length===2?`${+p[0]}/${+p[1]}`:h.d;});
    const name=g.title+" 시청(치지직)";
    TREND.groups[name]={
      products:[g.title], productsGoogle:[g.title],
      months:dates, naver:[norm], google:[norm],
      only:"naver", freq:"date", peak:peak,
      unit:"명(치지직 시청자)", srcName:"치지직 CHZZK · 국내 스트리밍"
    };
    (TREND_STOCK[g.stock]=TREND_STOCK[g.stock]||[]).push(name);
  });
})();
/* YouTube 채널의 '일일 조회수 증가'를 트렌드 비교 탭에 편입. 엔터 IP 컴백/관심 신호.
   누적 조회수의 전일 대비 증가분이 진짜 신호라, Δ 를 계열로 쓴다(며칠 쌓여야 뜬다). */
/* 유튜브 조회수 — 엔터사별 '일일 조회수 증가'를 기간 추이 스택 막대로(가수별 쪼갬 X, 스포티파이와 동일).
   injectCompanyStack 은 아래에 함수 선언(호이스팅)이라 여기서 호출 가능. */
(function(){
  if(typeof YT==="undefined"||!YT.channels) return;
  const vTxt=n=>n>=1e8?(n/1e8).toFixed(2)+"억회":n>=1e4?Math.round(n/1e4).toLocaleString()+"만회":(n||0).toLocaleString()+"회";
  const items=YT.channels.map(c=>{
    const h=(c.hist||[]).filter(x=>x&&x.views!=null);
    const pts=[];
    for(let i=1;i<h.length;i++) pts.push({d:h[i].d, v:Math.max(0,h[i].views-h[i-1].views)});  // 일일 조회수 증가분
    return {stock:c.stock, label:c.label, pts};
  });
  injectCompanyStack(items, {suffix:"조회수(YouTube)", unit:"회", fmt:vTxt, srcName:"YouTube 일일 조회수 증가 · 소속 채널 스택(기간 추이)"});
})();
/* 트위치(글로벌) 게임 시청자도 트렌드 비교 탭에 편입 — 치지직(국내)과 나란히. 며칠 쌓여야 뜬다. */
(function injectTwitchTrends(){
  if(typeof TWITCH==="undefined"||!TWITCH.games) return;
  TWITCH.games.forEach(g=>{
    const raw=(g.hist||[]).map(h=>h.v); const vals=raw.filter(x=>x!=null);
    if(vals.length<2) return;
    const peak=Math.max(...vals)||1;
    const norm=raw.map(v=>v==null?0:Math.round(v/peak*100));
    const dates=(g.hist||[]).map(h=>{const p=(h.d||"").slice(5).split("-");
      return p.length===2?`${+p[0]}/${+p[1]}`:h.d;});
    const name=g.title+" 시청(트위치)";
    TREND.groups[name]={
      products:[g.title], productsGoogle:[g.title],
      months:dates, naver:[norm], google:[norm],
      only:"naver", freq:"date", peak:peak,
      unit:"명(트위치 시청자)", srcName:"트위치 · 글로벌 스트리밍"
    };
    (TREND_STOCK[g.stock]=TREND_STOCK[g.stock]||[]).push(name);
  });
})();
/* Steam '일일 신규 리뷰'를 트렌드 편입 — 리뷰는 구매자만 쓰므로 일일 증가분이 판매 대리지표.
   누적 리뷰수(reviews[].t)의 전일 대비 Δ. 며칠 쌓여야 뜬다. */
(function injectSteamReviewTrends(){
  if(typeof STEAM==="undefined"||!STEAM.games) return;
  STEAM.games.forEach(g=>{
    const rv=(g.reviews||[]).filter(x=>x&&x.t!=null);
    if(rv.length<3) return;
    const d=[], dates=[];
    for(let i=1;i<rv.length;i++){
      d.push(Math.max(0,rv[i].t-rv[i-1].t));
      const p=(rv[i].d||"").slice(5).split("-"); dates.push(p.length===2?`${+p[0]}/${+p[1]}`:rv[i].d);
    }
    const peak=Math.max(...d)||1, pos=rv[rv.length-1].pos;
    const name=g.title+" 리뷰↑";
    TREND.groups[name]={
      products:[g.title], productsGoogle:[g.title],
      months:dates, naver:[d.map(v=>Math.round(v/peak*100))], google:[d.map(v=>Math.round(v/peak*100))],
      only:"naver", freq:"date", peak:peak,
      unit:"개(일일 신규리뷰)", srcName:"Steam · 일일 신규리뷰(판매 대리지표)",
      reviewNote:(pos!=null?`현재 긍정 ${pos.toFixed(0)}%`:"")
    };
    (TREND_STOCK[g.stock]=TREND_STOCK[g.stock]||[]).push(name);
  });
})();
/* Spotify 아티스트 인기도(0~100, 최근 스트리밍 반영)를 트렌드 편입. popularity 는 이미 0~100 이라
   정규화 없이 그대로 쓴다(차트 y축과 일치). 팔로워는 각주. 며칠 쌓이면 추이선 표시. */
(function injectSpotifyTrends(){
  if(typeof SPOTIFY==="undefined"||!SPOTIFY.artists) return;
  const dlab=x=>{const p=(x.d||"").slice(5).split("-");
    return p.length===2?`${+p[0]}/${+p[1]}`:x.d;};
  const folTxt=f=>`팔로워 ${f>=1e6?(f/1e6).toFixed(1)+"M":f>=1e3?(f/1e3).toFixed(0)+"K":f}`;
  const manTxt=n=>n>=1e8?(n/1e8).toFixed(2)+"억명":n>=1e4?Math.round(n/1e4).toLocaleString()+"만명":n.toLocaleString()+"명";
  SPOTIFY.artists.forEach(a=>{
    const rel=a.release&&a.release.name?` · 최근작 ${a.release.name}(${a.release.date})`:"";
    const tt=a.topTrack?` · 대표곡 ${a.topTrack}`:"";
    const last=(a.hist||[])[a.hist.length-1]||{};
    // 인기도(0~100) — 이미 0~100 이라 정규화 없이 그대로. 팔로워는 각주.
    const hp=(a.hist||[]).filter(x=>x&&x.pop!=null);
    if(hp.length>=2){
      const name=a.label+" 인기도(Spotify)";
      TREND.groups[name]={
        products:[a.label], productsGoogle:[a.label],
        months:hp.map(dlab), naver:[hp.map(x=>x.pop)], google:[hp.map(x=>x.pop)],
        only:"naver", freq:"date",
        srcName:"Spotify 인기도(0~100, 최근 스트리밍)",
        reviewNote:folTxt(last.fol||0)+rel+tt
      };
      (TREND_STOCK[a.stock]=TREND_STOCK[a.stock]||[]).push(name);
    }
    // 월간청취자(ml)·일간스트림(sd) 둘 다 가수별로 쪼개지 않고 injectSpotifyCompany 에서 엔터사별 막대로 모은다.
  });
})();
/* 엔터사별 '기간 추이' 스택 막대 헬퍼 — 여러 소비지표(스포티파이·유튜브 등)에서 공용.
   items: [{stock, label, pts:[{d, v}]}]. 회사마다 x=날짜, 막대=소속 아티스트 스택, 높이=회사 합계.
   써클 월간 앨범판매와 같은 형태. 이상치는 막대 호버로 아티스트별 확인. 회사 병렬 비교(스냅샷)는 안 쓴다. */
function injectCompanyStack(items, opt){
  const PAL=["#c4a7e7","#f6c177","#9ccfd8","#eb6f92","#a6da95","#3e8fb0","#ea9a97","#c9a227","#b08bd0","#7ea1c4","#8caf6e","#cf9f6a","#6ab0a3","#c98aa6"];
  const dlab=d=>{const p=(d||"").slice(5).split("-");return p.length===2?`${+p[0]}/${+p[1]}`:d;};
  const byCo={};
  items.forEach(it=>{ if(it.pts&&it.pts.length) (byCo[it.stock]=byCo[it.stock]||[]).push(it); });
  Object.entries(byCo).forEach(([co,arts])=>{
    const dates=[...new Set(arts.flatMap(a=>a.pts.map(p=>p.d)))].sort();
    if(dates.length<(opt.minDates||2)) return;       // 추이는 2일 이상 있어야
    arts.sort((x,y)=> y.pts[y.pts.length-1].v - x.pts[x.pts.length-1].v);
    const products=[], series=[], colors=[];
    arts.forEach((a,i)=>{
      const map=Object.fromEntries(a.pts.map(p=>[p.d,p.v]));
      products.push(a.label);
      series.push(dates.map(d=> map[d]!=null?map[d]:0));
      colors.push(PAL[i%PAL.length]);
    });
    const total=dates.map((_,i)=>series.reduce((s,ser)=>s+(ser[i]||0),0));
    const name=`${co} ${opt.suffix}`;
    TREND.groups[name]={
      products, productsGoogle:products, months:dates.map(dlab),
      naver:series, google:series, only:"naver", freq:"date",
      stack:true, colors, fmt:opt.fmt, unit:opt.unit, srcName:opt.srcName,
      reviewNote:`최근 ${opt.fmt(total[total.length-1])}`
    };
    (TREND_STOCK[co]=TREND_STOCK[co]||[]).push(name);
  });
}
/* 스포티파이 — 월간청취자·일간스트림을 엔터사별 기간 추이 막대로(가수별 쪼갬 X). */
(function(){
  if(typeof SPOTIFY==="undefined"||!SPOTIFY.artists) return;
  const manTxt=n=>n>=1e8?(n/1e8).toFixed(2)+"억명":n>=1e4?Math.round(n/1e4).toLocaleString()+"만명":(n||0).toLocaleString()+"명";
  const strTxt=n=>manTxt(n).replace("명","회");
  const items=metric=>SPOTIFY.artists.map(a=>({stock:a.stock, label:a.label,
    pts:(a.hist||[]).filter(x=>x&&x[metric]!=null).map(x=>({d:x.d, v:x[metric]}))}));
  injectCompanyStack(items("ml"), {suffix:"월간청취자 추이(Spotify)", unit:"명", fmt:manTxt, srcName:"Spotify 월간청취자(최근 28일 순청취자, 매일 기록) · 소속 아티스트 스택"});
  injectCompanyStack(items("sd"), {suffix:"일간 스트림(Spotify)", unit:"회", fmt:strTxt, srcName:"Spotify 일간 스트림 · 소속 아티스트 스택(기간 추이)"});
})();
/* 앱스토어(Apple) 게임 매출순위 — 게임 종목 소비/수요 신호(Spotify 스트림과 짝).
   순위는 낮을수록 좋으니 101−순위 점수로 변환(높을수록 상위 = 선이 위로). 실제 순위는 각주.
   구글 플레이는 무료 API 가 없어 미수집(애플만). 하루 더 쌓이면 선이 그려진다. */
(function injectAppRankTrends(){
  if(typeof APPRANK==="undefined"||!APPRANK.games) return;
  const dlab=x=>{const p=(x.d||"").slice(5).split("-"); return p.length===2?`${+p[0]}/${+p[1]}`:x.d;};
  APPRANK.games.forEach(g=>{
    const hp=(g.hist||[]).filter(x=>x&&x.gr!=null);
    if(hp.length<2) return;
    const score=hp.map(x=>101-x.gr);          // 순위1→100점, 순위100→1점
    const last=hp[hp.length-1];
    const fr=last.fr!=null?` · 무료 ${last.fr}위`:"";
    const t=last.t?` · ${last.t}`:"";
    const name=g.stock+" 앱스토어 매출순위(Apple)";
    TREND.groups[name]={
      products:[g.stock], productsGoogle:[g.stock],
      months:hp.map(dlab), naver:[score], google:[score],
      only:"naver", freq:"date",
      srcName:"Apple 앱스토어 게임 매출순위(101−순위 점수 · 무료 API 없어 구글 제외)",
      reviewNote:`매출 ${last.gr}위${fr}${t}`
    };
    (TREND_STOCK[g.stock]=TREND_STOCK[g.stock]||[]).push(name);
  });
})();
/* 방한 외래관광객(월별)을 호텔/면세/카지노 종목의 트렌드로 편입 — 인바운드 관광 = 수요 매크로. */
(function injectTourismTrends(){
  if(typeof TOURISM==="undefined"||!TOURISM.total||TOURISM.total.length<2) return;
  const months=(TOURISM.months||[]).map(m=>`${m.slice(2,4)}.${+m.slice(4,6)}`);
  const total=TOURISM.total, peak=Math.max(...total)||1;
  TREND.groups["방한 외래관광객"]={
    products:["방한 외래관광객"], productsGoogle:["방한 외래관광객"],
    months:months, naver:[total.map(v=>Math.round(v/peak*100))],
    google:[total.map(v=>Math.round(v/peak*100))],
    only:"naver", freq:"month", peak:peak,
    unit:"명(월)", srcName:"한국관광 데이터랩 · 방한 외래관광객(월별)"
  };
  ["파라다이스","롯데관광개발","GKL","호텔신라","현대백화점","신세계"].forEach(s=>{
    (TREND_STOCK[s]=TREND_STOCK[s]||[]).push("방한 외래관광객");
  });
})();
/* 써클차트 앨범 판매량 — 엔터 종목의 실물 수요/매출 신호. 회사 합계(월·주).
   회사 판매량 = 소속 아티스트 판매량의 합이므로 '아티스트별 색상 누적 막대'로 그린다
   (stack:true). 막대 높이=회사 총 판매량, 색 구간=아티스트. 추적 외 소속은 '기타'로 묶는다. */
(function injectCircleTrends(){
  if(typeof CIRCLE==="undefined"||!CIRCLE) return;
  const jang=n=>n>=1e8?(n/1e8).toFixed(2)+"억장":n>=1e4?Math.round(n/1e4).toLocaleString()+"만장":(n||0).toLocaleString()+"장";
  const aStock=CIRCLE.artistStock||{};
  const GREY=(getComputedStyle(document.documentElement).getPropertyValue('--muted')||"#8a8a99").trim();
  // 자체 팔레트(fetch_trends 가 TREND.colors 를 덮어쓰므로 여기 둔다). 세그먼트가 많아 14색.
  const CPAL=["#c4a7e7","#f6c177","#9ccfd8","#eb6f92","#a6da95","#3e8fb0","#ea9a97","#c9a227",
              "#b08bd0","#7ea1c4","#8caf6e","#cf9f6a","#6ab0a3","#c98aa6"];
  const MAXSEG=11;                    // 색 구간 상한. 초과 소속은 '기타'로 접힌다.
  ["month","week"].forEach(term=>{
    const b=CIRCLE[term]; if(!b||!(b.periods||[]).length) return;
    const fr=term==="week"?"week":"month", tag=term==="week"?"주":"월", N=b.periods.length;
    Object.entries(b.byStock||{}).forEach(([stock,total])=>{
      if(!total.some(v=>v)) return;
      // 소속 아티스트(판매 있는 것) — 기간 총합 큰 순, 상위 MAXSEG 만 개별 구간으로
      let arts=Object.entries(b.byArtist||{})
        .filter(([lab,ser])=>aStock[lab]===stock && ser.some(v=>v))
        .sort((x,y)=>y[1].reduce((s,v)=>s+(v||0),0)-x[1].reduce((s,v)=>s+(v||0),0))
        .slice(0,MAXSEG);
      const products=[], series=[], colors=[];
      arts.forEach(([lab,ser],i)=>{ products.push(lab); series.push(ser); colors.push(CPAL[i%CPAL.length]); });
      // 기타 = 회사총합 − 표시된 아티스트합(상한 초과·미추적 소속). 막대 맨 위 회색 구간.
      const etc=b.periods.map((_,i)=>Math.max(0, total[i]-arts.reduce((s,[,ser])=>s+(ser[i]||0),0)));
      if(etc.some(v=>v>0)){ products.push("기타"); series.push(etc); colors.push(GREY||"#8a8a99"); }
      const mine=(b.top||[]).filter(t=>t.stock===stock).sort((a,c)=>c.cnt-a.cnt)[0];
      const name=`${stock} 앨범판매(${tag}·써클)`;
      TREND.groups[name]={
        products, productsGoogle:products, months:b.periods,
        naver:series, google:series, only:"naver", freq:fr,
        stack:true, colors, fmt:jang, unit:"장",
        srcName:`써클차트 앨범판매(${term==="week"?"주간":"월간"})`,
        reviewNote:`최근 ${jang(total[N-1])}`+(mine?` · 최다 ${mine.artist.replace(/\s*\(.*\)/,"")} ${jang(mine.cnt)}`:"")
      };
      (TREND_STOCK[stock]=TREND_STOCK[stock]||[]).push(name);
    });
  });
})();
/* 데이터 있는 주제만. 게임사는 동접·리뷰(실측 플레이)가 검색보다 중요하므로 앞으로 당긴다.
   앨범판매(써클)는 엔터 실물수요라 검색보다 앞. 나머지는 삽입 순서를 유지(안정 정렬). */
const topicsOf=n=>{
  const list=(TREND_STOCK[n]||[]).filter(g=>TREND.groups[g]);
  const pri=g=> g.includes("동접")?0 : (g.includes("리뷰")||g.includes("시청"))?1
             : g.includes("앨범판매")?2 : 3;
  return list.map((g,i)=>[g,i]).sort((a,b)=>pri(a[0])-pri(b[0])||a[1]-b[1]).map(x=>x[0]);
};
const TREND_STOCKS=R.slice().sort((a,b)=>(a.rank||999)-(b.rank||999))
  .map(r=>r.name).filter(n=>topicsOf(n).length);   // 커버리지(rank) 순서
/* 처음엔 아무 종목도 고르지 않은 상태 — 눌러야 그래프가 나온다 */
let trendStock="", trendGroup="", trendFreq="week";   // 기간: 주별(롱텀)/일별(숏텀)
/* 그룹의 기본 빈도(freq). 하위호환: 옛 daily 플래그도 인식 */
const nativeFreq=G=> (G&&G.freq) || (G&&G.daily?"date":"month");
/* 그 그룹이 가진 빈도 목록. alt 에 반대 빈도가 있으면 둘 다. */
function freqsOf(G){ if(!G) return []; const f=[nativeFreq(G)];
  if(G.alt&&G.alt.freq&&!f.includes(G.alt.freq)) f.push(G.alt.freq); return f; }
/* 현재 선택된 기간(trendFreq)에 맞는 뷰를 돌려준다. 없으면 원본(네이티브).
   alt 는 반대 빈도의 완전한 그룹이라, 있으면 그쪽 months/naver/google/products 로 갈아끼운다. */
function viewGroup(G){ if(!G) return G;
  if(trendFreq===nativeFreq(G)) return G;
  if(G.alt&&G.alt.freq===trendFreq) return Object.assign({}, G, G.alt);
  return G; }
/* 그 주제가 실제로 가진 출처만 남긴다.
   only 가 붙어 있으면 반대쪽은 같은 값을 복사해 둔 것이라 눌러도 그래프가 안 바뀐다. */
const srcOfGroup=G=> G && G.only ? [G.only] : ["naver","google"];
/* 토스식 호버 툴팁 — 수출 차트에 쓰는 것과 같은 방식의 공용판.
   svg viewBox 좌표로 역변환해 커서가 가리키는 기간을 찾고,
   세로 가이드선 + 카드형 툴팁을 띄운다. 트렌드의 겹침·격자·스택 세 차트가 같이 쓴다.
   getScreenCTM 이 스케일·레터박스(가운데 여백)·preserveAspectRatio=none 까지 보정한다. */
function attachChartTip(box, o){
  // o: {W,H,pad,n, xOf(i)->viewBox x, html(i)->툴팁 내용(null 이면 안 띄움)}
  const svg=box.querySelector("svg"); if(!svg||!o.n) return;
  box.style.position="relative";
  const guide=document.createElement("div"); guide.className="chart-guide";
  const tip=document.createElement("div"); tip.className="chart-tip";
  box.append(guide,tip);
  const hide=()=>{ tip.style.display="none"; guide.style.display="none"; };
  box.onmousemove=(e)=>{
    const m=svg.getScreenCTM();
    if(!m||!m.a){ hide(); return; }                       // 미표시/0폭 방어
    const pt=svg.createSVGPoint(); pt.x=e.clientX; pt.y=e.clientY;
    const p=pt.matrixTransform(m.inverse());
    if(p.x<o.pad.l||p.x>o.W-o.pad.r||p.y<o.pad.t||p.y>o.H-o.pad.b){ hide(); return; }
    // 가장 가까운 점 — 등간격 가정 대신 실제 x 를 훑는다(막대 중심·꺾은선 둘 다 맞음)
    let i=0, best=Infinity;
    for(let k=0;k<o.n;k++){ const d=Math.abs(o.xOf(k)-p.x); if(d<best){best=d;i=k;} }
    const html=o.html(i); if(!html){ hide(); return; }
    tip.innerHTML=html; tip.style.display="block";
    const rc=box.getBoundingClientRect();
    const a=svg.createSVGPoint(); a.x=o.xOf(i); a.y=o.pad.t; const as=a.matrixTransform(m);
    const b=svg.createSVGPoint(); b.x=o.xOf(i); b.y=o.H-o.pad.b; const bs=b.matrixTransform(m);
    guide.style.display="block";
    guide.style.left=(as.x-rc.left).toFixed(1)+"px";
    guide.style.top=(as.y-rc.top).toFixed(1)+"px";
    guide.style.height=Math.abs(bs.y-as.y).toFixed(1)+"px";
    const tw=tip.offsetWidth||150, px=e.clientX-rc.left;
    tip.style.left=((px+16+tw>rc.width)? Math.max(4,px-tw-14) : px+16).toFixed(1)+"px";
    tip.style.top=Math.max(4,(e.clientY-rc.top)-tip.offsetHeight-10).toFixed(1)+"px";
  };
  box.onmouseleave=hide;
}

function drawTrend(){
  const box=document.getElementById("trendChart"); if(!box) return;
  const G0=TREND.groups[trendGroup];
  if(!G0){                                  // 종목 미선택 상태
    box.innerHTML=`<div class="ov-empty">위에서 <b>종목</b>을 고르면 트렌드가 표시됩니다.</div>`;
    document.getElementById("trendLegend").innerHTML="";
    const tb=document.getElementById("trendTable"); if(tb) tb.innerHTML="";
    const tt=document.getElementById("trendTblTitle"); if(tt) tt.textContent="";
    return;
  }
  const G=viewGroup(G0);                     // 선택된 기간(주별/일별)에 맞는 뷰
  const avail=srcOfGroup(G);
  if(!avail.includes(trendSrc)) trendSrc=avail[0];   // 없는 출처가 선택돼 있으면 되돌린다
  const series=G[trendSrc], M=G.months||TREND.months;
  // 표시 단위(일/주/월)별 용어 — 하위호환: 옛 daily 플래그도 인식
  const FREQ=G.freq||(G.daily?"date":"month");
  const U=({date:{u:"전일",back:"7일",n:7,g:"일별",p:"날"},
            week:{u:"전주",back:"4주",n:4,g:"주별",p:"주"},
            month:{u:"전월",back:"3개월",n:3,g:"월간",p:"달"}})[FREQ];
  // 구글은 영문 키워드로 수집하므로 라벨도 출처에 맞춰 표시
  const PRODUCTS=(trendSrc==="google" && G.productsGoogle) ? G.productsGoogle : G.products;
  const gc=getComputedStyle(document.documentElement).getPropertyValue('--line');
  const mut=getComputedStyle(document.documentElement).getPropertyValue('--muted');
  /* 국가별(multi)만 격자로 나눈다 — 계열마다 자기 최대가 100 인 별도 정규화라
     겹쳐 놓으면 크기를 비교할 수 있는 것처럼 읽히기 때문.
     반대로 브랜드 비교 그룹은 한 스케일로 같이 정규화돼 있어, 겹쳐 그리는 것 자체가
     정보다(메디큐브가 달바의 10배라는 사실). 그건 겹친 채로 둔다. */
  if(G.multi){
    drawTrendGrid(box, G, PRODUCTS, series, M, gc, mut);
    fillTrendLegendTable(G, PRODUCTS, series, M, U);
    return;
  }
  if(G.stack){                          // 앨범판매 등 절대수 누적 막대(색=계열)
    drawTrendStack(box, G, PRODUCTS, series, M, gc, mut);
    fillTrendLegendTable(G, PRODUCTS, series, M, U);
    return;
  }
  const W=box.clientWidth||1000, H=360, pad={l:44,r:70,t:16,b:36};
  // 점이 하나뿐인 계열(수집 첫날의 앱순위 등)은 M.length-1 == 0 이라 0/0 = NaN 이 된다.
  // 그러면 <polyline points="NaN,.."> 로 SVG 가 통째로 깨진다. 그땐 가운데에 점 하나만 찍는다.
  const sx=i=>M.length<2?pad.l+(W-pad.l-pad.r)/2:pad.l+i/(M.length-1)*(W-pad.l-pad.r);
  const sy=v=>H-pad.b-(v/100)*(H-pad.t-pad.b);
  let s=`<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" font-family="inherit">`;
  for(let g=0;g<=4;g++){const v=g*25;const y=sy(v);
    s+=`<line x1="${pad.l}" y1="${y}" x2="${W-pad.r}" y2="${y}" stroke="${gc}" stroke-width="1"/>`;
    s+=`<text x="${pad.l-8}" y="${y+4}" text-anchor="end" font-size="11" fill="${mut}">${v}</text>`;}
  const step=Math.max(1,Math.ceil(M.length/12));   // 라벨이 빽빽하면 솎아낸다(일별 대응)
  M.forEach((m,i)=>{ if(i%step===0 || i===M.length-1) s+=`<text x="${sx(i)}" y="${H-pad.b+18}" text-anchor="middle" font-size="10.5" fill="${mut}">${m}</text>`;});
  series.forEach((ser,pi)=>{
    const c=TREND.colors[pi];
    const pts=ser.map((v,i)=>`${sx(i).toFixed(1)},${sy(v).toFixed(1)}`).join(" ");
    s+=`<polyline points="${pts}" fill="none" stroke="${c}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>`;
    ser.forEach((v,i)=>{ s+=`<circle cx="${sx(i)}" cy="${sy(v)}" r="2.6" fill="${c}"><title>${PRODUCTS[pi]} ${M[i]}: ${v}</title></circle>`;});
    const last=ser[ser.length-1];
    s+=`<text x="${W-pad.r+8}" y="${sy(last)+4}" font-size="12" font-weight="700" fill="${c}">${PRODUCTS[pi]}</text>`;
  });
  s+="</svg>";
  box.innerHTML=s;
  /* 호버 툴팁 — 그 시점의 모든 계열 값과 전기간비를 한 카드에.
     얀덱스 그룹(peak)은 100 이 실제 몇 건인지 알고 있으므로 절대 건수도 같이 적는다. */
  attachChartTip(box,{W,H,pad,n:M.length,xOf:sx,html:i=>{
    const rows=series.map((ser,pi)=>({p:PRODUCTS[pi],c:TREND.colors[pi],v:ser[i],
        /* rawSer: 0-100 정규화 전의 실제 값. 순위처럼 peak 로 역산이 안 되는 계열이 쓴다. */
        r0:(G.rawSer&&G.rawSer[pi])?G.rawSer[pi][i]:null,
        /* 순위 계열(rawSer)은 전기간비 %가 뜻이 없다 — 10위→12위가 '-2.2%' 로 읽힌다. */
        d:(!G.rawSer&&i>0&&ser[i-1]>0&&ser[i]!=null)?(ser[i]/ser[i-1]-1)*100:null}))
      .filter(r=>r.v!=null)
      .sort((a,b)=>b.v-a.v);                 // 큰 것부터 — 차트에서 위에 있는 선 순서와 같다
    if(!rows.length) return null;
    return `<div class="tt-h">${M[i]}</div>`+rows.map(r=>
      `<div class="tt-r"><span class="k"><span class="dot" style="background:${r.c};width:8px;height:8px;display:inline-block;border-radius:50%;margin-right:5px"></span>${r.p}</span>`
      +`<span class="v">${r.r0!=null?"":r.v}${(r.r0!=null||G.peak)?`<span style="color:var(--muted);font-weight:600;font-size:10.5px">${r.r0!=null?"":" · "}${fmt0(r.r0!=null?r.r0:r.v*G.peak/100)}${G.unitShort||"건"}</span>`:""}`
      +`${r.d==null?"":` <span class="${cls(r.d)}" style="font-size:10.5px">${sign(r.d,0)}%</span>`}</span></div>`).join("");
  }});
  fillTrendLegendTable(G, PRODUCTS, series, M, U);
}

/* 계열별 미니 차트 격자. y축은 0–100 고정 —
   칸마다 자기 최대로 늘이면 작은 계열이 큰 계열처럼 보여 크기를 오해한다.
   대신 최근값을 헤더에 크게 적어 수치로 읽게 한다. */
function drawTrendGrid(box, G, PRODUCTS, series, M, gc, mut){
  const W=300, H=110, pad={l:6,r:6,t:10,b:16};
  const sx=i=>pad.l+i/Math.max(1,M.length-1)*(W-pad.l-pad.r);
  const sy=v=>H-pad.b-(v/100)*(H-pad.t-pad.b);
  // 계열별 출처 — 국가별은 수집 때 기록해 둔 값, 나머지는 지금 고른 출처
  const srcs=G.srcOf || PRODUCTS.map(()=> trendSrc==="naver" ? "네이버" : "구글");
  box.innerHTML=`<div class="sm-grid">`+PRODUCTS.map((p,i)=>{
    const ser=series[i]||[], c=TREND.colors[i], last=ser[ser.length-1];
    const src=srcs[i];
    let s=`<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" font-family="inherit" preserveAspectRatio="none">`;
    [0,50,100].forEach(v=>{ s+=`<line x1="${pad.l}" y1="${sy(v)}" x2="${W-pad.r}" y2="${sy(v)}" stroke="${gc}"/>`; });
    s+=`<polyline points="${ser.map((v,j)=>`${sx(j).toFixed(1)},${sy(v).toFixed(1)}`).join(" ")}"
         fill="none" stroke="${c}" stroke-width="2" stroke-linejoin="round"/>`;
    // x축은 양끝만 — 칸이 좁아 다 넣으면 뭉갠다
    s+=`<text x="${pad.l}" y="${H-3}" font-size="9" fill="${mut}">${M[0]||""}</text>`;
    s+=`<text x="${W-pad.r}" y="${H-3}" text-anchor="end" font-size="9" fill="${mut}">${M[M.length-1]||""}</text>`;
    s+="</svg>";
    return `<div class="sm-cell">
      <div class="sm-h"><span class="dot" style="background:${c}"></span>${p}
        ${src?`<span class="src">${src}</span>`:""}
        <span class="v" style="color:${c}">${last==null?"—":last}</span></div>${s}</div>`;
  }).join("")+`</div>`;
  // 칸마다 호버 툴팁 — 격자는 칸이 작아 x축 라벨이 양끝뿐이라, 중간 시점 값은 이걸로만 읽힌다
  [...box.querySelectorAll(".sm-cell")].forEach((cell,ci)=>{
    const ser=series[ci]||[];
    attachChartTip(cell,{W,H,pad,n:M.length,xOf:sx,html:i=>{
      const v=ser[i]; if(v==null) return null;
      const d=(i>0&&ser[i-1]>0)?(v/ser[i-1]-1)*100:null;
      return `<div class="tt-h">${PRODUCTS[ci]} · ${M[i]}</div>`
        +`<div class="tt-r"><span class="k">지수</span><span class="v">${v}`
        +`${d==null?"":` <span class="${cls(d)}" style="font-size:10.5px">${sign(d,0)}%</span>`}</span></div>`;
    }});
  });
}

/* 절대수 누적 막대 — 기간별로 계열(아티스트)을 쌓아 회사 총량을 만든다.
   y축은 0–100 이 아니라 실제 수치(장). 색=계열, 막대 위에 합계. */
function drawTrendStack(box, G, PRODUCTS, series, M, gc, mut){
  const W=box.clientWidth||1000, H=360, pad={l:70,r:74,t:20,b:36};
  const N=M.length, COL=G.colors||TREND.colors, fmt=G.fmt||(v=>v);
  const totals=M.map((_,i)=>series.reduce((s,ser)=>s+(ser[i]||0),0));
  const ymax=Math.max(...totals,1)*1.10, plotW=W-pad.l-pad.r;
  const bw=Math.max(6,Math.min(48, plotW/Math.max(1,N)*0.62));
  const cx=i=>pad.l+(i+0.5)/N*plotW;
  const sy=v=>H-pad.b-(v/ymax)*(H-pad.t-pad.b);
  const sN=v=>v>=1e8?(v/1e8).toFixed(1)+"억":v>=1e4?Math.round(v/1e4).toLocaleString()+"만":String(Math.round(v));
  let s=`<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" font-family="inherit">`;
  for(let g=0;g<=4;g++){const v=ymax*g/4, y=sy(v);
    s+=`<line x1="${pad.l}" y1="${y}" x2="${W-pad.r}" y2="${y}" stroke="${gc}" stroke-width="1"/>`;
    s+=`<text x="${pad.l-8}" y="${y+4}" text-anchor="end" font-size="11" fill="${mut}">${sN(v)}</text>`;}
  const step=Math.max(1,Math.ceil(N/12));
  M.forEach((m,i)=>{ if(i%step===0||i===N-1) s+=`<text x="${cx(i).toFixed(1)}" y="${H-pad.b+18}" text-anchor="middle" font-size="10.5" fill="${mut}">${m}</text>`; });
  M.forEach((m,i)=>{
    let acc=0;
    PRODUCTS.forEach((p,pi)=>{
      const v=(series[pi]||[])[i]||0; if(v<=0) return;
      const y0=sy(acc), y1=sy(acc+v); acc+=v;
      s+=`<rect x="${(cx(i)-bw/2).toFixed(1)}" y="${y1.toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(0,y0-y1).toFixed(1)}" fill="${COL[pi%COL.length]}"><title>${p} ${m}: ${fmt(v)}</title></rect>`;
    });
    if(totals[i]>0) s+=`<text x="${cx(i).toFixed(1)}" y="${(sy(totals[i])-4).toFixed(1)}" text-anchor="middle" font-size="9.5" fill="${mut}">${sN(totals[i])}</text>`;
  });
  s+="</svg>"; box.innerHTML=s;
  // 호버 툴팁 — 막대 하나에 계열이 쌓여 있어 구성비는 이걸로만 읽힌다. 큰 것부터, 합계는 맨 위.
  attachChartTip(box,{W,H,pad,n:N,xOf:cx,html:i=>{
    const rows=PRODUCTS.map((p,pi)=>({p,c:COL[pi%COL.length],v:(series[pi]||[])[i]||0}))
      .filter(r=>r.v>0).sort((a,b)=>b.v-a.v);
    if(!rows.length) return null;
    return `<div class="tt-h">${M[i]} · 합계 ${fmt(totals[i])}</div>`+rows.map(r=>
      `<div class="tt-r"><span class="k"><span class="dot" style="background:${r.c};width:8px;height:8px;display:inline-block;border-radius:50%;margin-right:5px"></span>${r.p}</span>`
      +`<span class="v">${fmt(r.v)}</span></div>`).join("");
  }});
}

function fillTrendLegendTable(G, PRODUCTS, series, M, U){
  const COL=G.colors||TREND.colors, F=G.fmt||(x=>x);   // 스택은 자체 색/장수 포맷을 쓴다
  document.getElementById("trendLegend").innerHTML=
    PRODUCTS.map((p,i)=>{
      const ser=series[i];
      const cur=G.snapshot?Math.max(...ser):ser[ser.length-1];   // 스냅샷(회사별 막대)은 자기 회사 칸 값
      const base=G.snapshot?0:ser[ser.length-2];
      const mom=(!G.rawSer&&base>0)?((ser[ser.length-1]/base-1)*100):null;
      // 순위 계열(rawSer)은 %가 뜻이 없다 — 10위→12위를 '-2.2%' 로 적으면 오독한다.
      const momTxt=(G.snapshot||G.rawSer)?"":` · ${U.u}비 ${mom==null?"—":`<span class="${cls(mom)}">${sign(mom)}%</span>`}`;
      // 계열마다 출처가 섞인 그룹에서만 출처를 붙인다(러시아=얀덱스 같은 경우)
      const mixed=G.srcOf && new Set(G.srcOf).size>1;
      const tag=mixed?` <small class="th-sub">${G.srcOf[i]}</small>`:"";
      return `<div class="li"><span class="dot" style="background:${COL[i]}"></span>${p}${tag}
        <small>최근 ${F(cur)}${momTxt}</small></div>`;
    }).join("")+(function(){
      if(G.stack){
        const rv=G.reviewNote?` · ${G.reviewNote}`:"";
        return `<div class="li" style="margin-left:auto"><small>출처: ${G.srcName||"써클차트"} · 색 = 소속 아티스트(막대=회사 합계) · 단위 ${G.unit||"장"}${rv}</small></div>`;
      }
      if(G.multi){
        // 계열마다 출처가 다를 수 있다(러시아는 얀덱스). 있는 그대로 적는다.
        const s=[...new Set(G.srcOf||["구글"])].join("·");
        return `<div class="li" style="margin-left:auto"><small>출처: ${s} · 나라별 현지 검색어·현지 지역 · <b>각국 자체 0–100 스케일(추이 비교용, 절대 크기 비교 불가)</b></small></div>`;
      }
      const gGeo=G.geo==="KR"?'국내':(G.geo?G.geo:'전세계');
      // srcOf 가 있으면 그게 실제 출처다. only:"google" 은 '출처 전환 없음' 표시일 뿐이라
      // 그대로 읽으면 얀덱스 데이터를 '구글 트렌드'로 잘못 적게 된다.
      const only1=(G.srcOf && [...new Set(G.srcOf)].length===1) ? G.srcOf[0] : null;
      const src=G.srcName ? G.srcName
        : only1 ? `${only1}(${gGeo})`
        : (trendSrc==='naver'?'네이버 데이터랩(국내)':`구글 트렌드(${gGeo})`);
      const solo=(G.only&&!G.srcName)?` · 이 주제는 ${src} 만 유효해 출처 전환 없음`:"";
      // 얀덱스·Steam 은 절대값이라 100 이 얼마인지 밝혀야 크기 감각이 산다
      const pk=G.peak?` · 100 = ${G.unit?"":"주당 "}${fmt0(G.peak)}${G.unit||"건"}`:"";
      const rv=G.reviewNote?` · ${G.reviewNote}`:"";
      return `<div class="li" style="margin-left:auto"><small>출처: ${src} · ${U.g} 상대값 0–100${pk} · 진행 중인 ${U.p} 제외${rv}${solo}</small></div>`;
    })();
  // table — 표시 단위에 맞춰 라벨/기준 전환
  const back=U.n, uMom=U.u+"비", lBack=U.back+"전", lChg=U.back+" 변화";
  const tt=document.getElementById("trendTblTitle");
  if(tt) tt.textContent=`${trendGroup} · ${G.srcName||(trendSrc==="naver"?"네이버":"구글")} — 최근값 · ${uMom}`;
  makeTable(document.getElementById("trendTable"),[
    {key:"p",label:"키워드",l:true,render:r=>`<span class="nm-cell"><span class="dot" style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${r.color};margin-right:6px"></span>${r.p}</span>`},
    {key:"cur",label:"최근값",render:r=>F(r.cur)},
    {key:"m3",label:lBack,render:r=>r.m3==null?"—":F(r.m3)},
    {key:"mom",label:uMom,render:r=>r.mom==null?"—":`<span class="${cls(r.mom)}">${sign(r.mom)}%</span>`},
    {key:"q",label:lChg,render:r=>r.q==null?"—":`<span class="${cls(r.q)}">${sign(r.q,0)}%</span>`},
  ], PRODUCTS.map((p,i)=>{
    const ser=series[i];const cur=ser[ser.length-1];const prev=ser[ser.length-2];
    const bk=ser.length>back?ser[ser.length-1-back]:null;
    const pct=!G.rawSer;   // 순위 계열은 증감률 칸을 비운다(위 momTxt 와 같은 이유)
    return {p,color:COL[i],cur,m3:bk,mom:(pct&&prev>0)?(cur/prev-1)*100:null,
            q:(pct&&bk>0)?(cur/bk-1)*100:null};
  }), {key:"cur",dir:-1});
}
/* ==== 해외 쇼핑몰 수요 (SHOP) ====
   검색 트렌드가 '관심'이라면 이쪽은 '팔리고 있나'다. 리뷰는 구매자만 남기므로
   주간 증가분이 판매 대리지표가 된다. 생산지가 아니라 그 나라에서 팔린 것을 재므로
   중국에서 만들어 러시아로 직수출되는 물량도 러시아 쪽에 잡힌다.
   두 API 다 과거를 안 줘서 주 1회 한 점씩 쌓는다 — 처음엔 점 하나뿐이다. */
const SHOP_SRC={wb:{name:"와일드베리즈",country:"러시아"},rk:{name:"라쿠텐",country:"일본"}};
/* 트렌드 수집일 — 주 1회 수집이라 '언제 것인지'를 모르면 판단이 어긋난다.
   시세는 매시간이지만 트렌드는 지난주 값일 수 있다는 걸 화면이 말해 줘야 한다. */
function setTrendFoot(){
  const el=document.getElementById("trendFoot"); if(!el) return;
  const t=(typeof TREND!=="undefined")&&TREND.asOf;
  el.innerHTML="네이버는 국내 검색, 구글은 해외 수요 — 두 값의 괴리 자체가 시그널."
    // '수집'이 아니라 '갱신'이다 — 값이 그대로면 파일을 건드리지 않으므로
    // 이 시각은 마지막으로 '값이 바뀐' 때다. 매주 확인은 하고 있다.
    +(t?` 최종 갱신 ${t} · 매주 확인.`:"");
}

function renderShop(){
  const box=document.getElementById("shopBox"); if(!box) return;
  const note=document.getElementById("shopNote");
  const S=(typeof SHOP!=="undefined")?SHOP:null;
  if(!S||!S.series||!trendStock){
    box.innerHTML=`<div class="ov-empty">${!trendStock?"종목을 고르면 해당 종목의 해외 쇼핑몰 수요가 표시됩니다."
      :"수집된 쇼핑몰 데이터가 없습니다."}</div>`;
    note.textContent=""; return;
  }
  const mine=(S.targets||[]).filter(t=>t.stock===trendStock);
  const cells=[];
  mine.forEach(t=>Object.keys(SHOP_SRC).forEach(src=>{
    const pts=S.series[`${t.label}|${src}`];
    if(!pts||!pts.length) return;
    const last=pts[pts.length-1], prev=pts.length>1?pts[pts.length-2]:null;
    const d=(prev&&prev.rev>0)?((last.rev/prev.rev-1)*100):null;   // 리뷰 증가율 = 판매 대리지표
    cells.push(`<div class="sm-cell"${t.comp?' style="opacity:.82"':''}>
      <div class="sm-h"><span class="dot" style="background:var(--${t.comp?'muted':'accent'})"></span>${t.label}
        ${t.comp?`<span class="src">경쟁 · ${t.comp}</span>`:""}
        <span class="src">${SHOP_SRC[src].country} · ${SHOP_SRC[src].name}</span>
        <span class="v">${fmt0(last.rev)}</span></div>
      <div class="shop-kv">리뷰 누적 <b>${fmt0(last.rev)}</b>
        · 상품 ${last.n}개 · 평점 ${last.rating==null?"—":last.rating}
        · ${d==null?`<span class="th-sub">추이는 다음 수집부터</span>`
                   :`전주비 <span class="${cls(d)}">${sign(d,1)}%</span>`}</div>
    </div>`);
  }));
  box.innerHTML=cells.length?`<div class="sm-grid">${cells.join("")}</div>`
    :`<div class="ov-empty">${trendStock} 은(는) 아직 추적 대상이 아닙니다.</div>`;
  note.textContent=cells.length
    ? `${S.asOf} 기준 · 리뷰는 구매자만 남기므로 누적 리뷰 증가분이 판매 대리지표 · `
      +`주 1회 수집이라 시계열은 쌓이는 중 · 대상 편집은 fetch_shop.py 의 TARGETS`
    : "";
}

/* ══════════ 탑툰챗 (탑코미디어) ══════════
   왜 랭킹 API 인가: 홈의 누적 대화수는 '지금까지 얼마나'라 유량이 안 보인다.
   랭킹의 활동지수는 기간별 유량이고 과거 기간까지 준다(백필).

   지역이 넷이다 — JS 번들에서 찾았다. 홈만 봐서는 국내·일본밖에 안 보인다.
   각 지역의 백필 시작 주가 진출 시점과 맞아 데이터 신뢰도를 교차검증해 준다:
     KR 4월 1주 · JP 5월 4주 · TW 5월 4주 · GLOBAL 7월 1주(북미 진출)

   ⚠ 규모가 20배 넘게 벌어져(한국 61,589 vs 북미 2,868) 절대값 한 장으로는
     작은 지역이 바닥에 붙어 안 보인다. 그래서 '성장(첫 기간=100)' 보기를 같이 둔다.
   ⚠ tot 는 '상위 n명의 score 합'이지 서비스 전체가 아니다. 초기 주차는 n 이 27~46 이라
     50 이 찬 주차와 직접 비교하면 안 된다 → n<50 은 점을 비워 그리고 표에 '부분'이라 적는다. */
const TT_PAL = (typeof TREND!=="undefined" && TREND.colors && TREND.colors.length>=4)
  ? TREND.colors : ["#c4a7e7","#f6c177","#9ccfd8","#eb6f92"];
const TT_REG = [
  {code:"KR",     nm:"한국"},
  {code:"JP",     nm:"일본"},
  {code:"TW",     nm:"중화권"},
  {code:"GLOBAL", nm:"북미·글로벌"}
];
TT_REG.forEach((r,i)=>{ r.c = TT_PAL[i % TT_PAL.length]; });
const TT_FULL = 50;             // 랭킹 명단이 다 찬 기준. 이 아래는 '부분 집계'
let ttPeriod = "weekly";
let ttMode   = "abs";           // abs = 절대값 · idx = 성장(첫 기간=100)
let ttMA     = true;            // 4주 이동평균 겹쳐 그리기

function ttSite(code){
  if(typeof TOPTOON==="undefined") return null;
  return (TOPTOON.sites||[]).find(s=>s.code===code)||null;
}
function ttRows(code, kind){
  const s=ttSite(code); return (s && s.rank && s.rank[kind]) ? s.rank[kind] : [];
}
/* 비교 가능한 구간만 — 명단이 덜 찬 기간을 섞으면 '성장'이 집계 확대로 오염된다.
   판단(전주비·정점比)은 여기서만 한다. */
function ttFull(rows){ return rows.filter(r=>r.n>=TT_FULL); }
function ttLive(code){ return (ttRows(code,"rt")||[]).slice(-1)[0]||null; }

function renderToptoonKpi(){
  const box=document.getElementById("ttKpi"); if(!box) return;
  const cells=[];
  TT_REG.forEach(reg=>{
    const full=ttFull(ttRows(reg.code,"weekly"));
    if(!full.length) return;
    const last=full[full.length-1], prev=full.length>1?full[full.length-2]:null;
    const peak=full.reduce((a,b)=>b.tot>a.tot?b:a);
    const wow=prev?(last.tot/prev.tot-1)*100:null;
    const vsPk=peak.tot>0?(last.tot/peak.tot-1)*100:null;
    const atPeak=Math.abs(vsPk)<0.01;
    cells.push('<div class="sm-cell">'
      +'<div class="sm-h"><span class="dot" style="background:'+reg.c+'"></span>'+reg.nm
      +'<span class="src">'+last.lab+'</span>'
      +'<span class="v" style="color:'+reg.c+'">'+fmt0(last.tot)+'</span></div>'
      +'<div class="shop-kv">전주비 <b class="'+cls(wow)+'">'+(wow==null?"—":sign(wow,1)+"%")+'</b> · '
      +(atPeak?'<b>지금이 정점</b>':'정점('+peak.lab+') 대비 <b class="'+cls(vsPk)+'">'+sign(vsPk,1)+'%</b>')
      +' · 상위 '+last.n+'명 합</div></div>');
  });
  // 해외 비중 — '국내가 꺾인 자리를 해외가 메우나'가 이 사업의 핵심 질문이다.
  const kr=ttFull(ttRows("KR","weekly"));
  if(kr.length){
    const km={}; kr.forEach(r=>km[r.k]=r.tot);
    const ov={};
    TT_REG.filter(r=>r.code!=="KR").forEach(r=>ttFull(ttRows(r.code,"weekly"))
      .forEach(x=>{ if(km[x.k]) ov[x.k]=(ov[x.k]||0)+x.tot; }));
    const ks=Object.keys(ov).sort();
    if(ks.length){
      const f=ks[0], l=ks[ks.length-1];
      const rf=ov[f]/km[f]*100, rl=ov[l]/km[l]*100;
      const labOf=k=>{const r=TT_REG.map(g=>ttRows(g.code,"weekly").find(x=>x.k===k)).find(Boolean);
        return (r&&r.lab)||k;};
      cells.push('<div class="sm-cell">'
        +'<div class="sm-h"><span class="dot" style="background:var(--good)"></span>해외 / 한국'
        +'<span class="src">활동지수 비율</span>'
        +'<span class="v" style="color:var(--good)">'+rl.toFixed(0)+'%</span></div>'
        +'<div class="shop-kv">'+labOf(f)+' <b>'+rf.toFixed(0)+'%</b> → '+labOf(l)+' <b>'+rl.toFixed(0)+'%</b>'
        +' · 해외 3개 지역 합 기준</div></div>');
    }
  }
  // 실시간 — 롤링 스냅샷이라 '지금 얼마나 돌고 있나'만 본다(추세는 주간으로).
  const rt=TT_REG.map(r=>({r:r,x:ttLive(r.code)})).filter(o=>o.x);
  if(rt.length){
    cells.push('<div class="sm-cell">'
      +'<div class="sm-h"><span class="dot" style="background:var(--muted)"></span>실시간 활동지수'
      +'<span class="src">'+rt[0].x.d+' '+rt[0].x.t+'</span>'
      +'<span class="v">'+fmt0(rt.reduce((a,o)=>a+o.x.tot,0))+'</span></div>'
      +'<div class="shop-kv">'+rt.map(o=>o.r.nm+' <b>'+fmt0(o.x.tot)+'</b>').join(" · ")
      +' · 접속자 수가 아니라 최근 활동량</div></div>');
  }
  // 캐릭터 수 — 콘텐츠 투입은 이 사업의 비용이자 성장 동력이다.
  const cat=TT_REG.map(r=>({r:r,c:(ttSite(r.code)||{}).cat})).filter(o=>o.c);
  if(cat.length){
    cells.push('<div class="sm-cell">'
      +'<div class="sm-h"><span class="dot" style="background:var(--muted)"></span>서비스 캐릭터'
      +'<span class="src">현재 카탈로그</span>'
      +'<span class="v">'+fmt0(cat.reduce((a,o)=>a+o.c.n,0))+'</span></div>'
      +'<div class="shop-kv">'+cat.map(o=>o.r.nm+' <b>'+o.c.n+'</b>'
          // '작품' = 여러 캐릭터가 묶인 신형 포맷. 캐릭터 목록과 별도 API 라 놓치기 쉽다.
          // 규모는 작아도 한국 실시간 랭킹 1·2위라 어디에 있는지 적어 둔다.
          +(o.c.con?'<span class="th-sub">(작품 '+o.c.con+')</span>':"")).join(" · ")
      +'</div></div>');
  }
  box.innerHTML = cells.length?'<div class="sm-grid">'+cells.join("")+'</div>':"";
}

function drawToptoon(){
  const box=document.getElementById("ttChart"); if(!box) return;
  const lg=document.getElementById("ttLegend");
  const cs=getComputedStyle(document.documentElement);
  const gc=cs.getPropertyValue("--line").trim(), mut=cs.getPropertyValue("--muted").trim();
  // 기간 축은 네 지역의 합집합 — 늦게 시작한 지역은 앞이 비고, 그 빈칸이 곧 '진출 전'이다.
  const keys=[...new Set(TT_REG.flatMap(r=>ttRows(r.code,ttPeriod).map(x=>x.k)))].sort();
  if(!keys.length){ box.innerHTML='<div class="ov-empty">수집된 랭킹 데이터가 없습니다.</div>';
    if(lg) lg.innerHTML=""; return; }
  const raw=TT_REG.map(g=>{const m={}; ttRows(g.code,ttPeriod).forEach(x=>m[x.k]=x);
    return keys.map(k=>m[k]||null);});
  const M=keys.map((k,i)=>{const r=raw.map(a=>a[i]).find(Boolean); return (r&&r.lab)||k;});
  /* 성장 보기 — 각 지역의 '비교 가능한 첫 기간(n>=50)'을 100 으로. 진출 시점이 다른 지역을
     같은 출발선에 세워야 '누가 빠르게 크나'가 보인다. 절대 규모는 절대값 보기로. */
  const val=raw.map(arr=>{
    if(ttMode==="abs") return arr.map(r=>r?r.tot:null);
    const b=arr.find(r=>r&&r.n>=TT_FULL);
    return arr.map(r=>(r&&b&&b.tot>0)?r.tot/b.tot*100:null);
  });
  const nums=val.flat().filter(v=>v!=null);
  const max=Math.max.apply(null,nums.concat([1]));
  const W=1000,H=340,pad={l:62,r:110,t:14,b:44};
  const sx=i=>pad.l+(keys.length<2?0.5:i/(keys.length-1))*(W-pad.l-pad.r);
  const sy=v=>H-pad.b-(v/max)*(H-pad.t-pad.b);
  let s='<svg viewBox="0 0 '+W+' '+H+'" width="100%" height="'+H+'" font-family="inherit">';
  for(let g=0;g<=4;g++){ const v=max*g/4;
    s+='<line x1="'+pad.l+'" y1="'+sy(v)+'" x2="'+(W-pad.r)+'" y2="'+sy(v)+'" stroke="'+gc+'" stroke-width="1"/>';
    s+='<text x="'+(pad.l-8)+'" y="'+(sy(v)+4)+'" text-anchor="end" font-size="11" fill="'+mut+'">'
      +(ttMode==="abs"?fmt0(v):Math.round(v))+'</text>'; }
  const step=Math.max(1,Math.ceil(keys.length/14));
  M.forEach((m,i)=>{ if(i%step===0||i===M.length-1)
    s+='<text x="'+sx(i)+'" y="'+(H-pad.b+18)+'" text-anchor="middle" font-size="10.5" fill="'+mut+'">'+m+'</text>'; });
  val.forEach((arr,gi)=>{
    const c=TT_REG[gi].c;
    // 값이 없는 구간(진출 전)에서 선이 이어지면 안 된다 — 연속 구간마다 따로 그린다.
    let seg=[];
    const flush=()=>{ if(seg.length>1)
      s+='<polyline points="'+seg.map(p=>p[0].toFixed(1)+","+p[1].toFixed(1)).join(" ")
        +'" fill="none" stroke="'+c+'" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>';
      seg=[]; };
    arr.forEach((v,i)=>{ if(v==null){ flush(); return; } seg.push([sx(i),sy(v)]); });
    flush();
    // n<50(부분 집계)은 속 빈 점으로 — 같은 선 위에 있되 '이건 덜 찬 값'이라고 말해 준다.
    arr.forEach((v,i)=>{ if(v==null) return;
      const partial=!raw[gi][i]||raw[gi][i].n<TT_FULL;
      s+='<circle cx="'+sx(i).toFixed(1)+'" cy="'+sy(v).toFixed(1)+'" r="'+(partial?2.8:2.6)+'"'
        +(partial?' fill="none" stroke="'+c+'" stroke-width="1.6"':' fill="'+c+'"')+'/>'; });
    const li=arr.map((v,i)=>v==null?-1:i).filter(i=>i>=0).pop();
    if(li>=0) s+='<text x="'+(W-pad.r+8)+'" y="'+(sy(arr[li])+4)+'" font-size="11.5" font-weight="700" fill="'+c+'">'
      +TT_REG[gi].nm+'</text>';
  });
  /* 4주 이동평균 — 주간 원본은 흔들림이 커서(한국 주간변동 표준편차 11.8%p) 추세가 안 보인다.
     4주로 묶으면 4.5%p 로 떨어지고, 5주로 늘려도 4.3%p 라 더 나아지지 않는다 → 4주.
     대가는 전환점을 1주 늦게 알려주는 것이라, 원본 선과 **같이** 그린다(하나만 보면 오독한다). */
  if(ttPeriod==="weekly" && ttMA){
    val.forEach((arr,gi)=>{
      const c=TT_REG[gi].c, N=4, pts=[];
      for(let i=0;i<arr.length;i++){
        const win=arr.slice(Math.max(0,i-N+1),i+1).filter(v=>v!=null);
        if(win.length<N) continue;                 // 창이 다 안 차면 안 그린다(가짜 시작점 방지)
        pts.push([sx(i), sy(win.reduce((a,b)=>a+b,0)/win.length)]);
      }
      if(pts.length>1)
        s+='<polyline points="'+pts.map(p=>p[0].toFixed(1)+","+p[1].toFixed(1)).join(" ")
          +'" fill="none" stroke="'+c+'" stroke-width="3" stroke-dasharray="7 4" opacity="0.55"/>';
    });
  }
  s+='</svg>';
  box.innerHTML=s;
  attachChartTip(box,{W:W,H:H,pad:pad,n:keys.length,xOf:sx,html:i=>{
    const rows=TT_REG.map((g,gi)=>({g:g,r:raw[gi][i],p:i>0?raw[gi][i-1]:null,v:val[gi][i]}))
      .filter(o=>o.r).sort((a,b)=>b.r.tot-a.r.tot);
    if(!rows.length) return null;
    let out='<div class="tt-h">'+M[i]+'</div>';
    rows.forEach(o=>{
      const d=(o.p&&o.p.tot>0&&o.p.n>=TT_FULL&&o.r.n>=TT_FULL)?(o.r.tot/o.p.tot-1)*100:null;
      out+='<div class="tt-r"><span class="k"><span class="dot" style="background:'+o.g.c
        +';width:8px;height:8px;display:inline-block;border-radius:50%;margin-right:5px"></span>'+o.g.nm+'</span>'
        +'<span class="v">'+fmt0(o.r.tot)
        +(ttMode==="idx"&&o.v!=null?' <span style="color:var(--muted);font-size:10.5px">지수 '+Math.round(o.v)+'</span>':"")
        +(d==null?"":' <span class="'+cls(d)+'" style="font-size:10.5px">'+sign(d,0)+'%</span>')
        +(o.r.n<TT_FULL?' <span style="color:var(--muted);font-size:10.5px">부분 '+o.r.n+'명</span>':"")
        +'</span></div>';
    });
    const t0=rows[0].r.top&&rows[0].r.top[0];
    if(t0) out+='<div class="tt-r"><span class="k">'+rows[0].g.nm+' 1위</span><span class="v">'
      +t0.nm.slice(0,16)+' '+fmt0(t0.s)+'</span></div>';
    return out;
  }});
  if(lg) lg.innerHTML=TT_REG.map(g=>'<span class="lg"><i style="background:'+g.c+'"></i>'+g.nm+'</span>').join("")
    +'<span class="lg" style="opacity:.65"><i style="background:transparent;border:1.6px solid '+TT_REG[0].c+'"></i>속 빈 점 = 상위 50명 미만(부분 집계)</span>';
}

function renderToptoonRank(){
  const t=document.getElementById("ttRank"); if(!t) return;
  const parts=[];
  TT_REG.forEach(g=>{
    const rows=ttRows(g.code,"weekly"); if(!rows.length) return;
    const last=rows[rows.length-1], prev=rows.length>1?rows[rows.length-2]:null;
    const pr={}; if(prev) (prev.top||[]).forEach((x,i)=>{ pr[x.id]={rank:i+1, s:x.s}; });
    const top=(last.top||[]).slice(0,5);
    if(!top.length) return;
    top.forEach((x,i)=>{
      const p=pr[x.id];
      const mv=p?p.rank-(i+1):null;                    // +면 순위 상승
      const ds=(p&&p.s>0)?(x.s/p.s-1)*100:null;
      parts.push('<tr>'
        +(i===0?'<td rowspan="'+top.length+'" style="vertical-align:top;font-weight:800;color:'+g.c+'">'
            +g.nm+'<div class="th-sub">'+last.lab+'</div></td>':"")
        +'<td style="text-align:center;font-weight:800">'+(i+1)+'</td>'
        +'<td>'+x.nm+(x.kind==="content"?' <span class="th-sub">작품</span>':"")+'</td>'
        +'<td style="text-align:right;font-variant-numeric:tabular-nums">'+fmt0(x.s)+'</td>'
        +'<td style="text-align:right" class="'+(ds==null?"":cls(ds))+'">'+(ds==null?"—":sign(ds,0)+"%")+'</td>'
        // 직전 기간 목록에 없다 = '신규'가 아니라 '보관 범위(상위 20) 밖'이다.
        // 신규라고 적으면 21위에서 3위로 올라온 캐릭터가 새로 생긴 것처럼 읽힌다.
        +'<td style="text-align:center">'+(p
            ? (mv===0?'<span class="th-sub">—</span>':'<span class="'+cls(mv)+'">'+(mv>0?"▲":"▼")+Math.abs(mv)+'</span>')
            : '<span class="th-sub" title="직전 기간 상위 '+(((prev&&prev.top)||[]).length||20)+'위 밖 — 변동폭을 알 수 없습니다">권외↑</span>')
        +'</td></tr>');
    });
  });
  t.innerHTML = parts.length
    ? '<thead><tr><th>지역</th><th>순위</th><th>캐릭터</th><th style="text-align:right">활동지수</th>'
      +'<th style="text-align:right">전주비</th><th>순위변동</th></tr></thead><tbody>'+parts.join("")+'</tbody>'
    : '<tbody><tr><td class="th-sub">아직 순위 데이터가 없습니다.</td></tr></tbody>';
}

/* 월별 신규 캐릭터 투입 — 카탈로그의 startAt 에서 나온다(백필).
   활동지수가 '결과'라면 이건 '투입'이다. 둘이 같이 꺾이는지 보는 게 요점. */
function renderToptoonSupply(){
  const t=document.getElementById("ttSupply"); if(!t) return;
  const cats=TT_REG.map(g=>({g:g,c:(ttSite(g.code)||{}).cat})).filter(o=>o.c&&o.c.new);
  if(!cats.length){ t.innerHTML=""; return; }
  const months=[...new Set(cats.flatMap(o=>Object.keys(o.c.new)))].sort();
  const head='<thead><tr><th>월</th>'+cats.map(o=>'<th style="text-align:right">'+o.g.nm+'</th>').join("")
    +'<th style="text-align:right">합계</th></tr></thead>';
  const body=months.map(m=>{
    const vs=cats.map(o=>o.c.new[m]||0);
    return '<tr><td style="font-weight:700">'+m.replace("-",".")+'</td>'
      +vs.map(v=>'<td style="text-align:right;font-variant-numeric:tabular-nums">'+(v||'<span class="th-sub">—</span>')+'</td>').join("")
      +'<td style="text-align:right;font-weight:700">'+vs.reduce((a,b)=>a+b,0)+'</td></tr>';
  }).join("");
  t.innerHTML=head+'<tbody>'+body+'</tbody>';
}

function renderToptoonTable(){
  const t=document.getElementById("ttTable"); if(!t) return;
  const keys=[...new Set(TT_REG.flatMap(r=>ttRows(r.code,ttPeriod).map(x=>x.k)))].sort().reverse();
  const users={}; (ttRows("KR","users")||[]).forEach(u=>{ users[u.k]=u; });
  const body=keys.map(k=>{
    const cellFor=g=>{
      const arr=ttRows(g.code,ttPeriod), i=arr.findIndex(x=>x.k===k);
      if(i<0) return '<td class="th-sub" style="text-align:right">—</td>';
      const r=arr[i], p=i>0?arr[i-1]:null;
      const d=(p&&p.tot>0&&p.n>=TT_FULL&&r.n>=TT_FULL)?(r.tot/p.tot-1)*100:null;
      return '<td style="text-align:right;font-variant-numeric:tabular-nums">'+fmt0(r.tot)
        +(r.n<TT_FULL?' <span class="th-sub">부분'+r.n+'</span>':"")
        +(d==null?"":' <span class="'+cls(d)+'" style="font-size:11px">'+sign(d,1)+'%</span>')+'</td>';
    };
    const lab=(TT_REG.map(g=>ttRows(g.code,ttPeriod).find(x=>x.k===k)).find(Boolean)||{}).lab||k;
    const u=(ttPeriod==="weekly")?users[k]:null;
    return '<tr><td style="font-weight:700">'+lab+'</td>'+TT_REG.map(cellFor).join("")
      +'<td style="text-align:right" class="th-sub">'+(u?u.new+"/"+u.n:"—")+'</td></tr>';
  }).join("");
  t.innerHTML='<thead><tr><th>기간</th>'
    +TT_REG.map(g=>'<th style="text-align:right">'+g.nm+'</th>').join("")
    +'<th style="text-align:right" title="한국 유저 주간 랭킹 30명 중 신규 진입 수 — 이용자 회전율">신규유저</th>'
    +'</tr></thead><tbody>'+body+'</tbody>';
}

/* 월별 추이 — 반드시 '주평균' 으로 낸다 (2026-09-01)
   달마다 주 수가 다르다(4월 5주 · 5월 4주 · 7월 5주 · 8월 4주). 단순 합계로 MoM 을 내면
   7월(5주) → 8월(4주) 이 -16% 로 찍히는데, 그건 주가 하나 적어서지 수요가 준 게 아니다.
   주평균으로 내면 같은 구간이 +5% 다. 여기가 이 표의 존재 이유다.

   ⚠ 분모는 **그 달의 전체 주 수**로 통일한다. 지역마다 자기가 가진 주로 나누면
     런칭 달이 부풀어 오른다 — 일본은 5월에 1주(5월 4주차)만 운영했는데 그 1주를
     '주평균 8,432' 으로 잡으면 한 달 내내 그 페이스였던 것처럼 되고, 5월 MoM 이
     +49% 가 아니라 +70% 로 찍힌다. 실제로는 3주간 서비스가 없었으므로 0 이 맞다.
   주가 모자란 칸은 이유를 나눠 표시한다:
     · 앞이 비면  = 그 달에 런칭 (0 으로 채우는 게 맞다)
     · 뒤가 비면  = 집계 지연 (북미는 한 주 늦게 공개된다) — 그만큼 과소평가된다 */
function ttMonthly(){
  const mon={};                        // {월: Set(주키)}  — 그 달에 존재하는 주(전 지역 합집합)
  const val={};                        // {월: {code: {sum, ks:Set}}}
  TT_REG.forEach(g=>{
    ttRows(g.code,"weekly").forEach(w=>{
      const m=/^(\d+)월/.exec(w.lab||""); if(!m) return;
      const k=+m[1];
      (mon[k]=mon[k]||new Set()).add(w.k);
      const c=((val[k]=val[k]||{})[g.code]=(val[k]||{})[g.code]||{sum:0, ks:new Set()});
      c.sum+=w.tot; c.ks.add(w.k);
    });
  });
  // 지역별 전체 관측 구간 — '앞이 빈 것(런칭)' 과 '뒤가 빈 것(지연)' 을 가르는 기준
  const span={};
  TT_REG.forEach(g=>{
    const ks=ttRows(g.code,"weekly").map(w=>w.k).sort();
    if(ks.length) span[g.code]={first:ks[0], last:ks[ks.length-1]};
  });
  return Object.keys(mon).map(Number).sort((a,b)=>a-b).map(k=>{
    const weeks=[...mon[k]].sort(), n=weeks.length;
    const per={}, note={};
    let tot=0;
    TT_REG.forEach(g=>{
      const c=(val[k]||{})[g.code];
      if(!c){ per[g.code]=null; return; }
      per[g.code]=c.sum/n;             // ← 분모는 언제나 그 달의 전체 주 수
      tot+=per[g.code];
      if(c.ks.size<n){
        const sp=span[g.code]||{};
        const missTail=weeks.some(w=>w>sp.last && !c.ks.has(w));
        note[g.code]= missTail ? "지연" : "런칭";   // 뒤가 비면 집계 지연, 앞이 비면 그 달 런칭
      }
    });
    return {m:k, per:per, note:note, n:n, weeks:weeks, tot:tot};
  });
}

function renderToptoonMonth(){
  const t=document.getElementById("ttMonth"); if(!t) return;
  const rows=ttMonthly();
  if(!rows.length){ t.innerHTML=""; return; }
  const price=ttPrice();
  const body=rows.map((r,i)=>{
    const p=i>0?rows[i-1]:null;
    const mom=(p&&p.tot>0)?(r.tot/p.tot-1)*100:null;
    const cells=TT_REG.map(g=>{
      const v=r.per[g.code], pv=p?p.per[g.code]:null;
      if(v==null) return '<td class="th-sub" style="text-align:right">—</td>';
      const d=(pv!=null&&pv>0)?(v/pv-1)*100:null;
      // 런칭 달은 앞이 비어 있어 낮게 나오는 게 맞고, '지연'은 그만큼 과소평가라 뜻이 다르다
      const nt=r.note[g.code];
      return '<td style="text-align:right;font-variant-numeric:tabular-nums">'+fmt0(v)
        +(nt?' <span class="th-sub" title="'+(nt==="런칭"
            ?"이 달에 서비스를 시작해 앞 주가 비어 있습니다 — 0 으로 채워 평균냈습니다"
            :"이 지역은 최신 주 집계가 늦게 올라옵니다 — 그만큼 과소평가된 값입니다")
          +'">'+nt+'</span>':"")
        +(d==null?"":' <span class="'+cls(d)+'" style="font-size:11px">'+sign(d,0)+'%</span>')+'</td>';
    }).join("");
    return '<tr><td style="font-weight:700">'+r.m+'월<span class="th-sub"> '+r.n+'주</span></td>'
      +cells
      +'<td style="text-align:right;font-weight:800;font-variant-numeric:tabular-nums">'+fmt0(r.tot)+'</td>'
      +'<td style="text-align:right;font-weight:800" class="'+(mom==null?"":cls(mom))+'">'
        +(mom==null?"—":sign(mom,0)+"%")+'</td>'
      +'<td style="text-align:right;font-variant-numeric:tabular-nums">'
        +(r.tot*4.33*price/1e8).toFixed(1)+'억</td></tr>';
  }).join("");
  t.innerHTML='<thead><tr><th>월</th>'
    +TT_REG.map(g=>'<th style="text-align:right">'+g.nm+'</th>').join("")
    +'<th style="text-align:right">합계<div class="th-sub">주평균</div></th>'
    +'<th style="text-align:right">MoM</th>'
    +'<th style="text-align:right">월매출<div class="th-sub">추정</div></th></tr></thead><tbody>'+body+'</tbody>';
  const n=document.getElementById("ttMonthNote");
  if(n) n.innerHTML='<b>주평균 기준</b>입니다 — 달마다 주 수가 달라(4·7월은 5주) 단순 합계로 MoM 을 내면 '
    +'7월→8월이 −16%로 잘못 찍힙니다. 주평균으로는 +5%입니다. · '
    +'매출 = 주평균 × 4.33주 × 방당 '+fmt0(price)+'원 · '
    +'지역마다 마지막 주 공개가 늦을 수 있어(북미) <b>각 지역이 가진 주로만 평균</b>냅니다.';
}

/* 방당 매출 단가 — 공시가 나올 때마다 재보정해야 하므로 화면에서 바꿀 수 있게 둔다.
   기본 1,832원 = 사용자가 준 2Q26 AI 매출 15억 ÷ 2Q 대화방 818,956개. */
function ttPrice(){
  const el=document.getElementById("ttPrice");
  const v=el?parseFloat(el.value):NaN;
  return (isFinite(v)&&v>0)?v:1832;
}

function renderToptoon(){
  const sec=document.querySelector('section[data-view="toptoon"]'); if(!sec) return;
  const kpi=document.getElementById("ttKpi");
  if(typeof TOPTOON==="undefined"||!TOPTOON.sites){
    if(kpi) kpi.innerHTML='<div class="ov-empty">탑툰챗 데이터가 아직 없습니다.</div>'; return;
  }
  renderToptoonKpi(); drawToptoon(); renderToptoonMonth(); renderToptoonRank();
  renderToptoonSupply(); renderToptoonTable();
  const n=document.getElementById("ttNote");
  if(n) n.innerHTML=TOPTOON.asOf+' 기준 · 활동지수 = 사이트 랭킹 API 의 score 합(상위 50명) — '
    +'<b>서비스 전체가 아니라 상위 구간</b>입니다. '
    +TT_REG.map(g=>g.nm+' '+ttRows(g.code,"weekly").length+'주').join(" · ")+' 수집 · '
    +'백필 시작 주가 각 지역 진출 시점과 일치합니다(북미 7월 1주차) · '
    +'누적 대화수·캐릭터별 추이는 <b>트렌드 비교</b> 탭에도 있습니다.';
}

(function bindToptoon(){
  const on=(id,fn)=>{ const el=document.getElementById(id); if(!el) return;
    el.addEventListener("click",e=>{ const b=e.target.closest("button"); if(!b) return;
      [...el.querySelectorAll("button")].forEach(x=>x.classList.toggle("active",x===b)); fn(b); }); };
  on("ttPeriodSeg", b=>{ ttPeriod=b.dataset.p; drawToptoon(); renderToptoonTable(); });
  on("ttModeSeg",   b=>{ ttMode=b.dataset.m; drawToptoon(); });
  on("ttMASeg",     b=>{ ttMA=b.dataset.ma==="on"; drawToptoon(); });
  const pe=document.getElementById("ttPrice");
  if(pe) pe.addEventListener("input",()=>renderToptoonMonth());
  window.addEventListener("resize",()=>{
    const s=document.querySelector('section[data-view="toptoon"]');
    if(s&&s.classList.contains("active")) drawToptoon();
  });
})();

/* 개봉 예정작 — 수집이 시작되기 전에도 D-day 를 보여주려고 손으로 적어둔다 */
const MOVIE_UPCOMING=[
  // title 은 KOBIS 표기와 정확히 같아야 한다 — 개봉 후 박스오피스에 같은 이름으로
  // 잡히는데, 다르면 '예정작'과 '집계작'이 따로 떠서 두 줄이 된다.
  {stock:"SAMG엔터", title:"사랑의 하츄핑: 고래보석의 전설", open:"2026-08-05", prev:1240000},
];

/* ==== 실시간 예매 ====
   개봉 전에는 박스오피스가 아무것도 주지 않는다(순위에 없으니까).
   그 구간에서 유일하게 움직이는 숫자가 예매다 — 예매관객은 개봉일 스코어의 선행 지표고,
   누적관객은 시사회 실적이다. 매 실행마다 한 점씩 쌓이므로 증분(전일 대비)이 핵심.
   1편 기준선: 개봉 4일 전 시사회 누적 30,553명 → 개봉일 107,156명 → 최종 121만명. */
function renderBooking(){
  const el=document.getElementById("movieBooking"); if(!el) return;
  const B=((typeof MOVIE!=="undefined")&&MOVIE.booking)||{};
  const names=Object.keys(B).filter(n=>(B[n]||[]).length);
  if(!names.length){ el.innerHTML=""; return; }
  const up=Object.fromEntries((MOVIE_UPCOMING||[]).map(x=>[x.title,x]));
  const MV=(typeof MOVIE!=="undefined")?MOVIE:{};
  const D=s=>new Date(+s.slice(0,4),+s.slice(4,6)-1,+s.slice(6,8));
  // 개봉 판정 — 박스오피스 실측이 잡혔고 개봉일이 지났으면 '개봉 후'로 본다.
  const isOpen=nm=>{const bo=(MV.movies||{})[nm];const u2=up[nm];return !!(bo&&bo.days&&bo.days.length)&&(!u2||new Date(u2.open)<=new Date());};
  const anyOpened=names.some(isOpen);
  let h=`<div class="sub-h">${anyOpened?"개봉 실적 · 실시간 예매":"실시간 예매"}</div>`;
  names.forEach(nm=>{
    const pts=B[nm], last=pts[pts.length-1], prev=pts.length>1?pts[pts.length-2]:null;
    const u=up[nm];
    const opened=isOpen(nm);
    const bo=(MV.movies||{})[nm], boDays=(bo&&bo.days)||[];
    const bl=boDays[boDays.length-1]||null, bp=boDays.length>1?boDays[boDays.length-2]:null;
    const openDate=(u&&u.open)||(bo&&bo.openDt)||null;
    const dday=openDate? Math.ceil((new Date(openDate)-new Date(last.d))/864e5) : null;
    // 증분은 점이 2개 이상 쌓여야 나온다. 첫날은 '수집 시작'으로 두고 빈 값을 보여준다.
    // 예매율·예매관객은 '전일 같은 시각'과 견준다.
    //   KOBIS 실시간 예매는 남은 상영분이라 하루가 갈수록 줄어든다
    //   (2026-08-08 실측: 05:38 145,190명 → 12:54 90,562명).
    //   전날 마지막 스냅샷과 빼면 시간대 차이를 재는 꼴이라 증감이 뒤집힌다.
    //   수집기가 archive 에서 전일 동시각 점을 찾아 pRate·pBook·pAt 로 실어 준다.
    //   누적관객(acc)은 하루 한 번 확정치라 종전대로 전일 대비다.
    const SAME={rate:"pRate", book:"pBook"};
    const delta=(k)=>{
      const sameKey=SAME[k], hasSame=sameKey && last[sameKey]!=null;
      const base=hasSame? last[sameKey] : (prev? prev[k] : null);
      if(base==null) return `전일 대비는 내일부터`;
      const dv=last[k]-base, unit=(k==="rate"?"%p":"명");
      const lab=hasSame? `전일 ${last.pAt} 대비` : "전일비";
      return `<span class="${cls(dv)}">${sign(dv,k==="rate"?1:0)}${unit} ${lab}</span>`;
    };
    const bdelta=(k)=> bp? `<span class="${cls(bl[k]-bp[k])}">${sign(bl[k]-bp[k],0)}명 전일비</span>` : ``;
    if(opened){
      // 개봉 후 — 헤드라인을 박스오피스 실측(당일 관객·누적·상영관)으로. 예매율은 다음 날 페이스의 선행지표로 보조.
      const dN=bl?Math.round((D(bl.d)-new Date(openDate))/864e5):null;
      const md=bl?bl.d.slice(4,6)+"/"+bl.d.slice(6,8):"";
      h+=`<div class="kpis">
      <div class="kpi"><div class="k">${nm}</div>
        <div class="v">${dN==null?"개봉":(dN===0?"개봉일":"개봉 D+"+dN)}</div>
        <div class="d">${openDate} 개봉</div></div>
      <div class="kpi"><div class="k">박스오피스 순위<span class="th-sub">${md} 확정</span></div>
        <div class="v">${bl&&bl.rank?bl.rank+"<small>위</small>":"—"}</div>
        <div class="d">전국 일별</div></div>
      <div class="kpi"><div class="k">당일 관객<span class="th-sub">${md}</span></div>
        <div class="v">${bl&&bl.audi!=null?fmt0(bl.audi):"—"}<small>명</small></div>
        <div class="d">${bdelta("audi")}</div></div>
      <div class="kpi"><div class="k">누적 관객</div>
        <div class="v">${bl?fmt0(bl.acc):"—"}<small>명</small></div>
        <div class="d">${bl&&bl.scrn?fmt0(bl.scrn)+"개 상영관":""}</div></div>
      <div class="kpi"><div class="k">실시간 예매율<span class="th-sub">오늘</span></div>
        <div class="v">${fmt(last.rate,1)}<small>%</small></div>
        <div class="d">${delta("rate")}</div></div>
      <div class="kpi"><div class="k">실시간 예매관객<span class="th-sub">오늘</span></div>
        <div class="v">${fmt0(last.book)}<small>명</small></div>
        <div class="d">${delta("book")}</div></div>
    </div>`;
    } else {
      h+=`<div class="kpis">
      <div class="kpi"><div class="k">${nm}</div>
        <div class="v">${dday!=null?(dday>0?"D-"+dday:"개봉"):"—"}</div>
        <div class="d">${openDate?openDate+" 개봉":""}</div></div>
      <div class="kpi"><div class="k">예매 순위</div>
        <div class="v">${last.rank?last.rank+"<small>위</small>":"—"}</div>
        <div class="d">${prev&&prev.rank&&last.rank
            ? `<span class="${cls(prev.rank-last.rank)}">${prev.rank===last.rank?"변동 없음":(prev.rank>last.rank?`${prev.rank-last.rank}계단 상승`:`${last.rank-prev.rank}계단 하락`)}</span>`
            : "전체 개봉작 중"}</div></div>
      <div class="kpi"><div class="k">예매율</div>
        <div class="v">${fmt(last.rate,1)}<small>%</small></div>
        <div class="d">${delta("rate")}</div></div>
      <div class="kpi"><div class="k">예매관객</div>
        <div class="v">${fmt0(last.book)}<small>명</small></div>
        <div class="d">${delta("book")}</div></div>
      <div class="kpi"><div class="k">누적관객 (시사회)</div>
        <div class="v">${fmt0(last.acc)}<small>명</small></div>
        <div class="d">${delta("acc")}</div></div>
    </div>`;
    }
    /* 1편 동시점 앵커 — 예매 이력은 KOBIS 가 안 남겨서 당시 보도 수치에 대고 잰다 */
    const ref=(typeof MOVIE_BOOKING_REF!=="undefined")&&MOVIE_BOOKING_REF[nm];
    const an=ref&&ref.anchors&&ref.anchors[0];
    if(an&&last.book){
      const pctOf=(last.book/an.book*100);
      h+=`<p class="note" style="margin:8px 0 0">↳ ${ref.prev} 같은 앵커 D${an.x>=0?"+":""}${an.x}:
        예매 <b>${fmt0(an.book)}명</b> · ${an.rate}% <small>(${an.src})</small>
        — 현재 D${dday!=null?-dday:"?"} 예매가 그 <b class="${pctOf>=100?"up":""}">${pctOf.toFixed(0)}%</b> 수준</p>`;
    }
    if(pts.length>1){
      h+=`<div class="tbl-wrap" style="margin-top:10px"><table class="mini-tbl"><thead><tr>
        <th class="l">날짜</th><th>일차</th><th>순위</th><th>예매율</th><th>예매관객</th><th>증분</th>
        <th>1편 예매율<span class="th-sub">같은 일차</span></th>
        <th>1편 예매관객<span class="th-sub">같은 일차 · 대비</span></th>
        <th>누적관객</th></tr></thead><tbody>`
        +pts.slice().reverse().map((p,i,ar)=>{
          const q=ar[i+1];   // 역순이라 다음 원소가 전일
          // 1편 앵커는 날짜가 아니라 일차(D-n)로 물린다. 개봉일이 2년 차이라 날짜로는 못 맞춘다.
          const dd=p.open?Math.round((new Date(p.d)-new Date(p.open))/864e5):null;
          const a=(ref&&ref.anchors||[]).find(x=>x.x===dd);
          const cmp=a&&p.book?p.book/a.book*100:null;
          return `<tr><td class="l">${p.d.slice(5)}</td>
            <td>${dd==null?"—":`D${dd>=0?"+":""}${dd}`}</td>
            <td>${p.rank?p.rank+"위":"—"}</td><td>${fmt(p.rate,1)}%</td>
            <td>${fmt0(p.book)}</td>
            <td>${q?`<span class="${cls(p.book-q.book)}">${sign(p.book-q.book,0)}</span>`:"—"}</td>
            <td>${a?`${fmt(a.rate,1)}%`:`<span style="color:var(--muted2)">—</span>`}</td>
            <td>${a?`${fmt0(a.book)}<span class="th-sub ${cmp>=100?"up":"down"}">${cmp.toFixed(0)}%</span>`
                   :`<span style="color:var(--muted2)">—</span>`}</td>
            <td>${fmt0(p.acc)}</td></tr>`;}).join("")
        +`</tbody></table></div>`;
    }
  });
  h+=`<p class="note">KOBIS ${anyOpened?"박스오피스 <b>전일 확정치</b> + 예매 <b>실시간</b>":"실시간 예매 · <b>매시간 갱신</b>"}(기준 ${(typeof MOVIE!=="undefined"&&MOVIE.asOf)||"—"}).
      ${anyOpened?"개봉 후엔 당일 관객·누적이 흥행의 실측이고, 예매율은 다음 날 페이스의 선행지표입니다":"개봉 전 유일한 실시간 지표입니다"}. 예매수·누적은 하루 종일 변하므로 위 값은 그 시각의 스냅샷입니다.
      1편 기준선: 개봉 4일 전 시사회 누적 30,553명 → 개봉일 107,156명 → 최종 1,212,652명.</p>`;
  el.innerHTML=h;
  renderScreens();
}

/* ==== 스크린 확보 현황 ====
   개봉 전 가장 중요한 선행 지표 — 1편은 개봉일 스크린이 146 -> 1,065 로 뛰며
   흥행이 결정됐다. 예매 패널 안에 묻혀 있던 걸 독립 섹션으로 꺼냈다.
   범위: CGV·롯데·메가 3사는 체인 안에서 전수(상영 걸린 지점 전부),
        독립·소형관(전국 스크린의 ~10%)은 예매 API 가 없어 미포함. */
function renderScreens(){
  const el=document.getElementById("movieScreens"); if(!el) return;
  const SC=(typeof MOVIE_SCREENS!=="undefined")?MOVIE_SCREENS:null;
  if(!SC||!Object.keys(SC.series||{}).length){ el.innerHTML=""; return; }
  const norm=t=>t.replace(/[\s:\-·]+/g,"");
  const todayISO=TODAY_C;
  const ups=Object.fromEntries((MOVIE_UPCOMING||[]).map(x=>[norm(x.title),x]));
  const MV=(typeof MOVIE!=="undefined")?MOVIE:{};
  // 작품별로 (상영일 -> 스냅샷들) 을 묶는다. 과거 상영일도 들고 간다 —
  // 기준 판매율(예측의 근거)과 전국 보정계수가 거기서 나온다.
  const byTitle={};
  Object.entries(SC.series).forEach(([k,ser])=>{
    const [t,play]=k.split("|");
    (byTitle[t]=byTitle[t]||[]).push({play, ser});
  });
  let h="";
  Object.entries(byTitle).forEach(([title,arr])=>{
    arr.sort((a,b)=>a.play.localeCompare(b.play));
    if(Math.max(...arr.map(x=>x.ser[x.ser.length-1].screens))<10) return;   // 소규모(재개봉 특별판) 생략
    const u=ups[norm(title)];
    const op=u?u.open.replace(/-/g,""):null;
    const ddOf=p=>op?Math.round((new Date(`${p.slice(0,4)}-${p.slice(4,6)}-${p.slice(6,8)}`)-new Date(u.open))/864e5):null;
    const dn=p=>{const dd=ddOf(p); return dd==null?"":`<span class="ye">D${dd>=0?"+":""}${dd}</span>`;};

    /* ── 예측 재료 ────────────────────────────────────────
       기준 판매율: 이미 지난(또는 오늘) 상영일이 실제로 채운 비율.
         규모가 비슷한 날을 먼저 고른다 — 시사회(수십 관)와 와이드 릴리즈(수백 관)는
         좌석이 차는 양상이 전혀 다르다. 규모가 크게 다르면 화면에 경고를 단다.
       전국 보정: 같은 상영일의 KOBIS 실측 관객 ÷ 3사 예매좌석 — 독립·소형관과
         현장 구매를 한 계수로 흡수한다. 실측 쌍이 생겨야 곱한다. */
    /* '그 날의 값'은 최신 스냅샷이 아니라 관측된 최댓값이다.
       오늘 날짜는 끝난 회차가 스케줄에서 빠진다 — 8/2 가 08:43 에 10,887석/8,617 이었는데
       09:52 엔 10,503석/8,570 으로 줄었다. 취소가 아니라 오전 회차가 사라진 것이다.
       최신값만 보면 저녁엔 '남은 회차'만 남아 판매율이 95% 처럼 부풀고,
       그게 기준 판매율로 쓰이면 뒤따르는 예상치가 통째로 틀어진다.
       그래서 수집일별로 묶어 최댓값을 그 날의 관측치로 삼는다.
       미래 날짜는 회차가 늘기만 하므로 최댓값 = 최신값이라 영향이 없다. */
    const FMAX=["screens","shows","sites","seatTot","seatSold"];
    const dayRoll=ser=>{
      const m=new Map();
      (ser||[]).filter(p=>p.seatTot>0).forEach(p=>{
        const d=p.t.slice(0,10), c=m.get(d);
        if(!c){ m.set(d,{...p}); return; }
        if((p.seatTot||0)>(c.seatTot||0)) c.by=p.by;
        FMAX.forEach(k=>c[k]=Math.max(c[k]||0,p[k]||0));
        c.t=p.t;
      });
      return [...m.values()];
    };
    /* 최댓값 규칙은 '지나간 회차가 사라지는' 날에만 옳다 = 오늘과 그 이전.
       아직 안 온 날짜는 회차가 사라지지 않으므로 최신값이 맞다 —
       최댓값을 쓰면 취소나 편성 변경으로 예매가 줄어든 걸 못 보고 옛 고점에 붙잡힌다
       (실제로 8/7 이 3,602 -> 3,350 으로 줄었는데 3,602 로 표시됐다). */
    const peakSer=(ser,play)=>{
      if(!ser||!ser.length) return {};
      const fut=play&&play>todayISO;
      if(fut){ const f=ser.filter(p=>p.seatTot>0); return f.length?f[f.length-1]:ser[ser.length-1]; }
      const d=dayRoll(ser); return d.length?d[d.length-1]:ser[ser.length-1];
    };
    const prevSer=(ser,play)=>{
      if(play&&play>todayISO){
        const f=(ser||[]).filter(p=>p.seatTot>0);
        const cur=f[f.length-1];
        const p=cur?[...f].reverse().find(q=>q.t.slice(0,10)!==cur.t.slice(0,10)):null;
        return p||null;
      }
      const d=dayRoll(ser); return d.length>1?d[d.length-2]:null;
    };
    const lastOf=x=>peakSer(x.ser,x.play);
    /* 체인마다 스케줄을 여는 시점이 다르다 — 메가박스는 3일치만 연다.
       그래서 먼 날짜는 CGV·롯데만 잡혀 '배정이 줄어든 것처럼' 보인다.
       실제로 8/5 621관(3사) -> 8/6 408관(2사)인데, 이건 감축이 아니라 미오픈이다.
       어느 체인이 빠졌는지 표시해서 그 착시를 막는다. */
    // '안 여는 것'과 '안 하는 것'을 가른다: 스케줄은 앞으로만 열리므로,
    // 그 체인이 더 이른 날짜엔 걸려 있는데 이 날짜엔 없다면 = 아직 안 연 것.
    // (8/2 시사회에 메가박스가 없는 건 미오픈이 아니라 그냥 안 하는 것이다.)
    const chDates={};
    arr.forEach(x=>Object.keys(lastOf(x).by||{}).forEach(c=>{
      (chDates[c]=chDates[c]||[]).push(x.play);}));
    /* 체인별 지평선(수집기의 chainHz) = 그 체인이 예매를 열어 둔 마지막 날.
       이게 있으면 '더 이른 날엔 있는데 여기 없다'는 추측 대신 정확히 가른다.
       없으면(옛 데이터) 예전 추측 방식으로 떨어진다. */
    const CHZ=SC.chainHz
      ? (SC.chainHz[title]||(Object.entries(SC.chainHz).find(([k])=>norm(k)===norm(title))||[])[1]||null)
      : null;
    const missOf=(s,play)=>Object.keys(chDates).filter(c=>
      !(s.by&&s.by[c]) &&
      ((CHZ&&CHZ[c]) ? play>CHZ[c] : chDates[c].some(d2=>d2<play)));
    /* 편성 지평선 — 극장은 예매 달력을 2~3주 열어 두지만 편성은 그보다 훨씬 앞서 끝난다.
       (8/2 현재 CGV 달력은 8/18 까지 열려 있는데 하츄핑2 는 8/10 까지만 걸려 있다.)
       그래서 뒤쪽 날짜는 스크린·좌석이 실제보다 적게 잡히고, 그대로 두면
       621->408->318->207 이 '개봉하자마자 관을 뺏기는 영화'처럼 읽힌다.
       지평선 근처(2일 이내) 날짜는 '편성 중'으로 표시해 그 오독을 막는다. */
    /* ⚠ 오늘·과거는 '편성 중'이 될 수 없다 — 이미 상영표가 확정된 날이다.
         이 가드가 없어서 지평선이 앞으로 당겨진 날(수집 버그) 오늘 날짜에도 딱지가 붙었다. */
    const HZ=SC.horizon||null;
    const fillingOf=play=>{ if(!HZ||play>HZ||play<=todayISO) return false;
      const g=(a,b)=>(new Date(`${b.slice(0,4)}-${b.slice(4,6)}-${b.slice(6,8)}`)
                     -new Date(`${a.slice(0,4)}-${a.slice(4,6)}-${a.slice(6,8)}`))/864e5;
      return g(play,HZ)<=2; };
    /* 지평선 '너머' — 편성이 아직 시작도 안 된 날. 그래도 값이 잡히는 건
       극장 한두 곳이 먼저 연 파편이다(8/4 실측: 8/17 은 CGV 왕십리 한 곳뿐인데 20관).
       '편성 중'(거의 다 찬 날)과 섞으면 안 된다 — 이건 아예 안 채워진 날이다. */
    const preOf=play=>!!HZ&&play>HZ&&play>todayISO;
    /* 1편의 같은 일차 실측(당일·누적) — 예상치를 못 내는 구간에서 비교 기준이 된다.
       같은 시리즈·같은 여름 성수기라 페이스를 견주기에 이만한 게 없다. */
    const refDay={}, refAcc={}, refScrn={};
    (()=>{
      const other=Object.entries(MV.movies||{}).find(([t])=>norm(t)!==norm(title));
      if(!other) return;
      const oOp=(other[1].openDt||"").replace(/-/g,""); if(!oOp) return;
      const d0=new Date(`${oOp.slice(0,4)}-${oOp.slice(4,6)}-${oOp.slice(6,8)}`);
      (other[1].days||[]).forEach(p=>{
        const dd=Math.round((new Date(`${p.d.slice(0,4)}-${p.d.slice(4,6)}-${p.d.slice(6,8)}`)-d0)/864e5);
        if(p.audi!=null) refDay[dd]=p.audi;
        if(p.acc!=null) refAcc[dd]=p.acc;
        // 1편의 같은 일차 스크린수 — 우리 스크린 옆에 나란히 놓으면 '관을 얼마나 덜/더 받았나'가
        // 바로 보인다. 관객 상한을 정하는 게 결국 이 숫자다.
        if(p.scrn!=null) refScrn[dd]=p.scrn;});
    })();
    // 오늘 상영분도 기준에 넣는다 — 개봉 전이라 '완료된' 날이 아직 없다.
    const done=arr.filter(x=>x.play<=todayISO&&lastOf(x).seatTot>0);
    /* 기준일은 '같은 성격의 날'이어야 한다. 시사회(개봉 전)는 소수 관에 팬만 오니
       거의 매진되지만, 본상영은 전혀 다르게 찬다 — 규모가 우연히 비슷해도 섞으면 안 된다.
       그래서 개봉 전/후를 가르고, 그 안에서 스크린 규모가 가장 가까운 날을 고른다. */
    const sideOf=play=>{ const d=ddOf(play); return d==null?0:(d<0?-1:1); };
    const pickBench=(target,play)=>{
      let cands=done.filter(x=>sideOf(x.play)===sideOf(play));
      // 완료된 날(오늘 이전)이 있으면 오늘(아직 채워지는 중)은 기준에서 뺀다.
      // 오늘 자신을 기준으로 삼으면 판매율이 '현재 진행값'이라 기준선이 확보선에 붙어버린다.
      const fin=cands.filter(x=>x.play<todayISO);
      if(fin.length) cands=fin;
      if(!cands.length) return null;
      return cands.slice().sort((a,b)=>{
        const ra=Math.abs(Math.log((lastOf(a).screens||1)/(target||1)));
        const rb=Math.abs(Math.log((lastOf(b).screens||1)/(target||1)));
        return (ra-rb) || b.play.localeCompare(a.play);
      })[0];
    };
    /* natF 는 '3사 예매좌석'을 분모로 역산하는데, 지나간 날은 끝난 회차가 스케줄에서
       빠져 예매좌석이 껍데기만 남는다(8/6 실측: 3사 299관·6,317석인데 KOBIS 는 801관·43,744명).
       그런 오염된 날로 역산하면 natF 가 6.9→상한 2.5 로 튀어 예측이 통째로 2배가 된다.
       그래서 '3사가 그날 스크린을 충분히(70%+) 잡은' 온전한 날로만 역산한다(8/5: 91% → 1.31). */
    const natCand=x=>{ const s=lastOf(x);
      const kob=Object.values(MV.movies||{}).flatMap(m=>m.days||[]).find(d2=>d2.d===x.play);
      return (kob&&s.seatSold>0&&kob.scrn>0)?{s,kob,cov:(s.screens||0)/kob.scrn}:null; };
    const setNat=c=>{ natF=Math.min(2.5,Math.max(1,c.kob.audi/c.s.seatSold));
      natSrc=`${c.kob.d.slice(4,6)}/${c.kob.d.slice(6,8)} KOBIS ${fmt0(c.kob.audi)}명 ÷ 3사 ${fmt0(c.s.seatSold)}석`; };
    let natF=null, natSrc="";
    for(const x of done.slice().reverse()){ const c=natCand(x); if(c&&c.cov>=0.7){ setNat(c); break; } }
    if(natF==null) for(const x of done.slice().reverse()){ const c=natCand(x); if(c){ setNat(c); break; } }  // 온전한 날 없으면 종전 방식
    /* 규모가 다른 날의 판매율을 갖다 쓰면 숫자가 망가진다.
       71개 관 시사회는 81% 가 차지만, 621개 관으로 넓게 거는 날이 그렇게 찰 리 없다
       — 그대로 곱하면 개봉 첫 주 누적 42만이 나온다(1편 전체가 121만인데).
       그래서 규모가 3배 넘게 차이 나면 예상치를 아예 내놓지 않는다.
       8/5 가 끝나 621관 실측이 생기는 순간 그 뒤 날짜들에 자동으로 기준이 선다. */
    const SCALE_TOL=3;
    const fillOf=(s,play)=>{ const b=pickBench(s.screens,play); if(!b) return null;
      const bl=lastOf(b); if(!(bl.seatTot>0)) return null;
      const a=bl.screens||1, c=s.screens||1;
      const ratio=Math.max(a/c, c/a);
      return {f:bl.seatSold/bl.seatTot, b, bl, ratio, ok:ratio<=SCALE_TOL}; };

    /* ── 예매 축적 곡선 ─────────────────────────────────────
       예전 식은 `총좌석 × 기준일 판매율 × 전국보정` 이었다. 기준일(개봉일)이 30% 를
       채웠으니 다른 날도 30% 채울 것이라고 본 셈인데, 그게 안 맞는다 —
       8/07 실측 41,684명인데 그 식은 7.6만(+82%)을 냈다. 개봉일 판매율을
       평일에 갖다 쓴 탓이다(8/07 은 실제로 15% 만 찼다).

       그래서 공급(총좌석)이 아니라 수요(이미 팔린 좌석)에 건다.
       배수는 아카이브에서 직접 잰다 — 같은 영화의 지난 상영일들에 대해
       "상영 N일 전 시점의 3사 예매좌석" 대비 "KOBIS 실측 관객" 이 몇 배였는가.

         D-0  1.31 · 1.40  → 1.35
         D-1  1.75 · 2.00  → 1.88
         D-2  2.44 · 3.15  → 2.79

       ⚠ D-2 이후는 쓰지 않는다. 그 배수는 개봉일·금요일에서 나온 값인데,
         평일은 예매가 훨씬 늦게 붙는다. 8/10(월)에 2.79 를 곱하면 1.5만이
         나오는데 실제로는 4만+ 나올 날이다. 근거 없는 숫자를 내느니
         1편 같은 일차 실측을 보여주는 게 낫다(아래에서 자동으로 그렇게 된다).

       표본이 쌓일수록 저절로 정확해진다 — 하드코딩이 아니라 매번 다시 잰다. */
    const LEAD_MAX=1;
    const dayKey=t=>t.slice(0,10).replace(/-/g,"");
    const kobOf=play=>Object.values(MV.movies||{}).flatMap(m=>m.days||[]).find(x=>x.d===play);
    const gapDays=(a,b)=>Math.round((new Date(`${b.slice(0,4)}-${b.slice(4,6)}-${b.slice(6,8)}`)
                                    -new Date(`${a.slice(0,4)}-${a.slice(4,6)}-${a.slice(6,8)}`))/864e5);
    const LEADK=(()=>{
      const acc={};
      arr.forEach(x=>{
        const kb=kobOf(x.play); if(!kb||!kb.audi) return;
        const fin=lastOf(x);
        if(!fin||fin.screens<100) return;                       // 시사회·소규모는 양상이 다르다
        if(!(kb.scrn>0)||fin.screens < 0.7*kb.scrn) return;      // 수집이 덜 된 날은 분모가 껍데기다
        const per={};                                           // 관측일 -> 그날 최댓값
        (x.ser||[]).forEach(pt=>{ if(!(pt.seatSold>0)) return;
          const k=dayKey(pt.t); if(!per[k]||pt.seatSold>per[k]) per[k]=pt.seatSold; });
        Object.entries(per).forEach(([obs,sold])=>{
          const lead=gapDays(obs,x.play);
          if(lead<0||lead>4) return;
          (acc[lead]=acc[lead]||[]).push(kb.audi/sold);
        });
      });
      const out={};
      Object.entries(acc).forEach(([k,v])=>{ out[k]={k:v.reduce((a,b)=>a+b,0)/v.length, n:v.length}; });
      return out;
    })();

    const est=(s,play)=>{
      if(!(s.seatSold>0)) return null;
      const lead=gapDays(todayISO, play);
      if(lead<0||lead>LEAD_MAX) return null;                    // 근거 없는 숫자는 내지 않는다
      const c=LEADK[lead];
      if(!c||c.n<2) return null;                                // 표본 1건짜리 배수는 안 쓴다
      return s.seatSold*c.k;
    };
    const estWhy=(s,play)=>{
      const lead=gapDays(todayISO, play), c=LEADK[lead];
      return (c&&c.n>=2)?{lead, k:c.k, n:c.n}:null;
    };
    // 확보 하한: 지금 이미 팔린 예매만으로 계산. 날짜가 다가올수록 예상선에 붙는다.
    const floorOf=s=>s.seatSold*(natF||1);

    const future=arr.filter(x=>x.play>=todayISO);
    // 헤드라인 상영일: 개봉 전이면 개봉일, 개봉 후면 '가장 가까운 날(오늘)'.
    // 예전엔 future[마지막] 이라 개봉 후엔 제일 먼 날(8/17, 21관짜리 파편)이 대문짝만하게 떴다.
    const main=future.find(x=>op&&x.play===op)||future[0]||arr[arr.length-1];
    const s1=lastOf(main);
    const s0=prevSer(main.ser,main.play);            // 전일 관측치(그 날의 최댓값)와 견준다
    const dv=k=> s0? `<span class="${cls(s1[k]-s0[k])}">${s1[k]===s0[k]?"변동 없음":sign(s1[k]-s0[k],0)+" 전일비"}</span>` : "첫 스냅샷";
    const rate1=s1.seatTot>0?(s1.seatSold/s1.seatTot*100):null;
    const by=s1.by?Object.entries(s1.by).map(([t2,v])=>`${t2} ${v.screens}`).join(" · "):"";
    const e1=est(s1,main.play), r1=fillOf(s1,main.play);
    const openLbl=op&&main.play===op?"개봉일":`${main.play.slice(4,6)}/${main.play.slice(6,8)}`;
    h+=`<div class="sub-h">스크린 확보 — ${title}
        <span class="tag-inline">3사 전수 · ${SC.chain}</span></div>
      <div class="kpis">
        <div class="kpi"><div class="k">${openLbl} 스크린</div>
          <div class="v">${fmt0(s1.screens)}<small>개</small></div>
          <div class="d">${dv("screens")}${by?` · ${by}`:""}</div></div>
        <div class="kpi"><div class="k">${openLbl} 좌석 <span class="th-sub">공급</span></div>
          <div class="v">${(s1.seatTot/1e4).toFixed(1)}<small>만석</small></div>
          <div class="d">지점 ${fmt0(s1.sites)}곳 · ${fmt0(s1.shows)}회차</div></div>
        <div class="kpi"><div class="k">${openLbl} 예매 <span class="th-sub">확보</span></div>
          <div class="v">${fmt0(s1.seatSold)}<small>석</small></div>
          <div class="d">좌석 판매율 ${rate1==null?"—":fmt(rate1,1)+"%"} · ${dv("seatSold")}</div></div>
        <div class="kpi"><div class="k">${openLbl} ${e1==null?"1편 같은 일차":"예상 관객"}</div>
          <div class="v">${e1!=null?"~"+(e1/1e4).toFixed(1)
             :(refDay[ddOf(main.play)]!=null?fmt0(refDay[ddOf(main.play)]):"—")}<small>${e1!=null?"만명":"명"}</small></div>
          <div class="d">${e1!=null
             ? (()=>{const w=estWhy(s1,main.play);
                 return `예매 ${fmt0(s1.seatSold)}석 × ${w.k.toFixed(2)} <span class="th-sub">D-${w.lead} 실측 ${w.n}건 평균</span>`;})()
             : (r1?`<span style="color:var(--warn)">기준 대기</span> · 기준일 ${fmt0(r1.bl.screens)}관 vs ${fmt0(s1.screens)}관`
                  :`<span style="color:var(--warn)">기준 대기</span> · 시사회 판매율은 못 씀`)}</div></div>
      </div>`;

    /* ── 차트 두 장, 같은 날짜 축을 세로로 맞춰 놓는다 ──
       위: 누적 관객 — 실선(실측) 뒤로 점선 두 줄이 이어진다.
           굵은 점선 = 기준 시나리오(좌석 x 기준 판매율), 얇은 점선 = 지금 확보된 예매만.
           둘 사이 간격이 곧 '아직 안 팔린 몫'이고, 날짜가 다가올수록 좁혀진다.
       아래: 좌석(공급) vs 예매(수요) — 같은 날짜에 뭘 얼마나 깔았고 얼마나 찼는지. */
    {
      const mvMine=Object.entries(MV.movies||{}).find(([t])=>norm(t)===norm(title));
      const actual=(mvMine?mvMine[1].days:[])
        .map(p=>({play:p.d, acc:p.acc})).sort((a,b)=>a.play.localeCompare(b.play));
      const lastAct=actual.length?actual[actual.length-1]:null;
      const seatDays=arr.filter(x=>lastOf(x).seatTot>0&&ddOf(x.play)!=null);
      // 실측이 끝난 뒤의 날짜들만 예측 대상 — 지난 날은 이미 KOBIS 가 답을 준다.
      const todo=seatDays.filter(x=>!lastAct||x.play>lastAct.play);
      let cA=lastAct?lastAct.acc:0, cB=lastAct?lastAct.acc:0;
      const projEst=[], projLow=[];
      // 확보선은 늘 그린다(실데이터). 기준선은 하루라도 근거가 끊기면 거기서 멈춘다 —
      // 누적이라 중간에 못 세운 날이 있으면 그 뒤 값도 못 믿는다.
      let estOn=true;
      todo.forEach(x=>{ const s=lastOf(x), e=est(s,x.play), dd=ddOf(x.play);
        cB+=floorOf(s); projLow.push({dd, acc:cB});
        if(estOn&&e!=null){ cA+=e; projEst.push({dd, acc:cA}); } else estOn=false; });
      const ref=(()=>{
        const other=Object.entries(MV.movies||{}).find(([t])=>norm(t)!==norm(title));
        if(!other||!op) return null;
        const oOp=(other[1].openDt||"").replace(/-/g,""); if(!oOp) return null;
        const d0=new Date(`${oOp.slice(0,4)}-${oOp.slice(4,6)}-${oOp.slice(6,8)}`);
        return (other[1].days||[]).map(p=>({
          dd:Math.round((new Date(`${p.d.slice(0,4)}-${p.d.slice(4,6)}-${p.d.slice(6,8)}`)-d0)/864e5), acc:p.acc}));
      })();
      const A0=actual.map(p=>({dd:ddOf(p.play), acc:p.acc})).filter(p=>p.dd!=null);
      if(A0.length||projEst.length){
        /* 축의 시작은 '좌석을 잰 첫 날'이다. KOBIS 실측만 있는 앞 날(8/1 시사회)까지
           끌어오면 막대가 하나도 없는 빈 칸이 앞에 붙는다. 누적 관객선은 누적값이라
           그 날을 떼도 8/2 값에 이미 들어 있어 손실이 없다. */
        const ddAll=[...projEst.map(p=>p.dd), ...seatDays.map(x=>ddOf(x.play))];
        const dLo=Math.min(...ddAll), dHi=Math.max(...ddAll);
        const A=A0.filter(p=>p.dd>=dLo&&p.dd<=dHi);
        const refPts=(ref||[]).filter(p=>p.dd>=dLo&&p.dd<=dHi);
        /* 날짜를 '칸'으로 잡고 그 한가운데에 찍는다. 예전처럼 양 끝에 딱 붙여 찍으면
           첫 날 막대의 왼쪽 절반이 세로축 눈금 글자 위로 올라탄다(8/1 이 빠지면서 첫 칸에
           막대가 생겨 드러났다). 세 차트가 같은 sx 를 쓰므로 한 번만 고치면 된다. */
        const W=900,pad={l:58,r:104};
        const nDay=Math.max(1,dHi-dLo+1), cellW=(W-pad.l-pad.r)/nDay;
        const sx=dd=>pad.l+(dd-dLo+0.5)*cellW;
        // 인라인 SVG 안에서는 CSS 변수를 그대로 쓸 수 있다. 계산된 색을 박아 넣으면
        // 테마를 바꿨을 때 다시 그리기 전까지 옛 색이 남는다.
        const gc="var(--line)", mut="var(--muted)";
        const calOf=dd=>{ if(!op) return "";
          const c=new Date(new Date(`${op.slice(0,4)}-${op.slice(4,6)}-${op.slice(6,8)}`).getTime()+dd*864e5);
          return `${String(c.getMonth()+1).padStart(2,"0")}/${String(c.getDate()).padStart(2,"0")}`; };
        const xAxis=(H,b)=>{ let s="";
          for(let dd=dLo;dd<=dHi;dd++){
            s+=`<text x="${sx(dd)}" y="${H-b+15}" text-anchor="middle" font-size="9.5" fill="${mut}">${calOf(dd)}</text>`;
            s+=`<text x="${sx(dd)}" y="${H-b+27}" text-anchor="middle" font-size="9" fill="${mut}" opacity=".7">D${dd>=0?"+":""}${dd}</text>`;}
          return s; };

        /* 위 — 누적 관객 */
        const H1=250, t1=16, b1=36;
        const yMax=Math.max(...A.map(p=>p.acc), ...projEst.map(p=>p.acc), ...refPts.map(p=>p.acc), 1)*1.14;
        const sy=v=>H1-b1-(v/yMax)*(H1-t1-b1);
        let s=`<div class="sub-h" style="margin-top:14px">누적 관객 전망
            <span class="tag-inline">실선=실측 · 굵은점선=기준 · 얇은점선=현재 예매만</span></div>
          <div class="chart-box scr-bars"><svg viewBox="0 0 ${W} ${H1}" width="100%" font-family="inherit">`;
        for(let g=0;g<=4;g++){const v=yMax*g/4,y=sy(v);
          s+=`<line x1="${pad.l}" y1="${y}" x2="${W-pad.r}" y2="${y}" stroke="${gc}"/>`;
          s+=`<text x="${pad.l-6}" y="${y+4}" text-anchor="end" font-size="11" fill="${mut}">${(v/1e4).toFixed(0)}만</text>`;}
        // 세로선은 개봉일이 아니라 '오늘'을 표시한다.
        //   모든 판단이 오늘 기준이라, 어디까지가 실측이고 어디부터가 전망인지를
        //   가르는 선이 개봉일보다 훨씬 자주 쓰인다.
        {const tdd=ddOf(todayISO);
         if(tdd!=null&&tdd>=dLo&&tdd<=dHi){
           s+=`<line x1="${sx(tdd)}" y1="${t1}" x2="${sx(tdd)}" y2="${H1-b1}" stroke="var(--accent)" stroke-dasharray="3 4" opacity=".75"/>`;
           s+=`<text x="${sx(tdd)}" y="${t1-4}" text-anchor="middle" font-size="9.5" fill="var(--accent)" opacity=".9">오늘</text>`;}}
        s+=xAxis(H1,b1);
        if(refPts.length>1){
          s+=`<path d="${refPts.map((p,i)=>(i?"L":"M")+sx(p.dd).toFixed(1)+","+sy(p.acc).toFixed(1)).join(" ")}" fill="none" stroke="#c4a7e7" stroke-width="2" opacity=".36"/>`;
          const rl=refPts[refPts.length-1];
          s+=`<text x="${sx(rl.dd)+6}" y="${sy(rl.acc)+4}" font-size="10.5" fill="#c4a7e7" opacity=".75">1편 실측</text>`;}
        if(A.length){
          s+=`<path d="${A.map((p,i)=>(i?"L":"M")+sx(p.dd).toFixed(1)+","+sy(p.acc).toFixed(1)).join(" ")}" fill="none" stroke="#eb6f92" stroke-width="2.6" stroke-linejoin="round"/>`;
          A.forEach(p=>{s+=`<circle cx="${sx(p.dd)}" cy="${sy(p.acc)}" r="3" fill="#eb6f92"><title>${calOf(p.dd)} D${p.dd>=0?"+":""}${p.dd} · 실측 누적 ${fmt0(p.acc)}명</title></circle>`;});}
        const head=A.length?A[A.length-1]:null;
        const draw=(pts,w,dash,op2,lbl)=>{ if(!pts.length) return "";
          const path=(head?[head,...pts]:pts);
          let o=`<path d="${path.map((p,i)=>(i?"L":"M")+sx(p.dd).toFixed(1)+","+sy(p.acc).toFixed(1)).join(" ")}" fill="none" stroke="#eb6f92" stroke-width="${w}" stroke-dasharray="${dash}" opacity="${op2}"/>`;
          pts.forEach(p=>{o+=`<circle cx="${sx(p.dd)}" cy="${sy(p.acc)}" r="2.8" fill="none" stroke="#eb6f92" stroke-width="1.5" opacity="${op2}"><title>${calOf(p.dd)} D${p.dd>=0?"+":""}${p.dd} · ${lbl} 누적 ~${fmt0(p.acc)}명</title></circle>`;});
          return o; };
        s+=draw(projLow,1.6,"3 4",.5,"현재 예매만");
        s+=draw(projEst,2.4,"6 5",.95,"기준");
        if(projEst.length){ const pl=projEst[projEst.length-1];
          s+=`<text x="${sx(pl.dd)+7}" y="${sy(pl.acc)+4}" font-size="11.5" font-weight="700" fill="#eb6f92">~${(pl.acc/1e4).toFixed(1)}만</text>`;}
        if(projLow.length){ const ql=projLow[projLow.length-1];
          s+=`<text x="${sx(ql.dd)+7}" y="${sy(ql.acc)+4}" font-size="10" fill="#eb6f92" opacity=".65">확보 ~${(ql.acc/1e4).toFixed(1)}만</text>`;}
        s+=`</svg></div>`;

        /* 아래 — 좌석(공급) vs 예매(수요) */
        const H2=170, t2=14, b2=36;
        const sMax=Math.max(...seatDays.map(x=>lastOf(x).seatTot),1)*1.16;
        const sy2=v=>H2-b2-(v/sMax)*(H2-t2-b2);
        const bw=Math.min(46,(W-pad.l-pad.r)/Math.max(1,dHi-dLo+1)*0.64);
        s+=`<div class="sub-h" style="margin-top:12px">좌석 vs 예매
            <span class="tag-inline">연한 막대=걸린 좌석 · 진한 막대=팔린 예매</span></div>
          <div class="chart-box scr-bars"><svg viewBox="0 0 ${W} ${H2}" width="100%" font-family="inherit">`;
        for(let g=0;g<=3;g++){const v=sMax*g/3,y=sy2(v);
          s+=`<line x1="${pad.l}" y1="${y}" x2="${W-pad.r}" y2="${y}" stroke="${gc}"/>`;
          s+=`<text x="${pad.l-6}" y="${y+4}" text-anchor="end" font-size="10.5" fill="${mut}">${v>=1e4?(v/1e4).toFixed(0)+"만":fmt0(v)}</text>`;}
        {const tdd=ddOf(todayISO);
         if(tdd!=null&&tdd>=dLo&&tdd<=dHi)
           s+=`<line x1="${sx(tdd)}" y1="${t2}" x2="${sx(tdd)}" y2="${H2-b2}" stroke="var(--accent)" stroke-dasharray="3 4" opacity=".75"/>`;}
        s+=xAxis(H2,b2);
        seatDays.forEach(x=>{ const dd=ddOf(x.play), s2=lastOf(x);
          const x0=sx(dd)-bw/2, r=s2.seatTot>0?s2.seatSold/s2.seatTot*100:0;
          s+=`<rect x="${x0.toFixed(1)}" y="${sy2(s2.seatTot).toFixed(1)}" width="${bw.toFixed(1)}" height="${(H2-b2-sy2(s2.seatTot)).toFixed(1)}" rx="3" fill="${mut}" opacity=".22"><title>${calOf(dd)} 좌석 ${fmt0(s2.seatTot)}석 · 스크린 ${fmt0(s2.screens)}</title></rect>`;
          s+=`<rect x="${x0.toFixed(1)}" y="${sy2(s2.seatSold).toFixed(1)}" width="${bw.toFixed(1)}" height="${(H2-b2-sy2(s2.seatSold)).toFixed(1)}" rx="3" fill="#eb6f92" opacity=".9"><title>${calOf(dd)} 예매 ${fmt0(s2.seatSold)}석 (${r.toFixed(1)}%)</title></rect>`;
          s+=`<text x="${sx(dd)}" y="${(sy2(s2.seatTot)-5).toFixed(1)}" text-anchor="middle" font-size="10" font-weight="700" fill="${mut}">${r.toFixed(0)}%</text>`;
          const ms=missOf(s2,x.play), lb=fillingOf(x.play)?"편성 중":preOf(x.play)?"편성 전":(ms.length?ms.join("·")+" 미오픈":"");
          if(lb) s+=`<text x="${sx(dd)}" y="${(sy2(s2.seatTot)-16).toFixed(1)}" text-anchor="middle" font-size="8.5" fill="var(--warn)">${lb}</text>`;});
        s+=`</svg></div>`;

        /* ── 날짜별 비교: 추이 선 두 장 + 압축 표 ──
           묶음 막대(한 줄에 40칸)도, 날짜별 카드(열 장)도 실패했다.
           앞은 어디까지가 같은 날인지 안 갈렸고, 뒤는 자리만 먹고 흐름이 안 보였다.
           날짜별로 궁금한 건 결국 둘이다 — 얼마나 걸었나(좌석), 얼마나 찼나(판매율).
           그래서 그 둘만 날짜 축 위에 선으로 얹고, 정확한 값은 아래 표에 모은다.
           주말 음영 같은 장식은 넣지 않는다. 요일은 축 라벨에 글자로 적으면 충분하다. */
        const PEERS=SC.peers||{};
        const peerNames=Object.keys(PEERS).filter(n=>norm(n)!==norm(title));
        if(peerNames.length){
          const mine=Object.fromEntries(seatDays.map(x=>[x.play,lastOf(x)]));
          const top=peerNames.map(n=>({n, m:Math.max(...Object.values(PEERS[n]).map(v=>v.screens||0))}))
                             .sort((a,b)=>b.m-a.m).slice(0,3).map(x=>x.n);
          const rows=[{n:title, mine:true, get:p=>mine[p]||null},
                      ...top.map(n=>({n, mine:false, get:p=>PEERS[n][p]||null}))];
          let days=[...new Set([...Object.keys(mine), ...top.flatMap(n=>Object.keys(PEERS[n]))])]
                     .sort()
                     .filter(p=>ddOf(p)!=null&&ddOf(p)>=dLo&&ddOf(p)<=dHi)
                     .filter(p=>rows.some(r=>((r.get(p)||{}).seatTot||0)>0));
          const PAL=["#eb6f92","#9ccfd8","#f6c177","#a6da95"];
          const COL={}; rows.forEach((r,i)=>COL[r.n]=PAL[i%PAL.length]);
          const WD=["일","월","화","수","목","금","토"];
          const wdOf=p=>WD[new Date(`${p.slice(0,4)}-${p.slice(4,6)}-${p.slice(6,8)}`).getDay()];
          const md=p=>`${p.slice(4,6)}/${p.slice(6,8)}`;
          const shortN=n=>{const b=n.split(/[:(（]/)[0].trim(); return b.length>7?b.slice(0,7)+"…":b;};
          const man=v=>v>=1e4?(v/1e4).toFixed(1)+"만":fmt0(v);
          const at=(r,p)=>{ const v=r.get(p); return (v&&v.seatTot>0)?v:null; };
          /* 값이 있는 날만 남기면 달력에 구멍이 뚫린다 — 8/3(월)은 하츄핑2 상영이 없었고
             비교군은 아직 수집 전이라 통째로 빠졌고, 그러면 축이 8/2 다음에 8/4 로 건너뛴다.
             날짜를 임의로 건너뛴 것처럼 읽히므로 처음부터 끝까지 하루도 빼지 않고 채운다.
             빈 날은 아래에서 '상영 없음 / 수집 전' 으로 갈라 표시한다. */
          const dayAdd=(p,n)=>{ const d=new Date(`${p.slice(0,4)}-${p.slice(4,6)}-${p.slice(6,8)}`);
            d.setDate(d.getDate()+n);
            return `${d.getFullYear()}${String(d.getMonth()+1).padStart(2,"0")}${String(d.getDate()).padStart(2,"0")}`; };
          const hit=days.filter(p=>rows.some(r=>at(r,p)));
          days=[]; if(hit.length){ const end=hit[hit.length-1];
            for(let p=hit[0]; p<=end; p=dayAdd(p,1)) days.push(p); }
          /* 영화마다 '언제부터 잡히기 시작했나'. 그 전 날짜에 값이 없는 건
             안 걸린 게 아니라 그때 우리가 안 재고 있었던 것이다 — 둘을 섞으면
             8/2 에 스파이더맨이 상영을 안 한 것처럼 읽힌다(실제로는 상영 중이었다). */
          const since={}; rows.forEach(r=>{ const d=days.filter(p=>at(r,p)); since[r.n]=d.length?d[0]:null; });
          if(days.length){
            /* 위 '좌석 vs 예매' 와 똑같은 막대를 날짜마다 네 편씩 묶는다.
               앞서 실패한 판은 묶음이 눈에 안 보인 게 원인이었다 — 그래서
                 · 날짜 사이에 세로 칸막이를 긋고(막대 위부터 날짜 라벨 아래까지)
                 · 데이터 없는 영화도 자리를 비워 두어(바닥에 짧은 선) 늘 네 칸이 되게 하고
                 · 막대 위 숫자에 % 를 붙여 그게 판매율임을 못 알아볼 수 없게 했다.
               장식용 음영은 넣지 않는다 — 칸막이만으로 하루가 갈린다. */
            const pctOf=v=>(v&&v.seatTot>0)?v.seatSold/v.seatTot*100:null;
            /* 폭·좌우 여백·날짜 좌표를 위 두 차트와 똑같이 쓴다(W·pad·sx 재사용).
               그래야 8/8 막대가 위 차트의 8/8 바로 아래에 오고 세 장을 세로로 훑을 수 있다.
               pt 를 넉넉히 잡는 건 판매율 라벨이 위로 밀릴 자리 때문이다. */
            const Wc=W, Hc=300, pl=pad.l, pr=pad.r, pt=36, pb=46;
            const gw=cellW;
            const gx=i=>sx(ddOf(days[i]));
            /* 묶음이 묶음으로 보이려면 '칸 사이 골'이 '막대 사이 틈'보다 확실히 넓어야 한다.
               막대를 칸 폭에 꽉 채웠더니 27.7 vs 21.7 — 눈이 못 갈랐다.
               묶음 폭을 칸의 66% 로 묶어 두면 골이 틈의 두 배 넘게 벌어진다. */
            const ig=2;
            const bw=Math.max(5,Math.min(20,(gw*0.66-(rows.length-1)*ig)/rows.length));
            const grpW=rows.length*bw+(rows.length-1)*ig;
            /* ── 눌러 놓은 세로 눈금 ──
               좌석이 982석(시사회)에서 40만석(스파이더맨 주말)까지 400배로 벌어진다.
               자를 곧게 대면 40만이 화면을 다 먹고 시사회는 1px 이 돼 보이지도 않는다.
               그렇다고 시사회를 빼면 개봉 전 흐름이 통째로 사라진다 — 지금 제일 궁금한 구간인데.
               그래서 제곱근에 가깝게(지수 0.55) 눌러, 값이 커질수록 높이에 덜 반영되게 한다.
               순서는 그대로 보존되고 작은 날도 눈에 남는다. 대신 '길이 비율 = 좌석 비율'이
               아니게 되므로 눌렸다는 사실이 화면에 드러나야 한다.
               그래서 눈금선을 값이 아니라 '같은 높이'마다 긋고 거기 해당하는 좌석수를 적는다.
               숫자가 2.8만 -> 10만 -> 21만 -> 35만 -> 53만 처럼 위로 갈수록 큰 폭으로 뛰는데,
               그 벌어짐이 곧 눌림의 눈금이다. (1·2·5 자리수로 눈금을 뽑으면 오히려
               간격이 위로 갈수록 넓어져서 눌린 게 아니라 늘어난 것처럼 읽힌다.) */
            const SQZ=0.55;
            const vmax=Math.max(...days.flatMap(p=>rows.map(r=>(at(r,p)||{}).seatTot||0)),1)*1.06;
            const yy=v=>Hc-pb-Math.pow(Math.max(0,v)/vmax,SQZ)*(Hc-pt-pb);
            const ticks=[0.2,0.4,0.6,0.8,1].map(f=>vmax*Math.pow(f,1/SQZ));
            s+=`<div class="sub-h" style="margin-top:14px">날짜별 · 좌석 vs 예매
                <span class="tag-inline">3사 합산 · 연한 막대=걸린 좌석 · 진한 막대=팔린 예매 · 위 숫자=판매율</span>
                <span class="tag-inline" style="color:var(--warn)">세로 눈금 눌림 — 클수록 덜 반영</span></div>
              <div class="scr-lg">`
              +rows.map(r=>`<span class="li"><span class="dot" style="background:${COL[r.n]}"></span><span style="color:${COL[r.n]}">${shortN(r.n)}</span></span>`).join("")
              +`</div>
              <div class="chart-box scr-bars" style="margin-top:8px"><svg viewBox="0 0 ${Wc} ${Hc}" width="100%" font-family="inherit">`;
            [0,...ticks].forEach(v=>{ const y=yy(v);
              s+=`<line x1="${pl}" y1="${y.toFixed(1)}" x2="${Wc-pr}" y2="${y.toFixed(1)}" stroke="${gc}"/>`;
              s+=`<text x="${pl-6}" y="${(y+4).toFixed(1)}" text-anchor="end" font-size="9.5" fill="${mut}">${v>=1e5?(v/1e4).toFixed(0)+"만":v>=1e4?(v/1e4).toFixed(1)+"만":fmt0(Math.round(v))}</text>`; });
            // 날짜 칸막이 — 어디까지가 하루인지 이것 하나로 갈린다
            days.forEach((p,i)=>{ if(!i) return; const x=(gx(i)-gw/2).toFixed(1);
              s+=`<line x1="${x}" y1="${pt-8}" x2="${x}" y2="${Hc-pb+38}" stroke="${gc}"/>`; });
            /* 판매율 라벨은 막대보다 넓다(막대 11px, '13%' 는 18px).
               겹치는 걸 버렸더니 옆과 높이가 비슷한 막대의 숫자가 통째로 사라졌다
               — 오디세이가 스파이더맨과 나란히 서는 날마다 값이 없어 보였다.
               버리지 말고 한 줄씩 위로 밀어 올린다. 넷 다 남고, 계단처럼 어긋나
               어느 막대 것인지도 오히려 또렷해진다. */
            const labs=[];
            days.forEach((p,i)=>{
              const x0=gx(i)-grpW/2;
              rows.forEach((r,ri)=>{
                const v=at(r,p), bx=x0+ri*(bw+ig), c=COL[r.n];
                if(!v){   // 그 날 안 걸린 영화도 칸은 남긴다 — 안 그러면 묶음 폭이 들쭉날쭉해진다
                  const pre=since[r.n]&&p<since[r.n];
                  s+=`<line x1="${bx.toFixed(1)}" y1="${Hc-pb}" x2="${(bx+bw).toFixed(1)}" y2="${Hc-pb}" stroke="${c}" stroke-width="1.5" opacity="${pre?".15":".35"}" stroke-dasharray="${pre?"2 2":"0"}"><title>${r.n} · ${md(p)} ${pre?"아직 수집 전(상영은 하고 있었음)":"상영 없음"}</title></line>`;
                  return; }
                const pct=pctOf(v), yT=yy(v.seatTot), yS=yy(v.seatSold);
                s+=`<rect x="${bx.toFixed(1)}" y="${yT.toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(0,Hc-pb-yT).toFixed(1)}" rx="2.5" fill="${c}" opacity=".22"><title>${r.n}
${md(p)}(${wdOf(p)}) · 걸린 좌석 ${fmt0(v.seatTot)}석 / ${fmt0(v.screens)}관</title></rect>`;
                s+=`<rect x="${bx.toFixed(1)}" y="${yS.toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(0,Hc-pb-yS).toFixed(1)}" rx="2.5" fill="${c}" opacity=".95"><title>${r.n}
${md(p)}(${wdOf(p)}) · 예매 ${fmt0(v.seatSold)}석 / 좌석 ${fmt0(v.seatTot)}석 · 판매율 ${pct.toFixed(1)}%</title></rect>`;
                labs.push({x:bx+bw/2, y:yT-5, t:`${pct.toFixed(0)}%`, c, mine:r.mine, sz:v.seatTot}); });
              const isOp=p===op;
              s+=`<text x="${gx(i).toFixed(1)}" y="${Hc-pb+17}" text-anchor="middle" font-size="10.5" font-weight="${isOp?800:600}" fill="${isOp?"var(--accent)":mut}">${md(p)}</text>`;
              s+=`<text x="${gx(i).toFixed(1)}" y="${Hc-pb+29}" text-anchor="middle" font-size="9" fill="${isOp?"var(--accent)":mut}" opacity="${isOp?1:.65}">${wdOf(p)} · ${isOp?"개봉":"D"+(ddOf(p)>=0?"+":"")+ddOf(p)}</text>`; });
            // 왼쪽부터 놓다가 부딪히면 한 줄 위로. 네 번까지 올리고 천장에서 멈춘다.
            const FS=8.5, LH=10, put=[];
            labs.sort((a,b)=>a.x-b.x).forEach(L=>{
              const w=L.t.length*FS*0.72+2;   // 실측: 8.5pt 세 글자가 18.1px
              let y=L.y;
              for(let k=0;k<4;k++){
                if(!put.some(q=>Math.abs(q.y-y)<LH && Math.abs(q.x-L.x)<(q.w+w)/2)) break;
                y-=LH; }
              y=Math.max(11,y);           // 천장 위로는 못 나간다
              put.push({x:L.x, y, w});
              s+=`<text x="${L.x.toFixed(1)}" y="${y.toFixed(1)}" text-anchor="middle" font-size="${FS}" font-weight="700" letter-spacing="-.4" fill="${L.c}">${L.t}</text>`; });
            s+=`</svg></div>`;
            // 정확한 값은 표로. 셀은 판매율을 크게, 예매/좌석을 작게 — 셋이 한 칸에 들어간다.
            s+=`<details class="fold"><summary>날짜별 값 표로 보기 <span class="sub">판매율 · 예매/좌석 · 읽는 법</span></summary>
              <div class="fold-b"><div class="tbl-wrap"><table class="mini-tbl"><thead><tr>
              <th class="l">상영일</th>`
              +rows.map(r=>`<th style="color:${COL[r.n]}">${shortN(r.n)}<span class="th-sub">판매율 · 예매/좌석</span></th>`).join("")
              +`</tr></thead><tbody>`
              +days.map(p=>`<tr><td class="l">${md(p)}<span class="th-sub">${wdOf(p)} · D${ddOf(p)>=0?"+":""}${ddOf(p)}</span></td>`
                +rows.map(r=>{ const v=at(r,p);
                  if(!v) return `<td style="color:var(--muted2)">—</td>`;
                  return `<td><b>${pctOf(v).toFixed(1)}%</b><span class="th-sub">${man(v.seatSold)} / ${man(v.seatTot)}</span></td>`; }).join("")
                +`</tr>`).join("")
              +`</tbody></table></div>
              <p class="note" style="margin:8px 0 0">
                <b style="color:var(--warn)">세로 눈금 눌림</b> — 좌석이 982석(시사회)~40만석으로 400배 벌어져, 곧은 자로는 작은 날이 1px 이 됩니다.
                <b>막대 길이 비율 ≠ 좌석 비율</b>이니 크기는 눈금 숫자와 이 표로 보십시오(눈금 값이 위로 갈수록 크게 뛰는 게 눌림의 표시).<br>
                빈 칸 — <b>실선</b>은 그 날 안 걸림, <b>점선</b>은 수집 시작 전(상영은 하고 있었음).
                비교작은 상영 중, 하츄핑2는 개봉 전이라 <b>개봉 전 예매의 통상 수준</b>을 가늠하는 용도입니다.</p>
              </div></details>`;
          }
        }
        h+=s;
      }
    }
    /* ── 날짜별 표 (예상 관객 포함) ── */
    h+=`<details class="fold"><summary>${title.split(":")[0].trim()} 날짜별 상세 <span class="sub">지점·회차·예상 관객·1편 같은 일차</span></summary>
      <div class="fold-b"><div class="tbl-wrap"><table class="mini-tbl"><thead><tr>
      <th class="l">상영일</th><th>일차</th><th>지점</th><th>스크린</th>
      <th>1편 스크린<span class="th-sub">같은 일차 · 대비</span></th><th>회차</th>
      <th>좌석<span class="th-sub">공급</span></th><th>예매<span class="th-sub">확보</span></th>
      <th>좌석 판매율<span class="th-sub">팔린÷걸린</span></th>
      <th>예상 관객</th><th>1편 같은 일차<span class="th-sub">당일 실측</span></th></tr></thead><tbody>`
      +arr.map(({play,ser})=>{
        const s=peakSer(ser,play), prev=prevSer(ser,play);
        const isPast=play<todayISO;
        if(!s.screens&&!s.shows)
          return `<tr><td class="l">${play.slice(4,6)}/${play.slice(6,8)}</td><td>${dn(play)}</td>
            <td colspan="9" style="color:var(--muted2)">스케줄 미오픈 (통상 1~2일 전 오픈)</td></tr>`;
        const r2=s.seatTot>0?(s.seatSold/s.seatTot*100):null;
        const dscr=prev?` <small class="${cls(s.screens-prev.screens)}">${s.screens===prev.screens?"":sign(s.screens-prev.screens,0)}</small>`:"";
        const kob=Object.values(MV.movies||{}).flatMap(m=>m.days||[]).find(d2=>d2.d===play);
        const ev=est(s,play);
        const eCell=isPast
          ? (kob?`<b>${fmt0(kob.audi)}</b><span class="th-sub">실측</span>`:`<span style="color:var(--muted2)">확정 대기</span>`)
          : (ev==null?`<span style="color:var(--muted2)">기준 대기</span>`:`~${fmt0(ev)}`);
        const rd=refDay[ddOf(play)];
        // 1편 같은 일차 스크린 + 우리 대비 비율. 1편이 개봉일 1,065관을 받았는데
        // 우리가 몇 %인지가 관객 상한을 좌우한다.
        const r1s=refScrn[ddOf(play)];
        const rs = r1s==null ? '<span style="color:var(--muted2)">—</span>'
          : `${fmt0(r1s)}<span class="th-sub ${s.screens>=r1s?"up":"down"}">${s.screens?fmt(s.screens/r1s*100,0)+"%":"—"}</span>`;
        const ms=missOf(s,play), fl=fillingOf(play);
        const mark=fl?`<span class="th-sub" style="color:var(--warn)">편성 중 · 더 늘어남</span>`
                   :preOf(play)?`<span class="th-sub" style="color:var(--warn)">편성 전 · 일부 극장만 열림</span>`
                     :(ms.length?`<span class="th-sub" style="color:var(--warn)">${ms.join("·")} 미오픈</span>`:"");
        return `<tr${isPast?' style="opacity:.6"':''}><td class="l">${play.slice(4,6)}/${play.slice(6,8)}</td><td>${dn(play)}</td>
          <td>${fmt0(s.sites)}</td><td><b>${fmt0(s.screens)}</b>${dscr}${mark}</td>
          <td>${rs}</td><td>${fmt0(s.shows)}</td>
          <td>${fmt0(s.seatTot)}</td><td>${fmt0(s.seatSold)}</td>
          <td><b>${r2==null?"—":fmt(r2,1)+"%"}</b></td><td>${eCell}</td>
          <td style="color:var(--muted)">${rd==null?"—":fmt0(rd)}</td></tr>`;}).join("")
      +`</tbody></table></div>
      <p class="note" style="margin:6px 0 0"><b>예상 관객</b> = 걸린 좌석 × 기준 판매율 × 전국 보정.
      기준 판매율은 <b>규모가 비슷한 상영일의 실측</b>에서만 가져옵니다${natF?` · 전국 보정 <b>${natF.toFixed(2)}</b>(${natSrc})`:" · 전국 보정은 KOBIS 실측이 잡히면 자동 적용"}.
      ${e1==null?`<b style="color:var(--warn)">지금은 기준 대기</b> — 끝난 상영일이 ${fmt0(lastOf(done[done.length-1]||{ser:[]}).screens||0)}개 관짜리 시사회뿐이라,
      그 판매율(약 80%)을 ${fmt0(s1.screens)}개 관에 곱하면 첫 주 누적이 40만을 넘습니다(1편 전체가 121만). 근거가 설 때까지 비워 둡니다 —
      <b>${op?`${+op.slice(4,6)}/${+op.slice(6,8)} `:""}개봉일이 지나면</b> 자동으로 채워집니다. 그전엔 <b>확보된 예매</b>(하한)와 <b>1편 같은 일차</b>로 견주십시오.`
      :"이미 판 좌석보다 낮게 예측하지 않습니다. 배정이 매일 늘므로 예상치도 따라 올라갑니다."}</p>
      </div></details>`;
  });
  h+=`<details class="fold"><summary>읽는 법 · 데이터 범위 <span class="sub">미편성 착시 · 판매율 정의 · 3사 커버리지</span></summary>
    <div class="fold-b">
    <p class="note"><b style="color:var(--warn)">뒤 날짜 스크린이 적은 건 축소가 아니라 미편성입니다.</b>
    예매 달력은 2~3주 열려도 편성은 훨씬 앞서 끝나고, 여는 시점도 체인마다 다릅니다
    (8/4 실측: 메가박스 8/6까지 · CGV 8/12까지 · 롯데는 더 멀리).
    <b>편성 중</b>(거의 다 찬 날) · <b>편성 전</b>(아직 시작도 안 된 날, 극장 한두 곳이 먼저 연 파편) ·
    <b>미오픈</b>(그 체인만 아직 안 엶) 표시가 붙은 날의 값은 전부 <b>하한</b>이고 날짜가 가까워지면 채워집니다.
    실제 축소는 <b>같은 날짜 값이 날이 갈수록 줄어드는지</b>로 판별하며, 스크린 옆 전일비에 나타납니다.</p>
    <p class="note"><b>좌석 판매율</b> = 그 상영일에 팔린 좌석 ÷ 걸린 좌석. 위 예매 패널의 <b>KOBIS 예매율</b>(전체 영화 중 이 영화 몫)과는 다른 지표입니다.
    오늘 날짜는 끝난 회차가 스케줄에서 빠지므로 그날 관측된 <b>최댓값</b>을 씁니다(저녁에 판매율이 부풀지 않도록).
    3사 합계는 KOBIS 전국 예매관객의 <b>89%</b>로 3사 점유율과 맞습니다 — 독립·소형관(~10%)은 예매 API 가 없어 미포함이라 KOBIS 확정 스크린수보다 적게 잡힙니다.</p>
    </div></details>
  <p class="note" style="margin-top:8px;text-align:right">갱신 ${SC.asOf}</p>`;
  el.innerHTML=h;
}

/* ==== 극장 흥행 탭 ====
   관객수는 KOBIS 확정치라 추정 오차가 없다. SAMG 는 극장판이 분기 실적 변수라
   누적 관객 페이스가 곧 선행 지표다.
   x축을 '개봉 N일차'로 잡아야 개봉일이 2년 차이 나는 1편·2편을 겹쳐 볼 수 있다.
   일별 박스오피스가 Top10 만 주므로 순위 밖으로 밀리면 그날부터 끊긴다. */

/* 1편 예매 동시점 기록 — KOBIS 예매 이력은 조회가 안 돼서(현재값만 공개)
   당시 언론 보도로 복원한 앵커. 2편 예매가 어디쯤인지 여기에 대고 잰다.
   출처: 맥스무비EN 2024-08-06 기사(예매관객 74,006 · 오후 17.0%) · 저녁 18.9% 1위 보도 */
const MOVIE_BOOKING_REF={
  "사랑의 하츄핑: 고래보석의 전설":{
    prev:"1편", anchors:[{x:-1, book:74006, rate:18.9, src:"2024-08-06 보도"}]},
};
let movieRange="zoom";                     // zoom=개봉 전후(기본) · all=전체
document.getElementById("movieRangeSeg").addEventListener("click",e=>{
  const b=e.target.closest("button"); if(!b) return;
  movieRange=b.dataset.r;
  document.querySelectorAll("#movieRangeSeg button").forEach(x=>x.classList.toggle("active",x===b));
  renderMovie();
});
function renderMovie(){
  const box=document.getElementById("movieBox"); if(!box) return;
  const note=document.getElementById("movieNote");
  const tbl=document.getElementById("movieTable");
  renderBooking();          // 박스오피스가 비어도(개봉 전) 예매는 나와야 한다
  const M=(typeof MOVIE!=="undefined")?MOVIE:null;
  const dnum=s=>new Date(+s.slice(0,4), +s.slice(4,6)-1, +s.slice(6,8));
  const runs=Object.entries((M||{}).movies||{}).map(([nm,mv],i)=>{
    const op=dnum((mv.openDt||"").replace(/-/g,"")||mv.days[0].d);
    return {nm, stock:mv.stock, color:MOVIE_COLORS[i%MOVIE_COLORS.length], openDt:mv.openDt,
      pts:(mv.days||[]).map(p=>({x:Math.round((dnum(p.d)-op)/864e5), ...p}))};
  }).filter(r=>r.pts.length);

  /* 개봉 전 작품도 같은 D±N 축에 올린다.
     박스오피스는 순위에 든 뒤에야 값을 주지만, 예매의 '누적관객'은 시사회 실적이라
     1편의 같은 일차(D-4 30,553명 …)와 바로 견줄 수 있는 성질이 같은 숫자다.
     이걸 안 올리면 개봉 전까지 두 편을 나란히 볼 수가 없다. */
  const B=((M||{}).booking)||{};
  const pre=(MOVIE_UPCOMING||[]).filter(x=>!runs.some(r=>r.nm===x.title)).map((u,i)=>{
    const op=new Date(u.open);
    return {nm:u.title, stock:u.stock, openDt:u.open, upcoming:true,
      color:MOVIE_COLORS[(runs.length+i)%MOVIE_COLORS.length],
      pts:(B[u.title]||[]).map(p=>({x:Math.round((new Date(p.d)-op)/864e5),
        d:p.d.replace(/-/g,""), acc:p.acc, audi:null, book:p.book, rate:p.rate,
        rank:p.rank}))};                     // 예매 순위 — 개봉 전 유일한 순위 지표
  });
  const preLive=pre.filter(p=>p.pts.length);

  if(!runs.length && !preLive.length){
    box.innerHTML=`<div class="ov-empty">수집된 극장 데이터가 없습니다.</div>`;
    note.textContent=""; tbl.innerHTML=""; return;
  }

  /* 구간 — 전체(1편 D+74)로 보면 지금 진행 중인 구간이 왼쪽 구석에 눌린다.
     기본은 '개봉 전후': 시사회 시작(D-10)부터, 최신작 진행도 + 일주일까지.
     최신작이 나아가면 창도 따라 늘어난다. */
  let draw=[...runs,...preLive];
  if(movieRange==="zoom"){
    const newest=draw.reduce((a,r)=>{const mx=Math.max(...r.pts.map(p=>p.x));
      return (a==null||r.openDt>a.openDt)?{openDt:r.openDt,mx}:a;},null);
    // 창을 최신작 진행에 맞춘다. 예전엔 max(14,…)로 항상 D+14까지 열어서, 옛 흥행작
    // (1편, 개봉 74일 실측)의 먼 뒷날 누적이 y축 최댓값을 끌어올려 신작 개봉 급증을
    // 납작하게 눌렀다. 이제 hi를 최신작 진도+3(최소 3)로 잡아 같은 스케일에서 겹쳐 본다.
    const lo=-10, hi=Math.max(3,(newest?newest.mx:0)+3);
    draw=draw.map(r=>({...r,pts:r.pts.filter(p=>p.x>=lo&&p.x<=hi)})).filter(r=>r.pts.length);
    if(!draw.length){ draw=[...runs,...preLive]; }   // 창이 비면 전체로 폴백
  }
  const W=900,H=300,pad={l:58,r:14,t:14,b:28};
  const xs=draw.flatMap(r=>r.pts.map(p=>p.x));
  const x0=Math.min(...xs,0), x1=Math.max(...xs,1);
  const ymax=Math.max(...draw.flatMap(r=>r.pts.map(p=>p.acc)),1);
  const sx=v=>pad.l+(v-x0)/Math.max(1,x1-x0)*(W-pad.l-pad.r);
  const sy=v=>H-pad.b-(v/ymax)*(H-pad.t-pad.b);
  const gc=getComputedStyle(document.documentElement).getPropertyValue('--line');
  const mut=getComputedStyle(document.documentElement).getPropertyValue('--muted');
  let s=`<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" font-family="inherit">`;
  for(let g=0;g<=4;g++){const v=ymax*g/4, y=sy(v);
    s+=`<line x1="${pad.l}" y1="${y}" x2="${W-pad.r}" y2="${y}" stroke="${gc}"/>`;
    s+=`<text x="${pad.l-6}" y="${y+4}" text-anchor="end" font-size="11" fill="${mut}">${(v/10000).toFixed(0)}만</text>`;}
  // 세로선 = '오늘'. 이 차트는 여러 영화를 같은 D±N 축에 겹쳐 놓으므로,
  // 오늘은 '상영 중인 영화가 지금 몇 일차인가' 로 잡는다.
  // (개봉일 D+0 선을 쓰던 자리다 — 개봉일은 축 눈금에 이미 D+0 으로 나온다.)
  {const cur=runs.slice().filter(r=>r.openDt).sort((a,b)=>b.openDt.localeCompare(a.openDt))[0]||runs[0];
   const tdd=cur&&cur.openDt? Math.round((new Date(TODAY)-new Date(cur.openDt))/864e5) : null;
   if(tdd!=null&&tdd>=x0&&tdd<=x1){
     s+=`<line x1="${sx(tdd)}" y1="${pad.t}" x2="${sx(tdd)}" y2="${H-pad.b}" stroke="var(--accent)" stroke-dasharray="4 4" opacity=".8"/>`;
     s+=`<text x="${sx(tdd)}" y="${pad.t-3}" text-anchor="middle" font-size="9.5" fill="var(--accent)">오늘</text>`;}}
  for(let t=0;t<=6;t++){const v=Math.round(x0+(x1-x0)*t/6);
    s+=`<text x="${sx(v)}" y="${H-pad.b+17}" text-anchor="middle" font-size="11" fill="${mut}">D${v>=0?"+":""}${v}</text>`;}
  draw.forEach(r=>{
    // 개봉 전 선은 점선 — 예매 기반 시사회 누적이라 박스오피스 확정치와 성질이 다르다
    s+=`<path d="${r.pts.map((p,i)=>(i?"L":"M")+sx(p.x).toFixed(1)+","+sy(p.acc).toFixed(1)).join(" ")}"
         fill="none" stroke="${r.color}" stroke-width="2.6" stroke-linejoin="round"${r.upcoming?' stroke-dasharray="5 4"':''}/>`;
    r.pts.forEach(p=>{ s+=`<circle cx="${sx(p.x)}" cy="${sy(p.acc)}" r="2.4" fill="${r.color}"><title>${r.nm} D${p.x>=0?"+":""}${p.x} · 누적 ${fmt0(p.acc)}${p.audi!=null?" · 당일 "+fmt0(p.audi):" · 예매 "+fmt0(p.book)}</title></circle>`; });
  });
  s+="</svg>";
  const upcoming=(MOVIE_UPCOMING||[]).filter(x=>!runs.some(r=>r.nm===x.title));
  const preOf=Object.fromEntries(pre.map(p=>[p.nm,p]));
  box.innerHTML=s+`<div class="trend-legend">`+runs.map(r=>{
      const e=r.pts[r.pts.length-1];
      return `<div class="li"><span class="dot" style="background:${r.color}"></span>${r.nm}
        <small>${r.openDt} 개봉 · D+${e.x} 누적 <b>${fmt0(e.acc)}</b>명</small></div>`;}).join("")
    +upcoming.map(x=>{
      const p=preOf[x.title], e=p&&p.pts.length?p.pts[p.pts.length-1]:null;
      const d=Math.ceil((new Date(x.open)-new Date(TODAY))/864e5);
      return `<div class="li"><span class="dot" style="background:${e?p.color:mut}"></span>${x.title}
        <small>${x.open} 개봉 · ${d>0?"D-"+d:"개봉"}`
        +(e?` · D${e.x} 시사회 누적 <b>${fmt0(e.acc)}</b>명 (점선 = 예매 기준)`
            :` — 개봉하면 이 축에 겹쳐 그려집니다`)+`</small></div>`;}).join("")
    +`</div>`;
  note.textContent=`${M.asOf} 기준 · KOBIS 영화관입장권통합전산망 확정치 · `
    +`x축 D+0 = 개봉일(음수는 개봉 전 시사회) · 일별 Top10 기준이라 순위 밖으로 밀리면 끊긴다(누적은 마지막 값 유지)`;

  /* 일별 표 — 같은 D+N 을 한 행에 놓아 편끼리 바로 견준다.
     미개봉작도 열을 미리 만들어 둔다. 지금은 비어 있지만 개봉하면 그 자리가 채워져서,
     '무엇과 무엇을 비교하게 되는지'가 지금부터 보인다.
     시사회(음수 일차)도 그대로 싣는다 — 1편은 D-4 부터 관객이 있었다. */
  const series=[...runs.map(r=>({nm:r.nm, pts:r.pts, live:true, color:r.color})),
                ...upcoming.map(u=>({nm:u.title, pts:(preOf[u.title]||{}).pts||[], live:false,
                                     color:(preOf[u.title]||{}).color||mut}))];
  const allX=[...new Set(series.flatMap(sr=>sr.pts.map(p=>p.x)))].sort((a,b)=>a-b);
  const rows=allX.map(x=>{
    const row={x};
    series.forEach((sr,i)=>{
      const q=sr.pts.find(z=>z.x===x);
      row["d"+i]=q?q.d:null; row["a"+i]=q?q.audi:null; row["c"+i]=q?q.acc:null;
      row["r"+i]=q?q.rank:null; row["s"+i]=q?q.scrn:null;
      row["b"+i]=q?q.book:null;                      // 개봉 전: 예매관객
    });
    if(series.length>1 && row.c0)
      row.gap=(row.c1!=null)?((row.c1/row.c0-1)*100):null;
    return row;
  });
  /* 지표별로 두 편을 같은 칸에 나란히 —
     예전엔 편별로 열 묶음(1편 날짜·당일·누적… | 2편 날짜·예매·누적…)이라
     같은 지표끼리 화면 반대편에 떨어져 있어 비교하려면 눈이 왕복해야 했다.
     이제 열 = 지표, 칸 안 = [1편값 · 2편값] 색으로 구분. 범례는 표 제목에. */
  const duo=(get)=>r=>series.map((sr,i)=>{
    const v=get(r,sr,i);
    return `<span style="color:${sr.color};font-weight:700">${v==null?"—":v}</span>`;
  }).join(`<span style="color:var(--muted2);margin:0 4px">·</span>`);
  const cols=[
    {key:"x",label:"일차",l:true,
     render:r=>`<span class="ye">D${r.x>=0?"+":""}${r.x}</span>`
       +(r.x<0?`<span class="th-sub" style="margin-left:4px">시사회</span>`:"")},
    // 개봉 전 작품은 '당일'이 없다(순위 밖) — 그 자리는 예매관객으로 채우고 표시를 단다
    {key:"a0",label:"당일 관객",render:duo((r,sr,i)=> sr.live
       ? (r["a"+i]==null?null:fmt0(r["a"+i]))
       : (r["b"+i]==null?null:fmt0(r["b"+i])+`<span class="th-sub">예매</span>`))},
    {key:"c0",label:"누적 관객",render:duo((r,sr,i)=> r["c"+i]==null?null:fmt0(r["c"+i]))},
    ...(series.length>1?[{key:"gap",label:`누적 차이<span class="th-sub">2편÷1편</span>`,
       render:r=>r.gap==null?"—":`<span class="${cls(r.gap)}">${sign(r.gap,1)}%</span>`}]:[]),
    {key:"r0",label:"순위",render:duo((r,sr,i)=> r["r"+i]
       ? r["r"+i]+"위"+(sr.live?"":`<span class="th-sub">예매</span>`) : null)},
    {key:"s0",label:"스크린",render:duo((r,sr,i)=> r["s"+i]==null?null:fmt0(r["s"+i]))},
  ];
  makeTable(tbl, cols, rows, {key:"x",dir:1});     // 개봉 순서대로(오름차순)
  const tt=document.getElementById("movieTblTitle");
  if(tt) tt.innerHTML=`일별 상세 `+series.map(sr=>
    `<span style="margin-left:10px;font-size:12.5px"><span class="dot" style="background:${sr.color};width:9px;height:9px;display:inline-block;border-radius:50%;margin-right:4px"></span>`
    +`<span style="color:${sr.color}">${sr.nm}</span> <small style="color:var(--muted)">${sr.live?"":"개봉 전 · D<0 예매 기준"}</small></span>`).join("");
}

/* 종목 줄 + (주제가 둘 이상일 때만) 주제 줄 을 다시 그린다 */
/* 각 트렌드 계열의 소스별 '최신화 시각' — 맨 위 하나로 뭉치지 않고 계열마다 표시.
   소스마다 주기가 다르다: 네이버 검색·편입지표(스포티파이/스팀/유튜브 등)는 매일,
   구글·얀덱스·국가별 검색은 주 1회(월). srcName 으로 소스를 판별해 각 asOf 를 붙인다. */
const TREND_SRC_ASOF=[
  ["Spotify", ()=>(typeof SPOTIFY!=="undefined")&&SPOTIFY.asOf],
  ["SteamCharts", ()=>(typeof STEAM!=="undefined")&&STEAM.asOf],
  ["Steam", ()=>(typeof STEAM!=="undefined")&&STEAM.asOf],
  ["치지직", ()=>(typeof CHZZK!=="undefined")&&CHZZK.asOf],
  ["YouTube", ()=>(typeof YT!=="undefined")&&YT.asOf],
  ["트위치", ()=>(typeof TWITCH!=="undefined")&&TWITCH.asOf],
  ["앱스토어", ()=>(typeof APPRANK!=="undefined")&&APPRANK.asOf],
  ["한국관광", ()=>(typeof TOURISM!=="undefined")&&TOURISM.asOf],
  ["방한", ()=>(typeof TOURISM!=="undefined")&&TOURISM.asOf],
  ["써클", ()=>(typeof CIRCLE!=="undefined")&&CIRCLE.asOf],
  ["탑툰챗", ()=>(typeof TOPTOON!=="undefined")&&TOPTOON.asOf],
];
function trendFresh(G){
  if(!G) return "";
  const sn=G.srcName||"";
  for(const [k,fn] of TREND_SRC_ASOF){ if(sn.indexOf(k)>=0){ const v=fn(); if(v) return "갱신 "+fmtUpd(v); } }
  // 검색 트렌드(srcName 없음) — 네이버(매일)·구글/얀덱스(주1회)를 각각 표시
  const nav=(typeof TREND!=="undefined"&&(TREND.asOfNaver||TREND.asOf))||"";
  const full=(typeof TREND!=="undefined"&&TREND.asOfFull)||"";
  return "네이버 "+(nav?fmtUpd(nav):"—")+" · 구글/얀덱스 "+(full?fmtUpd(full):"주1회(월)");
}
function renderTrendSegs(){
  document.getElementById("trendGroupSeg").innerHTML=TREND_STOCKS
    .map(n=>`<button data-stk="${attr(n)}" class="${n===trendStock?'active':''}">${n}</button>`).join("");
  const subs=topicsOf(trendStock), row=document.getElementById("trendTopicRow");
  if(subs.length>1){
    row.style.display="";
    document.getElementById("trendTopicSeg").innerHTML=subs
      .map(g=>`<button data-grp="${attr(g)}" class="${g===trendGroup?'active':''}">${g}</button>`).join("");
  }else{
    row.style.display="none";
    document.getElementById("trendTopicSeg").innerHTML="";
  }
  // 출처 줄 — 그 주제가 실제로 두 출처를 다 가질 때만 띄운다.
  // 예전엔 항상 떠 있어서, 해외 국가별 주제에서 '네이버'를 눌러도
  // 구글 값을 복사해 둔 탓에 같은 그래프가 나왔다.
  const G=TREND.groups[trendGroup], avail=srcOfGroup(G);
  const srow=document.getElementById("trendSrcRow");
  if(G && avail.length>1){
    srow.style.display="";
    document.querySelectorAll("#trendSeg button").forEach(x=>
      x.classList.toggle("active", x.dataset.src===trendSrc));
  }else{
    srow.style.display="none";
  }
  // 기간 줄 — 그 주제가 일별·주별 둘 다 가질 때만 띄운다(롱텀↔숏텀 전환).
  const freqs=freqsOf(G), frow=document.getElementById("trendFreqRow");
  if(freqs.length>1){
    frow.style.display="";
    const shown=freqs.includes(trendFreq)?trendFreq:freqs[0];
    const LAB={week:"주별(롱텀)",date:"일별(숏텀)",month:"월별"};
    document.getElementById("trendFreqSeg").innerHTML=freqs.map(f=>
      `<button data-frq="${f}" class="${f===shown?'active':''}">${LAB[f]||f}</button>`).join("");
  }else{
    frow.style.display="none";
  }
  // 주제 줄이 숨겨져 있어도 지금 보는 게 뭔지 알 수 있게 제목으로 남긴다
  const kw=(G&&G.stack)?[]:((viewGroup(G)||{}).products||[]);   // 스택(회사 막대)은 아티스트 목록이 길어 제목에 안 붙임
  const fresh=trendFresh(G);
  document.getElementById("trendTopicNow").innerHTML= !trendStock ? ""
    : `${trendStock} — ${trendGroup}` + (kw.length? ` (${kw.join(" · ")})` : "")
      + (fresh? ` <span style="color:var(--muted);font-weight:600;font-size:12px">· ${fresh}</span>` : "");
}
document.getElementById("trendGroupSeg").addEventListener("click",e=>{
  const b=e.target.closest("button"); if(!b) return;
  trendStock=b.dataset.stk;
  trendGroup=topicsOf(trendStock)[0]||trendGroup;   // 종목이 바뀌면 첫 주제로
  renderTrendSegs(); drawTrend(); renderShop();
});
document.getElementById("trendTopicSeg").addEventListener("click",e=>{
  const b=e.target.closest("button"); if(!b) return;
  trendGroup=b.dataset.grp;
  renderTrendSegs(); drawTrend(); renderShop();
});
// 하이라이트 칩 클릭 → 해당 종목·주제로 이동
function selectTrend(stock, group){
  if(stock) trendStock=stock;
  if(group) trendGroup=group;
  renderTrendSegs(); drawTrend(); renderShop();
  const c=document.getElementById("trendChart"); if(c) c.scrollIntoView({block:"nearest",behavior:"smooth"});
}
/* 트렌드 탭 상단 '주목할 추이' — 모든 계열을 훑어 상위 몇 개를 칩으로(클릭 시 이동).
   앨범판매(스택)는 0→대량이라 %가 무의미 → 최신 기간 '신보'(그 아티스트 신고점, 10만장+)를
   절대수로. 그 외(검색·동접·청취자)는 기준선이 충분(자기 고점의 15%+)할 때만 % 를 쓴다. */
function renderTrendHighlights(){
  const box=document.getElementById("trendHighlights"); if(!box) return;
  const g2s={}; Object.entries(TREND_STOCK).forEach(([st,gs])=>gs.forEach(g=>{ if(!g2s[g]) g2s[g]=st; }));
  const U={date:{u:"전일",n:7,unit:"일"},week:{u:"전주",n:4,unit:"주"},month:{u:"전월",n:3,unit:"개월"}};
  const cands=[];
  Object.keys(TREND.groups).forEach(gname=>{
    const G=TREND.groups[gname], stock=g2s[gname]; if(!stock) return;
    const freq=G.freq||"week";
    if(G.stack){                                   // 앨범: 최신 기간 최다판매 아티스트가 신보면
      const prods=G.products||[], ser=G.naver||[], N=(G.months||[]).length; if(!N) return;
      let bi=-1,bv=0; prods.forEach((p,i)=>{ if(p==="기타")return; const v=(ser[i]||[])[N-1]||0; if(v>bv){bv=v;bi=i;} });
      if(bi<0||bv<100000) return;                  // 10만장 미만은 뉴스가 아니다
      const col=(ser[bi]||[]).filter(v=>v!=null);
      if(bv<Math.max(...col)*0.98) return;         // 최신이 그 아티스트 피크(=신보)일 때만
      cands.push({gname,stock,prod:prods[bi],album:true,val:bv,fmt:G.fmt,score:60+Math.min(40,bv/1e5)});
      return;
    }
    const src=(G.only==="google"||!G.naver)?"google":"naver", series=G[src]||G.naver||[], prods=G.products||[];
    let best=null;
    series.forEach((raw,pi)=>{
      const c=(raw||[]).filter(v=>v!=null); if(c.length<3) return;
      const last=c[c.length-1], prev=c[c.length-2];
      const back=Math.min(c.length-1,(U[freq]||U.week).n), b=c[c.length-1-back];
      const hi=Math.max(...c), lo=Math.min(...c); if(hi<=lo) return;
      if(last<hi*0.3 && !(prev>=hi*0.15 && last/prev-1<-0.4)) return;   // 저점 노이즈 제외(급락 예외)
      const wow=(prev>=hi*0.15)?(last/prev-1)*100:null;                 // 기준선이 너무 작으면 % 무의미
      const win=(b>=hi*0.15)?(last/b-1)*100:null;
      const isHigh=last>=hi;
      const mag=Math.max(Math.abs(wow||0),Math.abs(win||0));
      if(mag<20 && !isHigh) return;
      const score=mag+(isHigh?25:0);
      if(!best||score>best.score) best={prod:prods[pi]||gname,wow,win,isHigh,score,freq};
    });
    if(best) cands.push({gname,stock,...best});
  });
  cands.sort((a,b)=>b.score-a.score);
  const per={}, top=[];
  for(const c of cands){ if((per[c.stock]||0)>=2) continue; per[c.stock]=(per[c.stock]||0)+1; top.push(c); if(top.length>=5) break; }
  const shortG=g=>g.replace(/\([^)]*\)/,"").replace(/앨범판매/,"앨범").replace(/월간청취자/,"청취자").trim();
  box.innerHTML= !top.length ? "" :
    `<span style="align-self:center;font-size:12px;color:var(--muted);font-weight:700">📌 주목할 추이</span>`+
    top.map(c=>{
      let icon,chg,up;
      if(c.album){ icon="🚀"; up=true; chg="신보 "+(c.fmt?c.fmt(c.val):c.val.toLocaleString()); }
      else{
        const u=U[c.freq]||U.week, useWin=c.win!=null&&Math.abs(c.win)>=Math.abs(c.wow||0);
        const v=useWin?c.win:(c.wow!=null?c.wow:null);
        up=(v==null||v>=0); icon=(c.isHigh&&up)?"🚀":up?"🔥":"🧊";
        chg=v==null?"신고점":(useWin?`${u.n}${u.unit} `:`${u.u}비 `)+`${v>=0?"+":""}${v.toFixed(0)}%`;
      }
      return `<button onclick='selectTrend(${JSON.stringify(c.stock)},${JSON.stringify(c.gname)})' style="display:flex;gap:7px;align-items:center;background:var(--panel2);border:1px solid var(--line);border-radius:20px;padding:6px 12px;cursor:pointer;font-size:12.5px;color:var(--text)"><span>${icon}</span><b>${c.prod}</b><span style="color:${up?'var(--up)':'var(--down)'};font-weight:700">${chg}</span><span style="color:var(--muted);font-size:11px">${c.stock} · ${shortG(c.gname)}</span></button>`;
    }).join("");
  return top;   // 최상위 = 그날 가장 주목할 추이(트렌드 탭 진입 시 기본 표시)
}
renderTrendSegs(); renderShop(); renderTrendHighlights();
document.getElementById("trendSeg").addEventListener("click",e=>{
  const b=e.target.closest("button"); if(!b) return;
  trendSrc=b.dataset.src;
  document.querySelectorAll("#trendSeg button").forEach(x=>x.classList.toggle("active",x===b));
  drawTrend();
});
document.getElementById("trendFreqSeg").addEventListener("click",e=>{
  const b=e.target.closest("button"); if(!b) return;
  trendFreq=b.dataset.frq;                         // 주별↔일별 전환(전역 유지)
  renderTrendSegs(); drawTrend();
});
window.addEventListener("resize",()=>{
  if(document.querySelector('section[data-view="trends"]').classList.contains("active")) drawTrend();
});

/* ==== 수출 데이터 (관세청) ==== */
/* ===== 잠정치 수동 입력 (선택) =====
   관세청은 매월 11일·21일·익월 1일에 '수출입 현황(잠정)'을 발표합니다.
   품목 세분화(HS)·국가별 잠정치는 무료 API로 제공되지 않으므로, 확정치가 나오기 전
   빈 구간을 메우고 싶으면 발표된 전체 수치를 아래에 직접 적으면 됩니다.
   → 차트 끝에 '잠정' 흐린 막대로 붙고, 확정치가 수집되면 그 달은 확정값이 우선합니다.

   단위: 백만달러(USD mn). 품목명은 아래 items 의 label 과 정확히 같아야 합니다.
   (TRADE.items 의 label 과 정확히 같아야 한다 — 이름이 바뀌면 여기도 바꿀 것)

   출처: 관세청 수출입무역통계 https://unipass.customs.go.kr  (또는 산업부 월간 수출입 동향)

   예시 — 2026년 7월 잠정치가 발표됐다면:
     "화장품 전체": { "202607": 1120 },
     "라면":       { "202607": 180  },                                        */
/* 관세청 잠정치 (단위 백만달러) — 확정치보다 2주 먼저 나온다.
   공표: 1~10일분 11일 · 1~20일분 21일 · 월 전체 익월 1일.
   화면에선 점선 반투명 막대 + '잠정' 꼬리표로 그려지고,
   확정치가 들어오는 달은 자동으로 밀려난다(그 달 키를 지울 필요 없음).

   국가 코드는 TRADE 의 byCountry.code 와 같아야 한다("" = 전체).
   보도자료의 홍콩·동남아5국·유럽5국·중동5국은 대시보드에 대응 계열이 없어 넣지 않았다
   (유럽 9개국과 유럽 5국은 구성이 달라 섞으면 안 된다).

   ⚠️ 하위 분류(기초·색조)는 넣지 않았다. 기준이 다르기 때문이다.
      화장품 전체는 맞는다:  우리 3304  26.06 $1,088.5m  vs 보도자료 역산 $1,098m
      기초는 1.8배 차이:     우리 330499        $1,009.4m  vs 보도자료      $567.3m
      색조는 1.9배 차이:     우리 립+아이+파우더 $76.4m    vs 보도자료      $146.9m
      우리 기초+색조는 3304 를 거의 다 덮지만(1,085.8/1,088.5),
      보도자료는 기초+색조가 714 뿐이고 384 가 남는다 — HS 10단위로 더 잘게
      나눈 분류다(메이크업이 우리 '기초' 쪽에 섞여 있다).
      기준을 맞추기 전에 얹으면 같은 그래프에 다른 잣대를 겹치는 셈이라 뺐다. */

/* 실시간 집계 속보 (텔레그램) — 관세청 확정치보다 2주 빠르다. 단위 백만달러.
   위 TRADE_PRELIM 과 따로 두는 이유: 분류 기준이 우리 HS 6단위와 다르다.
     화장품 전체는 3304 와 맞지만, 기초·색조는 HS 10단위로 더 잘게 나눈 기준이라
     우리 '기초(330499)' 안에 메이크업이 섞여 있다. 같은 그래프에 겹치면 잣대가 섞인다.
   그래서 차트에는 기준이 맞는 '화장품 전체'만 얹고(TRADE_PRELIM),
   레터는 이 블록을 그대로 읽어 발표된 형태 그대로 전한다.
   yy·mm 은 원문에 있던 값을 그대로 옮긴 것(우리가 다시 계산하지 않는다). */


(function(){
  const has = TRADE.items && TRADE.items.length && TRADE.months.length;
  document.getElementById("tradeUI").style.display   = has ? "" : "none";
  document.getElementById("tradeEmpty").style.display= has ? "none" : "";
  if(!has) return;
  (function(){
    const last=TRADE.months[TRADE.months.length-1];
    const ym=`${last.slice(0,4)}년 ${+last.slice(4,6)}월`;
    document.getElementById("tradeAsOfBadge").textContent=
      `확정치 ${ym}까지 · 당월 잠정치는 미포함`;
  })();

  let itemIdx=0, cIdx=0, period="m", view="chart";
  const chips=(el,arr,cls)=>{ el.innerHTML=arr.map((t,i)=>
    `<button class="chip ${cls||''}" data-i="${i}">${t}</button>`).join(""); };

  /* 품목 2단 선택 — 트렌드 탭과 같은 구조.
     첫 줄에서 품목군을, 둘째 줄에서 그 군의 품목을 고른다.
     '누르면 펼쳐지는' 방식을 써 봤는데 숨어 있는 게 있는지 자체가 안 보여서 걷어냈다.
     두 줄이면 모든 선택지가 항상 눈에 있다. */
  const ITEM_GROUPS=[
    ["화장품",   ["화장품 전체","기초","색조 합계","기타 화장품류","향수·화장수","매니큐어류"]],
    ["색조 상세", ["색조 합계","색조-립","색조-아이","색조-파우더"]],
    ["마스크팩", ["마스크팩 전체","마스크팩","기타 조제화장품"]],
    ["헤어",     ["헤어 총계","샴푸","린스"]],
    ["음식료",   ["라면","만두"]],
  ];
  let groupIdx=0;
  const groupOf=lbl=>{const g=ITEM_GROUPS.findIndex(([,ls])=>ls.includes(lbl));return g<0?0:g;};

  chips(document.getElementById("tradeItemChips"), TRADE.items.map(i=>i.label));
  let curRel=null;                                   // 종목을 골랐을 때 그 종목의 관련 품목 목록
  function paintItemChips(){
    // 품목군 줄
    const gEl=document.getElementById("tradeGroupChips");
    if(gEl && !gEl.childElementCount)
      gEl.innerHTML=ITEM_GROUPS.map(([g],i)=>`<button class="chip" data-g="${i}">${g}</button>`).join("");
    if(gEl) [...gEl.children].forEach((b,i)=>{
      b.classList.toggle("active", i===groupIdx);
      b.style.display=curRel?"none":"";              // 종목 선택 중엔 군 줄을 감춘다
    });
    // 품목 줄 — 선택된 군의 품목만
    const cur=ITEM_GROUPS[groupIdx][1];
    document.querySelectorAll("#tradeItemChips .chip").forEach((b,i)=>{
      const it=TRADE.items[i], lbl=it.label;
      const show=curRel? curRel.includes(lbl) : (!it.region && cur.includes(lbl));
      b.style.display=show?"":"none";
      b.classList.remove("chip-sub");
      b.textContent=lbl;
    });
  }
  function countryList(){ return TRADE.items[itemIdx].byCountry.map(c=>c.name); }
  function paintChips(){
    paintItemChips();                                // 선택이 바뀌면 펼침 상태도 다시 그린다
    document.querySelectorAll("#tradeItemChips .chip").forEach((b,i)=>b.classList.toggle("active",i===itemIdx));
    document.querySelectorAll("#tradeCountryChips .chip").forEach((b,i)=>b.classList.toggle("active",i===cIdx));
  }

  /* ── 종목별 수출 프로필 ────────────────────────────────
     items: 관련 관세 HS 품목(라벨) · mkt: 주력 수출시장(국가코드, 우선순위순) · note: 한줄 설명
     시장 비중은 공개 IR·언론(2025) 기준의 상대적 주력도 — 절대 비중이 아니라 '어디 위주로 파는가' 표시용 */
  const ALL_COS=["화장품 전체","기초","색조 합계","기타 화장품류","마스크팩","향수·화장수"];
  // 파마리서치는 리쥬란·필러가 '기타화장품 3304.99.9000'(=기초 330499)으로 통관되어 그 코드로 잡힌다
  //   (시장이 강릉 기타화장품 수출을 리쥬란 프록시로 사용 · 타 기초제품과 혼재하는 참고 지표).
  // 앨엔씨바이오(메가덤=조직이식재·HS3001, 중국 미포착)·그래피(치과 3D레진·미미)는 3304가 아니고
  //   주력 수출을 분리해낼 코드가 없어 제외한다.
  const CO_TRADE={
    "에이피알":   {items:ALL_COS,                     mkt:["US","JP"],       note:"메디큐브 등 브랜드 수출 — 미국·일본 중심"},
    "아모레퍼시픽":{items:ALL_COS,                     mkt:["US","JP","CN"],  note:"미국·일본 확대, 중국 비중은 축소 흐름"},
    "LG생활건강": {items:ALL_COS,                     mkt:["CN","US","JP"],  note:"해외 중 중국 비중 최대, 북미·일본 성장"},
    "달바글로벌":  {items:["화장품 전체","기초"],        mkt:["JP","US","EU9"], note:"선케어·앰플 — 일본이 최대, 북미·유럽 확장"},
    "한국콜마":   {items:["화장품 전체","기초","색조-립","색조-아이","색조-파우더"], mkt:["US","CN"], note:"ODM — 기초 스킨케어 중심, 미국·중국"},
    "실리콘투":   {items:ALL_COS,                     mkt:["US","EU9"],      note:"K뷰티 역직구 — 미국 최대, 유럽·신흥국 급증"},
    "코스맥스":   {items:["화장품 전체","색조-립","색조-아이","색조-파우더","기초"], mkt:["CN","US"], note:"ODM — 색조 메이크업 강점, 중국 최대·미국(+46%)·동남아 확대"},
    "제닉":      {items:["마스크팩 전체","마스크팩","화장품 전체"],   mkt:["CN","US"],       note:"마스크팩 ODM — 중국·미국"},
    "파마리서치": {items:["리쥬란(강릉 기타화장품)"],     mkt:[],                note:"리쥬란·필러 = 강릉공장 기타화장품(330499) 제조지 기준 프록시 (국가 구분 없음)"},
    "티앤엘":    {items:["창상피복재(안성)"],             mkt:[],                note:"미티패치·하이드로콜로이드 창상피복재 = 안성공장 제조지 기준 프록시 (미국 중심 · HERO/처치앤드와이트 ODM)"},
    "삼양식품":   {items:["라면"],                     mkt:["US","CN","EU9"], note:"불닭 — 미국·중국 양대 시장, 유럽 확대"},
    "농심":      {items:["라면"],                     mkt:["US","CN","JP"],  note:"신라면 — 북미·중국·일본 (현지 생산 병행)"},
    "CJ제일제당":  {items:["만두"],                     mkt:["US","EU9","JP"], note:"비비고 만두 — 미국 최대, 독일·영국 등 유럽 확대"},
  };
  const coOf=nm=>CO_TRADE[nm]||null;
  const relItems=nm=>{ const c=CO_TRADE[nm]; return c?c.items:[]; };   // 없으면 [] (수출 관련 없음)

  let curMkts=[];   // 현재 종목의 주력 시장(국가코드) — 국가 칩 ★ 표시에 사용

  /* 국가 칩에 주력 시장 ★ 표시 */
  function markMarkets(){
    const bc=TRADE.items[itemIdx].byCountry;
    [...document.querySelectorAll("#tradeCountryChips .chip")].forEach((b,i)=>{
      const code=(bc[i]||{}).code, isKey=curMkts.includes(code);
      b.classList.toggle("key",isKey);
      const nm=(bc[i]||{}).name||b.textContent.replace(/^★\s*/,"");
      b.textContent=(isKey?"★ ":"")+nm;
    });
  }

  /* 종목 선택 -> 관련 HS 품목 필터 + 주력 시장 표시 */
  function applyCompany(nm){
    const co=nm?coOf(nm):null, rel=co?co.items:null;
    curRel=rel;                       // 계층 표시가 이 값을 보고 접을지 말지 정한다
    paintItemChips();
    if(rel && !rel.includes(TRADE.items[itemIdx].label)){   // 선택 품목이 숨으면 관련 첫 품목으로
      const first=TRADE.items.findIndex(it=>rel.includes(it.label));
      if(first>=0) itemIdx=first;
    } else if(!rel && TRADE.items[itemIdx].region){         // 전체보기인데 지역 프록시가 선택돼 있으면 되돌림
      itemIdx=0;
    }
    groupIdx=groupOf(TRADE.items[itemIdx].label);           // 군 줄이 다시 나타날 때 어긋나지 않게
    curMkts=co?co.mkt:[];
    rebuildCountry();                                       // 국가 칩 재생성 + ★ 표시
    const bc=TRADE.items[itemIdx].byCountry;
    if(curMkts.length){                                     // 주력 시장(1순위) 자동 선택
      const pi=bc.findIndex(c=>c.code===curMkts[0]); cIdx=pi>=0?pi:0;
    } else if(cIdx>=bc.length) cIdx=0;                      // 지역 프록시 등 국가 수가 다르면 보정
    const noteEl=document.getElementById("tradeCoNote");
    if(co){
      const names=curMkts.map(cd=>(bc.find(c=>c.code===cd)||{}).name).filter(Boolean);
      const mk=names.length?`　<span style="color:var(--muted2)">주력 시장 ★ ${names.join(" · ")}</span>`:"";
      noteEl.innerHTML=`<b>${nm}</b> · ${co.note}${mk}`;
      noteEl.style.display="";
    } else noteEl.style.display="none";
    paintChips(); draw();
  }

  (function initStockSel(){
    const sel=document.getElementById("tradeStock"); if(!sel) return;
    const order={"화장품":0,"미용":1,"음식료":2};
    const named=R.filter(r=>(relItems(r.name)||[]).length)   // 관련 품목이 있는 종목만
                 .sort((a,b)=>(order[a.sub]??9)-(order[b.sub]??9));
    sel.innerHTML=`<option value="">전체 품목 보기</option>`
      +named.map(r=>`<option value="${r.name}">${r.name} · ${r.sub}</option>`).join("");
    sel.addEventListener("change",e=>applyCompany(e.target.value));
  })();

  /* 월 -> 분기 집계 */
  function agg(){
    const it=TRADE.items[itemIdx], c=it.byCountry[cIdx];
    let M=TRADE.months.slice(), V=c.exp.slice(), P=M.map(()=>false), PD=M.map(()=>0);
    /* 잠정치 덧붙이기 (단위 백만달러).
       확정치가 이미 있는 달은 건너뛴다 — 관세청 확정치가 들어오면 잠정치가 저절로 밀려난다.
       두 가지 형태를 받는다:
         "화장품 전체": {"202607": 1098.0}                     ← 전체만
         "화장품 전체": {"202607": {"": 1098.0, "CN": 136.6}}  ← 국가별
       예전엔 앞의 형태만 받아 '전체' 국가에서만 보였다. 보도자료가 국가별도 주므로 연다. */
    const pv=(typeof TRADE_PRELIM!=="undefined"?TRADE_PRELIM:{})[it.label];
    if(pv){
      Object.keys(pv).sort().forEach(ym=>{
        // '그 달이 목록에 있는지'가 아니라 '확정치 값이 실제로 있는지'를 본다.
        // 관세청 API 는 아직 집계 안 된 달도 빈 값으로 돌려주는데, 월 존재만 보고
        // 건너뛰면 잠정치가 통째로 가려진다(실제로 202607 이 그랬다).
        const j=M.indexOf(ym);
        if(j>=0 && V[j]!=null) return;
        const row=pv[ym];
        const v=(row!==null&&typeof row==="object")? row[c.code] : (c.code===""?row:undefined);
        if(v==null) return;                              // 그 국가 잠정치가 없으면 안 그린다
        // _d = '그 달 며칠까지의 누적인가'. 관세청 잠정은 10일·20일·월말 순으로 나오는데,
        // 20일까지 누적을 월 막대로 그대로 그리면 그 달이 실제보다 작아 보이고
        // YoY(12개월 전 '월 전체' 대비)까지 틀어진다. 그래서 부분월임을 들고 다닌다.
        const pd=(row!==null&&typeof row==="object")? (row._d||0) : 0;
        if(j>=0){ V[j]=v*1e6; P[j]=true; PD[j]=pd; }     // 빈 확정치 자리를 잠정치로 채운다
        else { M.push(ym); V.push(v*1e6); P.push(true); PD.push(pd); }   // 백만달러 -> 달러
      });
    }
    /* 값이 없는 뒤쪽 달은 잘라낸다.
       관세청 API 가 아직 집계 안 된 달을 빈 값으로 주는데, 그대로 두면 그리는 쪽에서
       null 을 0 으로 바꿔 마지막에 바닥 막대가 하나 생긴다 — 수출이 0으로 무너진 것처럼 읽힌다.
       (잠정치가 채운 달은 값이 있으므로 남는다) */
    while(V.length && V[V.length-1]==null){ V.pop(); M.pop(); P.pop(); PD.pop(); }
    if(period==="m") return {labels:M.map(m=>`${m.slice(2,4)}.${m.slice(4,6)}`), vals:V, keys:M, prelim:P, pday:PD};
    const buckets=new Map();
    M.forEach((m,i)=>{
      const q=`${m.slice(0,4)}Q${Math.floor((+m.slice(4,6)-1)/3)+1}`;
      if(!buckets.has(q)) buckets.set(q,[]);
      if(V[i]!=null && !PD[i]) buckets.get(q).push(V[i]);   // 부분월은 분기 합계에서 뺀다
    });
    const keys=[...buckets.keys()];
    return {labels:keys.map(k=>`${k.slice(2,4)}.${k.slice(4)}`), keys,
            vals:keys.map(k=>{const a=buckets.get(k);return a.length?a.reduce((x,y)=>x+y,0):null;}),
            prelim:keys.map(()=>false), pday:keys.map(()=>0)};
  }
  /* YoY: 월별은 12개월 전, 분기별은 4분기 전 */
  function yoyOf(vals){
    const lag = period==="m" ? 12 : 4;
    return vals.map((v,i)=> (i>=lag && v!=null && vals[i-lag]) ? (v/vals[i-lag]-1)*100 : null);
  }

  function draw(){
    const it=TRADE.items[itemIdx], c=it.byCountry[cIdx];
    const {labels,vals,prelim=[],pday=[]}=agg(), yoy=yoyOf(vals);
    // 부분월(20일까지 등)은 전년 '월 전체'와 견주면 무조건 감소로 보인다 — YoY 를 비운다.
    pday.forEach((d,i)=>{ if(d) yoy[i]=null; });
    document.getElementById("tradeChartTitle").textContent=`${it.label} · ${c.name}`;
    /* 집계 기준(HS 부호)을 차트 오른쪽 아래에 적는다.
       hs 는 수집기가 넣어 준 값으로, 합계 품목이면 '+'로 이어져 있다.
       6자리와 10자리가 값이 두 배씩 차이 나므로(330499 vs 3304991000)
       화면에 없으면 나중에 무엇을 본 건지 되짚을 수가 없다. */
    const hsEl=document.getElementById("tradeHs");
    if(hsEl){
      const codes=String(it.hs||"").split("+").filter(Boolean);
      hsEl.innerHTML = codes.length
        ? `HS ${codes.map(x=>`<code>${x}</code>`).join(" + ")}`
          + (it.region?` · 제조지 기준`:"")
          + (it.note?`<br><span style="opacity:.85">${it.note}</span>`:"")
        : (it.note||"");
    }
    const box=document.getElementById("tradeChart");
    const W=box.clientWidth||1000, H=380, pad={l:62,r:56,t:18,b:34};
    const shown=vals.map(v=>v==null?0:v/1e6);             // 달러 -> 백만달러
    const maxV=Math.max(...shown,1)*1.15;
    const ys=v=>H-pad.b-(v/maxV)*(H-pad.t-pad.b);
    const xs=i=>pad.l+(i+0.5)/labels.length*(W-pad.l-pad.r);
    const bw=(W-pad.l-pad.r)/labels.length*0.62;
    // YoY 축은 고정 -60~+180% (스텝 60) — 종목·국가·품목을 바꿔도 기울기 기준이 동일하게.
    // 범위를 벗어나는 값(소국 기저효과 등)은 가장자리에 삼각형으로 표시한다.
    const yMin=-60, yMax=180;
    const clampY=v=>Math.max(yMin,Math.min(yMax,v));
    const yy=v=>H-pad.b-((clampY(v)-yMin)/(yMax-yMin))*(H-pad.t-pad.b);
    const gc=getComputedStyle(document.documentElement).getPropertyValue('--line');
    const mut=getComputedStyle(document.documentElement).getPropertyValue('--muted');
    let s=`<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" font-family="inherit">`;
    for(let g=0;g<=4;g++){
      const y=pad.t+(H-pad.t-pad.b)*g/4, v=maxV*(1-g/4), r=yMax-(yMax-yMin)*g/4;
      s+=`<line x1="${pad.l}" y1="${y}" x2="${W-pad.r}" y2="${y}" stroke="${gc}"/>`;
      s+=`<text x="${pad.l-8}" y="${y+4}" text-anchor="end" font-size="10.5" fill="${mut}">${fmt0(v)}</text>`;
      s+=`<text x="${W-pad.r+8}" y="${y+4}" font-size="10.5" fill="${mut}">${fmt(r,0)}%</text>`;
    }
    labels.forEach((L,i)=>{
      const h=H-pad.b-ys(shown[i]);
      s+=`<rect x="${(xs(i)-bw/2).toFixed(1)}" y="${ys(shown[i]).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(0,h).toFixed(1)}" rx="2" fill="var(--warn)" opacity="${prelim[i]?.32:.75}"${prelim[i]?' stroke="var(--warn)" stroke-dasharray="3 2"':''}></rect>`;
      s+=`<text x="${xs(i).toFixed(1)}" y="${H-pad.b+16}" text-anchor="middle" font-size="10" fill="${mut}">${L}</text>`;
    });
    const pts=yoy.map((v,i)=>v==null?null:`${xs(i).toFixed(1)},${yy(v).toFixed(1)}`).filter(Boolean);
    if(pts.length>1) s+=`<polyline points="${pts.join(' ')}" fill="none" stroke="var(--muted)" stroke-width="1.6"/>`;
    yoy.forEach((v,i)=>{ if(v==null) return;
      const cx=+xs(i).toFixed(1), cy=+yy(v).toFixed(1), col=v>=0?'var(--up)':'var(--down)';
      if(v>yMax||v<yMin){   // 축 밖 — 방향 삼각형(캐럿)
        const up=v>yMax;
        const tri=up?`M${cx-4.5},${cy+4} L${cx+4.5},${cy+4} L${cx},${cy-3.5} Z`
                    :`M${cx-4.5},${cy-4} L${cx+4.5},${cy-4} L${cx},${cy+3.5} Z`;
        s+=`<path d="${tri}" fill="${col}"><title>YoY ${sign(v,1)}% (축 범위 밖)</title></path>`;
      } else {
        s+=`<circle cx="${cx}" cy="${cy}" r="3.4" fill="${col}"><title>YoY ${sign(v,1)}%</title></circle>`;
      }});
    s+=`<text x="16" y="${H/2}" text-anchor="middle" font-size="11" fill="${mut}" transform="rotate(-90 16 ${H/2})">수출액 (백만달러)</text>`;
    s+="</svg>";
    box.innerHTML=s;
    // ── 토스식 호버 툴팁: 커서를 대면 그 달의 수출액·YoY 가 즉시 뜬다 ──
    box.style.position="relative";
    box.insertAdjacentHTML("beforeend",`<div class="chart-guide" id="tradeGuide"></div><div class="chart-tip" id="tradeTip"></div>`);
    const tip=box.querySelector("#tradeTip"), guide=box.querySelector("#tradeGuide");
    const svg=box.querySelector("svg");
    const hideTip=()=>{ tip.style.display="none"; guide.style.display="none"; };
    box.onmousemove=(e)=>{
      const m=svg&&svg.getScreenCTM();
      if(!m||!m.a){ hideTip(); return; }                              // 미표시/0폭 방어
      // 마우스 화면좌표 → viewBox 좌표. getScreenCTM 이 스케일·레터박스(가운데 여백)까지 보정한다.
      const pt=svg.createSVGPoint(); pt.x=e.clientX; pt.y=e.clientY;
      const p=pt.matrixTransform(m.inverse());
      const plotW=W-pad.l-pad.r;
      // 플롯 영역(축 안쪽)에 있을 때만 — 제목·축 라벨·여백 위에선 안 뜬다
      if(p.x<pad.l||p.x>W-pad.r||p.y<pad.t||p.y>H-pad.b){ hideTip(); return; }
      let i=Math.round((p.x-pad.l)/plotW*labels.length-0.5);
      if(i<0||i>=labels.length){ hideTip(); return; }
      const v=shown[i], y=yoy[i];
      tip.innerHTML=`<div class="tt-h">${labels[i]}${prelim[i]?`<span style="color:var(--warn);font-weight:700;font-size:10.5px">잠정${pday[i]?` ${+labels[i].slice(3)}/1~${pday[i]}일`:''}</span>`:''}</div>`
        +`<div class="tt-r"><span class="k">수출액</span><span class="v">${v==null?'—':fmt(v,1)+'<span style="color:var(--muted);font-weight:600;font-size:11px"> 백만$</span>'}</span></div>`
        +`<div class="tt-r"><span class="k">YoY</span><span class="v ${y==null?'':cls(y)}">${y==null?'—':sign(y,1)+'%'}</span></div>`;
      tip.style.display="block";
      // 가이드선: 열 중심(viewBox xs(i))을 같은 변환으로 화면 px 에 매핑 → 커서와 정확히 일치
      const rc=box.getBoundingClientRect();
      const a=svg.createSVGPoint(); a.x=xs(i); a.y=pad.t; const as=a.matrixTransform(m);
      const b=svg.createSVGPoint(); b.x=xs(i); b.y=H-pad.b; const bs=b.matrixTransform(m);
      guide.style.display="block";
      guide.style.left=(as.x-rc.left).toFixed(1)+"px";
      guide.style.top=(as.y-rc.top).toFixed(1)+"px";
      guide.style.height=Math.abs(bs.y-as.y).toFixed(1)+"px";
      const tw=tip.offsetWidth||140, px=e.clientX-rc.left;
      tip.style.left=((px+16+tw>rc.width)? Math.max(4,px-tw-14) : px+16).toFixed(1)+"px";
      tip.style.top=Math.max(4,(e.clientY-rc.top)-tip.offsetHeight-10).toFixed(1)+"px";
    };
    box.onmouseleave=hideTip;
    document.getElementById("tradeLegend").innerHTML=
      `<div class="li"><span class="dot" style="background:var(--warn)"></span>수출액 (백만달러)</div>`+
      `<div class="li"><span class="dot" style="background:var(--up)"></span>YoY (%)</div>`+
      (prelim.some(Boolean)?`<div class="li"><span class="dot" style="background:var(--warn);opacity:.35"></span>잠정치(관세청 발표)${pday.some(Boolean)?` · 마지막 달은 ${pday.filter(Boolean).slice(-1)[0]}일까지 누적(YoY 생략)`:''}</div>`:"")+
      `<div class="li" style="margin-left:auto"><small>${it.note}</small></div>`;
    // 테이블
    makeTable(document.getElementById("tradeTable"),[
      {key:"L",label:period==="m"?"월":"분기",l:true,render:r=>r.L},
      {key:"v",label:"수출액(백만달러)",render:r=>r.v==null?"—":fmt(r.v,1)},
      {key:"y",label:"YoY",render:r=>r.y==null?"—":`<span class="${cls(r.y)}">${sign(r.y,1)}%</span>`},
    ], labels.map((L,i)=>({L,v:shown[i]||null,y:yoy[i]})), {key:"L",dir:-1});
    const eu9=(TRADE.items[itemIdx].byCountry.find(c=>c.code==="EU9")||{});
    const regionItem=TRADE.items[itemIdx].region;
    document.getElementById("tradeNote").innerHTML=
      `단위 백만달러(FOB 신고금액). YoY는 ${period==="m"?"전년 동월":"전년 동분기"} 대비, `+
      `<b>축 -60~+180% 고정</b>(비교 일관성 · 범위 밖은 ▲▼로 표시). `+
      (regionItem
        ? `제조장소 우편번호 기준 지역 집계(${TRADE.items[itemIdx].byCountry[0].name}) — 국가 구분 없음. `
        : `유럽 9개국은 ${eu9.members?.join("·")||"영국·프랑스·독일·네덜란드·폴란드·이탈리아·스페인·스웨덴·벨기에"} 합계. `)+
      `수집 ${TRADE.asOf}`;
  }
  function rebuildCountry(){ chips(document.getElementById("tradeCountryChips"), countryList(), "alt"); markMarkets(); }
  function refresh(){ paintChips(); draw(); }

  document.getElementById("tradeGroupChips").addEventListener("click",e=>{
    const b=e.target.closest(".chip"); if(!b) return;
    groupIdx=+b.dataset.g;
    // 군을 바꾸면 그 군의 첫 품목을 자동 선택 — 안 하면 이전 군의 품목이 그려진 채 남는다
    const first=ITEM_GROUPS[groupIdx][1][0];
    const i=TRADE.items.findIndex(it=>it.label===first);
    if(i>=0){ itemIdx=i; cIdx=Math.min(cIdx, TRADE.items[itemIdx].byCountry.length-1); }
    rebuildCountry(); refresh();
  });
  document.getElementById("tradeItemChips").addEventListener("click",e=>{
    const b=e.target.closest(".chip"); if(!b) return;
    itemIdx=+b.dataset.i; cIdx=Math.min(cIdx, TRADE.items[itemIdx].byCountry.length-1);
    groupIdx=groupOf(TRADE.items[itemIdx].label);   // 품목이 어느 군에 속하는지 동기화
    rebuildCountry(); refresh();
  });
  document.getElementById("tradeCountryChips").addEventListener("click",e=>{
    const b=e.target.closest(".chip"); if(!b) return; cIdx=+b.dataset.i; refresh();
  });
  document.getElementById("tradePeriodSeg").addEventListener("click",e=>{
    const b=e.target.closest("button"); if(!b) return; period=b.dataset.p;
    document.querySelectorAll("#tradePeriodSeg button").forEach(x=>x.classList.toggle("active",x===b));
    draw();
  });
  document.getElementById("tradeViewSeg").addEventListener("click",e=>{
    const b=e.target.closest("button"); if(!b) return; view=b.dataset.v;
    document.querySelectorAll("#tradeViewSeg button").forEach(x=>x.classList.toggle("active",x===b));
    document.querySelector("#tradeUI .chart-box").style.display = view==="chart"?"":"none";
    document.getElementById("tradeTableWrap").style.display     = view==="table"?"":"none";
  });
  rebuildCountry(); refresh();
  window.addEventListener("resize",()=>{ if(document.querySelector('section[data-view="altdata"]').classList.contains("active")) draw(); });
  window.__drawTrade=draw;
})();

/* ==== Stock detail drawer ==== */
const byName=Object.fromEntries(R.map(r=>[r.name,r]));
const thesisByName=Object.fromEntries(DATA.records.map(r=>[r.name,r.thesis]));
function openStock(name){
  const r=byName[name]; if(!r) return;
  const trendTopics=topicsOf(name);   // 관련 트렌드 주제(데이터 있는 것만)
  /* 연간·분기 실적은 전부 네이버 API 시계열(LIVE.cons.series). 엑셀 유래 데이터는 쓰지 않는다.
     series 원소: {k:"202412", t:"2024.12.", e:컨센여부, rev, op, np, opm, eps, bps, pbr} */
  const CS=(LIVE.stocks[name]||{}).cons||{};
  const A=((CS.year||{}).series||[]).map(s=>
    ({y:s.t.slice(0,4)+(s.e?"E":"A"), rev:s.rev, op:s.op, eps:s.eps, opm:s.opm}));
  // 27E 는 무료 API 에 없다. 엑셀 컨센(rev27·op27·eps27)을 마지막 열로 덧붙인다.
  if(r.rev27!=null||r.op27!=null||r.eps27!=null)
    A.push({y:"2027E", rev:r.rev27, op:r.op27, eps:r.eps27, opm:null});
  const Q=((CS.quarter||{}).series||[]).map(s=>
    ({q:`${Math.ceil(+s.k.slice(4,6)/3)}Q${s.k.slice(2,4)}${s.e?"E":""}`, rev:s.rev, op:s.op}));
  // 전기가 0 이하면 증가율이 무의미하므로 표시하지 않는다(적자전환 등)
  const yoy=(arr,key,i)=> (i>0 && arr[i-1][key]>0 && arr[i][key]!=null)
    ? (arr[i][key]/arr[i-1][key]-1)*100 : null;
  const opmOf=a=> (a.opm!=null? a.opm : (a.rev? a.op/a.rev*100 : null));
  const th=thesisByName[name];
  let html=`<button class="close" id="drawerClose" title="닫기">×</button>
    <div class="dsec">${r.sector} · ${r.sub}${r.code?` · ${r.code} ${r.mkt||''}`:''}</div>
    <div class="dnm">${stockLogo(name)}${name} ${ratingBadge(r.score)} ${pickPill(r)}
      ${r.chgPct!=null?`<span class="c ${cls(r.chgPct)}" style="font-size:14px">${sign(r.chgPct,2)}%</span>`:''}</div>
    ${(r.pick2&&th)?`<div class="pick-why"><b>${r.pick2} 근거</b> ${th}</div>`:(th?`<div class="dthesis">${th}</div>`:'')}
    ${trendTopics.length?`<div class="d-actions"><button class="tbtn" id="goTrend" type="button">📈 관련 트렌드 보기<span class="cnt">${trendTopics.length}</span></button></div>`:''}
    <div class="val-grid">
      <div class="vg"><div class="l">현재가</div><div class="v">${won(r.price)}</div></div>
      <div class="vg"><div class="l">목표가(컨센)</div><div class="v">${won(r.target)}</div></div>
      <div class="vg"><div class="l">상승여력</div><div class="v ${cls(r.upsideCons)}">${sign(r.upsideCons)}%</div></div>
      <div class="vg"><div class="l">시가총액</div><div class="v">${eok(mcJo(r),10000)}억</div></div>
      <div class="vg"><div class="l">적정시총(당사)</div><div class="v">${eok(r.fairMktcap,10)}억</div></div>
      <div class="vg"><div class="l">당사 상승여력</div><div class="v ${cls(r.upsideOwn)}">${sign(r.upsideOwn)}%</div></div>
      <div class="vg"><div class="l">PER(현)</div><div class="v">${r.perLive>0?fmt(r.perLive)+'x':'—'}</div></div>
      <div class="vg"><div class="l">TTM PBR</div><div class="v">${r.pbr>0?fmt(r.pbr)+'x':'—'}</div></div>
      <div class="vg"><div class="l">26E PBR</div><div class="v">${r.pbr26>0?fmt(r.pbr26)+'x':'—'}</div></div>
      <div class="vg"><div class="l">배당수익률</div><div class="v">${r.divYield>0?fmt(r.divYield)+'%':'—'}</div></div>
      <div class="vg"><div class="l">26E PER</div><div class="v">${r.per26>0?fmt(r.per26)+'x':'—'}</div></div>
      <div class="vg"><div class="l">27E PER</div><div class="v">${r.per27>0?fmt(r.per27)+'x':'—'}</div></div>
      <div class="vg"><div class="l">외국인 보유</div><div class="v">${r.foreign>0?fmt(r.foreign)+'%':'—'}</div></div>
    </div>
    ${r.w52pos!=null?`<div class="d-h">52주 레인지</div>
      <div class="w52" style="gap:10px">
        <span class="lbl">${won(r.w52l)}</span>
        <div class="bar" style="height:7px"><i style="left:${Math.max(0,Math.min(100,r.w52pos)).toFixed(0)}%;height:15px;top:-4px"></i></div>
        <span class="lbl">${won(r.w52h)}</span>
        <span class="lbl" style="font-weight:700;color:var(--accent)">${fmt(r.w52pos,0)}%</span>
      </div>`:''}
    <div class="d-h">연간 실적 추이 (억 원)</div>
    <table class="mini-tbl"><thead><tr><th class="l">구분</th>${A.map(a=>`<th class="ye">${a.y}</th>`).join('')}</tr></thead><tbody>
      <tr><td class="l">매출액</td>${A.map(a=>`<td>${eok(a.rev)}</td>`).join('')}</tr>
      <tr class="sub-row"><td class="l">매출 YoY</td>${A.map((a,i)=>{const v=yoy(A,'rev',i);return `<td>${v==null?'—':`<span class="${cls(v)}">${sign(v,0)}%</span>`}</td>`;}).join('')}</tr>
      <tr><td class="l">영업이익</td>${A.map(a=>`<td>${eok(a.op)}</td>`).join('')}</tr>
      <tr class="sub-row"><td class="l">영업이익률</td>${A.map(a=>{const v=opmOf(a);return `<td>${v==null?'—':fmt(v)+'%'}</td>`;}).join('')}</tr>
      <tr class="sub-row"><td class="l">영업익 YoY</td>${A.map((a,i)=>{const v=yoy(A,'op',i);return `<td>${v==null?'—':`<span class="${cls(v)}">${sign(v,0)}%</span>`}</td>`;}).join('')}</tr>
      <tr><td class="l">EPS(원)</td>${A.map(a=>`<td>${a.eps!=null?fmt0(a.eps):'—'}</td>`).join('')}</tr>
      <tr class="sub-row"><td class="l">EPS 증가율</td>${A.map((a,i)=>{const v=yoy(A,'eps',i);return `<td>${v==null?'—':`<span class="${cls(v)}">${sign(v,0)}%</span>`}</td>`;}).join('')}</tr>
    </tbody></table>
    <div class="d-h">분기 실적 추이 — 매출(막대)·OPM(선)</div><div id="qChart"></div>
    ${(()=>{const rs=(LIVE.researches||[]).filter(x=>x.co===name).slice(0,6);
      return rs.length?`<div class="d-h">최근 증권사 리포트</div>
      <table class="mini-tbl"><tbody>${rs.map(x=>`<tr>
        <td class="l">${x.date?`${x.date.slice(4,6)}/${x.date.slice(6,8)}`:''}</td>
        <td class="l" style="white-space:normal">${x.title}</td>
        <td class="l" style="color:var(--muted)">${x.broker}</td></tr>`).join('')}</tbody></table>`:'';})()}
    <p class="note">A는 확정 실적, E는 컨센서스 추정(2027E는 엑셀 컨센). 단위 억 원.
      실적·추정·현재가·PER·PBR·배당·52주·외국인·목표주가 전부 네이버 금융 수집(${LIVE.asOf}).
      적정시총만 당사 견적.</p>`;
  document.getElementById("drawerInner").innerHTML=html;
  drawQuarter(Q);
  const gt=document.getElementById("goTrend"); if(gt) gt.onclick=()=>gotoTrend(name);
  document.getElementById("drawerClose").onclick=closeDrawer;
  document.getElementById("drawer").classList.add("open");
  document.getElementById("drawerOverlay").classList.add("open");
}
function closeDrawer(){
  document.getElementById("drawer").classList.remove("open");
  document.getElementById("drawerOverlay").classList.remove("open");
}
/* 상세 패널 → 트렌드 비교 탭으로 이동하며 그 종목을 선택 */
function gotoTrend(name){
  if(!topicsOf(name).length) return;
  trendStock=name; trendGroup=topicsOf(name)[0]||"";
  const tb=document.querySelector('nav.tabs button[data-k="trends"]'); if(tb) tb.click();
  renderTrendSegs(); drawTrend(); renderShop();
  closeDrawer();
  window.scrollTo({top:0,behavior:"smooth"});
}
function drawQuarter(qs){
  const box=document.getElementById("qChart"); if(!box||!qs.length) return;
  const W=box.clientWidth||520, H=220, pad={l:8,r:8,t:14,b:26};
  const maxRev=Math.max(...qs.map(q=>q.rev))||1;
  const bw=(W-pad.l-pad.r)/qs.length*0.6;
  const sx=i=>pad.l+(i+0.5)/qs.length*(W-pad.l-pad.r);
  const sy=v=>H-pad.b-(v/maxRev)*(H-pad.t-pad.b);
  const opms=qs.map(q=>q.rev?q.op/q.rev*100:0);
  const maxOpm=Math.max(...opms,1)*1.25;
  const syo=v=>H-pad.b-(v/maxOpm)*(H-pad.t-pad.b);
  const mut=getComputedStyle(document.documentElement).getPropertyValue('--muted');
  const gc=getComputedStyle(document.documentElement).getPropertyValue('--line');
  let s=`<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" font-family="inherit">`;
  for(let g=0;g<=3;g++){const y=pad.t+(H-pad.t-pad.b)*g/3;s+=`<line x1="${pad.l}" y1="${y}" x2="${W-pad.r}" y2="${y}" stroke="${gc}"/>`;}
  qs.forEach((q,i)=>{
    const x=sx(i);const est=q.q.includes('E');
    s+=`<rect x="${(x-bw/2).toFixed(1)}" y="${sy(q.rev).toFixed(1)}" width="${bw.toFixed(1)}" height="${(H-pad.b-sy(q.rev)).toFixed(1)}" rx="2" fill="var(--accent)" opacity="${est?0.4:0.85}"><title>${q.q} 매출 ${eok(q.rev)}억 · OPM ${fmt(opms[i])}%</title></rect>`;
    s+=`<text x="${x.toFixed(1)}" y="${H-pad.b+15}" text-anchor="middle" font-size="9.5" fill="${mut}">${q.q}</text>`;
  });
  const line=qs.map((q,i)=>`${sx(i).toFixed(1)},${syo(opms[i]).toFixed(1)}`).join(" ");
  s+=`<polyline points="${line}" fill="none" stroke="var(--up)" stroke-width="2"/>`;
  qs.forEach((q,i)=>{s+=`<circle cx="${sx(i).toFixed(1)}" cy="${syo(opms[i]).toFixed(1)}" r="2.6" fill="var(--up)"/>`;});
  s+="</svg>";
  box.innerHTML=s;
}
document.getElementById("drawerOverlay").addEventListener("click",closeDrawer);
document.addEventListener("keydown",e=>{if(e.key==="Escape")closeDrawer();});
document.addEventListener("click",e=>{const el=e.target.closest("[data-stock]");if(el)openStock(el.dataset.stock);});

/* ==== 엑셀(.xlsx) 내보내기 — Universe 시트 양식 (D열 시작 / 상승여력 수식) ==== */
(function(){
  const enc=new TextEncoder();
  let CRC=null;
  function crc32(b){
    if(!CRC){CRC=new Uint32Array(256);for(let n=0;n<256;n++){let c=n;for(let k=0;k<8;k++)c=c&1?0xEDB88320^(c>>>1):c>>>1;CRC[n]=c>>>0;}}
    let c=0xFFFFFFFF;for(let i=0;i<b.length;i++)c=CRC[(c^b[i])&0xFF]^(c>>>8);return (c^0xFFFFFFFF)>>>0;
  }
  function zip(files){
    const parts=[],cen=[];let off=0;
    const u16=v=>[v&255,(v>>8)&255],u32=v=>[v&255,(v>>8)&255,(v>>16)&255,(v>>24)&255];
    files.forEach(f=>{
      const nm=enc.encode(f.name),d=f.data,crc=crc32(d);
      const lh=[...u32(0x04034b50),...u16(20),...u16(0),...u16(0),...u16(0),...u16(0),
                ...u32(crc),...u32(d.length),...u32(d.length),...u16(nm.length),...u16(0)];
      parts.push(new Uint8Array(lh),nm,d);
      cen.push(new Uint8Array([...u32(0x02014b50),...u16(20),...u16(20),...u16(0),...u16(0),...u16(0),...u16(0),
        ...u32(crc),...u32(d.length),...u32(d.length),...u16(nm.length),...u16(0),...u16(0),...u16(0),...u16(0),
        ...u32(0),...u32(off)]),nm);
      off+=lh.length+nm.length+d.length;
    });
    let cl=0;cen.forEach(c=>cl+=c.length);
    const tail=new Uint8Array([...u32(0x06054b50),...u16(0),...u16(0),...u16(files.length),...u16(files.length),
      ...u32(cl),...u32(off),...u16(0)]);
    return new Blob([...parts,...cen,tail],{type:"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"});
  }
  const esc=v=>String(v).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  const cn=i=>{let s="",n=i+1;while(n){s=String.fromCharCode(65+(n-1)%26)+s;n=Math.floor((n-1)/26);}return s;};

  /* ---------- 색 ---------- */
  const SEC_FILL={"소비재":"FF83CCEB","엔터/미디어":"FFF2CEEF","엔터":"FFF2CEEF","게임":"FFDAF2D0","호텔":"FFD0D0D0"};
  const RED =["FFFDF4F3","FFFCEEED","FFF9E1DF","FFF6C6C7","FFEE9D9E"];
  const BLUE=["FFF3F8FB","FFE7F0F6","FFDCE9F2","FFD0E1EE","FFBBD5E8"];
  const TITLE_BG="FF1F4E79", HDR1="FFDEDEDE", HDR2="FFF4F4F4", LINE="FF808080", LINE2="FF404040";

  /* ---------- 스타일 레지스트리 ---------- */
  const fills=['<fill><patternFill patternType="none"/></fill>','<fill><patternFill patternType="gray125"/></fill>'];
  const fillIdx={};
  const FILL=rgb=>{ if(!rgb) return 0; if(fillIdx[rgb]!==undefined) return fillIdx[rgb];
    fills.push('<fill><patternFill patternType="solid"><fgColor rgb="'+rgb+'"/><bgColor indexed="64"/></patternFill></fill>');
    return (fillIdx[rgb]=fills.length-1); };
  const borders=['<border><left/><right/><top/><bottom/><diagonal/></border>'];
  const bIdx={};
  function BORDER(b){                       // {l,r,t,bo} = 'thin'|'medium'|'double'|undefined
    const key=[b.l||"",b.r||"",b.t||"",b.bo||""].join("|");
    if(key==="|||") return 0;
    if(bIdx[key]!==undefined) return bIdx[key];
    const e=(tag,st)=>st?'<'+tag+' style="'+st+'"><color rgb="'+(st==="thin"?LINE:LINE2)+'"/></'+tag+'>':'<'+tag+'/>';
    borders.push('<border>'+e("left",b.l)+e("right",b.r)+e("top",b.t)+e("bottom",b.bo)+'<diagonal/></border>');
    return (bIdx[key]=borders.length-1);
  }
  /* pct = 엑셀의 진짜 백분율 서식(0.0%).
     예전엔 0.0"%" — 숫자 뒤에 % 글자만 붙인 가짜였다. 보기엔 똑같이 "35.6%" 지만
     셀 값이 35.6 이라, 그 칸으로 수식을 걸면 100배 틀린 답이 나오고
     수식 입력줄에 35.625913591223515 가 떠서 화면 표시와 어긋났다.
     이제 값을 0.356 으로 넣고 서식이 %를 만든다 — 표시는 같고 계산이 맞는다. */
  const NF={g:0,n1:164,n0:3,nd:165,dt:166,pct:169,mult:168};
  const PCT_SCALE=0.01;                     // pct 열 값 변환 계수 (35.6 -> 0.356)
  const xfs=[],xfIdx={};
  function ST(o){
    o=o||{};
    const b=o.bd||{};
    const key=[o.nf||"g",o.fill||"",b.l||"",b.r||"",b.t||"",b.bo||"",o.bold?1:0,o.center?1:0,o.wrap?1:0,o.white?1:0,o.left?1:0].join("|");
    if(xfIdx[key]!==undefined) return xfIdx[key];
    const al=(o.center||o.wrap||o.left)?'<alignment'+(o.left?' horizontal="left" vertical="center"':(o.center?' horizontal="center" vertical="center"':''))+(o.wrap?' wrapText="1"':'')+'/>':'';
    xfs.push('<xf numFmtId="'+NF[o.nf||"g"]+'" fontId="'+(o.white?2:(o.bold?1:0))+'" fillId="'+FILL(o.fill)+'" borderId="'+BORDER(b)+'" xfId="0"'
      +' applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1"'+(al?' applyAlignment="1"':'')+'>'+al+'</xf>');
    return (xfIdx[key]=xfs.length-1);
  }
  ST({});

  const styleXml=()=>'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    +'<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    +'<numFmts count="5"><numFmt numFmtId="164" formatCode="0.0"/><numFmt numFmtId="165" formatCode="#,##0.0"/><numFmt numFmtId="166" formatCode="yyyy-mm-dd"/><numFmt numFmtId="169" formatCode="0.0%"/><numFmt numFmtId="168" formatCode="0.0&quot;x&quot;"/></numFmts>'
    +'<fonts count="3"><font><sz val="11"/><name val="맑은 고딕"/></font>'
    +'<font><b/><sz val="11"/><name val="맑은 고딕"/></font>'
    +'<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="맑은 고딕"/></font></fonts>'
    +'<fills count="'+fills.length+'">'+fills.join("")+'</fills>'
    +'<borders count="'+borders.length+'">'+borders.join("")+'</borders>'
    +'<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    +'<cellXfs count="'+xfs.length+'">'+xfs.join("")+'</cellXfs></styleSheet>';

  /* ---------- 조건부 강조 ---------- */
  function scale(v,lo,hi){
    if(v===null||v===undefined||!isFinite(v)) return null;
    let t=Math.max(0,Math.min(1,(v-lo)/(hi-lo)));
    return t>=0.5 ? RED[Math.min(4,Math.floor((t-0.5)*10))] : BLUE[Math.min(4,Math.floor((0.5-t)*10))];
  }
  const hPct=v=>scale(v,-40,40), hScore=v=>scale(v,5,8);

  /* ---------- 데이터 막대 설정 ----------
     min~max 구간이 막대 0~100% 길이. 값이 음수인 열은 축이 오른쪽에 서고
     막대가 왼쪽으로 자라므로 neg 계열 색을 같이 지정한다. */
  // 막대가 걸리는 열은 전부 pct 서식이라, 셀 값이 소수(0.35=35%)다.
  // min/max 도 같은 단위여야 한다 — 200 으로 두면 막대가 영원히 안 찬다.
  const BAR_EPS ={min:0,    max:2,   fill:"FFAFC9E8", line:"FF5B8FD4", neg:"FFF4B8B8", negLine:"FFD46A6A"};  // 0~200%
  const BAR_DOWN={min:-0.6, max:0,   fill:"FFB9CFEA", line:"FF4A7EBB", neg:"FFB9CFEA", negLine:"FF4A7EBB"};  // 낙폭 : 파란 막대
  const BAR_UP  ={min:0,    max:1.5, fill:"FFF3B9B9", line:"FFC0504D", neg:"FFF3B9B9", negLine:"FFC0504D"};  // 반등 : 빨간 막대

  /* ---------- 컬럼 (D열부터) ---------- */
  const FULL={Top:"Top pick","2nd":"2nd pick",Beta:"Beta pick"};
  const C=[
    {s:"",       w:4.2,  get:(r,i)=>i+1,                     center:1},
    {s:"",       w:9.4,  get:r=>FULL[sectorPickOf(r)]||"",   center:1},
    {s:"대섹터", w:9.0,  get:r=>r.sector, fill:r=>SEC_FILL[r.sector], center:1},
    {s:"소섹터", w:7.5,  get:r=>r.sub,    center:1},
    {s:"종목",   w:13.0, get:r=>r.name,   center:1},
    {g:"점수",          s:"", w:7.5,  get:r=>r.score,      nf:"n1", fill:r=>hScore(r.score)},
    {g:"시가총액 (억 원)", s:"", w:15.0, get:r=>mcJo(r)*10000, nf:"n0"},
    {g:"견적 (억 원)", s:"", w:13.0, get:r=>r.fairMktcap!=null?r.fairMktcap*10:null, nf:"n0"},
    {g:"상승 여력 (%)",  s:"", w:15.0, get:r=>r.upsideOwn, nf:"pct", fill:r=>hPct(r.upsideOwn)},
    {g:"기간별 수익률", s:"1w", w:7.0, get:r=>r.ret1w, nf:"pct", fill:r=>hPct(r.ret1w)},
    {                   s:"1m", w:7.0, get:r=>r.ret1m, nf:"pct", fill:r=>hPct(r.ret1m)},
    {                   s:"3m", w:7.0, get:r=>r.ret3m, nf:"pct", fill:r=>hPct(r.ret3m)},
    {                   s:"6m", w:7.0, get:r=>r.ret6m, nf:"pct", fill:r=>hPct(r.ret6m)},
    {                   s:"1y", w:7.0, get:r=>r.ret1y, nf:"pct", fill:r=>hPct(r.ret1y)},
    {                   s:"YTD", w:7.0, get:r=>r.retYtd, nf:"pct", fill:r=>hPct(r.retYtd)},
    {g:"낙폭 (%)", s:"52주 고점", w:11.5, get:r=>r.mdd, nf:"pct", bar:BAR_DOWN},
    {g:"반등 (%)", s:"52주 저점", w:11.5, get:r=>r.rebound, nf:"pct", bar:BAR_UP},
    {g:"PER (배)", s:"12MF", w:7.6, get:r=>r.per12mf, nf:"mult"},
    {              s:"26E",  w:7.2, get:r=>r.per26,   nf:"mult"},
    {              s:"27E",  w:7.2, get:r=>r.per27,   nf:"mult"},
    {g:"PBR (배)", s:"TTM", w:7.6, get:r=>r.pbr,   nf:"mult"},
    {              s:"26E", w:7.2, get:r=>r.pbr26, nf:"mult"},
    {g:"매출액 (억 원)", s:"26E", w:11.0, get:r=>r.rev26!=null?r.rev26*10:null, nf:"n0"},
    {                    s:"27E", w:11.0, get:r=>r.rev27!=null?r.rev27*10:null, nf:"n0"},
    {g:"매출 YoY (%)", s:"26E", w:8.6, get:r=>r.revYoY26, nf:"pct", fill:r=>hPct(r.revYoY26)},
    {                  s:"27E", w:8.6, get:r=>r.revYoY27, nf:"pct", fill:r=>hPct(r.revYoY27)},
    {g:"영업이익 (억 원)", s:"26E", w:11.0, get:r=>r.op26!=null?r.op26*10:null, nf:"n0"},
    {                      s:"27E", w:11.0, get:r=>r.op27!=null?r.op27*10:null, nf:"n0"},
    {g:"순이익 (억 원)", s:"26E", w:11.0, get:r=>r.np26!=null?r.np26*10:null, nf:"n0"},
    {                    s:"27E", w:11.0, get:r=>r.np27!=null?r.np27*10:null, nf:"n0"},
    {g:"EPS (원)", s:"26E", w:9.0, get:r=>r.eps26, nf:"n0"},
    {              s:"27E", w:9.0, get:r=>r.eps27, nf:"n0"},
    {g:"EPS 증가율", s:"25→26", w:8.8, get:r=>r.epsg26!=null?r.epsg26:(r.epsg26t||null), nf:"pct", bar:BAR_EPS},
    {                s:"26→27", w:8.8, get:r=>r.epsg27!=null?r.epsg27:(r.epsg27t||null), nf:"pct", bar:BAR_EPS},
    {g:"현재 주가 (원)", s:"", w:17.0, get:r=>r.price,  nf:"n0"},
    {g:"목표주가 (원)",  s:"컨센서스", w:16.5, get:r=>r.target, nf:"n0"},
    {g:"상승여력 (%)",   s:"컨센서스 기준 산출",w:19.5, get:r=>r.upsideCons, nf:"pct", fill:r=>hPct(r.upsideCons)},
  ];
  const N=C.length, OFF=3;                 // D열 = index 3
  const gStart=[],gEnd=[];
  {let i=0;while(i<N){let j=i;
    if(C[i].g!==undefined){ while(j+1<N && !("g" in C[j+1])) j++; }
    for(let k=i;k<=j;k++){gStart[k]=(k===i);gEnd[k]=(k===j);} i=j+1;}}

  /* 내용 길이에 맞춘 열 너비 계산 (한글 2, 그 외 1) */
  let AUTOW=null;
  const wlen=t=>[...String(t==null?"":t)].reduce((a,ch)=>a+(/[ᄀ-ᇿ㄰-㆏가-힣]/.test(ch)?2:1),0);
  function fmtLen(v,nf){
    if(v===null||v===undefined||v==="") return 0;
    if(typeof v!=="number") return wlen(v);
    if(nf==="n0") return Math.round(v).toLocaleString("en-US").length;
    if(nf==="nd") return Math.abs(v).toLocaleString("en-US",{minimumFractionDigits:1,maximumFractionDigits:1}).length+(v<0?1:0);
    if(nf==="n1") return v.toFixed(1).length;
    return wlen(v);
  }
  function calcWidths(sorted){
    AUTOW=C.map((c,i)=>{
      if(c.g==="점수") return c.w;                    // 점수는 기존 폭 유지
      let need=wlen(c.s||"");
      if(c.g!==undefined && gStart[i] && gEnd[i]) need=Math.max(need,wlen(c.g));  // 단독 그룹은 제목도 수용
      sorted.forEach((r,idx)=>{ need=Math.max(need,fmtLen(c.get(r,idx),c.nf)); });
      return Math.max(6, Math.min(24, need+3));
    });
  }

  function build(){
    const rows=[],merges=[];
    const put=(r,c,v)=>{ (rows[r]=rows[r]||[])[c]=v; };
    const L=i=>gStart[i]?"medium":undefined, Rr=i=>gEnd[i]?"medium":undefined;
    const Li=i=>gStart[i]?"medium":"thin";   // 내부 구분선(5행·데이터행)
    // 2행 날짜 (3칸 병합해 ### 방지)
    for(let i=0;i<5;i++) put(1,OFF+i,{v:"", s:ST({nf:"dt",left:1})});
    put(1,OFF,{f:"TODAY()", s:ST({nf:"dt",left:1})});
    merges.push(cn(OFF)+"2:"+cn(OFF+4)+"2");
    // 3행 제목 밴드 (표 전체 폭)
    for(let i=0;i<N;i++) put(2,OFF+i,{v:"", s:ST({fill:TITLE_BG,white:1,left:1})});
    put(2,OFF,{v:"소비재/호텔/게임/엔터 Universe 구성_"+(DATA.analyst||""),
               s:ST({fill:TITLE_BG,white:1,left:1})});
    merges.push(cn(OFF)+"3:"+cn(OFF+N-1)+"3");
    // 4행 그룹헤더 / 5행 소제목
    for(let i=0;i<N;i++){
      // 4행: 짙은 음영(그룹) / 5행: 밝은 음영(소제목) — 두 행은 항상 분리
      put(3,OFF+i,{v:(C[i].g!==undefined?C[i].g:""),
        s:ST({fill:HDR1,bold:1,center:1,bd:{l:L(i),r:Rr(i),t:"medium",bo:"thin"}})});
      put(4,OFF+i,{v:(C[i].s||""),
        s:ST({fill:HDR2,bold:1,center:1,bd:{l:Li(i),r:Rr(i),bo:"double"}})});
    }
    for(let i=0;i<N;i++){
      if(!gStart[i]) continue;
      let j=i; while(j+1<N && !gStart[j+1]) j++;
      if(j>i) merges.push(cn(OFF+i)+"4:"+cn(OFF+j)+"4");   // 가로 병합만 (4/5행 분리 유지)
    }
    // 데이터
    const sorted=R.slice().sort((a,b)=>(a.rank||999)-(b.rank||999));
    calcWidths(sorted);
    sorted.forEach((r,idx)=>{
      const ri=5+idx, last=(idx===sorted.length-1), prev=idx>0?sorted[idx-1]:null;
      // 대섹터 바뀌면 굵은선, 소섹터만 바뀌면 얇은선, 같으면 선 없음
      let top;
      if(!prev) top="medium";
      else if(prev.sector!==r.sector) top="medium";
      else if(prev.sub!==r.sub) top="thin";
      C.forEach((c,i)=>{
        const bd={l:Li(i),r:Rr(i),t:top};
        if(last) bd.bo="medium";
        const st=ST({nf:c.nf,fill:(c.fill?c.fill(r):null),center:1,bd:bd});
        let v=c.get(r,idx);
        if(v===null||v===undefined||(typeof v==="number"&&!isFinite(v))) v="";
        // 백분율 열은 엑셀 규약대로 소수로 넣는다(35.6 -> 0.356). 서식이 %를 붙인다.
        // 조건부 서식(fill/bar)은 위에서 원본 값으로 이미 계산했으니 순서를 바꾸면 안 된다.
        if(c.nf==="pct"&&typeof v==="number") v*=PCT_SCALE;
        put(ri,OFF+i,{v:v, s:st});
      });
    });
    return {rows,merges};
  }

  /* 데이터 막대 (EPS 증가율 · 낙폭 · 반등) */
  let barExt=[];
  function cfBars(totalRows){
    const last=totalRows; if(last<6) return "";
    let out=""; barExt=[];
    C.forEach((c,i)=>{
      const b=c.bar; if(!b) return;
      const L=cn(OFF+i);
      const gid="{DB0E1C"+String(i).padStart(2,"0")+"-1111-4222-8333-"+String(i).padStart(12,"0")+"}";
      barExt.push('<x14:conditionalFormatting xmlns:xm="http://schemas.microsoft.com/office/excel/2006/main">'
        +'<x14:cfRule type="dataBar" id="'+gid+'">'
        +'<x14:dataBar minLength="0" maxLength="100" gradient="0" border="1" direction="leftToRight" '
        +'negativeBarColorSameAsPositive="0" negativeBarBorderColorSameAsPositive="0" axisPosition="automatic">'
        +'<x14:cfvo type="num"><xm:f>'+b.min+'</xm:f></x14:cfvo>'
        +'<x14:cfvo type="num"><xm:f>'+b.max+'</xm:f></x14:cfvo>'
        +'<x14:fillColor rgb="'+b.fill+'"/>'
        +'<x14:borderColor rgb="'+b.line+'"/>'
        +'<x14:negativeFillColor rgb="'+b.neg+'"/>'
        +'<x14:negativeBorderColor rgb="'+b.negLine+'"/>'
        +'<x14:axisColor rgb="FFD0D0D0"/>'
        +'</x14:dataBar></x14:cfRule>'
        +'<xm:sqref>'+L+'6:'+L+last+'</xm:sqref></x14:conditionalFormatting>');
      out+='<conditionalFormatting sqref="'+L+'6:'+L+last+'">'
         +'<cfRule type="dataBar" priority="'+(i+1)+'">'
         +'<dataBar showValue="1"><cfvo type="num" val="'+b.min+'"/><cfvo type="num" val="'+b.max+'"/>'
         +'<color rgb="'+b.fill+'"/></dataBar>'
         +'<extLst><ext uri="{B025F937-C7B1-47D3-B67F-A62EFF666E3E}" '
         +'xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main">'
         +'<x14:id>'+gid+'</x14:id></ext></extLst>'
         +'</cfRule></conditionalFormatting>';
    });
    return out;
  }

  function sheetXml(rows,merges){
    const cols='<col min="1" max="3" width="2.5" customWidth="1"/>'
      +C.map((c,i)=>'<col min="'+(OFF+i+1)+'" max="'+(OFF+i+1)+'" width="'+((AUTOW&&AUTOW[i])||c.w)+'" customWidth="1"/>').join("");
    const body=rows.map((r,ri)=>{
      const cells=(r||[]).map((cell,ci)=>{
        if(cell===null||cell===undefined) return "";
        const st=cell.s||0, ref=cn(ci)+(ri+1);
        if(cell.f!==undefined) return '<c r="'+ref+'" s="'+st+'"><f>'+esc(cell.f)+'</f></c>';
        const v=cell.v;
        if(v===""||v===null||v===undefined) return '<c r="'+ref+'" s="'+st+'"/>';
        if(typeof v==="number"&&isFinite(v)) return '<c r="'+ref+'" s="'+st+'"><v>'+v+'</v></c>';
        return '<c r="'+ref+'" t="inlineStr" s="'+st+'"><is><t>'+esc(v)+'</t></is></c>';
      }).join("");
      const h=(ri>=2&&ri<=4)?' ht="18.75" customHeight="1"':(ri>=5?' ht="17.25" customHeight="1"':'');
      return cells?'<row r="'+(ri+1)+'"'+h+'>'+cells+'</row>':"";
    }).join("");
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      +'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
      +'<sheetViews><sheetView showGridLines="0" workbookViewId="0">'
      +'<pane xSplit="8" ySplit="5" topLeftCell="I6" activePane="bottomRight" state="frozen"/></sheetView></sheetViews>'
      +'<sheetFormatPr defaultRowHeight="16.5"/><cols>'+cols+'</cols><sheetData>'+body+'</sheetData>'
      +(merges.length?'<mergeCells count="'+merges.length+'">'+merges.map(m=>'<mergeCell ref="'+m+'"/>').join("")+'</mergeCells>':"")
      +cfBars(rows.length)
      +(barExt.length?'<extLst><ext uri="{78C0D931-6437-407d-A8EE-F0AAD7539E65}" '
        +'xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main">'
        +'<x14:conditionalFormattings>'+barExt.join("")+'</x14:conditionalFormattings></ext></extLst>':"")
      +'</worksheet>';
  }

  function buildXlsx(){
    const {rows,merges}=build();
    const sh=sheetXml(rows,merges);
    const F=(n,t)=>({name:n,data:enc.encode(t)});
    return zip([
      F("[Content_Types].xml",'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>'),
      F("_rels/.rels",'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'),
      F("xl/workbook.xml",'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Universe" sheetId="1" r:id="rId1"/></sheets><calcPr fullCalcOnLoad="1"/></workbook>'),
      F("xl/_rels/workbook.xml.rels",'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'),
      F("xl/styles.xml",styleXml()),
      F("xl/worksheets/sheet1.xml",sh),
    ]);
  }

  const btns=[...document.querySelectorAll(".xlsxBtn")];
  if(!btns.length) return;
  btns.forEach(btn=>btn.addEventListener("click",function(){
    try{
      const a=document.createElement("a");
      a.href=URL.createObjectURL(buildXlsx());
      const d=TODAY_C;
      a.download=(DATA.analyst||"신주현")+"_소비재_커버리지_"+d+".xlsx";
      document.body.appendChild(a); a.click();
      setTimeout(function(){ URL.revokeObjectURL(a.href); a.remove(); },1000);
    }catch(e){ alert("엑셀 생성 실패: "+e.message); }
  }));
})();

/* ==== 랜딩 팝업: SAMG 하츄핑 극장 흥행 (KOBIS 일별 실데이터) ==== */
(function(){
  const ov=document.getElementById("samgOverlay");
  if(!ov) return;
  const MV=(typeof MOVIE!=="undefined")?MOVIE:{movies:{},booking:{}};
  const man=v=>v==null?"—":(v>=10000?(v/10000).toFixed(v>=1000000?0:1)+"만":fmt0(v));
  const parseD=s=>{ const d=String(s).replace(/-/g,""); return new Date(+d.slice(0,4),+d.slice(4,6)-1,+d.slice(6,8)); };
  const dayN=(d,open)=>Math.round((parseD(d)-open)/864e5);
  const fmtDate=dt=>`${dt.getFullYear()}-${String(dt.getMonth()+1).padStart(2,"0")}-${String(dt.getDate()).padStart(2,"0")}`;

  // 하츄핑 극장판들 — 개봉일 순. days 있는 것만(개봉 후)
  const movies=Object.entries(MV.movies||{})
    .map(([nm,m])=>({nm, ...m, open:parseD(m.openDt||(m.days[0]||{}).d||"20240807")}))
    .filter(m=>m.days&&m.days.length)
    .sort((a,b)=>a.open-b.open);
  const prev=movies[0];                                   // 1편(참조 히트)
  const cur =movies.slice(1).find(m=>m.days.length);      // 2편(개봉 후에만 days 존재)
  const NEXT_OPEN=new Date(2026,7,5);                     // 2편 개봉일(개봉 전 fallback)
  const bkKey=Object.keys(MV.booking||{}).find(k=>!prev||k!==prev.nm);   // 2편 예매 키
  const bk2=(bkKey?MV.booking[bkKey]:[])||[];             // 2편 예매(개봉 전에도 존재)
  const open2=cur?cur.open:(bk2.length?NEXT_OPEN:null);   // 2편 개봉일
  const has2=!!(cur||bk2.length);

  // ── 일별 차트: 당일 관객(막대,우축)+누적(선,좌축). 2편 개봉 후 같은 개봉일차로 겹쳐 비교 ──
  function chart(box){
    const W=512,H=214,pad={l:46,r:48,t:18,b:28};
    const clamp=(x,lo,hi)=>Math.max(lo,Math.min(hi,x));
    const S=[prev,cur].filter(Boolean).map((m,i)=>({label:i?"2편":"1편", c:i?"var(--accent2)":"var(--accent)",
      pts:m.days.map(x=>({n:dayN(x.d,m.open), acc:x.acc, audi:x.audi, d:x.d})).filter(p=>p.n>=0)}));
    // 2편(개봉 후)이 있으면 2편 진행범위로 창을 좁혀 같은 개봉일차에서 겹쳐 비교, 1편도 절단
    const fullMax=Math.max(1,...S.flatMap(s=>s.pts.map(p=>p.n)));
    const maxDay=cur ? Math.min(fullMax, Math.max(1,...cur.days.map(x=>dayN(x.d,cur.open)))+2) : fullMax;
    S.forEach(se=>se.pts=se.pts.filter(p=>p.n<=maxDay));
    const maxV=Math.max(1,...S.flatMap(s=>s.pts.map(p=>p.acc)))*1.1;
    const maxA=Math.max(1,...S.flatMap(s=>s.pts.map(p=>p.audi)))*1.15;
    const xs=n=>pad.l+n/Math.max(1,maxDay)*(W-pad.l-pad.r);
    const ys=v=>H-pad.b-v/maxV*(H-pad.t-pad.b), yA=v=>H-pad.b-v/maxA*(H-pad.t-pad.b);
    const gc="var(--line)", mut="var(--muted)";
    const bw=Math.max(1.6,(W-pad.l-pad.r)/(maxDay+1)*0.6);
    let s=`<svg viewBox="0 0 ${W} ${H}" width="100%" font-family="inherit">`;
    for(let v=0;v<=maxV;v+=500000){ const y=ys(v);
      s+=`<line x1="${pad.l}" y1="${y}" x2="${W-pad.r}" y2="${y}" stroke="${gc}"${v===1000000?' stroke-dasharray="4 3"':''}/>`;
      s+=`<text x="${pad.l-6}" y="${y+3.5}" text-anchor="end" font-size="10" fill="${mut}">${v/10000}만</text>`; }
    for(let g=0;g<=2;g++){ const v=maxA*g/2;
      s+=`<text x="${W-pad.r+6}" y="${yA(v)+3.5}" font-size="9.5" fill="${mut}">${(v/10000).toFixed(v>=100000?0:1)}만</text>`; }
    // x축 라벨 — 양 끝은 안쪽으로 붙여 잘림 방지
    [0,Math.round(maxDay/2),maxDay].filter((v,i,a)=>a.indexOf(v)===i).forEach((n,i,a)=>{
      const anc=i===0?"start":(i===a.length-1?"end":"middle");
      s+=`<text x="${clamp(xs(n),pad.l,W-pad.r)}" y="${H-pad.b+16}" text-anchor="${anc}" font-size="10" fill="${mut}">D+${n}</text>`; });
    s+=`<text x="${W-4}" y="12" text-anchor="end" font-size="9" fill="${mut}">당일 ▮</text>`;
    // 당일 관객 막대
    S.forEach(se=>se.pts.forEach(p=>{ const h=(H-pad.b)-yA(p.audi);
      s+=`<rect x="${(xs(p.n)-bw/2).toFixed(1)}" y="${yA(p.audi).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(0,h).toFixed(1)}" fill="${se.c}" opacity=".22"><title>${se.label} D+${p.n} · 당일 ${man(p.audi)}</title></rect>`; }));
    // 누적선 + 끝값 라벨(가장자리에서 방향 전환·클램프)
    S.forEach(se=>{
      s+=`<polyline points="${se.pts.map(p=>`${xs(p.n).toFixed(1)},${ys(p.acc).toFixed(1)}`).join(" ")}" fill="none" stroke="${se.c}" stroke-width="2.4" stroke-linejoin="round"/>`;
      se.pts.forEach(p=>s+=`<circle cx="${xs(p.n).toFixed(1)}" cy="${ys(p.acc).toFixed(1)}" r="1.6" fill="${se.c}"><title>${se.label} D+${p.n} (${p.d.slice(4,6)}/${p.d.slice(6,8)}) · 누적 ${man(p.acc)} · 당일 ${man(p.audi)}</title></circle>`);
      const last=se.pts[se.pts.length-1]; if(!last) return;
      const near=xs(last.n)>pad.l+(W-pad.l-pad.r)*0.5;
      const lx=clamp(near?xs(last.n)-4:xs(last.n)+4, pad.l+2, W-pad.r-2);
      s+=`<text x="${lx.toFixed(1)}" y="${clamp(ys(last.acc)-7,pad.t+9,H-pad.b-2).toFixed(1)}" text-anchor="${near?"end":"start"}" font-size="11" font-weight="800" fill="${se.c}">${S.length>1?se.label+" ":""}${man(last.acc)}</text>`;
    });
    if(S.length>1){   // 범례
      s+=`<rect x="${pad.l+2}" y="4" width="9" height="9" rx="2" fill="var(--accent)"/><text x="${pad.l+14}" y="12" font-size="9.5" fill="${mut}">1편</text>`;
      s+=`<rect x="${pad.l+42}" y="4" width="9" height="9" rx="2" fill="var(--accent2)"/><text x="${pad.l+54}" y="12" font-size="9.5" fill="${mut}">2편</text>`;
    }
    s+="</svg>"; box.innerHTML=s;
  }

  // ── 개봉 전 예매관객 추이 (D-day 축, 개봉선까지). 개봉하면 위 곡선에 합류하므로 숨김 ──
  function bookingChart(B, open2){
    const W=512,H=106,pad={l:46,r:18,t:14,b:20};
    const clamp=(x,lo,hi)=>Math.max(lo,Math.min(hi,x));
    const P=B.map(p=>({n:dayN(p.d,open2), book:p.book, rate:p.rate})).sort((a,b)=>a.n-b.n);
    const nMin=Math.min(-1,...P.map(p=>p.n)), nMax=0, span=Math.max(1,nMax-nMin);
    const maxB=Math.max(1,...P.map(p=>p.book))*1.25;
    const xs=n=>pad.l+(n-nMin)/span*(W-pad.l-pad.r);
    const yb=v=>H-pad.b-v/maxB*(H-pad.t-pad.b);
    const mut="var(--muted)", gc="var(--line)";
    let s=`<svg viewBox="0 0 ${W} ${H}" width="100%" font-family="inherit">`;
    s+=`<line x1="${pad.l}" y1="${yb(0)}" x2="${W-pad.r}" y2="${yb(0)}" stroke="${gc}"/>`;
    s+=`<text x="${pad.l-6}" y="${yb(maxB/1.25)+3}" text-anchor="end" font-size="9" fill="${mut}">${man(maxB/1.25)}</text>`;
    // 개봉선(D0)
    s+=`<line x1="${xs(0)}" y1="${pad.t}" x2="${xs(0)}" y2="${H-pad.b}" stroke="${mut}" stroke-dasharray="2 3" opacity=".55"/>`;
    s+=`<text x="${clamp(xs(0),pad.l,W-pad.r)}" y="${pad.t-3}" text-anchor="end" font-size="8.5" fill="${mut}">개봉(D0)</text>`;
    if(P.length){
      const line=P.map(p=>`${xs(p.n).toFixed(1)},${yb(p.book).toFixed(1)}`).join(" ");
      s+=`<polygon points="${xs(P[0].n).toFixed(1)},${yb(0)} ${line} ${xs(P[P.length-1].n).toFixed(1)},${yb(0)}" fill="var(--accent2)" opacity=".14"/>`;
      s+=`<polyline points="${line}" fill="none" stroke="var(--accent2)" stroke-width="2.2" stroke-linejoin="round"/>`;
      P.forEach(p=>{ s+=`<circle cx="${xs(p.n).toFixed(1)}" cy="${yb(p.book).toFixed(1)}" r="2.3" fill="var(--accent2)"><title>D${p.n} · 예매관객 ${man(p.book)} · 예매율 ${p.rate}%</title></circle>`;
        s+=`<text x="${clamp(xs(p.n),pad.l,W-pad.r)}" y="${H-6}" text-anchor="middle" font-size="8.5" fill="${mut}">D${p.n}</text>`; });
      const lp=P[P.length-1], nearR=xs(lp.n)>W*0.6;
      s+=`<text x="${clamp(nearR?xs(lp.n)-5:xs(lp.n)+5,pad.l,W-pad.r).toFixed(1)}" y="${clamp(yb(lp.book)-6,pad.t+8,H-pad.b-2).toFixed(1)}" text-anchor="${nearR?"end":"start"}" font-size="10.5" font-weight="800" fill="var(--accent2)">예매 ${man(lp.book)}</text>`;
    }
    s+="</svg>"; return s;
  }

  function render(){
    const chartEl=document.getElementById("samgChart"), statEl=document.getElementById("samgStats");
    const nextEl=document.querySelector(".samg-next"), subEl=document.querySelector(".samg-sub"), srcEl=document.querySelector(".samg-src");
    if(!prev){ chartEl.innerHTML=`<div style="color:var(--muted);font-size:13px;padding:22px 4px">극장 흥행 데이터 수집 대기 중입니다.</div>`; statEl.innerHTML=""; return; }
    chart(chartEl);
    const days=prev.days, finalAcc=days[days.length-1].acc;
    const peak=days.reduce((a,x)=>x.audi>a.audi?x:a, days[0]);
    statEl.innerHTML=[
      [man(finalAcc), `${prev.nm} 누적`],
      [man(peak.audi), `최고 일일 (${peak.d.slice(4,6)}/${peak.d.slice(6,8)})`],
      [`${days.length}일`, "집계 상영일"],
    ].map(([v,l])=>`<div class="samg-stat"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("");
    // 2편: 개봉 후면 누적, 전이면 실시간 예매
    const bkKey=Object.keys(MV.booking||{}).find(k=>k!==prev.nm);
    if(cur){
      const la=cur.days[cur.days.length-1];
      nextEl.innerHTML=`🎬 <b>${cur.nm}</b> · 개봉 ${fmtDate(cur.open)} · 누적 <b>${man(la.acc)}</b> (D+${dayN(la.d,cur.open)}) · 목표 150만`;
    } else if(bkKey && (MV.booking[bkKey]||[]).length){
      const b=MV.booking[bkKey][MV.booking[bkKey].length-1];
      const dd=Math.ceil((new Date(2026,7,5)-new Date())/864e5);
      nextEl.innerHTML=`🔜 <b>${bkKey}</b> · ${dd>0?`D-${dd} (8/5 개봉)`:"개봉"} · 예매율 <b>${b.rate}%</b> · 예매 <b>${man(b.book)}</b> · 목표 150만 <span>(KOBIS 실시간)</span>`;
    } else {
      nextEl.innerHTML=`🔜 <b>사랑의 하츄핑2: 고래보석의 전설</b> 2026-08-05 개봉 · 목표 150만 <span>(더벨)</span>`;
    }
    subEl.textContent=cur
      ? "1편 vs 2편 · 같은 개봉 N일차(D+)로 정렬해 페이스 비교 · 선=누적, 막대=당일"
      : "KOBIS 일별 확정 관객 · 막대=당일(우축) · 선=누적(좌축) · x축 개봉 N일차";
    srcEl.textContent=`자료: KOBIS 영화관입장권통합전산망 · ${MV.asOf||""}`;
    // 개봉 전 2편은 별도 예매관객 스트립으로 표시(개봉하면 위 곡선에 합류하므로 숨김)
    const bkEl=document.getElementById("samgBooking");
    if(bkEl){
      if(!cur && bk2.length){
        bkEl.innerHTML=`<div class="samg-bk-t">🎟️ 2편 <b>${bkKey||"고래보석의 전설"}</b> · 개봉 전 예매관객 <span style="color:var(--muted2);font-weight:600">(개봉까지 매일 누적)</span></div>`+bookingChart(bk2, open2||NEXT_OPEN);
        bkEl.style.display="";
      } else bkEl.style.display="none";
    }
  }
  render();

  // 극장 흥행 탭 바로가기
  const go=document.getElementById("samgGoTab");
  if(go) go.addEventListener("click",()=>{ const b=document.querySelector('nav .tabs button[data-k="boxoffice"], nav button[data-k="boxoffice"], [data-k="boxoffice"]'); if(b) b.click(); ov.hidden=true; });

  // ── 표시/닫기 로직 ──
  const KEY="samgPopupHiddenDay", today=new Date().toISOString().slice(0,10);
  const open =()=>{ ov.hidden=false; };
  const close=()=>{ ov.hidden=true;
    if(document.getElementById("samgDismiss").checked){ try{localStorage.setItem(KEY,today);}catch(e){} } };
  document.getElementById("samgClose").addEventListener("click",close);
  ov.addEventListener("click",e=>{ if(e.target===ov) close(); });
  document.addEventListener("keydown",e=>{ if(e.key==="Escape"&&!ov.hidden) close(); });
  document.getElementById("samgReopen").addEventListener("click",open);
  // 들어가자마자 표시 (단, '오늘 하루 보지 않기' 선택한 날은 생략)
  let hid=""; try{ hid=localStorage.getItem(KEY)||""; }catch(e){}
  if(hid!==today) setTimeout(open,350);
})();

/* 모든 데이터 const 초기화 후에 섹션 헤더 타임스탬프를 채운다(TREND 등 TDZ 회피) */
setSecUpdates();

/* ==== 아마존 (amazon-beauty-tracker → const AMAZON) ====
   판매량은 아마존이 상품페이지에 공개하는 구간값의 하한이다. 매출은 USD 로 담겨 있고
   원화 환산은 여기서 LIVE 의 실시간 USDKRW 로 한다(환율이 굳지 않게).
   절대값은 하한이라 과소평가되므로 화면에서도 '이상' 표기를 유지할 것. */
let amzMetric = "rev";
// 마켓 코드는 데이터에 그대로 쓰고, 화면에서만 한글로 바꾼다
const AMZ_MK_NAME = {US:"미국", UK:"영국", DE:"독일", FR:"프랑스", IT:"이탈리아",
  ES:"스페인", NL:"네덜란드", SE:"스웨덴", PL:"폴란드", JP:"일본"};
const amzMk = c => AMZ_MK_NAME[c] || c;

function amzFx(){
  return ((typeof LIVE!=="undefined" && LIVE.market && LIVE.market.FX && LIVE.market.FX.USDKRW) || 1380);
}
function amzEok(usd){ return (usd||0) * amzFx() / 1e8; }
function amzNum(n){ return (n||0).toLocaleString("ko-KR"); }

/* 변화율 배지. 한국 관행대로 상승=빨강(--up), 하락=파랑(--down). */
function amzDelta(cur, prev){
  if(prev===null || prev===undefined || !prev || !cur) return "";
  const p = (cur - prev) / prev * 100;
  if(Math.abs(p) < 0.5) return `<span style="color:var(--muted);font-size:11.5px">-</span>`;
  const c = p>0 ? "var(--up)" : "var(--down)";
  return `<span style="color:${c};font-size:11.5px;font-weight:700">${p>0?"▲":"▼"}${Math.abs(p).toFixed(0)}%</span>`;
}

/* 'n'(우리가 추적 중인 제품 수)은 화면에 내지 않는다. 그건 우리 수집 범위일 뿐
   브랜드의 성과가 아니다 — 추적을 늘리면 저절로 커지는 숫자다.
   대신 'il' = 그날 베스트셀러 목록(US 탑100 · 유럽 탑50)에 실제로 들어간 SKU 수를 쓴다.
   n 은 데이터에 그대로 남겨 두므로 필요하면 언제든 꺼내 볼 수 있다. */
/* 브랜드 로고 — 각 브랜드 공식 사이트 아이콘을 파일 안에 박아 둔다(총 14KB).
   외부에서 불러오면 그 서버가 죽거나 주소가 바뀌면 로고가 통째로 사라지고,
   보는 사람 IP 가 그 서버로 새어 나간다. 자체 포함이 이 프로젝트 방식과도 맞다.
   갱신하려면 각 사이트 파비콘을 다시 받아 이 상수만 갈아 끼우면 된다. */

/* 흰 판을 깔아야 하는 로고 — 배경이 뚫려 있고(테두리 투명 25% 초과) 잉크가 어두워
   (평균 밝기 170 미만) 어두운 테마에서 그냥 두면 묻히는 것들. 캔버스로 실측해 골랐다.
   나머지(퓨리토·조선미녀·닥터멜락신)는 배경이 이미 차 있어 판을 깔면 흰 링만 생긴다. */

/* 브랜드 배지. 로고가 없으면 이름 해시 이니셜 배지로 떨어진다(stockLogo 와 같은 모양). */
function brandLogo(brand){
  const src = BRAND_LOGO[brand];
  if(!src){
    // 브랜드 로고를 안 박아 둔 경우(예: 달바 — 운영사가 상장사라 종목 로고가 이미 있다)
    // 운영사 이름으로 넘긴다. stockLogo 가 LIVE.stocks 에서 코드를 찾아 토스 CDN 이미지를 준다.
    const b = (typeof AMAZON!=="undefined" && (AMAZON.brands||[]).find(x=>x.brand===brand)) || null;
    const key = (b && b.owner) || brand;
    return (typeof stockLogo==="function") ? stockLogo(key) : "";
  }
  // 파일 안에 박힌 데이터라 lazy 로딩은 의미가 없다(네트워크 요청이 없다).
  // 흰 판은 필요한 로고에만. 배경이 이미 찬 로고에 깔면 둥근 모서리에 흰 링이 생긴다.
  const plate = BRAND_PLATE.indexOf(brand)>=0 ? " plate" : "";
  return `<span class="nm-logo${plate}"><img src="${src}" alt=""></span>`;
}

function amzMetricVal(h, m){
  if(!h) return 0;
  return m==="rev" ? amzEok(h.rev) : m==="u" ? h.u : (h.il!=null ? h.il : 0);
}
function amzMetricFmt(v, m){
  return m==="rev" ? `${v.toFixed(1)}억` : m==="u" ? `${amzNum(Math.round(v))}개` : `${v}개`;
}

function renderAmazon(){
  if(typeof AMAZON==="undefined" || !AMAZON.brands || !AMAZON.brands.length) return;
  const asOf=document.getElementById("amzAsOf");
  if(asOf) asOf.textContent = `${AMAZON.latest} 기준 · 환율 ${amzNum(Math.round(amzFx()))}원`;

  const B = AMAZON.brands.slice().sort((a,b)=>{
    const x=amzMetricVal(a.hist[a.hist.length-1], amzMetric);
    const y=amzMetricVal(b.hist[b.hist.length-1], amzMetric);
    return y-x;
  });
  const unit = amzMetric==="rev" ? "월 매출(원)" : amzMetric==="u" ? "월 판매량" : "베스트셀러 진입 SKU";

  /* ---- 브랜드 카드 ---- */
  document.getElementById("amzCards").innerHTML = B.map(b=>{
    const n=b.hist.length, h=b.hist[n-1], prev=n>1?b.hist[n-2]:null;
    const v=amzMetricVal(h,amzMetric), pv=prev?amzMetricVal(prev,amzMetric):null;
    // 로고는 운영사 기준. stockLogo 는 LIVE.stocks 에 코드가 있으면 토스 CDN 이미지를,
    // 없으면 이름 해시로 색을 정한 이니셜 배지를 준다 — 비상장도 그대로 쓸 수 있다.
    const own = b.owner || "미확인";
    // 카드 제목이 브랜드명이니 로고도 브랜드 것이어야 한다.
    // 예전엔 운영사 로고였는데, 비상장 운영사(바이오던스·퓨리토·구다이 등)는 전부
    // 토스 CDN 에 없어서 이니셜 배지로 빠졌다.
    const logo = brandLogo(b.brand);
    const tie = b.listed
      ? `<span class="clickable" data-stock="${b.stock}" style="font-weight:700">${own}</span>`
      : `<span style="color:var(--muted)">${own}</span><span class="pill" style="margin-left:5px;font-size:10px">비상장</span>`;
    return `<div class="kpi" title="${b.brand} — ${unit}. 아마존 공개 판매량 기준 하한값">
      <div style="display:flex;align-items:center;gap:7px;margin-bottom:6px">${logo}
        <span style="font-weight:800;font-size:13.5px">${b.brand}</span></div>
      <div style="font-size:11.5px;margin-bottom:8px">${tie}</div>
      ${b.memo?`<div style="font-size:10.5px;color:var(--muted);margin:-4px 0 7px;line-height:1.4">${b.memo}</div>`:""}
      <div style="display:flex;align-items:baseline;gap:7px">
        <span style="font-size:21px;font-weight:800">${amzMetricFmt(v,amzMetric)}</span>
        ${amzDelta(v,pv)}
      </div>
      <div style="font-size:11.5px;color:var(--muted);margin-top:5px">
        ${h.bsr?`최고 BSR ${amzNum(h.bsr)}`:""}${h.bsr&&h.il&&amzMetric!=="n"?" · ":""}${h.il&&amzMetric!=="n"?`진입 ${h.il}개`:""}</div>
    </div>`;
  }).join("");

  /* ---- 브랜드 x 국가 ---- */
  const MK = AMAZON.markets;
  const idx = {rev:1, u:0, n:2};
  const cell = (mkArr)=>{
    if(!mkArr) return `<td style="text-align:right;color:var(--muted2)">·</td>`;
    let v = mkArr[idx[amzMetric]] || 0;
    if(amzMetric==="rev") v = amzEok(v);
    return `<td style="text-align:right">${amzMetric==="rev"?v.toFixed(1):amzNum(Math.round(v))}</td>`;
  };
  document.getElementById("amzMatrix").innerHTML = `<div class="tbl-wrap"><table>
    <thead><tr><th style="text-align:left">브랜드</th><th style="text-align:left">운영사</th>
      ${MK.map(m=>`<th style="text-align:right">${amzMk(m)}</th>`).join("")}
      <th style="text-align:right">합계</th></tr></thead>
    <tbody>${B.map(b=>{
      const h=b.hist[b.hist.length-1]; const mk=(h&&h.mk)||{};
      const tot=amzMetric==="rev"?amzEok(h?h.rev:0):amzMetricVal(h,amzMetric);
      return `<tr><td style="text-align:left;font-weight:700"><span style="display:inline-flex;align-items:center;gap:6px">${brandLogo(b.brand)}${b.brand}</span></td>
        <td style="text-align:left"><span style="display:inline-flex;align-items:center;gap:6px">
          ${typeof stockLogo==="function"?stockLogo(b.owner||"미확인"):""}
          <span style="${b.listed?"font-weight:700":"color:var(--muted)"}">${b.owner||"미확인"}</span></span></td>
        ${MK.map(m=>cell(mk[m])).join("")}
        <td style="text-align:right;font-weight:800">${amzMetric==="rev"?tot.toFixed(1):amzNum(Math.round(tot))}</td></tr>`;
    }).join("")}</tbody>
    <tfoot><tr style="border-top:2px solid var(--line)">
      <td style="text-align:left;font-weight:800">합계</td><td></td>
      ${MK.map(m=>{
        let s=0; B.forEach(b=>{const h=b.hist[b.hist.length-1];const a=h&&h.mk&&h.mk[m];
          if(a) s += amzMetric==="rev" ? amzEok(a[1]) : a[idx[amzMetric]]||0;});
        return `<td style="text-align:right;font-weight:800">${amzMetric==="rev"?s.toFixed(1):amzNum(Math.round(s))}</td>`;
      }).join("")}
      <td style="text-align:right;font-weight:800">${(()=>{let s=0;B.forEach(b=>{const h=b.hist[b.hist.length-1];
        s += amzMetric==="rev"?amzEok(h?h.rev:0):amzMetricVal(h,amzMetric);});
        return amzMetric==="rev"?s.toFixed(1):amzNum(Math.round(s));})()}</td>
    </tr></tfoot></table></div>
    <div style="font-size:11.5px;color:var(--muted);margin-top:7px">
      ${amzMetric==="rev"?"단위 억원/월 (USD→원 실시간 환산) · 모두 <b>하한값</b>":amzMetric==="u"?"단위 개/월 · 모두 <b>하한값</b>":"그날 베스트셀러 목록(US 탑100 · 유럽 탑50)에 들어간 제품 수"}</div>`;

  /* ---- 주요 제품 ---- */
  const rows=[];
  B.forEach(b=>(b.top||[]).forEach(p=>rows.push({...p, brand:b.brand})));
  rows.sort((a,b)=>(b.u||0)-(a.u||0));
  document.getElementById("amzTop").innerHTML = `<div class="tbl-wrap"><table>
    <thead><tr><th style="text-align:left">브랜드</th><th>국가</th><th style="text-align:right">BSR</th>
      <th style="text-align:left">하위 카테고리</th><th style="text-align:right">월 판매량</th>
      <th style="text-align:right">가격</th><th style="text-align:left">제품</th></tr></thead>
    <tbody>${rows.slice(0,40).map(p=>`<tr>
      <td style="text-align:left;font-weight:700"><span style="display:inline-flex;align-items:center;gap:6px">${brandLogo(p.brand)}${p.brand}</span></td>
      <td>${amzMk(p.mk)}</td>
      <td style="text-align:right">${p.bsr?amzNum(p.bsr):"-"}</td>
      <td style="text-align:left;color:var(--muted)">${p.sub?`${p.sub} ${p.subR}`:"-"}</td>
      <td style="text-align:right">${p.u?amzNum(p.u)+"+":"-"}</td>
      <td style="text-align:right">${p.p?`${p.p} ${p.cur}`:"-"}</td>
      <td style="text-align:left;white-space:normal;max-width:360px">${p.name}</td></tr>`).join("")}
    </tbody></table></div>`;
}

(function amzInit(){
  const seg=document.getElementById("amzMetricSeg");
  if(!seg) return;
  seg.addEventListener("click",e=>{
    const b=e.target.closest("button"); if(!b) return;
    amzMetric=b.dataset.m;
    seg.querySelectorAll("button").forEach(x=>x.classList.toggle("active",x===b));
    renderAmazon();
  });
})();

