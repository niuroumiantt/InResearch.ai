# 历史事实候选材料

本目录保留早期本地会话提交的原始候选，不是当前事实规范或自动采用入口。

现行格式、指标口径、原文身份和采用规则见 [知识格式](../../../framework/02_knowledge_format.md) 与 [指标目录](../../../framework/metrics.json)。原始候选中的 what、caliber_note、source_key 等字段须经核对和映射；原件及来源冲突保留，不直接转换成已采用结论。

`python3 manage.py deep-read record` 是受校验的录入入口；`python3 manage.py facts` 只审计既有事实，不负责自动映射或写入。Claude CLI、Spark 与其他终端调用同一录入契约。
