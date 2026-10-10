# BOM 分类更新交接（2026-10-10，m5）

## 目标
一张场景剖面＋分类说明的完整讲解图解释五大类、IT三分与处理器三分，同色贯穿下方分拆并上线。

## 已定规则
- 用户确认水与散热包含完整冷却链；存储下分内存与持久存储。
- 五类顺序：设施、水与散热、电、IT设施、控制与软件。IT分计算、存储、网络；计算处理器CPU/GPU/其他，承载与管理配套单列。
- 新增storage-group父级，保留原memory/storage叶子、全部部件/链路/研究问题ID；父聚合后代叶子恰一次。
- 03「一个骨架」与05「爆炸图2D」是现行源；旧图册来源bom字节保存在docs/design/technical-atlas/bom-source-20260928.json，原技术源SHA及历史审阅不改写。TA35仅加入口的历史页面约束单独保存原字节JSON快照，当前分类替代其整页不变约束，入口与几何继续验。域资产测试核历史源快照并继续核当前实际类别与未改几何。
- 原主工作区的未跟踪研究资料不动。此前上线授权有效，无新增审批。

## 进度与下一步
实现位于附属工作树的codex/bom-classification；版本2026.10.10.70。分类总图与61设备保留，节点矩阵6/11行、IT23类/存储6类汇总；运行严格校验、全单测、相关浏览器与治理检查后提交PR并部署。实际部署/验收回执保存本机~/.local/state/inresearch.ai/releases/bom-classification-20261010/receipt.json；本文不预先声称生产成功。

## 入口
framework/bom.json、src/inresearch/knowledge/skeleton.py、web/pages/bom.html、tests/bom_layout.cjs；旧部署操作见bom-page-layout-20261010.md。

## 用户整图补充
实际参考日报版式；imagegen生成无字剖面，独立SVG添加全部分类并内嵌许可字体，Chromium输出PNG；来源/提示词/字节登记于docs/design/bom-classification。页首直接显示，手机原尺寸平移/适应窗口，可展开文字分类定位。用户明确选择等待GitHub CI并按保护规则发布，不使用管理员合并。原候选7f772cfc的CI不能代表纳入此新图的最终head。
