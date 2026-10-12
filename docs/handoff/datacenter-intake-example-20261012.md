# 公开任务与 SG3 交付样例交接（2026-10-12，m5）

## 目标与已定规则

匿名显示首页与任务；登录后按原角色显示其他页面。任务可看目标、范围、状态和显式公开样例，内部协调字段及写入仍认证。完成一个真实投运园区的资料到地图链路，不把本地执行、CI、部署或公网显示相互冒充。用户已选择 CI 预算不足时完成本地验收并保留 PR，稍后上线。

## 实际进度

- 源码在 Codex 工作树 `~/.codex/worktrees/private-research-tasks/inresearch.ai`，分支 `codex/datacenter-intake-example`；主工作区的其他任务未移动。
- 选 Equinix SG3，六份实际原件含运营商开业声明、施工集团目录、CDP 坐标表与三份 SGX 披露。实际接收六个 SHA，重放零新增且首次接收时钟不变；未运行 Reader 全文任务、OCR 或外部模型调用。
- 私有材料根 `~/.local/share/inresearch.ai/task-examples/equinix-sg3-20261012/`。`acquisition-log.json`、`receiver-summary.json`、`receiver-receipts/` 保留真实来源与失败；原件不进 Git。定向提取不声称全文 C3。
- 普通来源登记使用独立 authoring 副本与隔离 runtime；园区、历史产权、开发/运营、施工参与及历史客户分开。IT/设施/电网 MW 和年度电量未披露，保持未知；原始坐标是自报点位，非测绘边界。
- 本地全部 2,482 项单测通过；完整浏览器与实际样例页面回执单独保存。GitHub Actions 仍明确返回预算不足，不能据本地通过宣称 CI 或生产已成功。

## 部署接续

1. 先核 PR 的最终 head、必过 CI 与当前 main。不得绕过门禁；继续已有 AWS 部署流程，不另启研究发布器。
2. 代码上线后，在现有持久运行根用 `source-publish install` 安装私有 `source-publication.json`，保留旧 registry 备份及首次/重放收据。只安装该园区和本包公司，不导入 authoring 的整份旧库。
3. 安装 `installed-example/` 到运行 `data/raw/research-task-examples/equinix-sg3-20261012/`。文件按 `example.json` allowlist、大小、SHA 校验；未声明 public 的文件默认仅登录下载。不要公开接收器目录或私有完整回执。
4. 核实际匿名首页/任务、登录后其他页、真实样例下载字节、SG3 公网地图点及项目档案。点位新增一，已知 IT GW 增量为零；生产阶段仅在真实回执后改完成。核网站与 Spark 版本/服务，保留原件和未合并分支。

## 入口

规则入口 `framework/CURRENT.md`；权限 `interfaces/public.py`；样例 `workflow/research_task_examples.py`；普通登记/发布 `workflow/source_statements.py` 与 `delivery/source_publication.py`。状态与审计放 `~/.local/state/inresearch.ai/`，不把源码清单当原件或运行库盘点。
