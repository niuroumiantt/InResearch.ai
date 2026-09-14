# docs/inbox — 候选与投递记录

本目录只放 Git 可管理的候选记录，不放原件。身份为“候选/外部输入”，不构成现行规则或已采用知识（见 [当前基准](../../framework/CURRENT.md)）。

现行入口：

- **材料原件**：网站“资料”页（`materials.html`）上传 → 私有收件箱 → Spark `manage.py receive` 拉取归档，见 [06 采集规范 §网站资料收件箱](../../framework/06_acquisition.md)。原件、数据库不进 Git。
- **成员投递单**：`submissions/`，运行 `python3 manage.py submissions`，规则见 [submissions/README.md](submissions/README.md)。
- **事实候选**：`facts_candidates/`（历史候选）；正式事实只经 `manage.py deep-read record` 进入 `data/facts.json`。
- **框架提案**：`framework_proposals/`，未采用前保持提案身份。

`digest_drafts/`、`scored_batches/`、`needs_password/`、`path_migrations/`、`project_registry/` 与 `PHASE2_REPORT.md` 是 2026-08 本地会话的遗留记录，只作历史输入，不再有程序消费。
