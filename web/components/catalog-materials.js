(() => {
const params=new URLSearchParams(location.search);
if(params.get('view')!=='materials')return;
const cid=params.get('c')||'nvidia',root=document.getElementById('catalog');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const original=u=>{try{const p=new URL(u);return p.protocol==='https:'&&!p.username&&!p.password?p.href:'';}catch{return '';}};
root.innerHTML='<h2>手册与附件索引</h2><p class="catalog-note">按归档内容身份去重。保留产品页链接关系；机箱手册、电源报告等按原标签展示。点击查看官方原文。</p><form id="material-search" class="controls"><input id="material-query" type="search" aria-label="搜索资料" placeholder="搜索文件名、型号或资料标签"><button>搜索</button></form><p id="material-status" role="status"></p><ul id="material-list"></ul><div class="pager"><button id="material-previous">上一页</button><button id="material-next">下一页</button></div>';
const input=document.getElementById('material-query'),status=document.getElementById('material-status'),list=document.getElementById('material-list');
let offset=Math.max(0,Number(params.get('offset'))||0),q=params.get('q')||'',generation=0;
input.value=q;
async function load(){const id=++generation;status.textContent='读取资料索引…';try{
 const r=await fetch('/api/product-catalog/'+encodeURIComponent(cid)+'?'+new URLSearchParams({view:'materials',q,offset:String(offset)}));if(!r.ok)throw Error();const d=await r.json();if(id!==generation)return;
 status.textContent=d.available?`${d.total} 份已索引资料 · ${d.unassigned} 份型号待关联 · 当前匹配 ${d.matched} 份`:'资料索引尚未接收。';
 list.innerHTML=d.items.map(v=>{const url=original(v.urls[0]);const links=[...new Map(v.links.map(l=>[l.product_id,l])).values()];return `<li><strong><a href="${esc(url)}" target="_blank" rel="noopener">${esc(v.name)}</a></strong><p>${esc(v.format.toUpperCase())} · ${links.length?links.map(l=>`<a href="/product-catalog.html?${esc(new URLSearchParams({c:cid,view:'products',product_id:l.product_id}).toString())}">${esc((l.product_name?l.product_name+' · ':'')+(l.label||'关联产品'))}</a>`).join(' · '):'型号待关联'}</p><small>${v.link_count>4?`另有 ${v.link_count-4} 个产品页关联 · `:''}资料原文请点击文件名</small></li>`;}).join('');
 document.getElementById('material-previous').disabled=offset<=0;document.getElementById('material-next').disabled=offset+d.limit>=d.matched;
 history.replaceState(null,'','/product-catalog.html?'+new URLSearchParams({c:cid,view:'materials',...(q?{q}:{}),...(offset?{offset:String(offset)}:{})}));
}catch{if(id===generation){status.textContent='资料索引读取失败，请重新搜索。';list.replaceChildren();}}}
document.getElementById('material-search').onsubmit=e=>{e.preventDefault();q=input.value;offset=0;load();};
document.getElementById('material-previous').onclick=()=>{offset=Math.max(0,offset-50);load();};document.getElementById('material-next').onclick=()=>{offset+=50;load();};load();
})();
