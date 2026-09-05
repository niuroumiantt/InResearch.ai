// 从配置生成 SOURCES.md —— 文档永远和代码一致,改完词表跑一遍即刷新:
//   node scripts/gen-sources.js
// 理念承自 niuroumiantt/news 的 gen_sources_doc.py:配置是真源,文档是产出。
import { writeFileSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';
import { GROUPS, LOCALES, buildShards } from '../src/config/keywords.js';
import { CONFIG } from '../src/scheduler.js';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const FEEDS = JSON.parse(readFileSync(join(ROOT, 'src/config/feeds.json'), 'utf8'));
const WATCHES = JSON.parse(readFileSync(join(ROOT, 'src/config/watches.json'), 'utf8'));

let commit = 'unknown';
try { commit = execSync('git rev-parse --short HEAD', { cwd: ROOT }).toString().trim(); } catch {}

const shards = buildShards();
const gnShards = shards.filter((s) => !s.feedUrl && !s.watchUrl);
const laneCount = shards.reduce((a, s) => { a[s.lane] = (a[s.lane] || 0) + 1; return a; }, {});
const perCycle = (laneCount.hot || 0) + CONFIG.warmPerCycle + CONFIG.coldPerCycle;

const ANGLE_ZH = {
  models: '大模型', chips: '芯片与硬件', infra: '算力基建', money: '资本',
  policy: '政策监管', safety: '安全风险', apps: '应用落地', research: '研究评测',
  people: '人物动向', region: '区域',
};

let md = `# 信息源清单 (SOURCES)

> 本文档由 \`scripts/gen-sources.js\` 从 \`src/config/{keywords.js, feeds.json, watches.json}\` 自动生成。
> 生成时 commit: \`${commit}\` · 生成时间: ${new Date().toISOString().slice(0, 16)}Z。
> **改配置后跑 \`node scripts/gen-sources.js\` 刷新本文档,不要手改。**

## 一、系统一页图:三通道采集

\`\`\`
 ①关键词查询(Google News)   ②直连/编辑源(RSS/HTML)  ③页面监控(links)
    ${String(gnShards.length).padStart(3)} 个查询 shard            ${String(FEEDS.length).padStart(3)} 路                  ${String(WATCHES.length).padStart(2)} 页
        └───────────────┬──────────────┴───────────────┬───────┘
                        ▼   统一车道轮询(热/温/冷,产出实测自动升降)
                  相关性闸门(词表打分 ≥3 上时间线;②③带来源先验 boost)
                        ▼
                  标题聚类去重(36h 同题归并,最早者记「首发」)
                        ▼
                  价值轴 0-3 分(规则粗判+LLM 精化;时间线默认只显示 ≥2)
                        ▼
                  LLM 翻译(保留品牌/人名) → 时间线
\`\`\`

三通道各管一件事:**①管广度** —— GN 索引的全部媒体,查询词决定照到哪里;
**②管一手与编辑认证** —— 官方博客/监管机构/顶级专栏绕过 GN 延迟，Techmeme
River/RSS 则保留其编辑选题事实，但原文发布者仍是下游域名;
**③管死角** —— 没有 RSS 的源(工信部/NIST/欧盟 AI Office),抓页面取链接增量当新文章。

## 二、调度与预算

| 参数 | 值 | 说明 |
|---|---|---|
| shard 总数 | ${shards.length} | ①${gnShards.length} + ②${FEEDS.length} + ③${WATCHES.length},同一套轮询 |
| 车道分布 | 热 ${laneCount.hot || 0} / 温 ${laneCount.warm || 0} / 冷 ${laneCount.cold || 0} | 初始车道只是猜测,产出实测自动升降(policy.js) |
| 节奏 | 一轮 ${CONFIG.cycleMs / 1000}s:热全发+温${CONFIG.warmPerCycle}+冷${CONFIG.coldPerCycle} ≈ ${perCycle} 请求/分 | 令牌桶硬上限 36/分;被限流自动减半再爬升 |
| 轮转周期 | 热每轮 · 温约 ${Math.ceil((laneCount.warm || 0) / CONFIG.warmPerCycle)} 分一圈 · 冷约 ${Math.ceil((laneCount.cold || 0) / CONFIG.coldPerCycle)} 分一圈 | ETag/304 条件请求;失败单 shard 指数退避 |
| 时间语义 | GN 查询带 \`when:${CONFIG.window}\`;feed 只收近 14 天;Techmeme 记其入选时间;监控页记首见时刻 | 36h 是聚类归并窗,另一个概念 |

**入库闸门**(所有通道同一条流水线):相关性词表(relevance.js:强词+4/实体+3/
上下文+1/黑名单−6,≥3 上时间线) → 聚类去重 → 价值轴 0-3(value.js 规则 +
classify.js LLM 精化,默认展示 ≥2) → LLM 翻译。通道②③每路带来源先验(boost):
纯 AI 官方源 +3 直通;全公司/全机构宽口源 +0~2,必须再命中词法信号才过线 ——
防「微软换 HR」蹭官方通道。Techmeme 不靠 boost 放行，而走单独的严格 AI 合同：
只收核心模型、实质事件和 AI 基建/供应链，硬拒证券行情、消费硬件、个人社交与口水。

## 三、语区(Google News)

| id | hl | gl | ceid | lang |
|---|---|---|---|---|
`;
for (const l of LOCALES) md += `| ${l.id} | ${l.hl} | ${l.gl} | ${l.ceid} | ${l.lang} |\n`;

md += `\n## 四、通道①:关键词查询(按角度)\n
通用查询在所属语区各查一次;本地组只在对应语区查。初始车道是猜测,实测产出会调。\n`;
const byAngle = new Map();
for (const g of GROUPS) {
  if (!byAngle.has(g.angle)) byAngle.set(g.angle, []);
  byAngle.get(g.angle).push(g);
}
for (const [angle, groups] of byAngle) {
  md += `\n### ${ANGLE_ZH[angle] || angle} (\`${angle}\`)\n\n| 组 | 初始车道 | 语区 | 查询 |\n|---|---|---|---|\n`;
  for (const g of groups) {
    for (const q of g.queries) {
      md += `| \`${g.id}\` | ${g.lane} | ${g.locales.join(' ')} | \`${q.replace(/\|/g, '\\|')}\` |\n`;
    }
  }
}

md += `\n## 五、通道②:直连与编辑源(${FEEDS.length} 路)\n
每路源即一个 shard,复用车道轮询与产出调档。RSS/Atom 是常规格式；Techmeme
用 RSS 做最新增量、River HTML 做约五日回填，以同一个 pml 去重。通过严格 AI
门槛的标题、原文链接、域名和入选时间另存为编辑认证，不把 Techmeme 冒充发布者。\n`;
// 按 boost 分三组展示 —— boost 3=一手直通,1~2=宽口过滤,0=大流量纯词法。
for (const [title, min, max] of [['一手直通(boost 3)', 3, 3], ['宽口过滤(boost 1~2)', 1, 2], ['大流量纯词法(boost 0)', 0, 0]]) {
  const rows = FEEDS.filter((f) => (f.boost ?? 3) >= min && (f.boost ?? 3) <= max);
  if (!rows.length) continue;
  md += `\n### ${title} · ${rows.length} 路\n\n| id | 域名 | 格式 | 角度 | 车道 | 说明 |\n|---|---|---|---|---|---|\n`;
  for (const f of rows) md += `| \`${f.id}\` | ${f.domain} | ${f.format || 'rss'} | ${f.angle} | ${f.lane} | ${f.why || ''} |\n`;
}

md += `\n## 六、通道③:页面监控(links 模式,${WATCHES.length} 页)\n
没有 RSS 的源:定期抓页面 HTML,提取链接列表,**新出现的链接=新文章**
(标题取锚文本,发布时间记首见时刻)。首轮只建基线不入库;单轮新增超过 30 条
视为页面改版,只更新基线 —— 宁可漏过,不灌错。全部冷车道。

| id | 页面 | 角度 | boost | 说明 |
|---|---|---|---|---|
`;
for (const w of WATCHES) {
  md += `| \`${w.id}\` | ${w.url.replace(/^https?:\/\//, '').slice(0, 48)} | ${w.angle} | ${w.boost ?? 2} | ${w.why || ''} |\n`;
}

md += `\n## 七、已知盲区与后备

- **Anthropic 无公开 RSS**(官网不提供)—— 靠 GN 关键词/转载覆盖;news 仓库
  的原方案是自建 RSSHub 桥抓 X@AnthropicAI,服务器装 RSSHub 后可加回
- **X/推特与微信公众号**(16 路)需要自建 RSSHub 实例(127.0.0.1),暂不可导
- **SEC EDGAR**(13 路 8-K/6-K)要求自报式 User-Agent,待 fetch 层支持后导入
- **YouTube 频道**(5 路)与 arXiv API 信号形态不同,暂缓
- **Techmeme AI Topic Leaderboard** 的公开付费预览只有无链接占位文本，不能当
  真实域名/标题摄取；拿到官方购买的 HTML/PDF 后再接入。免费 OpenAI 样例只可作
  窄域来源发现，不能替代广义 AI 新闻流
- 域名先验库 326 条见 \`src/config/sources.seed.json\`(与 niuroumiantt/news 同源);
  静音黑名单见 \`src/config/muted-domains.json\`;域名审核在分析页②区一键处置
`;

writeFileSync(join(ROOT, 'SOURCES.md'), md);
console.log(`SOURCES.md 已生成: ①${GROUPS.length} 组/${gnShards.length} GN shard + ②${FEEDS.length} feed + ③${WATCHES.length} watch = ${shards.length} shard`);
