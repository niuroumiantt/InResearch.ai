# 13 条现行政策验收矩阵

版本 2026.09.13.4。每行仅列本轮核对的要求，完整测试用例和审阅摘要见 framework/verification_contract.json。所有行都有未覆盖项；表格完整不表示语义验收完整。

| 规范 / scope | 已核对要求 | 未验证 / 未完成 |
|---|---|---|
| framework/00_overview.md / project | 对象身份、视角与产品生态边界、导航闭合 | 全行业知识完整性与各子树的语义 MECE 仍需研究审核；结构覆盖不证明结论正确。 |
| framework/01_data_standards.md / project | C3 支持链资格、定位、数值口径与非数字候选 | 38 条存量事实缺内容 SHA；27 条历史来源未登记；B 审核质量与语义冲突识别不能由机检代替。 |
| framework/02_knowledge_format.md / project | 采用依赖失效重开、候选隔离、被替代正文退出当前报告 | 150 条兼容 Finding 尚未逐条迁入对象证据链；不等同 150 条已采用证据。 |
| framework/03_bom_and_collaboration.md / project | 产品显式映射、稳定身份、任务来源共用 | 真实资产几何与来源许可逐件核对、厂商具体型号规格语义验证未全部完成。 |
| docs/local_reader/SPARK_OPERATIONS.md / project | 备份恢复和停止服务不报健康 | 本轮未连接 Spark/M4 验证服务、模型、备份和容量；历史启动记录不证明当前在线。 |
| framework/CURRENT.md / project | 替代链、规范摘要漂移、测试删除与操作指南身份 | 语义审核仍由人或代理负责；机器无法证明审阅者实际理解每条规范，不能把登记视为穷尽覆盖。 |
| framework/05_interface_system.md / project | 13 页皮肤/明暗/宽度、认证外观、状态保持与安全链接 | 截图矩阵不证明逐像素设计质量、屏幕阅读器体验或真实 3D 帧率；未修改页面的全站设计仍需持续人工体验验收。 |
| framework/06_acquisition.md / project | 原件修订与幂等、题目关联、失败不报成功、价格口径 | 全文翻译、可靠 acquisition→reader handoff、撤回增量、全局限速与 GPU 调度仍未完整实现。 |
| framework/07_product_ecosystems.md / project | 唯一主生态、非装配话题身份、厂商显式映射交互 | 专题综述、型号核验与真实 logo 仍待补充；结构导航不等于研究内容完成。 |
| framework/04_reading_scoring_standard.md / project | 逐篇覆盖、失败恢复、不因换模型重复读、同名新版 | 已完成全文材料显式重读→验收新版本→原子切换的完整事务未实现；图纸/OCR 等受能力及覆盖门槛阻塞的材料不算完成。 |
| docs/M4_TRIAGE_TASK.md / m4-triage | 同字节多路径、失败不盖成功、迟到拒写、移动可恢复 | 真实 M4 50 份当前模型小样及新版执行未验；Spark apply-triage catalog 桥未实现。 |
| framework/08_model_execution.md / project | 配置换模型、模型身份与执行器分离、固定旧任务配方、失败可重试 | Spark/第二实际模型未验证；旧配方自动路由与跨进程/跨项目公平调度未实现；本轮隔离测试不冒充真实推理验收。 |
| framework/09_software_contracts.md / project | 统一写入、跨进程并发、提交前失败与提交后不确定、重放去重 | 非价格/派工/快照的文件消费者仍按 OSError 停止；并非每个多文件流程都有逐阶段恢复验证。deep_read 与 3D 巨型实现还未全部收敛。 |
