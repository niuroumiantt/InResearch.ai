# 项目全景（2026-09-28）

> ENTRYPOINT。现行规则唯一入口是 [framework/CURRENT.md](../framework/CURRENT.md)；唯一逻辑一页在 [00 研究框架总览](../framework/00_overview.md)。

inresearch.ai 交付一件东西：**一座 AI 数据中心，可以被追问到底**——它怎么建、由什么组成、怎么运转、挣不挣钱，每个数从哪来、缺什么。读者是内部研究者、实习生、六个采集队和对外读者；成果是同一棵树的四种读法与一份可发布快照，全部由同一组权威文件生成。

## 唯一逻辑

一棵树（骨架：数据中心 → 五个系统，IT 分四个 → 链路 → 61 部件 + 软件 + 基型；六条站点权利并列）、三级账（成本、收入、回报，来自唯一的统一经济模型）、四问四段（它值多少 / 由什么组成 / 怎么影响账 / 数据从哪来，缺什么 = 采集 → 事实 → 规则 → 视图倒序）、五类变量（构成、运行、价格、时间、主体）、六队（fetchspec、inews、fetchstat、fetchfilings、fetchreports、fetchquotes）、一个模板（`node.html`）。旧模块 M01–M15 只是兼容属性。

## 目录（四问的全局视图）

- [数据中心](../node.html)：树本身，任一节点 × 五列 × 四问，根节点三级账在上，首屏四个读法入口。
- [账本](../ledger.html)：价格列的展开与三级账，四个视图、三种问法、三个校准锚。
- [爆炸图](../bom.html)：构成列的视觉形式（2D / 3D / 机柜拆解），部件档案与规格库入口。
- [采集](../supply.html)：第四问的全局视图——目标表是唯一任务书，六队卡、热图、派工、收件箱、规格批次、研究问题任务、供应台账。
- [成果](../report.html)：树的可发布快照，四章即四问，可信边界，专题目录。
- 管理（`ops.html`，仅 admin）：用户、管线、录价、生成物新鲜度、工具入口。

## 机器执行入口

骨架 `framework/bom.json`、`site_rights.json`；图谱与问题表由 `manage.py graph` 生成；目标表由 `manage.py targets` 生成；dashboard 快照由 `manage.py dashboard` 生成；登记表两列由 `manage.py nodes` 回填；治理 `manage.py governance`。生成物不进评审，规则表进评审（`framework/verification_contract.json`）。

## 谁配合我们

Spark 与 M4 拉同一提交后重导出快照（问题 ID 不变，旧对象 ID 由接收端折算）；六队只抓目标表上的行，交付走供应中心一个入口；inews 只给事件卡与原件指针。
