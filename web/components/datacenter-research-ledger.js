const region = document.getElementById('region-filter');
const country = document.getElementById('country-filter');
const search = document.getElementById('search-filter');
const status = document.getElementById('ledger-status');
const rows = document.getElementById('ledger-rows');
const esc = value => String(value ?? '未披露').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let records = [];
function sourceLinks(record) {
  return record.sources.map((url, i) => { try { const parsed = new URL(url); return /^https?:$/.test(parsed.protocol) ? '<li><a href="'+esc(parsed.href)+'" target="_blank" rel="noopener noreferrer">来源 '+(i+1)+'</a></li>' : ''; } catch { return ''; } }).join('');
}
function plain(value) { return String(value ?? '未披露').replace(/\[([^\]]+)\]\(https?:\/\/[^)]+\)/g, '$1'); }
function render() {
  const query = search.value.trim().toLocaleLowerCase();
  const selected = records.filter(r => (!region.value || r.region === region.value) && (!country.value || r.country_code === country.value) && (!query || [r.name, r.country_label, r.public_location, ...Object.values(r.roles), r.capacity.quoted_text, r.stage_and_date].join(' ').toLocaleLowerCase().includes(query)));
  rows.innerHTML = selected.map(r => '<tr data-research-id="'+esc(r.id)+'"><td><strong>'+esc(r.name)+'</strong><br>'+esc(r.country_label)+'</td><td class="location">'+esc(r.public_location)+'</td><td class="roles">建设：'+esc(r.roles.developer_or_builder)+'<br>运营：'+esc(r.roles.operator)+'<br>使用：'+esc(r.roles.disclosed_user)+'</td><td class="capacity">'+esc(r.capacity.quoted_text)+(r.boundary?'<p>'+esc(r.boundary)+'</p>':'')+'</td><td>'+esc(r.stage_and_date)+'<details><summary>证据日期与来源</summary><p>'+esc(plain(r.evidence_date_text))+'</p><ul>'+sourceLinks(r)+'</ul></details></td></tr>').join('');
  status.textContent = '显示 '+selected.length+' / '+records.length+' 条记录';
}
try {
  const response = await fetch('/research/data-centers-2026-project-ledger.json');
  if (!response.ok) throw Error('HTTP '+response.status);
  const payload = await response.json();
  if (payload.schema !== 'source-reported-project-ledger-v1' || !Array.isArray(payload.records)) throw Error('台账格式无效');
  records = payload.records;
  const countries = new Map(records.map(r=>[r.country_code,r.country_label]));
  for (const [code,label] of countries) { const option=document.createElement('option'); option.value=code; option.textContent=label; country.append(option); }
  for (const control of [region,country]) control.addEventListener('change',render);
  search.addEventListener('input',render);
  const params = new URLSearchParams(location.search);
  if (['us','sea','cn'].includes(params.get('region'))) region.value=params.get('region');
  if (countries.has(params.get('country'))) country.value=params.get('country');
  search.value=params.get('q') || '';
  render();
} catch (error) { status.textContent = '项目台账加载失败，请重新加载，或阅读地区附录。'; console.error(error); }
