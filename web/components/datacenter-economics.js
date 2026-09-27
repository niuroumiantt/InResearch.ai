(() => {
  'use strict';
  const HOURS=8760;
  const crf=(r,n)=>r===0?1/n:r*Math.pow(1+r,n)/(Math.pow(1+r,n)-1);
  function irr(flows){
    const npv=r=>flows.reduce((s,f,t)=>s+f/Math.pow(1+r,t),0);
    let lo=-0.99,hi=10;if(npv(lo)*npv(hi)>0)return null;
    for(let i=0;i<200;i++){const mid=(lo+hi)/2;if(npv(lo)*npv(mid)<=0)hi=mid;else lo=mid;}
    return (lo+hi)/2;
  }
  function compute(a){
    const mw=a.it_mw,gpus=mw*a.gpus_per_mw,paidHours=gpus*HOURS*a.utilization;
    const energyKwh=mw*1000*a.power_load*a.pue*HOURS,energy=energyKwh*a.power_price,other=a.other_opex_per_mw*mw*1e6;
    const itCapex=a.it_capex_per_mw*mw*1e6,shellCapex=(a.shell_capex_per_mw+a.btm_capex_per_mw)*mw*1e6,land=a.land_per_mw*mw*1e6;
    const mode=a.facility_mode,own=mode==='own',rent=a.shell_rent_per_mw*mw*1e6;
    const facilityCost=mode==='lease'?rent:mode==='colo'?a.colo_rate*mw*1000*12:0;
    // Ledger 2: compute operator
    const revenue=paidHours*a.gpu_price,opex=energy+other+facilityCost,ebitda=revenue-opex;
    const depIt=itCapex/a.it_life,depShell=own?shellCapex/a.shell_life:0,ebit=ebitda-depIt-depShell,nopat=ebit*(1-a.tax);
    const invested=itCapex+(own?shellCapex+land:0);
    const capitalCharge=itCapex*crf(a.wacc,a.it_life)+(own?shellCapex*crf(a.wacc,a.shell_life)+land*a.wacc:0);
    const unitCost=(capitalCharge+opex)/paidHours,cash=nopat+depIt+depShell;
    const residual=own?shellCapex*Math.max(0,1-a.it_life/a.shell_life)+land:0;
    const flows=[-invested];for(let t=0;t<a.it_life;t++)flows.push(cash);flows[flows.length-1]+=residual;
    const computeLedger={gpus,paidHours,revenue,energy,other,facilityCost,opex,ebitda,depIt,depShell,ebit,nopat,invested,
      roic:invested?nopat/invested:null,ebitdaMargin:revenue?ebitda/revenue:null,ebitMargin:revenue?ebit/revenue:null,
      unitCost,breakeven:unitCost,surplusPerHour:a.gpu_price-unitCost,payback:cash>0?invested/cash:null,irr:irr(flows),capexTotal:itCapex+shellCapex+land};
    // Ledger 1: landlord
    const shellInvested=shellCapex+land,noi=rent*a.noi_margin,term=a.lease_term;
    const rents=[];for(let t=0;t<term;t++)rents.push(rent*Math.pow(1+a.escalator,t));
    const nois=rents.map(r=>r*a.noi_margin),debt=shellInvested*a.shell_ltc,ads=debt*crf(a.debt_rate,term),equity=shellInvested-debt;
    const residualValue=shellCapex*a.residual_share;
    const unlev=[-shellInvested,...nois];unlev[unlev.length-1]+=residualValue;
    const lev=[-equity,...nois.map(n=>n-ads)];lev[lev.length-1]+=residualValue;
    const shellLedger={invested:shellInvested,rentY1:rent,noiY1:noi,yieldOnCost:shellInvested?noi/shellInvested:null,contractValue:rents.reduce((x,y)=>x+y,0),
      debt,equity,debtService:ads,dscr:ads?noi/ads:null,cashOnCash:equity>0?(noi-ads)/equity:null,payback:noi>0?shellInvested/noi:null,
      irrUnlevered:irr(unlev),irrLevered:equity>0?irr(lev):null};
    // Ledger 3: model company
    const mHours=paidHours*a.monetized_share,tokens=mHours*3600*a.tokens_per_gpu_sec,mRevenue=tokens/1e6*a.price_per_m_tokens;
    let mCost,mInvested;
    if(a.compute_source==='own'){mCost=energy+other+(own?0:facilityCost)+depIt+(own?shellCapex/a.shell_life:0);mInvested=invested;}
    else{mCost=mHours*a.rent_price;mInvested=0;}
    const mEbit=mRevenue-mCost,mNopat=mEbit*(1-a.tax);
    const modelLedger={tokens,revenue:mRevenue,cost:mCost,ebit:mEbit,nopat:mNopat,nopatMargin:mRevenue?mNopat/mRevenue:null,
      revenuePerGpuHour:mHours?mRevenue/mHours:null,invested:mInvested,roic:mInvested?mNopat/mInvested:null};
    // Ledger 0: chip vendor
    const chipGp=itCapex*a.accelerator_share*a.chip_gross_margin;
    const chipLedger={acceleratorCapex:itCapex*a.accelerator_share,grossProfit:chipGp,grossProfitPerYear:chipGp/a.it_life};
    const split={chip:chipGp/a.it_life,landlord:mode==='lease'?noi:0,compute:a.compute_source==='own'?0:nopat,model:mNopat};
    return {inputs:a,compute:computeLedger,shell:shellLedger,model:modelLedger,chip:chipLedger,split,
      capexStack:{accelerators:itCapex*a.accelerator_share,otherIt:itCapex*(1-a.accelerator_share),shell:a.shell_capex_per_mw*mw*1e6,btm:a.btm_capex_per_mw*mw*1e6,land}};
  }
  window.InresearchEconomics={compute,crf,irr};

  const app=document.getElementById('econ-app');if(!app)return;
  const byId=id=>document.getElementById(id);
  const make=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined&&text!==null)e.textContent=text;return e;};
  const svgEl=(tag,attrs)=>{const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const k in attrs)e.setAttribute(k,attrs[k]);return e;};
  const money=n=>n==null||!isFinite(n)?'—':(n<0?'−':'')+(Math.abs(n)>=1e9?'$'+(Math.abs(n)/1e9).toFixed(2)+'B':Math.abs(n)>=1e6?'$'+(Math.abs(n)/1e6).toFixed(0)+'M':'$'+Math.round(Math.abs(n)).toLocaleString());
  const pct=(x,d=1)=>x==null||!isFinite(x)?'—':(x*100).toFixed(d)+'%';
  const num=(x,d=1)=>x==null||!isFinite(x)?'—':Number(x).toLocaleString(undefined,{maximumFractionDigits:d,minimumFractionDigits:d});
  const years=x=>x==null||!isFinite(x)?'—':x.toFixed(1)+' 年';
  const COLORS={accelerators:'var(--ui-accent)',otherIt:'var(--ui-purple)',shell:'var(--ui-green)',btm:'var(--ui-yellow)',land:'var(--ui-muted)',chip:'var(--ui-accent)',landlord:'var(--ui-green)',compute:'var(--ui-purple)',model:'var(--ui-yellow)'};
  const GRADE_LABEL={regulatory:'监管披露',company:'公司披露',research:'研究实测',media:'媒体转述',estimate:'估算'};
  let spec,values,prices,activePreset='';

  function applyGeneration(a,gen){const g=spec.generations[gen];if(!g)return;a.generation=gen;for(const k of ['gpus_per_mw','it_capex_per_mw','shell_capex_per_mw','btm_capex_per_mw'])a[k]=g[k];}
  function withPreset(id){const a={...spec.assumptions};const p=spec.presets[id];if(!p)return a;const ch={...p.changes};if(ch.generation)applyGeneration(a,ch.generation);Object.assign(a,ch);return a;}
  function applyPreset(id){values=withPreset(id);activePreset=id;byId('preset-note').textContent=spec.presets[id]?.note||'';renderInputs();render();}

  function renderPresets(){
    const host=byId('presets');host.replaceChildren();
    for(const [id,p] of Object.entries(spec.presets)){const b=make('button','',p.label);b.type='button';b.dataset.id=id;b.title=p.group;b.addEventListener('click',()=>applyPreset(id));host.append(b);}
  }
  function markPreset(){document.querySelectorAll('#presets button').forEach(b=>b.classList.toggle('active',b.dataset.id===activePreset));}
  function renderInputs(){
    const form=byId('econ-inputs');form.replaceChildren();
    for(const group of spec.groups){
      const box=make('details','input-group');if(group.id==='project'||group.id==='compute')box.open=true;
      const sum=make('summary','',group.label);box.append(sum);
      for(const id of group.inputs){
        const cfg=spec.inputs[id],row=make('div','input-row'),label=make('label','',cfg.label);label.htmlFor='input-'+id;
        if(cfg.note)label.append(make('small','',cfg.note));
        const holder=make('div','input-box');
        if(cfg.type==='select'){
          const sel=make('select');sel.id='input-'+id;
          const opts=cfg.options==='generations'?Object.entries(spec.generations).map(([k,g])=>[k,g.label]):cfg.choices;
          for(const [v,l] of opts){const o=make('option','',l);o.value=v;sel.append(o);}
          sel.value=values[id];
          sel.addEventListener('change',()=>{if(id==='generation')applyGeneration(values,sel.value);else values[id]=sel.value;activePreset='';byId('preset-note').textContent='';renderInputs();render();});
          holder.append(sel);
        }else{
          const input=make('input');input.type='number';input.id='input-'+id;input.min=cfg.min;input.max=cfg.max;input.step=cfg.step;
          input.value=cfg.display==='percent'?Math.round(values[id]*1000)/10:values[id];
          input.addEventListener('input',()=>{const raw=Number(input.value);if(!Number.isFinite(raw))return;values[id]=cfg.display==='percent'?raw/100:raw;activePreset='';byId('preset-note').textContent='';render();});
          holder.append(input,make('span','',cfg.unit));
        }
        row.append(label,holder);box.append(row);
      }
      form.append(box);
    }
  }

  function kpi(id,val,sub){byId(id).textContent=val;if(sub!==undefined)byId(id+'-sub').textContent=sub;}
  function renderKpis(r){
    const a=r.inputs,c=r.compute,s=r.shell,m=r.model;
    kpi('kpi-chip',money(r.chip.grossProfitPerYear),'厂商毛利年化 · 加速器 '+money(r.chip.acceleratorCapex)+' × '+pct(a.chip_gross_margin,0));
    kpi('kpi-shell',pct(s.yieldOnCost),'成本收益率 · 杠杆现金回报 '+pct(s.cashOnCash)+' · DSCR '+num(s.dscr,2));
    kpi('kpi-compute',pct(c.roic),'ROIC · 盈亏平衡 $'+c.unitCost.toFixed(2)+'/h 对租金 $'+a.gpu_price.toFixed(2)+' · 回收 '+years(c.payback));
    kpi('kpi-model',pct(m.nopatMargin),'NOPAT 利润率 · '+(a.compute_source==='own'?'ROIC '+pct(m.roic):'租用算力 $'+a.rent_price.toFixed(2)+'/h')+' · 每 GPU 小时收入 $'+num(m.revenuePerGpuHour,2));
    byId('project-line').textContent=`${a.it_mw} MW · ${spec.generations[a.generation]?.label||a.generation} · ${Math.round(c.gpus).toLocaleString()} 颗 GPU · 总资本开支 ${money(c.capexTotal)}（每 GW ${money(c.capexTotal/a.it_mw*1000)}）· ${({own:'自建自持',lease:'租带电壳',colo:'托管'})[a.facility_mode]}`;
  }

  function renderCapexStack(r){
    const host=byId('capex-stack');host.replaceChildren();
    const mw=r.inputs.it_mw;const rows=[];
    for(const [id,g] of Object.entries(spec.generations)){
      const acc=g.it_capex_per_mw*r.inputs.accelerator_share,segs=[['accelerators',acc],['otherIt',g.it_capex_per_mw-acc],['shell',g.shell_capex_per_mw],['btm',g.btm_capex_per_mw]];
      rows.push({id,label:g.label,segs,total:segs.reduce((s,x)=>s+x[1],0),current:id===r.inputs.generation});
    }
    if(!spec.generations[r.inputs.generation]||rows.find(x=>x.current).total!==r.inputs.it_capex_per_mw+r.inputs.shell_capex_per_mw+r.inputs.btm_capex_per_mw){
      const a=r.inputs,acc=a.it_capex_per_mw*a.accelerator_share;const segs=[['accelerators',acc],['otherIt',a.it_capex_per_mw-acc],['shell',a.shell_capex_per_mw],['btm',a.btm_capex_per_mw]];
      rows.forEach(x=>x.current=false);rows.unshift({id:'current',label:'当前假设',segs,total:segs.reduce((s,x)=>s+x[1],0),current:true});
    }
    const W=640,rowH=26,left=150,max=Math.max(...rows.map(x=>x.total))*1.08;
    const svg=svgEl('svg',{viewBox:`0 0 ${W} ${rows.length*rowH+8}`,class:'chart'});
    rows.forEach((row,i)=>{
      const y=i*rowH+4;let x=left;
      svg.append(Object.assign(svgEl('text',{x:left-8,y:y+14,'text-anchor':'end',class:'chart-label'+(row.current?' current':'')}),{textContent:row.label}));
      for(const [key,val] of row.segs){if(val<=0)continue;const w=val/max*(W-left-60);const rect=svgEl('rect',{x,y,width:w,height:18,fill:COLORS[key],opacity:row.current?1:0.45});rect.append(Object.assign(svgEl('title'),{textContent:`${row.label} · ${({accelerators:'加速器',otherIt:'其他 IT',shell:'非 IT（带电壳）',btm:'表后电力'})[key]} ${val.toFixed(1)} $M/MW`}));svg.append(rect);x+=w;}
      svg.append(Object.assign(svgEl('text',{x:x+6,y:y+14,class:'chart-value'}),{textContent:'$'+row.total.toFixed(1)+'B/GW'}));
    });
    host.append(svg);
    const legend=byId('capex-legend');legend.replaceChildren();
    for(const [k,l] of [['accelerators','加速器'],['otherIt','其他 IT（网络、存储、服务器）'],['shell','非 IT：建筑、供配电、冷却'],['btm','表后电力']]){const it=make('span','legend-item');const sw=make('i');sw.style.background=COLORS[k];it.append(sw,document.createTextNode(l));legend.append(it);}
  }

  function renderWaterfall(r){
    const host=byId('waterfall');host.replaceChildren();const c=r.compute;
    const steps=[['收入',c.revenue,'total'],['电费',-c.energy,'neg'],['其他运营',-c.other,'neg']];
    if(c.facilityCost)steps.push([r.inputs.facility_mode==='lease'?'壳层租金':'托管费',-c.facilityCost,'neg']);
    steps.push(['EBITDA',c.ebitda,'sub'],['IT 折旧',-c.depIt,'neg']);if(c.depShell)steps.push(['设施折旧',-c.depShell,'neg']);
    steps.push(['EBIT',c.ebit,'sub'],['所得税',-(c.ebit-c.nopat),'neg'],['NOPAT',c.nopat,'total']);
    const W=640,H=230,left=8,bottom=40,colW=(W-left-8)/steps.length,max=Math.max(c.revenue,1),scale=(H-bottom-24)/max;
    const svg=svgEl('svg',{viewBox:`0 0 ${W} ${H}`,class:'chart'});let running=0;
    steps.forEach(([label,val,kind],i)=>{
      let y0,y1;if(kind==='total'||kind==='sub'){y0=0;y1=val;running=val;}else{y0=running;y1=running+val;running=y1;}
      const top=H-bottom-Math.max(y0,y1)*scale,h=Math.max(1,Math.abs(y1-y0)*scale),x=left+i*colW+4;
      const rect=svgEl('rect',{x,y:top,width:colW-8,height:h,fill:kind==='neg'?'var(--ui-red)':kind==='sub'?'var(--ui-muted)':'var(--ui-accent)',opacity:kind==='sub'?0.55:0.9});
      rect.append(Object.assign(svgEl('title'),{textContent:label+' '+money(val)}));svg.append(rect);
      svg.append(Object.assign(svgEl('text',{x:x+(colW-8)/2,y:top-4,'text-anchor':'middle',class:'chart-value'}),{textContent:money(val)}));
      svg.append(Object.assign(svgEl('text',{x:x+(colW-8)/2,y:H-bottom+14,'text-anchor':'middle',class:'chart-label'}),{textContent:label}));
    });
    host.append(svg);
    byId('waterfall-note').textContent=`EBITDA 利润率 ${pct(c.ebitdaMargin)} · EBIT 利润率 ${pct(c.ebitMargin)} · 投入资本 ${money(c.invested)} · ROIC ${pct(c.roic)} · ${r.inputs.it_life} 年 IRR ${pct(c.irr)}（期末非 IT 资产按账面残值）`;
  }

  function renderSplit(r){
    const host=byId('profit-split');host.replaceChildren();
    const items=[['chip','芯片厂商毛利（年化）'],['landlord','壳层出租方 NOI'],['compute','算力运营方 NOPAT'],['model','模型方 NOPAT']].map(([k,l])=>[k,l,r.split[k]]);
    const total=items.reduce((s,x)=>s+Math.max(0,x[2]),0),max=Math.max(...items.map(x=>Math.abs(x[2])),1);
    for(const [k,l,v] of items){
      const row=make('div','split-row'),lab=make('label','',l),track=make('div','bar-track'),fill=make('div','bar-fill'),out=make('output','',money(v)+(v>0&&total?' · '+pct(v/total,0):''));
      fill.style.width=Math.max(0.5,Math.abs(v)/max*100)+'%';fill.style.background=COLORS[k];if(v<0)fill.classList.add('negative');track.append(fill);row.append(lab,track,out);host.append(row);
    }
    const a=r.inputs;
    byId('split-note').textContent=(a.compute_source==='own'?'模型方使用自有算力，算力层利润并入模型方；':'算力方向模型方出租算力，两层分别计利润；')+(a.facility_mode==='lease'?'壳层按租约收取 NOI。':a.facility_mode==='colo'?'托管费计入算力方成本，托管商利润未单列。':'设施自建自持，无壳层出租方。')+' 芯片厂商毛利按加速器采购额 × 毛利率在 IT 折旧年限内年化。';
  }

  function renderLedgerTables(r){
    const s=r.shell,m=r.model,a=r.inputs;
    const shellRows=[['壳层投资（非 IT + 土地）',money(s.invested)],['首年租金 / NOI',money(s.rentY1)+' / '+money(s.noiY1)],['成本收益率（NOI ÷ 投资）',pct(s.yieldOnCost)],['租期合同总额（含递增）',money(s.contractValue)],['债务 / 权益',money(s.debt)+' / '+money(s.equity)],['年还本付息 · DSCR',money(s.debtService)+' · '+num(s.dscr,2)],['杠杆现金回报（首年）',pct(s.cashOnCash)],['无杠杆 IRR / 杠杆 IRR（租期）',pct(s.irrUnlevered)+' / '+pct(s.irrLevered)],['简单回收期',years(s.payback)]];
    const modelRows=[['GPU 小时（收费部分）',num(r.compute.paidHours*a.monetized_share/1e6,1)+'M h'],['token 产出',num(m.tokens/1e12,1)+' 万亿'],['收入',money(m.revenue)+'（每 GPU 小时 $'+num(m.revenuePerGpuHour,2)+'）'],[a.compute_source==='own'?'自有算力成本（运营 + 折旧）':'算力租金',money(m.cost)],['EBIT',money(m.ebit)],['NOPAT · 利润率',money(m.nopat)+' · '+pct(m.nopatMargin)],[a.compute_source==='own'?'ROIC（NOPAT ÷ 投入资本）':'投入资本','—'===pct(m.roic)?'不持有资产':pct(m.roic)]];
    for(const [id,rows] of [['shell-table',shellRows],['model-table',modelRows]]){const host=byId(id);host.replaceChildren();for(const [k,v] of rows){const li=make('li');li.append(make('span','',k),make('strong','',v));host.append(li);}}
  }

  function renderSensitivity(r){
    const host=byId('tornado');host.replaceChildren();const base=r.compute.roic;const rows=[];
    for(const d of spec.sensitivity.drivers){
      const lo={...r.inputs},hi={...r.inputs};
      if(d.delta_abs){lo[d.key]=Math.max(1,r.inputs[d.key]-d.delta_abs);hi[d.key]=r.inputs[d.key]+d.delta_abs;}else{lo[d.key]=r.inputs[d.key]*(1-d.delta);hi[d.key]=r.inputs[d.key]*(1+d.delta);}
      const a=compute(lo).compute.roic,b=compute(hi).compute.roic;
      rows.push({label:d.label+(d.delta_abs?` ±${d.delta_abs} 年`:` ±${Math.round(d.delta*100)}%`),lo:a-base,hi:b-base});
    }
    rows.sort((x,y)=>Math.max(Math.abs(y.lo),Math.abs(y.hi))-Math.max(Math.abs(x.lo),Math.abs(x.hi)));
    const W=640,rowH=26,left=190,mid=left+(W-left-40)/2,span=Math.max(...rows.map(x=>Math.max(Math.abs(x.lo),Math.abs(x.hi))),0.01),scale=(W-left-40)/2/span;
    const svg=svgEl('svg',{viewBox:`0 0 ${W} ${rows.length*rowH+8}`,class:'chart'});
    svg.append(svgEl('line',{x1:mid,y1:0,x2:mid,y2:rows.length*rowH+8,stroke:'var(--ui-line)'}));
    rows.forEach((row,i)=>{const y=i*rowH+4;
      svg.append(Object.assign(svgEl('text',{x:left-8,y:y+14,'text-anchor':'end',class:'chart-label'}),{textContent:row.label}));
      for(const [v,cls] of [[row.lo,'lo'],[row.hi,'hi']]){const w=Math.abs(v)*scale,x=v<0?mid-w:mid;const rect=svgEl('rect',{x,y,width:Math.max(1,w),height:18,fill:cls==='lo'?'var(--ui-red)':'var(--ui-green)',opacity:0.85});rect.append(Object.assign(svgEl('title'),{textContent:row.label+' → ROIC '+pct(base+v)}));svg.append(rect);
        svg.append(Object.assign(svgEl('text',{x:v<0?x-4:x+w+4,y:y+14,'text-anchor':v<0?'end':'start',class:'chart-value'}),{textContent:(v>=0?'+':'−')+pct(Math.abs(v))}));}
    });
    host.append(svg);
    byId('tornado-note').textContent=`基准 ROIC ${pct(base)}；红色为下调（或缩短年限）后的变化，绿色为上调后的变化。`;
    // heatmap
    const hm=spec.sensitivity.heatmap,table=make('table','matrix'),thead=make('thead'),head=make('tr');head.append(make('th','','利用率 \\ 租金'));
    for(const f of hm.price_factors)head.append(make('th','','$'+(r.inputs.gpu_price*f).toFixed(2)));thead.append(head);table.append(thead);
    const body=make('tbody'),vals=[];
    for(const u of hm.utilization)for(const f of hm.price_factors)vals.push(compute({...r.inputs,utilization:u,gpu_price:r.inputs.gpu_price*f}).compute.roic);
    const lo=Math.min(...vals),hi=Math.max(...vals);
    hm.utilization.forEach((u,i)=>{const tr=make('tr');tr.append(make('th','',Math.round(u*100)+'%'));hm.price_factors.forEach((f,j)=>{const v=vals[i*hm.price_factors.length+j],t=(v-lo)/Math.max(0.001,hi-lo),td=make('td','',pct(v,0));td.style.background=`color-mix(in srgb, ${v<0?'var(--ui-red)':'var(--ui-green)'} ${10+Math.round(t*40)}%, var(--ui-surface))`;tr.append(td);});body.append(tr);});
    table.append(body);byId('heatmap').replaceChildren(table);
  }

  function renderScenarios(r){
    const host=byId('scenario-table');host.replaceChildren();
    const table=make('table','scenarios'),thead=make('thead'),head=make('tr');
    for(const h of ['情景','设施','租金 $/h','每 GW 资本开支','算力 ROIC','盈亏平衡 $/h','回收期','壳层收益率','杠杆现金回报','模型 NOPAT 率'])head.append(make('th','',h));thead.append(head);table.append(thead);
    const body=make('tbody');
    const list=Object.entries(spec.presets).map(([id,p])=>[p.label,compute(withPreset(id)),id===activePreset]);
    if(!activePreset)list.unshift(['当前假设',r,true]);
    for(const [label,res,cur] of list){const tr=make('tr');if(cur)tr.className='current';const c=res.compute,s=res.shell,m=res.model,a=res.inputs;
      for(const v of [label,({own:'自建',lease:'租壳',colo:'托管'})[a.facility_mode],'$'+a.gpu_price.toFixed(2),money(c.capexTotal/a.it_mw*1000),pct(c.roic),'$'+c.unitCost.toFixed(2),years(c.payback),pct(s.yieldOnCost),pct(s.cashOnCash),pct(m.nopatMargin)])tr.append(make('td','',v));
      body.append(tr);}
    table.append(body);host.append(table);
  }

  function latestBySeries(records){const out={};for(const rec of records||[]){if(!out[rec.series_id]||rec.as_of>out[rec.series_id].as_of)out[rec.series_id]=rec;}return out;}
  function renderBenchmarks(){
    const host=byId('benchmark-list');host.replaceChildren();const latest=latestBySeries(prices.records);let group='';const shown=[];
    for(const b of spec.benchmark_series||[]){const rec=latest[b.series_id];if(!rec)continue;shown.push(rec);
      if(b.group&&b.group!==group){group=b.group;host.append(make('h3','benchmark-group',group));}
      const row=make('div','benchmark-row'),head=make('div'),name=make('b','',b.label),meta=make('small','',[rec.as_of,GRADE_LABEL[rec.grade]||rec.grade,rec.region||''].filter(Boolean).join(' · ')),val=make('strong','',(Math.abs(rec.value)>=1000?Math.round(rec.value).toLocaleString():Number(rec.value).toLocaleString(undefined,{maximumFractionDigits:2}))+' '+rec.unit);
      head.append(name,meta);row.append(head,val);row.title=(rec.note||'')+(rec.assumptions?'；'+rec.assumptions:'');host.append(row);}
    byId('benchmark-updated').textContent=shown.length?'价格库更新至 '+shown.map(x=>x.as_of).sort().pop():'价格库暂无对应序列';
  }

  function render(){
    const r=compute(values);markPreset();renderKpis(r);renderCapexStack(r);renderWaterfall(r);renderSplit(r);renderLedgerTables(r);renderSensitivity(r);renderScenarios(r);
    byId('export-json').onclick=()=>{const blob=new Blob([JSON.stringify({model_id:spec.model_id,as_of:spec.as_of,preset:activePreset||null,assumptions:values,results:r},null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='datacenter-economics-'+(activePreset||'custom')+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);};
  }
  const getJson=url=>fetch(url,{cache:'no-store'}).then(res=>{if(!res.ok)throw Error(url+' HTTP '+res.status);return res.json()});
  Promise.all([getJson('/data/datacenter_economics_model.json'),getJson('/data/prices.json').catch(()=>({records:[]}))]).then(([data,p])=>{
    spec=data;prices=p;byId('model-date').textContent='口径 '+spec.as_of;byId('model-note').textContent=spec.model_note;
    renderPresets();renderBenchmarks();applyPreset('ms_hyperscaler_gb300');
    byId('reset-model').addEventListener('click',()=>applyPreset('ms_hyperscaler_gb300'));app.removeAttribute('aria-busy');
  }).catch(error=>{const el=byId('econ-error');el.hidden=false;el.textContent='经济模型加载失败：'+error.message;app.setAttribute('aria-busy','false')});
})();
