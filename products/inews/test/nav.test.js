// 导航的用例。
//
// 2026-08-24 站长:两个入口(inews.today 的时间线、/rawarticle/ 的私站原文库)
// 要能互相跳。原文库按来源分开,页眉要给每一份
// 一条直达的路 —— 「我有 10 个页面,每个页面都要找到最优路径」。
// 登录:/rawarticle/* 由本站自己的 requireStaff 拦(test/rawarticle.test.js);本站时间线的
// 鉴权在本项目里(见 README「认证归本项目」)—— 两条路各自有门,都走得通。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('../web/index.html', import.meta.url), 'utf8');
const app = readFileSync(new URL('../web/app.js', import.meta.url), 'utf8');
const nav = html.slice(html.indexOf('<nav class="sd-tabs"'), html.indexOf('</nav>'));

test('导航里六个原文库各有一条直达的路', () => {
  assert.match(nav, /<a[^>]+href="\/rawarticle\/ft\/index\.html"/, '要有去 FT 库的链接');
  assert.match(nav, /<a[^>]+href="\/rawarticle\/bloomberg\/index\.html"/, '要有去 Bloomberg 库的链接');
  assert.match(nav, /<a[^>]+href="\/rawarticle\/cnbc\/index\.html"/, '要有去 CNBC 库的链接');
  assert.match(nav, /<a[^>]+href="\/rawarticle\/wsj\/index\.html"/, '要有去 WSJ 库的链接');
  assert.match(nav, /<a[^>]+href="\/rawarticle\/reuters\/index\.html"/, '要有去 Reuters 库的链接');
  assert.match(nav, /<a[^>]+href="\/rawarticle\/axios\/index\.html"/, '要有去 Axios 库的链接');
  assert.match(nav, /原文库/);
});

test('原文库暂时不对外:入口只有登录后的 staff 看得到', () => {
  // 9-02 站长:「让这些文章暂时不对外,对外的只有快讯」。页面本身由本站
  // requireStaff 拦住(没登录打不开),这里再把**入口**也收进登录可见 ——
  // 和「分析」「账号」同一套 data-staff 机制,auth.js 按角色统一开关。
  for (const m of nav.matchAll(/<a[^>]+rawarticle[^>]*>/g)) {
    assert.match(m[0], /data-staff/, `原文库入口要挂 data-staff:${m[0]}`);
    assert.match(m[0], /\bhidden\b/, `原文库入口默认要 hidden:${m[0]}`);
  }
  assert.ok([...nav.matchAll(/<a[^>]+rawarticle[^>]*index\.html[^>]*>/g)].length === 6,
    '六条来源入口都还得在');
});

test('原文库是链接不是页签按钮', () => {
  // 站内页签是 button(单页切换),原文库是**另一份静态产出**,只能用 a 跳过去。
  // 写成 button 的话 app.js 那个循环会把它当成一个不存在的面板去切,点了没反应。
  assert.doesNotMatch(nav, /<button[^>]*rawarticle/);
});

test('六个独立原文库共用一个 Dashboard', () => {
  // 清单与正文按来源分开，跨库总量、覆盖率、失败、积压和运行时间只维护一份。
  assert.match(html, /href="\/rawarticle\/dashboard\/"/);
  assert.doesNotMatch(html,
    /href="\/rawarticle\/(?:ft|bloomberg|cnbc|wsj|reuters|axios)\/dashboard\.html"/);
});

test('Techmeme 已建域名显示逐站确认的 A/B 路线', () => {
  const expected = new Map([
    ['ft.com', 'A'],
    ['bloomberg.com', 'B'],
    ['cnbc.com', 'B'],
    ['wsj.com', 'B'],
    ['reuters.com', 'B'],
    ['axios.com', 'A'],
  ]);
  for (const [domain, route] of expected) {
    const escaped = domain.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    assert.match(app, new RegExp(`\\['${escaped}',\\s*'${route} · 已建'\\]`),
      `${domain} 应显示 ${route} 路线已建`);
  }
  assert.match(app, /replace\(\/\^www\\\.\//, 'www 子域应归一到同一条路线');
});
