# 已验收的技术图册资产

画法唯一源：`framework/10_visual_atlas.md`；逐张队列：`framework/visual_atlas_migration.json`。

## TA-01 · SSD 结构样板 v1

- `ssd-v1.png`：内置 image_gen 生成的原始无字母图，1536×1024，未裁剪或插值。
- `ssd-v1-preview.jpg` / `ssd-v1-preview.svg`：同尺寸的JPEG编码和可编辑标注组成轻量预览；不改变构图、不插值。仅档案缩略图使用，高清母图与下载保持原件。
- `ssd-v1.svg`：在原始PNG字节上叠加独立文字与引线；PNG内嵌，下载后无需相邻文件，可离线查看和编辑文字。
- 标注源：`docs/design/technical-atlas/TA-01/labels-v1.json`。构建：`python3 scripts/build_technical_atlas.py docs/design/technical-atlas/TA-01/labels-v1.json`。
- 参考、提示词、技术依据、SHA、未知项与内容/视觉/页面验收：`docs/design/technical-atlas/TA-01/acceptance-v1.json`。
- 展示入口：已有 `bom.html#ssd`、`bom3d.html?p=ssd`、`rack3d.html?x=55&node=part:ssd#ssd` 的部件档案。真实生产发布按逐项回执确认。

这是通用有壳SSD类别结构示意，非具名型号、真实拆机照片或针脚/尺寸工程图。生成插图不冒称CC0或原厂授权。旧 `web/assets/renders/ssd.png`（机箱/抽盘示意）原样留存，不复活退役海报页；当前3D模型并未由此图取代。
