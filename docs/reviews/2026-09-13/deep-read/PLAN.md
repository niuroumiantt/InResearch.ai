# L2 深读用例整改：修改前契约

基线 `465f8defe21e9fe7a7a75ad87bfeaa07e10e2fab`。本文件与全文件清单先独立提交，再修改实现；它是本轮审阅快照，正式执行依据仍为 framework/CURRENT.md。

## 现状证据

`workflow/deep_read.py` 1057 行，混合 9 条 CLI 命令、领域判断、文本相似度、事实事务、缺口维护和来源修复；`test_m4_l2.py` 3617 行混合这些行为与现行指标/数据断言。CLI 直接注册 workflow 模块；纯规则测试也经 L2 转出口调用领域函数。

隔离反例见 baseline.json：有歧义的 pack 前缀选中第一份；受限制材料仍可 record 成功；相同 record 重放写两条完成回执；skip → filled → 重试 skip 重新打开缺口；缓存键回填将 report.pdf 匹配到无关的 report.pdf.backup。没有修改真实材料或运行台账。

## 目标职责与数据权威

| 责任 | 目标实现 | 权威及写入边界 |
|---|---|---|
| 参数、输出、退出码 | interfaces/deep_read.py | 注册名 deep-read 保留，调用显式 DeepRead 用例；接口不写台账 |
| 阅读队列、打包、录入、归属与限制更新 | workflow/deep_read.py 的 DeepRead | 实例显式绑定仓库和运行路径；L1 有效结果沿用 materials.records；归属/限制按外部已看过的版本基线提交 |
| 资料准入、归属缺项与时间排序 | materials/reading_policy.py | 纯规则；queue/pack/record 共用自写材料与限制准入，不以分数代替准入 |
| 文本指纹与近似提示 | materials/text_similarity.py | 原 JSONL 保留；仅提示，不决定材料身份、已读或正式采用 |
| 缺口提出与销账 | workflow/reading_gaps.py | data/metric_gaps.jsonl 唯一台账；完整加锁读改写，原行保留；稳定 gap_id 重放不恢复已销账项；批量销账可重放 |
| 来源候选解析 | knowledge/provenance.py | 明确 SHA 前缀、精确路径及缓存映射链；冲突不猜测，不用文件名/JSON 子串冒充身份；给出可复核计划 |
| 事实与完成回执 | DeepRead.record / remember_read | facts.json 为主提交；l2_read.jsonl 为可重放的完成回执，失败不重复事实；不是 Spark reader 的当前版本，也不授予 C3 |
| 阅读内容与提示格式 | delivery/reading_packet.py | 保留完整文本抽取/指标菜单/问题；新包独立目录，避免不同读取或并发相互覆盖 |

原件 SHA/字节、metrics/data_contract、research_knowledge 的权威不变。未知库外 Python 导入消费者不能靠 Git 穷尽；已知 M4/终端客户使用稳定 `manage.py deep-read` 命令。旧 Python 聚合导入退出，不建立动态代理。旧路径、原件、历史回执/指纹和已经登记的事实不删除。

## 修改顺序和退出标准

1. 提交本计划、反例、全部 591 个基线文件处置和公共函数/消费者清单。
2. 提取纯规则及来源解析，定义 DeepRead 的输入、返回值、事实主提交与回执重放；CLI 只负责协议转换。
3. 缺口提出先持久保存，再记阅读回执；重复提出保持 filled，重复销账返回已完成。提交不确定时读取权威台账再重试，不回滚可见新值。
4. 打包前统一解析全体 L1 的唯一 SHA，歧义不进入抽取；打印 L1 版本。attribute/flag 要求 expected-revision；来源 commit 要求干跑给出的 expected-plan，事实或解析结果变化拒绝旧计划。
5. 迁移所有仓内消费者与测试，取消 workflow 的 argparse/print/sys.exit、领域/交付函数转出口和固定包文件覆盖。拆开测试职责，保留每条既有有效业务断言；因新契约替代的断言逐项说明。
6. 更新正式软件契约、M4 当前说明、注册表与已复审验收映射；执行针对性及全量验证，逐项记录保留和未完成。

完整文件计划见 file-plan.csv；逐公共函数职责见 functions-before.csv；调用和操作引用见 consumers-before.csv。最终提供对应 after/result 表，不能以短文件、测试总数或部署代替这些退出条件。

## 验证与边界

- 真实 CLI：隔离原件/清单 → queue/pack → Claude CLI 阅读 → record → 重放 → 一份完成结果，保留候选/事实/C3 区别。
- 失败：无效/畸形输入、事实提交前/后失败、缺口主提交后回执失败、包发布中断、提交不确定后的重放。
- 独立进程：重复事实提交、相同缺口提出/销账、两位修改者争用同一 L1 版本、并发打包不覆盖。
- 版本：过期 L1 基线拒绝；来源干跑后事实或解析证据变化拒绝；已销账缺口不被旧重试恢复。
- 基线与最终源码、测试、文档、数据/配置、审计证据分别计量；不重写其他工作的研究数据。

未纳入本轮：真实 M4/Spark 台账升级或资料搬迁、所有历史来源补全、两个 3D 场景拆分、全语料语义质量、跨 L2/reader 的统一全文审核记录。这些继续列为未完成，不用本轮模块拆分代替。

实施中补充发现（先记录再修正）：现行 M4 任务卡 §3 明确 L2 接受 L1 ≥7 或用户点名，而基线 MIN_SCORE=8，pack --sha 仍经过默认分数筛选。对齐既有正式规则：自动队列默认 7；点名可绕过优先级分数，但不能绕过成功判定、准入限制或已读/--again 规则。任务卡旧 4000 字预览表述同步到实际最大 6000 字，并明确 L2 回执不自动生成正式评分。这是既有规范的实现对齐，不扩大原件或 C3 权限。
