# 原生 XLSX 字段证据接入

接续 stock-throughput-20261011 与私有 stock-tabular-pilot-20261011。用户授权持续扩批、具名审核、正常发布；不要求关联模型用途或读完整篇。

## 实现与验收

标准库适配器 `src/inresearch/adapters/xlsx_document.py` 读取真实 ZIP/XML 单元格，`xlsx:sheet:N:cell:C2:context:A1:E3` 选择值和审核矩形；冻结表名、原生值/类型、日期系统、合并表头与脚注。公式不执行，选中公式缓存/错误值拒绝；外链不读取，大小/重复成员/实体/合并表头截断有界拒绝。object-review 的来源SHA、首次接收、具名C3、CAS、旧版本和无写重放保持；固定提取只产候选。

本机完整单元2418项通过，76.967秒；研究与行业浏览器通过。三份真实HBM表在Spark私有目录用待发布适配器复验40处字段/上下文，0.135秒、0模型调用；没有修改原件。候选尚有发行者出处、组合产品身份和估算/单位待核，新增正式采用0、上线0，不能把能力或原生单元格数计为采用。

## 接续与发布

M5/Spark私有 `~/.local/state/inresearch.ai/stock-tabular-pilot-20261011/` 保存40项线索、原生上下文及adapter-acceptance.json；最新已完成采用批仍为 stock-throughput-20261011，总219条/44对象。正式CI、合并、网站镜像/API、Spark版本及小时实际吞吐以同目录后续回执为准，本文件不是上线证明。

本阶段设置具名stop-coordinator，允许已有子进程自然完成，并沿原发布器收尾#759；没有重启Reader。实际发布验收后必须只移除owner=native-xlsx-evidence-20261012的标记，恢复同一LaunchAgent。不得触碰有其他任务的主目录或并行发布。接下来核二手表真实出处/标准与产品/预测系列身份；未知不补造MS的全称或URL，也不把H200/H20组合值拆成单独型号。
