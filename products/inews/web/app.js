import { auth, initAuth, onAuthChange, refreshAuth, post, openModal } from './auth.js';

const $ = (s) => document.querySelector(s);
const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
const fmt = new Intl.DateTimeFormat([], { hour: '2-digit', minute: '2-digit', hour12: false });
const dayFmt = new Intl.DateTimeFormat([], { month: 'short', day: 'numeric', weekday: 'short' });

function ago(ms) {
  const s = Math.max(0, (Date.now() - ms) / 1000);
  if (s < 60) return `${s | 0}秒前`;
  if (s < 3600) return `${(s / 60) | 0}分前`;
  if (s < 86400) return `${(s / 3600) | 0}小时前`;
  return `${(s / 86400) | 0}天前`;
}

const state = { tab: 'timeline', items: [], pool: [], timer: null, genre: '', todayTotal: 0 };

/** Techmeme 发现的域名逐个确认抓取路线。A=固定关键词搜索，B=官方 AI 专题。 */
const TECHMEME_ROUTE_STATE = new Map([
  ['ft.com', 'A · 已建'],
  ['bloomberg.com', 'B · 已建'],
  ['cnbc.com', 'B · 已建'],
  ['wsj.com', 'B · 已建'],
  ['reuters.com', 'B · 已建'],
  ['axios.com', 'A · 已建'],
]);

/** 时间线公开，其余标签页要管理员。 */
const STAFF_TABS = new Set(['dashboard', 'admin']);

/** 每类标签一种颜色(2026-08-31 站长要求):
 *  必读=酸绿 · 首发=绿 · primary=蓝 · wire=紫 · relay/platform=灰 ·
 *  未收录=琥珀 · 低分/静音源=红。颜色即类别,一眼可辨。 */
const SEED_BADGE = {
  primary: 'sd-badge--info',   // 原创媒体 = 蓝
  wire: 'sd-badge--violet',    // 官方/通稿 = 紫
  relay: 'sd-badge--muted',    // 转载聚合 = 灰
  platform: 'sd-badge--muted',
};
const badge = (text, kind = 'sd-badge--muted') => el('span', `sd-badge ${kind}`, text);

function params() {
  // 读者只有一种视图:精选(v≥2)+合并转载,固定不可选 —— 复核和全量
  // 都在分析页。可变的只有:分类(模块条)、地区、搜索词。
  const p = new URLSearchParams({ limit: '200', mode: 'relevant', v: '2', collapse: '1' });
  const q = $('#q').value.trim(); if (q) p.set('q', q);
  if (state.genre) p.set('genre', state.genre);
  if ($('#region').value) p.set('region', $('#region').value);
  return p;
}

/** Fetch JSON, turning a server-side {error} into a real thrown Error so the
 *  status bar shows the cause instead of a downstream TypeError. */
async function getJson(url) {
  const res = await fetch(url);
  const fail = (msg) => {
    // refresh() 靠 status 识别「会话过期」并退回登录门 —— 不带上它,那个分支永远走不到。
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  };
  let data;
  try { data = await res.json(); } catch { fail(`HTTP ${res.status}`); }
  if (data && data.error) fail(data.error);
  if (!res.ok) fail(`HTTP ${res.status}`);
  return data;
}

/** 点分类的「秒开」架构(2026-08-31,对齐 yidian 的手感):无筛选的 200 条
 *  常驻内存(pool),点分类/地区/搜索时先在本地过滤立刻渲染 —— 0ms,不等网络;
 *  同时后台拉服务端权威结果(该分类完整深度,本地池只有全站前 200 的子集),
 *  回来后静默换上。seq 挡乱序:快速连点时只有最后一次点击的响应生效。 */
let tlSeq = 0;
function localFilter() {
  const q = $('#q').value.trim().toLowerCase();
  const region = $('#region').value;
  return state.pool.filter((it) =>
    (!state.genre || it.genre === state.genre)
    && (!region || it.region === region)
    && (!q || (it.title || '').toLowerCase().includes(q) || (it.title_zh || '').includes(q)));
}

async function loadTimeline() {
  const p = params();
  const filtered = p.has('q') || p.has('genre') || p.has('region');
  if (state.pool.length) {
    // 「回全部」也要秒开:池子本身就是无筛选视图,直接上屏,后台刷新换血。
    const quick = filtered ? localFilter() : state.pool;
    // 本地空结果不上屏:池子里没有≠库里没有,别闪一下「暂无数据」再变出文章。
    if (quick.length) { state.items = quick; render(); }
  }
  const my = ++tlSeq;
  const { items } = await getJson('/api/timeline?' + p);
  if (my !== tlSeq) return;
  state.items = items || [];
  if (!filtered) state.pool = state.items;
  render();
}

function render() {
  const root = $('#rows');
  root.textContent = '';
  if (!state.items.length) {
    root.append(el('div', 'sd-empty', '暂无数据 —— 采集器每 60 秒跑一轮'));
    $('#stream-count').textContent = '0 条';
    return;
  }
  // 转载恒合并:故事的时间锚点=最新动态(latest_at),新报道进来整个故事
  // 浮上来;行里展示的仍是首发标题。
  const anchorOf = (it) => (it.cluster_size > 1 && it.latest_at) ? it.latest_at : it.published_at;
  let day = '';
  for (const it of state.items) {
    const d = dayFmt.format(anchorOf(it));
    if (d !== day) { day = d; root.append(el('div', 'sd-daysep', d)); }
    root.append(row(it, anchorOf(it)));
  }
  const newest = state.items[0];
  const newestAt = anchorOf(newest);
  $('#stream-count').textContent = `${state.items.length} 条 · 最新 ${ago(newestAt)}`;
  $('#status').textContent = `今日收录 ${n2s(state.todayTotal)} 条 · 更新于 ${fmt.format(Date.now())}`;
  $('#clock-latest').textContent = fmt.format(newestAt);
  $('#clock-sub').textContent = `${ago(newestAt)} · ${newest.domain}`;
  $('#kicker-right').textContent = `${new Set(state.items.map((x) => x.domain)).size} 个来源在流`;
}

function row(it, anchorAt = it.published_at) {
  const node = el('div', 'sd-row');
  // 时间轴节点的疏密即推送节奏:60 分钟内的实心酸绿点,更早的空心(app.css)。
  if (Date.now() - anchorAt < 3600e3) node.classList.add('sd-row--hot');

  const time = el('div', 'sd-time', fmt.format(anchorAt));
  time.append(el('span', null, ago(anchorAt)));

  // 标题在左,标签跟在标题右侧同一行;来源列挪到最右;序号列取消。
  // 标题统一中文：有译文就用译文，原文降为第二行（默认收起，勾「显示原文」展开）。
  // 没有译文时回落到原标题 —— 宁可显示英文，也不能让这条新闻消失。
  const zh = it.title_zh || it.title;
  const translated = Boolean(it.title_zh && it.title_zh !== it.title);
  const importance = it.value === 3 ? ' sd-story--v3' : (it.value === 2 ? ' sd-story--v2' : '');
  const story = el('div', `sd-story${importance}${it.relevant === 0 ? ' sd-story--excluded' : ''}${translated ? ' sd-story--mt' : ''}`);
  const head = el('div', 'sd-story__head');
  const a = el('a', null, zh);
  // 链接走 /r/:id 服务端跳转:Google News 长链接不再进列表 payload,
  // 这一刀把 200 行从 143KB 压到 ~15KB(分类切换慢的最大头)。
  a.href = it.url || `/r/${it.id}`; a.target = '_blank'; a.rel = 'noopener noreferrer';
  a.title = it.title;
  head.append(a);
  // 标签只放读者关心的,按重要性排:分类 → 必读 → 首发 → 转载。
  // 「未收录/primary/relay」是运营概念(域名审核的事),从时间线撤下,
  // 留在分析页的域名工作台里;低分/静音源只在「全部」复核模式出现。
  const gm = GENRE_META[it.genre];
  if (gm) {
    // 分类胶囊即导航:点一下=按这个分类筛,和顶部下拉联动(再点下拉「全部分类」退出)。
    const chip = el('button', 'sd-cat sd-cat--tag');
    const sq = el('i');
    sq.style.background = gm[1];
    chip.append(sq, document.createTextNode(gm[0]));
    chip.title = `只看「${gm[0]}」`;
    chip.onclick = () => {
      state.genre = it.genre;
      if (lastFilters) renderGenreBar(lastFilters);
      window.scrollTo({ top: 0 });
      refresh();
    };
    head.append(chip);
  }
  if (it.value === 3) head.append(badge('必读', 'sd-badge--acid'));
  if (it.is_original) head.append(badge('首发', 'sd-badge--ok'));
  if (it.relevant === 0) head.append(badge(`低分 ${it.relevance}`, 'sd-badge--alert'));
  if (it.domain_status === 'muted') head.append(badge('已静音源', 'sd-badge--alert'));
  if (it.cluster_size > 1) {
    const dup = el('button', 'sd-badge sd-dup', `+${it.cluster_size - 1} 转载 ▾`);
    dup.onclick = () => expand(node, it.cluster_id, dup);
    head.append(dup);
  }
  story.append(head);
  if (translated) {
    // 原文默认收起(标题悬停可见);「显示原文」开关已随读者界面大扫除移除。
    const src = el('p', 'sd-story__src', it.title);
    src.hidden = true;
    story.append(src);
  }

  // 右列:域名(可点击,新窗口开该站) + 抓取延迟。
  // angle/lang 是采集配额概念,「models / en」对读者是噪音 —— 撤下。
  const lagMin = Math.round((it.first_seen_at - it.published_at) / 60000);
  const source = el('div', 'sd-source sd-source--right');
  source.append(domainLink(it.domain));
  const sub = el('small', null, `延迟 ${lagMin <= 0 ? '<1' : lagMin} 分`);
  if (lagMin > 15) sub.classList.add('sd-lag--slow');
  source.append(sub);

  node.append(time, story, source);
  return node;
}

async function expand(node, clusterId, pill) {
  const open = node.parentElement.querySelector(`.sd-sub[data-c="${clusterId}"]`);
  if (open) { open.remove(); pill.textContent = pill.textContent.replace('▴', '▾'); return; }
  const { items } = await getJson('/api/cluster?id=' + clusterId);
  const box = el('div', 'sd-sub');
  box.dataset.c = clusterId;
  for (const m of items) {
    const line = el('div');
    const a = el('a', null, m.title_zh || m.title);
    a.title = m.title;
    a.href = m.url; a.target = '_blank'; a.rel = 'noopener noreferrer';
    line.append(el('span', 'sd-lag', fmt.format(m.published_at)), a,
      badge(m.domain, m.is_original ? 'sd-badge--acid' : 'sd-badge--muted'));
    box.append(line);
  }
  node.after(box);
  pill.textContent = pill.textContent.replace('▾', '▴');
}

/* ================ 分析中心：内容 / 来源 / 抓取 / 车道，一页看完 ================
   信息按价值排序：先看抓到了什么（产品本身），再看谁在供给（域名资产），
   然后是抓得多快多稳（管道），最后是机器自己的调度（车道）。 */

/** 角度固定配色（CVD 校验过的 8 色）。颜色跟着角度走，整页一致；
 *  色块永远和文字标签一起出现，颜色不单独承载身份。 */
const ANGLE_COLOR = {
  models: 'var(--cat-models)', chips: 'var(--cat-chips)', money: 'var(--cat-money)',
  apps: 'var(--cat-apps)', research: 'var(--cat-research)', infra: 'var(--cat-infra)',
  policy: 'var(--cat-policy)', safety: 'var(--cat-safety)',
};
const catColor = (a) => ANGLE_COLOR[a] || 'var(--cat-other)';

function catChip(angle) {
  const c = el('span', 'sd-cat');
  const sq = el('i');
  sq.style.background = catColor(angle);
  c.append(sq, document.createTextNode(angle || '—'));
  return c;
}

/** 域名可点击:新窗口打开该网站首页 —— 审核前先看一眼它长什么样。 */
function domainLink(domain) {
  const a = el('a', null, domain);
  a.href = `https://${domain}`;
  a.target = '_blank'; a.rel = 'noopener noreferrer';
  a.title = `新窗口打开 ${domain},看看这个站的成色`;
  return a;
}

/** 域名一键处置:信任=永久白名单,静音=从默认时间线消失。都可随时改回。 */
function domainOps(domain, status) {
  const wrap4 = el('span');
  wrap4.style.whiteSpace = 'nowrap';
  const mk = (label, to, title) => {
    const b = el('button', 'sd-badge sd-dup', label);
    b.title = title;
    b.style.marginLeft = '4px';
    b.onclick = async () => {
      b.disabled = true;
      try {
        await post(`/api/domain-status?domain=${encodeURIComponent(domain)}&status=${to}`);
        loadDashboard();
      } catch (e) { $('#status').textContent = '操作失败 · ' + e.message; b.disabled = false; }
    };
    return b;
  };
  if (status === 'trusted') wrap4.append(badge('✓ 已信任', 'sd-badge--ok'));
  else wrap4.append(mk('信任', 'trusted', '通过审核:标为可靠源,不再出现在待审名单里'));
  if (status === 'muted') wrap4.append(mk('恢复', 'observing', '解除静音,重新出现在时间线'));
  else wrap4.append(mk('静音', 'muted', '内容农场:从默认时间线消失(「全部」模式可复核)'));
  return wrap4;
}

const VALUE_LABEL = { 3: '3 必读', 2: '2 可读', 1: '1 边角', 0: '0 垃圾' };

/** MECE 内容分类的中文名与配色(和角度是两套体系,但共用同一色板)。 */
const GENRE_META = {
  model: ['模型与研究', 'var(--cat-models)'], compute: ['算力与芯片', 'var(--cat-chips)'],
  business: ['资本与公司', 'var(--cat-money)'], policy: ['政策与治理', 'var(--cat-policy)'],
  safety: ['安全与风险', 'var(--cat-safety)'], apps: ['应用与落地', 'var(--cat-apps)'],
  society: ['社会与人', 'var(--cat-research)'], noise: ['噪音', 'var(--cat-other)'],
  other: ['其他', 'var(--cat-other)'],
};

/** 千分位:59921 → 59,921。五位数起没有分隔符就读不动了。 */
const n2s = (x) => Number(x || 0).toLocaleString('en-US');

/** 板块脚注:第一行「这是什么/怎么来」,酸绿行「你要做的」。 */
function explain(what, action) {
  const d = el('div', 'sd-note sd-note--tight');
  d.append(el('p', null, what));
  if (action) d.append(el('p', 'hl', '▸ 你要做的：' + action));
  return d;
}

/** 彩色条形列表。rows: {label: string|Node, n, val?, color?}；
 *  wide 给长标签（域名）用，rank 加名次前缀。 */
function bars(rows, opts = {}) {
  const max = Math.max(1, ...rows.map((r) => r.n));
  const box = el('div', `sd-bars${opts.wide ? ' sd-bars--wide' : ''}`);
  rows.forEach((r, idx) => {
    const line = el('div');
    const label = el('span');
    label.style.overflow = 'hidden';
    label.style.textOverflow = 'ellipsis';
    label.style.whiteSpace = 'nowrap';
    if (opts.rank) label.append(el('span', 'sd-rankn', String(idx + 1).padStart(2, '0')));
    if (r.label instanceof Node) label.append(r.label);
    else { label.append(document.createTextNode(r.label)); label.title = r.label; }
    const bar = el('div', 'sd-bar');
    const i = el('i');
    i.style.width = `${(r.n / max) * 100}%`;
    if (r.color) i.style.background = r.color;
    bar.append(i);
    line.append(label, bar, el('span', 'val', r.val ?? n2s(r.n)));
    box.append(line);
  });
  return box;
}

/** 给柱图套上数量级刻度:虚线画在整数位(2,000/4,000 这种),不是画在
 *  「最大值的一半」这种没人心算得出来的位置。 */
function sparkScale(sparkEl, max) {
  const wrap5 = el('div', 'sd-sparkwrap');
  // 选一个 1/2/5×10^k 的整级距,画出 2-4 条线。
  const raw = Math.max(1, max) / 3;
  const pow = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * pow).find((s) => s >= raw);
  for (let v = step; v <= max * 0.99; v += step) {
    const gl = el('div', 'sd-spark-gl');
    gl.style.top = `${(1 - v / max) * 68 + 12}px`;   // 柱区高 68px,上方留 12px 放标签
    gl.append(el('span', null, n2s(v)));
    wrap5.append(gl);
  }
  wrap5.append(sparkEl);
  return wrap5;
}

/** 固定桶数的柱图（perDay / perHour 都走这里，缺的桶补 0）。
 *  悬浮提示之外，下沿再给首尾两个刻度 —— 值不能只活在 tooltip 里。 */
function buckets(rows, key, bucketMs, count, now, label) {
  const m = new Map(rows.map((r) => [r[key], r.n]));
  const base = Math.floor(now / bucketMs) * bucketMs;
  const ticks = [];
  for (let i = count - 1; i >= 0; i--) ticks.push(base - i * bucketMs);
  const max = Math.max(1, ...ticks.map((t) => m.get(t) || 0));
  const box = el('div', 'sd-spark');
  for (const t of ticks) {
    const n = m.get(t) || 0;
    const col = el('i');
    col.style.height = `${(n / max) * 100}%`;
    col.title = `${label(t)} · ${n2s(n)} 条`;
    box.append(col);
  }
  const axis = el('div', 'sd-spark-x');
  axis.append(el('span', null, label(ticks[0])), el('span', null, label(ticks[ticks.length - 1])));
  return stack(sparkScale(box, max), axis);
}

/** 面板头下的一行紧凑数字。pairs: [label, value][] */
function minirow(pairs) {
  const d = el('div', 'sd-minirow');
  for (const [label, value] of pairs) {
    const s = el('span');
    s.append(document.createTextNode(label + ' '), el('b', null, String(value)));
    d.append(s);
  }
  return d;
}

/** 竖着摞几个节点（替代旧 wrap 的场景，去掉长篇说明）。 */
function stack(...nodes) { const d = el('div'); d.append(...nodes.filter(Boolean)); return d; }

async function loadDashboard() {
  const [s, d, r, th] = await Promise.all([
    getJson('/api/stats'), getJson('/api/domains?min=1'), getJson('/api/rules'),
    getJson('/api/throttle').catch(() => ({ unavailable: true })),
  ]);
  const root = $('#dashboard');
  root.textContent = '';
  const now = s.now;
  const T = s.totals, L = s.latencyP, F = s.fetchTotals;
  const TR = s.translation || { total: 0, done: 0 };

  /* ===== 总览：一眼看到结论 ===== */
  const cards = el('div', 'sd-metrics sd-metrics--3up');
  const card = (k, v, sub2) => {
    const c = el('div', 'sd-metric');
    c.append(el('strong', null, String(v)), el('span', null, k));
    if (sub2) c.append(el('span', null, sub2));
    return c;
  };
  cards.append(
    card('文章总数', n2s(T.articles),
      `AI 相关 ${n2s(T.relevant)} 条 · ${pct((T.relevant || 0) / Math.max(1, T.articles))}`),
    card('域名总数', n2s(T.domains),
      `= 文章里见过的独立域名 · 先验名单 ${s.seedTotal} · 已静音 ${s.mutedCount ?? 0}`),
    card('近 24 小时', n2s(s.last24h.n), `近 1 小时 ${n2s(s.lastHour.n)} 条`),
    card('抓取延迟 P50', L.p50 == null ? '—' : `${L.p50.toFixed(1)}分`,
      `P90 ${fx(L.p90)} · P99 ${fx(L.p99)}`),
    card('翻译覆盖', pct(TR.total ? TR.done / TR.total : NaN),
      `相关条目 ${n2s(TR.total)} · 待译 ${n2s(Math.max(0, (TR.total || 0) - (TR.done || 0)))}`),
    card('车道 热/温/冷', `${r.counts.hot || 0}/${r.counts.warm || 0}/${r.counts.cold || 0}`,
      `shard=一条具体的搜索查询,共 ${r.shards.length} 条 · 按产出分三档轮询:`
      + `热=每分钟扫 温≈${r.schedule.loopMin.warm}分一圈 冷≈${r.schedule.loopMin.cold}分一圈`
      + ` · 人工锁定 ${r.shards.filter((x) => x.pinned).length}`),
  );
  const board = el('div', 'sd-dashboard');
  const bh = el('div', 'sd-dashboard__head');
  const days = s.since ? Math.max(1, Math.ceil((now - s.since) / 864e5)) : 0;
  bh.append(el('span', null, '分析中心 / ANALYTICS'),
    el('em', null, days ? `自 ${new Date(s.since).toLocaleDateString()} · 运行 ${days} 天 · LIVE` : 'LIVE'));
  board.append(bh, cards);
  root.append(board);

  /* 页内导航：一页很长，锚点直达。订阅原文库的数据由 Python 链路生成，
     在统一 Dashboard 汇总；这里给一条直达路径，不重复搬运其指标。 */
  const toc = el('div', 'sd-toc');
  [['#sec-pipeline', '⓪ 流水线 · 抓取规则'], ['#sec-content', '① 内容 · 抓到了什么'],
   ['#sec-sources', '② 来源 · 谁在供给'], ['#sec-fetch', '③ 抓取 · 多快多稳'],
   ['#sec-lanes', '④ 车道 · 规则自演化'],
   ['/rawarticle/dashboard/', '统一原文库 Dashboard ↗']]
    .forEach(([href, label]) => { const a = el('a', null, label); a.href = href; toc.append(a); });
  root.append(toc);

  /* ===== ⓪ 采集流水线：先看清东西是怎么进来的，再看进来了什么 ===== */
  root.append(section('⓪ 流水线 —— 抓取规则与 24h 实测', 'sec-pipeline'));
  root.append(panel('采集流水线 · 格子=固定结构 · 数字=24h 实测', stack((() => {
    const flow = el('div', 'sd-flow');
    const boxNode = (value, name, sub, acid) => {
      const b = el('div', `sd-flow__box${acid ? ' sd-flow__box--acid' : ''}`);
      b.append(el('b', null, String(value)), el('span', null, name));
      if (sub) b.append(el('small', null, sub));
      return b;
    };
    const arrow = (label) => {
      const a = el('div', 'sd-flow__arrow');
      a.append(el('span', null, '→'));
      if (label) a.append(el('small', null, label));
      return a;
    };
    const bucketVal = th.unavailable ? '—' : `${th.reqPerMin}/分`;
    const bucketSub = th.unavailable
      ? '采集器未运行(演示模式)'
      : `基准 ${Math.round((th.basePerSec || 0) * 600) / 10}/分 · ${th.throttled ? '限流降速中,逐轮爬升' : '全速'} · 累计限流 ${th.throttleEvents}`;
    flow.append(
      boxNode(r.shards.length, '查询 shard',
        `角度×地区×关键词 · 热${r.counts.hot || 0} 温${r.counts.warm || 0} 冷${r.counts.cold || 0}`),
      arrow('分车道轮转'),
      boxNode(bucketVal, '令牌桶', bucketSub),
      arrow('限流即减半'),
      boxNode(n2s(F.runs), 'HTTP 请求',
        `304 缓存 ${pct((F.notModified || 0) / Math.max(1, F.runs))} · 限流 ${F.throttled ?? 0} · 错误 ${F.errors ?? 0}`),
      arrow(`${n2s(F.ok)} 次有货`),
      boxNode(n2s(F.items), '看到条目', 'RSS 返回·含每轮重复看到的旧条'),
      arrow(`新且相关 ${pct((F.kept || 0) / Math.max(1, F.items))}`),
      boxNode(n2s(F.kept), '入库', '先去掉已见过的,再过相关性闸门'),
      arrow('翻译+价值分'),
      boxNode(`${n2s(s.last24h.n)}/24h`, '时间线',
        `全库 ${n2s(T.articles)} 条 · 译文覆盖 ${pct(TR.total ? TR.done / TR.total : NaN)}`, true),
    );
    return flow;
  })(), explain(
    '一条新闻从 Google News 到时间线要过的每一道闸。「看到条目」含大量重复:热车道每分钟重扫,同一条新闻会被反复看到,所以「新且相关」比例低是去重的功劳、不是丢新闻 —— 先按唯一 ID 去掉已见过的,剩下的新条目再过相关性闸门,次序固定,没有随机。「36/分」是令牌桶给全站定的请求上限(防封),实际用量看 HTTP 请求格子。',
    '入库率骤降=词表出问题;限流数抬头=把 ST_CYCLE_MS 调大。平时这里绿灯就不用管。',
  ))));

  /* ===== ① 内容：抓到了什么（产品本身，最重要） ===== */
  root.append(section('① 内容 —— 抓到了什么', 'sec-content'));
  let g = el('div', 'sd-grid2');

  // 每日收录：把数字亮出来,不让读者去柱子上悬停找。
  const dayKey = Math.floor(now / 864e5) * 864e5;
  const dayMap = new Map((s.perDay || []).map((x) => [x.d, x.n]));
  const last7 = Array.from({ length: 7 }, (_, i) => dayMap.get(dayKey - i * 864e5) || 0);
  g.append(panel('每日收录量 · 近 30 天', stack(
    minirow([['今日', n2s(dayMap.get(dayKey) || 0)], ['昨日', n2s(dayMap.get(dayKey - 864e5) || 0)],
      ['近 7 日均', n2s(Math.round(last7.reduce((a, b) => a + b, 0) / 7))],
      ['30 日合计', n2s((s.perDay || []).reduce((a, x) => a + x.n, 0))]]),
    buckets(s.perDay, 'd', 864e5, 30, now, (t) => new Date(t).toLocaleDateString()),
    minirow([['近 24 小时 / 时', '']]),
    buckets(s.perHour, 'h', 36e5, 24, now, (t) => `${dayFmt.format(t)} ${fmt.format(t)}`),
    explain('按文章自己的发布时间统计每天/每小时入库多少条(悬停柱子看具体日期和数量)。',
      '某天突然塌到 0 = 采集器那天断过,去 ③ 对照请求图;持续下滑 = 车道普遍降档,去 ④ 看调档流水。'),
  )));

  const aAll = s.byAngleAll || [];
  g.append(panel('分类分布 · 全库按条数排序', stack(
    minirow([['角度', aAll.length], ['文章', T.articles ?? 0],
      ['相关率', pct((T.relevant || 0) / Math.max(1, T.articles))]]),
    bars(aAll.map((a) => ({
      label: catChip(a.angle), n: a.n, color: catColor(a.angle),
      val: `${a.n} · 24h +${a.n24 ?? 0}`,
    })), { wide: true }),
    explain('注意:角度记的是「哪组查询词先抓到它」,不是内容分类 —— 一篇英伟达融资新闻被 chips 组先抓到就记 chips,不互斥也不穷尽;region 更是语言/地域桶而非主题。它衡量的是各查询组的产出,不是世界上 AI 新闻的真实构成。',
      '把它当采集配额表看:你关心的角度长期垫底=那组词太窄,去 keywords.js 补。真正的内容归档看右边的「内容分类」。'),
  ), '色=角度 全页一致'));

  if (s.byGenre?.length) {
    const gTotal = s.byGenre.reduce((a, x) => a + x.n, 0) || 1;
    g.append(panel('内容分类 · 7 天 · 穷尽且互斥', stack(
      bars(s.byGenre.map((x) => {
        const [zh, color] = GENRE_META[x.g] || [x.g, 'var(--cat-other)'];
        return { label: zh, n: x.n, color, val: `${n2s(x.n)} · ${pct(x.n / gTotal)}` };
      }), { wide: true }),
      explain('这才是按内容归的档:模型/算力/资本/政策/安全/应用/社会 七大类 + 噪音 + 其他,一篇只属一类(难分按 政策>安全>资本>算力>模型>应用>社会 取先),穷尽且互斥。左边的角度负责撒网(允许重叠),这里负责归档(不许重叠)。',
        '规则先粗判,LLM 精化(ST_CLASSIFY)开启后按标题内容重归 —— 精化覆盖率看「价值分布」面板。'),
    ), '一篇只属一类'));
  }

  if (s.valueDist?.length) {
    const llmDone = s.valueDist.reduce((a, x) => a + (x.llm || 0), 0);
    const vTotal = s.valueDist.reduce((a, x) => a + x.n, 0);
    g.append(panel('价值分布 · 7 天(相关条目)', stack(
      barlist(s.valueDist.map((x) => [VALUE_LABEL[x.v] ?? String(x.v), x.n]),
        null, (label) => label.startsWith('3') || label.startsWith('2')),
      minirow([['信噪比(≥2)', pct(s.valueDist.filter((x) => x.v >= 2).reduce((a, x) => a + x.n, 0) / Math.max(1, vTotal))],
        ['LLM 精化', `${llmDone}/${vTotal}`]]),
      explain('第二根轴：每条按「对研究 AI 生态的价值」打 0-3 分(3=前沿实验室/芯片/重大融资/监管,0=导购/表彰/软文)。入库时用规则打,配置 LLM 后逐批精化。时间线默认只显示 ≥2。',
        '信噪比长期低于三成 = 垃圾源变多,去 ② 的「建议静音」清一轮。'),
    ), '时间线默认只显示 ≥2'));
  }

  {
    const b = s.editorialBenchmark;
    if (b?.available) {
      const ref = b.reference, cur = b.candidate, cmp = b.comparison;
      const bb = b.sources?.bloomberg || { total: 0, bodyCoverage: 0 };
      const tm = b.sources?.techmeme || { total: 0 };
      const fit = cmp.fit == null ? '—' : `${cmp.fit}%`;
      g.append(panel('Bloomberg × Techmeme 动态编辑基准', stack(
        minirow([['契合度', fit], ['联合样本', ref.total], ['Bloomberg', bb.total],
          ['Techmeme', tm.total], ['其他快讯 7 天', cur.total], ['Bloomberg 正文覆盖', pct(bb.bodyCoverage)]]),
        bars([
          { label: '必读(3)', n: cur.dist[3], val: `快讯 ${pct(cur.mustReadRate)} / 基准 ${pct(ref.mustReadRate)}`, color: 'var(--sd-warn)' },
          { label: '可见(≥2)', n: cur.dist[2] + cur.dist[3], val: `快讯 ${pct(cur.usefulRate)} / 基准 ${pct(ref.usefulRate)}`, color: 'var(--sd-acid)' },
          { label: '噪音(0)', n: cur.dist[0], val: `快讯 ${pct(cur.noiseRate)} / 基准 ${pct(ref.noiseRate)}`, color: 'var(--sd-line-strong)' },
        ], { wide: true }),
        explain(`近 ${b.windowDays} 天的 Bloomberg AI 专题负责“标题 + 正文语境”，Techmeme 严格筛出的 AI 条目负责“编辑选题 + 标题形态”；两者每天重新投影到同一套 0–3 价值档，再与其余快讯近 7 天比较（Techmeme 入选行从候选侧排除，避免自己给自己打分）。Techmeme 目前不抓下游正文，联合基准衡量选题结构，不冒充写作质量评分。`,
          cmp.status === 'aligned'
            ? '当前结构已对齐；继续观察新样本，不自动放宽硬门。'
            : '当前分布偏离基准；优先检查消费、证券和无实质动作标题，不因单日波动自动改规则。'),
      ), cmp.status === 'aligned' ? '结构已对齐' : '需继续收紧'));
    } else {
      g.append(panel('Bloomberg × Techmeme 动态编辑基准',
        el('div', 'sd-empty', '等待 Bloomberg ledger 或 Techmeme AI 样本后自动启用'), '暂无基准'));
    }
  }

  g.append(panel('待复核样本 · 近 2 天 ⚑ 需要人看', stack(
    minirow([['勉强过线(误收风险)', s.borderline.length], ['低分(漏判风险)', s.lowScoreSamples.length]]),
    sampleList([...s.borderline.slice(0, 5).map((x) => ({ ...x, relevant: 1 })),
      ...s.lowScoreSamples.slice(0, 5).map((x) => ({ ...x, relevant: 0 }))]),
    explain('相关性闸门两侧最容易出错的样本：酸绿徽章=刚过线(3-4分,可能是误收进来的垃圾),红徽章=没过线(可能是被错杀的真新闻)。',
      '每天扫一眼：看到「不该收的收了」或「该收的被拦了」,把标题发给开发者加进词表回归语料,闸门就会持续变准。'),
  ), '徽章=相关性分'));

  {
    // 21 个原始分数没法读 —— 折成 4 个有含义的段,每段对应一种处置。
    const sum = (f) => s.scoreHist.filter(f).reduce((a, x) => a + x.n, 0);
    const scoreTotal = sum(() => true) || 1;
    const bandRows = [
      { label: '≤2 未过线', n: sum((x) => x.score <= 2), color: 'var(--sd-line-strong)' },
      { label: '3-4 擦线过', n: sum((x) => x.score >= 3 && x.score <= 4), color: 'var(--sd-warn)' },
      { label: '5-7 稳过线', n: sum((x) => x.score >= 5 && x.score <= 7), color: 'var(--sd-acid)' },
      { label: '≥8 高确信', n: sum((x) => x.score >= 8), color: 'var(--sd-acid)' },
    ].map((b) => ({ ...b, val: `${n2s(b.n)} · ${pct(b.n / scoreTotal)}` }));
    g.append(panel('相关性分段 · 7 天', stack(
      bars(bandRows, { wide: true }),
      explain('第一根轴「是不是 AI」:标题命中强词+4/实体+3/上下文+1/黑名单−6,≥3 分上时间线。四段各有含义:未过线=被闸门挡下(入库但隐藏);擦线过=只靠一两个词过线,误收最可能藏在这里,价值轴会再筛一遍;稳过线和高确信基本可靠。',
        '只盯两个比例:「未过线」超过一半=查询词太宽;「擦线过」持续膨胀=该给词表补实体词了。现在不用动手。'),
    ), '琥珀=灰色地带'));
  }

  g.append(panel('语言分布与来源类型 · 7 天', stack(
    bars(s.byLang.map((l) => ({
      label: l.lang || '—', n: l.n, val: `${l.n} · 相关 ${pct(l.rel / Math.max(1, l.n))}`,
    }))),
    minirow(s.typeMix.map((t) => [t.type, `${t.n}条/${t.domains}域`])),
    explain('同一关键词在不同语言版本的 Google News 下结果完全不同 —— 多语言是覆盖面的主要来源。下行是来源类型构成(primary 原创媒体/wire 通稿/relay 聚合/未收录)。',
      '非英语占比长期走低 = 对应地区 shard 掉进冷车道了,去 ④ 核对。'),
  )));

  g.append(panel('热点故事 · 近 2 天被多家转载', stack(
    s.topClusters.length ? table(
      ['故事', '首发', '转载'],
      s.topClusters.slice(0, 8).map((c) => {
        const cell = titleCell(c.title);
        if (c.url) {
          const a = el('a', 'sd-cell', c.title || '—');
          a.title = c.title; a.href = c.url; a.target = '_blank'; a.rel = 'noopener noreferrer';
          return [a, c.domain || '—', c.n];
        }
        return [cell, c.domain || '—', c.n];
      }),
    ) : el('div', 'sd-empty', '近 2 天没有形成热点聚类'),
    explain('标题归一化后 36 小时内相同的算同一故事,最早那家记首发。被越多家转载 = 越重要,时间线默认只显示首发那一条。'),
  )));

  root.append(g);

  /* ===== ② 来源：谁在供给 —— 域名审核工作台 ===== */
  root.append(section('② 来源 —— 谁在供给（域名审核工作台）', 'sec-sources'));
  g = el('div', 'sd-grid2');

  // 白名单 Top 20 横贯整行:这是「通过审核」的主战场。
  const top20 = el('div', 'sd-span2');
  top20.append(panel('域名白名单候选 Top 20 · 全库评分', stack(
    table(
      ['#', '域名', '类型', '条数', '评分', '置信', '首发率', '处置'],
      d.domains.slice(0, 20).map((x, i) => [String(i + 1).padStart(2, '0'), domainLink(x.domain),
        typePill(x.seed_type || '未收录'), x.articles,
        scoreBar(x.score), pct(x.confidence), pct(x.originals / Math.max(1, x.articles)),
        domainOps(x.domain, x.status)]),
    ),
    explain('机器按全库表现给每个域名打的分(0-100 = 产出20+AI精准30+首发30+领先10+先验10),这 20 个是它认为最可靠的源,排队等你人工确认。域名可以点击,新窗口打开该网站看成色。「置信」不满 100% = 样本不足 20 条,分数当参考。',
      '点「信任」的三个实际效果:①从此不再进任何待审名单 ②时间线的「已收录来源/仅原创官方」筛选会包含它 ③永远不会被自动建议静音。点「静音」= 从默认时间线消失。不点 = 保持观察,无任何变化。每天过 20 个,一周清完主力源。'),
  ), '通过的尽快通过'));
  g.append(top20);

  g.append(panel(`建议静音 · 高产低价值${s.mutedCount ? `（已静音 ${s.mutedCount} 个）` : ''} ⚑ 需要人看`,
    stack(
      s.lowValueDomains?.length ? table(
        ['域名', '条数', '均值', '类型', '处置'],
        s.lowValueDomains.map((x) => [domainLink(x.domain), x.n, x.av, typePill(x.seed_type || '未收录'),
          domainOps(x.domain, x.status)]),
      ) : el('div', 'sd-empty', '没有达到建议静音标准的域名'),
      explain('7 天内发了 ≥5 条、平均价值分却不到 1 的域名 —— 内容农场的机器画像。静音后它的文章从默认时间线消失(「全部」模式仍可复核),随时可恢复。',
        '没用的尽快删:确认是农场就点「静音」,拿不准的点开域名看几条再定。'),
    ), '均值<1 且 ≥5 条'));

  g.append(panel(`未收录高产 · 7 天（${s.unlisted.length} 个待归类） ⚑ 需要人看`, stack(
    s.unlisted.length ? table(
      ['域名', '条数', '首发', '最近标题', '处置'],
      s.unlisted.slice(0, 8).map((x) => [domainLink(x.domain), x.n, x.originals, titleCell(x.sample),
        domainOps(x.domain, 'observing')]),
    ) : el('div', 'sd-empty', '全部来源都已归类'),
    explain('不在 326 个先验名单里、却持续给我们供稿的新源 —— Google News 替我们发现的,是这个项目最有价值的产出。',
      '看最近标题判断成色:好源点「信任」,农场点「静音」,拿不准先放着继续观察。'),
  ), '最有价值的发现'));

  {
    const tmDomains = s.techmemeDomains || [];
    const routeState = (domain) => TECHMEME_ROUTE_STATE.get(
      String(domain || '').toLowerCase().replace(/^www\./, ''),
    ) || '待定 A / B';
    const tmQueue = el('div', 'sd-span2');
    tmQueue.append(panel(`Techmeme AI 来源候选 · 30 天（${tmDomains.length} 个）`, stack(
      tmDomains.length ? table(
        ['域名', '媒体', '路线', '入选', '最近标题', '最近入选'],
        tmDomains.slice(0, 16).map((x) => [domainLink(x.domain), x.publisher || '—',
          routeState(x.domain), x.picks,
          titleCell(x.sample), ago(x.last_selected_at)]),
      ) : el('div', 'sd-empty', '尚无通过严格 AI 门槛的 Techmeme 来源'),
      explain('这是 Techmeme 编辑选中过、又通过本站 AI 范围门槛的原文域名队列。Techmeme 是选题认证层，不是原文发布者；这里只保存标题、入选时间、原文链接和域名。',
        '先观察样本，再逐个决定抓站路线：A = 像 FT 按关键词搜；B = 像 Bloomberg 沿指定专题/入口深入。未确认前不会自动抓整站。'),
    ), '等待逐域名定 A / B 路线'));
    g.append(tmQueue);
  }

  g.append(panel('产出 Top 10 · 7 天', stack(
    bars(s.topDomains.slice(0, 10).map((x) => ({
      label: domainLink(x.domain), n: x.n, val: `${n2s(x.n)} · 相关 ${pct(x.rel / Math.max(1, x.n))}`,
    })), { wide: true, rank: true }),
    explain('近 7 天发文最多的域名。量大 ≠ 质好 —— 聚合站靠转载也能刷量,对照右边的首发榜看。'),
  )));

  g.append(panel('首发最快 Top 10 · 全库', stack(
    s.fastestDomains?.length ? table(
      ['域名', '类型', '赢面', '胜率', '输时平均落后'],
      s.fastestDomains.map((x) => [domainLink(x.domain), typePill(x.seed_type || '未收录'),
        `${x.wins}/${x.contested}`, pctBar(x.win_rate),
        x.behind_min == null ? '全胜' : `${x.behind_min.toFixed(0)} 分`]),
    ) : el('div', 'sd-empty', '还没有被 ≥2 家报道的故事，无从比较'),
    explain('「首发」只在有竞争的故事里算：同一事件被 ≥2 家报道时,发布时间最早那家记一次「赢」。赢面 = 赢的次数/参赛次数;单独报道的冷门文章不算,否则人人都是 100% 首发。「输时平均落后」= 没抢到首发时平均比头条晚几分钟。',
      '胜率高的就是真正的一手信源,优先点「信任」;转载站永远赢不了这个榜。'),
  ), '只统计有竞争的故事'));

  g.append(panel('新出现的域名 · 近 2 天', stack(
    s.newDomains.length ? table(
      ['域名', '类型', '条数', '首次出现'],
      s.newDomains.slice(0, 8).map((x) => [domainLink(x.domain), typePill(x.seed_type || '未收录'),
        x.articles, ago(x.first_seen_at)]),
    ) : el('div', 'sd-empty', '近 2 天没有新面孔'),
    explain('第一次见到的域名。发现速度会随时间衰减 —— 从每天几十个降到几个,衰减本身说明主要信源已覆盖。'),
  )));

  g.append(panel('转载榜 · 7 天', stack(
    s.reprinters.length ? bars(
      s.reprinters.slice(0, 10).map((x) => ({
        label: domainLink(x.domain), n: x.reprints, color: 'var(--sd-line-strong)',
        val: `转载 ${x.reprints}/${x.n}`,
      })), { wide: true, rank: true },
    ) : el('div', 'sd-empty', '暂无转载记录'),
    explain('专发别人稿子的聚合站画像(msn/yahoo 这类)。转载不是罪 —— 覆盖广、速度快,但不该占据时间线,所以默认「合并转载」只显示首发。'),
  )));

  root.append(g);

  /* ===== ③ 抓取：多快多稳 ===== */
  root.append(section('③ 抓取 —— 多快多稳', 'sec-fetch'));
  g = el('div', 'sd-grid2');

  g.append(panel('抓取延迟分布 · 24h', stack(
    barlist(s.latencyBuckets.map((b) => [b.bucket, b.n]),
      ['<2分', '2-5分', '5-10分', '10-30分', '30-60分', '>60分'],
      (label) => label === '<2分' || label === '2-5分'),
    minirow([['P50', fx(L.p50)], ['P90', fx(L.p90)], ['P99', fx(L.p99)]]),
    explain('从文章发布到我们第一次看见它隔了多久。看分布别看平均:一个卡冷车道的角度能长期 40 分钟,平均数却still好看。目标是大多数落在 5 分钟内。',
      '>30 分的那截持续变厚 = 对应角度需要升车道,去 ④ 锁热。'),
  ), '发布→我们看见'));

  g.append(panel('各角度延迟 · 24h 越上越慢', stack(
    table(['角度', '条数', '平均延迟'],
      s.latencyByAngle.map((x) => [catChip(x.angle), x.n, `${x.avg_min.toFixed(1)} 分`])),
    explain('慢 ≠ 坏:冷车道本来就 15 分钟才轮一圈,低产角度慢是设计使然。',
      '只盯一件事:你认为重要的角度长期排最上面,去 ④ 的 shard 全表把它手动锁进热车道。'),
  )));

  g.append(panel('采集请求与错误 · 24h', stack(
    hourly(s.fetchPerHour.map((x) => ({ h: x.h, n: x.runs })), now, 24,
      s.fetchPerHour.map((x) => x.errors)),
    minirow([['请求', F.runs ?? 0], ['304 缓存命中', pct((F.notModified || 0) / Math.max(1, F.runs))],
      ['限流', F.throttled ?? 0], ['错误', F.errors ?? 0],
      ['入库/看到', pct((F.kept || 0) / Math.max(1, F.items))]]),
    explain('每小时发出的请求数,红色叠加=错误。请求量应该是平的(每轮固定条数);304=内容没变的零流量轮询,占比越高越省。',
      '突然掉坑 = 进程停过;红色抬头+限流数上涨 = 把 ST_CYCLE_MS 调大。'),
  ), '红叠加=错误'));

  g.append(panel('shard 采集 Top 12 · 24h 按入库', stack(
    table(['shard', '运行', '入库', '入库率', '耗时'],
      s.fetches.slice(0, 12).map((f) => [f.shard, f.runs, f.kept,
        pctBar(f.kept / Math.max(1, f.items)), `${Math.round(f.ms)}ms`])),
    s.fetchErrors.length ? stack(
      minirow([['错误分类', '']]),
      table(['原因', '次数'], s.fetchErrors.map((x) => [x.reason, x.n])),
    ) : null,
    explain('每个查询 24h 的体检表:运行次数反映车道(热车道一天上千次),入库率低 = 看到很多但都被闸门滤掉 = 词写得太宽。'),
  )));

  root.append(g);

  /* ===== ④ 车道：规则自演化 ===== */
  root.append(section('④ 车道 —— 规则自演化', 'sec-lanes'));
  const P = r.policy;
  const sc = r.schedule;

  g = el('div', 'sd-grid2');

  // 轮询节奏：三条车道各多久转完一圈（条越长=重扫越慢），加每轮请求构成。
  const LANE_BAR = { hot: 'var(--sd-acid)', warm: 'var(--sd-warn)', cold: 'var(--sd-line-strong)' };
  g.append(panel('轮询节奏 · 三条车道', stack(
    bars([
      { label: `热 ${r.counts.hot || 0} shard`, n: sc.loopMin.hot, color: LANE_BAR.hot,
        val: `每 ${sc.loopMin.hot} 分重扫一遍 · 每轮全发` },
      { label: `温 ${r.counts.warm || 0} shard`, n: sc.loopMin.warm, color: LANE_BAR.warm,
        val: `每 ${sc.loopMin.warm} 分一圈 · 每轮发 ${sc.warmPerCycle} 个` },
      { label: `冷 ${r.counts.cold || 0} shard`, n: sc.loopMin.cold, color: LANE_BAR.cold,
        val: `每 ${sc.loopMin.cold} 分一圈 · 每轮发 ${sc.coldPerCycle} 个` },
    ], { wide: true }),
    minirow([['一轮', `${sc.cycleMs / 1000} 秒`], ['每轮请求', `热${r.counts.hot || 0}+温${sc.warmPerCycle}+冷${sc.coldPerCycle}=${sc.perCycle}`],
      ['≈', `${sc.reqPerMin} 请求/分`], ['并发上限', sc.concurrency], ['查询窗口', `when:${sc.window}`]]),
  ), '条越长 = 重扫越慢'));

  // 升降档标尺：x 轴是实测产出，色带是判据区间，点是每个 shard 落在哪。
  // 一眼能看出：某条车道的点扎堆越过了自己的色带 → 机器接下来会动它。
  g.append(panel('升降档判据 · 产出标尺(条/轮)', (() => {
    const CAP = Math.max(2, P.promoteHot + 0.5);
    const x = (v) => `${Math.min(100, (v / CAP) * 100)}%`;
    const box = el('div', 'sd-scale');

    const band = el('div', 'sd-scale__band');
    const zones = [
      [0, P.demoteWarm, 'var(--sd-line-strong)'],           // 冷区
      [P.demoteWarm, P.promoteWarm, 'var(--sd-panel)'],     // 冷↔温缓冲
      [P.promoteWarm, P.demoteHot, 'var(--sd-warn)'],       // 温区
      [P.demoteHot, P.promoteHot, 'var(--sd-panel)'],       // 温↔热缓冲
      [P.promoteHot, CAP, 'var(--sd-acid)'],                // 热区
    ];
    for (const [a, b, c] of zones) {
      const i = el('i');
      i.style.width = `calc(${((b - a) / CAP) * 100}% - 2px)`;
      i.style.background = c;
      band.append(i);
    }

    const ticks = el('div', 'sd-scale__ticks');
    for (const v of [P.demoteWarm, P.promoteWarm, P.demoteHot, P.promoteHot]) {
      const t = el('span', null, String(v));
      t.style.left = x(v);
      ticks.append(t);
    }

    const rowsBox = el('div', 'sd-scale__rows');
    for (const lane of ['hot', 'warm', 'cold']) {
      const rowEl = el('div', 'sd-scale__row');
      rowEl.append(el('b', null, { hot: '热', warm: '温', cold: '冷' }[lane]));
      for (const sh of r.shards.filter((v) => v.lane === lane)) {
        const dot = el('i', 'sd-scale__dot');
        dot.style.left = x(Math.min(sh.yield_rate, CAP));
        dot.style.background = LANE_BAR[lane];
        dot.title = `${sh.shard} · ${sh.yield_rate.toFixed(2)} 条/轮${sh.pinned ? ' · 🔒锁定' : ''}`;
        rowEl.append(dot);
      }
      rowsBox.append(rowEl);
    }

    const chips = el('div', 'sd-chips');
    for (const c of [`单轮 ≥${P.burstKept} 条 直升热`, `换档后 ${P.minDwellRuns} 轮冷静期`,
      `错误率 >${P.errorRate * 100}% 强制降档`, `不满 ${P.minRuns} 轮不评估`, '冷=地板 永不停抓']) {
      chips.append(el('span', null, c));
    }

    box.append(band, ticks, rowsBox, chips);
    return box;
  })(), '点=shard · 悬浮看名字'));

  root.append(g);
  g = el('div', 'sd-grid2');

  const LANE_RANK = { cold: 0, warm: 1, hot: 2 };
  g.append(panel('最近调档 · 最多 10 条', r.events.length ? table(
    ['时间', 'shard', '变化', '理由'],
    r.events.slice(0, 10).map((e) => {
      const up = (LANE_RANK[e.to_lane] ?? 0) >= (LANE_RANK[e.from_lane] ?? 0);
      const dir = el('span', up ? 'sd-dir-up' : 'sd-dir-down',
        `${e.from_lane || '—'} → ${e.to_lane}`);
      return [ago(e.at), titleCell(e.shard), dir, titleCell(e.reason)];
    }),
  ) : el('div', 'sd-empty', '还没有调档记录 —— 每个 shard 跑满 6 轮才评估')));

  g.append(panel('调档频率 · 7 天', r.drift.length ? (() => {
    const box = el('div', 'sd-spark');
    const max = Math.max(1, ...r.drift.map((x) => x.n));
    for (const x of r.drift) {
      const b = el('i');
      b.style.height = `${(x.n / max) * 100}%`;
      b.style.background = x.up_hot >= x.down_cold ? 'var(--sd-acid)' : 'var(--sd-warn)';
      b.title = `${new Date(x.h).toLocaleString()} · ${x.n} 次（升热 ${x.up_hot} / 降冷 ${x.down_cold}）`;
      box.append(b);
    }
    return box;
  })() : el('div', 'sd-empty', '7 天内没有调档'), '酸绿=偏升 琥珀=偏降'));

  root.append(g);

  root.append(panel(`shard 全表（${r.shards.length} 个，按产出排序）`, table(
    ['查询', '角度', '地区', '车道', '产出/轮', '轮次', '判定理由'],
    r.shards.map((sh) => [queryCell(sh.q), catChip(sh.angle), sh.locale, laneCell(sh),
      sh.yield_rate.toFixed(2), sh.runs, titleCell(sh.reason)]),
  ), '点车道名锁定：热→温→冷→自动'));
}

const fx = (v) => (v == null ? '—' : `${v.toFixed(1)}分`);

function section(title, id) {
  const h = el('div', 'sd-kicker');
  h.style.marginTop = '30px';
  if (id) h.id = id;
  h.append(el('span', null, title));
  return h;
}

function typePill(t) { return badge(t || '未收录', SEED_BADGE[t] || 'sd-badge--warn'); }

function titleCell(t) {
  const c = el('span', 'sd-cell', t || '—');
  c.title = t || '';
  return c;
}

/** Horizontal bar list — better than a table for a small distribution. */
function barlist(pairs, order, isGood) {
  if (order) {
    const m = new Map(pairs);
    pairs = order.filter((k) => m.has(k)).map((k) => [k, m.get(k)]);
  }
  const max = Math.max(1, ...pairs.map((p) => p[1]));
  const total = pairs.reduce((a, p) => a + p[1], 0) || 1;
  const box = el('div', 'sd-bars');
  for (const [label, n] of pairs) {
    const line = el('div');
    const bar = el('div', 'sd-bar');
    const i = el('i');
    i.style.width = `${(n / max) * 100}%`;
    // Acid means "passed the gate"; everything else stays neutral (guide rule 2).
    if (isGood) i.className = isGood(label) ? 'acid' : 'dim';
    bar.append(i);
    line.append(el('span', null, label), bar, el('span', 'val', `${n2s(n)} · ${pct(n / total)}`));
    box.append(line);
  }
  return box;
}

/** Hourly column chart, optionally with an error series overlaid in red. */
function hourly(rows, now, hours, errs) {
  const m = new Map(rows.map((r) => [r.h, r.n]));
  const e = errs ? new Map(rows.map((r, i) => [r.h, errs[i]])) : null;
  const base = Math.floor(now / 36e5) * 36e5;
  const vals = [];
  for (let i = hours - 1; i >= 0; i--) {
    const h = base - i * 36e5;
    vals.push([h, m.get(h) || 0, e ? (e.get(h) || 0) : 0]);
  }
  const max = Math.max(1, ...vals.map((v) => v[1]));
  const box = el('div', 'sd-spark');
  for (const [h, n, err] of vals) {
    const col = el('i');
    col.style.height = `${(n / max) * 100}%`;
    col.title = `${new Date(h).toLocaleString()} · ${n2s(n)}${err ? ` · 错误 ${err}` : ''}`;
    if (err > 0) {
      const bad = el('b');
      bad.style.height = `${Math.min(100, (err / Math.max(1, n)) * 100)}%`;
      col.append(bad);
    }
    box.append(col);
  }
  const axis = el('div', 'sd-spark-x');
  const short = (t) => `${dayFmt.format(t)} ${fmt.format(t)}`;
  axis.append(el('span', null, short(vals[0][0])), el('span', null, short(vals[vals.length - 1][0])));
  return stack(sparkScale(box, max), axis);
}

function sampleList(rows) {
  if (!rows.length) return el('div', 'sd-empty', '暂无 —— 闸门两边都很干净');
  const box = el('div', 'sd-samples');
  for (const r of rows) {
    const line = el('div');
    // 中文译文 + 可点击原文链接 —— 复核就是「读标题拿不准就点开看」,
    // 没有链接的复核样本等于让人盲判(2026-08-31 站长要求)。
    const t = el(r.url ? 'a' : 'span', 't', r.title_zh || r.title);
    t.title = r.title;
    if (r.url) { t.href = r.url; t.target = '_blank'; t.rel = 'noopener noreferrer'; }
    // 分数徽章悬停显示判分依据(命中词):「为什么删/为什么收」不用猜。
    const b = badge(String(r.relevance), r.relevant ? 'sd-badge--acid' : 'sd-badge--alert');
    if (r.hits) b.title = `判分依据: ${r.hits}(!=黑名单 ~=体裁噪音)`;
    line.append(b, t, el('span', 'sd-lag', `${r.domain}${r.angle ? ' · ' + r.angle : ''}`));
    box.append(line);
  }
  return box;
}

function pctBar(x) {
  const wrap2 = el('span', 'sd-pct');
  const bar = el('span', 'sd-bar');
  const i = el('i');
  const v = Number.isFinite(x) ? x : 0;
  i.style.width = `${Math.round(v * 100)}%`;
  if (v < 0.5) i.style.background = 'var(--sd-warn)';
  bar.append(i);
  wrap2.append(el('span', null, pct(x)), bar);
  return wrap2;
}

const pct = (x) => (Number.isFinite(x) ? `${Math.round(x * 100)}%` : '—');
/** A flat bordered block. The kit has no generic panel, so this borrows the
 *  dashboard's own shape: hard border, mono rule, no radius, no shadow.
 *  hint 显示在头部右侧 —— 一句话读表提示，替代原来的大段说明。 */
function panel(title, child, hint) {
  const p = el('div', 'sd-dashboard');
  const head = el('div', 'sd-dashboard__head');
  head.append(el('span', null, title));
  if (hint) head.append(el('em', null, hint));
  const body = el('div', 'sd-panelbody');
  body.append(child);
  p.append(head, body);
  return p;
}
/** Attach an explanatory note under a chart or table. */
function wrap(child, html) { const d = el('div'); d.append(child, note(html)); return d; }
function scoreBar(score) {
  const wrap3 = el('span', 'sd-pct');
  const bar = el('span', 'sd-bar');
  const i = el('i');
  i.style.width = `${Math.min(100, score)}%`;
  if (score >= 60) i.className = 'acid';
  bar.append(i);
  wrap3.append(el('span', null, score.toFixed(1)), bar);
  return wrap3;
}
function table(head, rows) {
  const t = el('table', 'sd-table');
  const tr = el('tr');
  head.forEach((h, i) => tr.append(el('th', i ? 'num' : '', h)));
  const thead = el('thead');
  thead.append(tr);          // Node.append() returns undefined — never chain off it
  t.append(thead);
  const tb = el('tbody');
  for (const r of rows) {
    const row = el('tr');
    r.forEach((c, i) => {
      const td = el('td', i ? 'num' : '');
      if (c instanceof Node) td.append(c); else td.textContent = c;
      row.append(td);
    });
    tb.append(row);
  }
  t.append(tb);
  return t;
}

/* ---------------- 车道徽章（分析页 shard 全表用） ---------------- */
const LANE_LABEL = { hot: '热 · 每轮', warm: '温 · ~4分', cold: '冷 · ~14分' };

function note(html) { const d = el('div', 'sd-note'); d.innerHTML = html; return d; }

function laneCell(s) {
  const kind = s.lane === 'hot' ? 'sd-badge--acid' : s.lane === 'warm' ? 'sd-badge--warn' : 'sd-badge--muted';
  const b = el('button', `sd-badge ${kind}`, (LANE_LABEL[s.lane] || s.lane) + (s.pinned ? ' 🔒' : ''));
  b.style.cursor = 'pointer';
  b.style.border = '0';
  b.title = s.pinned ? '人工锁定中，点击恢复自动' : '点击锁定到下一档（热→温→冷→自动）';
  b.onclick = async () => {
    const next = s.pinned
      ? { hot: 'warm', warm: 'cold', cold: 'auto' }[s.lane]
      : s.lane;
    // 人工锁车道是写操作，和账号管理走同一条 CSRF 校验。
    await post(`/api/pin?shard=${encodeURIComponent(s.shard)}&lane=${next}`);
    refresh();
  };
  return b;
}

function queryCell(q) {
  const c = el('code', 'sd-q');
  c.textContent = q;
  return c;
}

/* ---------------- 账号管理 ---------------- */
async function loadAdmin() {
  const root = $('#admin');
  root.textContent = '';
  const [{ users }, { events }, tr] = await Promise.all([
    getJson('/api/admin/users'), getJson('/api/admin/audit'), getJson('/api/translate'),
  ]);

  const cards = el('div', 'sd-metrics sd-metrics--3up');
  const card = (k, v, sub) => {
    const c = el('div', 'sd-metric');
    c.append(el('strong', null, String(v)), el('span', null, k));
    if (sub) c.append(el('span', null, sub));
    return c;
  };
  cards.append(
    card('账号总数', users.length, `管理员 ${users.filter((u) => u.role === 'admin').length} 人`),
    card('已停用', users.filter((u) => u.status !== 'active').length, '停用即刻踢下线'),
    card('近 7 天登录', users.filter((u) => u.last_login && Date.now() - u.last_login < 7 * 864e5).length, ''),
    card('标题已译', tr.translated, `待译 ${tr.pending}`),
    card('译文缓存', tr.cached, `provider = ${tr.provider}`),
    card('审计条目', events.length, '最近 200 条'),
  );
  const box = el('div', 'sd-dashboard');
  const head = el('div', 'sd-dashboard__head');
  head.append(el('span', null, '账号 / OVERVIEW'), el('em', null, tr.enabled ? '翻译已启用' : '翻译已关闭'));
  box.append(head, cards);
  root.append(box);

  // ---- 用户表 ----
  const isAdmin = auth.user?.role === 'admin';
  const userRows = users.map((u) => {
    const role = el('select');
    for (const r of ['user', 'staff', 'admin']) role.append(new Option(r, r, false, u.role === r));
    role.disabled = !isAdmin;
    role.onchange = () => adminUpdate({ id: u.id, role: role.value }, role);

    // 用户名是**第二个登录名**：填了它就能不敲邮箱登进来。改完按回车生效，
    // 失焦不动 —— 点开一眼没改就走掉，不该发一次请求。
    const username = el('input');
    username.value = u.username || '';
    username.placeholder = '未设置';
    username.size = 10;
    username.disabled = !isAdmin;
    username.onkeydown = (ev) => {
      if (ev.key !== 'Enter') return;
      if (username.value.trim() === (u.username || '')) return;
      adminUpdate({ id: u.id, username: username.value.trim() }, username);
    };

    const toggle = el('button', 'sd-badge sd-dup', u.status === 'active' ? '停用' : '恢复');
    toggle.disabled = !isAdmin;
    toggle.onclick = () => adminUpdate({ id: u.id, status: u.status === 'active' ? 'disabled' : 'active' }, toggle);

    return [
      u.email,
      username,
      u.nickname || '—',
      role,
      badge(u.status === 'active' ? '正常' : '停用', u.status === 'active' ? 'sd-badge--ok' : 'sd-badge--alert'),
      u.last_login ? ago(u.last_login) : '从未',
      new Date(u.created_at).toLocaleDateString(),
      toggle,
    ];
  });
  root.append(panel('用户', wrap(
    table(['邮箱', '用户名', '昵称', '角色', '状态', '最后登录', '注册于', ''], userRows),
    isAdmin
      ? '<b>用户名</b>是第二个登录名（3–32 位小写字母/数字/<code>. _ -</code>），填了就能不敲邮箱登录，'
        + '改完按回车生效，清空即取消。邮箱仍然是身份本身：验证码、找回密码、通知都走它。'
        + '角色决定能看到什么：<b>staff / admin</b> 能打开分析页和这一页，<b>user</b> 只能看公开时间线。'
        + '停用会立刻销毁该用户的全部会话。系统拒绝把最后一个管理员降级 —— 那会让所有人都进不来。'
      : '只有 <b>admin</b> 能改角色和状态，你当前是 staff，这里是只读的。')));

  // ---- 审计流水 ----
  root.append(panel('审计日志（最近 200 条）', wrap(
    table(['时间', '操作者', '动作', '目标', '详情', 'IP'], events.map((e) => [
      new Date(e.at).toLocaleString(),
      e.actor_email || '—',
      e.action,
      titleCell(e.target || '—'),
      titleCell(e.detail || '—'),
      e.ip || '—',
    ])),
    '登录成功与失败、验证码发放、密码重置、角色变更全部记在这里：谁 / 何时 / 做了什么 / 对谁。'
      + '连续的 <code>login.failed</code> 后跟一条 <code>login.locked</code> 就是有人在撞库 —— 服务端已经把它锁到最多 60 分钟。')));
}

async function adminUpdate(patch, control) {
  control.disabled = true;
  try {
    await post('/api/admin/users', patch);
    await loadAdmin();
  } catch (e) {
    $('#status').textContent = '操作失败 · ' + e.message;
    control.disabled = false;
  }
}

/** 未登录（或权限不够）时，标签页显示的说明而不是一片空白。 */
function gate(sectionId) {
  // 时间线只在「整站需登录」时才会走到这里，说辞和管理页不是一回事。
  // 它也不能像分析页那样清空整个 section：筛选条和 #rows 就住在里面，
  // 删掉之后登录成功也没地方渲染。给它一个专用容器，藏起旁边两块。
  const sitewide = sectionId === 'timeline';
  const root = sitewide ? $('#timeline-gate') : $('#' + sectionId);
  root.textContent = '';
  if (sitewide) {
    root.classList.remove('sd-hide');
    $('.sd-stream').classList.add('sd-hide');
  }
  const box = el('div', 'sd-gate');
  box.append(
    el('h2', null, sitewide ? '本站需要登录' : '需要管理员登录'),
    el('p', null, sitewide
      ? '本站已开启整站登录（ST_REQUIRE_LOGIN），登录后即可查看时间线。'
      : '分析页和账号管理都在管理处里，请用管理员账号登录后查看。'),
  );
  const btn = el('button', 'sd-primary', '登录');
  btn.onclick = () => openModal('login');
  box.append(btn);
  root.append(box);
}

/* ---------------- wiring ---------------- */
async function refresh() {
  try {
    if (state.tab === 'timeline') {
      // 整站登录开着且没登录时，时间线本身就是一道门 —— 别去打一个注定 401
      // 的接口，也别把筛选条留在上面假装还能用。
      if (auth.requireLogin && !auth.user) { $('#controls').classList.add('sd-hide'); return gate('timeline'); }
      $('#controls').classList.remove('sd-hide');
      $('#timeline-gate').classList.add('sd-hide');
      $('.sd-stream').classList.remove('sd-hide');
      // filters 一起刷:模块条上的「今日条数」要跟着自动刷新走。
      await Promise.all([loadTimeline(), loadFilters()]);
      return;
    }
    if (STAFF_TABS.has(state.tab) && !auth.user?.is_staff) return gate(state.tab);
    if (state.tab === 'admin') await loadAdmin();
    else await loadDashboard();
  } catch (e) {
    // 会话可能在这一页开着的时候过期了：重新确认一次身份，让菜单和标签页
    // 立刻回到未登录状态，而不是留一个点不动的 Dashboard。
    if (e.status === 401 || e.status === 403) { await refreshAuth(); return gate(state.tab); }
    $('#status').textContent = '加载失败 · ' + e.message;
  }
}

function showTab(name) {
  if (STAFF_TABS.has(name) && !auth.user?.is_staff) { openModal('login'); return; }
  if (name === 'timeline' && auth.requireLogin && !auth.user) openModal('login');
  state.tab = name;
  // 分析页自己就有一屏的卡片和表格,再顶着一个 66px 的大标题只会把内容
  // 推到折叠线以下。首屏留给时间线,其余标签页直接收起。
  document.body.dataset.tab = name;
  for (const t of document.querySelectorAll('.sd-tabs button')) {
    t.setAttribute('aria-current', t.dataset.tab === name ? 'page' : 'false');
  }
  for (const id of ['timeline', 'dashboard', 'admin']) {
    $('#' + id).classList.toggle('sd-hide', name !== id);
  }
  refresh();
}

for (const tab of document.querySelectorAll('.sd-tabs button')) {
  tab.onclick = () => showTab(tab.dataset.tab);
}
document.querySelector('.sd-console__brand').onclick = (e) => { e.preventDefault(); showTab('timeline'); };

['#q', '#region'].forEach((s) => {
  const n = $(s);
  n.addEventListener(n.tagName === 'INPUT' ? 'input' : 'change', debounce(refresh, 300));
});
function debounce(fn, ms) { let t; return () => { clearTimeout(t); t = setTimeout(fn, ms); }; }
// 自动刷新恒开(开关已随读者界面大扫除移除):每 60 秒一轮。
state.timer = setInterval(refresh, 60_000);

// 筛选项来自 /api/filters：登录墙后面的是分析数据，不是「有哪些角度」。
// 放在身份确认之后再拉 —— 整站登录模式下它和时间线一样要账号。
/** 分类模块条:每格 = 色块 + 中文分类 + 今日条数,点击即筛(再点或点「全部」退出)。
 *  这同时就是给读者的「今天各分类收录了多少」概览,次日随日期窗口自动清零。 */
function renderGenreBar(f) {
  const bar = $('#genrebar');
  bar.textContent = '';
  const today = new Map((f.todayGenres || []).map((g) => [g.genre, g.n]));
  const mk = (slug, label, count, color) => {
    const b = el('button', `sd-genre-pill${state.genre === slug ? ' is-on' : ''}`);
    if (color) { const sq = el('i'); sq.style.background = color; b.append(sq); }
    b.append(document.createTextNode(label));
    if (count > 0) b.append(el('em', null, n2s(count)));
    b.onclick = () => { state.genre = state.genre === slug ? '' : slug; renderGenreBar(f); refresh(); };
    return b;
  };
  bar.append(mk('', '今日全部', f.todayTotal || 0, null));
  for (const g of f.genres || []) {
    const meta = GENRE_META[g.genre];
    if (meta) bar.append(mk(g.genre, meta[0], today.get(g.genre) || 0, meta[1]));
  }
  state.todayTotal = f.todayTotal || 0;
  // 时间线常先于 filters 渲染完(本地秒开后更是必然)——计数到位后
  // 把头部状态行补上,别让「今日收录 0 条」挂在页面上。
  if (state.items.length) {
    $('#status').textContent = `今日收录 ${n2s(state.todayTotal)} 条 · 更新于 ${fmt.format(Date.now())}`;
  }
}

let lastFilters = null;
let filtersAt = 0;
function loadFilters() {
  // 今日计数一分钟一刷就够 —— 别让每次点分类都多背一个跨洋请求。
  if (lastFilters && Date.now() - filtersAt < 55_000) return Promise.resolve();
  return getJson('/api/filters').then((f) => {
    lastFilters = f;
    filtersAt = Date.now();
    renderGenreBar(f);
  }).catch(() => { /* filters stay empty until there is data */ });
}

// Show the running commit next to the title: a stale browser cache or an
// un-pulled checkout is otherwise invisible and wastes a debugging round.
getJson('/api/version').then((v) => {
  const tag = $('#build');
  tag.textContent = v.commit;
  tag.title = `运行中的提交 ${v.commit}${v.date ? ' · ' + new Date(v.date).toLocaleString() : ''}`;
  // commit 哈希是给排查缓存/部署的人看的,读者看到只会困惑 —— 管理员才显示。
  tag.hidden = !auth.user?.is_staff;
  onAuthChange((a) => { tag.hidden = !a.user?.is_staff; });
}).catch(() => {});

async function runTranslate() {
  $('#status').textContent = '补译中…';
  try {
    const r = await post('/api/translate');
    $('#status').textContent = `补译 ${r.done} 条 · 剩余 ${r.pending}`;
    if (state.tab === 'timeline') await loadTimeline();
  } catch (e) { $('#status').textContent = '补译失败 · ' + e.message; }
}

// 先确认身份，再画第一屏。反过来（先画再问）在整站登录模式下会先打一个
// 注定 401 的 /api/timeline，用户看到的第一眼是「加载失败」而不是登录框。
let known;
initAuth({ onTab: showTab, onTranslate: runTranslate }).then(() => {
  // 整站登录模式下，第一屏除了登录没有别的可做 —— 直接把登录框摆出来。
  if (auth.requireLogin && !auth.user) openModal('login');
  // 身份变了（登录/退出/会话过期）就重画一次：管理员标签页要显示或隐藏，
  // 停在管理页面时退出登录必须马上退回时间线。
  onAuthChange((a) => {
    // requireLogin 也进这个 key：未登录时 user.id 恒为 null，只看 id 的话
    // 「公开」和「整站登录」两种未登录状态分不出来。
    const now = `${a.user?.id ?? ''}|${a.requireLogin}`;
    if (known === now) return;
    known = now;
    if (!a.requireLogin || a.user) loadFilters();
    if (STAFF_TABS.has(state.tab) && !a.user?.is_staff) showTab('timeline');
    else refresh();
  });
});
