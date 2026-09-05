# inews.today

一个仓库承载完整的 AI 新闻产品：公开时间线、账号与分析后台，以及 FT / Bloomberg /
CNBC / WSJ / Reuters / Axios 六个独立原文库。公开聚合服务使用 Node.js，私有原文
采集器使用 Python。FT、Bloomberg、WSJ、Reuters 与 Axios 的动态发现页由 Mac mini
上的专用可见 Chrome 串行打开；CNBC 使用公开的无头通道。两条链路共享产品导航与
Signal Desk 设计语言，但运行状态彼此隔离。

## 一套仓库，两条采集链路

| 能力 | 入口 | 数据 | 页面 |
| --- | --- | --- | --- |
| 公开新闻时间线 | `npm start` / `npm run collect` | `data/inews.sqlite3` | `/`、Dashboard、规则演化、账号 |
| 私有原文库 | `npm run subscriptions -- …` | `out/<SITE>/data/` | `/rawarticle/<site>/` 独立清单与正文 |
| 原文库统一后台 | 随任一来源自动重画 | 只读各库台账，不新增状态 | `/rawarticle/dashboard/` |

首次启用私有原文采集器：

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
npm run subscriptions -- --group all --pages 5 --limit 20
```

完整回归测试使用 `npm run test:all`。私有原文采集、数据布局、运行保护和发布方式见
[`docs/subscription-archive.md`](docs/subscription-archive.md)。

### 六个原文来源

| 来源 | 发现路线 | 私有清单 | 正文页 | 浏览器档位 |
| --- | --- | --- | --- | --- |
| FT | A：按已审关键词搜索 | `/rawarticle/ft/index.html` | `/rawarticle/ft/p/<年月>/<uuid>.html` | 专用可见 Chrome；正文使用站长登录态 |
| Bloomberg | B：官方 AI 专题 | `/rawarticle/bloomberg/index.html` | `/rawarticle/bloomberg/p/<年月>/<日期-slug>.html` | 专用可见 Chrome；正文使用站长登录态 |
| CNBC | B：官方 AI 专题，展开 Load More | `/rawarticle/cnbc/index.html` | `/rawarticle/cnbc/p/<年月>/<日期-slug>.html` | 公开直抓，失败时只用无头 Chromium |
| WSJ | B：官方 AI 专题 | `/rawarticle/wsj/index.html` | `/rawarticle/wsj/p/<年月>/<article_id>.html` | 专用可见 Chrome；正文使用站长登录态 |
| Reuters | B：官方 Artificial Intelligence 专题，展开 Load More | `/rawarticle/reuters/index.html` | `/rawarticle/reuters/p/<年月>/<日期-slug>.html` | 专用可见 Chrome；用于通过列表页的 DataDome 挑战 |
| Axios | A：固定搜索 `artificial intelligence` 并选 Latest，展开 Show 10 more results | `/rawarticle/axios/index.html` | `/rawarticle/axios/p/<年月>/<日期-slug>.html` | 专用可见 Chrome；用于通过搜索页的 Cloudflare 验证 |

“可见”是有意的运行契约：自动任务只使用带哨兵页的专用 Chrome 窗口，并由共享
`daily_chrome` 资源锁保证同一时间只有一个来源占用它，不会把失败的无头请求偷偷
回落到站长正在浏览的窗口。Reuters 与 Axios 的正文是公开稿，但它们的发现页仍需
这个通道；CNBC 则不会弹出窗口。

AI 新闻时间线以 Google News RSS 为抓取面，按**文章真实发布时间**倒序展示，
并在后台持续给来源域名打分。

零依赖：只用 Node 22 内置的 `fetch` / `node:sqlite` / `node:http`。不需要 `npm install`。

```bash
node src/cli.js collect     # 跑一轮采集，看结果
npm start                   # 起服务 + 常驻采集器 → http://localhost:8787
```

## 它怎么满足「准 / 新 / 广」

**广（覆盖面）** — `src/config/keywords.js` 把 AI 拆成 10 个角度
（models / chips / infra / money / policy / safety / apps / research / people / region），
每个角度 × 语言地区（10 个 locale）× 关键词，展开成 **36 个独立 shard**。
加角度或加语言就是往 `GROUPS` 里加一行。

**新（时效）** — 每个查询都带 `when:1h`，Google News 只回最近一小时的条目，
包体小、噪音少。`hot` 车道（模型 / 芯片 / 融资 / 中文大模型，共 8 个 shard）**每 60 秒全量重扫一次**，
所以一条新闻从发布到出现在时间线上通常在 1–2 分钟内。
Dashboard 上的「平均抓取延迟」= `first_seen_at - published_at`，直接量化这个指标。

**准（相关性）** — 两道闸门。第一道是查询本身（英文从不单用裸 `AI`）。
第二道是 `src/lib/relevance.js`：强特征词 +4、实体词 +3、上下文词 +1、
黑名单（Allen Iverson / Air India / 禽流感 / 爱奇艺…）−6。
`score >= 3` 记为相关；0 < score < 3 仍入库但打「低分」标签，切到「全部」可复核，
这样能不断反查漏判、调词表。

## 反爬策略（为什么不是一次性并发全打）

- **分批轮转**：一个 cycle 只发 `hot(8) + warm(4) + cold(1)` ≈ 13 个请求，
  warm 约 4 分钟轮完一圈、cold 约 14 分钟。总请求量 ~13/分钟。
- **全局令牌桶**：`TokenBucket(capacity 8, 0.6/s)`，硬上限 ~36 请求/分钟。
- **并发上限 3** + 每个请求前随机抖动，避免整齐的脉冲流量。
- **条件请求**：存 ETag / Last-Modified，多数轮询拿到 304，零包体。
- **单 shard 退避**：失败后 30s → 60s → 120s…（上限 30 分钟）冷却，只惩罚出问题的那个查询，
  不影响其它 shard。

调参统一使用 `INEWS_*`：`INEWS_COLLECTION_CYCLE_MS`、`INEWS_FETCH_CONCURRENCY`、
`INEWS_WARM_SHARDS_PER_CYCLE`、`INEWS_COLD_SHARDS_PER_CYCLE`、
`INEWS_GOOGLE_NEWS_WINDOW`。翻译看 `INEWS_TRANSLATION_PROVIDER`，账号看
`ADMIN_EMAIL` / `ADMIN_PASSWORD` / `INEWS_REGISTRATION_OPEN` /
`INEWS_REQUIRE_LOGIN` / `INEWS_SECURE_COOKIES` / `SMTP_*`。

未登录账号接口还有一层进程内过载保护，先于 JSON 解析、PBKDF2、发信与 SQLite
写入执行。默认登录为每 IP 30 次/15 分钟、全站 300 次/15 分钟、最多 4 个并发；
验证码为每 IP 10 次/小时、全站 200 次/小时。需要调整时使用
`INEWS_AUTH_PUBLIC_{IP,GLOBAL}_LIMIT`、`INEWS_AUTH_LOGIN_{IP,GLOBAL}_LIMIT`、
`INEWS_AUTH_CODE_{IP,GLOBAL}_LIMIT`。登录后的改密另用
`INEWS_AUTH_PASSWORD_{IP,GLOBAL}_LIMIT`；并发项对应 `*_CONCURRENCY`。这些是防过载
的短期内存闸门；原有按账号/邮箱的 SQLite 限流仍负责跨重启锁定。

### 持久化数据库的正式命名

本项目只有一份应用数据库：默认本机为 `data/inews.sqlite3`，生产容器为
`/data/inews.sqlite3`，宿主机为 `/srv/inews-data/inews.sqlite3`。它同时保存新闻、
抓取观测、译文、用户、会话与审计记录，因此不能再称作 `news.db`，也不能按可丢弃的
新闻缓存对待。自定义路径只用 `INEWS_DB_PATH`。

旧变量 `SINGLETITLE_DB` 仅作为一个发布周期的回滚兼容名；新旧变量同时存在时必须指向
同一个文件，否则应用拒绝启动。旧 `news.db` 改名必须停掉所有写进程，使用 SQLite
一致性备份并校验后再切换，不能在线只移动主文件而漏掉 WAL。

## 车道会自己进化（src/lib/policy.js）

`keywords.js` 里写死的车道**只是初始猜测**。真正决定轮询频率的是**实测产出**：
一次轮询能带回多少条「新的、通过相关性闸门的」文章（`kept/轮`）。

每个 cycle 开始前重算一遍（一条 group by 查询，很便宜），所以突发是下一轮就响应，不是第二天。

| 判据 | 阈值 |
|---|---|
| 观察窗口 | 24 小时 |
| 升 hot | ≥ 1.5 条/轮 |
| 掉出 hot | < 0.8 条/轮 |
| 升 warm | ≥ 0.35 条/轮 |
| 掉到 cold | < 0.12 条/轮 |
| 突发直升 hot | 单轮 ≥ 5 条 |
| 换档冷静期 | 8 轮 |
| 错误率强制降档 | > 50% |

四条防翻车的设计：

1. **迟滞（dead band）**——升档和降档阈值之间留空档。产出稳定在 1.0 条/轮的 shard，
   在 hot 就留在 hot，在 warm 就留在 warm，不会在边界来回抖。
2. **冷静期**——换档后必须再跑满 8 轮才允许再动。
3. **棘轮式升档**——一次只升一档（cold → warm → hot），只有突发才跳级。降档同理一次一档。
4. **cold 是地板**——永远不会有 shard 被完全停掉。AI 政策产出低不代表价值低，
   它只是从「60 秒内看到」变成「最多 14 分钟内看到」，对这类新闻完全够用。
   省下的请求预算自动流向真正在产出的车道。

**「规则演化」标签页**（第三个 tab）就是看这个的：

- 当前每个 shard 在哪条车道、实测产出、跑了多少轮、**为什么是这一档**（一句话理由）
- 7 天调档频率柱图（绿=偏升档、黄=偏降档），一眼看出系统是在收敛还是在抖
- 最近 120 次调档的完整流水：时间 / shard / `warm → hot` / 理由 / 当时的产出
- 阈值本身也显示在页面上
- 不同意机器的判断可以**人工锁定**：点车道名在 热→温→冷→自动 之间切换，
  锁定后（🔒）机器不再动它，锁定动作本身也进演化流水

## 为什么是一个应用，而不是多个应用再 sync

多进程 + 同步会引入一致性、去重竞态和运维成本，而当前瓶颈根本不是 CPU——
是**故意压低的请求速率**。一个进程里的 shard 轮转已经能做到全覆盖 + 分钟级新鲜度。
真要横向扩展，边界已经画好了：`shard` 是天然的分片键，
把 `scheduler.js` 拆成 N 个 worker、各认领一部分 shard、共写同一个 SQLite（WAL）即可，
存储层和去重逻辑一行都不用改。

## 域名评分

Google News 的 `<source url>` 直接给出发布方域名，所以每条新闻都能归属到域名。
`src/config/sources.seed.json`（你给的那份）作为先验注入 `domains.seed_type`。
评分（0–100，`src/lib/domains.js`）：

| 维度 | 分值 | 含义 |
|---|---|---|
| volume | 0–20 | AI 新闻产出量（log） |
| precision | 0–30 | 过相关性闸门的比例 |
| originality | 0–30 | 在同一故事簇里**首发**的比例 |
| speed | 0–10 | 比同簇其它家平均早多少 |
| seed | 0–10 | 先验：primary/wire > platform > relay |

`confidence = min(1, n/20)`：样本不足 20 条时分数只是参考——这正是「先跑一段时间再定论」。
转载识别靠**故事簇**：标题归一化后 36 小时窗口内相同 key 即同一故事，
最早的那条是 original，其余记为转载。relay 站会自然沉底。

## 标题中文化（src/lib/translate.js）

时间线上**所有标题都以中文呈现**：源标题已经是中文的直接用，其余的走机器翻译，
原文降为第二行（勾「显示原文」展开，鼠标悬停也能看到）。机器翻译是线索不是引文，
所以原文永远调得出来 —— 否则一处误译就没法被证伪。

译文按**源文本**缓存（`translations` 表），不是按文章 id：同一条通稿会从二十家聚合站进来，
按文章缓存等于为同一句话付二十次钱。

`INEWS_TRANSLATION_PROVIDER` 选后端：

| 值 | 说明 | 需要的配置 |
|---|---|---|
| `google`（默认） | `translate.googleapis.com` 的 gtx 端点 | 无 —— 不用注册、不用 key |
| `cloudflare` | Workers AI `@cf/meta/m2m100-1.2b`，免费额度每天 10k neurons，够这个量级用 | `CF_ACCOUNT_ID` `CF_API_TOKEN` |
| `libre` | 自建或公共 LibreTranslate | `LIBRETRANSLATE_URL`（可选 `LIBRETRANSLATE_KEY`） |
| `ollama` | **自己机器上的 Ollama**（家里的 DGX Spark），标题不出网、无配额、无 429 | `INEWS_TRANSLATION_URL` `INEWS_TRANSLATION_MODEL` |
| `none` | 关掉，标题保持原语言 | — |

### `ollama`：本地模型

前四种都要把标题发给第三方，而且都受制于别人的额度和存废
（`cfllm` 原来用的 `llama-3.1-8b-instruct` 就在 2026-08-31 被 Cloudflare 废弃返回 410）。
本地模型没有这两个问题，代价是那台机器得活着——所以失败路径和别的 provider 完全一样：
拿不到译文就留原标题，**新闻不会因为家里断电而消失**。

```
INEWS_TRANSLATION_PROVIDER=ollama
INEWS_TRANSLATION_URL=http://<Spark 的 Tailscale IP>:11434
INEWS_TRANSLATION_MODEL=hf.co/tencent/Hy-MT2-7B-GGUF
```

**「保持原文」只对拉丁字母成立。** 2026-09-04 上线当天一轮 33 条失败全是韩文标题，
模型翻得没错——它在服从当时那句「公司名、产品名、人名保持原文不译」：

```
原文  SKT·KT·카카오, '모두의 AI' 개발 착수…배경훈 "국민 감탄할 서비스 나와야"
译文  SKT、KT、Kakao启动"모두의 AI"开发，배경훈称"必须推出令国民惊叹的服务"
```

句子结构、机构名、语气全对，产品名和人名还是谚文。**判据是读者的字表，不是文风偏好**：
中文读者认得 `OpenAI`，不认得 `배경훈`——前者留原文是帮忙，后者留着等于没翻。
所以提示词现在分开说：拉丁字母的专有名词保持原文，韩文/日文的必须转成中文。

提示词**按模型族分**，这不是风格问题：

- **Hy-MT / hunyuan-mt** 是翻译专用模型，用官方模板
  `把下面的文本翻译成中文，不要额外解释。`——换一句或加系统提示词都会掉分；
- **其余通用模型**（`qwen3.8:27b` 等）走系统提示词，靠它保住品牌名不被译成人名。

限速默认值也按 provider 分：本地不限速（`GAP_MS=0`），远端免费接口仍是 700ms。
「慢一点」的理由是别人的善意不是 SLA，这条对自己的机器不成立。

### 换模型之前先量一遍

```bash
npm run bench:translate -- hf.co/tencent/Hy-MT2-7B-GGUF qwen3.8:27b
```

语料优先取库里**还没译过的真标题**（取不到会明说退到内置样本），逐条并排打印译文、
过闸率（用的就是线上那把 `translationLooksBad`）和每条耗时。

**为什么非要自己量**：榜单上的分数是别人的语料上的分数。上一次凭榜单选模型，
选出来的 m2m100 把 `Claude` 译成了人名「克劳德·塞辛斯」。
过闸率只拦得住「明显是垃圾」，**「翻错了但看着像话」只有人读得出来**——
所以这个脚本把译文整条打出来，不只给分数。

### 2026-09-04 实测结果（DGX Spark，八条内置样本）

| 模型 | 过闸 | 平均耗时 | 判断 |
|---|---|---|---|
| `qwen3.8:27b` | 8/8 | **850ms** | **选它** |
| `kaelri/hy-mt2:7b` | 8/8 | 1273ms | 不用 |
| `qwen3:30b-a3b` | 0/8 | 3655ms | 不能用 |

**通用模型赢了翻译专用模型**，而且是在专用模型的主场（中英互译）上赢的。
三条具体理由，都不是过闸率看得出来的：

1. **Hy-MT2 把品牌名译了。** `오픈AI` / `オープンAI` 它译成「**开放AI**」——
   这正是当年 m2m100 的病。专用模型走官方模板，**没有地方能告诉它「保留品牌名」**；
   通用模型靠系统提示词就能守住。这不是调参能补的差距，是接口形状的差距。
2. **Hy-MT2 会加原文里没有的话。** 韩文那条它译完补了一句「真是令人兴奋啊！」——
   源标题里没有这五个字。新闻产品里这是不能接受的。
3. **语体不对。** 它产出的是句子（「Anthropic公司推出了……版本。」），不是标题。
   时间线要的是标题。

另外 Hy-MT2 的译文尾巴上挂着 `<｜hy_end▁of▁sentence｜>`、`<ａ｜hy_Emo｜>`。
**要说清跑的是哪一份**：官方的 `hf.co/tencent/Hy-MT2-7B-GGUF` 两次都没拉成功，
实际跑的是社区上传的 `kaelri/hy-mt2:7b`——**用户命名空间，无人审核**。
停止符设错是手工转 GGUF 最常见的翻车方式，这是更可能的解释；
但**我们没验证过官方那份，所以证不出问题出在哪一层**。质量闸已补上这一条。

`qwen3:30b-a3b` 的 0/8 也不是翻译水平问题：它把推理过程当正文吐了出来，
而且没有 `<think>` 标记可剥，`think: false` 对它无效。**它快，但这条路走不通。**

结论只对**这八条样本**成立。换了语料要重跑——这个脚本存在的意义就是让重跑很便宜。

翻译在每个采集 cycle 结束后以单独的 single-flight 任务运行，有自己的时间预算
（默认 cycle 的 60%），采集循环不会等待它；连续失败 3 次就停手等下一轮，
不去锤免费接口。
拿不到译文的条目照常显示原标题，不会消失。

存量补译：`npm run translate`。页面上也可以从「管理 → 补译标题」手动跑一轮。

判断「这条是不是已经是中文」不是按字符比例算的：中文科技标题里全是拉丁品牌名，
`Gemini 3 发布` 只有 17% 是汉字却完全是中文。实际比的是**汉字数 vs 拉丁单词数**。
日文假名、韩文谚文出现即判定为非中文 —— 它们和中文共用汉字，按汉字数会被误判成「已经翻好了」。

## 登录与权限（src/auth/）

### 认证归本项目，不再走 legacy platform accounts

**决定（2026-08-21）：登录由本项目负责，Caddy 那层不再做鉴权。**

原来的形态是 Caddy `forward_auth` → infra 的 `accounts` 服务把整站拦下，
而角色（谁能看 Dashboard、谁能锁车道）只有本站知道 —— 一次请求要过两套互不认识的
身份系统，两套密码库，两个「退出登录」。现在统一到一处：

- 本站自己发会话、自己判角色，不读任何上游身份头。
- 页眉「管理」菜单里不再有跳去 `/account/settings` 的入口。
- 反代退回它该做的事：TLS、转发、限速。

**部署那边要做的三件事**（配置在 infra 仓库，不在这里）：

1. 主应用路由去掉整站 `forward_auth`，直接反代到 compose 服务名与容器端口：

   ```caddyfile
   inews.today {
       encode zstd gzip
       reverse_proxy inews:8789
   }
   ```

   这里的 `inews:8789` 是生产 compose 内网地址；本机裸进程仍是
   `127.0.0.1:8787`。两种拓扑不能混写。

2. 把宿主机 `/srv/rawarticle/` 只读挂进应用容器，并用 `RAWARTICLE_DIR` 指向挂载点。
   `/rawarticle/*` 仍经过本站 Node 服务，由 `requireStaff` 复用同一个 `inews_session`
   判权；Caddy 不能再为这条路径直接读文件或另设一套登录门。

3. 确认没有任何中间层还在注入身份头。本站不读这些头，所以伪造它们拿不到权限；
   但留着会让下一个人误以为它们还有意义。

改完先验一次：`curl -si https://inews.today/api/timeline | head -1` 应当是 `200`
而不是 302 到登录页；未带本站会话访问 `/api/stats` 与 `/rawarticle/ft/index.html`
都应当是 `401`。

### 整站需要登录怎么办

反代那层撤掉之后，「整站需登录」这个能力必须由本站接住，否则就是白丢了一个功能。
`INEWS_REQUIRE_LOGIN=1` 就是它：开启后连时间线和筛选项都要账号，未登录访问首页
直接显示登录墙。默认关闭 —— 时间线是一个公开的新闻页。

`/api/version` 任何情况下都不鉴权：它是浏览器分辨「缓存旧了」和「部署旧了」的唯一手段，
登录页上也得答得出来。

### 权限分层

**时间线是公开的**（除非开了 `INEWS_REQUIRE_LOGIN`）。Dashboard、规则演化、账号管理、
以及所有写操作（人工锁车道、手动补译）都要求 `staff` 或 `admin`。所有入口都收在
**页眉右上角的「管理」菜单**里，未登录时那些标签页直接隐藏 ——
让访客先点进去再吃 403 是最差的一种交互。

创建第一个管理员：

```bash
read -rsp '管理员密码（至少12位）: ' ADMIN_PASSWORD; echo
export ADMIN_PASSWORD
node src/cli.js admin you@example.com
unset ADMIN_PASSWORD
```

不要把密码直接写在命令行或长期留在容器 env；上面的写法让 shell 历史只记录变量名，
不会记录密码值。`ADMIN_EMAIL` + `ADMIN_PASSWORD` 的启动 bootstrap 仍保留给受控的一次性部署，
密码不足 12 位时会拒绝启动且不改账号。

登录框接受邮箱或可选用户名。用户名是 3–32 位小写字母、数字及 `. _ -` 组成的
第二登录名，由管理员在账号页设置或清空；邮箱始终是身份记录，也是验证码、找回密码
和通知的唯一地址。管理员 bootstrap 与 CLI 因此只接受完整邮箱，不会把同名用户名误提权。

没有管理员时服务启动会明确警告 —— 一个没人能进管理处的实例，和正常实例长得一模一样。

实现要点（与 `infra/docs/identity-architecture.md` 一致，零依赖，只用 `node:crypto`）：

- 密码 PBKDF2-SHA256 600k 轮，登录时若发现是旧参数哈希会**就地升级**（只有那一刻拿得到明文）。
- 会话 token 256 bit，**哈希后入库**：库泄漏不等于会话被接管。Cookie 是 HttpOnly + SameSite=Lax，
  `INEWS_SECURE_COOKIES=1` 或反代带 `X-Forwarded-Proto: https` 时自动加 `Secure`。
- 写操作要 session 绑定的 CSRF 令牌（HMAC）。SameSite 已经挡住了跨站表单 POST，
  但那是一个浏览器默认值之遥的唯一防线。
- 登录失败 5 次/15 分钟触发指数锁定（15 → 30 → 60 分钟封顶）。
  「密码错」「账号不存在」「账号已停用」返回**同一条文案**，否则登录接口就是个账号枚举器。
- 验证码 6 位、10 分钟、5 次尝试，只存哈希；每邮箱每小时最多 5 条。
  未配 SMTP 的开发模式下验证码打到服务端日志（生产环境直接拒绝这条回退路径）。
- 改密码/重置密码会销毁该用户的其它会话；停用账号立刻踢下线。
- 登录成功/失败、锁定、验证码发放、角色变更全进 `audit_log`（谁 / 何时 / 做了什么 / 对谁 / 从哪个 IP），
  管理页直接看得到。
- 系统拒绝把**最后一个管理员**降级或停用 —— 那会让所有人都进不来，且没有站内退路。

自助注册默认关闭（`INEWS_REGISTRATION_OPEN=1` 打开）。注册出来的账号永远是 `user`，
升 `staff`/`admin` 只能由管理员在账号页操作。

## 字体与品牌

界面**不加载任何 web font**。中日韩字体即便做了子集也有几 MB，而首屏就是要读的；
`--sd-sans` 从 `system-ui` 起手（各系统各自用 PingFang SC / HarmonyOS Sans / 微软雅黑），
后面按系统列了具体回退名。结果是文字在第一帧就有，零 FOUT、零网络往返。

品牌资源在 `web/brand/`：`favicon.svg`（浏览器图标）、`header-mark.svg`（页眉标记）、
`inews-og-card.svg`（社交分享图）。它们沿用历史 Signal Desk 设计参考的酸绿内框与
`AI` 标记，但所有对外名称都明确属于 `inews.today`。
三者共用同一套记号：酸绿内框 + `AI` 字面 + 套准标记。

## 界面

- **时间线**（公开）：按 `published_at` 倒序，按天分组。标题中文呈现、原文可展开。
  每条显示 时间 / 标题 / 域名（按 seed 类型着色）/
  角度 / 语言 / 首发标记 / 抓取延迟 / `+N 转载`（点开看同一故事的所有来源）。
  支持标题搜索、角度、语言、只看首发、相关/全部 切换。
  默认「合并转载」：同一故事只显示首发那一条，点「+N 转载 ▾」展开全部来源。
- **分析**（需管理员）：总量与延迟卡片、24 小时发布量柱图、角度与语言分布、
  域名评分表（含各维度拆解与置信度）、热点故事（转载数排序）、采集器健康度，
  以及轮询机制的明文说明（车道数量、每轮发多少、转一圈多久、请求/分钟）、自适应阈值表、
  **角度与关键词全表**（每一个真实发出的查询串 + 语言地区 + 当前车道 + 实测产出 + 判定理由）、
  调档频率图、完整调档流水。
- **账号**（需管理员）：用户列表（改角色、停用/恢复）、翻译进度、审计流水。

想直接看界面长什么样、不等真实数据：`npm run demo`（灌一份演示数据并起服务，不联网）。

## 结构

```
src/config/keywords.js   角度 × 语言 × 关键词 → shards
src/config/sources.seed.json  域名先验
src/lib/rss.js           RSS 解析（无依赖）
src/lib/normalize.js     域名提取 / 标题归一化 / 去重 key
src/lib/relevance.js     AI 相关性打分
src/lib/ingest.js        入库 + 故事簇 + 域名累积
src/lib/domains.js       域名评分
src/lib/fetcher.js       令牌桶 / 并发 / 条件请求 / 重试
src/lib/translate.js     标题中文化 + 译文缓存（google / cloudflare / libre）
src/scheduler.js         分批轮转调度
src/server.js            API + 静态资源 + 权限闸门
src/auth/                密码 / 会话 / 验证码 / 邮件 / 账号接口
web/                     时间线 + Dashboard + 管理处
web/brand/               favicon / 页眉标记 / og:image
```

## 下一步（第二版候选）

1. 解析 Google News 跳转链接拿到真实文章 URL（现在存的是 GN 链接，`<source url>` 已足够做域名归属）。
2. 高分域名直连它们自己的 RSS，绕开 Google News 的收录延迟。
3. 用标题向量做近似去重，替代当前的词袋 key（跨语言同一故事目前会被算成两条）。
4. `status = muted` 的域名在时间线里默认折叠（内容农场，比如 seed 里已标注的 mshale.com）。
