# 美国数据中心抢电，争的是通电时间

第四版｜格洛可｜资料截至2026-10-09。

正文围绕一个判断重新撰写：能按期送到园区的可靠电力，正在改变扩建门槛、长期付款和选址。6,193个汉字、7,225个非空白字符（含标点/英文，排除标题、信息行、图注、引用编号与来源/备注），按含标点正文约7000字交付。六章保留需求→地区瓶颈→项目真实性→成本分担→供电路线→布局变化，去掉岔线、官方套话与重复平衡段。

## 阅读与公众号文件

- `wechat.html`：公众号复制版，约2.95MB，全部样式内联、11张图片Base64内嵌（首图+10正文图），无脚本、外链CSS或操作按钮。
- `full.html`：完整网页版，桌面正文720px；手机390px视口中正文374px、两侧8px。
- `lite.html`：轻量网页版，图片使用同目录assets相对路径，需要与assets一起保留。
- `article.md`：可编辑正文；`assets/v4-*`：10张正文图与可编辑SVG（2张地图、3张工程路径图、5张数据/阶段/合同/机制图）。
- 首图：`cover-master.svg`与2400×3600 PNG母版、1080×1620正文JPEG；另交900×383列表封面，不代替正文完整图。

正文发布图JPG/PNG、1280px宽，单张小于1MB，按照已读取的[微信官方正文图片上传接口](https://developers.weixin.qq.com/doc/service/api/material/permanent/api_uploadimage)要求提供。Base64是本地复制包形式，尚未转换为账号素材URL。微信编辑器实际粘贴、素材上传及发布待验证。浏览器复制测试不等于微信实粘。

重要标签、收费基数、年度/小时和合同/批准/投运状态直接在图中。第一章首段后就是三大互联地图。地图的州形状来自Census，互联边界对照EIA/ERCOT概览重绘，不用于园区接入判定。工程图、曲线和调度为通用示意；AI插画不作项目证据。

## 研究文字及溯源

`research.txt`、`research/research.md`继续保留未删节研究内容；本轮仅精简公开正文，不降低材料覆盖。附13个现行问题、9条目标需求快照、50条机制/数字候选、23份素材接收导读、反证和缺口。

`sources.json`保存52条访问/线索记录，45条成功访问身份按原始字节SHA或网页工具响应SHA分别核对；受限原站链接与工具正文的身份分开，失败不算已读。`work/v3/visual-sources.json`记录地图/地理/技术来源，第四版沿用已核对图并重新选择排序，任务及人工审核见`work/v4/figure-plan.json`。

实际23份submission字段与JSON Schema验证通过；候选状态、原文定位与原件身份保持。原件放本机数据目录，并单独提供research-originals.zip和visual-originals.zip，不进入Git。研究文字与正文不重复算独立证据；未执行远程导入、Reader逐页深读/C3、事实/价格/项目容量/模型采用或研究问题关闭。

## 验收与制作

`checks/build.json`记录字数、图片尺寸和HTML体积；`checks/browser.json`记录最终HTML哈希对应的桌面/手机渲染和11张图复制往返；`checks/validation.json`核对来源身份、候选短引、schema、上传限额、计算及EIA原表。10幅正文图及首图已按最终手机显示核对，编辑取舍见`checks/editorial-review.md`。同一作者复核，不宣称独立第三方终审。

制作顺序：`work/tools/render_v4.cjs`检查10份SVG文字边界并渲染首图→`build.py`组装三种HTML→`validate.cjs`生成最终浏览器检查→`audit.py`核对资料与交付。正文图沿用v3已审核资产，新版复制为v4文件；本次没有重新生成工程插画或把旧图强塞进新正文。程序环境见runtime工具；audit另需BeautifulSoup和jsonschema。

长文规则v2.7补充明确角度、删中庸套话与基建机制讲解；规范与实现均在独立工作树处理。旧规则v2.6已归档，前三版文字/HTML/检查与包保存在本机history/v1—v3，旧图资产仍留存。交接见docs/handoff/us-datacenter-power-20261009.md，研究反哺见docs/research/2026-10-09/us-datacenter-power/README.md。

交付包仅包括当前成品、当前图源、制作/检查和未删节研究材料；原件另包，SHA见下载目录packages.json。源码PR与本地交付不代表网站上线、微信发布或数据库采用。
