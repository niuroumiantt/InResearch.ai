# Abilene模型参数预览交接（更新于2026-10-14，机器m5）

## 目标
恢复按最新复核区分已有资料、候选、假设和未知的本地园区参数预览，保留来源／推导，异常不自动填参；暂不上线。

## 已定规则
- 用户已授权本地实现，无需再次确认。未获本轮上线授权，不推送、开PR、合并或部署。
- 当前规范05；架构沿00／03／06的对象、观察、问题和应用分工，不回到固定数字总纲。
- `us-tx-abilene`、旧地址、正式事实与通用模型数值保持。只在确认后生成浏览器情景。
- 固定原观察`30103f2fd01b810c-b03dfa2fe924b039`、2026-07-28全园区聚合421MW第三方估算；不是实测。原观察变化拒绝映射，但园区事实仍可读。
- 843预测／1.2GW计划、GPU／冷源／发电／成本候选不自动填参。三异常与五条候选推导保留；来源工作簿公式不执行、不修复。实际未知与计算假设分开。

## 进度
- 在独立工作树`~/.codex/worktrees/navigation-auth-shell/inresearch.ai`的`codex/abilene-parameter-preview`分支完成；主工作区其他任务未触碰。
- 新增site_model_bridges.json与校验／投影，园区详情回链账本预览；来源SHA／定位／阅读范围、已有观察回链、候选、异常、假设／未知和全输入快照齐全。逐层白名单排除未来私有元数据。
- 421MW＋70%负载假设＋PUE1.28假设＋得州0.0707美元/kWh参考：年设施电量3,304,412,160kWh；电量费233,621,939.712美元，未含需量／合同费。模型原校准与公式未改，利润／回报／可行性未验证。
- 81项相关单元及六个受影响浏览器套件通过；strict零warning、registry有效；本地离线实际组件确认、改参、栏目共用输入、JSON导出、浅深色及1440／390／320检查通过，零网络。governance .122的2703文件与验收映射已通过；完整CI与生产未执行。
- 可直接打开`~/.local/share/inresearch.ai/observation-audit/abilene-20261013/model-preview/preview.html`；同目录scenario.json与三张截图。原件、旧草稿、两轮审计保留在上级应用数据目录，不进Git。

## 下一步
1. 用户先审阅本地预览；后续改动从此分支继续。
2. 将来明确授权上线时再对最新基线复核冲突、最终head全部CI与生产版本／服务及页面回执；当前不得自发发布。
3. 扩展其它园区或采用候选须逐字段补范围／时点／主体／模型用途，不按值接近或来源较新覆盖。

## 待用户决定
- 无本地实施阻塞；上线尚未授权。

## 入口文件与工具
- `framework/05_interface_system.md`、`data/site_model_bridges.json`、`docs/reviews/2026-10-14/abilene-model-preview/receipt.json`。
- 导出：`python3 scripts/export_site_model_preview.py --output <本地资料目录>/preview.html`。
- 验证：`python3 manage.py validate --strict`、`registry`、`governance --check`；`PYTHONPATH=src python3 -m unittest tests.unit.test_site_model_bridge tests.unit.test_model`；`node tests/run_browser.cjs site_model_bridge economics_navigation datacenter_cost datacenter_economics datacenter_tco global_campuses`。
- 本机Playwright可设`NODE_PATH=/Users/m5/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules`。
