# 首页公开与全球园区任务页交接（2026-10-12，m5）

## 目标与已定规则
用户要求仅首页对外，其余页面登录后查看；新增全球既有数据中心普查任务，明确分工、素材方向、现场主体与交付格式。已授权实现和正常发布，无新增人工审批。

- 首页匿名白名单与 GET/HEAD 服务端门禁；完整 API、研究资料与下载登录后按既有角色读取。私有/身份响应禁止共享缓存，部署须清除曾公开的 CDN 缓存。
- `/tasks.html` 提供 P1 普查与六个未分配区域工作包；member/admin分配，intern只更新自己的进展和交付。私有运行台账为 `data/raw/research-tasks/ledger.json`，不进Git。
- 原件及共同 `fetchdata-handoff/1` 六文件优先，OCR可选且保留原件定位。四队交换包尚未自动接通生产；普通园区来源基础登记不要求C3/全文/模型目标，研究结论另核。交付不等于接收、登记、采用或上线。
- 90+GW仅为待校准普查目标；园区/分期、IT/设施/接入/租赁功率和期间耗电不能混算。地图进度复用实际样本，估算/未知/区间独立显示。

## 进度与验收
实现及独立复核完成。任务浏览器已验证真实保存、刷新、409并发保护、实习生权限、下载与320–1440宽度；下载模板填充合成原件后通过现有离线验包。严格校验、registry、asset-check、verify、indicators与治理检查通过；完整单元2460项通过；容器只读根、HTTP/CLI、A→B→A运行数据保留及构建缓存/敏感文件隔离通过。完整浏览器43套/66场景通过且无漏项，最终资料基线另复验research_summary/research_delivery；固定研究回归422项及规范检查13项通过。逐case回执在 `/private/tmp/inresearch-browser-matrix-complete.json`。

GitHub Actions曾返回“an Actions budget is preventing further use”，旧研究PR889的core未启动失败。不得据其他PR已合并推定预算恢复，不跳过本次最终head检查。用户本轮已明确选择“先完成本地验收并保留 PR，稍后上线”。本轮只保留PR，不合并或部署。后续上线仍待最终head全部所需CI通过，AWS既有部署流程实际回执及网站权限核对。

## 下一步与入口
1. 核对本PR最终head所需CI，正常合并；检查最新main资料增量，冲突只按实际来源保留并重建治理清单。
2. 验证AWS镜像SHA、服务及Spark状态；使旧公开CDN缓存失效，再实测匿名首页200、其他HTML登录跳转/完整API401、登录账号可用。
3. 给六包填写真实负责人、机器、模型和截止时间；页面仅协调，不自动启动各队采集。

现行依据：`framework/CURRENT.md`、`framework/current_state.json`、`framework/05_interface_system.md`、`framework/06_acquisition.md`、`framework/verification_contract.json`。
实现：`src/inresearch/workflow/research_tasks.py`、`src/inresearch/interfaces/public.py`、`web/pages/tasks.html`。本机独立工作树：`/Users/m5/.codex/worktrees/private-research-tasks/inresearch.ai`；主工作区未改。
本机临时日志：`/private/tmp/inresearch-private-tasks-*.log`、`/private/tmp/inresearch-browser-matrix-{a,b}.log`。本机预览 `http://127.0.0.1:8765/tasks.html` 仅环回地址使用隔离临时运行根且关闭认证，权限验收另用AUTH_ON服务；重启需重新准备，不能作为生产回执。
