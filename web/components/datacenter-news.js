/* Shared homepage/operations projection from Spark; headline leads only. */
const host = document.querySelector('[data-datacenter-news]');
if (host) {
  const isHome=['/','/index.html'].includes(location.pathname);
  const headlines=host.dataset.newsPresentation==='headlines';
  const heading = document.createElement('h2'); heading.textContent = '数据中心新闻';
  const meta = document.createElement('p'); meta.className = 'dc-news-meta';
  if(headlines)meta.textContent='正在读取新闻…';
  const list = document.createElement('div'); list.className = 'dc-news-list'; list.tabIndex = 0;
  list.setAttribute('aria-label', '数据中心新闻列表，可滚动');
  const scroll=headlines?document.createElement('div'):null;
  if(scroll){scroll.className='dc-news-headlines-scroll';scroll.append(list);}
  if(!headlines){const timezone=document.createElement('span');timezone.className='dc-news-timezone';timezone.textContent='北京时间';heading.append(timezone);}
  host.replaceChildren(...(headlines?[meta,scroll]:[heading,meta,list]));
  const dateFormat=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'});
  const timeFormat=new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
  const timestamp=item=>typeof item.published_at==='number'&&Number.isFinite(item.published_at)&&!Number.isNaN(new Date(item.published_at).getTime())?item.published_at:0;
  const count=host.parentElement.querySelector('[data-news-count]');
  function showCount(value=null){if(count)count.textContent=isHome?`当前筛选 · ${host.dataset.newsSelection==='selected'?'精选报道':'报道'} ${value || '—'} 条`:`本次快照 · 当前筛选${host.dataset.newsSelection==='selected'?'精选':'线索'} ${value || '—'} 条`; }
  let currentRequest;
  let industryFilter=window.industryFilter || {};
  window.addEventListener('inresearch:industry-filter',e=>{const changed=['company','region','site','scope','role','relation'].some(k=>(industryFilter[k]||'')!==(e.detail[k]||''));industryFilter=e.detail;if(e.detail.force)refresh();else if((changed||e.detail.redraw)&&latestData)render(latestData);});
  // 研究员可给线索点「有用 / 没用」(2026-10-01):只是线索评价,不是 C3 采用;按目标行的计数经公开 /api/news 回流给 inews。
  let canMark=false, marks={};
  const canonical=u=>{try{const x=new URL(u);if(!['http:','https:'].includes(x.protocol))return null;return 'https://'+x.hostname.toLowerCase().replace(/^www\./,'')+(x.pathname.replace(/\/+$/,'')||'/')+x.search;}catch{return null;}};
  const whoami=headlines?Promise.resolve():fetch('/api/whoami',{cache:'no-store'}).then(r=>r.ok?r.json():null).then(async u=>{
    canMark=['member','admin'].includes(u?.role);
    if(canMark){const r=await fetch('/api/news/marks',{cache:'no-store'});if(r.ok)marks=(await r.json()).marks||{};}
  }).catch(()=>{});
  function markButtons(url){
    const box=document.createElement('span');box.className='dc-news-mark';
    const key=canonical(url);
    for(const [value,label] of [['useful','有用'],['not_useful','没用']]){
      const b=document.createElement('button');b.type='button';b.textContent=label;b.setAttribute('aria-pressed',String(marks[key]===value));
      b.onclick=async()=>{
        const next=marks[key]===value?'clear':value;
        b.disabled=true;
        try{
          const r=await fetch('/api/news/mark',{method:'POST',headers:{'Content-Type':'application/json','X-Requested-With':'news-mark'},body:JSON.stringify({url,mark:next})});
          const d=await r.json().catch(()=>({}));
          if(!r.ok)throw new Error(d.error||('HTTP '+r.status));
          if(d.mark)marks[d.url]=d.mark;else delete marks[d.url];
          for(const x of box.children)x.setAttribute('aria-pressed',String(marks[key]===(x.dataset.value)));
        }catch(e){b.title=e.message;}finally{b.disabled=false;}
      };
      b.dataset.value=value;box.append(b);
    }
    return box;
  }
  let latestData=null;
  function inewsLink(item,url){
    if(['inews.today','www.inews.today'].includes(url.hostname.toLowerCase()))return url.href;
    // feed.id is the research ledger's ID, not an inews article ID. Only
    // editorial picks have a public story page; other leads use its real search.
    const cluster=String(item.cluster_id??'');
    if(item.editorial_pick===true&&/^[1-9][0-9]*$/.test(cluster)&&Number.isSafeInteger(Number(cluster)))return 'https://inews.today/s/'+cluster;
    const search=new URL('https://inews.today/');search.searchParams.set('q',item.title||item.title_zh);return search.href;
  }
  function headlineRow(item,url){
    const article=document.createElement('article');
    if(item.raw)article.dataset.rawId=item.raw.id;
    const link=document.createElement('a');link.className='dc-news-headline';link.href=inewsLink(item,url);link.target='_blank';link.rel='noopener noreferrer';link.textContent=item.title_zh;
    const original=document.createElement('a');original.className='dc-news-original';original.href=url.href;original.target='_blank';original.rel='noopener noreferrer';original.textContent='↗';original.title='阅读原始报道';original.setAttribute('aria-label','阅读原始报道');
    article.append(link,original);return article;
  }
  function displayedItems(data){
    const byURL=new Map((data.feed?.items||[]).map(item=>[canonical(item.url),item]));
    const raw=(data.raw_atlas?.records||[]).filter(r=>r.origin!=='research_publication');
    if(isHome)for(const row of raw){
      const key=canonical(row.url);if(!key)continue;
      const previous=byURL.get(key);
      byURL.set(key,{...previous,title_zh:previous?.title_zh||row.title,url:row.url,published_at:previous?.published_at||row.published_at,
        object_ids:previous?.object_ids||(row.company_ids||[]).map(id=>'actor:'+id),raw:row});
    }
    return [...byURL.values()].sort((a,b)=>timestamp(b)-timestamp(a));
  }
  function render(data){
    const feed=data.feed,raw=(data.raw_atlas?.records||[]).filter(r=>r.origin!=='research_publication');
    if((!feed||['awaiting_sync','not_initialized'].includes(feed.status))&&!raw.length){
      meta.hidden=false;meta.textContent=isHome?'暂无可显示的近期报道，项目与研究资料仍可浏览。':data.reader?.status==='not_connected'?'尚未连接阅读服务':data.reader?.status==='degraded'?'新闻快照暂不可用，请稍后重试。':feed?.status==='not_initialized'?'新闻尚未初始化':'等待新闻同步';
      list.replaceChildren();showCount();return;
    }
    const age=Date.now()-Date.parse(feed?.exported_at||''),stale=!!data.reader?.stale||(!!feed&&(!Number.isFinite(age)||age>2*3600000));
    meta.hidden=feed?.status==='success'&&!stale||headlines&&!feed&&raw.length>0;
    meta.textContent=feed?.status==='running'?'正在更新':feed&&feed.status!=='success'?'更新暂时失败':stale?'更新延迟':!feed?(isHome?'日报报道 · 原始新闻时间以来源为准':'已接收日报事件 · 原始新闻时间以来源为准'):'';
    const progress=data.pipeline?.progress;
    if(!isHome&&progress&&Number.isInteger(progress.leads)){
      meta.hidden=false;const link=document.createElement('a');link.href='/projects.html?view=pipeline';link.textContent=`历史 ${progress.leads} 条线索 · ${progress.linked} 已关联 · 查看核验进展`;
      if(meta.textContent)meta.append(document.createTextNode(' · '));meta.append(link);
    }
    const rows=[];let lastDay='';
    for(const item of displayedItems(data)){
      if(host.dataset.newsSelection==='selected'&&item.editorial_pick!==true)continue;
      if(industryFilter.company&&!(item.object_ids||[]).includes('actor:'+industryFilter.company))continue;
      if(industryFilter.region||industryFilter.site||industryFilter.scope||industryFilter.role||industryFilter.relation){
        const raw=item.raw;
        const matched=raw&&((industryFilter.site&&raw.site_id===industryFilter.site)||(!industryFilter.site&&industryFilter.siteIds?.includes(raw.site_id))||(!industryFilter.site&&!industryFilter.scope&&!industryFilter.role&&!industryFilter.relation&&raw.region===industryFilter.region))
          ||(data.pipeline?.records||[]).some(p=>p.site_id&&(industryFilter.site?p.site_id===industryFilter.site:industryFilter.siteIds?.includes(p.site_id))&&(p.events||[]).some(e=>e.url===item.url));
        if(!matched)continue;
      }
      if(typeof item.title_zh!=='string'||!item.title_zh.trim())continue;
      let url;try{url=new URL(item.url);}catch{continue;}if(!['http:','https:'].includes(url.protocol)||url.username||url.password)continue;
      if(headlines){rows.push(headlineRow(item,url));continue;}
      const stamp=timestamp(item),date=stamp?new Date(stamp):null,day=date?dateFormat.format(date):item.raw?.report_date?'日报 '+item.raw.report_date+' · 原文时间待补充':'时间待补充';
      if(day!==lastDay){const label=document.createElement('h3');label.className='dc-news-day';label.textContent=day;rows.push(label);lastDay=day;}
      const article=document.createElement('article');
      const time=document.createElement('time');time.className='dc-news-time';time.textContent=date?timeFormat.format(date):'—';if(date){time.dateTime=date.toISOString();time.title=day+' '+time.textContent+' 北京时间';}
      const content=document.createElement('div');content.className='dc-news-content';
      const link=document.createElement('a');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';link.textContent=item.title_zh;
      const note=document.createElement('small');note.textContent=item.domain||url.hostname.replace(/^www\./,'');content.append(link,note);
      if(item.raw){
        const raw=item.raw;article.dataset.rawId=raw.id;
        const observations=(raw.capacity_observations||[]).slice(0,3);
        for(const observed of observations){
          const capacity=document.createElement('p');capacity.className='dc-news-capacity';
          const numeric=typeof observed.mw==='number'&&Number.isFinite(observed.mw)?(observed.mw>=1000?(observed.mw/1000).toLocaleString('en-US',{maximumFractionDigits:2})+' GW':observed.mw.toLocaleString('en-US',{maximumFractionDigits:2})+' MW'):'';
          const quoted=observed.quoted_value||numeric,basis=observed.basis==='it'?'IT 报道值':observed.basis==='facility_or_grid'?'设施 / 电网口径':'口径待核验';
          capacity.textContent=quoted+(numeric&&numeric!==quoted?'（'+numeric+'）':'')+' · '+basis;content.append(capacity);
        }
        if(!observations.length&&raw.capacity_text){const capacity=document.createElement('p');capacity.className='dc-news-capacity';capacity.textContent=raw.capacity_text+' · 原文多口径，未合计';content.append(capacity);}
        const state=document.createElement('small');state.className='dc-news-state';state.textContent=isHome?'新闻观察 · 原文报道口径':raw.verification_status==='project_adopted'?'关联项目已采用部分字段':'新闻观察 · 待核验';
        if(Array.isArray(raw.coordinates)&&raw.coordinates.length===2&&raw.coordinates.every(Number.isFinite)){
          const locate=document.createElement('button');locate.type='button';locate.className='dc-news-locate';locate.textContent=raw.location_precision==='country'?'国家示意 ↗':'地图定位 ↗';locate.onclick=()=>window.dispatchEvent(new CustomEvent('inresearch:locate-news',{detail:{id:raw.id}}));state.append(document.createTextNode(' · '),locate);
        }else state.append(document.createTextNode(' · 地点未定位'));
        content.append(state);
      }
      if(canMark)content.append(markButtons(url.href));article.append(time,content);rows.push(article);
    }
    if(!rows.length){const empty=document.createElement('p');empty.textContent=host.dataset.newsSelection==='selected'?'当前范围暂无编辑精选新闻，可切换全部线索。':'当前范围暂无已整理的中文新闻。';rows.push(empty);}
    list.replaceChildren(...rows);showCount(list.querySelectorAll('article').length);
  }
  async function refresh(){
    currentRequest?.abort();showCount();const request=new AbortController();currentRequest=request;const timeout=setTimeout(()=>request.abort(),20000);
    window.dispatchEvent(new CustomEvent('inresearch:news-state',{detail:{status:'loading'}}));
    try{
      const r=await fetch(isHome?'/api/news?overview=1':'/api/news',{cache:'no-store',signal:request.signal});if(!r.ok)throw new Error('HTTP '+r.status);
      const data=await r.json();if(request!==currentRequest)return;latestData=data;
      window.dispatchEvent(new CustomEvent('inresearch:news-data',{detail:data}));render(data);
    }catch{if(request!==currentRequest)return;window.dispatchEvent(new CustomEvent('inresearch:news-state',{detail:{status:'failed'}}));meta.hidden=false;meta.textContent=isHome?'近期报道暂不可用，请稍后重试。':'新闻暂时无法同步，请稍后重试。';}
    finally{clearTimeout(timeout);}
  }
  whoami.then(()=>{if(latestData&&canMark)render(latestData);});
  refresh();setInterval(()=>{if(!document.hidden)refresh();},60000);
}
