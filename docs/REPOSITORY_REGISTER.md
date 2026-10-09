# 在册源码与记录清单

> GENERATED · 由 `python3 manage.py governance --refresh` 从 Git 在册与本次新增路径生成。当前基准：2026.10.09.29。

现行依据见 [CURRENT](../framework/CURRENT.md)。本清单覆盖每个在册文件；对应内容 SHA-256、大小和记录集合结构见 `framework/repository_manifest.json`。修改内容或新增文件须重新生成并通过 CI。

范围仅限 Git 源码和记录，不扫描百度网盘、Spark 原件/SQLite、密钥、忽略文件或外置盘。记录集合分别计数，不能相加当作唯一文档数、已读数或研究完成度。内容摘要用于发现改动，不表示逐条事实已核验。

在册文件：1628。

| 身份 | 文件数 |
|---|---|
| 静态资源 | 110 |
| 候选与外部输入 | 146 |
| 已采用设计依据 | 1 |
| 现行入口 | 4 |
| 生成物 | 13 |
| 历史快照 | 317 |
| 运行代码 | 313 |
| 现行规范 | 15 |
| 项目配置 | 357 |
| 兼容研究记录 | 16 |
| 已退役入口 | 3 |
| 在册数据/索引 | 29 |
| 配套说明 | 152 |
| 测试 | 152 |

## 在册记录集合

| 文件 | 集合 | 条数 |
|---|---|---|
| `.claude/launch.json` | configurations | 1 |
| `data/assignments.json` | statuses | 5 |
| `data/assignments.json` | records | 0 |
| `data/brief.json` | sec | 16 |
| `data/brief.json` | review_marked | 23 |
| `data/companies.json` | records | 257 |
| `data/company_disclosures.json` | records | 1 |
| `data/contracts.json` | records | 8 |
| `data/dashboard.json` | stages | 6 |
| `data/dashboard.json` | system_nodes | 8 |
| `data/dashboard.json` | parent_systems | 1 |
| `data/dashboard.json` | factors | 26 |
| `data/datacenter_model.json` | groups | 5 |
| `data/datacenter_model.json` | anchors | 2 |
| `data/datacenter_model.json` | sensitivity_drivers | 12 |
| `data/datacenter_model.json` | benchmark_series | 43 |
| `data/event_cards.json` | records | 42 |
| `data/facts.json` | records | 7849 |
| `data/policies.json` | records | 2 |
| `data/prices.json` | records | 512 |
| `data/product_docs_plan.csv` | rows | 801 |
| `data/products.json` | records | 175 |
| `data/projects.json` | records | 126 |
| `data/research_knowledge.json` | documents | 27 |
| `data/research_knowledge.json` | evidence | 168 |
| `data/research_knowledge.json` | statements | 166 |
| `data/research_knowledge.json` | answers | 0 |
| `data/schema/company.schema.json` | required | 6 |
| `data/schema/contract.schema.json` | required | 7 |
| `data/schema/fact.schema.json` | required | 9 |
| `data/schema/policy.schema.json` | required | 7 |
| `data/schema/price.schema.json` | required | 6 |
| `data/schema/products.schema.json` | required | 9 |
| `data/schema/project.schema.json` | required | 7 |
| `data/schema/source.schema.json` | required | 5 |
| `data/schema/submission.schema.json` | required | 4 |
| `data/sources.json` | records | 74 |
| `docs/CN_PROJECT_ARCHIVES.csv` | rows | 40 |
| `docs/LIBRARY_SCORES.csv` | rows | 13664 |
| `docs/archive/2026-10-06/worktree-snapshots/patches.json` | git_diff_options | 3 |
| `docs/archive/2026-10-06/worktree-snapshots/patches.json` | patches | 3 |
| `docs/design/technical-atlas/TA-01/acceptance-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-01/acceptance-v1.json` | technical_sources | 3 |
| `docs/design/technical-atlas/TA-01/acceptance-v1.json` | unknowns | 3 |
| `docs/design/technical-atlas/TA-01/acceptance-v1.json` | visual_review | 5 |
| `docs/design/technical-atlas/TA-01/acceptance-v1.json` | page_entries | 3 |
| `docs/design/technical-atlas/TA-01/acceptance-v1.json` | artifacts | 8 |
| `docs/design/technical-atlas/TA-01/labels-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-01/labels-v1.json` | labels | 9 |
| `docs/design/technical-atlas/TA-01/labels-v1.json` | leaders | 7 |
| `docs/design/technical-atlas/TA-01/publication-20261008.json` | asset_checks | 4 |
| `docs/design/technical-atlas/TA-02/acceptance-v1.json` | references | 2 |
| `docs/design/technical-atlas/TA-02/acceptance-v1.json` | implementation_at_review | 7 |
| `docs/design/technical-atlas/TA-02/acceptance-v1.json` | browser_checks | 7 |
| `docs/design/technical-atlas/TA-02/acceptance-v1.json` | local_visual_evidence | 4 |
| `docs/design/technical-atlas/TA-02/acceptance-v1.json` | remaining_work | 3 |
| `docs/design/technical-atlas/TA-02/publication-20261008.json` | public_source_bytes | 6 |
| `docs/design/technical-atlas/TA-02/publication-20261008.json` | browser_evidence | 2 |
| `docs/design/technical-atlas/TA-02/publication-20261008.json` | found_during_public_review | 2 |
| `docs/design/technical-atlas/TA-03/acceptance-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-03/acceptance-v1.json` | references | 2 |
| `docs/design/technical-atlas/TA-03/acceptance-v1.json` | technical_sources | 2 |
| `docs/design/technical-atlas/TA-03/acceptance-v1.json` | unknowns | 3 |
| `docs/design/technical-atlas/TA-03/acceptance-v1.json` | artifacts | 7 |
| `docs/design/technical-atlas/TA-03/acceptance-v1.json` | browser_checks | 2 |
| `docs/design/technical-atlas/TA-03/labels-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-03/labels-v1.json` | labels | 8 |
| `docs/design/technical-atlas/TA-03/labels-v1.json` | leaders | 8 |
| `docs/design/technical-atlas/TA-03/publication-20261008.json` | public_source_bytes | 3 |
| `docs/design/technical-atlas/TA-03/publication-20261008.json` | browser_evidence | 5 |
| `docs/design/technical-atlas/TA-03/publication-20261008.json` | limits | 3 |
| `docs/design/technical-atlas/TA-04/acceptance-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-04/acceptance-v1.json` | references | 2 |
| `docs/design/technical-atlas/TA-04/acceptance-v1.json` | technical_sources | 3 |
| `docs/design/technical-atlas/TA-04/acceptance-v1.json` | unknowns | 3 |
| `docs/design/technical-atlas/TA-04/acceptance-v1.json` | artifacts | 9 |
| `docs/design/technical-atlas/TA-04/acceptance-v1.json` | browser_checks | 2 |
| `docs/design/technical-atlas/TA-04/labels-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-04/labels-v1.json` | labels | 8 |
| `docs/design/technical-atlas/TA-04/labels-v1.json` | leaders | 8 |
| `docs/design/technical-atlas/TA-04/preparation-v1.json` | primary_sources | 2 |
| `docs/design/technical-atlas/TA-04/preparation-v1.json` | actual_source_observations | 2 |
| `docs/design/technical-atlas/TA-04/publication-20261008.json` | public_source_bytes | 3 |
| `docs/design/technical-atlas/TA-04/publication-20261008.json` | public_download_head | 2 |
| `docs/design/technical-atlas/TA-04/publication-20261008.json` | browser_evidence | 5 |
| `docs/design/technical-atlas/TA-04/publication-20261008.json` | public_probe_history | 1 |
| `docs/design/technical-atlas/TA-04/publication-20261008.json` | limits | 4 |
| `docs/design/technical-atlas/TA-05/acceptance-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-05/acceptance-v1.json` | references | 2 |
| `docs/design/technical-atlas/TA-05/acceptance-v1.json` | technical_sources | 3 |
| `docs/design/technical-atlas/TA-05/acceptance-v1.json` | unknowns | 3 |
| `docs/design/technical-atlas/TA-05/acceptance-v1.json` | artifacts | 8 |
| `docs/design/technical-atlas/TA-05/acceptance-v1.json` | browser_checks | 2 |
| `docs/design/technical-atlas/TA-05/labels-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-05/labels-v1.json` | labels | 8 |
| `docs/design/technical-atlas/TA-05/labels-v1.json` | leaders | 8 |
| `docs/design/technical-atlas/TA-05/preparation.json` | primary_sources | 2 |
| `docs/design/technical-atlas/TA-05/preparation.json` | unknowns | 1 |
| `docs/design/technical-atlas/TA-05/publication-20261009.json` | public_source_bytes | 3 |
| `docs/design/technical-atlas/TA-05/publication-20261009.json` | public_download_head | 2 |
| `docs/design/technical-atlas/TA-05/publication-20261009.json` | browser_evidence | 5 |
| `docs/design/technical-atlas/TA-05/publication-20261009.json` | limits | 5 |
| `docs/design/technical-atlas/TA-06/acceptance-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-06/acceptance-v1.json` | references | 2 |
| `docs/design/technical-atlas/TA-06/acceptance-v1.json` | technical_sources | 2 |
| `docs/design/technical-atlas/TA-06/acceptance-v1.json` | unknowns | 4 |
| `docs/design/technical-atlas/TA-06/acceptance-v1.json` | artifacts | 7 |
| `docs/design/technical-atlas/TA-06/acceptance-v1.json` | browser_checks | 2 |
| `docs/design/technical-atlas/TA-06/labels-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-06/labels-v1.json` | labels | 9 |
| `docs/design/technical-atlas/TA-06/labels-v1.json` | leaders | 9 |
| `docs/design/technical-atlas/TA-06/preparation.json` | primary_sources | 1 |
| `docs/design/technical-atlas/TA-06/preparation.json` | source_access_failures | 1 |
| `docs/design/technical-atlas/TA-06/preparation.json` | unknowns | 1 |
| `docs/design/technical-atlas/TA-06/publication-20261009.json` | public_source_bytes | 3 |
| `docs/design/technical-atlas/TA-06/publication-20261009.json` | public_download_head | 2 |
| `docs/design/technical-atlas/TA-06/publication-20261009.json` | public_actions | 2 |
| `docs/design/technical-atlas/TA-06/publication-20261009.json` | browser_evidence | 9 |
| `docs/design/technical-atlas/TA-06/publication-20261009.json` | public_anonymous_research | 2 |
| `docs/design/technical-atlas/TA-06/publication-20261009.json` | limits | 6 |
| `docs/design/technical-atlas/TA-07/acceptance-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-07/acceptance-v1.json` | references | 2 |
| `docs/design/technical-atlas/TA-07/acceptance-v1.json` | technical_sources | 2 |
| `docs/design/technical-atlas/TA-07/acceptance-v1.json` | unknowns | 3 |
| `docs/design/technical-atlas/TA-07/acceptance-v1.json` | artifacts | 7 |
| `docs/design/technical-atlas/TA-07/acceptance-v1.json` | browser_checks | 2 |
| `docs/design/technical-atlas/TA-07/labels-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-07/labels-v1.json` | labels | 8 |
| `docs/design/technical-atlas/TA-07/labels-v1.json` | leaders | 8 |
| `docs/design/technical-atlas/TA-07/preparation.json` | references_to_pass | 2 |
| `docs/design/technical-atlas/TA-07/preparation.json` | primary_sources | 2 |
| `docs/design/technical-atlas/TA-07/preparation.json` | unknowns | 3 |
| `docs/design/technical-atlas/TA-07/publication-20261009.json` | public_source_bytes | 3 |
| `docs/design/technical-atlas/TA-07/publication-20261009.json` | public_actions | 1 |
| `docs/design/technical-atlas/TA-07/publication-20261009.json` | browser_evidence | 5 |
| `docs/design/technical-atlas/TA-07/publication-20261009.json` | public_anonymous_research | 1 |
| `docs/design/technical-atlas/TA-07/publication-20261009.json` | limits | 5 |
| `docs/design/technical-atlas/TA-08/acceptance-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-08/acceptance-v1.json` | references | 1 |
| `docs/design/technical-atlas/TA-08/acceptance-v1.json` | technical_sources | 3 |
| `docs/design/technical-atlas/TA-08/acceptance-v1.json` | unknowns | 3 |
| `docs/design/technical-atlas/TA-08/acceptance-v1.json` | artifacts | 7 |
| `docs/design/technical-atlas/TA-08/acceptance-v1.json` | browser_checks | 2 |
| `docs/design/technical-atlas/TA-08/acceptance-v1.json` | issues_resolved | 2 |
| `docs/design/technical-atlas/TA-08/acceptance-v1.json` | source_access_limits | 2 |
| `docs/design/technical-atlas/TA-08/labels-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-08/labels-v1.json` | labels | 8 |
| `docs/design/technical-atlas/TA-08/labels-v1.json` | leaders | 8 |
| `docs/design/technical-atlas/TA-08/preparation-v1.json` | references_to_pass | 1 |
| `docs/design/technical-atlas/TA-08/preparation-v1.json` | primary_sources | 3 |
| `docs/design/technical-atlas/TA-08/preparation-v1.json` | unknowns | 3 |
| `docs/design/technical-atlas/TA-08/publication-20261009.json` | public_source_bytes | 4 |
| `docs/design/technical-atlas/TA-08/publication-20261009.json` | browser_evidence | 11 |
| `docs/design/technical-atlas/TA-08/publication-20261009.json` | limits | 6 |
| `docs/design/technical-atlas/TA-09/acceptance-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-09/acceptance-v1.json` | references | 1 |
| `docs/design/technical-atlas/TA-09/acceptance-v1.json` | technical_sources | 3 |
| `docs/design/technical-atlas/TA-09/acceptance-v1.json` | source_access_limits | 2 |
| `docs/design/technical-atlas/TA-09/acceptance-v1.json` | unknowns | 3 |
| `docs/design/technical-atlas/TA-09/acceptance-v1.json` | artifacts | 7 |
| `docs/design/technical-atlas/TA-09/acceptance-v1.json` | browser_checks | 2 |
| `docs/design/technical-atlas/TA-09/acceptance-v1.json` | issues_resolved | 5 |
| `docs/design/technical-atlas/TA-09/labels-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-09/labels-v1.json` | labels | 10 |
| `docs/design/technical-atlas/TA-09/labels-v1.json` | leaders | 9 |
| `docs/design/technical-atlas/TA-09/preparation-v1.json` | references_to_pass | 1 |
| `docs/design/technical-atlas/TA-09/preparation-v1.json` | primary_sources | 3 |
| `docs/design/technical-atlas/TA-09/preparation-v1.json` | access_limits | 2 |
| `docs/design/technical-atlas/TA-09/preparation-v1.json` | unknowns | 3 |
| `docs/design/technical-atlas/TA-09/publication-20261009.json` | public_source_bytes | 4 |
| `docs/design/technical-atlas/TA-09/publication-20261009.json` | browser_evidence | 11 |
| `docs/design/technical-atlas/TA-09/publication-20261009.json` | limits | 7 |
| `docs/design/technical-atlas/TA-10/acceptance-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-10/acceptance-v1.json` | references | 1 |
| `docs/design/technical-atlas/TA-10/acceptance-v1.json` | technical_sources | 5 |
| `docs/design/technical-atlas/TA-10/acceptance-v1.json` | source_access_limits | 0 |
| `docs/design/technical-atlas/TA-10/acceptance-v1.json` | unknowns | 3 |
| `docs/design/technical-atlas/TA-10/acceptance-v1.json` | artifacts | 9 |
| `docs/design/technical-atlas/TA-10/acceptance-v1.json` | browser_checks | 2 |
| `docs/design/technical-atlas/TA-10/acceptance-v1.json` | issues_resolved | 2 |
| `docs/design/technical-atlas/TA-10/labels-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-10/labels-v1.json` | labels | 10 |
| `docs/design/technical-atlas/TA-10/labels-v1.json` | leaders | 9 |
| `docs/design/technical-atlas/TA-10/preparation-v1.json` | primary_sources | 5 |
| `docs/design/technical-atlas/TA-10/preparation-v1.json` | access_limits | 0 |
| `docs/design/technical-atlas/TA-10/preparation-v1.json` | unknowns | 3 |
| `docs/design/technical-atlas/TA-10/preparation-v1.json` | rejected_iterations | 2 |
| `docs/design/technical-atlas/TA-10/publication-20261009.json` | public_source_bytes | 4 |
| `docs/design/technical-atlas/TA-10/publication-20261009.json` | browser_evidence | 11 |
| `docs/design/technical-atlas/TA-10/publication-20261009.json` | limits | 8 |
| `docs/design/technical-atlas/TA-10/publication-20261009.json` | ci_observations | 1 |
| `docs/design/technical-atlas/TA-11/acceptance-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-11/acceptance-v1.json` | references | 1 |
| `docs/design/technical-atlas/TA-11/acceptance-v1.json` | technical_sources | 6 |
| `docs/design/technical-atlas/TA-11/acceptance-v1.json` | source_access_limits | 1 |
| `docs/design/technical-atlas/TA-11/acceptance-v1.json` | unknowns | 5 |
| `docs/design/technical-atlas/TA-11/acceptance-v1.json` | artifacts | 10 |
| `docs/design/technical-atlas/TA-11/acceptance-v1.json` | browser_checks | 6 |
| `docs/design/technical-atlas/TA-11/acceptance-v1.json` | issues_resolved | 8 |
| `docs/design/technical-atlas/TA-11/labels-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-11/labels-v1.json` | labels | 12 |
| `docs/design/technical-atlas/TA-11/labels-v1.json` | leaders | 12 |
| `docs/design/technical-atlas/TA-11/preparation-v1.json` | primary_sources | 6 |
| `docs/design/technical-atlas/TA-11/preparation-v1.json` | access_limits | 1 |
| `docs/design/technical-atlas/TA-11/preparation-v1.json` | rejected_iterations | 3 |
| `docs/design/technical-atlas/TA-11/preparation-v1.json` | boundaries | 5 |
| `docs/design/technical-atlas/TA-11/publication-20261009.json` | public_source_bytes | 6 |
| `docs/design/technical-atlas/TA-11/publication-20261009.json` | browser_evidence | 26 |
| `docs/design/technical-atlas/TA-11/publication-20261009.json` | limits | 8 |
| `docs/design/technical-atlas/TA-12/acceptance-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-12/acceptance-v1.json` | references | 2 |
| `docs/design/technical-atlas/TA-12/acceptance-v1.json` | technical_sources | 2 |
| `docs/design/technical-atlas/TA-12/acceptance-v1.json` | reviewed_differences | 5 |
| `docs/design/technical-atlas/TA-12/acceptance-v1.json` | unknowns | 3 |
| `docs/design/technical-atlas/TA-12/acceptance-v1.json` | browser_checks | 4 |
| `docs/design/technical-atlas/TA-12/acceptance-v1.json` | issues_resolved | 4 |
| `docs/design/technical-atlas/TA-12/acceptance-v1.json` | artifacts | 6 |
| `docs/design/technical-atlas/TA-12/labels-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-12/labels-v1.json` | labels | 15 |
| `docs/design/technical-atlas/TA-12/labels-v1.json` | leaders | 12 |
| `docs/design/technical-atlas/TA-12/preparation-v1.json` | reference_identity | 2 |
| `docs/design/technical-atlas/TA-12/preparation-v1.json` | primary_sources_rechecked | 2 |
| `docs/design/technical-atlas/TA-12/preparation-v1.json` | reviewed_differences | 5 |
| `docs/design/technical-atlas/TA-12/preparation-v1.json` | not_claimed | 3 |
| `docs/design/technical-atlas/TA-12/publication-20261009.json` | correction_ci_official_cause | 1 |
| `docs/design/technical-atlas/TA-12/publication-20261009.json` | boundaries | 5 |
| `docs/design/technical-atlas/TA-36/acceptance-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-36/acceptance-v1.json` | references | 3 |
| `docs/design/technical-atlas/TA-36/acceptance-v1.json` | technical_sources | 2 |
| `docs/design/technical-atlas/TA-36/acceptance-v1.json` | unknowns | 2 |
| `docs/design/technical-atlas/TA-36/acceptance-v1.json` | artifacts | 6 |
| `docs/design/technical-atlas/TA-36/labels-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-36/labels-v1.json` | labels | 7 |
| `docs/design/technical-atlas/TA-36/labels-v1.json` | leaders | 7 |
| `docs/design/technical-atlas/TA-36/publication-20261008.json` | public_source_bytes | 2 |
| `docs/design/technical-atlas/TA-36/publication-20261008.json` | browser_evidence | 5 |
| `docs/design/technical-atlas/TA-36/publication-20261008.json` | limits | 1 |
| `docs/design/technical-atlas/TA-37/acceptance-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-37/acceptance-v1.json` | references | 2 |
| `docs/design/technical-atlas/TA-37/acceptance-v1.json` | technical_sources | 3 |
| `docs/design/technical-atlas/TA-37/acceptance-v1.json` | unknowns | 2 |
| `docs/design/technical-atlas/TA-37/acceptance-v1.json` | artifacts | 6 |
| `docs/design/technical-atlas/TA-37/labels-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-37/labels-v1.json` | labels | 7 |
| `docs/design/technical-atlas/TA-37/labels-v1.json` | leaders | 7 |
| `docs/design/technical-atlas/TA-37/publication-20261008.json` | public_source_bytes | 2 |
| `docs/design/technical-atlas/TA-37/publication-20261008.json` | browser_evidence | 5 |
| `docs/design/technical-atlas/TA-37/publication-20261008.json` | limits | 1 |
| `docs/design/technical-atlas/TA-38/acceptance-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-38/acceptance-v1.json` | references | 1 |
| `docs/design/technical-atlas/TA-38/acceptance-v1.json` | technical_sources | 2 |
| `docs/design/technical-atlas/TA-38/acceptance-v1.json` | unknowns | 2 |
| `docs/design/technical-atlas/TA-38/acceptance-v1.json` | artifacts | 8 |
| `docs/design/technical-atlas/TA-38/labels-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-38/labels-v1.json` | labels | 7 |
| `docs/design/technical-atlas/TA-38/labels-v1.json` | leaders | 7 |
| `docs/design/technical-atlas/TA-38/publication-20261008.json` | public_source_bytes | 2 |
| `docs/design/technical-atlas/TA-38/publication-20261008.json` | browser_evidence | 5 |
| `docs/design/technical-atlas/TA-38/publication-20261008.json` | limits | 2 |
| `docs/design/technical-atlas/TA-39/acceptance-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-39/acceptance-v1.json` | references | 2 |
| `docs/design/technical-atlas/TA-39/acceptance-v1.json` | technical_sources | 3 |
| `docs/design/technical-atlas/TA-39/acceptance-v1.json` | unknowns | 2 |
| `docs/design/technical-atlas/TA-39/acceptance-v1.json` | artifacts | 6 |
| `docs/design/technical-atlas/TA-39/labels-v1.json` | pixels | 2 |
| `docs/design/technical-atlas/TA-39/labels-v1.json` | labels | 7 |
| `docs/design/technical-atlas/TA-39/labels-v1.json` | leaders | 7 |
| `docs/design/technical-atlas/TA-39/publication-20261008.json` | public_source_bytes | 2 |
| `docs/design/technical-atlas/TA-39/publication-20261008.json` | browser_evidence | 5 |
| `docs/design/technical-atlas/TA-39/publication-20261008.json` | limits | 2 |
| `docs/handoff/compute-catalog-batch2-production-20261003.json` | companies | 7 |
| `docs/handoff/compute-catalog-batch2-production-20261003.json` | unpublished | 2 |
| `docs/inbox/facts_candidates/m01_market_20260817.json` | records | 4 |
| `docs/inbox/facts_candidates/m02_supply_20260817.json` | records | 5 |
| `docs/inbox/facts_candidates/m03_demand_20260817.json` | records | 5 |
| `docs/inbox/facts_candidates/m04_power_20260817.json` | records | 5 |
| `docs/inbox/facts_candidates/m05_siting_20260817.json` | records | 3 |
| `docs/inbox/facts_candidates/m06r1_compute_20260817.json` | records | 5 |
| `docs/inbox/facts_candidates/m06r2_memory_20260817.json` | records | 6 |
| `docs/inbox/facts_candidates/m06r3_server_20260817.json` | records | 5 |
| `docs/inbox/facts_candidates/m07_network_20260817.json` | records | 5 |
| `docs/inbox/facts_candidates/m08_cooling_20260817.json` | records | 6 |
| `docs/inbox/facts_candidates/m09_supplychain_20260817.json` | records | 10 |
| `docs/inbox/facts_candidates/m10_ops_20260817.json` | records | 10 |
| `docs/inbox/facts_candidates/m11_reits_20260817.json` | records | 10 |
| `docs/inbox/facts_candidates/m12_tokenecon_20260817.json` | records | 4 |
| `docs/inbox/facts_candidates/m13_utilization_20260817.json` | records | 10 |
| `docs/inbox/facts_candidates/m14_china_20260817.json` | records | 10 |
| `docs/inbox/facts_candidates/m15_scenario_20260817.json` | records | 7 |
| `docs/inbox/framework_proposals/2026-09-06-attachments.json` | files | 2 |
| `docs/inbox/inresearch-alignment/bom_parts_extension.json` | proposed_parts | 14 |
| `docs/inbox/inresearch-alignment/companies_patch.json` | records | 166 |
| `docs/inbox/inresearch-alignment/library_index.json` | records | 6 |
| `docs/inbox/inresearch-alignment/products.json` | records | 175 |
| `docs/inbox/needs_password/needs_password_20260816.csv` | rows | 362 |
| `docs/inbox/path_migrations/migration_20260818_01.csv` | rows | 28751 |
| `docs/inbox/scored_batches/batch_20260815_01.csv` | rows | 5 |
| `docs/inbox/scored_batches/batch_20260815_02.csv` | rows | 26 |
| `docs/inbox/scored_batches/batch_20260815_03.csv` | rows | 24 |
| `docs/inbox/scored_batches/batch_20260816_01.csv` | rows | 24 |
| `docs/inbox/scored_batches/batch_20260816_02.csv` | rows | 28 |
| `docs/inbox/scored_batches/batch_20260816_03.csv` | rows | 41 |
| `docs/inbox/scored_batches/batch_20260816_04.csv` | rows | 37 |
| `docs/inbox/scored_batches/batch_20260816_05.csv` | rows | 53 |
| `docs/inbox/scored_batches/batch_20260816_06.csv` | rows | 36 |
| `docs/inbox/scored_batches/batch_20260816_07.csv` | rows | 36 |
| `docs/inbox/scored_batches/batch_20260816_08.csv` | rows | 36 |
| `docs/inbox/scored_batches/batch_20260816_09.csv` | rows | 15 |
| `docs/inbox/scored_batches/batch_20260816_10.csv` | rows | 34 |
| `docs/inbox/scored_batches/batch_20260816_11.csv` | rows | 32 |
| `docs/inbox/scored_batches/batch_20260816_12.csv` | rows | 37 |
| `docs/inbox/scored_batches/batch_20260816_13.csv` | rows | 24 |
| `docs/inbox/scored_batches/batch_20260816_14.csv` | rows | 75 |
| `docs/inbox/scored_batches/batch_20260816_15.csv` | rows | 74 |
| `docs/inbox/scored_batches/batch_20260816_16.csv` | rows | 74 |
| `docs/inbox/scored_batches/batch_20260816_17.csv` | rows | 55 |
| `docs/inbox/scored_batches/batch_20260816_18.csv` | rows | 50 |
| `docs/inbox/scored_batches/batch_20260816_19.csv` | rows | 58 |
| `docs/inbox/scored_batches/batch_20260816_20.csv` | rows | 50 |
| `docs/inbox/scored_batches/batch_20260816_21.csv` | rows | 40 |
| `docs/inbox/scored_batches/batch_20260816_22.csv` | rows | 26 |
| `docs/inbox/scored_batches/batch_20260816_23.csv` | rows | 65 |
| `docs/inbox/scored_batches/batch_20260816_24.csv` | rows | 13 |
| `docs/inbox/scored_batches/batch_20260816_25.csv` | rows | 35 |
| `docs/inbox/scored_batches/batch_20260816_26.csv` | rows | 28 |
| `docs/inbox/scored_batches/batch_20260816_27.csv` | rows | 31 |
| `docs/inbox/scored_batches/batch_20260816_28.csv` | rows | 72 |
| `docs/inbox/scored_batches/batch_20260816_29.csv` | rows | 20 |
| `docs/inbox/scored_batches/batch_20260816_30.csv` | rows | 258 |
| `docs/inbox/scored_batches/batch_20260816_31.csv` | rows | 346 |
| `docs/inbox/scored_batches/batch_20260816_32.csv` | rows | 60 |
| `docs/inbox/scored_batches/batch_20260816_33.csv` | rows | 164 |
| `docs/inbox/scored_batches/batch_20260816_34.csv` | rows | 500 |
| `docs/inbox/scored_batches/batch_20260816_35.csv` | rows | 500 |
| `docs/inbox/scored_batches/batch_20260816_36.csv` | rows | 488 |
| `docs/inbox/scored_batches/batch_20260816_37.csv` | rows | 648 |
| `docs/inbox/scored_batches/batch_20260816_38.csv` | rows | 745 |
| `docs/inbox/scored_batches/batch_20260817_39.csv` | rows | 309 |
| `docs/inbox/scored_batches/batch_20260817_40.csv` | rows | 700 |
| `docs/inbox/scored_batches/batch_20260817_41.csv` | rows | 700 |
| `docs/inbox/scored_batches/batch_20260817_42.csv` | rows | 700 |
| `docs/inbox/scored_batches/batch_20260817_43.csv` | rows | 700 |
| `docs/inbox/scored_batches/batch_20260817_44.csv` | rows | 700 |
| `docs/inbox/scored_batches/batch_20260817_45.csv` | rows | 700 |
| `docs/inbox/scored_batches/batch_20260817_46.csv` | rows | 700 |
| `docs/inbox/scored_batches/batch_20260817_47.csv` | rows | 700 |
| `docs/inbox/scored_batches/batch_20260817_48.csv` | rows | 700 |
| `docs/inbox/scored_batches/batch_20260817_49.csv` | rows | 700 |
| `docs/inbox/scored_batches/batch_20260817_50.csv` | rows | 700 |
| `docs/inbox/scored_batches/batch_20260817_51.csv` | rows | 556 |
| `docs/inbox/scored_batches/batch_20260817_52.csv` | rows | 241 |
| `docs/inbox/scored_batches/batch_20260817_53.csv` | rows | 3 |
| `docs/inbox/scored_batches/batch_20260817_54.csv` | rows | 359 |
| `docs/inbox/scored_batches/batch_20260817_55.csv` | rows | 1 |
| `docs/inbox/scored_batches/batch_20260817_56.csv` | rows | 3 |
| `docs/inbox/scored_batches/batch_20260817_57.csv` | rows | 3 |
| `docs/inbox/scored_batches/batch_20260817_58.csv` | rows | 3 |
| `docs/inbox/scored_batches/batch_20260817_59.csv` | rows | 3 |
| `docs/inbox/scored_batches/batch_20260817_60.csv` | rows | 2 |
| `docs/inbox/scored_batches/batch_20260817_61.csv` | rows | 1 |
| `docs/inbox/scored_batches/batch_20260817_62.csv` | rows | 1 |
| `docs/inbox/scored_batches/batch_20260817_63.csv` | rows | 1 |
| `docs/inbox/scored_batches/batch_20260817_64.csv` | rows | 2 |
| `docs/inbox/scored_batches/batch_20260817_65.csv` | rows | 2 |
| `docs/inbox/scored_batches/batch_20260817_66.csv` | rows | 2 |
| `docs/inbox/scored_batches/batch_20260817_67.csv` | rows | 2 |
| `docs/inbox/scored_batches/batch_20260817_68.csv` | rows | 2 |
| `docs/inbox/scored_batches/batch_20260817_69.csv` | rows | 2 |
| `docs/inbox/scored_batches/batch_20260817_70.csv` | rows | 2 |
| `docs/inbox/scored_batches/batch_20260817_71.csv` | rows | 1 |
| `docs/inbox/scored_batches/batch_20260817_72.csv` | rows | 1 |
| `docs/inbox/submissions/_selftest/submission.json` | items | 2 |
| `docs/inbox/submissions/_template/submission.json` | items | 1 |
| `docs/research/2026-09-14/datacenter-cost/model-results.json` | sensitivity | 14 |
| `docs/research/2026-09-14/datacenter-cost/model-results.json` | matrix | 18 |
| `docs/research/2026-09-14/datacenter-cost/model-results.json` | delay | 5 |
| `docs/research/2026-09-14/datacenter-cost/model-results.json` | apac | 7 |
| `docs/research/2026-09-14/datacenter-cost/model-results.json` | epoch | 10 |
| `docs/research/2026-09-27/datacenter-profit/profit-model-results.json` | report_price_paths | 5 |
| `docs/research/2026-10-01/ai-walle/cards.json` | cards | 10 |
| `docs/research/2026-10-01/ai-walle/sources.json` | groups | 8 |
| `docs/research/2026-10-01/ai-walle/sources.json` | background_sources | 1 |
| `docs/reviews/2026-09-06/evidence/backend-probes.json` | public_ranges | 4 |
| `docs/reviews/2026-09-06/evidence/backend-probes.json` | public_precision | 3 |
| `docs/reviews/2026-09-06/evidence/backend-probes.json` | collect_steps | 3 |
| `docs/reviews/2026-09-06/evidence/http-probes.json` | items | 4 |
| `docs/reviews/2026-09-06/evidence/runtime.json` | limits | 3 |
| `docs/reviews/2026-09-13/architecture/after.json` | top_level_directories | 12 |
| `docs/reviews/2026-09-13/architecture/after.json` | unresolved_old_references | 0 |
| `docs/reviews/2026-09-13/architecture/baseline.json` | scope_limits | 2 |
| `docs/reviews/2026-09-13/architecture/consumers.csv` | rows | 748 |
| `docs/reviews/2026-09-13/architecture/dependency-audit.json` | cycles | 0 |
| `docs/reviews/2026-09-13/architecture/dependency-audit.json` | forbidden_direction_edges | 0 |
| `docs/reviews/2026-09-13/architecture/deployment.json` | application_containers | 2 |
| `docs/reviews/2026-09-13/architecture/external-consumers.csv` | rows | 5 |
| `docs/reviews/2026-09-13/architecture/file-migration.csv` | rows | 491 |
| `docs/reviews/2026-09-13/architecture/legacy-removal.csv` | rows | 19 |
| `docs/reviews/2026-09-13/architecture/new-files.csv` | rows | 67 |
| `docs/reviews/2026-09-13/architecture/provenance-debt.csv` | rows | 38 |
| `docs/reviews/2026-09-13/architecture/public-consumers.csv` | rows | 2184 |
| `docs/reviews/2026-09-13/architecture/real-reader-flow.json` | states | 1 |
| `docs/reviews/2026-09-13/architecture/real-reader-flow.json` | coverage | 1 |
| `docs/reviews/2026-09-13/architecture/real-reader-flow.json` | acceptance | 1 |
| `docs/reviews/2026-09-13/architecture/shared-implementations.csv` | rows | 152 |
| `docs/reviews/2026-09-13/architecture/source-reference-debt.csv` | rows | 27 |
| `docs/reviews/2026-09-13/data-authority/consumers-after.csv` | rows | 104 |
| `docs/reviews/2026-09-13/data-authority/consumers-before.csv` | rows | 2115 |
| `docs/reviews/2026-09-13/data-authority/file-plan.csv` | rows | 653 |
| `docs/reviews/2026-09-13/data-authority/file-results.csv` | rows | 661 |
| `docs/reviews/2026-09-13/data-authority/legacy-removal.csv` | rows | 11 |
| `docs/reviews/2026-09-13/data-authority/production-before.json` | files | 32 |
| `docs/reviews/2026-09-13/data-authority/public-consumers.csv` | rows | 790 |
| `docs/reviews/2026-09-13/data-authority/scope.json` | changed | 33 |
| `docs/reviews/2026-09-13/data-authority/scope.json` | new | 4 |
| `docs/reviews/2026-09-13/data-authority/storage-consumers.csv` | rows | 44 |
| `docs/reviews/2026-09-13/deep-read/baseline.json` | ambiguous_pack_selected | 1 |
| `docs/reviews/2026-09-13/deep-read/consumers-after.csv` | rows | 455 |
| `docs/reviews/2026-09-13/deep-read/consumers-before.csv` | rows | 425 |
| `docs/reviews/2026-09-13/deep-read/dependency-audit.json` | cycles | 0 |
| `docs/reviews/2026-09-13/deep-read/dependency-audit.json` | import_edges | 187 |
| `docs/reviews/2026-09-13/deep-read/file-plan.csv` | rows | 603 |
| `docs/reviews/2026-09-13/deep-read/file-results.csv` | rows | 621 |
| `docs/reviews/2026-09-13/deep-read/functions-before.csv` | rows | 38 |
| `docs/reviews/2026-09-13/deep-read/integration-files.csv` | rows | 621 |
| `docs/reviews/2026-09-13/deep-read/public-contracts.csv` | rows | 76 |
| `docs/reviews/2026-09-13/deep-read/real-flow.json` | steps | 6 |
| `docs/reviews/2026-09-13/deep-read/test-results.csv` | rows | 413 |
| `docs/reviews/2026-09-13/deep-read/verification.json` | remaining | 5 |
| `docs/reviews/2026-09-13/news-projection/consumers-before.csv` | rows | 24 |
| `docs/reviews/2026-09-13/news-projection/file-plan.csv` | rows | 667 |
| `docs/reviews/2026-09-13/news-projection/file-results.csv` | rows | 674 |
| `docs/reviews/2026-09-13/news-projection/legacy-removal.csv` | rows | 7 |
| `docs/reviews/2026-09-13/news-projection/payload-before.json` | consumers | 2 |
| `docs/reviews/2026-09-13/news-projection/payload-before.json` | news_hosts | 2 |
| `docs/reviews/2026-09-13/news-projection/public-consumers.csv` | rows | 45 |
| `docs/reviews/2026-09-13/news-projection/scope.json` | changed | 12 |
| `docs/reviews/2026-09-13/news-projection/scope.json` | new | 0 |
| `docs/reviews/2026-09-13/reading-authority/consumers-after.csv` | rows | 177 |
| `docs/reviews/2026-09-13/reading-authority/consumers-before.csv` | rows | 113 |
| `docs/reviews/2026-09-13/reading-authority/file-plan.csv` | rows | 628 |
| `docs/reviews/2026-09-13/reading-authority/file-results.csv` | rows | 642 |
| `docs/reviews/2026-09-13/reading-authority/method-migration.csv` | rows | 6 |
| `docs/reviews/2026-09-13/reading-authority/public-consumers.csv` | rows | 1258 |
| `docs/reviews/2026-09-13/reading-authority/real-flow.json` | actual_models | 1 |
| `docs/reviews/2026-09-13/reading-authority/real-flow.json` | unverified | 3 |
| `docs/reviews/2026-09-13/reading-authority/test-migration.csv` | rows | 951 |
| `docs/reviews/2026-09-13/reading-authority/test-migration.json` | added | 17 |
| `docs/reviews/2026-09-13/reading-authority/test-migration.json` | missing | 0 |
| `docs/reviews/2026-09-13/reading-revisions/baseline.json` | documents_columns | 18 |
| `docs/reviews/2026-09-13/reading-revisions/baseline.json` | jobs_columns | 13 |
| `docs/reviews/2026-09-13/reading-revisions/consumers-after.csv` | rows | 100 |
| `docs/reviews/2026-09-13/reading-revisions/consumers-before.csv` | rows | 82 |
| `docs/reviews/2026-09-13/reading-revisions/dependencies.json` | cycles | 0 |
| `docs/reviews/2026-09-13/reading-revisions/file-plan.csv` | rows | 588 |
| `docs/reviews/2026-09-13/reading-revisions/file-results.csv` | rows | 591 |
| `docs/reviews/2026-09-13/reading-revisions/public-contracts.csv` | rows | 10 |
| `docs/reviews/2026-09-13/reading-revisions/real-flow.json` | model | 1 |
| `docs/reviews/2026-09-13/research-summary/consumers-before.csv` | rows | 31 |
| `docs/reviews/2026-09-13/research-summary/file-plan.csv` | rows | 690 |
| `docs/reviews/2026-09-13/research-summary/file-results.csv` | rows | 702 |
| `docs/reviews/2026-09-13/research-summary/legacy-removal.csv` | rows | 6 |
| `docs/reviews/2026-09-13/research-summary/public-consumers.csv` | rows | 78 |
| `docs/reviews/2026-09-13/research-summary/scope.json` | changed | 14 |
| `docs/reviews/2026-09-13/scene-interaction/consumers-before.csv` | rows | 80 |
| `docs/reviews/2026-09-13/scene-interaction/file-plan.csv` | rows | 676 |
| `docs/reviews/2026-09-13/scene-interaction/file-results.csv` | rows | 689 |
| `docs/reviews/2026-09-13/scene-interaction/legacy-removal.csv` | rows | 13 |
| `docs/reviews/2026-09-13/scene-interaction/news-release-verification.json` | news_keys | 3 |
| `docs/reviews/2026-09-13/scene-interaction/previous-release-verification.json` | containers | 11 |
| `docs/reviews/2026-09-13/scene-interaction/public-consumers.csv` | rows | 64 |
| `docs/reviews/2026-09-13/scene-interaction/scope.json` | changed | 14 |
| `docs/reviews/2026-09-13/standards/baseline-probes.json` | C_tier_closed_questions | 1 |
| `docs/reviews/2026-09-13/standards/baseline-probes.json` | C_tier_validation_errors | 0 |
| `docs/reviews/2026-09-13/standards/baseline-probes.json` | same_filename_rejections | 1 |
| `docs/reviews/2026-09-13/standards/consumers-after.csv` | rows | 62 |
| `docs/reviews/2026-09-13/standards/consumers-before.json` | knowledge.registry | 11 |
| `docs/reviews/2026-09-13/standards/consumers-before.json` | workflow.submissions | 2 |
| `docs/reviews/2026-09-13/standards/consumers-before.json` | storage.files | 13 |
| `docs/reviews/2026-09-13/standards/consumers-before.json` | interfaces.governance | 2 |
| `docs/reviews/2026-09-13/standards/dependencies.json` | cycles | 0 |
| `docs/reviews/2026-09-13/standards/file-changes.csv` | rows | 42 |
| `docs/reviews/2026-09-13/standards/integrated-consumers-after.csv` | rows | 114 |
| `docs/reviews/2026-09-13/standards/integrated-dependencies.json` | cycles | 0 |
| `docs/reviews/2026-09-13/standards/integrated-file-changes.csv` | rows | 53 |
| `docs/reviews/2026-09-14/cli-root/baseline.json` | temporary_root_files | 0 |
| `docs/reviews/2026-09-14/cli-root/consumers-after.csv` | rows | 227 |
| `docs/reviews/2026-09-14/cli-root/consumers-before.csv` | rows | 214 |
| `docs/reviews/2026-09-14/cli-root/dispatch.csv` | rows | 44 |
| `docs/reviews/2026-09-14/cli-root/file-plan.csv` | rows | 761 |
| `docs/reviews/2026-09-14/cli-root/file-results.csv` | rows | 765 |
| `docs/reviews/2026-09-14/cli-root/legacy-removal.csv` | rows | 6 |
| `docs/reviews/2026-09-14/cli-root/scope.json` | changed | 10 |
| `docs/reviews/2026-09-14/model-assets/baseline.json` | rejected_sample_requests | 1 |
| `docs/reviews/2026-09-14/model-assets/consumers-before.csv` | rows | 77 |
| `docs/reviews/2026-09-14/model-assets/file-plan.csv` | rows | 722 |
| `docs/reviews/2026-09-14/model-assets/file-results.csv` | rows | 736 |
| `docs/reviews/2026-09-14/model-assets/legacy-removal.csv` | rows | 7 |
| `docs/reviews/2026-09-14/model-assets/public-consumers.csv` | rows | 207 |
| `docs/reviews/2026-09-14/model-assets/public-contracts.csv` | rows | 17 |
| `docs/reviews/2026-09-14/model-assets/scope.json` | changed | 32 |
| `docs/reviews/2026-09-14/scene-bootstrap/baseline.json` | items | 2 |
| `docs/reviews/2026-09-14/scene-bootstrap/consumers-before.csv` | rows | 8 |
| `docs/reviews/2026-09-14/scene-bootstrap/file-plan.csv` | rows | 704 |
| `docs/reviews/2026-09-14/scene-bootstrap/file-results.csv` | rows | 717 |
| `docs/reviews/2026-09-14/scene-bootstrap/legacy-removal.csv` | rows | 4 |
| `docs/reviews/2026-09-14/scene-bootstrap/public-consumers.csv` | rows | 32 |
| `docs/reviews/2026-09-14/scene-bootstrap/scope.json` | changed | 15 |
| `docs/reviews/2026-09-14/scene-framing/baseline.json` | camera | 3 |
| `docs/reviews/2026-09-14/scene-framing/baseline.json` | target | 3 |
| `docs/reviews/2026-09-14/scene-framing/baseline.json` | box | 2 |
| `docs/reviews/2026-09-14/scene-framing/baseline.json` | projected | 8 |
| `docs/reviews/2026-09-14/scene-framing/baseline.json` | renderer | 2 |
| `docs/reviews/2026-09-14/scene-framing/consumers-before.csv` | rows | 48 |
| `docs/reviews/2026-09-14/scene-framing/file-plan.csv` | rows | 738 |
| `docs/reviews/2026-09-14/scene-framing/file-results.csv` | rows | 752 |
| `docs/reviews/2026-09-14/scene-framing/legacy-removal.csv` | rows | 6 |
| `docs/reviews/2026-09-14/scene-framing/public-consumers.csv` | rows | 122 |
| `docs/reviews/2026-09-14/scene-framing/public-contracts.csv` | rows | 10 |
| `docs/reviews/2026-09-14/scene-framing/scope.json` | changed | 21 |
| `docs/reviews/2026-09-14/scene-framing/scope.json` | inherited | 19 |
| `docs/reviews/2026-09-14/scene-resources/consumers-after.csv` | rows | 127 |
| `docs/reviews/2026-09-14/scene-resources/consumers-before.csv` | rows | 75 |
| `docs/reviews/2026-09-14/scene-resources/file-plan.csv` | rows | 772 |
| `docs/reviews/2026-09-14/scene-resources/file-results.csv` | rows | 780 |
| `docs/reviews/2026-09-14/scene-resources/legacy-removal.csv` | rows | 10 |
| `docs/reviews/2026-09-14/scene-resources/scope.json` | inherited | 6 |
| `docs/reviews/2026-09-14/scene-resources/scope.json` | changed | 16 |
| `docs/reviews/2026-09-15/l1-pipeline/consumers.csv` | rows | 16 |
| `docs/reviews/2026-09-15/l1-pipeline/file-plan.csv` | rows | 18 |
| `docs/reviews/2026-09-15/task-authority/file-plan.csv` | rows | 796 |
| `docs/reviews/2026-09-15/task-authority/scope.json` | changed | 15 |
| `docs/reviews/2026-10-09/research-publication/old-ready12-followup.json` | batches | 12 |
| `docs/reviews/2026-10-09/research-publication/original-23-stage-1422.json` | documents | 23 |
| `docs/reviews/2026-10-09/research-publication/original-23-stage-1422.json` | review_batches | 121 |
| `docs/reviews/2026-10-09/research-publication/original-23-stage-1422.json` | dispositions | 19 |
| `docs/reviews/2026-10-09/research-publication/original-23-stage-1422.json` | canonical_formal_records | 0 |
| `docs/reviews/2026-10-09/research-publication/original-23-stage.json` | sources | 23 |
| `docs/reviews/2026-10-09/research-publication/pr453-actual-closure.json` | head_chain | 3 |
| `docs/reviews/2026-10-09/research-publication/receipts.json` | receipts | 4 |
| `framework/bom.json` | scales | 5 |
| `framework/bom.json` | parts | 63 |
| `framework/bom.json` | stages | 6 |
| `framework/current_state.json` | policies | 49 |
| `framework/current_state.json` | entrypoints | 4 |
| `framework/current_state.json` | retired_entrypoints | 3 |
| `framework/current_state.json` | known_retired_patterns | 28 |
| `framework/current_state.json` | operational_guides | 11 |
| `framework/current_state.json` | retired_scan_snapshots | 1 |
| `framework/current_state.json` | compat_retirements | 7 |
| `framework/dashboard_rules.json` | honesty | 5 |
| `framework/data_contract.json` | source_grades | 5 |
| `framework/data_contract.json` | project_statuses | 9 |
| `framework/data_contract.json` | current_supply_statuses | 2 |
| `framework/data_contract.json` | price_frequency_rules | 4 |
| `framework/indicators.json` | indicators | 44 |
| `framework/interface_manifest.json` | static_pages | 32 |
| `framework/interface_manifest.json` | public_pages | 14 |
| `framework/interface_manifest.json` | template_fragments | 6 |
| `framework/material_retention.json` | required | 7 |
| `framework/metrics.json` | metrics | 312 |
| `framework/modules.json` | modules | 15 |
| `framework/research_graph.json` | legacy_root_prefixes | 4 |
| `framework/research_graph.json` | objects | 353 |
| `framework/research_graph.json` | relations | 372 |
| `framework/research_questions.json` | records | 458 |
| `framework/site_rights.json` | rights | 6 |
| `framework/supply_contract.json` | providers | 7 |
| `framework/tco_factors.json` | factors | 26 |
| `framework/tco_targets.json` | principles | 4 |
| `framework/tco_targets.json` | targets | 351 |
| `framework/verification_contract.json` | policies | 16 |
| `framework/visual_atlas.json` | references | 14 |
| `framework/visual_atlas_migration.json` | states | 5 |
| `framework/visual_atlas_migration.json` | items | 39 |
| `framework/visual_atlas_migration.json` | supplemental_items | 4 |
| `outputs/geluoke-research/2026-09-26/checks/validation.json` | images | 5 |
| `outputs/geluoke-research/2026-09-26/sources.json` | published_source_numbering | 48 |
| `outputs/geluoke-research/2026-09-26/sources.json` | events | 15 |
| `outputs/geluoke-research/2026-09-26/sources.json` | commentary_named_cases | 5 |
| `outputs/geluoke-research/2026-09-26/sources.json` | figures | 4 |
| `outputs/geluoke-research/2026-09-26/sources.json` | excluded_verified_candidates | 25 |
| `outputs/geluoke-research/2026-09-26/validation.json` | images | 5 |
| `outputs/geluoke-research/2026-09-26/work/content.json` | lead | 2 |
| `outputs/geluoke-research/2026-09-26/work/content.json` | events | 15 |
| `outputs/geluoke-research/2026-09-26/work/content.json` | commentary | 3 |
| `outputs/geluoke-research/2026-09-26/work/content.json` | sources | 48 |
| `outputs/geluoke-research/2026-09-26/work/cover.json` | modules | 5 |
| `outputs/geluoke-research/2026-09-26/work/cover.json` | regions | 4 |
| `outputs/geluoke-research/2026-09-26/work/cover.json` | maps | 5 |
| `outputs/geluoke-research/2026-09-26/work/event_plan.json` | events | 15 |
| `outputs/geluoke-research/2026-09-26/work/event_plan.json` | related_for_commentary | 24 |
| `outputs/geluoke-research/2026-09-26/work/event_plan.json` | sweep_related | 5 |
| `outputs/geluoke-research/2026-09-26/work/event_plan.json` | sweep_related_cards | 5 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/2026-09-27-sources.json` | items | 62 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/checks/validation.json` | images | 7 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/article.json` | lead | 2 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/article.json` | chapters | 6 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/article.json` | summary | 3 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/article.json` | commentary | 3 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/article.json` | sources | 62 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/chapters.json` | chapters | 6 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/chapters_final.json` | chapters | 6 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/cover/cover.json` | paths | 3 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/cover/cover.json` | layers | 4 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/cover/cover.json` | modules | 5 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/lead.json` | commentary | 3 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/lead.json` | sources_added | 0 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/lead.json` | summary | 3 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/cards.json` | records | 50 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/browser.json` | render | 6 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/build-title-20261009.json` | public_images | 15 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/build-title-20261009.json` | images | 31 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/build.json` | public_images | 11 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/build.json` | images | 41 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/cover-layout.json` | overflow | 0 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/eia-table-rows.json` | Ohio | 11 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/eia-table-rows.json` | Georgia | 11 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/eia-table-rows.json` | Virginia | 11 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/eia-table-rows.json` | Texas | 11 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/eia-table-rows.json` | Arizona | 11 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/eia-table-rows.json` | Oregon | 11 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/eia-table-rows.json` | U.S. Total | 11 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/figure9-title-html-20261009.json` | render | 6 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/figure9-title-html-20261009.json` | not_performed | 3 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/figure9-title-html-final-20261009.json` | render | 6 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/figure9-title-html-final-20261009.json` | not_performed | 3 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/figure9-title-render-20261009.json` | overflow | 0 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/repository-intake-20261009.json` | commands | 6 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/repository-intake-20261009.json` | not_verified | 3 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/repository.json` | tests | 5 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/source-provenance-live-http-20261009.json` | snapshot_sources | 23 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/source-provenance-live-http-20261009.json` | target_sources | 13 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/source-provenance-public-https-20261009.json` | target_sources | 2 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/spark-intake-final-provenance-20261009.json` | decoded_archived_tool_response_carriers | 3 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/spark-intake-final-receipt-20261009.json` | source_items | 23 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/spark-intake-final-receipt-20261009.json` | reader_before | 0 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/spark-intake-final-receipt-20261009.json` | reader_hold_source_ids | 0 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/spark-intake-provenance-20261009.json` | decoded_archived_tool_response_carriers | 3 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/spark-intake-receipt-20261009.json` | source_items | 23 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/spark-intake-receipt-20261009.json` | reader_before | 0 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/spark-intake-receipt-20261009.json` | reader_hold_source_ids | 2 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/spark-reader-progress-20261009.json` | rows | 21 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/spark-reader-progress-final-20261009.json` | rows | 23 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/spark-source-provenance-stage-20261009.json` | rows | 23 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/svg-layout.json` | items | 7 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/v3-svg-layout.json` | items | 14 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/v4-svg-layout.json` | items | 10 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/validation.json` | not_verified | 5 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/research/claims.json` | records | 50 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/research/demand-snapshot.json` | research_questions | 13 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/research/demand-snapshot.json` | tco_targets | 9 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/research/originals-manifest.json` | files | 89 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/research/research-gaps.json` | records | 8 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/research/sources.json` | records | 52 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/research/submission.json` | items | 23 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/sources.json` | records | 52 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/v3/figure-plan.json` | figures | 14 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/v3/visual-sources.json` | records | 6 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/v3/visual-sources.json` | failures_retained | 2 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/v4/figure-plan.json` | figures | 10 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/visual-references.json` | records | 9 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/writing-plan.json` | mainline | 6 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/writing-plan.json` | headings | 6 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/writing-plan.json` | lead_sources | 2 |
| `reports/blindspot.json` | modules | 15 |
| `reports/workorders.json` | orders | 564 |
| `research/M01.md` | Finding | 7 |
| `research/M02.md` | Finding | 13 |
| `research/M03.md` | Finding | 5 |
| `research/M04.md` | Finding | 9 |
| `research/M05.md` | Finding | 14 |
| `research/M06.md` | Finding | 16 |
| `research/M07.md` | Finding | 8 |
| `research/M08.md` | Finding | 10 |
| `research/M09.md` | Finding | 12 |
| `research/M10.md` | Finding | 18 |
| `research/M11.md` | Finding | 3 |
| `research/M12.md` | Finding | 6 |
| `research/M13.md` | Finding | 6 |
| `research/M14.md` | Finding | 11 |
| `research/M15.md` | Finding | 12 |
| `web/assets/models/manifest.json` | models | 1 |
| `web/assets/world.geo.json` | features | 180 |
| `web/pages/admin/repo-content/infra-daily.json` | reach | 6 |

## 全部文件

| 路径 | 身份 |
|---|---|
| `.claude/launch.json` | 项目配置 |
| `.dockerignore` | 项目配置 |
| `.gitattributes` | 项目配置 |
| `.github/CODEOWNERS` | 项目配置 |
| `.github/workflows/validate.yml` | 项目配置 |
| `.gitignore` | 项目配置 |
| [AGENTS.md](../AGENTS.md) | 现行入口 |
| [CLAUDE.md](../CLAUDE.md) | 现行入口 |
| [README.md](../README.md) | 配套说明 |
| `data/assignments.json` | 在册数据/索引 |
| `data/brief.json` | 在册数据/索引 |
| `data/companies.json` | 在册数据/索引 |
| `data/company_disclosures.json` | 在册数据/索引 |
| `data/contracts.json` | 在册数据/索引 |
| `data/dashboard.json` | 在册数据/索引 |
| `data/datacenter_model.json` | 在册数据/索引 |
| `data/event_cards.json` | 在册数据/索引 |
| `data/facts.json` | 在册数据/索引 |
| `data/metric_gaps.jsonl` | 在册数据/索引 |
| `data/policies.json` | 在册数据/索引 |
| `data/prices.json` | 在册数据/索引 |
| [data/product_docs_plan.csv](../data/product_docs_plan.csv) | 在册数据/索引 |
| `data/products.json` | 在册数据/索引 |
| `data/projects.json` | 在册数据/索引 |
| `data/research_knowledge.json` | 在册数据/索引 |
| `data/schema/company.schema.json` | 在册数据/索引 |
| `data/schema/contract.schema.json` | 在册数据/索引 |
| `data/schema/fact.schema.json` | 在册数据/索引 |
| `data/schema/policy.schema.json` | 在册数据/索引 |
| `data/schema/price.schema.json` | 在册数据/索引 |
| `data/schema/products.schema.json` | 在册数据/索引 |
| `data/schema/project.schema.json` | 在册数据/索引 |
| `data/schema/source.schema.json` | 在册数据/索引 |
| `data/schema/submission.schema.json` | 在册数据/索引 |
| `data/sources.json` | 在册数据/索引 |
| `deploy/Dockerfile` | 项目配置 |
| [deploy/README.md](../deploy/README.md) | 配套说明 |
| `deploy/m5-research/research-publish.plist.example` | 项目配置 |
| `deploy/models.json` | 项目配置 |
| `deploy/spark-reader/inresearch-editorial.service` | 项目配置 |
| `deploy/spark-reader/inresearch-editorial.timer` | 项目配置 |
| `deploy/spark-reader/inresearch-material-intake.service` | 项目配置 |
| `deploy/spark-reader/inresearch-material-intake.timer` | 项目配置 |
| `deploy/spark-reader/inresearch-news.service` | 项目配置 |
| `deploy/spark-reader/inresearch-news.timer` | 项目配置 |
| `deploy/spark-reader/inresearch-reader-publish.service` | 项目配置 |
| `deploy/spark-reader/inresearch-reader-publish.timer` | 项目配置 |
| `deploy/spark-reader/inresearch-reader.service` | 项目配置 |
| `deploy/spark-reader/inresearch-research-review.service` | 项目配置 |
| `deploy/spark-reader/install.sh` | 运行代码 |
| `deploy/spark-reader/reader.env.example` | 项目配置 |
| [docs/CN_PROJECT_ARCHIVES.csv](CN_PROJECT_ARCHIVES.csv) | 在册数据/索引 |
| [docs/DATA_SOURCING.md](DATA_SOURCING.md) | 配套说明 |
| [docs/DECISIONS.md](DECISIONS.md) | 现行入口 |
| [docs/LIBRARY_REPORT.md](LIBRARY_REPORT.md) | 在册数据/索引 |
| [docs/LIBRARY_SCORES.csv](LIBRARY_SCORES.csv) | 在册数据/索引 |
| [docs/M4_TRIAGE_TASK.md](M4_TRIAGE_TASK.md) | 现行规范 |
| [docs/PROJECT_PANORAMA.md](PROJECT_PANORAMA.md) | 现行入口 |
| [docs/REPOSITORY_REGISTER.md](REPOSITORY_REGISTER.md) | 生成物 |
| [docs/archive/2026-09-06/ACQUISITION_LEGACY.md](archive/2026-09-06/ACQUISITION_LEGACY.md) | 历史快照 |
| [docs/archive/2026-09-06/CLAUDE.md](archive/2026-09-06/CLAUDE.md) | 历史快照 |
| [docs/archive/2026-09-06/README.md](archive/2026-09-06/README.md) | 历史快照 |
| [docs/archive/2026-09-06/UI_BEFORE_SKINS.md](archive/2026-09-06/UI_BEFORE_SKINS.md) | 历史快照 |
| [docs/archive/2026-09-06/docs__DECISIONS.md](archive/2026-09-06/docs__DECISIONS.md) | 历史快照 |
| [docs/archive/2026-09-06/docs__PROJECT_PANORAMA.md](archive/2026-09-06/docs__PROJECT_PANORAMA.md) | 历史快照 |
| [docs/archive/2026-09-06/docs__local_reader__CONTINUOUS_READER_DESIGN.md](archive/2026-09-06/docs__local_reader__CONTINUOUS_READER_DESIGN.md) | 历史快照 |
| [docs/archive/2026-09-06/docs__local_reader__KICKOFF_PROMPT.md](archive/2026-09-06/docs__local_reader__KICKOFF_PROMPT.md) | 历史快照 |
| [docs/archive/2026-09-06/docs__local_reader__PROJECT_BRIEF.md](archive/2026-09-06/docs__local_reader__PROJECT_BRIEF.md) | 历史快照 |
| [docs/archive/2026-09-06/docs__local_reader__RUN_TO_COMPLETION.md](archive/2026-09-06/docs__local_reader__RUN_TO_COMPLETION.md) | 历史快照 |
| [docs/archive/2026-09-06/docs__local_setup__PRODUCT_LIBRARY.md](archive/2026-09-06/docs__local_setup__PRODUCT_LIBRARY.md) | 历史快照 |
| [docs/archive/2026-09-06/docs__local_setup__README.md](archive/2026-09-06/docs__local_setup__README.md) | 历史快照 |
| [docs/archive/2026-09-06/docs__local_setup__setup.sh.md](archive/2026-09-06/docs__local_setup__setup.sh.md) | 历史快照 |
| [docs/archive/2026-09-06/framework__01_data_standards.md](archive/2026-09-06/framework__01_data_standards.md) | 历史快照 |
| [docs/archive/2026-09-06/framework__02_knowledge_format.md](archive/2026-09-06/framework__02_knowledge_format.md) | 历史快照 |
| [docs/archive/2026-09-12/docs__M4_TRIAGE_TASK.md](archive/2026-09-12/docs__M4_TRIAGE_TASK.md) | 历史快照 |
| [docs/archive/2026-09-12/docs__local_reader__M4_TRIAGE_RUNBOOK.md](archive/2026-09-12/docs__local_reader__M4_TRIAGE_RUNBOOK.md) | 历史快照 |
| [docs/archive/2026-09-12/framework__04_reading_scoring_standard.md](archive/2026-09-12/framework__04_reading_scoring_standard.md) | 历史快照 |
| [docs/archive/2026-09-14/deploy__Caddyfile.md](archive/2026-09-14/deploy__Caddyfile.md) | 历史快照 |
| [docs/archive/2026-09-14/deploy__README.md](archive/2026-09-14/deploy__README.md) | 历史快照 |
| [docs/archive/2026-09-14/deploy__docker-compose.yml.md](archive/2026-09-14/deploy__docker-compose.yml.md) | 历史快照 |
| [docs/archive/2026-09-14/docs__LIBRARY_INDEX.md](archive/2026-09-14/docs__LIBRARY_INDEX.md) | 历史快照 |
| [docs/archive/2026-09-28/framework__00_overview.md](archive/2026-09-28/framework__00_overview.md) | 历史快照 |
| [docs/archive/2026-09-28/framework__07_product_ecosystems.md](archive/2026-09-28/framework__07_product_ecosystems.md) | 历史快照 |
| [docs/archive/2026-10-02/framework__00_overview.md](archive/2026-10-02/framework__00_overview.md) | 历史快照 |
| [docs/archive/2026-10-02/framework__05_interface_system.md](archive/2026-10-02/framework__05_interface_system.md) | 历史快照 |
| [docs/archive/2026-10-02/framework__06_acquisition.md](archive/2026-10-02/framework__06_acquisition.md) | 历史快照 |
| [docs/archive/2026-10-06/before_dispatch__framework__04_reading_scoring_standard.md](archive/2026-10-06/before_dispatch__framework__04_reading_scoring_standard.md) | 历史快照 |
| [docs/archive/2026-10-06/before_dispatch__framework__05_interface_system.md](archive/2026-10-06/before_dispatch__framework__05_interface_system.md) | 历史快照 |
| [docs/archive/2026-10-06/before_dispatch__framework__06_acquisition.md](archive/2026-10-06/before_dispatch__framework__06_acquisition.md) | 历史快照 |
| [docs/archive/2026-10-06/codex-reader/04_reading_scoring_standard.md](archive/2026-10-06/codex-reader/04_reading_scoring_standard.md) | 历史快照 |
| [docs/archive/2026-10-06/codex-reader/05_interface_system.md](archive/2026-10-06/codex-reader/05_interface_system.md) | 历史快照 |
| [docs/archive/2026-10-06/codex-reader/08_model_execution.md](archive/2026-10-06/codex-reader/08_model_execution.md) | 历史快照 |
| [docs/archive/2026-10-06/framework__04_reading_scoring_standard.md](archive/2026-10-06/framework__04_reading_scoring_standard.md) | 历史快照 |
| [docs/archive/2026-10-06/framework__06_acquisition.md](archive/2026-10-06/framework__06_acquisition.md) | 历史快照 |
| [docs/archive/2026-10-06/framework__06_acquisition_before_daily_delivery.md](archive/2026-10-06/framework__06_acquisition_before_daily_delivery.md) | 历史快照 |
| [docs/archive/2026-10-06/worktree-snapshots/README.md](archive/2026-10-06/worktree-snapshots/README.md) | 历史快照 |
| `docs/archive/2026-10-06/worktree-snapshots/macos-vision-ocr-428ea8b.patch` | 历史快照 |
| `docs/archive/2026-10-06/worktree-snapshots/patches.json` | 历史快照 |
| `docs/archive/2026-10-06/worktree-snapshots/terminal-boundaries-plan-7e35305.patch` | 历史快照 |
| `docs/archive/2026-10-06/worktree-snapshots/terminal-office-wip-d9477a7.patch` | 历史快照 |
| [docs/archive/2026-10-07/framework__04_before_native_text.md](archive/2026-10-07/framework__04_before_native_text.md) | 历史快照 |
| [docs/archive/2026-10-08/docs__geluoke__专题写作规则-v2.2.md](archive/2026-10-08/docs__geluoke__专题写作规则-v2.2.md) | 历史快照 |
| [docs/archive/2026-10-08/framework__05_interface_system__before_reader_company.md](archive/2026-10-08/framework__05_interface_system__before_reader_company.md) | 历史快照 |
| [docs/archive/2026-10-08/framework__05_interface_system__before_repository_daily.md](archive/2026-10-08/framework__05_interface_system__before_repository_daily.md) | 历史快照 |
| [docs/archive/2026-10-09/docs__geluoke__专题写作规则-v2.3.md](archive/2026-10-09/docs__geluoke__专题写作规则-v2.3.md) | 历史快照 |
| [docs/archive/2026-10-09/docs__geluoke__专题写作规则-v2.4.md](archive/2026-10-09/docs__geluoke__专题写作规则-v2.4.md) | 历史快照 |
| [docs/archive/2026-10-09/docs__geluoke__专题写作规则-v2.5.md](archive/2026-10-09/docs__geluoke__专题写作规则-v2.5.md) | 历史快照 |
| [docs/archive/2026-10-09/docs__geluoke__专题写作规则-v2.6.md](archive/2026-10-09/docs__geluoke__专题写作规则-v2.6.md) | 历史快照 |
| [docs/design/technical-atlas/MIGRATION_PLAN.md](design/technical-atlas/MIGRATION_PLAN.md) | 配套说明 |
| `docs/design/technical-atlas/TA-01/acceptance-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-01/labels-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-01/prompt-repair-v2.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-01/prompt-repair-v3.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-01/prompt-v1.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-01/publication-20261008.json` | 项目配置 |
| `docs/design/technical-atlas/TA-02/acceptance-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-02/publication-20261008.json` | 项目配置 |
| `docs/design/technical-atlas/TA-03/acceptance-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-03/labels-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-03/preparation-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-03/prompt-v1.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-03/publication-20261008.json` | 项目配置 |
| `docs/design/technical-atlas/TA-04/acceptance-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-04/labels-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-04/preparation-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-04/prompt-correction-v2.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-04/prompt-rebuild-v3.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-04/prompt-v1.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-04/publication-20261008.json` | 项目配置 |
| `docs/design/technical-atlas/TA-05/acceptance-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-05/labels-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-05/preparation.json` | 项目配置 |
| `docs/design/technical-atlas/TA-05/prompt-v1.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-05/prompt-v2.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-05/publication-20261009.json` | 项目配置 |
| `docs/design/technical-atlas/TA-06/acceptance-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-06/labels-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-06/preparation.json` | 项目配置 |
| `docs/design/technical-atlas/TA-06/prompt-v1.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-06/publication-20261009.json` | 项目配置 |
| `docs/design/technical-atlas/TA-07/acceptance-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-07/labels-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-07/preparation.json` | 项目配置 |
| `docs/design/technical-atlas/TA-07/prompt-v1.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-07/publication-20261009.json` | 项目配置 |
| `docs/design/technical-atlas/TA-08/acceptance-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-08/labels-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-08/preparation-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-08/prompt-v1.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-08/publication-20261009.json` | 项目配置 |
| `docs/design/technical-atlas/TA-09/acceptance-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-09/labels-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-09/preparation-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-09/prompt-v1.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-09/publication-20261009.json` | 项目配置 |
| `docs/design/technical-atlas/TA-10/acceptance-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-10/labels-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-10/preparation-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-10/prompt-correction-v2.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-10/prompt-cutaway-v3.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-10/prompt-v1.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-10/publication-20261009.json` | 项目配置 |
| `docs/design/technical-atlas/TA-11/acceptance-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-11/labels-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-11/legacy/rack3d-996cfa2e.html` | 运行代码 |
| `docs/design/technical-atlas/TA-11/preparation-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-11/publication-20261009.json` | 项目配置 |
| `docs/design/technical-atlas/TA-11/ta11-prompt-correction-v2.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-11/ta11-prompt-nic-correction-v3.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-11/ta11-prompt-nic-correction-v4.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-11/ta11-prompt-v1.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-12/acceptance-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-12/labels-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-12/mobile-fix-20261009.json` | 项目配置 |
| `docs/design/technical-atlas/TA-12/preparation-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-12/publication-20261009.json` | 项目配置 |
| [docs/design/technical-atlas/TA-12/render-spec-v1.md](design/technical-atlas/TA-12/render-spec-v1.md) | 配套说明 |
| `docs/design/technical-atlas/TA-36/acceptance-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-36/labels-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-36/prompt-v1.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-36/publication-20261008.json` | 项目配置 |
| `docs/design/technical-atlas/TA-37/acceptance-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-37/labels-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-37/prompt-v1.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-37/publication-20261008.json` | 项目配置 |
| `docs/design/technical-atlas/TA-38/acceptance-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-38/labels-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-38/prompt-retry-v2.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-38/prompt-retry-v3.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-38/prompt-v1.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-38/publication-20261008.json` | 项目配置 |
| `docs/design/technical-atlas/TA-39/acceptance-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-39/labels-v1.json` | 项目配置 |
| `docs/design/technical-atlas/TA-39/prompt-v1.txt` | 项目配置 |
| `docs/design/technical-atlas/TA-39/publication-20261008.json` | 项目配置 |
| `docs/design/technical-atlas/references/01-chain.png` | 项目配置 |
| `docs/design/technical-atlas/references/02-server.png` | 项目配置 |
| `docs/design/technical-atlas/references/03-ssd.png` | 项目配置 |
| `docs/design/technical-atlas/references/04-explainer.png` | 项目配置 |
| `docs/design/technical-atlas/references/05-thermal-cutaway.png` | 项目配置 |
| `docs/design/technical-atlas/references/06-campus-cutaway.png` | 项目配置 |
| `docs/design/technical-atlas/references/07-heat-path.png` | 项目配置 |
| `docs/design/technical-atlas/references/08-water-reuse.png` | 项目配置 |
| `docs/design/technical-atlas/references/09-water-isometric.png` | 项目配置 |
| `docs/design/technical-atlas/references/10-industrial-campus-cutaway.png` | 项目配置 |
| `docs/design/technical-atlas/references/11-industrial-building-paths.png` | 项目配置 |
| `docs/design/technical-atlas/references/12-site-context-triptych.png` | 项目配置 |
| `docs/design/technical-atlas/references/13-supply-to-power-path.png` | 项目配置 |
| `docs/design/technical-atlas/references/14-modern-campus-cutaway.png` | 项目配置 |
| [docs/design/technical-atlas/references/README.md](design/technical-atlas/references/README.md) | 配套说明 |
| [docs/geluoke/专题写作规则.md](geluoke/专题写作规则.md) | 现行规范 |
| [docs/geluoke/专题反哺规则.md](geluoke/专题反哺规则.md) | 配套说明 |
| `docs/guides/model-governance-2026-09-27.html` | 运行代码 |
| `docs/guides/model-governance-2026-09-27.pdf` | 项目配置 |
| [docs/handoff/2026-10-01-ai-walle.md](handoff/2026-10-01-ai-walle.md) | 配套说明 |
| [docs/handoff/2026-10-01-geluoke-longform.md](handoff/2026-10-01-geluoke-longform.md) | 配套说明 |
| [docs/handoff/catalog-ownership-20261007.md](handoff/catalog-ownership-20261007.md) | 配套说明 |
| [docs/handoff/codex-batch-reader-20261006.md](handoff/codex-batch-reader-20261006.md) | 配套说明 |
| [docs/handoff/company-catalog-map-20261007.md](handoff/company-catalog-map-20261007.md) | 配套说明 |
| [docs/handoff/company-category-navigation-20261007.md](handoff/company-category-navigation-20261007.md) | 配套说明 |
| [docs/handoff/company-page-20261007.md](handoff/company-page-20261007.md) | 配套说明 |
| [docs/handoff/company-reader-design-20261008.md](handoff/company-reader-design-20261008.md) | 配套说明 |
| [docs/handoff/company-window-20261007.md](handoff/company-window-20261007.md) | 配套说明 |
| [docs/handoff/compute-catalog-20261002.md](handoff/compute-catalog-20261002.md) | 配套说明 |
| [docs/handoff/compute-catalog-batch2-20261002.md](handoff/compute-catalog-batch2-20261002.md) | 配套说明 |
| `docs/handoff/compute-catalog-batch2-production-20261003.json` | 项目配置 |
| [docs/handoff/daily-evidence-loop-20261006.md](handoff/daily-evidence-loop-20261006.md) | 配套说明 |
| [docs/handoff/daily-oct7-adoption.md](handoff/daily-oct7-adoption.md) | 配套说明 |
| [docs/handoff/event-delivery-20261006.md](handoff/event-delivery-20261006.md) | 配套说明 |
| [docs/handoff/event-verification-20261007.md](handoff/event-verification-20261007.md) | 配套说明 |
| [docs/handoff/evidence-followup-20261007.md](handoff/evidence-followup-20261007.md) | 配套说明 |
| [docs/handoff/evidence-gaps-20261007.md](handoff/evidence-gaps-20261007.md) | 配套说明 |
| [docs/handoff/fetchdata-bootstrap.md](handoff/fetchdata-bootstrap.md) | 配套说明 |
| [docs/handoff/fetchspec-redesign-2026-09-29.md](handoff/fetchspec-redesign-2026-09-29.md) | 配套说明 |
| [docs/handoff/historical-source-recovery-20261007.md](handoff/historical-source-recovery-20261007.md) | 配套说明 |
| [docs/handoff/history-foundation-writing-20261008.md](handoff/history-foundation-writing-20261008.md) | 配套说明 |
| [docs/handoff/home-map-visible-20261008.md](handoff/home-map-visible-20261008.md) | 配套说明 |
| [docs/handoff/homepage-first-screen.md](handoff/homepage-first-screen.md) | 配套说明 |
| [docs/handoff/homepage-map-audit-20261003.md](handoff/homepage-map-audit-20261003.md) | 配套说明 |
| [docs/handoff/inews-2026-09-29.md](handoff/inews-2026-09-29.md) | 配套说明 |
| [docs/handoff/infra-2026-09-29.md](handoff/infra-2026-09-29.md) | 配套说明 |
| [docs/handoff/m4-deepread.md](handoff/m4-deepread.md) | 配套说明 |
| [docs/handoff/material-lineage-dashboard-20261008.md](handoff/material-lineage-dashboard-20261008.md) | 配套说明 |
| [docs/handoff/material-progress-overview-20261006.md](handoff/material-progress-overview-20261006.md) | 配套说明 |
| [docs/handoff/news-research-matching-20261006.md](handoff/news-research-matching-20261006.md) | 配套说明 |
| [docs/handoff/nvidia-product-catalog.md](handoff/nvidia-product-catalog.md) | 配套说明 |
| [docs/handoff/ocr-gap-rescue-four-20261007.md](handoff/ocr-gap-rescue-four-20261007.md) | 配套说明 |
| [docs/handoff/ops-dashboard-20261007.md](handoff/ops-dashboard-20261007.md) | 配套说明 |
| [docs/handoff/ops-loading-fix-20261008.md](handoff/ops-loading-fix-20261008.md) | 配套说明 |
| [docs/handoff/pdf-native-text-20261007.md](handoff/pdf-native-text-20261007.md) | 配套说明 |
| [docs/handoff/pr-412-conflict-fix-20261009.md](handoff/pr-412-conflict-fix-20261009.md) | 配套说明 |
| [docs/handoff/pr-417-conflict-fix-20261009.md](handoff/pr-417-conflict-fix-20261009.md) | 配套说明 |
| [docs/handoff/primary-records-20261007.md](handoff/primary-records-20261007.md) | 配套说明 |
| [docs/handoff/project-evidence-loop-20261006.md](handoff/project-evidence-loop-20261006.md) | 配套说明 |
| [docs/handoff/publication-throughput-recovery-20261009.md](handoff/publication-throughput-recovery-20261009.md) | 配套说明 |
| [docs/handoff/reader-failure-ocr-repair-20261006.md](handoff/reader-failure-ocr-repair-20261006.md) | 配套说明 |
| [docs/handoff/reading-adoption-first-batch-20261007.md](handoff/reading-adoption-first-batch-20261007.md) | 配套说明 |
| [docs/handoff/repository-daily-refresh-20261008.md](handoff/repository-daily-refresh-20261008.md) | 配套说明 |
| [docs/handoff/repository-pages-20261003.md](handoff/repository-pages-20261003.md) | 配套说明 |
| [docs/handoff/research-flow-recovery-20261009.md](handoff/research-flow-recovery-20261009.md) | 配套说明 |
| [docs/handoff/research-throughput-20261008.md](handoff/research-throughput-20261008.md) | 配套说明 |
| [docs/handoff/research-verification-20261008.md](handoff/research-verification-20261008.md) | 配套说明 |
| [docs/handoff/review-2026-09-29.md](handoff/review-2026-09-29.md) | 配套说明 |
| [docs/handoff/review-literal-recovery-20261008.md](handoff/review-literal-recovery-20261008.md) | 配套说明 |
| [docs/handoff/supermicro-historical-supplement-20261007.md](handoff/supermicro-historical-supplement-20261007.md) | 配套说明 |
| [docs/handoff/tco-model-fetch-teams.md](handoff/tco-model-fetch-teams.md) | 配套说明 |
| [docs/handoff/technical-atlas-m4-20261009.md](handoff/technical-atlas-m4-20261009.md) | 配套说明 |
| [docs/handoff/technical-atlas-standard-20261008.md](handoff/technical-atlas-standard-20261008.md) | 配套说明 |
| [docs/handoff/us-datacenter-power-20261009.md](handoff/us-datacenter-power-20261009.md) | 配套说明 |
| [docs/handoff/worktree-integration-20261006.md](handoff/worktree-integration-20261006.md) | 配套说明 |
| [docs/inbox/PHASE2_REPORT.md](inbox/PHASE2_REPORT.md) | 候选与外部输入 |
| [docs/inbox/README.md](inbox/README.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/7B_人工智能算力高质量发展评估体系_浪潮信息中国信通院.md](inbox/digest_drafts/7B_人工智能算力高质量发展评估体系_浪潮信息中国信通院.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8A_2026年AI供应链瓶颈与CoWoS产能分配_伯恩斯坦.md](inbox/digest_drafts/8A_2026年AI供应链瓶颈与CoWoS产能分配_伯恩斯坦.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8A_AI扩散出口管制_SemiAnalysis.md](inbox/digest_drafts/8A_AI扩散出口管制_SemiAnalysis.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8A_AI数据中心电力困局_SemiAnalysis.md](inbox/digest_drafts/8A_AI数据中心电力困局_SemiAnalysis.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8A_Blackwell性能TCO_SemiAnalysis.md](inbox/digest_drafts/8A_Blackwell性能TCO_SemiAnalysis.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8A_DeepSeek成本辩论_SemiAnalysis.md](inbox/digest_drafts/8A_DeepSeek成本辩论_SemiAnalysis.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8A_GPU云评级体系_SemiAnalysis.md](inbox/digest_drafts/8A_GPU云评级体系_SemiAnalysis.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8A_GTC2025与黄氏算术_SemiAnalysis.md](inbox/digest_drafts/8A_GTC2025与黄氏算术_SemiAnalysis.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8A_中国AI芯片供需与出口管制测算_伯恩斯坦.md](inbox/digest_drafts/8A_中国AI芯片供需与出口管制测算_伯恩斯坦.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8A_关税与设备供应链_SemiAnalysis.md](inbox/digest_drafts/8A_关税与设备供应链_SemiAnalysis.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8A_华为晶圆厂网络_SemiAnalysis.md](inbox/digest_drafts/8A_华为晶圆厂网络_SemiAnalysis.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8A_华为永州1号楼建筑预算_永州开发投资.md](inbox/digest_drafts/8A_华为永州1号楼建筑预算_永州开发投资.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8A_戴尔如何击败超微_SemiAnalysis.md](inbox/digest_drafts/8A_戴尔如何击败超微_SemiAnalysis.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8A_扩展律与推理基建_SemiAnalysis.md](inbox/digest_drafts/8A_扩展律与推理基建_SemiAnalysis.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8A_数据中心制冷系统_SemiAnalysis.md](inbox/digest_drafts/8A_数据中心制冷系统_SemiAnalysis.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8A_星际之门合资拆解_SemiAnalysis.md](inbox/digest_drafts/8A_星际之门合资拆解_SemiAnalysis.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8A_移动粤港澳控制价编制说明_中国移动.md](inbox/digest_drafts/8A_移动粤港澳控制价编制说明_中国移动.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8A_移动粤港澳项目招标控制价总表_中国移动.md](inbox/digest_drafts/8A_移动粤港澳项目招标控制价总表_中国移动.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8A_算力中心创新融资研究报告_中国信通院.md](inbox/digest_drafts/8A_算力中心创新融资研究报告_中国信通院.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8A_芜湖联通智算中心环评_中国联通.md](inbox/digest_drafts/8A_芜湖联通智算中心环评_中国联通.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8A_跨数据中心训练_SemiAnalysis.md](inbox/digest_drafts/8A_跨数据中心训练_SemiAnalysis.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8B_2026Q1海外大厂CapEx与ROIC核验_国信证券.md](inbox/digest_drafts/8B_2026Q1海外大厂CapEx与ROIC核验_国信证券.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8B_AI对机架与机房的指数级需求_NVIDIA-Google.md](inbox/digest_drafts/8B_AI对机架与机房的指数级需求_NVIDIA-Google.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8B_GB200机房设计指导_NVIDIA.md](inbox/digest_drafts/8B_GB200机房设计指导_NVIDIA.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8B_云端算力芯片全指标_半导体综研.md](inbox/digest_drafts/8B_云端算力芯片全指标_半导体综研.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8B_内存带宽墙与B200利用率_Eliyan.md](inbox/digest_drafts/8B_内存带宽墙与B200利用率_Eliyan.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8B_台积电节点与应用收入_半导体综研.md](inbox/digest_drafts/8B_台积电节点与应用收入_半导体综研.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/8B_美国电网拥堵与DOM电价结构性上涨_中泰证券.md](inbox/digest_drafts/8B_美国电网拥堵与DOM电价结构性上涨_中泰证券.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/9A_GPU云运营手册_SemiAnalysis.md](inbox/digest_drafts/9A_GPU云运营手册_SemiAnalysis.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/9A_数据中心电气系统_SemiAnalysis.md](inbox/digest_drafts/9A_数据中心电气系统_SemiAnalysis.md) | 候选与外部输入 |
| [docs/inbox/digest_drafts/README.md](inbox/digest_drafts/README.md) | 候选与外部输入 |
| [docs/inbox/facts_candidates/README.md](inbox/facts_candidates/README.md) | 候选与外部输入 |
| `docs/inbox/facts_candidates/m01_market_20260817.json` | 候选与外部输入 |
| `docs/inbox/facts_candidates/m02_supply_20260817.json` | 候选与外部输入 |
| `docs/inbox/facts_candidates/m03_demand_20260817.json` | 候选与外部输入 |
| `docs/inbox/facts_candidates/m04_power_20260817.json` | 候选与外部输入 |
| `docs/inbox/facts_candidates/m05_siting_20260817.json` | 候选与外部输入 |
| `docs/inbox/facts_candidates/m06r1_compute_20260817.json` | 候选与外部输入 |
| `docs/inbox/facts_candidates/m06r2_memory_20260817.json` | 候选与外部输入 |
| `docs/inbox/facts_candidates/m06r3_server_20260817.json` | 候选与外部输入 |
| `docs/inbox/facts_candidates/m07_network_20260817.json` | 候选与外部输入 |
| `docs/inbox/facts_candidates/m08_cooling_20260817.json` | 候选与外部输入 |
| `docs/inbox/facts_candidates/m09_supplychain_20260817.json` | 候选与外部输入 |
| `docs/inbox/facts_candidates/m10_ops_20260817.json` | 候选与外部输入 |
| `docs/inbox/facts_candidates/m11_reits_20260817.json` | 候选与外部输入 |
| `docs/inbox/facts_candidates/m12_tokenecon_20260817.json` | 候选与外部输入 |
| `docs/inbox/facts_candidates/m13_utilization_20260817.json` | 候选与外部输入 |
| `docs/inbox/facts_candidates/m14_china_20260817.json` | 候选与外部输入 |
| `docs/inbox/facts_candidates/m15_scenario_20260817.json` | 候选与外部输入 |
| `docs/inbox/framework_proposals/2026-09-06-attachments.json` | 候选与外部输入 |
| [docs/inbox/framework_proposals/2026-09-21-feeder-repos.md](inbox/framework_proposals/2026-09-21-feeder-repos.md) | 候选与外部输入 |
| [docs/inbox/framework_proposals/2026-09-23-product-research-and-site-evolution.md](inbox/framework_proposals/2026-09-23-product-research-and-site-evolution.md) | 候选与外部输入 |
| [docs/inbox/framework_proposals/README.md](inbox/framework_proposals/README.md) | 候选与外部输入 |
| `docs/inbox/framework_proposals/framework_proposal_L1-L4_20260831.html` | 候选与外部输入 |
| [docs/inbox/inresearch-alignment/ALIGNMENT.md](inbox/inresearch-alignment/ALIGNMENT.md) | 候选与外部输入 |
| [docs/inbox/inresearch-alignment/GROUP_ID_RENAMES.md](inbox/inresearch-alignment/GROUP_ID_RENAMES.md) | 候选与外部输入 |
| `docs/inbox/inresearch-alignment/bom_parts_extension.json` | 候选与外部输入 |
| `docs/inbox/inresearch-alignment/companies_patch.json` | 候选与外部输入 |
| `docs/inbox/inresearch-alignment/library_index.json` | 候选与外部输入 |
| `docs/inbox/inresearch-alignment/products.json` | 候选与外部输入 |
| [docs/inbox/needs_password/README.md](inbox/needs_password/README.md) | 候选与外部输入 |
| [docs/inbox/needs_password/needs_password_20260816.csv](inbox/needs_password/needs_password_20260816.csv) | 候选与外部输入 |
| [docs/inbox/path_migrations/README.md](inbox/path_migrations/README.md) | 候选与外部输入 |
| `docs/inbox/path_migrations/cache_key_remap_20260818.json` | 候选与外部输入 |
| [docs/inbox/path_migrations/migration_20260818_01.csv](inbox/path_migrations/migration_20260818_01.csv) | 候选与外部输入 |
| [docs/inbox/project_registry/README.md](inbox/project_registry/README.md) | 候选与外部输入 |
| [docs/inbox/scored_batches/README.md](inbox/scored_batches/README.md) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260815_01.csv](inbox/scored_batches/batch_20260815_01.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260815_02.csv](inbox/scored_batches/batch_20260815_02.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260815_03.csv](inbox/scored_batches/batch_20260815_03.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_01.csv](inbox/scored_batches/batch_20260816_01.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_02.csv](inbox/scored_batches/batch_20260816_02.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_03.csv](inbox/scored_batches/batch_20260816_03.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_04.csv](inbox/scored_batches/batch_20260816_04.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_05.csv](inbox/scored_batches/batch_20260816_05.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_06.csv](inbox/scored_batches/batch_20260816_06.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_07.csv](inbox/scored_batches/batch_20260816_07.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_08.csv](inbox/scored_batches/batch_20260816_08.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_09.csv](inbox/scored_batches/batch_20260816_09.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_10.csv](inbox/scored_batches/batch_20260816_10.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_11.csv](inbox/scored_batches/batch_20260816_11.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_12.csv](inbox/scored_batches/batch_20260816_12.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_13.csv](inbox/scored_batches/batch_20260816_13.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_14.csv](inbox/scored_batches/batch_20260816_14.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_15.csv](inbox/scored_batches/batch_20260816_15.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_16.csv](inbox/scored_batches/batch_20260816_16.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_17.csv](inbox/scored_batches/batch_20260816_17.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_18.csv](inbox/scored_batches/batch_20260816_18.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_19.csv](inbox/scored_batches/batch_20260816_19.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_20.csv](inbox/scored_batches/batch_20260816_20.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_21.csv](inbox/scored_batches/batch_20260816_21.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_22.csv](inbox/scored_batches/batch_20260816_22.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_23.csv](inbox/scored_batches/batch_20260816_23.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_24.csv](inbox/scored_batches/batch_20260816_24.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_25.csv](inbox/scored_batches/batch_20260816_25.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_26.csv](inbox/scored_batches/batch_20260816_26.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_27.csv](inbox/scored_batches/batch_20260816_27.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_28.csv](inbox/scored_batches/batch_20260816_28.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_29.csv](inbox/scored_batches/batch_20260816_29.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_30.csv](inbox/scored_batches/batch_20260816_30.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_31.csv](inbox/scored_batches/batch_20260816_31.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_32.csv](inbox/scored_batches/batch_20260816_32.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_33.csv](inbox/scored_batches/batch_20260816_33.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_34.csv](inbox/scored_batches/batch_20260816_34.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_35.csv](inbox/scored_batches/batch_20260816_35.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_36.csv](inbox/scored_batches/batch_20260816_36.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_37.csv](inbox/scored_batches/batch_20260816_37.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260816_38.csv](inbox/scored_batches/batch_20260816_38.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_39.csv](inbox/scored_batches/batch_20260817_39.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_40.csv](inbox/scored_batches/batch_20260817_40.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_41.csv](inbox/scored_batches/batch_20260817_41.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_42.csv](inbox/scored_batches/batch_20260817_42.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_43.csv](inbox/scored_batches/batch_20260817_43.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_44.csv](inbox/scored_batches/batch_20260817_44.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_45.csv](inbox/scored_batches/batch_20260817_45.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_46.csv](inbox/scored_batches/batch_20260817_46.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_47.csv](inbox/scored_batches/batch_20260817_47.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_48.csv](inbox/scored_batches/batch_20260817_48.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_49.csv](inbox/scored_batches/batch_20260817_49.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_50.csv](inbox/scored_batches/batch_20260817_50.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_51.csv](inbox/scored_batches/batch_20260817_51.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_52.csv](inbox/scored_batches/batch_20260817_52.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_53.csv](inbox/scored_batches/batch_20260817_53.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_54.csv](inbox/scored_batches/batch_20260817_54.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_55.csv](inbox/scored_batches/batch_20260817_55.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_56.csv](inbox/scored_batches/batch_20260817_56.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_57.csv](inbox/scored_batches/batch_20260817_57.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_58.csv](inbox/scored_batches/batch_20260817_58.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_59.csv](inbox/scored_batches/batch_20260817_59.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_60.csv](inbox/scored_batches/batch_20260817_60.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_61.csv](inbox/scored_batches/batch_20260817_61.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_62.csv](inbox/scored_batches/batch_20260817_62.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_63.csv](inbox/scored_batches/batch_20260817_63.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_64.csv](inbox/scored_batches/batch_20260817_64.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_65.csv](inbox/scored_batches/batch_20260817_65.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_66.csv](inbox/scored_batches/batch_20260817_66.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_67.csv](inbox/scored_batches/batch_20260817_67.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_68.csv](inbox/scored_batches/batch_20260817_68.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_69.csv](inbox/scored_batches/batch_20260817_69.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_70.csv](inbox/scored_batches/batch_20260817_70.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_71.csv](inbox/scored_batches/batch_20260817_71.csv) | 候选与外部输入 |
| [docs/inbox/scored_batches/batch_20260817_72.csv](inbox/scored_batches/batch_20260817_72.csv) | 候选与外部输入 |
| [docs/inbox/submissions/README.md](inbox/submissions/README.md) | 配套说明 |
| `docs/inbox/submissions/_selftest/submission.json` | 候选与外部输入 |
| `docs/inbox/submissions/_template/submission.json` | 候选与外部输入 |
| [docs/intern/BATCH01_A_product_links.md](intern/BATCH01_A_product_links.md) | 历史快照 |
| [docs/intern/BATCH01_B_gpu_rental_snapshot.md](intern/BATCH01_B_gpu_rental_snapshot.md) | 历史快照 |
| [docs/intern/BATCH01_C_m11_abs_presales.md](intern/BATCH01_C_m11_abs_presales.md) | 历史快照 |
| [docs/local_reader/ACQUISITION_OPERATIONS.md](local_reader/ACQUISITION_OPERATIONS.md) | 配套说明 |
| [docs/local_reader/CONTINUOUS_READER_DESIGN.md](local_reader/CONTINUOUS_READER_DESIGN.md) | 已退役入口 |
| [docs/local_reader/EDITORIAL_DELIVERY.md](local_reader/EDITORIAL_DELIVERY.md) | 现行规范 |
| [docs/local_reader/KICKOFF_PROMPT.md](local_reader/KICKOFF_PROMPT.md) | 已退役入口 |
| [docs/local_reader/M4_LOCAL_READER.md](local_reader/M4_LOCAL_READER.md) | 配套说明 |
| [docs/local_reader/M4_PREFLIGHT.md](local_reader/M4_PREFLIGHT.md) | 配套说明 |
| [docs/local_reader/M4_TRIAGE_RUNBOOK.md](local_reader/M4_TRIAGE_RUNBOOK.md) | 配套说明 |
| [docs/local_reader/M4_TRIAGE_TASK.md](local_reader/M4_TRIAGE_TASK.md) | 配套说明 |
| [docs/local_reader/PROJECT_BRIEF.md](local_reader/PROJECT_BRIEF.md) | 配套说明 |
| [docs/local_reader/RUN_TO_COMPLETION.md](local_reader/RUN_TO_COMPLETION.md) | 配套说明 |
| [docs/local_reader/SPARK_OPERATIONS.md](local_reader/SPARK_OPERATIONS.md) | 现行规范 |
| [docs/local_setup/ADD_3D_MODEL.md](local_setup/ADD_3D_MODEL.md) | 配套说明 |
| [docs/local_setup/PRODUCT_LIBRARY.md](local_setup/PRODUCT_LIBRARY.md) | 配套说明 |
| [docs/local_setup/README.md](local_setup/README.md) | 配套说明 |
| [docs/local_setup/REPOSITORY_PAGES.md](local_setup/REPOSITORY_PAGES.md) | 配套说明 |
| `docs/local_setup/progress.sh` | 运行代码 |
| `docs/local_setup/setup.sh` | 已退役入口 |
| `docs/local_setup/sync.sh` | 运行代码 |
| [docs/research/2026-09-14/datacenter-cost/README.md](research/2026-09-14/datacenter-cost/README.md) | 配套说明 |
| [docs/research/2026-09-14/datacenter-cost/article.md](research/2026-09-14/datacenter-cost/article.md) | 配套说明 |
| [docs/research/2026-09-14/datacenter-cost/bernstein-report-trace.md](research/2026-09-14/datacenter-cost/bernstein-report-trace.md) | 配套说明 |
| `docs/research/2026-09-14/datacenter-cost/datacenter-cost-model.xlsx` | 项目配置 |
| [docs/research/2026-09-14/datacenter-cost/m4-materials-review.md](research/2026-09-14/datacenter-cost/m4-materials-review.md) | 配套说明 |
| `docs/research/2026-09-14/datacenter-cost/model-results.json` | 项目配置 |
| `docs/research/2026-09-14/datacenter-cost/model.py` | 运行代码 |
| [docs/research/2026-09-14/datacenter-cost/semianalysis-materials-review.md](research/2026-09-14/datacenter-cost/semianalysis-materials-review.md) | 配套说明 |
| [docs/research/2026-09-14/datacenter-cost/sources.md](research/2026-09-14/datacenter-cost/sources.md) | 配套说明 |
| [docs/research/2026-09-27/datacenter-profit/README.md](research/2026-09-27/datacenter-profit/README.md) | 配套说明 |
| [docs/research/2026-09-27/datacenter-profit/article.md](research/2026-09-27/datacenter-profit/article.md) | 配套说明 |
| [docs/research/2026-09-27/datacenter-profit/feedback.md](research/2026-09-27/datacenter-profit/feedback.md) | 配套说明 |
| `docs/research/2026-09-27/datacenter-profit/price_records.py` | 运行代码 |
| `docs/research/2026-09-27/datacenter-profit/profit-model-results.json` | 项目配置 |
| `docs/research/2026-09-27/datacenter-profit/profit-model.py` | 运行代码 |
| [docs/research/2026-09-27/datacenter-profit/sources.md](research/2026-09-27/datacenter-profit/sources.md) | 配套说明 |
| [docs/research/2026-10-01/ai-walle/README.md](research/2026-10-01/ai-walle/README.md) | 配套说明 |
| [docs/research/2026-10-01/ai-walle/article-review.md](research/2026-10-01/ai-walle/article-review.md) | 配套说明 |
| [docs/research/2026-10-01/ai-walle/article.md](research/2026-10-01/ai-walle/article.md) | 配套说明 |
| `docs/research/2026-10-01/ai-walle/cards.json` | 项目配置 |
| [docs/research/2026-10-01/ai-walle/feedback.md](research/2026-10-01/ai-walle/feedback.md) | 配套说明 |
| [docs/research/2026-10-01/ai-walle/review.md](research/2026-10-01/ai-walle/review.md) | 配套说明 |
| `docs/research/2026-10-01/ai-walle/sources.json` | 项目配置 |
| [docs/research/2026-10-09/us-datacenter-power/INTAKE-20261009.md](research/2026-10-09/us-datacenter-power/INTAKE-20261009.md) | 配套说明 |
| [docs/research/2026-10-09/us-datacenter-power/README.md](research/2026-10-09/us-datacenter-power/README.md) | 配套说明 |
| [docs/research/datacenter-economics/README.md](research/datacenter-economics/README.md) | 配套说明 |
| `docs/research/datacenter-economics/model.py` | 运行代码 |
| `docs/research/datacenter-economics/results.json` | 项目配置 |
| [docs/research/datacenter-tco/README.md](research/datacenter-tco/README.md) | 配套说明 |
| `docs/research/datacenter-tco/model.py` | 运行代码 |
| `docs/research/datacenter-tco/results.json` | 项目配置 |
| [docs/reviews/2026-09-06/2026-09-06_NODE_RESEARCH_OVERVIEW_PROPOSAL.md](reviews/2026-09-06/2026-09-06_NODE_RESEARCH_OVERVIEW_PROPOSAL.md) | 历史快照 |
| [docs/reviews/2026-09-06/CURRENT_BASELINE_ALIGNMENT.md](reviews/2026-09-06/CURRENT_BASELINE_ALIGNMENT.md) | 历史快照 |
| [docs/reviews/2026-09-06/IMPLEMENTATION.md](reviews/2026-09-06/IMPLEMENTATION.md) | 历史快照 |
| [docs/reviews/2026-09-06/RESEARCH_ARCHITECTURE_V2.md](reviews/2026-09-06/RESEARCH_ARCHITECTURE_V2.md) | 已采用设计依据 |
| [docs/reviews/2026-09-06/REVIEW.md](reviews/2026-09-06/REVIEW.md) | 历史快照 |
| [docs/reviews/2026-09-06/architecture-physical.md](reviews/2026-09-06/architecture-physical.md) | 历史快照 |
| [docs/reviews/2026-09-06/architecture-research.md](reviews/2026-09-06/architecture-research.md) | 历史快照 |
| [docs/reviews/2026-09-06/architecture-valuechain.md](reviews/2026-09-06/architecture-valuechain.md) | 历史快照 |
| [docs/reviews/2026-09-06/architecture-verification.md](reviews/2026-09-06/architecture-verification.md) | 历史快照 |
| [docs/reviews/2026-09-06/backend.md](reviews/2026-09-06/backend.md) | 历史快照 |
| `docs/reviews/2026-09-06/build_architecture_pdf.py` | 历史快照 |
| `docs/reviews/2026-09-06/evidence/backend-probes.json` | 历史快照 |
| `docs/reviews/2026-09-06/evidence/http-probes.json` | 历史快照 |
| `docs/reviews/2026-09-06/evidence/research-stats.json` | 历史快照 |
| `docs/reviews/2026-09-06/evidence/runtime.json` | 历史快照 |
| `docs/reviews/2026-09-06/evidence/sync-probes.json` | 历史快照 |
| [docs/reviews/2026-09-06/evidence/verification.md](reviews/2026-09-06/evidence/verification.md) | 历史快照 |
| [docs/reviews/2026-09-06/frontend.md](reviews/2026-09-06/frontend.md) | 历史快照 |
| [docs/reviews/2026-09-06/research.md](reviews/2026-09-06/research.md) | 历史快照 |
| [docs/reviews/2026-09-06/spark-storage.md](reviews/2026-09-06/spark-storage.md) | 历史快照 |
| [docs/reviews/2026-09-12/IMPLEMENTATION.md](reviews/2026-09-12/IMPLEMENTATION.md) | 历史快照 |
| [docs/reviews/2026-09-13/architecture/DELIVERY.md](reviews/2026-09-13/architecture/DELIVERY.md) | 历史快照 |
| [docs/reviews/2026-09-13/architecture/README.md](reviews/2026-09-13/architecture/README.md) | 历史快照 |
| `docs/reviews/2026-09-13/architecture/after.json` | 历史快照 |
| `docs/reviews/2026-09-13/architecture/audit.py` | 历史快照 |
| `docs/reviews/2026-09-13/architecture/baseline-result-divergence.json` | 历史快照 |
| `docs/reviews/2026-09-13/architecture/baseline.json` | 历史快照 |
| [docs/reviews/2026-09-13/architecture/consumers.csv](reviews/2026-09-13/architecture/consumers.csv) | 历史快照 |
| `docs/reviews/2026-09-13/architecture/dependency-audit.json` | 历史快照 |
| `docs/reviews/2026-09-13/architecture/deployment.json` | 历史快照 |
| [docs/reviews/2026-09-13/architecture/external-consumers.csv](reviews/2026-09-13/architecture/external-consumers.csv) | 历史快照 |
| [docs/reviews/2026-09-13/architecture/file-migration.csv](reviews/2026-09-13/architecture/file-migration.csv) | 历史快照 |
| [docs/reviews/2026-09-13/architecture/legacy-removal.csv](reviews/2026-09-13/architecture/legacy-removal.csv) | 历史快照 |
| [docs/reviews/2026-09-13/architecture/new-files.csv](reviews/2026-09-13/architecture/new-files.csv) | 历史快照 |
| [docs/reviews/2026-09-13/architecture/provenance-debt.csv](reviews/2026-09-13/architecture/provenance-debt.csv) | 历史快照 |
| [docs/reviews/2026-09-13/architecture/public-consumers.csv](reviews/2026-09-13/architecture/public-consumers.csv) | 历史快照 |
| `docs/reviews/2026-09-13/architecture/real-reader-flow.json` | 历史快照 |
| [docs/reviews/2026-09-13/architecture/shared-implementations.csv](reviews/2026-09-13/architecture/shared-implementations.csv) | 历史快照 |
| [docs/reviews/2026-09-13/architecture/source-reference-debt.csv](reviews/2026-09-13/architecture/source-reference-debt.csv) | 历史快照 |
| `docs/reviews/2026-09-13/architecture/verification.json` | 历史快照 |
| [docs/reviews/2026-09-13/c3-a-review/DELIVERY.md](reviews/2026-09-13/c3-a-review/DELIVERY.md) | 历史快照 |
| [docs/reviews/2026-09-13/data-authority/DELIVERY.md](reviews/2026-09-13/data-authority/DELIVERY.md) | 历史快照 |
| [docs/reviews/2026-09-13/data-authority/PLAN.md](reviews/2026-09-13/data-authority/PLAN.md) | 历史快照 |
| `docs/reviews/2026-09-13/data-authority/audit.py` | 历史快照 |
| [docs/reviews/2026-09-13/data-authority/consumers-after.csv](reviews/2026-09-13/data-authority/consumers-after.csv) | 历史快照 |
| [docs/reviews/2026-09-13/data-authority/consumers-before.csv](reviews/2026-09-13/data-authority/consumers-before.csv) | 历史快照 |
| [docs/reviews/2026-09-13/data-authority/file-plan.csv](reviews/2026-09-13/data-authority/file-plan.csv) | 历史快照 |
| [docs/reviews/2026-09-13/data-authority/file-results.csv](reviews/2026-09-13/data-authority/file-results.csv) | 历史快照 |
| [docs/reviews/2026-09-13/data-authority/legacy-removal.csv](reviews/2026-09-13/data-authority/legacy-removal.csv) | 历史快照 |
| `docs/reviews/2026-09-13/data-authority/production-before.json` | 历史快照 |
| [docs/reviews/2026-09-13/data-authority/public-consumers.csv](reviews/2026-09-13/data-authority/public-consumers.csv) | 历史快照 |
| `docs/reviews/2026-09-13/data-authority/scope.json` | 历史快照 |
| `docs/reviews/2026-09-13/data-authority/statistics-after.json` | 历史快照 |
| `docs/reviews/2026-09-13/data-authority/statistics-before.json` | 历史快照 |
| [docs/reviews/2026-09-13/data-authority/storage-consumers.csv](reviews/2026-09-13/data-authority/storage-consumers.csv) | 历史快照 |
| [docs/reviews/2026-09-13/deep-read/DELIVERY.md](reviews/2026-09-13/deep-read/DELIVERY.md) | 历史快照 |
| [docs/reviews/2026-09-13/deep-read/PLAN.md](reviews/2026-09-13/deep-read/PLAN.md) | 历史快照 |
| `docs/reviews/2026-09-13/deep-read/audit.py` | 历史快照 |
| `docs/reviews/2026-09-13/deep-read/baseline.json` | 历史快照 |
| [docs/reviews/2026-09-13/deep-read/consumers-after.csv](reviews/2026-09-13/deep-read/consumers-after.csv) | 历史快照 |
| [docs/reviews/2026-09-13/deep-read/consumers-before.csv](reviews/2026-09-13/deep-read/consumers-before.csv) | 历史快照 |
| `docs/reviews/2026-09-13/deep-read/contracts_audit.py` | 历史快照 |
| `docs/reviews/2026-09-13/deep-read/dependency-audit.json` | 历史快照 |
| [docs/reviews/2026-09-13/deep-read/file-plan.csv](reviews/2026-09-13/deep-read/file-plan.csv) | 历史快照 |
| [docs/reviews/2026-09-13/deep-read/file-results.csv](reviews/2026-09-13/deep-read/file-results.csv) | 历史快照 |
| [docs/reviews/2026-09-13/deep-read/functions-before.csv](reviews/2026-09-13/deep-read/functions-before.csv) | 历史快照 |
| [docs/reviews/2026-09-13/deep-read/integration-files.csv](reviews/2026-09-13/deep-read/integration-files.csv) | 历史快照 |
| [docs/reviews/2026-09-13/deep-read/public-contracts.csv](reviews/2026-09-13/deep-read/public-contracts.csv) | 历史快照 |
| `docs/reviews/2026-09-13/deep-read/real-flow.json` | 历史快照 |
| `docs/reviews/2026-09-13/deep-read/statistics-after.json` | 历史快照 |
| `docs/reviews/2026-09-13/deep-read/statistics-before.json` | 历史快照 |
| `docs/reviews/2026-09-13/deep-read/test-migration.json` | 历史快照 |
| [docs/reviews/2026-09-13/deep-read/test-results.csv](reviews/2026-09-13/deep-read/test-results.csv) | 历史快照 |
| `docs/reviews/2026-09-13/deep-read/verification.json` | 历史快照 |
| [docs/reviews/2026-09-13/fact-conflicts/DELIVERY.md](reviews/2026-09-13/fact-conflicts/DELIVERY.md) | 历史快照 |
| [docs/reviews/2026-09-13/news-projection/DELIVERY.md](reviews/2026-09-13/news-projection/DELIVERY.md) | 历史快照 |
| [docs/reviews/2026-09-13/news-projection/PLAN.md](reviews/2026-09-13/news-projection/PLAN.md) | 历史快照 |
| `docs/reviews/2026-09-13/news-projection/audit.py` | 历史快照 |
| [docs/reviews/2026-09-13/news-projection/consumers-before.csv](reviews/2026-09-13/news-projection/consumers-before.csv) | 历史快照 |
| [docs/reviews/2026-09-13/news-projection/file-plan.csv](reviews/2026-09-13/news-projection/file-plan.csv) | 历史快照 |
| [docs/reviews/2026-09-13/news-projection/file-results.csv](reviews/2026-09-13/news-projection/file-results.csv) | 历史快照 |
| [docs/reviews/2026-09-13/news-projection/legacy-removal.csv](reviews/2026-09-13/news-projection/legacy-removal.csv) | 历史快照 |
| `docs/reviews/2026-09-13/news-projection/payload-after.json` | 历史快照 |
| `docs/reviews/2026-09-13/news-projection/payload-before.json` | 历史快照 |
| [docs/reviews/2026-09-13/news-projection/public-consumers.csv](reviews/2026-09-13/news-projection/public-consumers.csv) | 历史快照 |
| `docs/reviews/2026-09-13/news-projection/scope.json` | 历史快照 |
| `docs/reviews/2026-09-13/news-projection/statistics-after.json` | 历史快照 |
| `docs/reviews/2026-09-13/news-projection/statistics-before.json` | 历史快照 |
| [docs/reviews/2026-09-13/reading-authority/DELIVERY.md](reviews/2026-09-13/reading-authority/DELIVERY.md) | 历史快照 |
| [docs/reviews/2026-09-13/reading-authority/INTEGRATION.md](reviews/2026-09-13/reading-authority/INTEGRATION.md) | 历史快照 |
| [docs/reviews/2026-09-13/reading-authority/PLAN.md](reviews/2026-09-13/reading-authority/PLAN.md) | 历史快照 |
| `docs/reviews/2026-09-13/reading-authority/audit.py` | 历史快照 |
| `docs/reviews/2026-09-13/reading-authority/baseline.json` | 历史快照 |
| [docs/reviews/2026-09-13/reading-authority/consumers-after.csv](reviews/2026-09-13/reading-authority/consumers-after.csv) | 历史快照 |
| [docs/reviews/2026-09-13/reading-authority/consumers-before.csv](reviews/2026-09-13/reading-authority/consumers-before.csv) | 历史快照 |
| [docs/reviews/2026-09-13/reading-authority/file-plan.csv](reviews/2026-09-13/reading-authority/file-plan.csv) | 历史快照 |
| [docs/reviews/2026-09-13/reading-authority/file-results.csv](reviews/2026-09-13/reading-authority/file-results.csv) | 历史快照 |
| [docs/reviews/2026-09-13/reading-authority/method-migration.csv](reviews/2026-09-13/reading-authority/method-migration.csv) | 历史快照 |
| [docs/reviews/2026-09-13/reading-authority/public-consumers.csv](reviews/2026-09-13/reading-authority/public-consumers.csv) | 历史快照 |
| `docs/reviews/2026-09-13/reading-authority/real-flow.json` | 历史快照 |
| `docs/reviews/2026-09-13/reading-authority/statistics-after.json` | 历史快照 |
| `docs/reviews/2026-09-13/reading-authority/statistics-before.json` | 历史快照 |
| [docs/reviews/2026-09-13/reading-authority/test-migration.csv](reviews/2026-09-13/reading-authority/test-migration.csv) | 历史快照 |
| `docs/reviews/2026-09-13/reading-authority/test-migration.json` | 历史快照 |
| `docs/reviews/2026-09-13/reading-authority/test-renames.json` | 历史快照 |
| `docs/reviews/2026-09-13/reading-authority/verification.json` | 历史快照 |
| [docs/reviews/2026-09-13/reading-revisions/DELIVERY.md](reviews/2026-09-13/reading-revisions/DELIVERY.md) | 历史快照 |
| [docs/reviews/2026-09-13/reading-revisions/PLAN.md](reviews/2026-09-13/reading-revisions/PLAN.md) | 历史快照 |
| `docs/reviews/2026-09-13/reading-revisions/baseline.json` | 历史快照 |
| [docs/reviews/2026-09-13/reading-revisions/consumers-after.csv](reviews/2026-09-13/reading-revisions/consumers-after.csv) | 历史快照 |
| [docs/reviews/2026-09-13/reading-revisions/consumers-before.csv](reviews/2026-09-13/reading-revisions/consumers-before.csv) | 历史快照 |
| `docs/reviews/2026-09-13/reading-revisions/dependencies.json` | 历史快照 |
| [docs/reviews/2026-09-13/reading-revisions/file-plan.csv](reviews/2026-09-13/reading-revisions/file-plan.csv) | 历史快照 |
| [docs/reviews/2026-09-13/reading-revisions/file-results.csv](reviews/2026-09-13/reading-revisions/file-results.csv) | 历史快照 |
| [docs/reviews/2026-09-13/reading-revisions/public-contracts.csv](reviews/2026-09-13/reading-revisions/public-contracts.csv) | 历史快照 |
| `docs/reviews/2026-09-13/reading-revisions/real-flow.json` | 历史快照 |
| `docs/reviews/2026-09-13/reading-revisions/statistics-after.json` | 历史快照 |
| `docs/reviews/2026-09-13/reading-revisions/statistics-before.json` | 历史快照 |
| `docs/reviews/2026-09-13/reading-revisions/verification.json` | 历史快照 |
| [docs/reviews/2026-09-13/research-summary/DELIVERY.md](reviews/2026-09-13/research-summary/DELIVERY.md) | 历史快照 |
| [docs/reviews/2026-09-13/research-summary/PLAN.md](reviews/2026-09-13/research-summary/PLAN.md) | 历史快照 |
| `docs/reviews/2026-09-13/research-summary/audit.py` | 历史快照 |
| [docs/reviews/2026-09-13/research-summary/consumers-before.csv](reviews/2026-09-13/research-summary/consumers-before.csv) | 历史快照 |
| [docs/reviews/2026-09-13/research-summary/file-plan.csv](reviews/2026-09-13/research-summary/file-plan.csv) | 历史快照 |
| [docs/reviews/2026-09-13/research-summary/file-results.csv](reviews/2026-09-13/research-summary/file-results.csv) | 历史快照 |
| [docs/reviews/2026-09-13/research-summary/legacy-removal.csv](reviews/2026-09-13/research-summary/legacy-removal.csv) | 历史快照 |
| `docs/reviews/2026-09-13/research-summary/payload-evidence.json` | 历史快照 |
| [docs/reviews/2026-09-13/research-summary/public-consumers.csv](reviews/2026-09-13/research-summary/public-consumers.csv) | 历史快照 |
| `docs/reviews/2026-09-13/research-summary/scope.json` | 历史快照 |
| `docs/reviews/2026-09-13/research-summary/statistics-after.json` | 历史快照 |
| `docs/reviews/2026-09-13/research-summary/statistics-before.json` | 历史快照 |
| [docs/reviews/2026-09-13/scene-interaction/DELIVERY.md](reviews/2026-09-13/scene-interaction/DELIVERY.md) | 历史快照 |
| [docs/reviews/2026-09-13/scene-interaction/PLAN.md](reviews/2026-09-13/scene-interaction/PLAN.md) | 历史快照 |
| `docs/reviews/2026-09-13/scene-interaction/audit.py` | 历史快照 |
| [docs/reviews/2026-09-13/scene-interaction/consumers-before.csv](reviews/2026-09-13/scene-interaction/consumers-before.csv) | 历史快照 |
| [docs/reviews/2026-09-13/scene-interaction/file-plan.csv](reviews/2026-09-13/scene-interaction/file-plan.csv) | 历史快照 |
| [docs/reviews/2026-09-13/scene-interaction/file-results.csv](reviews/2026-09-13/scene-interaction/file-results.csv) | 历史快照 |
| [docs/reviews/2026-09-13/scene-interaction/legacy-removal.csv](reviews/2026-09-13/scene-interaction/legacy-removal.csv) | 历史快照 |
| `docs/reviews/2026-09-13/scene-interaction/news-release-verification.json` | 历史快照 |
| `docs/reviews/2026-09-13/scene-interaction/previous-release-verification.json` | 历史快照 |
| [docs/reviews/2026-09-13/scene-interaction/public-consumers.csv](reviews/2026-09-13/scene-interaction/public-consumers.csv) | 历史快照 |
| `docs/reviews/2026-09-13/scene-interaction/scope.json` | 历史快照 |
| `docs/reviews/2026-09-13/scene-interaction/statistics-after.json` | 历史快照 |
| `docs/reviews/2026-09-13/scene-interaction/statistics-before.json` | 历史快照 |
| [docs/reviews/2026-09-13/standards/DELIVERY.md](reviews/2026-09-13/standards/DELIVERY.md) | 历史快照 |
| [docs/reviews/2026-09-13/standards/INTEGRATION_PLAN.md](reviews/2026-09-13/standards/INTEGRATION_PLAN.md) | 历史快照 |
| [docs/reviews/2026-09-13/standards/PLAN.md](reviews/2026-09-13/standards/PLAN.md) | 历史快照 |
| [docs/reviews/2026-09-13/standards/POLICY_MATRIX.md](reviews/2026-09-13/standards/POLICY_MATRIX.md) | 历史快照 |
| `docs/reviews/2026-09-13/standards/baseline-probes.json` | 历史快照 |
| `docs/reviews/2026-09-13/standards/cli-flow.json` | 历史快照 |
| [docs/reviews/2026-09-13/standards/consumers-after.csv](reviews/2026-09-13/standards/consumers-after.csv) | 历史快照 |
| `docs/reviews/2026-09-13/standards/consumers-before.json` | 历史快照 |
| `docs/reviews/2026-09-13/standards/dependencies.json` | 历史快照 |
| [docs/reviews/2026-09-13/standards/file-changes.csv](reviews/2026-09-13/standards/file-changes.csv) | 历史快照 |
| [docs/reviews/2026-09-13/standards/integrated-POLICY_MATRIX.md](reviews/2026-09-13/standards/integrated-POLICY_MATRIX.md) | 历史快照 |
| [docs/reviews/2026-09-13/standards/integrated-consumers-after.csv](reviews/2026-09-13/standards/integrated-consumers-after.csv) | 历史快照 |
| `docs/reviews/2026-09-13/standards/integrated-dependencies.json` | 历史快照 |
| [docs/reviews/2026-09-13/standards/integrated-file-changes.csv](reviews/2026-09-13/standards/integrated-file-changes.csv) | 历史快照 |
| `docs/reviews/2026-09-13/standards/integrated-statistics.json` | 历史快照 |
| `docs/reviews/2026-09-13/standards/integrated-verification.json` | 历史快照 |
| `docs/reviews/2026-09-13/standards/statistics.json` | 历史快照 |
| `docs/reviews/2026-09-13/standards/verification.json` | 历史快照 |
| [docs/reviews/2026-09-13/verification-map-repair.md](reviews/2026-09-13/verification-map-repair.md) | 历史快照 |
| [docs/reviews/2026-09-14/cli-root/DELIVERY.md](reviews/2026-09-14/cli-root/DELIVERY.md) | 历史快照 |
| [docs/reviews/2026-09-14/cli-root/PLAN.md](reviews/2026-09-14/cli-root/PLAN.md) | 历史快照 |
| `docs/reviews/2026-09-14/cli-root/audit.py` | 历史快照 |
| `docs/reviews/2026-09-14/cli-root/baseline.json` | 历史快照 |
| [docs/reviews/2026-09-14/cli-root/consumers-after.csv](reviews/2026-09-14/cli-root/consumers-after.csv) | 历史快照 |
| [docs/reviews/2026-09-14/cli-root/consumers-before.csv](reviews/2026-09-14/cli-root/consumers-before.csv) | 历史快照 |
| [docs/reviews/2026-09-14/cli-root/dispatch.csv](reviews/2026-09-14/cli-root/dispatch.csv) | 历史快照 |
| [docs/reviews/2026-09-14/cli-root/file-plan.csv](reviews/2026-09-14/cli-root/file-plan.csv) | 历史快照 |
| [docs/reviews/2026-09-14/cli-root/file-results.csv](reviews/2026-09-14/cli-root/file-results.csv) | 历史快照 |
| [docs/reviews/2026-09-14/cli-root/legacy-removal.csv](reviews/2026-09-14/cli-root/legacy-removal.csv) | 历史快照 |
| `docs/reviews/2026-09-14/cli-root/scope.json` | 历史快照 |
| `docs/reviews/2026-09-14/cli-root/statistics-after.json` | 历史快照 |
| `docs/reviews/2026-09-14/cli-root/statistics-before.json` | 历史快照 |
| [docs/reviews/2026-09-14/code-review/REVIEW.md](reviews/2026-09-14/code-review/REVIEW.md) | 历史快照 |
| `docs/reviews/2026-09-14/code-review/screenshots/bom3d-folk-light-1440-drill-hidden.png` | 历史快照 |
| `docs/reviews/2026-09-14/code-review/screenshots/materials-skinbar-72px.png` | 历史快照 |
| `docs/reviews/2026-09-14/code-review/screenshots/ops-member-folk-light-1440.png` | 历史快照 |
| `docs/reviews/2026-09-14/code-review/screenshots/rack3d-gpu-dossier-black-preview.png` | 历史快照 |
| [docs/reviews/2026-09-14/model-assets/DELIVERY.md](reviews/2026-09-14/model-assets/DELIVERY.md) | 历史快照 |
| [docs/reviews/2026-09-14/model-assets/INTEGRATION.md](reviews/2026-09-14/model-assets/INTEGRATION.md) | 历史快照 |
| [docs/reviews/2026-09-14/model-assets/PLAN.md](reviews/2026-09-14/model-assets/PLAN.md) | 历史快照 |
| `docs/reviews/2026-09-14/model-assets/audit.py` | 历史快照 |
| `docs/reviews/2026-09-14/model-assets/baseline.json` | 历史快照 |
| [docs/reviews/2026-09-14/model-assets/consumers-before.csv](reviews/2026-09-14/model-assets/consumers-before.csv) | 历史快照 |
| [docs/reviews/2026-09-14/model-assets/file-plan.csv](reviews/2026-09-14/model-assets/file-plan.csv) | 历史快照 |
| [docs/reviews/2026-09-14/model-assets/file-results.csv](reviews/2026-09-14/model-assets/file-results.csv) | 历史快照 |
| [docs/reviews/2026-09-14/model-assets/legacy-removal.csv](reviews/2026-09-14/model-assets/legacy-removal.csv) | 历史快照 |
| [docs/reviews/2026-09-14/model-assets/public-consumers.csv](reviews/2026-09-14/model-assets/public-consumers.csv) | 历史快照 |
| [docs/reviews/2026-09-14/model-assets/public-contracts.csv](reviews/2026-09-14/model-assets/public-contracts.csv) | 历史快照 |
| `docs/reviews/2026-09-14/model-assets/scope.json` | 历史快照 |
| `docs/reviews/2026-09-14/model-assets/statistics-after.json` | 历史快照 |
| `docs/reviews/2026-09-14/model-assets/statistics-before.json` | 历史快照 |
| [docs/reviews/2026-09-14/scene-bootstrap/DELIVERY.md](reviews/2026-09-14/scene-bootstrap/DELIVERY.md) | 历史快照 |
| [docs/reviews/2026-09-14/scene-bootstrap/PLAN.md](reviews/2026-09-14/scene-bootstrap/PLAN.md) | 历史快照 |
| `docs/reviews/2026-09-14/scene-bootstrap/audit.py` | 历史快照 |
| `docs/reviews/2026-09-14/scene-bootstrap/baseline.json` | 历史快照 |
| `docs/reviews/2026-09-14/scene-bootstrap/ci-timeout.json` | 历史快照 |
| [docs/reviews/2026-09-14/scene-bootstrap/consumers-before.csv](reviews/2026-09-14/scene-bootstrap/consumers-before.csv) | 历史快照 |
| [docs/reviews/2026-09-14/scene-bootstrap/file-plan.csv](reviews/2026-09-14/scene-bootstrap/file-plan.csv) | 历史快照 |
| [docs/reviews/2026-09-14/scene-bootstrap/file-results.csv](reviews/2026-09-14/scene-bootstrap/file-results.csv) | 历史快照 |
| [docs/reviews/2026-09-14/scene-bootstrap/legacy-removal.csv](reviews/2026-09-14/scene-bootstrap/legacy-removal.csv) | 历史快照 |
| [docs/reviews/2026-09-14/scene-bootstrap/public-consumers.csv](reviews/2026-09-14/scene-bootstrap/public-consumers.csv) | 历史快照 |
| `docs/reviews/2026-09-14/scene-bootstrap/scope.json` | 历史快照 |
| `docs/reviews/2026-09-14/scene-bootstrap/statistics-after.json` | 历史快照 |
| `docs/reviews/2026-09-14/scene-bootstrap/statistics-before.json` | 历史快照 |
| [docs/reviews/2026-09-14/scene-framing/DELIVERY.md](reviews/2026-09-14/scene-framing/DELIVERY.md) | 历史快照 |
| [docs/reviews/2026-09-14/scene-framing/INTEGRATION.md](reviews/2026-09-14/scene-framing/INTEGRATION.md) | 历史快照 |
| [docs/reviews/2026-09-14/scene-framing/PLAN.md](reviews/2026-09-14/scene-framing/PLAN.md) | 历史快照 |
| `docs/reviews/2026-09-14/scene-framing/audit.py` | 历史快照 |
| `docs/reviews/2026-09-14/scene-framing/baseline.json` | 历史快照 |
| [docs/reviews/2026-09-14/scene-framing/consumers-before.csv](reviews/2026-09-14/scene-framing/consumers-before.csv) | 历史快照 |
| [docs/reviews/2026-09-14/scene-framing/file-plan.csv](reviews/2026-09-14/scene-framing/file-plan.csv) | 历史快照 |
| [docs/reviews/2026-09-14/scene-framing/file-results.csv](reviews/2026-09-14/scene-framing/file-results.csv) | 历史快照 |
| [docs/reviews/2026-09-14/scene-framing/legacy-removal.csv](reviews/2026-09-14/scene-framing/legacy-removal.csv) | 历史快照 |
| [docs/reviews/2026-09-14/scene-framing/public-consumers.csv](reviews/2026-09-14/scene-framing/public-consumers.csv) | 历史快照 |
| [docs/reviews/2026-09-14/scene-framing/public-contracts.csv](reviews/2026-09-14/scene-framing/public-contracts.csv) | 历史快照 |
| `docs/reviews/2026-09-14/scene-framing/scope.json` | 历史快照 |
| `docs/reviews/2026-09-14/scene-framing/statistics-after.json` | 历史快照 |
| `docs/reviews/2026-09-14/scene-framing/statistics-before.json` | 历史快照 |
| [docs/reviews/2026-09-14/scene-resources/DELIVERY.md](reviews/2026-09-14/scene-resources/DELIVERY.md) | 历史快照 |
| [docs/reviews/2026-09-14/scene-resources/INTEGRATION.md](reviews/2026-09-14/scene-resources/INTEGRATION.md) | 历史快照 |
| [docs/reviews/2026-09-14/scene-resources/PLAN.md](reviews/2026-09-14/scene-resources/PLAN.md) | 历史快照 |
| `docs/reviews/2026-09-14/scene-resources/audit.py` | 历史快照 |
| `docs/reviews/2026-09-14/scene-resources/baseline.json` | 历史快照 |
| [docs/reviews/2026-09-14/scene-resources/consumers-after.csv](reviews/2026-09-14/scene-resources/consumers-after.csv) | 历史快照 |
| [docs/reviews/2026-09-14/scene-resources/consumers-before.csv](reviews/2026-09-14/scene-resources/consumers-before.csv) | 历史快照 |
| [docs/reviews/2026-09-14/scene-resources/file-plan.csv](reviews/2026-09-14/scene-resources/file-plan.csv) | 历史快照 |
| [docs/reviews/2026-09-14/scene-resources/file-results.csv](reviews/2026-09-14/scene-resources/file-results.csv) | 历史快照 |
| [docs/reviews/2026-09-14/scene-resources/legacy-removal.csv](reviews/2026-09-14/scene-resources/legacy-removal.csv) | 历史快照 |
| `docs/reviews/2026-09-14/scene-resources/scope.json` | 历史快照 |
| `docs/reviews/2026-09-14/scene-resources/statistics-after.json` | 历史快照 |
| `docs/reviews/2026-09-14/scene-resources/statistics-before.json` | 历史快照 |
| [docs/reviews/2026-09-15/l1-pipeline/PLAN.md](reviews/2026-09-15/l1-pipeline/PLAN.md) | 历史快照 |
| [docs/reviews/2026-09-15/l1-pipeline/consumers.csv](reviews/2026-09-15/l1-pipeline/consumers.csv) | 历史快照 |
| [docs/reviews/2026-09-15/l1-pipeline/file-plan.csv](reviews/2026-09-15/l1-pipeline/file-plan.csv) | 历史快照 |
| [docs/reviews/2026-09-15/task-authority/PLAN.md](reviews/2026-09-15/task-authority/PLAN.md) | 历史快照 |
| `docs/reviews/2026-09-15/task-authority/audit.py` | 历史快照 |
| [docs/reviews/2026-09-15/task-authority/file-plan.csv](reviews/2026-09-15/task-authority/file-plan.csv) | 历史快照 |
| `docs/reviews/2026-09-15/task-authority/scope.json` | 历史快照 |
| [docs/reviews/2026-09-21/supply-center/DELIVERY.md](reviews/2026-09-21/supply-center/DELIVERY.md) | 历史快照 |
| [docs/reviews/2026-09-27/nvidia-m5-aws/DELIVERY.md](reviews/2026-09-27/nvidia-m5-aws/DELIVERY.md) | 历史快照 |
| [docs/reviews/2026-09-28/alignment/AUDIT.md](reviews/2026-09-28/alignment/AUDIT.md) | 历史快照 |
| `docs/reviews/2026-09-28/architecture/ARCHITECTURE.svg` | 历史快照 |
| [docs/reviews/2026-09-28/architecture/README.md](reviews/2026-09-28/architecture/README.md) | 历史快照 |
| [docs/reviews/2026-09-28/bom-recut/PROPOSAL.md](reviews/2026-09-28/bom-recut/PROPOSAL.md) | 历史快照 |
| [docs/reviews/2026-09-28/dashboard/PROPOSAL.md](reviews/2026-09-28/dashboard/PROPOSAL.md) | 历史快照 |
| [docs/reviews/2026-09-28/model/PROPOSAL.md](reviews/2026-09-28/model/PROPOSAL.md) | 历史快照 |
| [docs/reviews/2026-09-28/site/PROPOSAL.md](reviews/2026-09-28/site/PROPOSAL.md) | 历史快照 |
| [docs/reviews/2026-09-29/inews/README.md](reviews/2026-09-29/inews/README.md) | 历史快照 |
| [docs/reviews/2026-09-29/infra/README.md](reviews/2026-09-29/infra/README.md) | 历史快照 |
| [docs/reviews/2026-09-29/skeleton/README.md](reviews/2026-09-29/skeleton/README.md) | 历史快照 |
| [docs/reviews/2026-09-29/verify/README.md](reviews/2026-09-29/verify/README.md) | 历史快照 |
| `docs/reviews/2026-09-29/verify/aws.sh` | 历史快照 |
| `docs/reviews/2026-09-29/verify/local.sh` | 历史快照 |
| `docs/reviews/2026-09-29/verify/macmini.sh` | 历史快照 |
| `docs/reviews/2026-09-29/verify/spark.sh` | 历史快照 |
| [docs/reviews/2026-10-02/homepage/DELIVERY.md](reviews/2026-10-02/homepage/DELIVERY.md) | 历史快照 |
| [docs/reviews/2026-10-09/research-publication/README.md](reviews/2026-10-09/research-publication/README.md) | 历史快照 |
| `docs/reviews/2026-10-09/research-publication/old-ready12-followup.json` | 历史快照 |
| `docs/reviews/2026-10-09/research-publication/original-23-stage-1422.json` | 历史快照 |
| `docs/reviews/2026-10-09/research-publication/original-23-stage.json` | 历史快照 |
| `docs/reviews/2026-10-09/research-publication/pr453-actual-closure.json` | 历史快照 |
| `docs/reviews/2026-10-09/research-publication/receipts.json` | 历史快照 |
| `docs/source/全球数据中心行业_项目状态与玩家清单_v0.2_信源追溯版_2026-07-23.xlsx` | 项目配置 |
| `docs/source/全球数据中心行业深度研究Q&A总报告_Q1-Q35_v1.0(2).docx` | 项目配置 |
| `docs/source/全球数据中心行业现状_参考初稿版式v0.2_信源追溯版_2026-07-23.docx` | 项目配置 |
| `docs/source/全球数据中心行业现状_参考初稿版式v0.2_信源追溯版_2026-07-23.pdf` | 项目配置 |
| [framework/00_overview.md](../framework/00_overview.md) | 现行规范 |
| [framework/01_data_standards.md](../framework/01_data_standards.md) | 现行规范 |
| [framework/02_knowledge_format.md](../framework/02_knowledge_format.md) | 现行规范 |
| [framework/03_bom_and_collaboration.md](../framework/03_bom_and_collaboration.md) | 现行规范 |
| [framework/04_reading_scoring_standard.md](../framework/04_reading_scoring_standard.md) | 现行规范 |
| [framework/05_interface_system.md](../framework/05_interface_system.md) | 现行规范 |
| [framework/05_source_map.md](../framework/05_source_map.md) | 配套说明 |
| [framework/06_acquisition.md](../framework/06_acquisition.md) | 现行规范 |
| [framework/07_product_ecosystems.md](../framework/07_product_ecosystems.md) | 配套说明 |
| [framework/08_model_execution.md](../framework/08_model_execution.md) | 现行规范 |
| [framework/09_software_contracts.md](../framework/09_software_contracts.md) | 现行规范 |
| [framework/10_visual_atlas.md](../framework/10_visual_atlas.md) | 现行规范 |
| [framework/CURRENT.md](../framework/CURRENT.md) | 现行规范 |
| `framework/bom.json` | 项目配置 |
| `framework/current_state.json` | 项目配置 |
| `framework/dashboard_rules.json` | 项目配置 |
| `framework/data_contract.json` | 项目配置 |
| `framework/indicators.json` | 项目配置 |
| `framework/interface_manifest.json` | 项目配置 |
| `framework/material_retention.json` | 项目配置 |
| `framework/metrics.json` | 项目配置 |
| `framework/modules.json` | 项目配置 |
| [framework/modules/M01_市场规模与增长.md](../framework/modules/M01_市场规模与增长.md) | 配套说明 |
| [framework/modules/M02_供给格局.md](../framework/modules/M02_供给格局.md) | 配套说明 |
| [framework/modules/M03_需求格局.md](../framework/modules/M03_需求格局.md) | 配套说明 |
| [framework/modules/M04_电力与能源.md](../framework/modules/M04_电力与能源.md) | 配套说明 |
| [framework/modules/M05_土地与区域.md](../framework/modules/M05_土地与区域.md) | 配套说明 |
| [framework/modules/M06_芯片与服务器.md](../framework/modules/M06_芯片与服务器.md) | 配套说明 |
| [framework/modules/M07_网络与互联.md](../framework/modules/M07_网络与互联.md) | 配套说明 |
| [framework/modules/M08_散热与制冷.md](../framework/modules/M08_散热与制冷.md) | 配套说明 |
| [framework/modules/M09_电气设备供应链.md](../framework/modules/M09_电气设备供应链.md) | 配套说明 |
| [framework/modules/M10_建设运营与人才.md](../framework/modules/M10_建设运营与人才.md) | 配套说明 |
| [framework/modules/M11_资本与金融.md](../framework/modules/M11_资本与金融.md) | 配套说明 |
| [framework/modules/M12_需求侧经济学.md](../framework/modules/M12_需求侧经济学.md) | 配套说明 |
| [framework/modules/M13_有效算力与软件.md](../framework/modules/M13_有效算力与软件.md) | 配套说明 |
| [framework/modules/M14_中国板块.md](../framework/modules/M14_中国板块.md) | 配套说明 |
| [framework/modules/M15_情景与监测.md](../framework/modules/M15_情景与监测.md) | 配套说明 |
| `framework/part_fetch.json` | 项目配置 |
| `framework/repository_manifest.json` | 生成物 |
| `framework/research_graph.json` | 项目配置 |
| `framework/research_questions.json` | 项目配置 |
| `framework/site_rights.json` | 项目配置 |
| `framework/storage_contract.json` | 项目配置 |
| `framework/supply_contract.json` | 项目配置 |
| `framework/tco_factors.json` | 项目配置 |
| `framework/tco_targets.json` | 项目配置 |
| `framework/verification_contract.json` | 项目配置 |
| `framework/visual_atlas.json` | 项目配置 |
| `framework/visual_atlas_migration.json` | 项目配置 |
| `manage.py` | 运行代码 |
| `outputs/geluoke-research/2026-09-26/2026-09-26-article-summary-wechat.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-09-26/2026-09-26-article-summary.png` | 项目配置 |
| `outputs/geluoke-research/2026-09-26/2026-09-26-daily-wechat.html` | 运行代码 |
| `outputs/geluoke-research/2026-09-26/2026-09-26-fig1-jupiter-power-chain.png` | 项目配置 |
| `outputs/geluoke-research/2026-09-26/2026-09-26-fig2-us-power-cost.png` | 项目配置 |
| `outputs/geluoke-research/2026-09-26/2026-09-26-fig3-funding-stages.png` | 项目配置 |
| `outputs/geluoke-research/2026-09-26/2026-09-26-fig4-asia-conditions.png` | 项目配置 |
| `outputs/geluoke-research/2026-09-26/checks/render-desktop.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-09-26/checks/render-mobile390.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-09-26/checks/validation.json` | 项目配置 |
| `outputs/geluoke-research/2026-09-26/sources.json` | 项目配置 |
| `outputs/geluoke-research/2026-09-26/validation.json` | 项目配置 |
| `outputs/geluoke-research/2026-09-26/work/assemble.py` | 运行代码 |
| `outputs/geluoke-research/2026-09-26/work/build_all.sh` | 运行代码 |
| `outputs/geluoke-research/2026-09-26/work/build_html.py` | 运行代码 |
| `outputs/geluoke-research/2026-09-26/work/charts.py` | 运行代码 |
| `outputs/geluoke-research/2026-09-26/work/composite_qr.py` | 运行代码 |
| `outputs/geluoke-research/2026-09-26/work/content.json` | 项目配置 |
| `outputs/geluoke-research/2026-09-26/work/cover.html` | 运行代码 |
| `outputs/geluoke-research/2026-09-26/work/cover.json` | 项目配置 |
| `outputs/geluoke-research/2026-09-26/work/cover_template.html` | 运行代码 |
| `outputs/geluoke-research/2026-09-26/work/event_plan.json` | 项目配置 |
| `outputs/geluoke-research/2026-09-26/work/facts_all.json` | 项目配置 |
| `outputs/geluoke-research/2026-09-26/work/fig_asia.svg` | 项目配置 |
| `outputs/geluoke-research/2026-09-26/work/fig_funding.svg` | 项目配置 |
| `outputs/geluoke-research/2026-09-26/work/fig_jupiter.svg` | 项目配置 |
| `outputs/geluoke-research/2026-09-26/work/fig_us_power.svg` | 项目配置 |
| `outputs/geluoke-research/2026-09-26/work/fill_cover.py` | 运行代码 |
| `outputs/geluoke-research/2026-09-26/work/gen_xsec_A.py` | 运行代码 |
| `outputs/geluoke-research/2026-09-26/work/make_figs.py` | 运行代码 |
| `outputs/geluoke-research/2026-09-26/work/postedit.py` | 运行代码 |
| `outputs/geluoke-research/2026-09-26/work/render.py` | 运行代码 |
| `outputs/geluoke-research/2026-09-26/work/tojpeg.py` | 运行代码 |
| `outputs/geluoke-research/2026-09-26/work/validate.py` | 运行代码 |
| `outputs/geluoke-research/2026-09-26/work/wf_lead.js` | 运行代码 |
| `outputs/geluoke-research/2026-09-26/work/wf_verify_slice.js` | 运行代码 |
| `outputs/geluoke-research/2026-09-26/work/wf_write.js` | 运行代码 |
| `outputs/geluoke-research/2026-09-26/work/xsec_final.svg` | 项目配置 |
| [outputs/geluoke-research/2026-09-27-datacenter-profit/2026-09-27-article.md](../outputs/geluoke-research/2026-09-27-datacenter-profit/2026-09-27-article.md) | 配套说明 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/2026-09-27-cover-wechat.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/2026-09-27-cover.png` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/2026-09-27-datacenter-profit-full.html` | 运行代码 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/2026-09-27-datacenter-profit-lite.html` | 运行代码 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/2026-09-27-datacenter-profit-wechat.html` | 运行代码 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/2026-09-27-fig1-1gw-capex-by-chip.png` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/2026-09-27-fig2-three-paths-roic.png` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/2026-09-27-fig3-shell-lease-contracts.png` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/2026-09-27-fig4-capital-stack.png` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/2026-09-27-fig5-roic-sensitivity.png` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/2026-09-27-fig6-china-vs-us.png` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/2026-09-27-sources.json` | 项目配置 |
| [outputs/geluoke-research/2026-09-27-datacenter-profit/README.md](../outputs/geluoke-research/2026-09-27-datacenter-profit/README.md) | 配套说明 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/checks/render-desktop.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/checks/render-mobile390.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/checks/validation.json` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/article.json` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/canon.json` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/chapters.json` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/chapters_final.json` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/cover/cover.html` | 运行代码 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/cover/cover.json` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/cover/cover_long.html` | 运行代码 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/cover/fill_cover_long.py` | 运行代码 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/cover/ledger.json` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/cover/ledger_xsec.py` | 运行代码 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/cover/ledger_xsec.svg` | 项目配置 |
| [outputs/geluoke-research/2026-09-27-datacenter-profit/work/dropped_numbers.md](../outputs/geluoke-research/2026-09-27-datacenter-profit/work/dropped_numbers.md) | 配套说明 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/figmap.json` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/figs/fig1.svg` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/figs/fig2.svg` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/figs/fig3.svg` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/figs/fig4.svg` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/figs/fig5.svg` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/figs/fig6.svg` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/lead.json` | 项目配置 |
| [outputs/geluoke-research/2026-09-27-datacenter-profit/work/outline_v1.md](../outputs/geluoke-research/2026-09-27-datacenter-profit/work/outline_v1.md) | 配套说明 |
| [outputs/geluoke-research/2026-09-27-datacenter-profit/work/report_facts.md](../outputs/geluoke-research/2026-09-27-datacenter-profit/work/report_facts.md) | 配套说明 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/research/cards.json` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/tools/assemble_long.py` | 运行代码 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/tools/build_all_long.sh` | 运行代码 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/tools/build_long.py` | 运行代码 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/tools/charts.py` | 运行代码 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/tools/export_figs.py` | 运行代码 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/tools/figdata.json` | 项目配置 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/tools/make_cover_long.py` | 运行代码 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/tools/make_figs_long.py` | 运行代码 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/tools/render.py` | 运行代码 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/tools/tojpeg.py` | 运行代码 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/tools/validate.py` | 运行代码 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/tools/wf_condense.js` | 运行代码 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/tools/wf_lead_long.js` | 运行代码 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/tools/wf_research.js` | 运行代码 |
| `outputs/geluoke-research/2026-09-27-datacenter-profit/work/tools/wf_write_long.js` | 运行代码 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/README.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/README.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/article.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/article.md) | 配套说明 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/cover-list-2.35.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/cover-master.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/cover-master.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/cover-wechat.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/fig1-grid.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/fig1-grid.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/fig2-demand.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/fig2-demand.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/fig3-project.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/fig3-project.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/fig4-cost.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/fig4-cost.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/fig5-routes.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/fig5-routes.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/fig6-location.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/fig6-location.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/scene-bottleneck.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/scene-campus.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/scene-cooling.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/scene-cost-assets.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/scene-gas-labeled.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/scene-gas-pipeline.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/scene-nuclear-grid.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/scene-stages.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-01-interconnections-map.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-01-interconnections-map.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-02-roles.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-02-roles.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-03-demand.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-03-demand.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-04-bottlenecks.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-04-bottlenecks.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-05-regional-cases.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-05-regional-cases.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-06-project-evidence.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-06-project-evidence.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-07-planning-rules.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-07-planning-rules.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-08-cost-contracts.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-08-cost-contracts.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-09-customer-costs.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-09-customer-costs.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-10-nuclear-routes.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-10-nuclear-routes.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-11-onsite-sofc.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-11-onsite-sofc.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-12-annual-hourly.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-12-annual-hourly.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-13-state-prices-map.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-13-state-prices-map.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-14-flexible-load.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-14-flexible-load.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v3-sofc-base.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v4-01-interconnections-map.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v4-01-interconnections-map.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v4-02-demand.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v4-02-demand.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v4-03-bottlenecks.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v4-03-bottlenecks.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v4-04-project-evidence.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v4-04-project-evidence.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v4-05-cost-contracts.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v4-05-cost-contracts.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v4-06-nuclear-routes.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v4-06-nuclear-routes.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v4-07-onsite-sofc.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v4-07-onsite-sofc.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v4-08-annual-hourly.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v4-08-annual-hourly.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v4-09-state-prices-map.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v4-09-state-prices-map.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v4-10-flexible-load.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/assets/v4-10-flexible-load.svg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/calculations.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/cards.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/article-1000-full.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/article-1000-top.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/article-390-full.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/article-390-top.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/browser.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/build-title-20261009.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/build.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/cover-layout.json` | 项目配置 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/editorial-review.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/editorial-review.md) | 配套说明 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/eia-table-rows.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/figure9-title-1000-20261009.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/figure9-title-390-20261009.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/figure9-title-final-1000-20261009.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/figure9-title-final-390-20261009.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/figure9-title-html-20261009.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/figure9-title-html-final-20261009.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/figure9-title-render-20261009.json` | 项目配置 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/figure9-title-review-20261009.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/figure9-title-review-20261009.md) | 配套说明 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/figures-contact-title-20261009.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/figures-contact.jpg` | 项目配置 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/intake-review.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/intake-review.md) | 配套说明 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/intake-v4.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/mobile-chapter-1.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/mobile-chapter-2.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/mobile-chapter-3.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/mobile-chapter-4.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/mobile-chapter-5.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/mobile-chapter-6.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/mobile-figure-1.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/mobile-figure-10.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/mobile-figure-2.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/mobile-figure-3.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/mobile-figure-4.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/mobile-figure-5.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/mobile-figure-6.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/mobile-figure-7.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/mobile-figure-8.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/mobile-figure-9.png` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/repository-intake-20261009.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/repository.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/source-provenance-live-http-20261009.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/source-provenance-public-https-20261009.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/source-provenance-release-20261009.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/spark-intake-final-provenance-20261009.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/spark-intake-final-receipt-20261009.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/spark-intake-provenance-20261009.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/spark-intake-receipt-20261009.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/spark-parser-service-release-20261009.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/spark-reader-progress-20261009.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/spark-reader-progress-final-20261009.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/spark-source-provenance-runtime-20261009.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/spark-source-provenance-stage-20261009.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/svg-layout.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/v3-svg-layout.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/v4-svg-layout.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/checks/validation.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/full.html` | 运行代码 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/lite.html` | 运行代码 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/report_facts.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/report_facts.md) | 配套说明 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/research/claims.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/research/demand-snapshot.json` | 项目配置 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/intake-scope-review.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/intake-scope-review.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/aep-onsite.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/aep-onsite.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/alphabet-q1.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/alphabet-q1.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/crane-pdf.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/crane-pdf.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/doe-transformer.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/doe-transformer.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/doe-transmission.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/doe-transmission.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/eia-grid.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/eia-grid.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/eia-ytd.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/eia-ytd.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/ercot-batch.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/ercot-batch.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/ferc-june.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/ferc-june.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/ga-contract.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/ga-contract.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/gallup.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/gallup.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/google-flex.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/google-flex.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/iea.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/iea.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/intersect.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/intersect.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/jlarc.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/jlarc.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/lbnl-full.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/lbnl-full.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/nerc.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/nerc.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/ohio.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/ohio.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/pjm-forecast.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/pjm-forecast.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/pjm-large.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/pjm-large.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/pledge.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/pledge.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/scc.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/scc.md) | 配套说明 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/talen-sec.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/materials/talen-sec.md) | 配套说明 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/research/originals-manifest.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/research/research-gaps.json` | 项目配置 |
| [outputs/geluoke-research/2026-10-09-us-datacenter-power/research/research.md](../outputs/geluoke-research/2026-10-09-us-datacenter-power/research/research.md) | 配套说明 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/research/research.txt` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/research/sources.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/research/submission.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/sources.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/wechat.html` | 运行代码 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/gas-clean-prompt.txt` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/illustration-prompts.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/reference-previews/VR3.jpg` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/tools/acquire.py` | 运行代码 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/tools/audit.py` | 运行代码 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/tools/build.py` | 运行代码 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/tools/figures.py` | 运行代码 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/tools/figures_v3.py` | 运行代码 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/tools/prepare_scenes.py` | 运行代码 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/tools/render.cjs` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/tools/render_scene_labels.cjs` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/tools/render_v3.cjs` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/tools/render_v4.cjs` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/tools/research.py` | 运行代码 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/tools/revise_v3.py` | 运行代码 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/tools/validate.cjs` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/tools/visual_sources_v3.py` | 运行代码 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/v3/figure-plan.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/v3/illustration-prompt.txt` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/v3/map-geography.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/v3/visual-sources.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/v4/figure-plan.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/visual-references.json` | 项目配置 |
| `outputs/geluoke-research/2026-10-09-us-datacenter-power/work/writing-plan.json` | 项目配置 |
| [reports/HOW_TO_OUTPUT.md](../reports/HOW_TO_OUTPUT.md) | 生成物 |
| `reports/blindspot.json` | 生成物 |
| [reports/blindspot.md](../reports/blindspot.md) | 生成物 |
| [reports/daily_brief.md](../reports/daily_brief.md) | 生成物 |
| [reports/intake_review.md](../reports/intake_review.md) | 生成物 |
| [reports/reading_queue.md](../reports/reading_queue.md) | 生成物 |
| [reports/stale_paths.md](../reports/stale_paths.md) | 生成物 |
| [reports/templates/README.md](../reports/templates/README.md) | 生成物 |
| [reports/verify_queue.md](../reports/verify_queue.md) | 生成物 |
| `reports/workorders.json` | 生成物 |
| [reports/workorders.md](../reports/workorders.md) | 生成物 |
| [research/M01.md](../research/M01.md) | 兼容研究记录 |
| [research/M02.md](../research/M02.md) | 兼容研究记录 |
| [research/M03.md](../research/M03.md) | 兼容研究记录 |
| [research/M04.md](../research/M04.md) | 兼容研究记录 |
| [research/M05.md](../research/M05.md) | 兼容研究记录 |
| [research/M06.md](../research/M06.md) | 兼容研究记录 |
| [research/M07.md](../research/M07.md) | 兼容研究记录 |
| [research/M08.md](../research/M08.md) | 兼容研究记录 |
| [research/M09.md](../research/M09.md) | 兼容研究记录 |
| [research/M10.md](../research/M10.md) | 兼容研究记录 |
| [research/M11.md](../research/M11.md) | 兼容研究记录 |
| [research/M12.md](../research/M12.md) | 兼容研究记录 |
| [research/M13.md](../research/M13.md) | 兼容研究记录 |
| [research/M14.md](../research/M14.md) | 兼容研究记录 |
| [research/M15.md](../research/M15.md) | 兼容研究记录 |
| [research/SUMMARY.md](../research/SUMMARY.md) | 兼容研究记录 |
| `scripts/build_technical_atlas.py` | 运行代码 |
| `scripts/cards_ocr.py` | 运行代码 |
| `scripts/cards_verify.py` | 运行代码 |
| `scripts/daily_repository_pages.py` | 运行代码 |
| `scripts/editorial-outbox.py` | 运行代码 |
| `scripts/export_inews_research.cjs` | 项目配置 |
| `scripts/publish_repository_pages.py` | 运行代码 |
| `scripts/repository_checks.py` | 运行代码 |
| `scripts/repository_pages_daemon.py` | 运行代码 |
| `scripts/sync_repo_pages.py` | 运行代码 |
| [src/inresearch/README.md](../src/inresearch/README.md) | 配套说明 |
| `src/inresearch/__init__.py` | 运行代码 |
| `src/inresearch/__main__.py` | 运行代码 |
| `src/inresearch/adapters/__init__.py` | 运行代码 |
| `src/inresearch/adapters/acquisition.py` | 运行代码 |
| `src/inresearch/adapters/asset_check.py` | 运行代码 |
| `src/inresearch/adapters/asset_compare.py` | 运行代码 |
| `src/inresearch/adapters/asset_download.py` | 运行代码 |
| `src/inresearch/adapters/codex_inference.py` | 运行代码 |
| `src/inresearch/adapters/company_quotes.py` | 运行代码 |
| `src/inresearch/adapters/editorial_sync.py` | 运行代码 |
| `src/inresearch/adapters/fetchspec_projection.py` | 运行代码 |
| `src/inresearch/adapters/gap_ocr.py` | 运行代码 |
| `src/inresearch/adapters/historical_brief.py` | 运行代码 |
| `src/inresearch/adapters/html_document.py` | 运行代码 |
| `src/inresearch/adapters/models.py` | 运行代码 |
| `src/inresearch/adapters/news_projection.py` | 运行代码 |
| `src/inresearch/adapters/news_sync.py` | 运行代码 |
| `src/inresearch/adapters/ocr_worker.py` | 运行代码 |
| `src/inresearch/adapters/office.py` | 运行代码 |
| `src/inresearch/adapters/office_biff.py` | 运行代码 |
| `src/inresearch/adapters/office_container.py` | 运行代码 |
| `src/inresearch/adapters/office_grid.py` | 运行代码 |
| `src/inresearch/adapters/office_ooxml.py` | 运行代码 |
| `src/inresearch/adapters/office_ppt.py` | 运行代码 |
| `src/inresearch/adapters/pdf_text.py` | 运行代码 |
| `src/inresearch/adapters/reader_model.py` | 运行代码 |
| `src/inresearch/adapters/thermal.py` | 运行代码 |
| `src/inresearch/delivery/__init__.py` | 运行代码 |
| `src/inresearch/delivery/acquisition_status.py` | 运行代码 |
| `src/inresearch/delivery/backup.py` | 运行代码 |
| `src/inresearch/delivery/export.py` | 运行代码 |
| `src/inresearch/delivery/map.py` | 运行代码 |
| `src/inresearch/delivery/material_measurements.py` | 运行代码 |
| `src/inresearch/delivery/publish.py` | 运行代码 |
| `src/inresearch/delivery/publish_pilot_progress.py` | 运行代码 |
| `src/inresearch/delivery/reader_export.py` | 运行代码 |
| `src/inresearch/delivery/reader_progress.py` | 运行代码 |
| `src/inresearch/delivery/reader_status.py` | 运行代码 |
| `src/inresearch/delivery/reading_packet.py` | 运行代码 |
| `src/inresearch/delivery/report.py` | 运行代码 |
| `src/inresearch/delivery/snapshot_overlay.py` | 运行代码 |
| `src/inresearch/interfaces/__init__.py` | 运行代码 |
| `src/inresearch/interfaces/auth.py` | 运行代码 |
| `src/inresearch/interfaces/cli.py` | 运行代码 |
| `src/inresearch/interfaces/deep_read.py` | 运行代码 |
| `src/inresearch/interfaces/governance.py` | 运行代码 |
| `src/inresearch/interfaces/http.py` | 运行代码 |
| `src/inresearch/interfaces/material_flow.py` | 运行代码 |
| `src/inresearch/interfaces/pages.py` | 运行代码 |
| `src/inresearch/interfaces/public.py` | 运行代码 |
| `src/inresearch/interfaces/reader.py` | 运行代码 |
| `src/inresearch/interfaces/repository_pages.py` | 运行代码 |
| `src/inresearch/interfaces/static.py` | 运行代码 |
| `src/inresearch/interfaces/users.py` | 运行代码 |
| `src/inresearch/interfaces/verification.py` | 运行代码 |
| `src/inresearch/knowledge/__init__.py` | 运行代码 |
| `src/inresearch/knowledge/company_ids.py` | 运行代码 |
| `src/inresearch/knowledge/coverage.py` | 运行代码 |
| `src/inresearch/knowledge/dashboard.py` | 运行代码 |
| `src/inresearch/knowledge/deliveries.py` | 运行代码 |
| `src/inresearch/knowledge/economics.py` | 运行代码 |
| `src/inresearch/knowledge/fact_contract.py` | 运行代码 |
| `src/inresearch/knowledge/facts.py` | 运行代码 |
| `src/inresearch/knowledge/graph.py` | 运行代码 |
| `src/inresearch/knowledge/indicators.py` | 运行代码 |
| `src/inresearch/knowledge/industry.py` | 运行代码 |
| `src/inresearch/knowledge/material_baseline.py` | 运行代码 |
| `src/inresearch/knowledge/navigation.py` | 运行代码 |
| `src/inresearch/knowledge/news_observations.py` | 运行代码 |
| `src/inresearch/knowledge/news_policy.py` | 运行代码 |
| `src/inresearch/knowledge/nodes.py` | 运行代码 |
| `src/inresearch/knowledge/policy.py` | 运行代码 |
| `src/inresearch/knowledge/provenance.py` | 运行代码 |
| `src/inresearch/knowledge/registry.py` | 运行代码 |
| `src/inresearch/knowledge/targets.py` | 运行代码 |
| `src/inresearch/knowledge/validate.py` | 运行代码 |
| `src/inresearch/knowledge/verify.py` | 运行代码 |
| `src/inresearch/materials/__init__.py` | 运行代码 |
| `src/inresearch/materials/artifacts.py` | 运行代码 |
| `src/inresearch/materials/daily_bundle.py` | 运行代码 |
| `src/inresearch/materials/daily_events.py` | 运行代码 |
| `src/inresearch/materials/daily_research.py` | 运行代码 |
| `src/inresearch/materials/daily_sources.py` | 运行代码 |
| `src/inresearch/materials/fetchspec_receive.py` | 运行代码 |
| `src/inresearch/materials/inbox.py` | 运行代码 |
| `src/inresearch/materials/inventory.py` | 运行代码 |
| `src/inresearch/materials/library.py` | 运行代码 |
| `src/inresearch/materials/mapping.py` | 运行代码 |
| `src/inresearch/materials/model_assets.py` | 运行代码 |
| `src/inresearch/materials/naming.py` | 运行代码 |
| `src/inresearch/materials/organize.py` | 运行代码 |
| `src/inresearch/materials/paths.py` | 运行代码 |
| `src/inresearch/materials/preflight.py` | 运行代码 |
| `src/inresearch/materials/reader_contracts.py` | 运行代码 |
| `src/inresearch/materials/reading_artifacts.py` | 运行代码 |
| `src/inresearch/materials/reading_policy.py` | 运行代码 |
| `src/inresearch/materials/receive.py` | 运行代码 |
| `src/inresearch/materials/records.py` | 运行代码 |
| `src/inresearch/materials/retention.py` | 运行代码 |
| `src/inresearch/materials/source_provenance.py` | 运行代码 |
| `src/inresearch/materials/text_similarity.py` | 运行代码 |
| `src/inresearch/materials/triage.py` | 运行代码 |
| `src/inresearch/paths.py` | 运行代码 |
| `src/inresearch/storage/__init__.py` | 运行代码 |
| `src/inresearch/storage/catalog.py` | 运行代码 |
| `src/inresearch/storage/files.py` | 运行代码 |
| `src/inresearch/storage/jsonl.py` | 运行代码 |
| `src/inresearch/storage/layout.py` | 运行代码 |
| `src/inresearch/storage/moves.py` | 运行代码 |
| `src/inresearch/workflow/__init__.py` | 运行代码 |
| `src/inresearch/workflow/apply_triage.py` | 运行代码 |
| `src/inresearch/workflow/attribution.py` | 运行代码 |
| `src/inresearch/workflow/catalog_browse.py` | 运行代码 |
| `src/inresearch/workflow/catalog_bundle.py` | 运行代码 |
| `src/inresearch/workflow/catalog_materials.py` | 运行代码 |
| `src/inresearch/workflow/catalog_ownership.py` | 运行代码 |
| `src/inresearch/workflow/catalog_ownership_audit.py` | 运行代码 |
| `src/inresearch/workflow/commands.py` | 运行代码 |
| `src/inresearch/workflow/company_window.py` | 运行代码 |
| `src/inresearch/workflow/compute_catalog.py` | 运行代码 |
| `src/inresearch/workflow/daily_dispatch.py` | 运行代码 |
| `src/inresearch/workflow/deep_read.py` | 运行代码 |
| `src/inresearch/workflow/dispatch.py` | 运行代码 |
| `src/inresearch/workflow/l1_batch.py` | 运行代码 |
| `src/inresearch/workflow/model_assets.py` | 运行代码 |
| `src/inresearch/workflow/news_marks.py` | 运行代码 |
| `src/inresearch/workflow/operations.py` | 运行代码 |
| `src/inresearch/workflow/pilot_progress.py` | 运行代码 |
| `src/inresearch/workflow/product_catalog.py` | 运行代码 |
| `src/inresearch/workflow/product_coverage.py` | 运行代码 |
| `src/inresearch/workflow/product_navigation.py` | 运行代码 |
| `src/inresearch/workflow/progress.py` | 运行代码 |
| `src/inresearch/workflow/project_pipeline.py` | 运行代码 |
| `src/inresearch/workflow/project_review.py` | 运行代码 |
| `src/inresearch/workflow/reader.py` | 运行代码 |
| `src/inresearch/workflow/reader_scope.py` | 运行代码 |
| `src/inresearch/workflow/reading_gaps.py` | 运行代码 |
| `src/inresearch/workflow/reading_queue.py` | 运行代码 |
| `src/inresearch/workflow/reading_results.py` | 运行代码 |
| `src/inresearch/workflow/reading_revisions.py` | 运行代码 |
| `src/inresearch/workflow/reading_stages.py` | 运行代码 |
| `src/inresearch/workflow/research_match.py` | 运行代码 |
| `src/inresearch/workflow/research_publish.py` | 运行代码 |
| `src/inresearch/workflow/research_review.py` | 运行代码 |
| `src/inresearch/workflow/research_sources.py` | 运行代码 |
| `src/inresearch/workflow/review_preference.py` | 运行代码 |
| `src/inresearch/workflow/score.py` | 运行代码 |
| `src/inresearch/workflow/submissions.py` | 运行代码 |
| `src/inresearch/workflow/supply.py` | 运行代码 |
| `src/inresearch/workflow/terminal_batch.py` | 运行代码 |
| `src/inresearch/workflow/triage.py` | 运行代码 |
| `src/inresearch/workflow/workorders.py` | 运行代码 |
| `tests/auth_appearance.cjs` | 测试 |
| `tests/browser_suites.cjs` | 测试 |
| `tests/catalog_materials.cjs` | 测试 |
| `tests/company_catalog_map.cjs` | 测试 |
| `tests/company_page.cjs` | 测试 |
| `tests/company_window.cjs` | 测试 |
| `tests/compute_catalog.cjs` | 测试 |
| `tests/container_storage.py` | 测试 |
| `tests/dashboard.cjs` | 测试 |
| `tests/datacenter_cost.cjs` | 测试 |
| `tests/datacenter_economics.cjs` | 测试 |
| `tests/datacenter_news.cjs` | 测试 |
| `tests/datacenter_tco.cjs` | 测试 |
| `tests/industry.cjs` | 测试 |
| `tests/model_assets.cjs` | 测试 |
| `tests/nvidia_pilot.cjs` | 测试 |
| `tests/ops_dashboard.cjs` | 测试 |
| `tests/part_dossier.cjs` | 测试 |
| `tests/product_catalog.cjs` | 测试 |
| `tests/repository_pages.cjs` | 测试 |
| `tests/research_delivery.cjs` | 测试 |
| `tests/research_summary.cjs` | 测试 |
| `tests/run_browser.cjs` | 测试 |
| `tests/scene_atlas.cjs` | 测试 |
| `tests/scene_bootstrap.cjs` | 测试 |
| `tests/scene_framing.cjs` | 测试 |
| `tests/scene_resources.cjs` | 测试 |
| `tests/server_assembly.cjs` | 测试 |
| `tests/server_plan.cjs` | 测试 |
| `tests/supply.cjs` | 测试 |
| `tests/technical_atlas.cjs` | 测试 |
| `tests/ui_skin.cjs` | 测试 |
| `tests/unit/deep_read_fixtures.py` | 测试 |
| `tests/unit/test_acquisition.py` | 测试 |
| `tests/unit/test_apply_triage.py` | 测试 |
| `tests/unit/test_auth.py` | 测试 |
| `tests/unit/test_bom.py` | 测试 |
| `tests/unit/test_browser_shards.py` | 测试 |
| `tests/unit/test_catalog_bridge.py` | 测试 |
| `tests/unit/test_catalog_browse.py` | 测试 |
| `tests/unit/test_catalog_migration.py` | 测试 |
| `tests/unit/test_catalog_ownership.py` | 测试 |
| `tests/unit/test_catalog_supplement.py` | 测试 |
| `tests/unit/test_claim_floor.py` | 测试 |
| `tests/unit/test_codex_batch_reader.py` | 测试 |
| `tests/unit/test_codex_failure_ocr_rescue.py` | 测试 |
| `tests/unit/test_commands.py` | 测试 |
| `tests/unit/test_company_window.py` | 测试 |
| `tests/unit/test_compute_catalog.py` | 测试 |
| `tests/unit/test_continuous_reader.py` | 测试 |
| `tests/unit/test_daily_bundle.py` | 测试 |
| `tests/unit/test_daily_dispatch.py` | 测试 |
| `tests/unit/test_dashboard.py` | 测试 |
| `tests/unit/test_datacenter_news.py` | 测试 |
| `tests/unit/test_declared_admin.py` | 测试 |
| `tests/unit/test_deep_read.py` | 测试 |
| `tests/unit/test_deep_read_transactions.py` | 测试 |
| `tests/unit/test_deliveries.py` | 测试 |
| `tests/unit/test_display_regressions.py` | 测试 |
| `tests/unit/test_dropped_claims.py` | 测试 |
| `tests/unit/test_editorial_sync.py` | 测试 |
| `tests/unit/test_export_fold.py` | 测试 |
| `tests/unit/test_fact_contract.py` | 测试 |
| `tests/unit/test_fetchspec_backflow.py` | 测试 |
| `tests/unit/test_fetchspec_receive.py` | 测试 |
| `tests/unit/test_file_moves.py` | 测试 |
| `tests/unit/test_gap_ocr.py` | 测试 |
| `tests/unit/test_governance.py` | 测试 |
| `tests/unit/test_graph.py` | 测试 |
| `tests/unit/test_html_document.py` | 测试 |
| `tests/unit/test_http_workflow.py` | 测试 |
| `tests/unit/test_industry.py` | 测试 |
| `tests/unit/test_intake.py` | 测试 |
| `tests/unit/test_interface_system.py` | 测试 |
| `tests/unit/test_m4_ocr_gaps.py` | 测试 |
| `tests/unit/test_m4_office_text.py` | 测试 |
| `tests/unit/test_m4_offload_requeue.py` | 测试 |
| `tests/unit/test_m4_paths.py` | 测试 |
| `tests/unit/test_m4_redo_reads.py` | 测试 |
| `tests/unit/test_m4_triage.py` | 测试 |
| `tests/unit/test_m4_triage_apply.py` | 测试 |
| `tests/unit/test_m4_triage_export.py` | 测试 |
| `tests/unit/test_m4_triage_extract.py` | 测试 |
| `tests/unit/test_m4_triage_local.py` | 测试 |
| `tests/unit/test_m4_triage_report.py` | 测试 |
| `tests/unit/test_m4_triage_versions.py` | 测试 |
| `tests/unit/test_material_baseline.py` | 测试 |
| `tests/unit/test_material_flow.py` | 测试 |
| `tests/unit/test_material_intake.py` | 测试 |
| `tests/unit/test_material_retention.py` | 测试 |
| `tests/unit/test_model.py` | 测试 |
| `tests/unit/test_model_assets.py` | 测试 |
| `tests/unit/test_model_roles.py` | 测试 |
| `tests/unit/test_model_runtime.py` | 测试 |
| `tests/unit/test_news_feedback.py` | 测试 |
| `tests/unit/test_news_incremental.py` | 测试 |
| `tests/unit/test_news_marks.py` | 测试 |
| `tests/unit/test_news_projection.py` | 测试 |
| `tests/unit/test_news_targets.py` | 测试 |
| `tests/unit/test_nodes.py` | 测试 |
| `tests/unit/test_ocr_repeat_penalty.py` | 测试 |
| `tests/unit/test_ocr_worker_named.py` | 测试 |
| `tests/unit/test_ocr_worker_resume.py` | 测试 |
| `tests/unit/test_ollama_schema.py` | 测试 |
| `tests/unit/test_operations.py` | 测试 |
| `tests/unit/test_optional_mapping_ids.py` | 测试 |
| `tests/unit/test_pdf_native_text.py` | 测试 |
| `tests/unit/test_pilot_progress.py` | 测试 |
| `tests/unit/test_placeholder_output.py` | 测试 |
| `tests/unit/test_product_catalog.py` | 测试 |
| `tests/unit/test_product_catalog_companies.py` | 测试 |
| `tests/unit/test_product_coverage.py` | 测试 |
| `tests/unit/test_product_library.py` | 测试 |
| `tests/unit/test_project_review.py` | 测试 |
| `tests/unit/test_public_reader.py` | 测试 |
| `tests/unit/test_publish_reader.py` | 测试 |
| `tests/unit/test_read_batch.py` | 测试 |
| `tests/unit/test_reader_claim_scope.py` | 测试 |
| `tests/unit/test_reader_demands.py` | 测试 |
| `tests/unit/test_reader_depth.py` | 测试 |
| `tests/unit/test_reader_progress.py` | 测试 |
| `tests/unit/test_reader_scope_capacity.py` | 测试 |
| `tests/unit/test_reader_thermal.py` | 测试 |
| `tests/unit/test_reading_results.py` | 测试 |
| `tests/unit/test_reading_revisions.py` | 测试 |
| `tests/unit/test_record_validates.py` | 测试 |
| `tests/unit/test_report_model.py` | 测试 |
| `tests/unit/test_repository_checks.py` | 测试 |
| `tests/unit/test_repository_pages.py` | 测试 |
| `tests/unit/test_repository_projection.py` | 测试 |
| `tests/unit/test_research.py` | 测试 |
| `tests/unit/test_research_flow_recovery.py` | 测试 |
| `tests/unit/test_research_match.py` | 测试 |
| `tests/unit/test_research_navigation.py` | 测试 |
| `tests/unit/test_research_progress.py` | 测试 |
| `tests/unit/test_research_publication_merge.py` | 测试 |
| `tests/unit/test_research_review.py` | 测试 |
| `tests/unit/test_research_sources.py` | 测试 |
| `tests/unit/test_result_versions.py` | 测试 |
| `tests/unit/test_review_preference.py` | 测试 |
| `tests/unit/test_snapshot_overlay.py` | 测试 |
| `tests/unit/test_storage_layout.py` | 测试 |
| `tests/unit/test_suite_integrity.py` | 测试 |
| `tests/unit/test_supply.py` | 测试 |
| `tests/unit/test_target_dispatch.py` | 测试 |
| `tests/unit/test_tco_factors.py` | 测试 |
| `tests/unit/test_tco_targets.py` | 测试 |
| `tests/unit/test_text_similarity.py` | 测试 |
| `tests/unit/test_transient_model_errors.py` | 测试 |
| `tests/unit/test_verification_contract.py` | 测试 |
| `tests/unit/test_visual_atlas.py` | 测试 |
| `tests/url_rendering.cjs` | 测试 |
| `web/assets/datacenter-news.css` | 运行代码 |
| `web/assets/fonts/LICENSE-Inter.txt` | 静态资源 |
| `web/assets/fonts/LICENSE-NotoSansSC.txt` | 静态资源 |
| `web/assets/fonts/fonts.css` | 运行代码 |
| `web/assets/fonts/inter-variable-italic.woff2` | 静态资源 |
| `web/assets/fonts/inter-variable.woff2` | 静态资源 |
| `web/assets/fonts/manifest.json` | 静态资源 |
| `web/assets/fonts/noto-sans-sc-1.woff2` | 静态资源 |
| `web/assets/fonts/noto-sans-sc-10.woff2` | 静态资源 |
| `web/assets/fonts/noto-sans-sc-2.woff2` | 静态资源 |
| `web/assets/fonts/noto-sans-sc-3.woff2` | 静态资源 |
| `web/assets/fonts/noto-sans-sc-4.woff2` | 静态资源 |
| `web/assets/fonts/noto-sans-sc-5.woff2` | 静态资源 |
| `web/assets/fonts/noto-sans-sc-6.woff2` | 静态资源 |
| `web/assets/fonts/noto-sans-sc-7.woff2` | 静态资源 |
| `web/assets/fonts/noto-sans-sc-8.woff2` | 静态资源 |
| `web/assets/fonts/noto-sans-sc-9.woff2` | 静态资源 |
| [web/assets/hdri/README.md](../web/assets/hdri/README.md) | 配套说明 |
| `web/assets/hdri/lab.exr` | 静态资源 |
| `web/assets/hdri/studio.exr` | 静态资源 |
| `web/assets/hdri/warehouse.exr` | 静态资源 |
| `web/assets/material-flow.css` | 运行代码 |
| `web/assets/material-flow.js` | 运行代码 |
| `web/assets/materials.js` | 运行代码 |
| [web/assets/models/README.md](../web/assets/models/README.md) | 配套说明 |
| `web/assets/models/manifest.json` | 静态资源 |
| `web/assets/models/server_v2_console.glb` | 静态资源 |
| `web/assets/ops-dashboard.css` | 运行代码 |
| `web/assets/ops-dashboard.js` | 运行代码 |
| `web/assets/ops-forms.js` | 运行代码 |
| [web/assets/panels/README.md](../web/assets/panels/README.md) | 配套说明 |
| `web/assets/panels/server_gpu.png` | 静态资源 |
| `web/assets/panels/server_nvme.png` | 静态资源 |
| `web/assets/panels/server_storage.png` | 静态资源 |
| `web/assets/panels/switch_ib.png` | 静态资源 |
| `web/assets/panels/switch_tor.png` | 静态资源 |
| [web/assets/renders/README.md](../web/assets/renders/README.md) | 配套说明 |
| `web/assets/renders/chassis.png` | 静态资源 |
| `web/assets/renders/coldplate.png` | 静态资源 |
| `web/assets/renders/fans.png` | 静态资源 |
| `web/assets/renders/gpu-board.png` | 静态资源 |
| `web/assets/renders/hbm.png` | 静态资源 |
| `web/assets/renders/mobo.png` | 静态资源 |
| `web/assets/renders/nic.png` | 静态资源 |
| `web/assets/renders/psu.png` | 静态资源 |
| `web/assets/renders/ssd.png` | 静态资源 |
| `web/assets/repository-status.js` | 运行代码 |
| `web/assets/research.css` | 运行代码 |
| [web/assets/technical-atlas/README.md](../web/assets/technical-atlas/README.md) | 配套说明 |
| `web/assets/technical-atlas/chassis-v1-preview.jpg` | 静态资源 |
| `web/assets/technical-atlas/chassis-v1-preview.svg` | 静态资源 |
| `web/assets/technical-atlas/chassis-v1.png` | 静态资源 |
| `web/assets/technical-atlas/chassis-v1.svg` | 静态资源 |
| `web/assets/technical-atlas/coldplate-v1-preview.jpg` | 静态资源 |
| `web/assets/technical-atlas/coldplate-v1-preview.svg` | 静态资源 |
| `web/assets/technical-atlas/coldplate-v1.png` | 静态资源 |
| `web/assets/technical-atlas/coldplate-v1.svg` | 静态资源 |
| `web/assets/technical-atlas/fan-wall-v1-preview.jpg` | 静态资源 |
| `web/assets/technical-atlas/fan-wall-v1-preview.svg` | 静态资源 |
| `web/assets/technical-atlas/fan-wall-v1.png` | 静态资源 |
| `web/assets/technical-atlas/fan-wall-v1.svg` | 静态资源 |
| `web/assets/technical-atlas/fire-v1-preview.jpg` | 静态资源 |
| `web/assets/technical-atlas/fire-v1-preview.svg` | 静态资源 |
| `web/assets/technical-atlas/fire-v1.png` | 静态资源 |
| `web/assets/technical-atlas/fire-v1.svg` | 静态资源 |
| `web/assets/technical-atlas/gpu-board-v1-preview.jpg` | 静态资源 |
| `web/assets/technical-atlas/gpu-board-v1-preview.svg` | 静态资源 |
| `web/assets/technical-atlas/gpu-board-v1.png` | 静态资源 |
| `web/assets/technical-atlas/gpu-board-v1.svg` | 静态资源 |
| `web/assets/technical-atlas/hbm-package-v1-preview.jpg` | 静态资源 |
| `web/assets/technical-atlas/hbm-package-v1-preview.svg` | 静态资源 |
| `web/assets/technical-atlas/hbm-package-v1.png` | 静态资源 |
| `web/assets/technical-atlas/hbm-package-v1.svg` | 静态资源 |
| `web/assets/technical-atlas/motherboard-v1-preview.jpg` | 静态资源 |
| `web/assets/technical-atlas/motherboard-v1-preview.svg` | 静态资源 |
| `web/assets/technical-atlas/motherboard-v1.png` | 静态资源 |
| `web/assets/technical-atlas/motherboard-v1.svg` | 静态资源 |
| `web/assets/technical-atlas/nic-v1-preview.jpg` | 静态资源 |
| `web/assets/technical-atlas/nic-v1-preview.svg` | 静态资源 |
| `web/assets/technical-atlas/nic-v1.png` | 静态资源 |
| `web/assets/technical-atlas/nic-v1.svg` | 静态资源 |
| `web/assets/technical-atlas/psu-v1-preview.jpg` | 静态资源 |
| `web/assets/technical-atlas/psu-v1-preview.svg` | 静态资源 |
| `web/assets/technical-atlas/psu-v1.png` | 静态资源 |
| `web/assets/technical-atlas/psu-v1.svg` | 静态资源 |
| `web/assets/technical-atlas/rack-frame-v1-preview.jpg` | 静态资源 |
| `web/assets/technical-atlas/rack-frame-v1-preview.svg` | 静态资源 |
| `web/assets/technical-atlas/rack-frame-v1.png` | 静态资源 |
| `web/assets/technical-atlas/rack-frame-v1.svg` | 静态资源 |
| `web/assets/technical-atlas/security-v1-preview.jpg` | 静态资源 |
| `web/assets/technical-atlas/security-v1-preview.svg` | 静态资源 |
| `web/assets/technical-atlas/security-v1.png` | 静态资源 |
| `web/assets/technical-atlas/security-v1.svg` | 静态资源 |
| `web/assets/technical-atlas/server-plan-v1-preview.svg` | 静态资源 |
| `web/assets/technical-atlas/server-plan-v1.png` | 静态资源 |
| `web/assets/technical-atlas/server-plan-v1.svg` | 静态资源 |
| `web/assets/technical-atlas/server-v1-preview.jpg` | 静态资源 |
| `web/assets/technical-atlas/server-v1-preview.svg` | 静态资源 |
| `web/assets/technical-atlas/server-v1.png` | 静态资源 |
| `web/assets/technical-atlas/server-v1.svg` | 静态资源 |
| `web/assets/technical-atlas/shell-v1-preview.jpg` | 静态资源 |
| `web/assets/technical-atlas/shell-v1-preview.svg` | 静态资源 |
| `web/assets/technical-atlas/shell-v1.png` | 静态资源 |
| `web/assets/technical-atlas/shell-v1.svg` | 静态资源 |
| `web/assets/technical-atlas/ssd-v1-preview.jpg` | 静态资源 |
| `web/assets/technical-atlas/ssd-v1-preview.svg` | 静态资源 |
| `web/assets/technical-atlas/ssd-v1.png` | 静态资源 |
| `web/assets/technical-atlas/ssd-v1.svg` | 静态资源 |
| `web/assets/vendor/BufferGeometryUtils.js` | 静态资源 |
| `web/assets/vendor/CopyShader.js` | 静态资源 |
| `web/assets/vendor/EXRLoader.js` | 静态资源 |
| `web/assets/vendor/EffectComposer.js` | 静态资源 |
| `web/assets/vendor/GLTFLoader.js` | 静态资源 |
| `web/assets/vendor/LuminosityHighPassShader.js` | 静态资源 |
| `web/assets/vendor/MaskPass.js` | 静态资源 |
| `web/assets/vendor/OrbitControls.js` | 静态资源 |
| `web/assets/vendor/OutputPass.js` | 静态资源 |
| `web/assets/vendor/OutputShader.js` | 静态资源 |
| `web/assets/vendor/Pass.js` | 静态资源 |
| `web/assets/vendor/RenderPass.js` | 静态资源 |
| `web/assets/vendor/ShaderPass.js` | 静态资源 |
| `web/assets/vendor/UnrealBloomPass.js` | 静态资源 |
| `web/assets/vendor/fflate.module.js` | 静态资源 |
| `web/assets/vendor/three.module.js` | 静态资源 |
| `web/assets/world.geo.json` | 静态资源 |
| `web/components/auth-form.js` | 运行代码 |
| `web/components/auth.css` | 运行代码 |
| `web/components/catalog-admin.js` | 运行代码 |
| `web/components/catalog-materials.js` | 运行代码 |
| `web/components/company-browser.js` | 运行代码 |
| `web/components/company-context.js` | 运行代码 |
| `web/components/company-home.js` | 运行代码 |
| `web/components/company-overview.js` | 运行代码 |
| `web/components/compute-catalog.js` | 运行代码 |
| `web/components/datacenter-model.js` | 运行代码 |
| `web/components/datacenter-news.js` | 运行代码 |
| `web/components/industry.js` | 运行代码 |
| `web/components/markdown-inline.js` | 运行代码 |
| `web/components/model-assets.js` | 运行代码 |
| `web/components/object-network.js` | 运行代码 |
| `web/components/part-dossier.js` | 运行代码 |
| `web/components/part-inspector.js` | 运行代码 |
| `web/components/pilot.js` | 运行代码 |
| `web/components/product-catalog.js` | 运行代码 |
| `web/components/research-graph.js` | 运行代码 |
| `web/components/scene-atlas.js` | 运行代码 |
| `web/components/scene-data.js` | 运行代码 |
| `web/components/scene-motion.js` | 运行代码 |
| `web/components/scene-picking.js` | 运行代码 |
| `web/components/scene-resources.js` | 运行代码 |
| `web/components/scene-view.js` | 运行代码 |
| `web/components/series-summary.js` | 运行代码 |
| `web/components/server-assembly.js` | 运行代码 |
| `web/components/server-plan-generator.js` | 运行代码 |
| `web/components/site-shell.js` | 运行代码 |
| `web/components/supply.js` | 运行代码 |
| `web/components/targets.js` | 运行代码 |
| `web/components/tasks-board.js` | 运行代码 |
| `web/components/technical-atlas.css` | 运行代码 |
| `web/components/technical-atlas.js` | 运行代码 |
| `web/pages/admin/agentrepo.html` | 运行代码 |
| `web/pages/admin/aimailrepo.html` | 运行代码 |
| `web/pages/admin/company.html` | 运行代码 |
| `web/pages/admin/fetchspec/reporg.html` | 运行代码 |
| `web/pages/admin/fetchspecrepo.html` | 运行代码 |
| `web/pages/admin/glocalstoragerepo.html` | 运行代码 |
| `web/pages/admin/inewsrepo.html` | 运行代码 |
| `web/pages/admin/infrarepo.html` | 运行代码 |
| `web/pages/admin/inresearchrepo.html` | 运行代码 |
| `web/pages/admin/leadsgenrepo.html` | 运行代码 |
| `web/pages/admin/oarepo.html` | 运行代码 |
| `web/pages/admin/openapirepo.html` | 运行代码 |
| `web/pages/admin/product/index.html` | 运行代码 |
| `web/pages/admin/repo-content/checks.json` | 项目配置 |
| `web/pages/admin/repo-content/fetchspec.html` | 运行代码 |
| `web/pages/admin/repo-content/infra-daily.json` | 项目配置 |
| `web/pages/admin/repo-content/infra.html` | 运行代码 |
| `web/pages/admin/repo-content/manifest.json` | 项目配置 |
| `web/pages/admin/repos.html` | 运行代码 |
| `web/pages/admin/semiflyrepo.html` | 运行代码 |
| `web/pages/auth/forbidden.html` | 运行代码 |
| `web/pages/auth/layout.html` | 运行代码 |
| `web/pages/auth/login.html` | 运行代码 |
| `web/pages/auth/password.html` | 运行代码 |
| `web/pages/bom.html` | 运行代码 |
| `web/pages/bom3d.html` | 运行代码 |
| `web/pages/company-home.html` | 运行代码 |
| `web/pages/company-products.html` | 运行代码 |
| `web/pages/company.html` | 运行代码 |
| `web/pages/compare.html` | 运行代码 |
| `web/pages/compute-catalog.html` | 运行代码 |
| `web/pages/doc.html` | 运行代码 |
| `web/pages/index.html` | 运行代码 |
| `web/pages/ledger.html` | 运行代码 |
| `web/pages/node.html` | 运行代码 |
| `web/pages/ops.html` | 运行代码 |
| `web/pages/product-catalog.html` | 运行代码 |
| `web/pages/rack3d.html` | 运行代码 |
| `web/pages/report.html` | 运行代码 |
| `web/pages/server-plan.html` | 运行代码 |
| `web/pages/supply.html` | 运行代码 |
| `web/robots.txt` | 项目配置 |
| `web/routes.json` | 项目配置 |
| `web/themes/company-browser.css` | 运行代码 |
| `web/themes/company-home.css` | 运行代码 |
| `web/themes/company.css` | 运行代码 |
| `web/themes/industry.css` | 运行代码 |
| `web/themes/preference.js` | 运行代码 |
| `web/themes/site-skin.css` | 运行代码 |
| `web/themes/supply.css` | 运行代码 |
