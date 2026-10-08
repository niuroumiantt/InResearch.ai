# 白底技术图册标准与逐图计划交接（2026-10-08，m5）

## 目标
采用用户提供五张技术图为今后标准，按已登记顺序逐项更新。用户已进一步授权“一个一个更新，开始更新”，无需每项重复询问是否开始。

## 已定规则（不再重复确认）
- 用户已采用“白底技术图册”：真实设备体积/材质/细节、结构拆解与正交平面、局部放大、可信剖面和功能路径；不能只改白背景或继续用方块替代设备。
- 五张参考已按原字节保存，视觉采用不证明型号/尺寸/结构事实。四种用法见10规范；R5允许有解释作用的场景上下文，不强制抹成无背景。
- 当前已从计划进入实施，一次一项，accepted/published留回执；不覆盖旧资产/研究原件，不恢复退役海报/烘焙页。

## 进度
- 已完成：五参考身份/尺寸/SHA、基线main六种浏览器画面及9张部件资产实看、35项清单、规范/机器配方/验收映射。
- TA-01：通用有壳SSD样板、3次生成/结构修正、独立SVG标注与嵌入原PNG、现有部件档案入口、放大/部件说明/双下载已通过本地检查。验收见 `docs/design/technical-atlas/TA-01/acceptance-v1.json`；已完成PR382与首次公网验收，见publication-20261008.json；轻量预览PR383合并983c90并实读，470464字节，9条可编辑文字；公网预览SVG6.49秒，AWS独立发布HEALTHY。用户明确肯定线上样板并要求继续，已记队列。旧渲染原件保留。
- TA-02本轮固定共用暖白/无色柔光/轮廓/独立SVG文字与导出配方，实际测试/发布见TA-02验收及PR回执。仅共用基础；其余33项具体模型/插图仍待制作。旧2D仍需重制，独立严格俯视入口尚无。1个GLB明确rejected，不自动采用。
- 实际发布按逐项回执；源文件存在不冒称生产完成。

## 下一步
1. 收口TA-02验收与实际发布后，下一项TA-03机箱盖板与壳体；对照R2和已验SSD画法，保留无字原图/独立标注，不把现有低细节3D几何当精细重制完成。
2. 随后按队列逐张部件→服务器/机柜→2D→园区/领域→档案/面板→跨尺度讲解。
3. 新会话读此交接与10规范、对应队列项即可；不从历史启动已结案的审批。

## 待用户决定
当前标准与计划登记无需追加决定。具体图若要从通用示意升级为某厂商/型号，领取该项时核对证据与交付用途。

## 入口文件与工具
- `framework/10_visual_atlas.md`、`framework/visual_atlas.json`、`framework/visual_atlas_migration.json`。
- `docs/design/technical-atlas/MIGRATION_PLAN.md`、`docs/design/technical-atlas/references/`。
- 本地观察截图：`~/.local/share/inresearch.ai/technical-atlas-audit/2026-10-08/`，非生产改版回执。
- `PYTHONPATH=src:tests/unit python3 -m unittest test_visual_atlas -q`；governance refresh/check、validate --strict、registry。
