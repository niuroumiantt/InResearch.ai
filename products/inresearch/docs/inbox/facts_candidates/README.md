# 事实候选（本地会话 → 云端）

本地会话精读材料时，除 summary 外产出的**事实候选**。每条是「某指标 × 某口径 × 某时点 × 某出处的一个数」。

字段：
- `what` 指标是什么、`value`/`value_range` 数值、`unit` 单位
- `locator` **必填**——页码/表号/段落。写不出 locator 说明没真看到那个数，该条不收
- `caliber_note` 口径：含什么不含什么、什么阶段、什么地域
- `source_key` 本地 `cache/text/<key>.txt` 的键，可回原文逐行核对
- `grade` 证据分级（S2=一手/官方披露，S3=区域市场统计）

云端 `pipeline/facts.py` 负责映射 `metric_id` 并入 `data/facts.json`。**本地不自行分配 metric_id。**
