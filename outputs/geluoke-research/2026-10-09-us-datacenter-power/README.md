# 美国数据中心的电力现状：缺口在哪里，谁来补，谁付钱

格洛可专题｜资料截至2026-10-09。正文12,889个汉字、15,013个非空白字符（含标点/英文，排除图注、来源与制作说明）。六章沿需求→地区瓶颈→项目真实性→成本分担→供电路线→布局变化展开，第一章补美国电力与数据中心底图。

## 公众号与阅读

- `wechat.html`：公众号复制版，约3.50MB，全部样式内联、15张图片Base64内嵌，无脚本、外链CSS或操作按钮。
- `full.html`：完整网页版；`lite.html`：轻量网页版，图片使用同目录assets相对路径。
- `article.md`：可编辑文字稿；`assets/`：首图2400×3600母版、1080×1620正文版、可选横版列表封面、14幅正文解释图（3张地图、3张对应工程图及8张数据/关系/阶段/对照图）；14份可编辑SVG附文字层与来源。

正文图片都是JPG/PNG，单张均小于1MB，符合[微信官方正文图片上传接口](https://developers.weixin.qq.com/doc/service/api/material/permanent/api_uploadimage)所列单张1MB限制；该接口原文已保存，读取于2026-10-09。正文总览图和横版封面分别提供。工程场景为用户提供的AI插画或本次生成的通用示意，不是真实项目照片。五张用户参考与历次新图原件共10件保存在本机visual-originals；可移植预览、SHA、实际尺寸与角色见work/visual-references.json；历次内置image_gen提示词保留；新版SOFC提示词见work/v3/illustration-prompt.txt。原始PNG另交新版visual-originals.zip，未把AI图当研究证据。

公众号使用：打开wechat.html复制渲染后的正文；若编辑器不接受内嵌图片，按checks/build.json的public_images顺序上传首图与14张正文JPEG/PNG，用公众号素材替换。Base64是本地复制包，不是微信素材URL。实际公众号账号上传、编辑器实粘及发布尚未执行，状态为“公众号待验证”。

## inresearch.ai素材

`research/research.txt`为UTF-8研究文字材料，`research/research.md`为可点击来源版。它们提供50条数字/机制候选、13个现行问题对应关系、9条五类变量目标快照、反证与剩余缺口。它们不同于文章去排版，不把文章当成独立佐证。

`research/submission.json`沿现行接收schema登记23份有定位的素材导读，全部通过真实`manage.py submissions`字段机检及JSON Schema检查。新版另补6份地图/地理/技术来源用于图面核对，未增补submission或50条候选；没有虚构workorder。接收器分流4份疑似冲突A与19份待匹配；报告保留在checks/intake-review.md。A提示包含美国/全球、年份、百分比分母不同的比较，不能自动视为实质冲突，也没有因格式通过自动采用。`research/intake-scope-review.md`解释这些边界。

`sources.json`保留52条访问/线索记录：包括成功原件、网页工具正文与失败访问；失败不计已读证据。实际核对45条来源访问身份，其中7条受限原站链接使用归档工具响应，分别标识。原始PDF/HTML及响应放在本机原件目录，并独立打包`research-originals.zip`，不进入Git。`research/originals-manifest.json`记录原件SHA；网页工具响应的SHA不冒充原站字节SHA。

2026-10-09续做已核对传输147文件与上游原始归档89文件SHA，Spark实际接收23/23来源（20下载原件+3明确身份的工具响应UTF-8载体），候选匹配23、错误0。接收回执与载体响应/派生SHA说明分别见checks/spark-intake-final-receipt-20261009.json和checks/spark-intake-final-provenance-20261009.json；当前状态与剩余步骤见[研究接收台账](../../../docs/research/2026-10-09/us-datacenter-power/INTAKE-20261009.md)。本包不是inews日报daily-receive事件包；正式价格、事实、项目GW与模型基准均未改写，研究问题未关闭。

## 核验

初次第三版的历史检查：checks/validation.json记录来源身份、短引、实际表格、作者计算、HTML与图片限额；checks/browser.json记录当时wechat/full/lite在1000px和390px的整篇布局检查，无横向溢出。网页手机版两侧8px，实际正文374px，桌面正文720px。浏览器实际复制并读取HTML剪贴板，再插入contenteditable，15张图片全部保留（含首图）。

初次第三版的十四幅正文图及首图已目检；当时手机正文与六章视口已检查，整篇截图在checks中。来源核对与编辑审核由同一作者完成，不宣称独立第三方终审。PDF采用物理页码并与正文页码分别标记；引用只定位相关内容，未宣称全部原件逐页深读。配电变压器历史交期不推广为全部主变2026报价，供电容量不冒充IT负荷，未来节点不冒充投运。

仓库治理9项单元测试、governance检查、严格数据校验及对象引用检查通过。额外运行现有`submissions --selftest`时，一项既有“普通材料”样例被库内不同施工口径的11600元/㎡记录判为疑似冲突A（样例4200元/㎡），导致旧预期“待匹配”断言失败。本次未改分流代码、样例或事实库；实际交付23件格式校验通过，既有自检失败单独记录在checks/repository.json。

## 制作与保留

文风为A行业编辑讲解主、B科技报道叙事辅；事件导语与六章专属问题目录已落实，编辑审核见checks/editorial-review.md。旧规则v2.4/v2.5已归档，旧稿HTML与文字在本机history/v1、history/v2保留；旧场景资产保留但不再嵌入新版正文。inews口吻/提纲/提示词与PR256合并状态已核对，没有改动该仓库自动图表渲染器。

work/tools包含取材、研究侧车、SVG制图、浏览器渲染、组装、校验脚本。新版按figures_v3.py→render_v3.cjs→PNG优化→build.py制作；生成几何使用Shapely、Albers投影和Census原件，地理数据与工程原始栅格另包。重新生成图后review_status恢复pending，必须再次人工审核才能运行最终audit.py；旧figures.py/prepare_scenes.py流程只用于历史版本。build.py在渲染完成后运行；渲染环境需要Python/Pillow、PyMuPDF、BeautifulSoup、jsonschema与Playwright。acquire.py只用于本篇人工研究原件，不是生产采集器；重跑取材可能改变当前网页版本，应另建批次保留旧原件。候选生成时以原件已有状态与日期为准。

规则v2.6与交付登记在独立工作树分支完成，未改动原主工作区已有任务。成品zip不含原件、缓存或密钥；研究原件zip另外交付，不计第二份独立证据。交接与研究反哺台账在仓库docs/handoff和docs/research中，后续按台账补证，不直接覆盖既有事实。


## 第三版图文对应修订

第一章首段之后就是美国本土三大互联地图，州界和系统概览分界分别标注，得州覆盖与有限直流联络直接写在图内。所有图先回答紧邻正文的问题，任务及逐图审核见work/v3/figure-plan.json。费用图说明两种85%的基数，核电图分清购电与重启，俄亥俄现场供电图采用案例实际设备SOFC，州价地图直接标中文州名。正文重写章节承接、调整案例顺序、删去重复尾段；沿用A主B辅。重要说明进入主图，图注只保留图题与来源。

三张地图使用真实州形状，互联范围依据EIA/ERCOT概览重绘，不能判定具体园区接入边界；其他两张州地图只标示案例/价格所在州。新版来源和几何身份在work/v3/visual-sources.json，原件/工具响应与失败请求分别保留。全部正文发布图1280px宽，单张最大约0.55MB。完整浏览器检查已通过15张图复制往返，真实公众号实粘仍待验证。

第三版规则与成品源码[PR #427](https://github.com/niuroumiantt/InResearch.ai/pull/427)已合并；该PR的CI因Actions预算阻止job启动，不能记为CI通过。旧PR #423也已合并。已保留远程同期技术图册改动。初次交付包仍在m5原位置，续做图9成品zip另存本次工作树ignored的reports/output/geluoke-delivery/，不覆盖旧包；本轮包装SHA另存同目录packages.json。

## 2026-10-09续做：图9与实际研究接收

图9总题、alt与图注改为客户成本，数据及条件保持；只重制图9并实际查看374px手机图。三版HTML的390/1000px共6次检查通过；新检查为checks/*title*20261009*，原有检查未覆盖或冒充本轮执行。

Reader scope保留既有133条与日报选择，追加23条至156（先21、解析器部署后再加DOE/PJM两条）。2026-10-09 11:39:55北京时间快照：23/23注册，hold0，queued22/complete1，triage14/read2/extract6/complete1，chunks_read13、完整封存报告1；完成项为Crane工具响应正文载体，不称23份已深读/C3。PR #436已合并，Spark Reader于11:27:32安全换代，新PID1644248 active/running、源码b5e669ab、解析器SHA322b316bbc5bc0bce0c3fc4b4835b2a23c7f9d42f06c0f81ae20f17a26aaa650。最终快照与服务回执为checks/spark-reader-progress-final-20261009.json和checks/spark-parser-service-release-20261009.json。

首次官方扫描因another_worker_owns_queue拒绝，当时未强占/第二worker/重启；11:10:44的21注册/封存0快照与初次回执继续保留。后续安全换代及23注册以最终记录为准。最终回执保留初次阶段字段，当前由scope_after_parser_release156和空hold明确覆盖。

FERC六月改革、Crane、Talen三份正文载体只解码归档工具JSON正文并加身份头；响应SHA与派生UTF-8 SHA分别登记，原站字节SHA保持null，不增加独立证据。URL仍在永久incoming来源侧车，未完整导入catalog。来源接收、候选匹配、Reader注册与完整阅读分开计量；已有1份封存，C3、正式研究采用及公众号实粘/上传/发布均未执行。

初次交付历史保留：原README曾写“实际公众号账号上传、编辑器实粘及发布尚未执行”和“该命令没有执行Reader深读、C3或远程数据库采用”。其中公众号、深读与C3边界仍适用；本轮新增来源接收/Reader登记以真实回执为准，不改写旧检查。

最终本轮本地验收：治理2026.10.09.12、1532文件清单通过，严格数据校验0 warnings、对象/问题引用353/458有效、9项治理单测及最终三HTML×两视口6次检查通过。图9最终374px手机图已实际目检。CI按本次用户授权不查询或等待；本机图文交付与Spark来源/Reader服务回执分别计量。
