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
- 已通过产品、公司页、公司窗口、真实目录分类/CSV、历史附件、共享外观浏览器回归及界面权限单元测试；严格数据校验通过。治理与登记结果见最终提交。dashboard回归按现行边界改到真实管理员公司后台，原部件、已采用供电协议与地域表仍有验收，读者部件关系无需读取私有附表。
- 本地预览截图在 `/Users/m5/.local/state/inresearch.ai/design-reviews/company-reader-20261008/`。A10截图使用 2026-10-08 只读取得的生产公开API数据，未导入/改写研究库，不代表改版上线。

## 下一步
- 本轮改版已部署并验收，回执见下方；不重复询问上线授权。
- 后续逐页落实非企业页面的前后台边界，再处理客户会员与内部成员权限；不把本轮授权扩大为全站重做。

## 待用户决定
- 本轮上线已授权，无待审批事项。

## 入口文件与工具
- 现行规范：`framework/05_interface_system.md` 的读者页面/内部工作区章节；替代链 `framework/current_state.json`，验收映射 `framework/verification_contract.json`。
- 页面：`web/pages/product-catalog.html`、`web/pages/admin/company.html`；组件 `product-catalog.js`、`catalog-admin.js`，共享外观 `company.css`。
- 检查：`python3 manage.py governance --check`、`python3 manage.py validate --strict`、`PYTHONPATH=src python3 -m unittest discover -s tests/unit -p test_interface_system.py`。
- 浏览器：`NODE_PATH=/Users/m5/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules node tests/run_browser.cjs product_catalog company_page company_window company_catalog_map catalog_materials ui_skin`。
- 预览服务仅监听127.0.0.1，临时运行根使用系统临时目录，不是生产服务或新事实权威。

## 发布验收

- 本地新增 dashboard 回归通过；PR #360 的 `7390ac50` 四项云端检查全部通过（run `37717345133`），已于2026-10-08 10:30北京时间合并为 `74d5b66c5b7395276e0c3e268f8cf54ddc07434d`。
- AWS 经现有 `inresearch-only-deploy.service` 发布；status=`HEALTHY: 74d5b66c…`，applied与实际运行镜像一致：`sha256:c225f709d56f3e6dbb2adc9395c47c984a0896f1a8fd18e83c7f02b52066eea3`，容器healthy。源码目录 `/srv/sources/inresearch.ai`，运行挂载保持。
- 生产页面、组件与样式共7条实际路由内容SHA全部与审阅实现一致，公网 `/healthz` 正常。NVIDIA目录全部595条 ID 与上线前基线相同。
- Spark只读核对：源码 `3719daae`，Reader/研究核验服务与发布timer均active；进程声明 `READER_RELEASE=3a0408f11c3dd135fc4ad91fbc664ed8ddec1dfe`，不把源码HEAD或声明值冒充进程已重启。本轮不改Spark服务。

- 真实公网Playwright验收：DGX10行、无small重复标签、首行39.98px；四项比较完整矩阵、320/390无页面横溢、管理员与匿名正文相同，脚本运行错误0。后台真实管理员GET200并private/no-store，匿名GET/HEAD302，现有普通账号GET/HEAD403；未新建或改写用户。
- 实际截图/摘要/发布回执在 m5 `/Users/m5/.local/state/inresearch.ai/design-reviews/company-reader-20261008/`；生产会话临时文件验收后移除，不存Git。
- 既有企业模板重复引用不存在的 `/assets/site-shell.js`；实际共享导航通过现行 `/assets/site-skin.js` 加载，功能与内容摘要核对该正式路由。此既有冗余资源清理未纳入本轮，不误称网络资源错误为0。
