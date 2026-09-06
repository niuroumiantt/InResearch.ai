# Spark资料落点与百度网盘迁入建议

> 同日后续方向更新：用户希望每日持续投料，由27B逐篇粗读、深读和整理。新的投递口建议为
> `/home/spark/.local/share/inresearch.ai/raw-materials/`（尚未创建），`library/`细化为整理后目录。
> 详见 `docs/local_reader/CONTINUOUS_READER_DESIGN.md`。下文保留前一轮静态存储建议与核查记录；
> 其中直接复制到library的命令不作为后续常驻收件流程，传输完成识别与原件台账须一并落实。

2026-09-06用户确认：原件已临时迁出，全部在百度网盘；希望利用Spark余量存储，并让模型持续分析。此文是落点建议与已完成环境核查，尚未执行资料下载、迁移或后台分析部署。

Spark（SSH别名spark，实际主机dgx，用户spark）为ARM64 Ubuntu；实测根盘3.7T，已用103G，剩余约3.4T。系统可用内存当时约61GiB，总内存121GiB。磁盘可存放全库，模型处理仍需分批，不能把磁盘容量当模型上下文容量。

已准备的空目录：

- Spark原件主库：`/home/spark/.local/share/inresearch.ai/library/`，目录权限0700。
- m5百度网盘下载暂存：`/Users/m5/.local/share/inresearch.ai/downloads/`。

建议本轮使用m5官方百度网盘客户端下载，再以rsync复制到Spark。m5实测尚余约1.7TiB，足够历史91GB量级的暂存；实际下载量以网盘清单为准。百度有[官方Linux下载入口](https://wangpan.baidu.com/download)，但本轮未验证其客户端在Spark ARM64上的可用性；Spark当前也没有查到BaiduPCS-Go、bypy或baidunetdisk命令。直接下载并非原则上不可行，需另行验证官方客户端/网页或授权接口，不把第三方文章声称的ARM支持当作已确认事实。

在m5的Terminal执行（先等客户端确认下载完成）：

```bash
rsync -rt --partial --progress /Users/m5/.local/share/inresearch.ai/downloads/ spark:/home/spark/.local/share/inresearch.ai/library/
```

该命令复制下载目录内的内容，可重跑接续未完成传输，不带删除选项。迁入前后核对目录结构、文件数/大小及哈希，百度网盘继续保留原件。rsync完成不等于百度端全部文件已经下载，必须对照客户端完成清单。若客户端多套一层总目录，接入研究索引前再按实际结构定位，保留内部分类与文件名。

建议后续布局（除library外尚未创建）：

```text
/home/spark/.local/share/inresearch.ai/
  library/       原始研报、工程文档，保留目录结构
  product/       产品规格与官方资料
  extracted/     文本、表格、逐页OCR结果
  indexes/       本研究项目的检索索引
  candidates/    模型提出的候选事实与待审结论
  artifacts/     需要长期保存的审读成果与报告

/home/spark/.local/state/inresearch.ai/
  jobs/          队列、断点和处理状态
  logs/          运行日志

/home/spark/code/inresearch.ai/   源码与已审核的版本化研究
```

该布局遵循infra工作区规范。迁移接入时可让代码目录中的`docs/library`软链到library、`product`软链到产品原件目录，保留当前索引引用契约；须等完整性和目录结构确认后设置，不能覆盖已有文件。

Spark现在已有Ollama、LiteLLM、Open WebUI及文本/视觉/向量模型；pdftotext和LibreOffice可用。现有infra运行分工仍是Spark供模型、mini跑文件worker。把数据放上Spark不会自动产生持续分析，下一轮需明确部署读取本地资料的worker与断点队列，优先并发1，并与既有模型负载协调。

分析流程建议：新文件哈希登记→文字PDF抽取/扫描PDF逐页渲染→分类与候选事实→口径和原文页码检查→审核后入facts/Finding→报告。模型只读原件，结果落独立目录；空文本应报读取失败，不让模型猜内容。现有通用队列终态payload/result默认14天清理，不能当长期成果库；采用结果及时写入artifacts或版本化知识层。网站继续消费审核后的研究资产，无需随原件一起搬到Spark。
