# 计算芯片目录交接（2026-10-02，m5）

## 已定规则与状态
- 本次是补充；CPU / GPU / 其他计算加速器独立于原厂 navigation。形态分芯片、板卡/模组、整机/平台、系列、IP、待核验。
- 复用 `data/companies.json.records` 全部既有 ID。鲲鹏/昇腾→华为，海光 DCU→海光；不建同名新公司。中国筛选指总部国家，不表示制造地。
- Gaudi、昇腾、寒武纪、燧原为其他计算加速器；ARM IP/网络不混入成品 CPU/GPU；DCU 逐型号核验，不推定 GCN/CDNA/RDNA。
- InResearch 基线 d24b60a；Fetchspec 基线 8c71669。bce9102 在本机对象、reflog、已有 worktree 列表未找到，远端短 SHA fetch 也未解析。现有 docs/upstream 补丁已检查并保留，没有假设该提交已推送或已合入。
- InResearch #305 已合并为 `4a1218d11c83e122fc69476eb8625982a04e966c`，Fetchspec #73 已合并为 `a7f0f57e1e744a5da8bd66288592bf84aeb04f3d`。2026-10-02 21:18（上海）网站新版健康，12 份真实目录交付成功；Spark 未操作。发布修正与回执交接工作树为 `~/.worktrees/inresearch.ai/compute-catalog-release-20261002`。

## 线上实际覆盖（生产回执、数据库与公开接口对账）

| 公司/产品线 ID | 目录实体 | 具体命名型号 | 有原文规格表/字段的实体 |
|---|---:|---:|---:|
| ampere-computing | 8 | 7 | 8 |
| biren | 3 | 3 | 3 |
| cambricon | 1 | 1 | 1 |
| huawei-ascend | 2 | 2 | 2 |
| huawei-kunpeng | 1 | 1 | 1 |
| hygon | 23 | 23 | 23 |
| iluvatar-corex | 3 | 3 | 3 |
| intel | 2 | 2 | 1 |
| loongson | 3 | 2 | 3 |
| metax | 3 | 3 | 3 |
| moore-threads | 3 | 3 | 1 |
| nvidia（保留既有线上批次） | 595 | 237 | 294 |
| micron（保留既有线上批次） | 4940 | 4824 | 1354 |
| phytium | 6 | 3 | 6 |

本次新增 58 个实体，53 个为具体命名型号，55 个实体有原文规格表或字段。NVIDIA 本地旧导出是 597 项，但线上已有较新的 595 项（生成于 08:33 UTC），此次不回退、不重发。旧本地多出的两项是 Spectrum-4 SN5000 交换系统与 MMS4X00-NM-T 光模块，旧导出与原件原样保留；Micron 原批次 4,940 项不动。有规格的系列与有规格型号不能混合为型号覆盖率；这些计数不是厂商全量产品数或在售证明。

中国 GPU 已核验 9 个板卡/模组：天垓100 BI-V100、天垓150、智铠100 MR-V100；MTT S80/S4000/S5000；曦云C500/C500X/C550。其中 7 个有原文规格字段，MTT S4000/S5000 数值表仍待提取。壁仞166M/166L/166C 另有3个真实板卡/模组及功耗原文，但当前型号页不足以证明芯片架构，分类留待核验，不混入上述9个 GPU。

AmpereOne 按官方SKU表得到7个子型号及1个系列，保留 Usage Power 的估计测试条件、不改叫TDP。海光23个CPU来自官网引用的静态JSON组件，字段原键原值；飞腾3个系列加S5000C-64/-32/-16三个明确子型号；龙芯3C6000仍为S/D/Q系列，3A6000、3D5000为型号；Intel Xeon 6980P 与 Gaudi3 HL-338分属CPU/其他加速器；昇腾950PR芯片与Atlas350板卡分开。

## 未完成项
- AMD：官方 robots 请求多次超时，本轮没有形成真实产品交付。
- 兆芯：根页无可识别产品内容；检出的新闻路径 robots 禁止，需取得允许的官方产品/原件通道。
- 燧原：robots 返回403，未绕过；只有候选配置，没有产品上架。
- 海光DCU：当前官网没有取得Z100/K100的型号架构证据；model_reviews记录逐项缺口，参数和架构不补值。
- 壁仞：当前166系列AI板卡已收；BR100/BR104旧产品官方原件与166系列具体芯片架构尚缺。
- 更多Intel/AMD/中国厂商型号、动态切换规格与PDF附件尚未穷尽。昇腾URL的tag切换在静态HTML里仍返回默认型号，没有把这些URL误当不同产品。
- AMD、兆芯、燧原、海光 DCU 线上仍为 0；Supermicro、SK hynix 亦无已交付目录，本次不填示例。CPU/GPU/加速器的全厂商穷尽、动态规格与附件提取仍未完成。

## 数据与重跑入口
- 实际原件/来源观察/目录导出：`~/.local/share/fetchspec/compute-catalog-20261002/`；不可当临时缓存删除。
- NVIDIA原件保留在 `~/.local/share/fetchspec/pipeline/`；只读导出没有重建ID或搬走原件。
- InResearch本地验收库：`~/.local/share/inresearch.ai/compute-catalog-20261002/data/raw/product-catalog/`；测试夹具只在系统临时目录。
- Fetchspec规则：`config/compute_catalog.json`、`adapters/compute.py`、`hygon_catalog.py`、`compute_catalog.py`。型号正文依据不匹配报错，不产出真实产品。原件已收仍可按SHA重解析；Hygon要求新鲜页面引用链。
- InResearch规则：03/05/06现行规范，`workflow/compute_catalog.py`、`workflow/product_catalog.py`；页面 `/compute-catalog.html`，逐公司详情仍 `/product-catalog.html`。
- 阶段完成后可以 `/clear` 或开新会话，从本页接续；原件只在m5本机，Git提交不会同步这些数据库和字节。

## 本轮验证
- Fetchspec：223项测试全部通过（含3项与干净origin/main d24b60a接收端的集成；开发分支因上游必须等于origin/main的门禁拒绝，未绕过）；新型号门禁、原文参数、Ampere行/飞腾列拆分、Hygon只解码不执行均有回归。reporg已重生成并通过check。
- InResearch：目录23项、计算分类5项、公开读取5项、界面4项、治理9项测试通过；严格数据校验0 warnings，registry引用有效，governance refresh/check通过。
- 浏览器：compute_catalog、product_catalog两套通过；另用实际接收库检查桌面/390px手机、中国GPU过滤和详情跳转，未见脚本错误或横向页面溢出。浏览器夹具与原件运行库隔离。
- 来源审计清单在Fetchspec `docs/records/2026-10-02-compute-coverage.json`（含型号、SHA、URL、观察时间；不含原件字节）。

集成基线另有只读工作树 `~/.worktrees/inresearch.ai/compute-receiver-baseline-20261002`；本次开发分支的新接收代码另用真实58个新增实体及597个既有NVIDIA实体进行来源SHA校验和接收验收。

## 2026-10-02 生产发布验收与续接
- 使用既有 `nvidia-pilot.token`，经 `product_catalog.publish` 的固定 HTTPS 接收端逐公司交付；先验证 schema 与全部原件 SHA。12 份 `ok=true` 回执的 `run_id` 与本地规范化包 SHA 一致；公开 full API 的 58 个产品身份、原表、compute 原文证据逐字段相等。回执时间为 13:17:55–13:18:12 UTC。
- 本机完整回执、发布前后 API 快照、生产数据库只读核验、浏览器报告/截图/CSV：`~/.local/share/inresearch.ai/compute-catalog-release-20261002/`；不含凭据，不删除这些运行记录。`receipts/<公司>.json` 含原包 SHA 与生产 run_id；`production-db-audit.jsonl` 含逐公司当前批次与数量；`payload-verification.json` 记录公开原表对账。
- NVIDIA 批次 `fdf9817ef66957b2d2b87863aad754661ae20a2257434ec87915624d29e52f5e` 与 Micron 批次 `9805ea26eda47d97886dcaf7628f80da872d7b0dba279a8d58fe6decfd1347cd`、接收时间均未变化。Micron 的 4,940 项含 116 个系列/目录及 3,461 个停产登记，不代表 4,940 款在售产品。
- PR/main CI 的 validate、browser core/model_assets、storage-container 均成功；Fetchspec 未配置 GitHub CI，合并后以当前 InResearch 主线重跑 223 测试（含 3 项接收集成）成功，reporg check 通过。InResearch 严格校验 0 warnings、registry、governance 与目录相关 47 测试通过。
- 真实浏览器额外发现并修正：CPU option 开始标签误写成结束标签，导致 CPU 选项丢失；整轮共用 20 秒与字体传输竞争造成其他公司批量超时。修正 CPU 标签、逐请求 30 秒与数据请求高优先级，并补 CPU 选项、首批慢响应及单厂超时隔离回归。窄屏表格设置最小宽度以在容器内横向滚动，避免产品名与表头挤成逐字竖排。修正随本次发布收口 PR；线上最终 SHA 以部署镜像与该 PR 合并提交复核。
- 入口：`https://inresearch.ai/compute-catalog.html`，原厂目录 `https://inresearch.ai/product-catalog.html`。后续只补明确缺口，不重做 Spark，不把目录交付当研究采用或 target delivered。
