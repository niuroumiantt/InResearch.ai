# Abilene模型预览与年度用电复核交接（更新于2026-10-14，机器m5）

## 目标
本地完成前两步，并按用户新增授权完成第三步年度用电四项适用性核对、证据补充及敏感性；保留候选、未知与三异常，暂不上线。

## 已定规则
- 用户已授权前两步及第三步年度用电本地实施，无需再次确认；不推送、开PR、合并或部署。
- 05是模型预览当前规范。原`us-tx-abilene`、旧URL、正式园区观察及通用模型值／公式保持。
- 421MW原观察`30103f2fd01b810c-b03dfa2fe924b039`仍为2026-07-28估算。固定引用不等于来源证据独立：复核工作簿的GPU取整进入容量、算力及方法成本；旧观察网页与新版工作簿SHA不同，旧版公式同一性未证。
- 原件内容经代理核对只表示可人工复核；没有人类批准、现场／产权／最终许可确认或模型采用。三异常、159亿精确系数／舍入未知、未检查余页和影像保留。

## 进度
- 独立工作树`~/.codex/worktrees/navigation-auth-shell/inresearch.ai`，分支`codex/abilene-parameter-preview`；上一阶段本地提交600d3cd6，主工作区未触碰。
- 本轮桥接v3登记13条候选关系、10项原件内容核对、完整83输入标签。GPU／421MW／算力／成本共享上游，断链或伪称独立拒绝；源公式不执行，显式常数算术仅作解释。
- TCEQ官方37589-ac与原附件SHA完全一致，算同一原件镜像；后续37589-tc完整331页只核前四页，余327页未逐页审阅，行政变更候选不覆盖产权或当前主体。BLDG2图内四翼不是四栋，图纸与申请不证明实际安装或最终批准。
- 接入约束0标未知／未设置；等待0年为假设；审批12个月为假设；建设2年为通用参考。地点、费率／法定／历史参考、情景分支和研究口径分别表达。
- 86项相关单元、六套受影响浏览器回归、strict零warning和registry有效。治理.123的2704文件与验收映射通过；完整CI与生产未执行。
- 新预览在`~/.local/share/inresearch.ai/observation-audit/abilene-20261013/model-preview-v2-20261014/preview.html`，同目录scenario.json和截图。上一稿model-preview目录完整保留。
- 新审计／原件／官方接收回执在`dependency-review-20261014/`；169资料单元、192去向（含表头／参数），160候选、2已有观察、23未知、3异常、4未检查项；零新增正式采用／人类确认／模型认证／发布。原件不进Git。

## 第三步本地结果（2026-10-14）
- 本地桥接v4／2026.10.14.3、治理.124；原421MW观察及共享依赖保持，正式projects.json／通用datacenter_model.json均未改。
- 年度用电四项登记容量范围、平均IT电力负载、期间PUE和适用电价。逐栋全年容量、现场双电量/负载、期间PUE、2026合同/电价及购电/自发电份额仍未知，未自动填入候选。
- 新增十份原件取得回执和一份SEC工具转录；新报告70页仅文本8/16/21/31/62、视觉16/21/62；EIA技术注释31页仅文本7/13、视觉7；PUC16页仅文本1/2/3/12/16、视觉2/16。余页/SEC表格原HTML均未核。原HTML下载exit56失败不冒充取得，工具转录SHA只绑定该转录。
- PUC2024-12-19历史REP申请关联Lancium QSE I（Option2/10329）与Abilene DC1；SEC首两栋租约注释有租户向Lancium支付电力费用的工具转录。二者是历史/局部关系候选，不能直接确认2026所选四栋的合同、价格或批准状态；起租日期不是IT容量投运曲线。
- 年度化设计PUE1.2–1.4是新增设计候选，旧公司1.2–1.3及来源峰值比1.4保留，期间实测仍未知。组织购电116100MWh不分配给园区，不能反算负载。
- 纠正上一稿收费语义：EIA2026-07得州7.07美分为收入/售电量平均零售价，已含需量等。桥接确认使用平均零售代理费用，锁定额外demand_rate=0并停用Oncor3.8叠加；0是防重复计费的研究口径，不是实际需量免费。其他地区通用模型同类口径未由本批认证。
- 421MW×70%×8760×1.28得设施3.30441216TWh，IT2.581572TWh；代理费用233621939.712美元。仅固定快照规模365天假设年，不是2026实耗。9单项／27联合／2容量时间对照可导出复算，不把模型ramp再扣一次；实际电网购电/账单为null。
- 累计217项去向／189资料单元：175候选、28未知、3异常、8未检查、1排除、2引用已有观察。24来源登记／22不同SHA；Mortenson重取与旧版完全一致，与TCEQ同SHA镜像均不多计独立证据。零新增正式采用／人类确认／模型用途认证／发布。
- 89项相关单元、六套相关浏览器、strict零warning和registry有效。首次完整单元在沙箱中五个loopback绑定失败，授权本地socket后全89通过；非源码错误。真实组件离线1440/390/320、明暗、确认/切换/导出复算、零HTTP检查通过。
- 用户结果：`~/.local/share/inresearch.ai/observation-audit/abilene-20261013/energy-review-20261014/result.html`；完整审计同目录，预览/情景/截图在`model-preview-v3-20261014/`。旧model-preview、v2和前两步回执完整保留。Git只存源码、规范和脱敏回执`docs/reviews/2026-10-14/abilene-energy/receipt.json`，不存原件/转录/运行产物。

## 下一步
1. 用户查看第三步结果；未获准推进下一阶段完整成本或收入回报，也未获发布授权。
2. 先追PUC批准/后续REP变更及所选范围合同/账单，再补逐栋投运容量与同期间IT/设施/市电/自发电计量。无法取得时继续保留未知和分析情景，不把联系计划计作已发消息。
3. 原三异常、GPU措辞/精度、旧版工作簿及159亿精确系数/舍入仍待来源澄清，不自动解除。
4. 将来授权上线时复核最新基线、最终head全CI及实际生产版本／服务／页面回执；当前不自发推送、PR、合并或部署。

## 待用户决定
- 无本地实施阻塞；下一阶段和上线尚未授权。

## 入口文件与工具
- `framework/05_interface_system.md`、`data/site_model_bridges.json`、`docs/reviews/2026-10-14/abilene-energy/receipt.json`。
- `python3 scripts/export_site_model_preview.py --output <新本地资料目录>/preview.html`，不得覆盖已接受稿。
- `python3 manage.py observation-audit --input <audit-input.json> --output <新结果.json> --html <新结果.html>`；禁止覆盖原件。检验读取边界与去向不证明研究采用。
- `python3 manage.py validate --strict`、`registry`、`governance --check`；相关单元与`node tests/run_browser.cjs site_model_bridge economics_navigation datacenter_cost datacenter_economics datacenter_tco global_campuses`。
- 本机Playwright：`NODE_PATH=/Users/m5/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules`。需要临时loopback的测试使用允许socket的本地执行。
