# fetchquotes：Lambda公开报价单源受控接收

精确范围：fetchquotes-lambda-bootstrap／Lambda-instances-pricing／https://lambda.ai/pricing，原生JSON岛中1x标签、NVIDIA H100 SXM行及每GPU每小时表头和税费脚注。固定干净fetchdata提交在AWS真实取得公开HTML，Spark经生产接收器的独立目录/锁及不可变日志接收候选。正式采用、模型用途及调度另行验收。

这是公开标价offer，不是成交价、结算价、合同折扣或实际园区算力收入。原始$符号、$/GPU-hour单位及1GPU/VRAM/vCPU/RAM/存储配置保持；未知币种代码不猜USD、不换汇，不由报价推断实际库存、地域可用性、计费最小单位、承诺期限或有效期。适用sales tax/VAT/GST另计，完整实际费用仍未知。不把GPU租用服务报价当GPU采购单价。

先完整保留所有旧包，在run中明确history-root。同字节返回原ID和原信封，本次真实下载另记acquisitions.jsonl；不改旧采样时点，不宣称今天生效或新的成交。新字节另留SHA版本、采样取得时间；发布日及来源有效期限没有披露则未知。同一来源跨版本不算独立证据，不自动取最新覆盖旧值。

```sh
python3 fetchdata.py run --team fetchquotes --history-root /绝对路径/旧队数据根
python3 manage.py collector-receive /绝对路径/完整包 --data-root /现有私有数据根 --expected-receiver-revision <实际已部署40位提交>
```

整包冻结/校验/持久原件与候选后，核对共享catalog/blobs/originals才ACK。截断副本拒绝、完整重试；同包重放零新增且首次/完成时钟不变。投影失败保留待恢复到达、不ACK；已存原件损坏拒绝覆盖。布局/计费表头/脚注/行歧义变化报错留原件，不静默补值。

当前connection仍not_connected，真实AWS采集/Spark接收、重复和失败恢复待验。候选保持未审核/对象未匹配，不入Reader、不采用、不自动填参；不新增后台服务、自动传输或调度。
