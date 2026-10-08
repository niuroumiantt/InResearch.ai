# 白底技术图册标准与逐图计划交接（2026-10-08，m5）

## 目标
采用用户提供五张技术图为今后标准，按已登记顺序逐项更新。用户已进一步授权“一个一个更新，开始更新”，无需每项重复询问是否开始。

## 已定规则（不再重复确认）
- 用户已采用“白底技术图册”：真实设备体积/材质/细节、结构拆解与正交平面、局部放大、可信剖面和功能路径；不能只改白背景或继续用方块替代设备。
- 五张参考已按原字节保存，视觉采用不证明型号/尺寸/结构事实。四种用法见10规范；R5允许有解释作用的场景上下文，不强制抹成无背景。
- 当前已从计划进入实施，一次一项，accepted/published留回执；不覆盖旧资产/研究原件，不恢复退役海报/烘焙页。

## 进度
- 已完成：五参考身份/尺寸/SHA、基线main六种浏览器画面及9张部件资产实看、35项清单、规范/机器配方/验收映射。
- TA-01：通用有壳SSD样板、3次生成/结构修正、独立SVG标注与嵌入原PNG、现有部件档案入口、放大/部件说明/双下载已通过本地检查。验收见 `docs/design/technical-atlas/TA-01/acceptance-v1.json`；实际生产发布另留回执。旧渲染原件原样保留，其他34项未制作。
- 当前旧2D是分类平台/方块；3D有色光/反光地面/雾化；SSD旧图实际是机箱抽盘；独立严格俯视入口尚无。1个GLB明确rejected，不自动采用。
- 源码合并/CI回执见本PR；规范与计划登记不宣称生产画面已改版。

## 下一步
1. 完成TA-01生产发布回执后进入TA-02共享3D图册配方，对照R2/R3与已验SSD样板；静态图不能替代原交互。
2. 随后按队列逐张部件→服务器/机柜→2D→园区/领域→档案/面板→跨尺度讲解。
3. 新会话读此交接与10规范、对应队列项即可；不从历史启动已结案的审批。

## 待用户决定
当前标准与计划登记无需追加决定。具体图若要从通用示意升级为某厂商/型号，领取该项时核对证据与交付用途。

## 入口文件与工具
- `framework/10_visual_atlas.md`、`framework/visual_atlas.json`、`framework/visual_atlas_migration.json`。
- `docs/design/technical-atlas/MIGRATION_PLAN.md`、`docs/design/technical-atlas/references/`。
- 本地观察截图：`~/.local/share/inresearch.ai/technical-atlas-audit/2026-10-08/`，非生产改版回执。
- `PYTHONPATH=src:tests/unit python3 -m unittest test_visual_atlas -q`；governance refresh/check、validate --strict、registry。
