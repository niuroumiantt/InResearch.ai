# CI 影响范围调整交接 · 2026-10-10

用户授权将小图片与文案分流，并同步规则和必过设置。实现入口 scripts/ci_scope.py，规范唯一源 docs/CI.md。变更机制自身属于 full；上线须保留最终 head 全套 CI 回执后再收敛 GitHub 保护名单，保留 validate/browser (core) 两个已有名称和 app_id 15368、enforce_admins=true。

已同步 AGENTS、CURRENT、DECISIONS、current_state、verification_contract、研究发布器与相关测试。内容路线仅启动 scope、validate、browser(core) 三个作业；已映射页面文字/模型图像加对应浏览器，完整路线保留全部 17 分片和 storage-container。取消同一 PR 旧 head 的运行；手动与每日北京时间 02:17 全套。

发布器两个必过上下文必须成功，可选 skipped 仅在汇总门禁成功时可接受。已有完整四检查 PR 满足保留的两个名字。没有重启 Reader、研究队列或修改正式研究数据。GitHub 保护与实际执行结果另以实测回执补充，不以本文件存在冒充已上线。
