# 上游整合记录

本批实施基线为 52eaad0。实现及相关测试完成后，合并 main 的 84c7bb7；该版本包含 PR #183 的 CLI 测试环境修正及其后已进入 main 的研究处理结果。

相对实施基线新增的 6 个非本批差异逐项登记在 scope.json 的 inherited：`data/facts.json`、`data/metric_gaps.jsonl`、CLI 审计的三份结果及 `tests/unit/test_commands.py`。这些文件原样保留；本批没有把事实增量、缺口、CLI 测试或其统计归为场景资源工作。`framework/verification_contract.json` 与生成清单同时被两侧更新，合并后保留上游 CLI 测试摘要，再加入本批资源契约并由 governance 重建清单。

第一次实施后审计已输出这 6 项为 unplanned，但命令链没有 `set -e`，后续台账提交仍继续。e7284d9 保留该现场。此修正把它们登记为 inherited，并要求重新审计结果 `unplanned=[]` 后才允许后续 PR；不删除、回退或重新归类上游业务数据。
