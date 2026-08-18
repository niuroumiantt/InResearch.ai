# 回传：9 条厂商组 ID 改名（请对方项目同步）

**发出方**：InResearch.ai（本库）　**日期**：2026-08-18　**紧要程度**：高——不同步则 ID 锚点断裂

## 为什么要改

两个项目的唯一锚点是 `company_id` 与 `bom_part_id`。对齐包 `companies_patch.json` 里有
9 条 `is_group: true` 的厂商组，导出时中文组名被 kebab 化**塌缩成了同一个 ID**
（多组共用 `group` 或近似串），违反主键唯一，本库无法入库。

本库已单方面改名后落库（决策记录：DECISIONS 会话续 45 / B5②）。**请对方项目在下次导出前
按下表改，否则整文件替换时会把旧 ID 带回来，两边锚点对不上。**

## 映射表（旧 ID 塌缩值 → 新 ID）

| 新 company_id | 覆盖厂商 |
|---|---|
| `cn-kunpeng-feiteng-server-group` | 长城、宝德、神州鲲泰、湘江鲲鹏、超越申泰、黄河 |
| `cn-dpu-group` | 中科驭数、云豹智能、大禹智芯 |
| `cn-optics-group` | 索尔思、海信宽带、剑桥科技、铭普 |
| `cn-genset-group` | 潍柴、玉柴、科泰电源 |
| `cn-dry-transformer-group` | 金盘科技、特锐德、白云电器 |
| `cn-cooling-group` | 同飞股份、佳力图、依米康、海悟 |
| `cn-rack-group` | 图腾、一舟、威腾电气 |
| `cn-security-group` | 海康威视、大华 |
| `cn-inspection-robot-group` | 国自机器人、优必选等 |

## 另外两条顺带核对项

1. **导出条数对不上**：`companies_patch.json` 自述 160 条，实际 166 条（含上述 9 条 group）
   ——请核对导出脚本的计数逻辑。
2. **`coldplate` 挂着 motivair 但公司表里没有**：本库已补最小记录（cooling / M08 / 待核验），
   如对方库也有此节点请同步补齐。

## 对接约定（不变）

- 锚点只有 `company_id` + `bom_part_id` 两个 ID；`bom.json` 是 `bom_part_id` 的唯一定义源。
- 对方每次目录更新，重新投递 `products.json` 整文件替换。
- 爬完交 `library_index.json`（清单 + URL + 日期），爆炸图最深处链到对方文件。
