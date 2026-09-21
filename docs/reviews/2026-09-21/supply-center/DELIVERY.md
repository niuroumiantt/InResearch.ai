# 资料供应中心第一阶段

2026-09-21，用户明确授权方向定稿、提交仓库与网站上线。基线 e029ceb，独立工作树 codex/supply-center；不修改主工作区或 Spark 原件。

## 已采用方向与交付范围

正式规范为 framework/06_acquisition.md，修订原采集职责解释；五视角/产品生态/九主题不变。九类专业供应能力与本地材料渠道分开；能力目录不是创建九个仓库的承诺。fetchspec 与 inews 使用已有 GitHub 仓库，其他能力待逐项落实。

新增 supply.html（真实需求、任务计划）和 supply-demo.html（独立模拟交付验收）。入口从 materials.html 进入。共享主题和登录保持；成员只读，管理员写需求与分配，实习生按现行规则拒绝。真实后台没有交付/采用按钮，未连接清楚说明。

## 权威、写入和消费者

framework/supply_contract.json 随源码发布能力与最小交付协议。workflow.supply 唯一管理计划；interfaces.http 只做认证与参数，supply.js 消费视图。data/raw/supply-center/ledger.json 复用已有私有运行目录，版本锁与操作 UUID 防重复和覆盖，损坏不重建，读取不建目录，静态 URL 不可下载。没有存储布局迁移、新种子或原件搬移。

全部已知消费者：GET/POST /api/supply、supply.html、supply.js、单元测试；演示只有页面局部状态。既有新闻、SEC、GPU、上传与 Spark reader 没有切换到新 API。

## 验证与边界

新增 tests/unit/test_supply.py 覆盖持久化、读取无副作用、UUID 重放与请求冲突、版本竞争、未知问题/供应方拒绝、损坏不覆盖、多供应方、HTTP 权限与私有存储。tests/supply.cjs 加入默认 CI，覆盖真实空态、问题目录、演示分配/部分验收、两风格明暗与窄屏。

现行 05/06/09/CURRENT 与 tests/run_browser.cjs 的改动逐项审阅，verification_contract 的 acquisition/interface/software 对应要求与未覆盖项同步修订。哈希更新只覆盖本批已审阅文件，不重算无关条目。

尚未实现：外部 repo 自动领取执行、交付包/原件传输与逐项验收、Spark 历史批次映射、自动关闭研究问题、生产真实交付和全部材料专业校验。演示不作运行验收证明。已保存计划不等于执行任务。生产与 Spark 版本须分别核对。

## 本地实际验证

- governance --check、validate --strict（0 warnings）、registry（118 对象 / 449 问题）通过。
- 新增供应专项 4 项单元测试通过；浏览器 supply 与 ui_skin 通过，16 个页面的两风格/两明暗/手机检查无页面异常。
- 首次全量测试发现本机 Homebrew Node 缺动态库，以及演示残留宿主专用代码触发界面契约；使用已配置 Node runtime，删除宿主专用代码后重跑。未修改机器软件或弱化测试。
- 真实供应页截图已人工查看；修正详情列不必要的拉伸。
- 远端确认 fetchspec 已存在，AWS 自动部署定时器 active；这不是本批部署已完成的声明。
- 最终全量单元测试：1130 项通过（固定使用已配置 Node，测试期间不改文件）。
- Spark 只读核对：源码 e029ceb4；用户服务 inresearch-news 与 inresearch-reader-publish 显示 failed，常规 reader service 未显示 active。本批不修复、重启或迁移这些已有任务，网站能力登记仍明确未连通统一供应协议。
