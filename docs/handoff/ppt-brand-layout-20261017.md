# PPT 品牌排版交接（2026-10-17，m5）

## 目标与已定规则
用户要求按 marketing 页面和仓库模板，为客户上传的 PPT 只改字体与排版、不改内容；无需模型则直接在页面底部上线，无需再确认。正式规则在 `framework/05_interface_system.md`「PPTX 品牌排版工具」。这是无模型的有界首版：普通文本框字体与可判定常规文字页排版，复杂页保留几何，报告逐页边界。

## 实现与验收
- `delivery/presentation_layout.py` 使用 Python 标准库直接编辑 OOXML；原文、链接、字段、页数与未改 ZIP 成员回读核验。图片、图表、备注、附件等原字节保留，不重新创建整份演示稿。
- 独立 worker、20 MiB／100 页上限、同源检查、并发与频率限制；文件仅在请求内存中，结果 ZIP 包含 PPTX 和逐页说明。匿名与客户可用，客户页面资产只增加精确公开路径，研究权限不扩展。
- 已完成真实 v0.2 模板和合成文稿回读、HTTP worker、浏览器上传／实际下载／模式／坏文件回归。已有全套 3064 单元测试一次通过；后续新增客户入口测试与安全修正以 PR 最终 head CI 为准。
- 本机 LibreOffice 能打开改后 PPTX，但未安装仿宋的渲染出现中文缺字；不能声称字体视觉通过。页面和报告明确要求合法安装字体及人工复核；PDF 暂不提供。

## 发布与继续
代码阶段交接，不作为已部署回执。分支 `codex/ppt-brand-layout`，工作树 `~/.codex/worktrees/ppt-brand-layout/inresearch.ai`；按最终 head 的治理、strict、registry、完整 CI 后合并，不绕过 validate／browser(core)。infra 自动部署后核公网页底、匿名真实上传与 ZIP 内容、服务器源码／应用 SHA 和服务健康，Spark 仅只读核对，不干预研究服务。

测试与诊断暂存 `/tmp/inresearch-ppt-layout/`，生产回执另存 `~/.local/state/inresearch.ai/ppt-brand-layout/`；这些不是源码或客户材料库存。不要迁移／删除主工作区的未跟踪资料。现有品牌文件原字节保持。

## 待用户决定
无阻断决定。若要求 PDF、复杂任意稿件完整换版或嵌入仿宋，需另行落实合法字体、渲染验收及适用版式；不把此次首版表述为已完成这些能力。
