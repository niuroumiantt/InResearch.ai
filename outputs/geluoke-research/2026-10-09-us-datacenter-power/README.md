# 美国数据中心的电力现状：缺口在哪里，谁来补，谁付钱

格洛可专题｜资料截至2026-10-09。正文14,967个汉字、17,261个非空白字符（含标点/英文，排除图注、来源与制作说明）。六章沿需求→地区瓶颈→项目真实性→成本分担→供电路线→布局变化展开，第一章补美国电力与数据中心底图。

## 公众号与阅读

- `wechat.html`：公众号复制版，约1.02MB，全部样式内联、7张图片Base64内嵌，无脚本、外链CSS或操作按钮。
- `full.html`：完整网页版；`lite.html`：轻量网页版，图片使用同目录assets相对路径。
- `article.md`：可编辑文字稿；`assets/`：首图2400×3600母版、1080×1620正文版、可选横版列表封面、6幅1280px正文PNG及SVG源文件。

正文图片都是JPG/PNG，单张约62—205KB，小于[微信官方正文图片上传接口](https://developers.weixin.qq.com/doc/service/api/material/permanent/api_uploadimage)所列1MB限制；该接口原文已保存，读取于2026-10-09。正文总览图和横版封面分别提供。未使用外部摄影图或伪二维码。

公众号使用：打开wechat.html复制渲染后的正文；若编辑器不接受内嵌图片，按正文顺序上传assets中的cover-wechat.jpg和fig1—fig6 PNG，用公众号素材替换。Base64是本地复制包，不是微信素材URL。实际公众号账号上传、编辑器实粘及发布尚未执行，状态为“公众号待验证”。

## inresearch.ai素材

`research/research.txt`为UTF-8研究文字材料，`research/research.md`为可点击来源版。它们提供50条数字/机制候选、13个现行问题对应关系、9条五类变量目标快照、反证与剩余缺口。它们不同于文章去排版，不把文章当成独立佐证。

`research/submission.json`沿现行接收schema登记23份有定位的素材导读，全部通过真实`manage.py submissions`字段机检及JSON Schema检查。没有虚构workorder。接收器分流4份疑似冲突A与19份待匹配；报告保留在checks/intake-review.md。A提示包含美国/全球、年份、百分比分母不同的比较，不能自动视为实质冲突，也没有因格式通过自动采用。`research/intake-scope-review.md`解释这些边界。

`sources.json`保留46条访问/线索记录：包括成功原件、网页工具正文与失败访问；失败不计已读证据。实际核对39条来源访问身份，其中6条受限原站链接使用归档工具响应，分别标识。原始PDF/HTML及响应放在本机原件目录，并独立打包`research-originals.zip`，不进入Git。`research/originals-manifest.json`记录原件SHA；网页工具响应的SHA不冒充原站字节SHA。

导入前先核对原件包SHA，将research文字与submission目录交给既有素材接收/阅读流程。可运行`python3 manage.py submissions <解压目录>/research`复核字段；该命令没有执行Reader深读、C3或远程数据库采用。本包也不是inews日报daily-receive事件包。正式价格、事实、项目GW与模型基准均未改写，研究问题未关闭。

## 核验

checks/validation.json记录来源身份、短引、实际表格、作者计算、HTML与图片限额；checks/browser.json记录wechat/full/lite在1000px和390px的整篇布局检查，无横向溢出。网页手机版两侧8px，实际正文374px，桌面正文720px。浏览器实际复制并读取HTML剪贴板，再插入contenteditable，7张图片全部保留。

六幅图及首图已目检；手机正文与六章视口已检查，整篇截图在checks中。来源核对与编辑审核由同一作者完成，不宣称独立第三方终审。PDF采用物理页码并与正文页码分别标记；引用只定位相关内容，未宣称全部原件逐页深读。配电变压器历史交期不推广为全部主变2026报价，供电容量不冒充IT负荷，未来节点不冒充投运。

仓库治理9项单元测试、governance检查、严格数据校验及对象引用检查通过。额外运行现有`submissions --selftest`时，一项既有“普通材料”样例被库内不同施工口径的11600元/㎡记录判为疑似冲突A（样例4200元/㎡），导致旧预期“待匹配”断言失败。本次未改分流代码、样例或事实库；实际交付23件格式校验通过，既有自检失败单独记录在checks/repository.json。

## 制作与保留

work/tools包含取材、研究侧车、SVG制图、浏览器渲染、组装、校验脚本。build.py在渲染完成后运行；渲染环境需要Python/Pillow、PyMuPDF、BeautifulSoup、jsonschema与Playwright。acquire.py只用于本篇人工研究原件，不是生产采集器；重跑取材可能改变当前网页版本，应另建批次保留旧原件。候选生成时以原件已有状态与日期为准。

规则v2.4与交付登记在独立工作树分支完成，未改动原主工作区已有任务。成品zip不含原件、缓存或密钥；研究原件zip另外交付，不计第二份独立证据。交接与研究反哺台账在仓库docs/handoff和docs/research中，后续按台账补证，不直接覆盖既有事实。
