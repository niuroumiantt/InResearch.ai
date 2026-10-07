# 历史日报来源追补交接（2026-10-07，m5）

## 目标与已定边界
追补 10:34 北京时间基线的 153 条缺网址事件；原 HTML、原引用号、来源冲突及旧事实保留。标题匹配只作查找线索；补链接不授予整条事实核验或 C3 采用。主工作区与 Reader 未重启或改动，本次没有正式容量更新。

## 已完成
- 九批 **153 条**、58 个 SHA 验证包，均有 Spark `daily-receive` 的真实 `indexed_candidate` 回执：9 / 25 / 18 / 12 / 25 / 4 / 23 / 16 / 21 条。143 条恢复原发布网址，10 条采用可靠转载；组合事件可能仅核对明确子项，逐条说明保留未覆盖部分。续补阶段为最后三批 **60 条、31 包**（55 原发布、5 可靠转载）。
- 全台账 318 条均有至少一个实际网址，缺网址 **153 → 60 → 0**。153 条原事件标题、正文、容量观察、318 个既有 ID 和旧网址均逐项对账保留；这个结果只完成缺网址追补，不表示每条全部子项或 C3 核验完成。
- 核对 153 条原 HTML SHA、20 份 sources 侧车、指定 iNews 只读快照全部 404289 条标题及 3968 份正文。快照 SHA：`2865c840546aa9c298ba0bda13b84431d375b3586d3877544d97a8261015e399`。未修改快照。
- 网页 `/supply.html?day=2026-10-07#matching` 于 11:42:37 北京时间发布后实测显示 **0 条事件待找回来源**；“来源齐全的事件”显示 **257**，属于页面去重交付口径，与原始台账 318 不混算。`website-phase2-progress.png` / `website-phase2-gaps.png`、逐项结果、正文/raw SHA 和回执见下列证据目录。
- 接收与 publisher 固定运行版本 `67662877bd8d4f22c3b4cd5ad75d94a5b6fdec18`；仅触发既有 publisher，同步成功。Reader 保持原 checkout `85f5eb9fb1ec8726335500444a546680fb1fce46` 且服务 active。

## 续补核验发现与剩余证据工作
1. 读 `recovery-results.json` / `.md` 的每条 `review`、`body_scope`、`quote_review`，范围说明与实际正文、回执逐一对应。直接 HTTP 失败、200 空模板、web 可读正文和原始 HTML 分开记录；失败壳体不作为正文证据。未批准标题候选仍不绑定。
2. 新恢复的原件包括 GDS、NERC（原 HTML 内的正文模型）、华为、Oracle、纽约州长、SCDES、Micron、SD Guthrie、DMG、LG、Poland CPPC，以及 Aofei/雅安公司 PDF；PDF 相关页已渲染目视核对。韩国中央日报、Blockfusion/CleanSpark 原公告等用公开 web 可读正文取回，原请求失败同时保留。
3. 重要范围差异：GDS 超800MW是整个廊坊安次/香河集群，并非两个新项目合计；DigitalToday 英国瓶颈是网络布线，不是高压电缆；粤西项目实际为广东极算，不支持“疆算入渝”归属；Blockfusion 新租约公告未披露85MW/$1.75b；雅安披露机房建设与千卡组网，不确认商业投运。Loudoun 当时是提出暂停方案、后续拟表决，申请仍可提交；日期差异及旧稿保留，不自动覆盖。
4. 原件层面仍待补：FERC 主裁定 `20260929-3099`（已读 See 并行意见不替代主裁定）；参议院程序投票 roll call；Mesa County 正式暂停令；Ascension 草案；CleanSpark 8-K/租约；NJDEP 执法令、DEQ 拟议令；EPE 拟议裁决；Saudi Exchange/MIS 工作订单。韩国采访、媒体引述市场调查等不冒充完整底层报告。
5. 组合子项仍待补：内蒙古农商银行维保采购、NVIDIA功率预算、KT容量与统计模型、开普敦正式暂停决定、CDC 9月20日 Green Street 原稿、张家口开工、Southaven诉状、泰国班昌水资源论坛、巴淡岛抗议/DayOne报道等。田纳西恢复的是同题同日 The Center Square 转载，另存的9月22日 CDC Wagga 新报不冒充9月20日旧来源。
6. 已补网址不授予整条通过：保留第一阶段 Lancaster 84/156 跨期、Virginia by-right、韩国公司名等说明，以及本阶段日期、计量、主体差异；正式容量更新为0。其余后续研究按现行逐事件核验流程推进。

## 入口与验证
- Spark 永久证据：`/home/spark/.local/share/inresearch.ai/material-reviews/source-recovery-20261007/`；逐事件包：`/home/spark/.local/share/inresearch.ai/incoming/source-recovery-20261007/`。JSON 中 m5 文件路径在永久证据根下有相同相对路径；接收回执提供 Spark 包绝对路径。
- m5 证据：`/Users/m5/.local/state/inresearch.ai/source-recovery-20261007/`；工作树：`/Users/m5/.worktrees/inresearch.ai/historical-source-recovery-20261007`，续补分支 `codex/historical-source-recovery-20261007-continue`。第一阶段 PR #331 已合并为 `65c56ecb294532284c40ed3383ab0563ae16abc6`；`verification-phase1.json` 保存其历史验收，不当作续补结果。
- 现行依据：`framework/06_acquisition.md`、`docs/local_reader/ACQUISITION_OPERATIONS.md`；本次仅新增阶段交接，未修改规范、操作指南、验收测试或验证合同。
- 提交前验证：153 条包 SHA / 原 HTML section 与事件 ID / 回执与权威台账网址逐项对账；`governance --refresh` / `--check`、`validate --strict`（0 warnings）、`registry`、`PYTHONPATH=src python3 -m unittest discover -s tests/unit -p test_daily_bundle.py`（7项通过）。
- 无新增待用户决定事项；缺网址追补已完成，剩余原件与事实核验缺口如上。原件、数据库及运行包不进 Git，证据目录同步到 Spark 永久位置。
