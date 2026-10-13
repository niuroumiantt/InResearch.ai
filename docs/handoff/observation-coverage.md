# 十二观察角度与Abilene离线审计

用户最新要求：先落实可执行清单、报告信息去向检查，用Abilene正文／计算表／附件跑通，候选、未知、异常和未读保留；先给结果再恢复模型，暂不上线。同时评估3／4／5／6与十二角度的职责和两类对象连接。

已完成本地：framework/observation_checklist.json十二角度58检查，逐项引用现有问题、site/model/metric字段和供应队；通用／园区用途分别表达。manage.py observation-audit支持模板、原件及提取文本SHA、原文片段、显式资料单元去向、完整58检查与JSON／HTML结果。不采集、不派工、不执行公式、不采用、不上线；显式资料清单通过不认证语义穷尽。

实际Abilene资料保存在本机应用数据目录：`/Users/m5/.local/share/inresearch.ai/observation-audit/abilene-20261013/`。正文、Timeline HTML、方法、Mortenson和另外四个原生CSV工作表已保存；两份PDF获取超过约三分钟整体预算后终止，未保存完整PDF；原影像未逐张审阅。不要删除原件／回执／audit-input.json／audit-result.json／audit-result.html。Git只保存无原文摘要，见docs/reviews/2026-10-13/observation-coverage/abilene-audit-receipt.json。

本次显式登记132资料单元、155信息去向：124候选（包含表头及通用参数行，不是124独立事实）、2引用原容量观察、23未知、3异常、2未读附件、1未检查影像项。三异常为#REF!、FP16与8-bit表述、公司披露数量标签与整数NVL72配置推导待核。零新增事实采用、零模型参数认证、零发布。CSV值不证明公式正确；通用参数不证明现场设备。

已完成本地8项新增测试及30项相关组合回归，strict零warning、registry引用有效、治理清单核验；HTML在1440和390预览、390无全页横溢。代码未跑全套CI、未合并、未部署；仅离线交付不能代替发布验收。

此前模型草稿的9个文件已按SHA完整隔离保存至同目录`model-draft/files/`，tracked差异为`model-draft/draft.patch`，manifest.json保存每文件SHA。工作树已恢复其HEAD版本，只保留本次离线审计源码。恢复前核当前基线及本次审计规范，再用patch和4个新文件逐项合入；不要直接覆盖新基线。主工作区/Users/m5/code/inresearch.ai原其他任务dirty文件保持未触碰。

建议待讨论：对象（通用类型／真实园区实例）先明确；一棵骨架连接类型、产品、配置与实例；十二角度作跨对象覆盖检查；五类变量组织信息；三账组织经济输出；四问四段保留问题与证据流程；六队按来源机制履约，不为十二角度创建十二队。check_id只作覆盖追踪，不成为新的模型派工ID；正式目标仍复用既有目标及requirement，普通对象信息不强制模型目标。不得机械要求每部件填满58项；不适用需要理由。
