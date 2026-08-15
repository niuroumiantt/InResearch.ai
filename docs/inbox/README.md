# 收件箱 — 材料统一投递口

**有任何材料就放这里**：Word、PDF、CAD（dwg/dxf）、Excel、PPT、图片……不用改名、不用分类。

之后的处理流程（您不用做）：
1. 后台"扫描收件箱"按钮 / 每日流水线会列出新到材料；
2. 由 Claude 按内容归类：第三方报告 → `docs/library/<分类>/`（统一重命名 `年份_主题_机构`）；
   自产文档 → `docs/source/`；工程图纸 → `docs/library/06_工程图纸/`；
   含数据的表格 → 提取入六张表后原件归档；
3. 归档后登记进 `docs/LIBRARY_INDEX.md` 与 `data/sources.json`，收件箱清空。

二进制不进 git（本索引与 README 进）。
