# 产品资料工具 — 兼容目录的核对

现行映射与身份规则见 [对象与产品规范](../../framework/03_bom_and_collaboration.md)，数据状态见 [口径手册](../../framework/01_data_standards.md)。产品线目录不是具体型号或现场资产；资料计划和历史索引不代表当前已下载、已读或采用。

已有 `src/inresearch/materials/library.py` 的 plan/fetch/adopt/status 保留给登记产品库使用。先运行 `python3 manage.py library --help` 和 `status --verify` 核对实际参数与文件；只有明确存在的库或外置卷才能作为目标。文档中的历史 Mac mini 路径不证明文件目前存在，不调用旧 setup.sh 搬工作区。

新的批量研究原件通过 Spark 的 raw-materials 入口与永久台账处理，见 [Spark 手册](../local_reader/SPARK_OPERATIONS.md)。旧库、归档索引与新文档须按来源、内容哈希和版本建立关联，不凭文件名继承“已读/已核验”。

原来的两机分工及固定外置卷设计已归档于 `docs/archive/2026-09-06/docs__local_setup__PRODUCT_LIBRARY.md`。
