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
- TA-02首次发布PR388合并7d369257，AWSHEALTHY/容器healthy，6项公网代码字节摘要匹配，机柜双外观下载/查看器正常。生产审图发现导出文字避让和园区匿名依赖受保护products.json，本轮修正并在后续PR实读，原权限保留。TA-02本轮固定共用暖白/无色柔光/轮廓/独立SVG文字与导出配方，实际测试/发布见TA-02验收及PR回执。仅共用基础；其余33项具体模型/插图仍待制作。旧2D仍需重制，独立严格俯视入口尚无。1个GLB明确rejected，不自动采用。
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

## 审图文件边界
TA-02初稿审图误复用了基线截图文件名，Git中的参考/旧渲染原件未改变；根目录截图不再作冻结基线原件。TA-02正式本地验收只引用`TA-02/final/`独立截图及SHA，生产另写`TA-02/live/`，后续每项使用独立目录。初始基线源码453f3625仍在Git历史。

本轮复审导出增加1x/2x像素比与文字位置/暖白底，公开园区启动的302登录HTML不再当必需数据；覆盖未读取明确未知。发布回执首次版本在TA-02/publication-20261008.json，修正后实际版本在本次PR的production receipt。下一项TA-03机箱盖板与壳体，不重复改SSD。

## 用户主入口补全（2026-10-08）

用户确认TA-02仅绘图/导出基础，截图显示2D SSD还是方块与旧机柜标签页。TA-01已有样板补入bom.html#ssd主图区，两排法的SSD缩略图替代方块；档案atlasHost显式路由且跨对象清除，3D默认档案行为保持。页面/JS/CSS no-cache条件核对，旧标签需刷新。TA-16/17其他对象仍planned；完成数仍2/35。实际发布凭据留在本次PR，不以本段提前宣布发布。下一项TA-03。

## SSD展示层级修正（2026-10-08）

用户确认新图已可见，指出放在数据中心总览之前不合适。移至包含SSD的系统/尺度行后，显示“IT · 存储 → 企业级 SSD”；#ssd定位该处，切换排法保持选中，其他对象清除SSD。现行10规范1.4替代此前不限定位置的主图区要求；母图、系统顺序和2/35进度保持。实际源码及生产核对另见本次PR回执。下一项TA-03。

## 用户改为设施2D优先（2026-10-08）

补充四张原始场景参考R6–R9并登记；现行10规范1.5。先TA-36土地与建筑→TA-37消防→TA-38安防→TA-39机柜结构，再回TA-03机箱；四张新增插图让计划成为39项，原35项身份/依赖不改。逐张无字母图、SVG标签、缩略预览和实际上下文入口验收，最终发布凭据见本轮PR，不据本地审图预填published。消防/安防沿原BOM分别显示，图为类别剖面而非严格俯视/施工图。

SSD位置修正PR397已上线162cf88a，四项CI通过，AWS HEALTHY/容器healthy；公网系统/尺度×桌面/手机四幅图确认所属行与可见路径。Spark只读观察仍06f96964、两服务active，未在本轮启动或重启Spark。来源/部署完整回执见PR397。

## 持续更新与当前补充批次

用户再次明确原35项按01–35推进，主计划2/35已发布，设施TA-36–39为独立补充。四张图完成本地验收，真实系统/尺度×桌面/手机入口检查和四对象technical_atlas+part_dossier回归通过；建筑/消防PR398已部署AWS fc0e2cc2、healthy，四项CI通过。公网主图与下载分别核验，最终收口见逐项publication记录。安防两次网络失败后第三次内置生成成功，无API/CLI切换；机柜结构是2D类别图，TA-13原3D几何仍planned。

本对话自动续做id=automation-3，每小时；无变化保持安静，原35项全部真实发布后停止。补充批次发布收尾后下一张TA-03机箱盖板与壳体。工作树 `/Users/m5/.codex/worktrees/ops-dashboard/inresearch.ai`，当前分支codex/atlas-facility-continue-20261008。禁止重做已验SSD/配方或把简化3D计完成。

Spark本轮只读观察06f96964，reader active；research-review在20:10后inactive（Result success、退出状态15），没有在本图册任务中启动/重启，网站2D部署独立。其他研究任务可能正在调整它，不擅自改动。

建筑/消防公网系统/尺度×桌面/手机及高清原SVG实际打开复验完成，7条可编辑标注，错误0；公网源码SHA与本地一致。高清原图在当前网络78.612/91.39秒，预览2.612/4.929秒；原件质量未压低。合入独立研究恢复PR399，只更新图册自己的实现与计量，保留其规则/私有worker操作范围。

## 补充四图实际发布完毕

建筑/消防PR398 fc0e2cc2；安防/机柜结构PR400 26b2aa2e（源头568d6f37，四项CI全通过）。四对象系统/尺度×桌面/手机及高清原SVG实际打开，逐项publication-20261008.json保存来源字节/PNG SHA、图像与DOM证据。最后观察AWS和Spark均26b2aa2e，AWS healthy、reader/research-review均active；图册任务仅只读Spark，没有替其他研究任务重启服务。

主计划2/35、补充4/4；下一TA-03。机箱旧原图已实际看过，机械折边/开孔/紧固不足；新图应明确服务器机箱子装配，不能当TA-11整服务器完成。M5预备提示词与待确认来源说明在 `~/.local/share/inresearch.ai/technical-atlas-audit/2026-10-08/TA-03/`；尚未生成/采纳，Dell网页仅目录可读，详细结构先核官方手册。当前工作树仍ops-dashboard/inresearch.ai，分支改为codex/atlas-facility-receipt-20261008。

公网冷加载/高清原件比本地慢，预览SVG每张约285–505KiB；2D总览随新图增加会出现缩略图和字体下载竞争，TA-16/17要处理实际视口按需读取，不能只以小于512KiB宣称网络已快。自动续做automation-3仍每小时，只在实际上线/失败/所需决定通知，35项实际全部完成后停止。

## TA-03 本地验收历史

补充发布收尾PR402四项CI全通过，2026-10-08T13:28:57Z合并d97b21ef。主计划继续分支codex/atlas-chassis-20261008；TA-03母图通过内置工具生成，原生1536×1024，8条SVG独立标签/271KiB预览；server为原有计算对象，图标题明确机箱子装配。旧chassis原件SHA不变，完整服务器TA-11未完成。正文和网页审图及technical_atlas/part_dossier实际回归已完成；精确头CI/实际公网验收后再登记published和3/35。当前主工作树不切换，仍复用ops-dashboard/inresearch.ai。

## 上一阶段 · TA-03 实际发布，下一TA-04

PR404精确头fec2ce60四项CI通过，首次发布 2ab6e7af2371514d81307b2bda637982f3949df2；实际系统/尺度×桌面/手机入口及高清8标签/嵌入原PNG SHA实读，AWS healthy，Spark两服务active（只读，没有重启）。逐项publication-20261008.json保留字节/浏览器/服务观察。主计划3/35、补充4/4，下一TA-04；当前收尾分支codex/atlas-chassis-receipt-20261008。

TA-04旧图已实看：八个虹彩简化器件在基板上，不能当单裸GPU die。备料在 `~/.local/share/inresearch.ai/technical-atlas-audit/2026-10-08/TA-04/`，含preparation.json和prompt-prepared-v1.txt；NVIDIA官方HGX H100/H200组件页与官方技术博客支持八SXM模组/NVSwitch类别关系，具体PCB布局/孔位/封装内部未知。尚未生成/采纳，续做从TA-04实际制作开始，保留old gpu-board.png的SHA。自动续做仍automation-3每小时，以队列未完成项为准，已授权发布无需重问。

本次公网审图为匿名浏览器，部件研究侧栏显示未载入；只读/api/research-summary实测401，保留原权限，不据pageerror=0声称已登录研究数据已验收。图册实际入口/原件与服务版本分别已验。

## 当前状态 · TA-04 实际发布，下一TA-05

制作分支codex/atlas-gpu-baseboard-20261008，复用ops-dashboard工作树，主工作区不动。前两张母图因GPU模组数量错误被拒，原件/提示词保留；第三张重建为2×4位置，七个已安装+一个抬起模组，独立8标注与四视图/放大下载及3D回归已实际本地通过。官方来源只支持八SXM/NVSwitch类别，具体几何/PCB走线/连接端/散热接触结构仍示意。主计划4/35、设施4/4；修正2D档案传入prices对象的既有GPU加载中断。PR409精确头44567d2a四项CI成功，首次发布e51cc0e65e573940e60a035bbf8b99d0af3e2ff2；实际公网四视图/8标签与嵌入PNG SHA、双下载HEAD、AWS healthy、Spark两服务active。当前收尾分支codex/atlas-gpu-receipt-20261008，先完成发布回执PR再领取TA-05。

下一TA-05备料在 `~/.local/share/inresearch.ai/technical-atlas-audit/2026-10-08/TA-05/`：preparation.json、prompt-prepared-v1.txt；旧hbm.png已实看，GPU+HBM封装与基板/板级模组区别明确。TSMC CoWoS-S与Micron HBM2E官方页支持硅中介层/相邻逻辑与HBM/垂直TSV类别；不假设所有CoWoS为硅中介层，堆栈数/层数/代际/尺寸未知。尚未生成，需实际传入R2/R3，保持TA-04/TA-03图可达。
