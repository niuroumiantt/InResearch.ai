# 合并后的验收映射回退：证据与修复范围

修复前基线 f91859c（PR #169），问题于 #168 发布后的线上验收发现。原发布 bc789d5 的 Python、浏览器和治理检查均已通过；后续合并重新写回旧测试路径，并删掉三个已经生效的事务验收入口。

`manage.py governance --check` 实际报告 7 个缺失的 `tests/unit/test_m4_l2.py` 测试入口，以及 repository_manifest / REPOSITORY_REGISTER 过期。源码中的旧测试文件已按 #168 删除，413 个测试身份已迁入三个文件，不能重新建立一份旧测试来消除报错。

目标职责与权威：verification_contract 登记已复审的正式规则和真实测试；测试当前实现路径以 #168 迁移结果为准，#169 新增分发限制规则与测试继续保留。治理检查既有失败行为正确，不改检查器，不降低门槛，不重新批准测试哈希。

本轮完整文件处置范围：修改 framework/verification_contract.json 的 7 个迁移路径，恢复 3 个被遗漏的事务验收；刷新 framework/repository_manifest.json 和 docs/REPOSITORY_REGISTER.md；新增本审计文件。其余 f91859c 的全部文件保留，尤其保留 1,991 条事实、新指标、分发限制实现与新测试。无源码、测试或研究数据删除与迁移。

公共契约消费者：13 个 scope 的规范验收由 interfaces.verification 与 governance、CI validate 和生产治理检查消费。只更正登记地址和遗漏项，不改变消费者实现；#168 的 76 个公开实现及 413 条测试迁移清单仍见 deep-read/。

验证计划：治理检查从上述失败恢复；运行所有 Python 测试、严格数据校验和 registry；PR CI 通过后发布，在线核对当前合并版本。首次 HTTPS 全量验收在 API 大响应下载中发生 IncompleteRead，同期服务器发生另一次发布；这两个事实不能直接证明因果，须在版本稳定时直连公共 HTTPS 再验证。admin 登录与全部页面在首次检查中已通过，但不能以此代替 API 验收。

实现与验证结果将在对应修复 PR 和发布报告更新；本文件写于修复前，不宣称治理或在线验收已经恢复。
