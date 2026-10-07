# 历史产品/文档增补接收（2026-10-07）

用户 mini 当前只读查询返回4,916个PDF内容、1,735个HTML快照，最近 observation 2026-09-23T17:55:06Z；产品样例含旧SYS、MicroCloud、SSG和带+型号。链接样例含机箱手册、电源Test Report、插件规格书。原文归档不是产品总数，更不是全文采用。生产9000b22用户回执为5型号/105原表，原件归档与网站接收断点单独补齐。

Fetchspec `legacy_catalog` 离线验证HTML、保留观察时间和原表，从edges挂接附件并生成按台账内容身份去重的文档索引；只打包HTML/JSON，不传输40GB PDF。接收支持显式`historical_supplement`：保留当前批次全部已有型号的payload，追加新身份，重叠旧来源进版本/spec历史；不会因更晚导出时间自动覆盖已接收资料。相同增补run在任意后续批次后可重放；默认snapshot行为保持，未知mode拒绝。sources与material父页面关系需有官方HTML回执，文档链接ID来自台账，不声称PDF字节在本批被核对或抽取。

`import-bundle`从文件或stdin读有界tar，只允许清单/报告、batch JSON、按SHA命名的HTML普通文件。拒绝路径穿越、链接、重复项；所有清单、batch、HTML字节和跨批产品关系验证后开始逐批事务。批次可独立重试，收到部分批次仍保留原目录；并发更新可能使后续旧导出批次拒绝，重跑离线导出即可，无需修改原件或当前库。

文档元数据分库存SQLite。公司首页仅取count；同一公司入口`view=materials`分页50条，链接/关联按每项最多4个投影，按文件名/官方路径/型号/标签搜索，未关联文档仍显示。点击官方文件名打开原文；关联型号打开同一产品规格入口。旧height路径按官方路径关联服务器，SSG路径关联存储，chassis关联服务器业务，未知插件仍待关联；不改厂商taxonomy。不将电源报告等推成整机规格。

用户推进入口在Fetchspec的`scripts/publish_supermicro_legacy_from_m5.sh`：m5与mini均采用独立worktree；mini导出、AWS部署模块检查、SSH管道传输、容器验证入库、m5存回执、查询生产轻量摘要。旧台账、原件、源代码常驻分支和研究采用状态保持各自边界。测试使用明确TEST_VALUE，真实mini解析与本次AWS入库数量需新回执，不能复用9000b22的旧数据验收。

后续生产验收：用户m5导入回执及AWS API确认保留5条并加入1,142条，合计1,147条目、1,063型号、10,101原表、4,916文档索引。AWS8ab28002健康，未关联文档4,376份仍可检索。导入无需重复执行；分类导航的新发布见`company-category-navigation-20261007.md`。
