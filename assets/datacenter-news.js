/* Shared homepage/operations projection from Spark; headline leads only. */
const host = document.querySelector('[data-datacenter-news]');
if (host) {
  const heading = document.createElement('h2'); heading.textContent = '数据中心新闻';
  const meta = document.createElement('p'); meta.className = 'dc-news-meta';
  const list = document.createElement('div'); list.className = 'dc-news-list'; list.tabIndex = 0;
  list.setAttribute('aria-label', '数据中心新闻列表，可滚动');
  host.replaceChildren(heading, meta, list);
  async function refresh() {
    try {
      const r = await fetch('/api/research', {cache:'no-store'});
      if (!r.ok) throw new Error('HTTP '+r.status);
      const data = await r.json(); const feed = data.reader?.acquisition?.news_feed;
      if (!feed || ['awaiting_sync','not_initialized'].includes(feed.status)) {meta.hidden=false;meta.textContent = '新闻正在同步'; list.replaceChildren();return;}
      const age = Date.now()-Date.parse(feed.exported_at || '');
      const stale = !Number.isFinite(age) || age > 2*3600000 || data.reader?.stale;
      meta.hidden=feed.status === 'success' && !stale;
      meta.textContent=feed.status === 'running' ? '正在更新' : feed.status !== 'success' ? '更新暂时失败' : stale ? '更新延迟' : '';
      const rows = [];
      for (const item of (feed.items || []).slice(0,80)) {
        if (typeof item.title_zh !== 'string' || !item.title_zh.trim()) continue;
        let url; try {url=new URL(item.url);} catch {continue;}
        if (!['http:','https:'].includes(url.protocol) || url.username || url.password) continue;
        const article = document.createElement('article');
        const link = document.createElement('a');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';link.textContent=item.title_zh;
        const note = document.createElement('small');note.textContent=item.domain || url.hostname.replace(/^www\./,'');
        article.append(link,note);
        rows.push(article);
      }
      if (!rows.length) {const empty=document.createElement('p');empty.textContent='暂无已整理的中文新闻。';rows.push(empty);}
      list.replaceChildren(...rows);
    } catch {meta.hidden=false;meta.textContent='新闻暂时无法同步，请稍后重试。';}
  }
  refresh(); setInterval(()=>{if(!document.hidden) refresh();},60000);
}
