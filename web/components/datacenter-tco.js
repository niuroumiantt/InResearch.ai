(() => {
  'use strict';
  const HOURS=8760;
  const CATS=['capex_facility','capex_it','energy','demand','water','staff','maintenance','maintenance_it','software','insurance_tax','bandwidth','other','lease','decommission'];
  const IT_ONLY=['capex_it','maintenance_it'];
  const LABEL={capex_facility:'设施资本开支',capex_it:'IT 资本开支与更新',energy:'电费',demand:'需量费',water:'水费',staff:'运维人员',maintenance:'设施维护',maintenance_it:'IT 维护',software:'软件与 DCIM',insurance_tax:'保险与财产税',bandwidth:'带宽',other:'其他运营',lease:'租金 / 托管费',decommission:'退役'};
  const COLOR={capex_facility:'var(--ui-green)',capex_it:'var(--ui-accent)',energy:'var(--ui-yellow)',demand:'color-mix(in srgb,var(--ui-yellow) 60%,var(--ui-surface))',water:'color-mix(in srgb,var(--ui-info-ink,#405879) 70%,var(--ui-surface))',staff:'var(--ui-purple)',maintenance:'color-mix(in srgb,var(--ui-green) 60%,var(--ui-surface))',maintenance_it:'color-mix(in srgb,var(--ui-accent) 55%,var(--ui-surface))',software:'color-mix(in srgb,var(--ui-purple) 55%,var(--ui-surface))',insurance_tax:'var(--ui-muted)',bandwidth:'color-mix(in srgb,var(--ui-muted) 60%,var(--ui-surface))',other:'color-mix(in srgb,var(--ui-muted) 40%,var(--ui-surface))',lease:'var(--ui-red)',decommission:'color-mix(in srgb,var(--ui-red) 50%,var(--ui-surface))'};
  let spec;
  function compute(a){
    const mw=a.it_mw,itKw=mw*1000,red=spec.redundancy_factors[a.redundancy],C=a.construction_years,H=a.horizon_years,own=a.facility_mode==='own';
    const hard={building:own?a.capex_building:0,electrical:own?a.capex_electrical*red.electrical:0,mechanical:own?a.capex_mechanical*red.mechanical:0,fitout:a.facility_mode!=='colo'?a.capex_fitout:0,land:own?a.land_per_mw:0};
    const hardSum=Object.values(hard).reduce((x,y)=>x+y,0),soft=(hardSum-hard.land)*a.soft_cost_pct,contingency=(hardSum-hard.land)*a.contingency_pct;
    const facilityPerMw=hardSum+soft+contingency,facilityCapex=facilityPerMw*mw*1e6,hardExLand=(hardSum-hard.land)*mw*1e6,itCapex=a.it_capex_per_kw*itKw;
    const years=[];
    for(let y=0;y<C+H;y++){
      const row={year:y-C+1,it_kwh:0,gpu_hours:0};CATS.forEach(k=>row[k]=0);
      if(y<C){row.capex_facility=facilityCapex/C;years.push(row);continue;}
      const t=y-C,ramp=t===0?a.ramp_year1:t===1?a.ramp_year2:1,escO=Math.pow(1+a.opex_escalation,t),escP=Math.pow(1+a.power_escalation,t);
      if(t===0)row.capex_it=itCapex;else if(a.it_refresh_years&&t%a.it_refresh_years===0&&t<H)row.capex_it=itCapex*a.refresh_cost_factor;
      const itLoadKw=itKw*a.load_factor*ramp,itKwh=itLoadKw*HOURS;row.it_kwh=itKwh;
      row.energy=itKwh*a.pue*a.power_price*escP;row.demand=itKw*a.pue*ramp*a.demand_rate*12*escP;row.water=itKwh*a.wue/1000*a.water_price*escO;
      row.staff=a.fte_per_mw*mw*a.cost_per_fte*a.labor_index*escO;row.maintenance=hardExLand*a.maint_pct_facility*escO;row.maintenance_it=itCapex*a.maint_pct_it*escO;
      row.software=a.software_per_mw*mw*1e6*escO;row.insurance_tax=facilityCapex*(a.insurance_pct+(own?a.property_tax_rate:0))*escO;row.bandwidth=a.bandwidth_per_mw*mw*1e6*escO;row.other=a.other_opex_per_mw*mw*1e6*escO;
      if(a.facility_mode==='lease')row.lease=a.shell_rent_per_mw*mw*1e6*escO;else if(a.facility_mode==='colo')row.lease=a.colo_rate*itKw*12*escO;
      if(t===H-1)row.decommission=facilityCapex*a.decommission_pct;
      row.gpu_hours=mw*a.gpus_per_mw*HOURS*a.gpu_utilization*ramp;years.push(row);
    }
    years.forEach(r=>{r.total=CATS.reduce((s,k)=>s+r[k],0);r.capex=r.capex_facility+r.capex_it;r.opex=r.total-r.capex;});
    const r=a.wacc,disc=y=>1/Math.pow(1+r,y+1),pv={};CATS.forEach(k=>pv[k]=years.reduce((s,row,i)=>s+row[k]*disc(i),0));
    const pvTotal=CATS.reduce((s,k)=>s+pv[k],0),nominalTotal=years.reduce((s,row)=>s+row.total,0);
    const pvItKwh=years.reduce((s,row,i)=>s+row.it_kwh*disc(i),0),pvGpuHours=years.reduce((s,row,i)=>s+row.gpu_hours*disc(i),0);
    let annuity=0;for(let t=0;t<H;t++)annuity+=disc(C+t);
    const levelised=pvTotal/annuity,lev={};CATS.forEach(k=>lev[k]=pv[k]/annuity);
    const facilityLevelised=levelised-IT_ONLY.reduce((s,k)=>s+lev[k],0);
    const out={inputs:a,capexPerMw:{...hard,soft,contingency,facility:facilityPerMw,it:a.it_capex_per_kw/1000},facilityCapex,itCapex,years,pv,pvTotal,nominalTotal,annuity,levelised,lev,
      perMwYear:levelised/mw,perKwMonth:levelised/itKw/12,perKwMonthFacility:facilityLevelised/itKw/12,perItKwh:pvItKwh?pvTotal/pvItKwh:null,perGpuHour:pvGpuHours?pvTotal/pvGpuHours:null,
      capexShare:(pv.capex_facility+pv.capex_it)/pvTotal,facilityLevelised};
    const bm=a.business_model;let market=null,cost=null,unit=null;
    if(bm==='gpu_rental'&&out.perGpuHour){market=a.price_gpu_hour;cost=out.perGpuHour;unit='$/GPU·h';}else if(bm==='colo'){market=a.price_colo_kw_month;cost=out.perKwMonthFacility;unit='$/kW·月';}
    out.benchmark={model:bm,market,cost,unit,margin:market?(market-cost)/market:null};
    return out;
  }
  window.InresearchTco={compute:a=>compute(a)};

  const app=document.getElementById('tco-app');if(!app)return;
  const byId=id=>document.getElementById(id);
  const make=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined&&text!==null)e.textContent=text;return e;};
  const svgEl=(tag,attrs)=>{const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const k in attrs)e.setAttribute(k,attrs[k]);return e;};
  const money=n=>n==null||!isFinite(n)?'—':(n<0?'−':'')+(Math.abs(n)>=1e9?'$'+(Math.abs(n)/1e9).toFixed(2)+'B':Math.abs(n)>=1e6?'$'+(Math.abs(n)/1e6).toFixed(1)+'M':'$'+Math.round(Math.abs(n)).toLocaleString());
  const pct=(x,d=1)=>x==null||!isFinite(x)?'—':(x*100).toFixed(d)+'%';
  const num=(x,d=1)=>x==null||!isFinite(x)?'—':Number(x).toLocaleString(undefined,{maximumFractionDigits:d,minimumFractionDigits:d});
  const delta=(cur,base,fmt,lowerIsBetter=true)=>{if(base==null||cur==null||!isFinite(base)||!isFinite(cur))return null;const d=cur-base;if(Math.abs(d)<1e-9*Math.max(1,Math.abs(base)))return {text:'= 基准',cls:'flat'};const rel=base?d/base:null;return {text:(d>0?'+':'−')+fmt(Math.abs(d))+(rel!=null?' ('+(d>0?'+':'−')+Math.abs(rel*100).toFixed(1)+'%)':''),cls:(d<0)===lowerIsBetter?'better':'worse'};};
  const chip=(d)=>{const c=make('span','delta '+(d?d.cls:'flat'),d?d.text:'—');return c;};
  let values,baseline,baselineLabel='',activePreset='',prices,tree;

  function applyTable(a,key,table){const rec=spec[table][a[key]];if(!rec)return;for(const k in rec){if(k in a&&k!=='label'&&k!=='source')a[k]=rec[k];}}
  function withPreset(id){const a={...spec.assumptions};const p=spec.presets[id];if(!p)return a;const ch={...p.changes};for(const [key,table] of [['site','sites'],['cooling','coolings'],['it_class','it_classes']]){if(ch[key]){a[key]=ch[key];applyTable(a,key,table);}}Object.assign(a,ch);return a;}
  function applyPreset(id){values=withPreset(id);activePreset=id;renderInputs();render();}
  function setBaseline(label){baseline=compute({...values});baselineLabel=label||(activePreset?spec.presets[activePreset].label:'当前假设');byId('baseline-label').textContent='对比基准：'+baselineLabel;render();}

  const STATUS={input:['用户给定','input'],sourced:['已有来源','sourced'],assumed:['作者假设','assumed'],needed:['待获取','needed']};
  function renderPresets(){const host=byId('presets');host.replaceChildren();for(const [id,p] of Object.entries(spec.presets)){const b=make('button','',p.label);b.type='button';b.dataset.id=id;b.addEventListener('click',()=>applyPreset(id));host.append(b);}}
  function markPreset(){document.querySelectorAll('#presets button').forEach(b=>b.classList.toggle('active',b.dataset.id===activePreset));}
  function renderInputs(){
    const form=byId('tco-inputs');const openState={};form.querySelectorAll('details').forEach(d=>openState[d.dataset.group]=d.open);form.replaceChildren();
    spec.groups.forEach((group,gi)=>{
      const box=make('details','input-group');box.dataset.group=group.id;box.open=group.id in openState?openState[group.id]:gi<2;
      const sum=make('summary');sum.append(make('b','',group.label),make('small','',group.hint),make('output','group-total'));box.append(sum);
      for(const id of group.inputs){
        const cfg=spec.inputs[id],ev=spec.evidence[id]||{status:'needed'},row=make('div','input-row'),label=make('label');label.htmlFor='input-'+id;
        const name=make('span','',cfg.label),badge=make('i','badge '+STATUS[ev.status][1]);badge.title=STATUS[ev.status][0]+(ev.note?'：'+ev.note:'')+(ev.fetch_what?'｜抓取：'+ev.fetch_what:'');
        label.append(badge,name);if(cfg.note)label.append(make('small','',cfg.note));
        const holder=make('div','input-box');
        if(cfg.type==='select'){const sel=make('select');sel.id='input-'+id;const opts=cfg.options?Object.entries(spec[cfg.options]).map(([k,v])=>[k,v.label]):cfg.choices;for(const [v,l] of opts){const o=make('option','',l);o.value=v;sel.append(o);}sel.value=values[id];
          sel.addEventListener('change',()=>{values[id]=sel.value;if(cfg.options)applyTable(values,id,cfg.options);activePreset='';renderInputs();render();});holder.append(sel);}
        else{const input=make('input');input.type='number';input.id='input-'+id;input.min=cfg.min;input.max=cfg.max;input.step=cfg.step;input.value=cfg.display==='percent'?Math.round(values[id]*10000)/100:values[id];
          input.addEventListener('input',()=>{const raw=Number(input.value);if(!Number.isFinite(raw))return;values[id]=cfg.display==='percent'?raw/100:raw;activePreset='';render();});holder.append(input,make('span','',cfg.unit));}
        row.append(label,holder);box.append(row);
      }
      form.append(box);
    });
  }
  const GROUP_CATS={project:null,site:['energy','demand','water','insurance_tax'],design:['energy','water','capex_facility'],it:['capex_it','maintenance_it'],build:['capex_facility','lease'],operate:['staff','maintenance','software','bandwidth','other','decommission'],finance:null};
  function renderGroupTotals(r){document.querySelectorAll('#tco-inputs details').forEach(d=>{const cats=GROUP_CATS[d.dataset.group];const out=d.querySelector('.group-total');if(!cats){out.textContent='';return;}const v=cats.reduce((s,k)=>s+r.lev[k],0);out.textContent='相关成本 '+money(v)+'/年';});}

  function renderKpis(r){
    const b=baseline||r,a=r.inputs;
    const tiles=[['kpi-lev','平准化年成本',money(r.levelised),delta(r.levelised,b.levelised,money)],['kpi-mw','每 MW·年',money(r.perMwYear),delta(r.perMwYear,b.perMwYear,money)],['kpi-kw','每 kW·月','$'+num(r.perKwMonth,0),delta(r.perKwMonth,b.perKwMonth,x=>'$'+num(x,0))],['kpi-kwh','每 IT kWh','$'+num(r.perItKwh,3),delta(r.perItKwh,b.perItKwh,x=>'$'+num(x,3))],['kpi-gpu','每付费 GPU 小时',r.perGpuHour?'$'+num(r.perGpuHour,2):'非 GPU',delta(r.perGpuHour,b.perGpuHour,x=>'$'+num(x,2))],['kpi-capex','资本开支占比',pct(r.capexShare,0),delta(r.capexShare,b.capexShare,x=>pct(x,1),false)]];
    for(const [id,label,val,d] of tiles){const el=byId(id);el.replaceChildren(make('small','',label),make('strong','',val),chip(d));}
    byId('project-line').textContent=`${a.it_mw} MW · ${spec.sites[a.site]?.label||a.site} · ${spec.coolings[a.cooling]?.label||a.cooling} · ${spec.it_classes[a.it_class]?.label||a.it_class} · ${spec.redundancy_factors[a.redundancy].label} · ${({own:'自建自持',lease:'租带电壳',colo:'托管'})[a.facility_mode]} · 建设 ${a.construction_years} 年 + 运营 ${a.horizon_years} 年 · 设施 ${num(r.capexPerMw.facility,1)} $M/MW + IT ${num(r.capexPerMw.it,1)} $M/MW · TCO 现值 ${money(r.pvTotal)}`;
  }

  function renderStructure(r){
    const host=byId('structure');host.replaceChildren();const b=baseline||r;
    const W=760,barH=26,left=70;
    const svg=svgEl('svg',{viewBox:`0 0 ${W} 92`,class:'chart'});
    const draw=(res,y,label)=>{let x=left;const total=res.levelised;svg.append(Object.assign(svgEl('text',{x:left-8,y:y+17,'text-anchor':'end',class:'chart-label'}),{textContent:label}));
      for(const k of CATS){const v=res.lev[k];if(v<=0)continue;const w=v/total*(W-left-8);const rect=svgEl('rect',{x,y,width:w,height:barH,fill:COLOR[k]});rect.append(Object.assign(svgEl('title'),{textContent:LABEL[k]+' '+money(v)+' · '+pct(v/total)}));svg.append(rect);
        if(w>46)svg.append(Object.assign(svgEl('text',{x:x+w/2,y:y+17,'text-anchor':'middle',class:'chart-inbar'}),{textContent:pct(v/total,0)}));x+=w;}};
    draw(r,8,'当前');draw(b,52,'基准');host.append(svg);
    const legend=byId('structure-legend');legend.replaceChildren();
    for(const k of CATS){const v=r.lev[k],bv=b.lev[k];if(v<=0&&bv<=0)continue;const it=make('div','legend-row');const sw=make('i');sw.style.background=COLOR[k];const d=delta(v,bv,money);it.append(sw,make('span','',LABEL[k]),make('strong','',money(v)),chip(d));legend.append(it);}
  }

  function renderTimeline(r){
    const host=byId('timeline');host.replaceChildren();const b=baseline||r;
    const W=760,H=260,left=54,bottom=34,top=12,n=r.years.length,colW=(W-left-10)/n;
    const max=Math.max(...r.years.map(y=>y.total),...b.years.map(y=>y.total))*1.05,scale=(H-top-bottom)/max;
    const svg=svgEl('svg',{viewBox:`0 0 ${W} ${H}`,class:'chart'});
    for(let i=0;i<=4;i++){const v=max/4*i,y=H-bottom-v*scale;svg.append(svgEl('line',{x1:left,y1:y,x2:W-8,y2:y,stroke:'var(--ui-line)','stroke-dasharray':i?'2 3':''}));svg.append(Object.assign(svgEl('text',{x:left-6,y:y+4,'text-anchor':'end',class:'chart-label'}),{textContent:money(v)}));}
    r.years.forEach((row,i)=>{let y0=H-bottom;const x=left+i*colW+2,w=Math.max(2,colW-4);
      for(const k of CATS){const v=row[k];if(v<=0)continue;const h=v*scale;const rect=svgEl('rect',{x,y:y0-h,width:w,height:h,fill:COLOR[k]});rect.append(Object.assign(svgEl('title'),{textContent:`第 ${row.year} 年 · ${LABEL[k]} ${money(v)}`}));svg.append(rect);y0-=h;}
      if(i%Math.ceil(n/12)===0||i===n-1)svg.append(Object.assign(svgEl('text',{x:x+w/2,y:H-bottom+14,'text-anchor':'middle',class:'chart-label'}),{textContent:row.year<=0?'建':String(row.year)}));
    });
    if(baseline&&b.years.length===n){const pts=b.years.map((row,i)=>`${left+i*colW+colW/2},${H-bottom-row.total*scale}`).join(' ');svg.append(svgEl('polyline',{points:pts,fill:'none',stroke:'var(--ui-ink)','stroke-width':1.5,'stroke-dasharray':'4 3'}));}
    svg.append(Object.assign(svgEl('text',{x:W-8,y:H-4,'text-anchor':'end',class:'chart-label'}),{textContent:'建 = 建设期；虚线 = 基准年度合计；名义金额'}));
    host.append(svg);
    byId('timeline-note').textContent=`名义合计 ${money(r.nominalTotal)}，折现后 TCO 现值 ${money(r.pvTotal)}（折现率 ${pct(r.inputs.wacc,1)}）；IT 每 ${r.inputs.it_refresh_years} 年更新一次（更新造价 ${pct(r.inputs.refresh_cost_factor,0)}），电价年涨 ${pct(r.inputs.power_escalation,1)}，运营成本年涨 ${pct(r.inputs.opex_escalation,1)}。`;
  }

  function renderTable(r){
    const host=byId('cost-table');host.replaceChildren();const b=baseline||r,itKw=r.inputs.it_mw*1000;
    const table=make('table','bi'),thead=make('thead'),tr=make('tr');for(const h of ['成本项','平准化年成本','占比','每 kW·月','TCO 现值','名义合计','对基准'])tr.append(make('th','',h));thead.append(tr);table.append(thead);
    const body=make('tbody');const nominal={};CATS.forEach(k=>nominal[k]=r.years.reduce((s,y)=>s+y[k],0));
    for(const k of CATS){const v=r.lev[k];if(v<=0&&(b.lev[k]||0)<=0)continue;const row=make('tr');const sw=make('i');sw.style.background=COLOR[k];const c1=make('td');c1.append(sw,document.createTextNode(LABEL[k]));row.append(c1,make('td','',money(v)),make('td','',pct(v/r.levelised)),make('td','','$'+num(v/itKw/12,0)),make('td','',money(r.pv[k])),make('td','',money(nominal[k])));const dc=make('td');dc.append(chip(delta(v,b.lev[k],money)));row.append(dc);body.append(row);}
    const tot=make('tr','total');tot.append(make('td','','合计'),make('td','',money(r.levelised)),make('td','','100%'),make('td','','$'+num(r.perKwMonth,0)),make('td','',money(r.pvTotal)),make('td','',money(r.nominalTotal)));const dc=make('td');dc.append(chip(delta(r.levelised,b.levelised,money)));tot.append(dc);body.append(tot);
    table.append(body);host.append(table);
  }

  function renderCapex(r){
    const host=byId('capex-bars');host.replaceChildren();const b=baseline||r;
    const items=[['building','建筑与土建'],['electrical','电气'],['mechanical','机械'],['fitout','机房装配'],['land','土地'],['soft','软成本'],['contingency','不可预见费'],['it','IT 设备']];
    const max=Math.max(...items.map(([k])=>Math.max(r.capexPerMw[k],b.capexPerMw[k])),0.1);
    for(const [k,l] of items){const v=r.capexPerMw[k],bv=b.capexPerMw[k];const row=make('div','bar-row'),lab=make('label','',l),track=make('div','bar-track'),fill=make('div','bar-fill'),ghost=make('div','bar-ghost');fill.style.width=(v/max*100)+'%';ghost.style.width=(bv/max*100)+'%';fill.style.background=k==='it'?'var(--ui-accent)':'var(--ui-green)';track.append(ghost,fill);const out=make('output','',num(v,2)+' $M/MW');row.append(lab,track,out,chip(delta(v,bv,x=>num(x,2))));host.append(row);}
    byId('capex-note').textContent=`设施 ${num(r.capexPerMw.facility,1)} $M/MW（硬成本 × 冗余系数 ${spec.redundancy_factors[r.inputs.redundancy].label}，加软成本 ${pct(r.inputs.soft_cost_pct,0)} 与不可预见费 ${pct(r.inputs.contingency_pct,0)}）+ IT ${num(r.capexPerMw.it,1)} $M/MW；浅色为基准。`;
  }

  function renderSensitivity(r){
    const host=byId('tornado');host.replaceChildren();const base=r.perKwMonth,rows=[];
    for(const d of spec.sensitivity_drivers){const lo={...r.inputs},hi={...r.inputs};if(d.delta_abs){lo[d.key]=Math.max(0.5,r.inputs[d.key]-d.delta_abs);hi[d.key]=r.inputs[d.key]+d.delta_abs;}else{lo[d.key]=r.inputs[d.key]*(1-d.delta);hi[d.key]=r.inputs[d.key]*(1+d.delta);}
      rows.push({label:d.label+(d.delta_abs?` ±${d.delta_abs}`:` ±${Math.round(d.delta*100)}%`),lo:compute(lo).perKwMonth-base,hi:compute(hi).perKwMonth-base});}
    rows.sort((x,y)=>Math.max(Math.abs(y.lo),Math.abs(y.hi))-Math.max(Math.abs(x.lo),Math.abs(x.hi)));
    const W=760,rowH=24,left=170,mid=left+(W-left-60)/2,span=Math.max(...rows.map(x=>Math.max(Math.abs(x.lo),Math.abs(x.hi))),1),scale=(W-left-60)/2/span;
    const svg=svgEl('svg',{viewBox:`0 0 ${W} ${rows.length*rowH+6}`,class:'chart'});svg.append(svgEl('line',{x1:mid,y1:0,x2:mid,y2:rows.length*rowH+6,stroke:'var(--ui-line)'}));
    rows.forEach((row,i)=>{const y=i*rowH+3;svg.append(Object.assign(svgEl('text',{x:left-8,y:y+14,'text-anchor':'end',class:'chart-label'}),{textContent:row.label}));
      for(const v of [row.lo,row.hi]){const w=Math.abs(v)*scale,x=v<0?mid-w:mid;const rect=svgEl('rect',{x,y,width:Math.max(1,w),height:17,fill:v<0?'var(--ui-green)':'var(--ui-red)',opacity:.85});rect.append(Object.assign(svgEl('title'),{textContent:row.label+' → $'+num(base+v,0)+'/kW·月'}));svg.append(rect);svg.append(Object.assign(svgEl('text',{x:v<0?x-4:x+w+4,y:y+13,'text-anchor':v<0?'end':'start',class:'chart-value'}),{textContent:(v>=0?'+':'−')+'$'+num(Math.abs(v),0)}));}});
    host.append(svg);byId('tornado-note').textContent=`基准每 kW·月 $${num(base,0)}；左（绿）为该因子下调后的成本变化，右（红）为上调后的变化；单因素，其他不变。`;
  }

  function renderScenarios(r){
    const host=byId('scenario-table');host.replaceChildren();const table=make('table','bi'),thead=make('thead'),tr=make('tr');
    for(const h of ['情景','站点','设施 $M/MW','平准化年成本','每 MW·年','每 kW·月','每 GPU·h','资本开支占比','对标价差'])tr.append(make('th','',h));thead.append(tr);table.append(thead);const body=make('tbody');
    const list=Object.entries(spec.presets).map(([id,p])=>[p.label,compute(withPreset(id)),id===activePreset]);if(!activePreset)list.unshift(['当前假设',r,true]);
    for(const [label,res,cur] of list){const row=make('tr');if(cur)row.className='current';const bm=res.benchmark;for(const v of [label,spec.sites[res.inputs.site]?.label||'',num(res.capexPerMw.facility,1),money(res.levelised),money(res.perMwYear),'$'+num(res.perKwMonth,0),res.perGpuHour?'$'+num(res.perGpuHour,2):'—',pct(res.capexShare,0),bm.market?(bm.margin>=0?'+':'−')+pct(Math.abs(bm.margin),0)+'（'+bm.unit+'）':'—'])row.append(make('td','',v));body.append(row);}
    table.append(body);host.append(table);
  }

  function renderBenchmark(r){
    const bm=r.benchmark,host=byId('benchmark-compare');host.replaceChildren();
    if(!bm.market){host.append(make('p','muted','自用口径不做市场对标，只看成本。'));}else{
      const max=Math.max(bm.market,bm.cost)*1.1;for(const [l,v,c] of [['平准化单位成本',bm.cost,'var(--ui-accent)'],['市场价格',bm.market,'var(--ui-yellow)']]){const row=make('div','bar-row'),lab=make('label','',l),track=make('div','bar-track'),fill=make('div','bar-fill');fill.style.width=(v/max*100)+'%';fill.style.background=c;track.append(fill);row.append(lab,track,make('output','','$'+num(v,bm.unit==='$/GPU·h'?2:0)+' '+bm.unit));host.append(row);}
      const m=make('p','bench-verdict',bm.margin>=0?`市场价高于成本 ${pct(bm.margin,0)}：按当前假设该项目可覆盖全生命周期成本（含 ${pct(r.inputs.wacc,0)} 资本回报）。`:`市场价低于成本 ${pct(-bm.margin,0)}：按当前假设该项目无法在 ${pct(r.inputs.wacc,0)} 资本成本下收回全生命周期成本。`);m.classList.add(bm.margin>=0?'better':'worse');host.append(m);
      if(bm.model==='colo')host.append(make('p','muted','托管口径的成本不含 IT 资本开支与 IT 维护（租户自带设备）。'));}
    const list=byId('benchmark-list');list.replaceChildren();const latest={};for(const rec of prices.records||[]){if(!latest[rec.series_id]||rec.as_of>latest[rec.series_id].as_of)latest[rec.series_id]=rec;}
    const GL={regulatory:'监管披露',company:'公司披露',research:'研究实测',media:'媒体转述',estimate:'估算'};let group='';const shown=[];
    for(const b of spec.benchmark_series||[]){const rec=latest[b.series_id];if(!rec)continue;shown.push(rec);if(b.group!==group){group=b.group;list.append(make('h3','benchmark-group',group));}
      const row=make('div','benchmark-row'),head=make('div');head.append(make('b','',b.label),make('small','',[rec.as_of,GL[rec.grade]||rec.grade,rec.region||''].filter(Boolean).join(' · ')));row.append(head,make('strong','',(Math.abs(rec.value)>=1000?Math.round(rec.value).toLocaleString():Number(rec.value).toLocaleString(undefined,{maximumFractionDigits:2}))+' '+rec.unit));row.title=(rec.note||'')+(rec.assumptions?'；'+rec.assumptions:'');list.append(row);}
    byId('benchmark-updated').textContent=shown.length?'价格库更新至 '+shown.map(x=>x.as_of).sort().pop():'价格库暂无对应序列';
  }

  function renderGaps(){
    const host=byId('gap-list');host.replaceChildren();const counts={input:0,sourced:0,assumed:0,needed:0};const rows=[];
    for(const group of spec.groups)for(const id of group.inputs){const ev=spec.evidence[id]||{status:'needed'};counts[ev.status]=(counts[ev.status]||0)+1;if(ev.status==='assumed'||ev.status==='needed')rows.push([group.label.replace(/^\d+ · /,''),spec.inputs[id].label,ev]);}
    byId('gap-summary').textContent=`${Object.keys(spec.inputs).length} 个输入：用户给定 ${counts.input}、已有来源 ${counts.sourced}、作者假设 ${counts.assumed}、待获取 ${counts.needed}。下面是要去找数据替换的项。`;
    const table=make('table','bi gaps'),thead=make('thead'),tr=make('tr');for(const h of ['分组','输入','现状','抓取类型','要找什么'])tr.append(make('th','',h));thead.append(tr);table.append(thead);const body=make('tbody');
    const KIND={product:'产品',news:'新闻',data:'数据',report:'报告'};
    for(const [g,l,ev] of rows){const row=make('tr');const st=make('td');st.append(make('span','badge-text '+ev.status,STATUS[ev.status][0]));row.append(make('td','',g),make('td','',l),st,make('td','',KIND[ev.fetch_kind]||'—'),make('td','',ev.fetch_what||ev.note||''));body.append(row);}
    table.append(body);host.append(table);
  }

  function render(){
    const r=compute(values);markPreset();renderKpis(r);renderGroupTotals(r);renderStructure(r);renderTimeline(r);renderTable(r);renderCapex(r);renderSensitivity(r);renderScenarios(r);renderBenchmark(r);
    byId('copy-results').onclick=()=>{const text=JSON.stringify({model_id:spec.model_id,as_of:spec.as_of,preset:activePreset||null,baseline:baselineLabel,assumptions:values,levelised:r.levelised,per_mw_year:r.perMwYear,per_kw_month:r.perKwMonth,per_it_kwh:r.perItKwh,per_gpu_hour:r.perGpuHour,pv_total:r.pvTotal,lev_by_category:r.lev},null,2);const btn=byId('copy-results');const done=()=>{btn.textContent='已复制';setTimeout(()=>btn.textContent='复制假设与结果',1500);};(navigator.clipboard&&navigator.clipboard.writeText?navigator.clipboard.writeText(text).then(done):Promise.reject()).catch(()=>{const ta=document.createElement('textarea');ta.value=text;document.body.append(ta);ta.select();try{document.execCommand('copy');done();}catch(e){}ta.remove();});};
  }
  const getJson=url=>fetch(url,{cache:'no-store'}).then(res=>{if(!res.ok)throw Error(url+' HTTP '+res.status);return res.json()});
  const boot=([data,p,t])=>{spec=data;prices=p;tree=t;byId('model-date').textContent='口径 '+spec.as_of;byId('model-note').textContent=spec.model_note;renderPresets();renderGaps();values=withPreset('ai_virginia_own');activePreset='ai_virginia_own';renderInputs();setBaseline(spec.presets.ai_virginia_own.label);
    byId('reset-model').addEventListener('click',()=>applyPreset('ai_virginia_own'));byId('set-baseline').addEventListener('click',()=>setBaseline());app.removeAttribute('aria-busy');};
  const fail=error=>{const el=byId('tco-error');el.hidden=false;el.textContent='TCO 模型加载失败：'+error.message;app.setAttribute('aria-busy','false');};
  if(window.__TCO_SPEC)Promise.resolve([window.__TCO_SPEC,{records:window.__TCO_PRICES||[]},window.__TCO_TREE||null]).then(boot).catch(fail);
  else Promise.all([getJson('/data/datacenter_tco_model.json'),getJson('/data/prices.json').catch(()=>({records:[]})),getJson('/data/tco_factors.json').catch(()=>null)]).then(boot).catch(fail);
})();
