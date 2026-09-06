# 知识记录与 Finding 兼容格式 v2

> CURRENT · 2026-09-06。现行入口：[CURRENT](CURRENT.md)。规范源由 `current_state.json` 指定。

## 共同底座

研究对象与关系在 `research_graph.json`，问题与验收在 `research_questions.json`，正式文档、证据、陈述和回答在 `data/research_knowledge.json`。Spark 运行快照仅是候选；产品目录、资料计划及历史来源索引另行登记。

每条证据有稳定身份、文档版本与原文定位；每个陈述指向支持/反证，回答指向问题和证据。范围、时间、配置与来源的变化触发复核。旧版结论和原件保留，使用 superseded / needs-review 等状态及新旧引用，不靠覆盖原文抹掉历史。

## 兼容模块研究文档

`research/Mxx.md` 保留既有 Finding ID 与报告导出，承担兼容研究分工，不是独占的知识底座。M01–M15 均可按 ID、版本、范围与依赖引用其他模块。

```markdown
# M08 散热与制冷 — 研究文档

## M08-F1 结论标题 {Q26}
- **状态**：needs-review ｜ **修订**：2026-09-06 ｜ **触发器**：periodic:180d
- **结论**：有适用条件的结论。
- **论证**：
  - 说明支持与反证。
- **证据**：
  - [S2/company] 具体出处与版本 — https://example.com/source
- **口径提醒**：时间、范围、配置与不确定性。
- **待办**：需要补证或复核的内容。
```

Finding ID `Mxx-Fn` 永不复用；`{Qnn}` 追溯旧报告问题，新增使用 `{new}`。状态为 current、needs-review、stale、superseded。更新结论须保留前版或对应提交及替代关系；仅完成复核可更新核验日期，不伪造实质修订。示例是格式示意，不能进入证据库。

`verify.py` 生成复核任务；`export.py` 对 needs-review/stale 强制提示，对 superseded 不当作当前正文。现有解析器及旧记录不自动具备新证据链；迁移须逐条核对，150 条既有 Finding 不能据数量直接算作已采用的对象证据。

## 变更顺序

来源或范围变化 → 标受影响记录待复核 → 回到原文与反证 → 通过口径与 C3 → 建立新版本及替代链 → 更新当前回答与下游交付。较新的文件时间或模型结论本身不是采用授权。研究记录的修订与规范的修订分别遵循 [当前基准](CURRENT.md)。
