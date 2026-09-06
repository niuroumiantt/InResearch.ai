# inresearch.ai 前端与产品审阅（2026-09-06）

审阅范围：根目录 13 个 HTML + `admin/product/index.html`，共 5,858 行；各页内嵌的自写 JavaScript/CSS；`assets/levels.json`、模型 manifest、HDRI/图片来源说明；读 `CLAUDE.md`、`docs/DECISIONS.md`、旧 `docs/PROJECT_PANORAMA.md`。第三方 `assets/vendor/` 不逐行审计，仅核对本地模块接入。只读审阅，没有改源码/数据，也没有触发采集、写入、发布。静态 HTML 引用检查未发现缺失文件；15 个可执行 script 均通过 Node 语法检查。

结论：前端已从总览发展成完整的研究导航和操作工作台，3D/BOM 是有价值的知识入口。当前问题不是缺少更多展示页面，而是“看到的状态与真实数据生命周期一致”以及让已有链条稳定运作。数据输入、安全输出与重复的 3D 实现还有实际缺陷，不能把“页面能打开”当作产品闭环已经验收。

## 已实现的真实能力

| 页面/资产 | 已有能力与边界 |
|---|---|
| index.html | 项目库 L1–L9 分桶、运营/在建/规划分开；区域和开发商结构；地图公司下钻；价格时序；预警指标；研究、事实与工单入口。数据来自 JSON，60 秒重新读取；不是市场数据实时采集。 |
| company.html | 248 家公司切换器；项目/合同关联；15 篇研究文档内实体引用；本地 SEC 文件、新闻信号聚合。容量/实体链接成立，但公司档案页没有公司库列表搜索。 |
| report.html | 全部研究模块拼成活文档；Finding 状态、论证、口径提醒、证据、待办和章节目录；浏览器打印。打印是内部活文档副本，不等于已走公开口径的可交付报告。 |
| doc.html | Markdown/CSV 阅读器，打分表按分数/深度/模块过滤，每页 50 行。已解决“把 CSV 当段落”，尚未解决全量加载和解析。 |
| bom.html | 46 个 BOM 部件、5 层等轴测 SVG；部件→研究/公司/价格/指标/材料导航；hash 深链。所有部件都能从文字入口访问。 |
| bom3d.html | 程序化园区/机房/机柜/服务器拆解、六个领域定位、46 节点数据覆盖热图、工单数、时序小图、部件单独旋转、领域/部件深链。部分 BOM 节点仍显示“未建模”，这是明确呈现的范围边界。 |
| rack3d.html | ORV3 形态示意；外板、电源架、歧管、交换机、托盘、GPU/HBM 分层；真实设备前面板图、风扇/LED 动效、部件档案和旋转查看器。是结构示意，并无型号配置/量化 BOM/选型验算。 |
| poster.html / bake.html | 九层服务器海报、自渲染透明 PNG、每层回链到 BOM/3D；海报有“非特定厂商产品”说明。烘焙台为内部工具。 |
| compare.html | GLB 候选模型旋转与网格数/材质数/面数/包围盒检查；可拆解性是名称和网格数启发式。是资产验收工具，不是采购产品对比。 |
| admin/product/index.html | 175 作业单元按环节/品类组织；P0/P1/P2、型号与产品线资料覆盖；公司/型号两层资料卡、来源和本地打开。当前主索引不存在，实际只展示对齐包 6 条样例，不能视为产品库已建成。 |
| team.html | 工单筛选、模块统计、派工/认领对话框，写回 `/api/assign`；当前 assignments 0 条。页面存在不等于协作运转。 |
| ops.html | 16 个管线任务入口，价格/事件录入，管理员用户/角色管理、密码重置，数据/项目/模块状态概览。部分动作只适用于本机，已有文案标注。 |
| framework_poster.html | 15 模块静态 A3 总图；保留 M11/M14 的位置，没有擅自落地未决 A5。尺寸固定 1587px，适用于海报/导出，不适合作为手机主入口。 |
| assets | Three.js 模块全部本地；HDRI、面板图、渲染图有来源/许可说明；levels.json 驱动下钻链；有 1 个 GLB 样例，但 manifest 明确注明用户“不采用”，目前仍在 rack 页面右侧载入。GPU 服务器复用 rack 的 x=70，存储/交换机独立页 planned。 |

## 可复现缺陷（优先级按本产品影响）

### P1：URL 可直接进入未转义 HTML（当前用户身份下脚本执行风险）

- `/Users/m5/code/inresearch.ai/company.html:89` 从 `c` 参数取任意字符串，`:95` 拼入 Error，`:215` 把 `e.message` 放进 `innerHTML`。
- `/Users/m5/code/inresearch.ai/compare.html:55`–`:56` 从 `f` 参数取文件名，`:88` 直接拼入卡片 `innerHTML`。加载模型成功与否不影响 HTML 已被插入。
- 隔离脚本 `/tmp/inresearch_frontend_review.mjs` 执行了 company 的实际完整脚本（用内存 fetch/DOM setter），及 compare 的实际参数解析与卡片构建片段。两个输出都含真正的 `<img ... onerror=...>`，不是被编码的文本。
- 本地无害复现参数：`company.html?c=%3Cimg%20src%3Dx%20onerror%3D%22globalThis.__reviewXss%3D1%22%3E`，compare 改成 `compare.html?f=...`。此审阅只验证实际代码 sink，没有在浏览器触发脚本，没有对生产测试。
- 登录/HttpOnly 无法替代输出编码：登录用户打开链接后，脚本仍能以该同源用户身份请求 API。修复用 `textContent` 呈现错误/文件名，文件名路径另做白名单；补两个小回归用例即可。
- 同类输入边界仍散布在 `/Users/m5/code/inresearch.ai/ops.html:295`–`:304`（外部新闻标题/来源/URL 等 raw HTML）；`/Users/m5/code/inresearch.ai/admin/product/index.html:159`–`:163`、`:240`–`:258`（资料/公司字段 raw HTML）；`/Users/m5/code/inresearch.ai/doc.html:81`–`:86` 和 `/Users/m5/code/inresearch.ai/report.html:100`–`:106`（Markdown href 无协议约束）。实际 report `inline('[proof](javascript:globalThis.__reviewXss=1)')` 产出 javascript: 链接。应统一“文本/属性/URL”三种边界，而非仅补某一页 esc。

### P1：CSV 虽分页，仍在前端把 25.7 MB 放大到数百 MB

位置：`/Users/m5/code/inresearch.ai/doc.html:150`–`:174`、`:238`–`:254`、`:270`–`:273`。

- 当前打分表 25,677,396 字节、13,663 条记录。先下载整文件，字符循环 `cell += c` 全量解析，再做对象/筛选/排序；页大小 50 仅限制 DOM。
- 独立 Node 22 进程执行原始 `parseCSV`：约 290 ms；heap 从 30 MiB 到 553 MiB，RSS 从 119 MiB 到 678 MiB。该数字是 M5 本地 Node 逻辑实测，不应当表述成手机/浏览器实测；它已经足以证明前端解析的显著内存放大。
- 每次输入又 `r.join(' ').toLowerCase()` 全量构建筛选文本，没有 debounce。应优先做标准库分页/过滤读取 API 或生成按模块/分数划分的小索引，并保留静态模式兜底；无需引入前端框架。

### P1/P2：3D 多阶段动画后段覆盖前段，服务器脱离机柜的空间关系错误

位置：`/Users/m5/code/inresearch.ai/bom3d.html:555`–`:556`、`:607`–`:609`、`:785`–`:790`；`/Users/m5/code/inresearch.ai/rack3d.html:501`、`:509`、`:628`–`:633`。

- 同一对象被登记多条动画；每条都以初始 home 计算并调用 position.set，而不是先还原 home 后累积位移，后段即使尚未开始（k=0）也覆盖前段。
- 执行 bom3d 原 apply，套用第 4 层服务器的实际两个位移：滑杆 68% 时实际 z=5.1（原位），第一段既已完成应为 z=18.9；100% 实际 z=9.15，累积后应为 z=22.95。冷板/GPU 等三个阶段同样相互覆盖，标签却用累积距离，文字与部件可能分离。
- rack 的明星托盘 36%–52%“阶梯抽出”同样被下一段 k=0 覆盖，表现为其它托盘动而明星托盘不跟随。
- 应把时间轴改成对象级的明确轨道/分层坐标，给 0/52/68/84/100% 几个关键帧核验位置；具体要绝对目标还是叠加增量需分别检查，不能机械地把每个 set 改 add。

### P2：连续查看部件时，单独旋转模型会漂移甚至出画

位置：`/Users/m5/code/inresearch.ai/bom3d.html:1027`–`:1044`；`/Users/m5/code/inresearch.ai/rack3d.html:759`–`:776`。

- 重建只 remove children，没有归零 iGroup 的上一次位移。新 Box3 含旧位移，却把“世界中心”的负值直接再赋给局部位移；iPivot 旋转后还会混入父级旋转坐标。
- 调用实际 buildInspector，使用本地 Three.js、位于 [10,5,2] 的简单部件，不启动 WebGL：连续三次同一部件中心 `[0,0,0] → [10,5,2] → [0,0,0]`。单独查看器应每次中心都为 0。
- 同时旧 clone 材质移除时不 dispose，反复操作会留下资源；应归零并在统一坐标系居中，移除时只 dispose 自己 clone 的材质，不释放仍由主场景共享的 geometry。

### P2：主板 DIMM 错接 HBM 档案

位置：`/Users/m5/code/inresearch.ai/rack3d.html:556`–`:561`。DIMM Mesh 的 `userData.part` 是 `hbm`，所以点击服务器主内存会显示 HBM 供应商/技术/价格。`framework/bom.json:603` 已有 `dram` 专门节点，`:617` 明确“服务器内存与HBM供需周期不同步，价格序列应分开”。这正是项目的口径要求，应改为 dram，并核验 poster 主板/风扇映射。风扇目前在 rack 被 tag 为 server，而海报风扇链接 fan-vc，会出现可打开档案但没有该结构的 inspector。

### P2：产品看板的中文搜索完全无效

位置：`/Users/m5/code/inresearch.ai/admin/product/index.html:134`、`:278`–`:281`。norm 删除所有非 `[a-z0-9]`，输入“华为/液冷/电源”都变空字符串，过滤条件 `!q` 为 true，因此所有卡片仍显示。直接执行原 norm，`norm('华为') === ''`。搜索需要保留 Unicode 字母数字，产品型号匹配可继续使用单独的英文规范化函数。

### P2：产品页从历史补丁取画像，已有公司知识仍显示待接入

位置：`/Users/m5/code/inresearch.ai/admin/product/index.html:177`–`:178`、`:243`–`:248`。comps 数据源是 `docs/inbox/inresearch-alignment/companies_patch.json`，该文件 0 条 profile；主 `data/companies.json` 有 94 条 profile，覆盖产品目录中 13 家公司。页面因此把已存在的画像显示成“公司画像待接入”。应读主公司表，历史补丁只保留溯源用途。

同页 `:131` 的本地根路径写死 `/Users/yidian/...`，当前 m5 工作区在 `/Users/m5/...`；`:153`–`:157` 复制出来的路径在本机不可用。应让本地服务返回路径能力或只显示可移植相对路径，不能把远程服务器与旧 Mac 用户的路径当成通用入口。

### P2：产品资料“核心达标/型号覆盖”混用待下载、需人工与已核验状态

位置：`/Users/m5/code/inresearch.ai/admin/product/index.html:188`–`:199`。

- 型号覆盖只判断记录存在，pending、needs_manual、superseded 都会算 `ok`。
- 核心达标仅排除 superseded，pending DS + pending WEB 也能算绿色达标。
- 这是条件分支可确定的逻辑缺陷；当前只有 6 条样例，未宣称已在当前数据里造成大面积误报。应分开“有采集计划”“已拿到可用文件”“已核验”，达标取用户规定的真实可用状态。

### P2：数据时效和页面刷新时钟混淆

位置：`/Users/m5/code/inresearch.ai/index.html:450`、`:468`–`:469`；`/Users/m5/code/inresearch.ai/report.html:220`–`:224`；`/Users/m5/code/inresearch.ai/company.html:196`、`:209`–`:211`。

- 首页用现在时钟标“实时”；report 用浏览器当天标“数据快照”。当前 `data/brief.json` 的 date/generated 都在 08-18，工单 generated 在 08-26；刷新不代表采集完成。
- company 仍把老 brief 的计数写“近 3 天新闻信号”，没有与当前日期比较。
- 指标卡多处已经显示 as_of，是应保留的优点；但 `index.html:123`–`:131`、`ops.html:263`–`:270` 颜色只看值与阈值，不实现注册表声称的 stale。例：变压器 monthly 指标仍 06-30。
- 应展示“页面读取时间”“数据更新时间”“待复核/过期”三个独立语义。报告快照应用固定的源版本/生成时间，保证之后可重现。

### P2/P3：两张总览的容量汇总集合不一致

位置：`/Users/m5/code/inresearch.ai/index.html:220` 明确过滤 `portfolio`；`/Users/m5/code/inresearch.ai/ops.html:325` 不过滤。当前 `in-portfolio-nxtra` 带 L8 300 MW + L2 700 MW，故两页漏斗会差这 1,000 MW。ops 文案还声称“集群级不计入”。应把项目计量集合/portfolio 策略收敛到同一生成逻辑，明确公司页显示组合级口径还是站点级口径。不要借修复编造未披露容量。

### 次级稳定性/体验问题

- `/Users/m5/code/inresearch.ai/compare.html:63`–`:67`：无模型时先写空态，下一行立即清空，最终只剩空白。
- `/Users/m5/code/inresearch.ai/rack3d.html:307`–`:311`：panel 的 fallback 参数未使用，失败只 console.warn，注释“用程序化面板兜底”实际没有执行。bom3d/rack3d 的 JSON 顶层 await 也无整页可见错误状态，单表失败就停在空画布/HUD。
- `/Users/m5/code/inresearch.ai/bom3d.html:50` 和 `/Users/m5/code/inresearch.ai/rack3d.html:35`：340px 右档案 + 300px 左 HUD 全固定；唯一 900px 响应规则只是隐藏 drill。窄屏会互相覆盖；顶部多页导航亦不换行/不折叠。需要主审补浏览器小屏实测，不将静态推断当成实测。
- 2D 部件 span/SVG group、3D domain div、产品 span 主要依赖鼠标 click，无统一按钮语义/tabindex/Enter；键盘快捷键只覆盖 bom3d 领域。应在主要业务入口使用原生 button/link，图形有等价文本入口。
- `/Users/m5/code/inresearch.ai/bom3d.html:1109` 与 `/Users/m5/code/inresearch.ai/rack3d.html:825`–`:832` 持续主循环 + Bloom + 2048 阴影；无质量档位/静止时按需渲染。compare 每模型一个 WebGLRenderer 且每帧 resize。不是当前需立即重构的问题，但扩模前应设场景面数/纹理/帧时预算。
- 页面有多份导航、调色板、esc/get、容量分桶、Finding 解析和两套 3D inspector。零 npm/pip 不要求这些永远复制；可用本地 ES module/生成时模板保持标准库部署。

## 旧 PROJECT_PANORAMA 的前端问题复核

| 旧问题 | 今日状态 |
|---|---|
| doc 大 CSV 前端解析 | 仍在；原报告“无分页”的笼统理解需纠正：现在有每页 50 行 DOM 分页，但网络和解析没有分页，内存仍数百 MB。 |
| esc/导航/颜色/地图/Markdown 复制 | 仍在；且页面增至 14 个，3D 两页又复制 inspector/拾取/时序函数，已经出现同缺陷双份传播。 |
| 首页每分钟全量重读、公司/报告拉 15 篇研究 | 仍在。可以先生成轻量摘要/倒排索引；报告全量阅读本身合理，公司切换则没必要反复扫所有正文。 |
| ops 缺 workorder/blindspot/intake/facts 按钮 | 已修，当前 :388–:391 四项均在。 |
| reader/map 服务器不可用 | 已加“仅本机/服务器缺依赖”文案，任务按钮仍可点；建议由服务端能力声明隐藏/禁用不支持动作。 |
| bom3d 的 lot 死 mesh | 原符号已不存在；场地已重写，不能沿用旧问题结论。 |
| 旧 URL 编码权限绕过 | 服务器 `_gate` 目前有规范化后的路径封锁；归后端审阅进一步确认。本轮发现的是独立的前端 DOM XSS，不应因旧安全 P0 完成而忽略。 |
| 模型槽“最后一公里” | 已有1个 GLB和HDRI/面板素材，不能说完全没有资产；但唯一 GLB 是明确不采用的参照，没有正式采纳的实物模型。 |

## 产品思路与下一步

保留：稳定 15 模块、事实/知识分层、显式口径/缺数、BOM 作为研究导航、程序化模型与本地依赖、内部审阅流程。A5 双轴分层仍是未决商业/框架选择，不在本次代码审阅里替用户决定，更不重命名或改骨架。

近期顺序建议：

1. 先把信任边界和错误状态做好：URL/动态文字安全输出、Markdown URL scheme、数据日期与过期状态。验收是恶意 URL 只能显示文本，过期简报不能显示为“近3天”。
2. 再修已经影响主交互的 3D：关键帧位移、重复打开 inspector 居中、DIMM/风扇的正确部件映射、缺图/缺 JSON 降级。验收用代表性的三条用户路径，而非只看初始截图。
3. 把产品资料链跑通：主公司表接入、中文筛选、资料状态分层、主索引真实建库、本地路径能力。验收至少一条真实产品线从计划→下载→人工检查→adopt→网页可打开原件。当前6条对齐样例不能替代这条验收。
4. 做资料检索的分页/索引和轻量共享代码；以实际响应时间/内存作为指标。优先服务“找到材料/回证据/完成工单”，不先上框架、不先新增数据库。
5. 完成一条“工单→精读→事实/结论→核验→内部报告→公开口径版本”的运营闭环，再扩人员和设备页。团队页已有真实 API，但 assignments=0，说明眼下短板是实际运行样例。

中期（约1–3个月的排序建议，非工期承诺）：围绕研究员、审核者、报告使用者收敛导航；研究列表可按主题/公司/证据成熟度搜索；结果能回到 record_id/原件；报告带明确用途与版本；持续记录采集成功率、可用/核验材料覆盖、结论复核积压、工单从派到合并时长。3D 覆盖热图从“有字段”进到“有可用且保鲜证据”的覆盖，才成为研究管理工具。

中长期（约3–12个月的排序建议）：在实际需求证明后扩交换机/存储独立页、模型结构映射与数量化配置；维持研究导航和工程配置两种语义的区分。公司/价值链轴如果 A5 通过，再与15课题轴并行。可公开交付必须有来源/权限/金额区间/年份/版本快照，不能从内部活文档直接打印来替代。届时再按真实并发量/查询需求决定存储形态；目前没有证据要求重平台化。

## 验证材料

- `/tmp/inresearch_frontend_review.mjs`：可复跑隔离逻辑测试，包括 URL→HTML、两页 inspector、bom3d apply、中文 norm、CSV解析。无网络、无外部写入。
- 静态语法/文件引用检查结果：14页、15个可执行script，语法错误0，静态本地文件缺链0；不覆盖动态/API/生产网络状态。
- 主审另做 CUA 页面实测；本报告中的 XSS 只确认真实代码输出进入 HTML sink，3D 坐标为本地 Three.js 逻辑复现，不冒充浏览器点击结果。
