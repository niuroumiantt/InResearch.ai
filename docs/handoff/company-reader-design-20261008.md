# 企业专栏读者设计交接（更新于 2026-10-08，机器 m5）

## 目标
从用户截图中的 NVIDIA 产品页开始，落实客户交付前台与内部研究后台的分工，完成可交付读者页面并按用户授权上线。

## 已定规则（用户确认过的，不要再问）
- 非管理页面默认按客户读者设计；后台/dashboard 指内部工作区，新入口放 `/admin/`。
- 前台保留官方来源、资料日期、配置/脚注和影响判断的缺失信息；进度、技术版本和来源 SHA 放后台。
- 管理员在前台看到相同读者正文；同一事实投影供两种页面使用，不建第二套事实库。
- 用户于 2026-10-08 明确授权：压紧左侧列表、去掉重复类型说明，其余按设计上线。此授权替代此前仅预览范围。

## 进度
- 独立工作树 `/Users/m5/.codex/worktrees/company-reader-design/inresearch.ai`，分支 `codex/company-reader-design-20261008`；基线 `939a1d55`，原主工作区保持。
- 通用产品页移除覆盖首屏、重复型号表、登记覆盖 iframe 与内部附表；分类、单一型号列表、规格详情、四项比较、产业位置与资料导出已实现。
- `/admin/company.html?c=` 承接同批目录的覆盖/变化、来源身份及研究附表，GET/HEAD 在本地与认证模式均要求真实管理员；读者/普通成员拒绝。
- 公司首页维持既有四部分；Supermicro 独立浏览页仅接入读者导航，原表来源折叠仍保留。未来会员权限与其他内部页地址迁移未做。
- 已通过产品、公司页、公司窗口、真实目录分类/CSV、历史附件、共享外观浏览器回归及界面权限单元测试；严格数据校验通过。治理与登记结果见最终提交。
- 本地预览截图在 `/Users/m5/.local/state/inresearch.ai/design-reviews/company-reader-20261008/`。A10截图使用 2026-10-08 只读取得的生产公开API数据，未导入/改写研究库，不代表改版上线。

## 下一步
1. 左侧密度调整完成后整合最新主线，运行检查与CI。
2. 合并并经 AWS 独立发布服务上线，核对实际版本、读者页面和后台门禁。
3. 逐页落实非企业页面的前后台边界，再处理客户会员与内部成员权限。

## 待用户决定
- 本轮上线已授权，无待审批事项。

## 入口文件与工具
- 现行规范：`framework/05_interface_system.md` 的读者页面/内部工作区章节；替代链 `framework/current_state.json`，验收映射 `framework/verification_contract.json`。
- 页面：`web/pages/product-catalog.html`、`web/pages/admin/company.html`；组件 `product-catalog.js`、`catalog-admin.js`，共享外观 `company.css`。
- 检查：`python3 manage.py governance --check`、`python3 manage.py validate --strict`、`PYTHONPATH=src python3 -m unittest discover -s tests/unit -p test_interface_system.py`。
- 浏览器：`NODE_PATH=/Users/m5/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules node tests/run_browser.cjs product_catalog company_page company_window company_catalog_map catalog_materials ui_skin`。
- 预览服务仅监听127.0.0.1，临时运行根使用系统临时目录，不是生产服务或新事实权威。
