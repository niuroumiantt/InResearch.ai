/* Shared homepage/operations projection from Spark; headline leads only. */
const host = document.querySelector('[data-datacenter-news]');
if (host) {
  const heading = document.createElement('h2'); heading.textContent = '数据中心新闻';
  const meta = document.createElement('p'); meta.className = 'dc-news-meta';
  const list = document.createElement('div'); list.className = 'dc-news-list'; list.tabIndex = 0;
  list.setAttribute('aria-label', '数据中心新闻列表，可滚动');
  host.replaceChildren(heading, meta, list);
  const date = value => {const d = new Date(value); return Number.isNaN(+d) ? '时间未知' : d.toLocaleString('zh-CN');};
  async function refresh() {
    try {
      const r = await fetch('/api/research', {cache:'no-store'});
      if (!r.ok) throw new Error('HTTP '+r.status);
      const data = await r.json(); const feed = data.reader?.acquisition?.news_feed;
      if (!feed || ['awaiting_sync','not_initialized'].includes(feed.status)) {meta.textContent = '等待 Spark 新闻同步 · 新闻标题线索不等于已核验结论'; list.replaceChildren();return;}
      const age = Date.now()-Date.parse(feed.exported_at || '');
      const stale = !Number.isFinite(age) || age > 2*3600000 || data.reader?.stale;
      meta.textContent = `来源 inews.today · ${feed.status === 'running' ? '同步中，展示上次结果' : feed.status !== 'success' ? '同步异常，保留上次结果' : stale ? '同步延迟' : '已同步'} · ${date(feed.exported_at)}${feed.truncated ? ' · 有界窗口，非全部新闻' : ''} · 标题线索，待核验`;
      const rows = [];
      for (const item of (feed.items || []).slice(0,80)) {
        let url; try {url=new URL(item.url);} catch {continue;}
        if (!['http:','https:'].includes(url.protocol) || url.username || url.password) continue;
        const article = document.createElement('article');
        const link = document.createElement('a');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';link.textContent=item.title_zh || item.title;
        const note = document.createElement('small');note.textContent=`${item.publisher || '来源未标注'} · ${date(item.published_at)} · ${item.category || '数据中心'}`;
        article.append(link,note);
        if (item.title_zh && item.title_zh !== item.title) {const original=document.createElement('details');const summary=document.createElement('summary');summary.textContent='原文标题';const text=document.createElement('p');text.textContent=item.title;original.append(summary,text);article.append(original);}
        rows.push(article);
      }
      if (!rows.length) {const empty=document.createElement('p');empty.textContent='当前窗口暂无符合数据中心范围的新闻。';rows.push(empty);}
      list.replaceChildren(...rows);
    } catch {meta.textContent='新闻暂时无法同步，请稍后重试。';}
  }
  refresh(); setInterval(()=>{if(!document.hidden) refresh();},60000);
}
