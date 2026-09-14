# 继承变更

本批以 7f9941a 为清单基线，通过 b7f9536 继承 PR 179 的最终资产测试拆分（db5e7c5）；这些源码/验收变化归前批，scope.inherited 逐项登记。PR 179 随后合并为 dd56dcb，其间主分支 4d01cb2 又增加事实与缺口。本批完成自己的提交后将整合该发布基线，事实原样保留，不计为构图整改研究成果。

已整合发布基线 dd56dcb；facts 当前 2442 条。事实和缺口字节与该主分支完全一致，规范/清单按 2026.09.14.3 刷新。

## 最终同步时并行 PR 180 已合并

待整合 fdbe5e9：包括现有事实修订/指标菜单、L2 同机构/年/体裁在 3 份处理回执均无数字事实时同覆盖组内降权，以及 6 个回归测试。已阅读实际算法与测试：降权仍保留队列、有产出解除，不修改当前全文指针或 C3 采用。排序启发式的语义质量并非本批构图验证内容，继承其明确未验证项；不把 L2 处理回执视为完整阅读。以下路径原样继承后刷新合并清单，不能算成本批研究发现或 UI 代码增长。

- data/facts.json
- docs/DECISIONS.md
- docs/REPOSITORY_REGISTER.md
- framework/indicators.json
- framework/metrics.json
- framework/repository_manifest.json
- framework/verification_contract.json
- reports/verify_queue.md
- src/inresearch/interfaces/deep_read.py
- src/inresearch/workflow/deep_read.py
- tests/unit/test_deep_read.py
