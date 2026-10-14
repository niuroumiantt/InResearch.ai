# Abilene模型预览与前两步复核交接（更新于2026-10-14，机器m5）

## 目标
本地完成共用依赖纠正、设计／许可／图纸逐项原件核对和参数标签细化；保留候选、未知与三异常，暂不上线。

## 已定规则
- 用户已授权本轮前两步，无需再次确认；不推送、开PR、合并或部署。
- 05是模型预览当前规范。原`us-tx-abilene`、旧URL、正式园区观察及通用模型值／公式保持。
- 421MW原观察`30103f2fd01b810c-b03dfa2fe924b039`仍为2026-07-28估算。固定引用不等于来源证据独立：复核工作簿的GPU取整进入容量、算力及方法成本；旧观察网页与新版工作簿SHA不同，旧版公式同一性未证。
- 原件内容经代理核对只表示可人工复核；没有人类批准、现场／产权／最终许可确认或模型采用。三异常、159亿精确系数／舍入未知、未检查余页和影像保留。

## 进度
- 独立工作树`~/.codex/worktrees/navigation-auth-shell/inresearch.ai`，分支`codex/abilene-parameter-preview`；上一阶段本地提交600d3cd6，主工作区未触碰。
- 本轮桥接v3登记13条候选关系、10项原件内容核对、完整83输入标签。GPU／421MW／算力／成本共享上游，断链或伪称独立拒绝；源公式不执行，显式常数算术仅作解释。
- TCEQ官方37589-ac与原附件SHA完全一致，算同一原件镜像；后续37589-tc完整331页只核前四页，余327页未逐页审阅，行政变更候选不覆盖产权或当前主体。BLDG2图内四翼不是四栋，图纸与申请不证明实际安装或最终批准。
- 接入约束0标未知／未设置；等待0年为假设；审批12个月为假设；建设2年为通用参考。地点、费率／法定／历史参考、情景分支和研究口径分别表达。
- 86项相关单元、六套受影响浏览器回归、strict零warning和registry有效。治理.123的2704文件与验收映射通过；完整CI与生产未执行。
- 新预览在`~/.local/share/inresearch.ai/observation-audit/abilene-20261013/model-preview-v2-20261014/preview.html`，同目录scenario.json和截图。上一稿model-preview目录完整保留。
- 新审计／原件／官方接收回执在`dependency-review-20261014/`；169资料单元、192去向（含表头／参数），160候选、2已有观察、23未知、3异常、4未检查项；零新增正式采用／人类确认／模型认证／发布。原件不进Git。

## 下一步
1. 用户查看新预览与逐项原件内容核对，再决定后续阶段。当前没有获准推进现场能耗取证、完整成本或收入回报采集，也没有发布授权。
2. 人工确认须分别处理来源内容和模型用途；不能点确认就把候选改成现场事实。需要时追旧版工作簿、成本系数／舍入，澄清精度及GPU型号／单位。
3. 将来授权上线时复核最新基线、最终head全部CI及实际生产版本／服务／页面回执；当前不得自发发布。

## 待用户决定
- 无本地实施阻塞；后续阶段和上线尚未授权。

## 入口文件与工具
- `framework/05_interface_system.md`、`data/site_model_bridges.json`、`docs/reviews/2026-10-14/abilene-dependencies/receipt.json`。
- `python3 scripts/export_site_model_preview.py --output <本地资料目录>/preview.html`。
- `python3 manage.py observation-audit --input <audit-input.json> --output <新结果.json> --html <新结果.html>`；禁止覆盖输入／原件。
- `python3 manage.py validate --strict`、`registry`、`governance --check`；`PYTHONPATH=src python3 -m unittest tests.unit.test_site_model_bridge tests.unit.test_model`；`node tests/run_browser.cjs site_model_bridge economics_navigation datacenter_cost datacenter_economics datacenter_tco global_campuses`。
- 本机Playwright：`NODE_PATH=/Users/m5/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules`。
