# 目录与登录外壳交接（更新于2026-10-13，机器m5）

## 目标
按用户已接受方案分阶段实施交付／后台目录、三种身份的页眉页脚及必要聚合、搜索和辅助入口。

## 已定规则
- 05为现行语义规范，site_navigation.json为机器导航／页面归属唯一登记。交付6一级14二级、后台6一级20二级，精确标签以登记和05为准，不再重设计。
- 匿名仅首页和tasks；客户customer与member分开；IT后台可见与动作授权分开。普通登记不强制全文或研究C3；模型、主体、来源和状态各有唯一记录。
- 旧URL、查询、锚点、对象ID和下载保持受保护兼容；手机两行；账号菜单只放账号工具。设计、源码、测试和生产回执分别确认。

## 进度
- 工作树：`/Users/m5/.codex/worktrees/navigation-auth-shell/inresearch.ai`；分支`codex/navigation-auth-shell`；起点`54b18867`。不改主工作区。
- 已登记接受方案：05、CURRENT、DECISIONS、current_state由.113推进至.115（保留主分支.114的研究传输修复），机器导航清单已建立。
- 本地第一批已接入：唯一导航登记及角色默认拒绝、共享页眉页脚、workspace/search/guide/反馈，以及后台只读聚合和页面归属；customer企业、行业、经济、默认报告、节点研究及已审核2D/3D资源按精确闭包分发。主会话仍在集成，不将当前已审目录等同于全站所有资料的客户许可。
- 经济栏目已接入：basis/cost/returns/scenarios同页切换，保持唯一模型、输入与当前情景；旧hash和cost/tco/economics地址保留。生命周期与稳态年化口径独立，模型引擎段逐字节保持。交付页移除内部抓取派工提示，两身份统一适用性说明，缺少内部元数据不冒充0项缺口。
- 已通过的本地验证：共享壳5种角色场景、真实auth、ui_skin、product_catalog、BOM、scene_framing、technical_atlas、tasks、supply、ops；主会话报告site_workspace/interface/auth/customer首批36项通过，后续权限扩展继续复验并由主会话收口结果。
- 经济验证：datacenter_tco、datacenter_economics、datacenter_cost、dashboard四套原浏览器回归通过；新增economics_navigation真实admin/customer通过，含共享状态、返回历史、旧入口、原校准数值、手机与客户0写请求；test_model 9项通过。适用性提示最终修正后新增浏览器验收再次通过。测试不代表生产回执。
- 默认报告已完成窄分区：封面只模型／口径／源数据版本，q1～q3保留原模型、分类与公式，q4为口径来源说明；内部派工、抓取列、兼容目录及CLI入口移出默认阅读。legacy原正文保留内部授权，客户页面／API均拒绝。research_delivery临时真实双账号通过默认同结构、数值、深字段边界、章节重排、PDF、手机及原15章／SVG／168项目／后台任务断言；run_browser已为CI提供隔离customer签名Cookie。
- 节点研究与内部工作台分开：node只读分类、五类变量、建设阶段、物理值和公式，仅取dashboard安全投影；原采集目标、材料、研究摘要与采用正文留在research-workbench。col=3/5仍聚焦原变量，旧研究别名进入受保护工作台。dashboard真实双账号13路由正文一致，保留55格／6阶段与变压器交期；六种站点权利在工作台验证价格／时间／主体三类目标及规范ID过滤。
- BOM及两个3D场景显式使用交付档案；研究图谱依赖只在内部模式动态加载。纯scene-navigation保留原mesh身份绑定、阶段控件和URL函数，并由原研究模块reexport。3D不取内部modules/products/目标表，覆盖率未知保持禁用；独立预览、实例聚焦、原几何与导出ID保持。BOM别名提供旧场景ID，正式权利链接使用canonical site ID。已许可2D/3D切换按navigation.delivery_pages生成。
- 研究与图册分区验证：scene_bootstrap、research_summary、part_dossier全部10个原场景、technical_atlas、dashboard通过；原问题／证据／关联任务／关系及部件目标断言迁入真实工作台，物理／来源／预览／下载断言保留。默认报告、新闻与BOM布局也通过。权限负责方报告node/BOM69项、3D扩展76项深投影及实际HTTP通过；这些阶段结果不代替最终整合后的全量检查。
- 3D最终本地验证：开启AUTH_ON的独立临时双账号服务运行scene_delivery，七类园区／分层／非物理权利／服务器／机柜／机柜分层／芯片视图通过同相位world matrix、顶点／索引及实例ID对照，实际WebGL帧、独立预览、原图SHA、SVG取证元数据、手机、零私有请求及零资源拒绝。缺失的纯research.css精确许可由主会话补齐后复跑通过。原campus_overview／campus_exploded navigation、server_assembly、rack_assembly、rack_exploded views、chip_package assembly、scene_atlas DPR1/2矩阵通过；整柜类别导出part:rack-frame与完整预览rack/whole分别保留原口径。
- 客户企业/产品边界已完成：七个catalog JSON视图、公司窗口与行情缓存逐层投影；真实双角色六CSV字节一致，财报/型号/附件/筛选/手机和未登记运行企业空态通过。6模板旧壳404引用删除，未登记目录不请求受限API。模型已知容器和报价叶值深审后13预设计算/生命周期一致，真实socket HEAD不发CSV正文。
- 已保存实现checkpoint dcdb7ce8；已合入origin/main的PR900（afcadb42，研究快照增量/网络恢复），当前规范.115，没有覆盖主工作区。治理refresh/check、strict、registry/deliveries通过；完整最终unit、CI和生产回执由主会话收口。
- 实际发布：尚未执行本批最终合并、部署及生产回执核验。

## 尚未完成
- 新增报告、研究原件与模型资源继续逐项审核分发资格，不从已审页面推定许可。当前3D客户模型接口为models=[]，原GLB／HDR／原件清单及后台研究API保持拒绝；不把程序示意几何当作实际项目配置或获得授权的真实模型。
- 完整在线研究审核、普通信息编辑；当前聚合只读入口不能当作这些写入能力完成。
- 真实部署恢复回执、完整历史趋势；未知值继续明确留空，现有滚动统计不倒推历史。
- 最终整合后的完整CI、合并和生产验收；批准目录的客户字段及资源闭包已接通，新增资料须单独审查。

## 下一步
1. 完成当前整合工作树的最终全量unit与完整CI，提交受保护PR；不要重启已结束的设计或另开资料发布队列。
2. 核最终head的治理／严格数据与所有选定CI，通过后正常合并；后台在线写入和历史看板按实际未完范围另批实施。
3. 审阅verification_contract并记录实际测试和未覆盖项；统一治理刷新／检查、严格校验、registry与相关浏览器回归。
4. 最终head通过必过CI并正常合并后，核网站／服务精确版本、匿名／客户／IT、手机与下载回执，据实更新本交接。

## 待用户决定
无新增设计待决。已授权范围继续实施；未建立的历史分析、自动部署回执等按实际能力标识，不编造。

## 入口文件与工具
framework/05_interface_system.md、framework/site_navigation.json、framework/current_state.json、framework/verification_contract.json、docs/CI.md；账本实现为web/pages/ledger.html及web/components/datacenter-model.js；研究阅读／工作台为node.html与research-workbench.html；图册共用part-dossier及纯scene-navigation。新增验收为tests/economics_navigation.cjs、tests/scene_delivery.cjs，run_browser提供隔离双账号。经济截图在本机`/private/tmp/navigation-docs-cehemqfh/economics-qa`，临时文件不进Git。`python3 manage.py governance --refresh`、`governance --check`、`validate --strict`及注册浏览器入口由主会话集中执行、提交和发布。
