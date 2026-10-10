> 当前继续入口：[2026-10-10图册交接](technical-atlas-20261010.md)。下文为2026-10-09历史快照；旧单图PR/当时进度与工具指令不恢复为当前执行规则。

# 白底技术图册移交 m4（2026-10-09）

## 目标与现行入口

用户要求把本任务放到 m4 的 Codex 对话继续。原35项按01–35逐张推进，TA-36–39补充独立计量。本文件仅为跨机器交接快照；实际进度以 `framework/visual_atlas_migration.json` 和逐项发布回执为准，不从旧 heartbeat 的3/35起点重做。

开场先读 AGENTS.md、framework/CURRENT.md、framework/current_state.json、docs/DECISIONS.md 当前变更摘要、framework/10_visual_atlas.md、framework/visual_atlas_migration.json。历史细节按需读 docs/handoff/technical-atlas-standard-20261008.md 的末尾；不是整篇启动指令。

## 当前进度

- 主计划7/35真实发布：TA-01 SSD、02共用配方、03机箱、04 GPU基板、05 GPU/HBM封装、06 CPU/RDIMM主板、07网卡。补充TA-36–39已发布4/4。
- TA-07源码PR425合并de17171b；回执PR426合并0f7dc743。最终AWS0f7dc743为HEALTHY/容器healthy，主图四公网视图、八标签、原PNG SHA、真实SVG/PNG双下载和3D档案画布已核验。记录：docs/design/technical-atlas/TA-07/publication-20261009.json。
- TA-07最终收尾原始记录已同步m4数据目录 ~/.local/share/inresearch.ai/technical-atlas-audit/2026-10-09/TA-07/release-closure.json；原截图、CI jobs/annotations与本地/公网观察保留。旧nic.png和全部参考原件保留。
- 下一项TA-08电源模块，仍planned、尚未生成。旧图web/assets/renders/psu.png；参考R2。先核对官网连接器/抽拉/格栅结构，再实际传入参考并使用内置图像工具。
- 并行长文PR423/427是其他任务，已合并内容必须保留；TA-07合并后曾出现治理摘要过期，已在PR426人工复核并修正，不能再覆盖其他任务规则。

## 已授权规则与质量

- 暖白#FAF9F2、真实材质、细轮廓、精细结构、独立清晰标注。正式源10_visual_atlas.md v1.7及visual_atlas.json登记14张参考；R10–14是未来园区/建筑/供能细节参考，不是新完成项。每张实际查看并传入指定图，源PNG、旧版本原件保留。
- 只用内置image_gen.imagegen，不切换CLI/API。SVG独立标签与同像素JPEG轻量预览使用仓库脚本，母图不改写。不能把未知型号、几何、接口代际/速率、数量或路径当工程事实。
- 新图必须接到实际2D系统/尺度入口；3D画布保持交互，不冒称具体3D几何重建。整机图加入时保留此前子装配可达。
- 每项制作→审图→页面→相关测试→规范治理→精确PR头→部署→真实公网验收闭环，只实际发布才published。通常一张两PR（源码、真实发布回执），私有最终收尾避免递归PR。
- 用户已授权持续修改/发布，不每张确认。对Actions预算阻止启动已明确“忽略这个，直接close pr并更新”：核对精确头、四job零steps和budget annotation后可处理此预算阻塞；不得声称CI通过或把真实执行失败豁免成预算。
- Spark服务检查只读：旧观察10cd748f，reader/research-review active，较网站旧的版本差异已记录；不为图片任务拉代码/重启Spark，不冒称同步。匿名研究401不等于已登录数据验证。

## m4执行与续做

1. 使用独立工作树 ~/.worktrees/inresearch.ai/technical-atlas；不切换、stash、reset或暂存主目录及其他任务变更。从最新远程main接续并保留并行规则；本机数据使用~/.local/share/inresearch.ai/，日志~/.local/state/inresearch.ai/。
2. 先核对本任务没有未收尾PR、当前队列仍TA08，再领取并制作，禁止重复TA07。旧提示词中的M5工作树路径不要套到m4。
3. 验证入口：scripts/build_technical_atlas.py；tests/technical_atlas.cjs、tests/part_dossier.cjs；tests/unit/test_visual_atlas.py、test_governance.py。人工审阅verification_contract.json摘要/未覆盖项后governance --refresh/--check、validate --strict、registry及相关测试。
4. 真实公网图验证见已有逐项publication记录；AWS自动独立部署后读取实际版本和healthy，Spark只读。仅新图上线、失败或需用户决定时通知；35项全部实际完成才停止。

m5旧automation-3已因本次迁移暂停，避免双重续做。当前Codex工具只看得到m5，没有m4远程对话连接，不能声称已创建/移动m4对话。用户在m4新对话读本文件接续；旧自动化不恢复。若用户希望继续原每小时频率，应在m4目标对话建立/接续唯一自动续做，保留上述真实队列和安静通知规则。
