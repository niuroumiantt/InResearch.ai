/* Company window loads bounded indexes; product specifications live in the products view. */
(()=>{'use strict';
const $=id=>document.getElementById(id), params=new URLSearchParams(location.search), cid=params.get('c')||'nvidia';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safe=v=>{try{const u=new URL(v);return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password?u.href:'';}catch{return '';}};
const external=(url,label)=>safe(url)?`<a href="${esc(safe(url))}" target="_blank" rel="noopener">${esc(label)} ↗</a>`:esc(label);
const product=(extra={})=>'/product-catalog.html?'+new URLSearchParams({c:cid,view:'products',...extra});
async function json(url){const r=await fetch(url,{signal:AbortSignal.timeout(12000)});if(!r.ok)throw new Error(String(r.status));return r.json();}
function setLink(id,url){$(id).href=url;}
const icons=[
'<rect x="3" y="5" width="22" height="18" rx="2"/><path d="M8 10h12M8 15h12M8 19h3"/>',
'<rect x="5" y="2" width="18" height="24" rx="2"/><path d="M5 10h18M5 18h18M9 6h2M9 14h2M9 22h2"/>',
'<ellipse cx="14" cy="6" rx="10" ry="4"/><path d="M4 6v15c0 5 20 5 20 0V6M4 13c0 5 20 5 20 0"/>',
'<rect x="6" y="6" width="16" height="16" rx="2"/><path d="M10 1v5M18 1v5M10 22v5M18 22v5M1 10h5M1 18h5M22 10h5M22 18h5"/>',
'<rect x="9" y="2" width="10" height="7" rx="1"/><rect x="1" y="20" width="10" height="7" rx="1"/><rect x="17" y="20" width="10" height="7" rx="1"/><path d="M14 9v6H6v5M14 15h8v5"/>',
'<path d="M9 7L2 14l7 7M19 7l7 7-7 7M16 4l-4 20"/>'
];
function reports(rows,type){$('financial-reports').innerHTML=rows.filter(r=>r.kind===type).slice(0,5).map(r=>`<a class="report-row" href="${esc(safe(r.url))}" target="_blank" rel="noopener"><span><strong>${esc(r.period)}</strong><small>截至 ${esc(r.period_end)} · ${esc(r.form)}</small></span><span>官方原文 ↗</span></a>`).join('')||'<p class="window-empty">尚未登记此类报告。可从投资者关系网站查看。</p>';}
function render(data){const c=data.company;document.title=(c.name_cn||c.name)+' · 企业窗口';$('catalog-title').textContent=c.name;$('company-listing').textContent=[c.legal_name||c.name,c.ticker||'上市代码未登记'].join(' / ');$('company-profile').textContent=c.profile||'公司简介尚待补充。可访问官方网站了解其业务。';
$('actor-switch').innerHTML=data.companies.map(v=>`<option value="${esc(v.id)}" ${v.id===cid?'selected':''}>${esc(v.name)}</option>`).join('');
$('actor-switch').onchange=e=>{location.href='/product-catalog.html?'+new URLSearchParams({c:e.target.value});};
$('company-links').innerHTML=[external(c.website&&(/^https?:/.test(c.website)?c.website:'https://'+c.website),'官方网站'),c.ir_url?external(c.ir_url,'投资者关系'):null].filter(Boolean).join('');
const facts=[['成立',c.founded_year?c.founded_year+' 年':'未登记'],['总部',c.hq_address||c.hq_country||'未登记'],['员工',c.employees||'未登记'],['首席执行官',c.ceo||'未登记']];
$('company-facts').innerHTML=facts.map(([k,v])=>`<div><dt>${k}</dt><dd>${esc(v)}${k==='员工'&&c.employees_as_of?`<small>截至 ${esc(c.employees_as_of)}</small>`:''}</dd></div>`).join('');
$('profile-source').innerHTML=c.profile_source?`公司资料：${external(c.profile_source,'官方披露')} · 披露期 ${esc(c.profile_as_of||'未登记')}`:'公司基本资料以已登记信息为准；空缺项待核对官方披露。';
for(const id of ['catalog-link','all-products'])setLink(id,product());setLink('research-link',product()+'#research-details');
$('product-lines').innerHTML=data.product_lines.map((v,i)=>`<a class="product-line-card" href="${esc(product({q:v.query||v.name}))}"><svg fill="none" stroke="currentColor" stroke-width="1.4" viewBox="0 0 28 28" aria-hidden="true">${icons[i%icons.length]}</svg><strong>${esc(v.name)}</strong><small>${esc(v.description)}</small><b>↗</b></a>`).join('')||'<p class="window-empty">产品线尚未登记；可进入产品目录查看交付状态。</p>';
const reviewed=data.product_lines.some(v=>v.basis==='reviewed_business_categories');$('product-basis').innerHTML=reviewed?'按公司披露整理业务分类；分类下的检索结果仅包含已收录产品。':'按已登记产品线呈现；目录尚未交付时不表示公司没有产品。';
const groups=data.catalog.groups||[];$('catalog-categories').innerHTML=groups.length?'<span>已收录的原厂分类</span>'+groups.map(g=>`<a href="${esc(product({group:g.id}))}">${esc(g.label)} <small>${esc(g.entities)} 个目录实体</small></a>`).join(''):(data.catalog.status==='error'?'<span>原厂目录分类读取失败；公司资料仍可查看。</span>':'<span>原厂目录分类尚未交付</span>');
const rows=(data.financials||[]).filter(r=>safe(r.url));reports(rows,'annual');document.querySelectorAll('[data-reports]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-reports]').forEach(v=>v.setAttribute('aria-pressed',String(v===b)));reports(rows,b.dataset.reports);});
if(safe(c.ir_url)){setLink('investor-relations',safe(c.ir_url));$('investor-relations').hidden=false;}
$('financial-basis').textContent=rows.length?'已核对的官方报告索引 · '+data.checked_at+'。只加载链接，点击后打开原文。':'报告索引尚待接通。首页不加载报告正文。';
}
function money(v,cap=false){return typeof v==='number'&&Number.isFinite(v)?(cap?(v>=1e12?(v/1e12).toFixed(2)+' 万亿':(v/1e8).toFixed(2)+' 亿'):'$'+v.toFixed(2)):'—';}
async function quote(attempt=0){try{const q=await json('/api/company-quote?'+new URLSearchParams({c:cid}));$('quote-price').textContent=money(q.price);$('quote-cap').textContent=money(q.market_cap,true);$('quote-currency').textContent=q.market_cap?'美元':'';
$('quote-change').textContent=typeof q.change_percent==='number'?(q.change_percent>=0?'+':'')+q.change_percent.toFixed(2)+'%':'';
$('quote-change').className=q.change_percent>=0?'positive':'negative';
const available=typeof q.price==='number';$('quote-time').innerHTML=available?`${external(q.source_url,q.provider||'行情来源')} · ${esc(q.as_of)}<br>${q.status==='stale'?'缓存已过期，等待更新。':'按提供方时间展示；不保证实时行情。'}`:({unregistered:'上市代码未登记，暂不提供行情。',unsupported:'该交易所行情暂未接通。',pending:'正在更新行情…',unavailable:'行情暂不可用，等待来源更新。'}[q.status]||'行情暂不可用。');
if(q.refreshing&&attempt<4)setTimeout(()=>quote(attempt+1),3000);
}catch{$('quote-time').textContent='行情读取失败，请稍后刷新。';}}
function date(v){if(typeof v==='number'){const d=new Date(v<1e11?v*1000:v);return Number.isNaN(d.getTime())?'时间未登记':d.toLocaleDateString('zh-CN',{timeZone:'Asia/Shanghai'});}return '时间未登记';}
async function news(){$('news-retry').hidden=true;try{const n=await json('/api/news?'+new URLSearchParams({company:cid,limit:'6'})),items=(n.feed?.items||[]).filter(v=>safe(v.url));$('company-news-list').innerHTML=items.map(v=>`<li><a href="${esc(safe(v.url))}" target="_blank" rel="noopener">${esc(v.title_zh||v.title||'查看新闻原文')}</a><small>${esc(v.domain||'新闻来源')} · ${esc(date(v.published_at))}${!v.title_zh?' · 原文标题':''}</small></li>`).join('');
$('news-status').textContent=!n.feed||['not_connected','unavailable','disabled'].includes(n.feed.status)?'inews 公司新闻尚未接通。':n.reader?.stale?'inews 同步已过期；下方保留此前公司新闻。':items.length?'inews 已关联此公司 · 最近 '+items.length+' 条':'当前 inews 同步窗口没有此公司的已关联新闻。';
}catch{$('news-status').textContent='公司新闻读取失败，请重试。';$('company-news-list').replaceChildren();$('news-retry').hidden=false;}}
$('news-retry').onclick=news;
json('/api/company-window?'+new URLSearchParams({c:cid})).then(data=>{render(data);quote();news();}).catch(e=>{$('company-profile').textContent=e.message==='404'?'公司档案读取失败：公司不存在: '+cid:'公司资料暂不可用，请稍后刷新。';$('quote-time').textContent='公司资料不可用，未请求行情。';$('news-status').textContent='公司资料不可用，未请求新闻。';});
})();
