/* Shared homepage/operations projection from Spark; headline leads only. */
const host = document.querySelector('[data-datacenter-news]');
if (host) {
  const heading = document.createElement('h2'); heading.textContent = '数据中心新闻';
  const meta = document.createElement('p'); meta.className = 'dc-news-meta';
  const list = document.createElement('div'); list.className = 'dc-news-list'; list.tabIndex = 0;
  list.setAttribute('aria-label', '数据中心新闻列表，可滚动');
  const timezone=document.createElement('span');timezone.className='dc-news-timezone';timezone.textContent='北京时间';heading.append(timezone);
  host.replaceChildren(heading, meta, list);
  const dateFormat=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'});
  const timeFormat=new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
  const timestamp=item=>typeof item.published_at==='number'&&Number.isFinite(item.published_at)&&!Number.isNaN(new Date(item.published_at).getTime())?item.published_at:0;
  let currentRequest;
  async function refresh() {
    currentRequest?.abort();
    const request = new AbortController(); currentRequest = request;
    const timeout = setTimeout(()=>request.abort(), 20000);
    try {
      const r = await fetch('/api/news', {cache:'no-store', signal:request.signal});
      if (!r.ok) throw new Error('HTTP '+r.status);
      const data = await r.json();
      if (request !== currentRequest) return;
      const feed = data.feed;
      if (!feed || ['awaiting_sync','not_initialized'].includes(feed.status)) {
        meta.hidden=false;
        meta.textContent = data.reader?.status === 'not_connected' ? '尚未连接阅读服务'
          : data.reader?.status === 'degraded' ? '新闻快照暂不可用，请稍后重试。'
          : feed?.status === 'not_initialized' ? '新闻尚未初始化' : '等待新闻同步';
        list.replaceChildren();return;
      }
      const age = Date.now()-Date.parse(feed.exported_at || '');
      const stale = !Number.isFinite(age) || age > 2*3600000 || data.reader?.stale;
      meta.hidden=feed.status === 'success' && !stale;
      meta.textContent=feed.status === 'running' ? '正在更新' : feed.status !== 'success' ? '更新暂时失败' : stale ? '更新延迟' : '';
      const rows = [];let lastDay='';
      for (const item of feed.items || []) {
        if (typeof item.title_zh !== 'string' || !item.title_zh.trim()) continue;
        let url; try {url=new URL(item.url);} catch {continue;}
        if (!['http:','https:'].includes(url.protocol) || url.username || url.password) continue;
        const stamp=timestamp(item),date=stamp?new Date(stamp):null,day=date?dateFormat.format(date):'时间待补充';
        if(day!==lastDay){const label=document.createElement('h3');label.className='dc-news-day';label.textContent=day;rows.push(label);lastDay=day;}
        const article = document.createElement('article');
        const time=document.createElement('time');time.className='dc-news-time';time.textContent=date?timeFormat.format(date):'—';if(date){time.dateTime=date.toISOString();time.title=day+' '+time.textContent+' 北京时间';}
        const content=document.createElement('div');content.className='dc-news-content';
        const link = document.createElement('a');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';link.textContent=item.title_zh;
        const note = document.createElement('small');note.textContent=item.domain || url.hostname.replace(/^www\./,'');
        content.append(link,note);article.append(time,content);
        rows.push(article);
      }
      if (!rows.length) {const empty=document.createElement('p');empty.textContent='暂无已整理的中文新闻。';rows.push(empty);}
      list.replaceChildren(...rows);
    } catch {
      if (request !== currentRequest) return;
      meta.hidden=false;meta.textContent='新闻暂时无法同步，请稍后重试。';
    } finally {clearTimeout(timeout);}
  }
  refresh(); setInterval(()=>{if(!document.hidden) refresh();},60000);
}
