# 路径迁移表（目录重组，2026-08-18）

按 `RUN_TO_COMPLETION` 第八节把 `docs/library/` 重建为 M01–M15 结构后产出。

## migration_YYYYMMDD_NN.csv
两列 `old_path,new_path`，**全库 28,751 份逐条列出**。云端据此批量更新
`LIBRARY_SCORES.csv` 与 `data/sources.json` 的路径（单一写入方不变）。

**匹配方式**：按 `old_path` 精确匹配 CSV 的 `new_path` 列。

## cache_key_remap_YYYYMMDD.json
`cache_key → {pre_path, new_path, new_key}`。

**为什么需要它**：第八节假设"提取缓存以内容哈希为键、不受搬家影响"，
但 `pipeline/extract.py` 的 `key()` 实际用的是 **绝对路径 + 文件大小** 的 sha1，
**是路径相关的**。搬家后旧 `cache_key` 与新路径失去关联，
而 `facts_candidates/*.json` 的 `source_key` 正是这个旧键。

本表把旧键接回新路径，保证已交付事实候选的证据链不断。
`new_key` 是按新路径重算的键——若将来重跑 extract.py，新键即为其缓存文件名。

## 已知残留
迁移只搬**磁盘上实际存在**的文件。合并前 `LIBRARY_SCORES.csv` 中有 **629 行**
的 `new_path` 指向已不存在的文件（隔离件、改判后改名的旧行、已删压缩包），
这些行不会出现在 migration CSV 里，合并后仍指向失效路径，**需云端单独清理**。
