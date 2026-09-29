# 系统检查 3 · inews.today：设计、爬取进度、展现端（2026-09-29）

> 检查记录，不是规范。inews 跑在 AWS 容器 `inresearch-host-inews-1`（`/srv/inews-data`），采集量、失败率、聚簇质量、限速的**数字都要实机跑**，本文只给命令与判据，不填猜测值。外部仓库只引用路径与结论：`niuroumiantt/inews.today` 的 `README.md`、`docs/select-then-translate.md`、`docs/display-angles.md`、`docs/datacenter-feed.md`、`docs/translation-backends.md`、`src/scheduler.js`、`src/event-aggregation-job.js`、`src/lib/{datacenter-feed,event-types,selection,translate,fetcher,lane-policy,db}.js`、`src/config/angles.json`、`Dockerfile`；本仓库 `src/inresearch/adapters/news_sync.py`、`adapters/acquisition.py`、`knowledge/news_policy.py`、`web/components/datacenter-news.js`、`deploy/spark-reader/inresearch-news.*`。涉及 inresearch 的评价只回到第④问"数据从哪来、缺什么"。

## 一、现状

### 1. 设计：采集线 / 编辑线

| 项 | 现状 | 依据 |
|---|---|---|
| 分离方式 | **逻辑分离，进程与预算不分离。** 采集线 = `scheduler.js runCycle`（分片轮询 → 入库 → 相关性 / 价值闸 → 事件类型 / 角度 / 层标签 → `/api/feeds/datacenter`）；编辑线 = `event-aggregation-job.js`（每 5 分钟 `aggregateEvents` 聚簇 + `runSelection` 按角度配额选题）。但 `translatePending`、`classifyPending`（价值 LLM 精化）、`mergeTranslatedPending` 三个花模型的步骤仍在采集线的 `runCycle` 里按周期预算跑（`scheduler.js:195,205,214`），不是编辑线触发。 | inews `src/scheduler.js`、`src/event-aggregation-job.js` |
| 翻译门 | "挑选在先、翻译在后"落实在 `translatePending` 的选行条件（只收精选故事及其同题 ≤ 6 条、最近 7 天、未下架），批 20 条（`INEWS_TRANSLATION_BATCH_SIZE`），失败回落逐条。 | `docs/select-then-translate.md`「翻译的位置」、`translate.js:535,776` |
| 选题 | `angles.json` 试行：13 个展示角度，配额 300/天（数据中心 180、AI 120），每 6 小时匀速上限 ⌈配额/4⌉+1，候选窗 12 h，静置 15 min，36 h 内同题跳过；质量分 = 价值档 × 15 + 来源等级分 + 6·log2(独立来源数) + 编辑引用 8 − 0.5·小时。`_status: trial`。 | `src/config/angles.json`、`docs/display-angles.md` §3–§5 |
| 未收口 | 选题结果没有同步到 Mac mini 的 Python 原文库采集器（全文翻译仍按原文库自己的规则）；角度与配额待观察后定稿。 | `docs/select-then-translate.md`「待定」 |

### 2. 给 inresearch 的 feed v2 与 `news_sync` 校验

| 字段 | inews 侧 | `news_sync.py` 校验 | 透传 |
|---|---|---|---|
| `event_type` | 10 类之一或 null，标题规则 | ∈ `EVENT_TYPES`（10 个同名常量） | ✓ |
| `research_angle` | 9 个 | ∈ `RESEARCH_ANGLES` | ✓ |
| `layer_tags` | 事件类型 → 层（1–5） | list，≤5，1..5，去重 | ✓ |
| `origin_pointer` | 仅当链接本身是通稿 / 监管 / IR 原文 | 公网 http(s) URL、无用户信息 | ✓ |
| `editorial_pick` | 簇被选中或旧批准页批准且未撤 | bool | ✓ |
| 基本字段 | id / title / title_zh / url / domain / publisher / published_at / cluster_id / topics(7 类) | 完整校验（ID、URL、时间在窗内、topics 词形） | ✓ |

结论：**feed v2 的五个附加字段被完整校验并透传**（`FEED_V2_FIELDS` 与 `collectionTags` 一一对应）。缺的不是校验，是字段：feed 里没有骨架挂点（`object_ids` / `part_id` / `site_right_id` / `target_id`），也没有簇级信息（展示角度、报道家数、来源等级分布只在 `news_events`）。窗口规则：`hours ≤ 168`、`until` 必须在最近 24 h 内、游标不能放宽窗；`news_sync` 每小时拉最近 7 天 100 页封顶。Spark `inresearch-news.timer` 每小时一次，一次失败不会丢数据，连续 7 天失败才会漏。

### 3. 爬取面与限速（仓库登记值，实机数见 §三）

| 项 | 登记值 | 依据 |
|---|---|---|
| 来源数 | Google News 分片 119（上限 135）、直连 RSS/Atom 74、页面监测 10、原文库全文站 19（Mac mini，Python 链路） | `docs/display-angles.md` §1 |
| 车道 | hot 10 每 60 s 全量；warm 每轮 10、cold 每轮 5；按实测产出自动升降档，`test/keywords.test.js` 守冷圈 ≤ 45 min、温圈 ≤ 15 min | `README.md`「车道会自己进化」 |
| 限速 | `BucketPool`：Google News 主桶 capacity 8 / 0.6 s（约 36 次/分）AIMD；其他主机各 capacity 2 / 0.2 s；并发 3；ETag 条件请求；单分片退避 30 s → 30 min | `src/lib/fetcher.js:17–94` |
| 量级 | 文档估算：每天约 3,200 条标题入库、机器初选约 700 故事、编辑线目标 300 | `docs/display-angles.md` §1 |
| 去重 / 聚簇 | 标题归一化 + 36 h 窗同 key 为同簇，`cluster_id` = 簇内最早文章；`news_events` 按簇聚合报道家数、来源数、等级分布 | `README.md`「域名评分」、`event-aggregation.js` |
| 来源健康 | `source-health.js`：采集尝试 / 成功 / 解析失败 / HTTP 错误计数，评估状态 new → healthy / warning / critical / retired，有 `/api/sources/health` | `docs/source-health-monitoring.md` |

### 4. 翻译策略与成本

- 后端链 `translation-backends.json`（顺序即优先级）；默认 Spark Ollama `qwen3.8:27b` 经 tailnet `100.100.1.2:11434`；可选付费兜底（OpenAI 兼容，四个 `INEWS_TRANSLATION_FALLBACK_*` 都填才生效，只用于标题）；本地单条超时 20 s 转兜底。是否配置了兜底、兜底占比：**未核实**。
- 只译精选：上限约 300 故事/天 × 每故事 ≤ 6 同题，标题级；Spark 本地推理不计 token 费，成本是 Spark 占用（与 reader 争 GPU）。付费兜底按 token，只在 Spark 掉线时产生。
- 数字一致性检查默认关；旧译文保留标 `legacy:*` 不重译。

### 5. 展现端

| 端 | 现状 | 依据 |
|---|---|---|
| inews.today 站点 | 单条时间流（`view=selected`），按故事最新动态倒序；左栏按角度筛不分栏；管理员另有原文库、分析、系统页；`web/app.js` 约 44 KB + 页面脚本 | `docs/display-angles.md` §5、`web/app.js:118` |
| inresearch 首屏新闻区 | `datacenter-news.js` 每 60 s 拉 `/api/news`，只渲染 `title_zh` 非空的条目（= 编辑线精选），按北京时间分日；数据路径：inews（AWS）→ Spark `news-sync`（每小时）→ Spark `publish`（每 5 分钟）→ AWS 快照 → 首屏。同一台 AWS 上的两个容器绕一圈家里的 Spark，最坏延迟约 65 分钟；Spark 掉线首屏显示"更新延迟 / 尚未连接阅读服务"。 | `web/components/datacenter-news.js`、`deploy/spark-reader/inresearch-news.timer`、`inresearch-reader-publish.timer` |

## 二、问题与优化清单（按影响 / 成本）

先说第④问的结论：**目标表 50 行 inews 任务（39 条部件 news 行 + 11 条权利 holders 行）今天 0 行 delivered，而且没有一条路能让它非零**——feed 没有挂点字段，本仓库没有 `event_cards.json` 的写入者（详见 skeleton 报告 S7）。inews 已经把"事件类型 → 层 → 原件归属队"登记得很清楚（`event-types.js EVENT_LAYERS / EVENT_OWNER`），差的是最后一跳。

| 序 | 影响/成本 | 问题 | 建议 | 落点 |
|---|---|---|---|---|
| 1 | 高 / 中 | feed 没有骨架挂点，事件进不了目标行 | feed v2 加 `object_ids`（骨架 ID，用 inresearch 公开的 `bom.json` 别名表 + 公司词典；schema_version 仍为 1，只增不改）；本仓库 `news_sync.validate_v2_fields` 加校验（⊂ 现行骨架 ID）；再由作者侧导入命令生成事件卡。 | inews `datacenter-feed.js collectionTags`、`event-types.js`；本仓库 `news_sync.py`、`targets.py` |
| 2 | 高 / 低 | `origin_pointer` 命中率未知 | 先跑 §三 的 feed 抽样命令；若非空率很低，把"链接本身是原文"的判定扩到已知 IR / 监管 / 通稿域名白名单（`source-routes.js` 已有域名路由）。目标行 news 类的 delivered 判据就是它。 | inews `event-types.js` |
| 3 | 中 / 低 | 翻译 / 价值精化仍在采集循环里跑 | 把 `translatePending` / `classifyPending` / `mergeTranslatedPending` 移到 `event-aggregation-job`（编辑线）里，在 `runSelection` 之后按精选行跑；采集线只留不花模型的步骤。两条线的模型预算与节奏才真正分开。 | inews `scheduler.js:195–214` → `event-aggregation-job.js` |
| 4 | 中 / 低 | inresearch 首屏新闻绕 Spark 一圈 | 两种选法：(a) 保持"新闻是 Spark 台账的投影"的原则，但把 `inresearch-news.timer` 从 1 h 缩到 15 min（feed 有 ETag 与游标，成本低）；(b) AWS 容器直接拉同机 inews 的 feed 做首屏"最新线索"（不进台账、只显示），台账仍走 Spark。建议 (a)，不破坏"AWS 不采集"的边界。 | 本仓库 `deploy/spark-reader/inresearch-news.timer` |
| 5 | 中 / 低 | 首屏只显示有中文标题的条目 | 与"给 inresearch 默认不翻译"一致，但读者只看到精选（≤ 180 条/天数据中心组），首屏没有说明"只显示编辑精选"。加一行文案，并给未翻译条目一个"原文"折叠入口（可选）。 | 本仓库 `datacenter-news.js` |
| 6 | 中 / 中 | 选题结果未同步到 Mac mini 原文库 | inews 文档已列为下一步；实现前先决定原文库全文翻译是否也只收精选（省 Spark GPU）。 | inews Python 链路 `inews/` |
| 7 | 低 / 低 | inews.today 时间流页 44 KB 脚本 | 首屏先渲染近 24 h 精选，按角度懒加载；`/api/version` 已不受门控可做缓存失效。 | inews `web/app.js` |
| 8 | 低 / 低 | 角度与配额 `trial` | 观察窗到期后把 `_status` 改 `adopted` 并到 inresearch 06 登记（inews 文档已写）。 | `angles.json`；本仓库 06 |
| 9 | 低 / 低 | `topics` 7 类与骨架不对应 | 保留（它是 inews 自己的分类），骨架挂点走 `object_ids`；不要再造第三套分类。 | — |

## 三、需要在实机跑的统计（AWS `ubuntu@ip-172-26-11-47`）

数据库：`/srv/inews-data/inews.sqlite3`（README「持久化数据库的正式命名」；infra `backup-app.py` 仍写旧名 `news.db`，以实机 `ls` 为准）。用只读方式打开，不装任何包。列名以 inews `src/lib/db.js` 为准，若报"no such column"按该文件改。

```bash
hostname; test "$(hostname)" = ip-172-26-11-47 && echo host-ok
sudo ls -la /srv/inews-data/ | grep -E 'sqlite3|\.db$'
sudo docker exec inresearch-host-inews-1 curl -fsS http://127.0.0.1:8789/api/version
DB=/srv/inews-data/inews.sqlite3
sudo python3 - "$DB" <<'PY'
import sqlite3,sys,json,time
db=sqlite3.connect(f"file:{sys.argv[1]}?mode=ro",uri=True); q=lambda s,*a:db.execute(s,a).fetchall()
now=int(time.time()*1000); d=86400000
print("来源数 · 分片按车道:", q("SELECT lane,COUNT(*) FROM shard_policy GROUP BY lane"))
print("来源数 · 域名按状态:", q("SELECT COALESCE(status,'observing'),COUNT(*) FROM domains GROUP BY 1"))
print("来源健康 · 评估状态:", q("SELECT COALESCE(assessment_status,'new'),COUNT(*) FROM domains GROUP BY 1"))
print("每日入库 / 相关 / 价值≥2（近 7 天，按首次见到）:")
for r in q("SELECT date(first_seen_at/1000,'unixepoch'),COUNT(*),SUM(relevant),SUM(CASE WHEN value>=2 THEN 1 ELSE 0 END) FROM articles WHERE first_seen_at>=? GROUP BY 1 ORDER BY 1",now-7*d): print("  ",r)
print("失败率 · 近 24 h 拉取:", q("SELECT COUNT(*),SUM(CASE WHEN error IS NOT NULL OR status>=400 THEN 1 ELSE 0 END),SUM(CASE WHEN status=304 THEN 1 ELSE 0 END) FROM fetches WHERE started_at>=?",now-d))
print("失败最多的分片（近 24 h）:", q("SELECT shard,COUNT(*) FROM fetches WHERE started_at>=? AND (error IS NOT NULL OR status>=400) GROUP BY shard ORDER BY 2 DESC LIMIT 10",now-d))
print("限速 · 近 1 h 对 Google News 的请求数（应 ≤ 36/分 × 60）:", q("SELECT COUNT(*) FROM fetches WHERE started_at>=? AND shard NOT LIKE 'direct:%'",now-3600000))
print("去重 · 近 7 天转载占比:", q("SELECT COUNT(*),SUM(CASE WHEN is_original=0 THEN 1 ELSE 0 END) FROM articles WHERE first_seen_at>=?",now-7*d))
print("聚簇 · 近 7 天簇数与平均簇大小:", q("SELECT COUNT(DISTINCT COALESCE(cluster_id,id)), 1.0*COUNT(*)/COUNT(DISTINCT COALESCE(cluster_id,id)) FROM articles WHERE first_seen_at>=? AND relevant=1",now-7*d))
print("编辑线 · 近 24 h 选题状态:", q("SELECT COALESCE(selection_status,'-'),COUNT(*) FROM news_events WHERE last_updated>=? GROUP BY 1",now-d))
print("编辑线 · 近 24 h 按展示角度:", q("SELECT display_angle,COUNT(*) FROM news_events WHERE selection_status='selected' AND last_updated>=? GROUP BY 1 ORDER BY 2 DESC",now-d))
print("翻译 · 近 24 h 按后端:", q("SELECT provider,COUNT(*) FROM translations WHERE at>=? GROUP BY 1",now-d))
print("翻译 · 精选中仍无中文标题:", q("SELECT COUNT(*) FROM articles a JOIN news_events e ON e.cluster_id=COALESCE(a.cluster_id,a.id) WHERE e.selection_status='selected' AND e.last_updated>=? AND (a.title_zh IS NULL OR a.title_zh='')",now-d))
PY
```

feed v2 字段命中率（第④问最关心的两个数）：

```bash
curl -s 'https://inews.today/api/feeds/datacenter?hours=168&limit=100' | python3 -c "
import json,sys,collections;p=json.load(sys.stdin);it=p['items']
print('条数',len(it),'next_cursor',bool(p.get('next_cursor')))
print('event_type 非空',sum(1 for i in it if i.get('event_type')),collections.Counter(i.get('event_type') for i in it).most_common(6))
print('origin_pointer 非空',sum(1 for i in it if i.get('origin_pointer')))
print('editorial_pick',sum(1 for i in it if i.get('editorial_pick')))
print('layer_tags 分布',collections.Counter(l for i in it for l in (i.get('layer_tags') or [])))"
```

翻译兜底是否配置（只看变量名是否存在，不打印值）：

```bash
sudo grep -cE '^INEWS_TRANSLATION_FALLBACK_(PROVIDER|URL|KEY|MODEL)=.' /srv/host/inresearch-host/.env.inews
sudo docker exec inresearch-host-inews-1 sh -c 'test -f translation-backends.json && echo backends-file-present || echo default-chain'
```

**Spark `spark@dgx`**（inresearch 消费端）：

```bash
hostname; test "$(hostname)" = dgx && echo host-ok
systemctl --user list-timers --no-pager | grep inresearch-news
journalctl --user -u inresearch-news.service -n 5 --no-pager
cat ~/.local/share/inresearch.ai/acquisition/news-window.json
```

## 四、结论一句

两条线的思路与字段设计是对的，校验也是完整的；差的是把事件挂到骨架的一个字段和把回执写回 Git 的一条通道。没有这两样，inews 对第④问的贡献停在"线索可见"，进不了"目标行已交付"。
