# 四队员工启动包：四个独立仓库

2026-10-11：按用户明确决定，替代一个fetchdata仓库四目录的方案。各仓库已经可运行，不要求员工先重建公共框架。这个文档目录与fetchdata-handoff/1合同名仅为兼容路径。

| 员工 | 仓库及可直接执行的说明 | 目的 | 已跑通的第一个样本 |
|---|---|---|---|
| A | [fetchstat](https://github.com/niuroumiantt/fetchstat#readme) | 地域统计、费率、规则及生效时间 | EIA Texas工业YTD电价，1条 |
| B | [fetchfilings](https://github.com/niuroumiantt/fetchfilings#readme) | 法人披露、经营、财务及项目关系 | Microsoft FY2025现金PP&E支出，1条 |
| C | [fetchreports](https://github.com/niuroumiantt/fetchreports#readme) | 研究测量、估算、方法、区间与版本 | LBNL官方发布页方法信息，1条；PDF下载403，数值未提取 |
| D | [fetchquotes](https://github.com/niuroumiantt/fetchquotes#readme) | 配置、地区、条件和时点的公开报价 | Lambda 1x H100 SXM，1条；币种代码/地区留未知 |

四仓库已按用户明确选择公开，使用标准Ubuntu托管Actions；原件、运行库和凭据保持私有。每个仓库包含README、docs/TEAM_TASK.md、docs/DELIVERY_CONTRACT.md、真实冒烟摘要、标准库采集器、适配器和测试。真实原件不在Git。

## 第一次交付

各员工克隆自己的仓库，运行：

```sh
python3 collector.py check-config
python3 -m unittest discover -s tests -v
python3 collector.py run
python3 collector.py verify /命令输出的实际package目录
```

先交一个真实原件、一条人工核对的候选、校验与重放结果即可。后续再扩来源和指标；本目录旧任务书里的较大样本数字是扩展方向，不是首包门槛。每队8项离线测试与一次真实采集/重放已经通过，GitHub检查另取实际回执。

## 交还内容

1. 源码PR、提交SHA、来源配置与运行说明。
2. 私有包：原生HTML/PDF/JSON/CSV等原件、manifest.json、SHA256SUMS、observations.jsonl、errors.jsonl、run-report.json。不要求同一信息收齐所有格式。
3. 测试结果、真实样本核对、重复/修订/缺失/冲突/访问受阻清单。
4. 研究接收/采用/上线回执，取得前明确待联调，不用离线成功冒充。

来源身份与唯一对象线索先行，研究目标可空。未知字段不填零，不明身份不硬配；首次接收由研究端记录，供应方只交实际取得/复用凭据。同口径冲突并列保留。采集和固定字段提取不调用模型。

## 存量资料与节奏

第一步运行已有适配器；第二步加一个来源或指标；第三步联调研究接收，之后指定执行机和调度。不要把整库复制到员工机器。授权端按只读索引筛SHA和原件，员工用 `--existing` + `--provenance` 复用本适配器对应资料，无历史下载时间留空。原件不搬动或删除。

正式采用不等全文阅读或模型用途：原件SHA/字段定位/关键上下文可核，唯一对象确认，逐条审核即可追加。报告全文深读和模型支持是另一个工作，不阻挡已核字段。四队尚未生产接通、未安装周期任务，171项未接通需求不能因建仓库而改为已完成。

完整合同：[共同交付规范](delivery-contract.md)。运行骨架及验收：[开发与验收](implementation-and-acceptance.md)。本批81条存量正式采用及公开字段入口见[对象观测指南](../OBJECT_OBSERVATIONS.md)。
