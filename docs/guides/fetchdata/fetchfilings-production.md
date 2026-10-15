# fetchfilings：公司披露候选的受控生产接收

当前准备范围只有Microsoft官方FY2025年报HTML，来源fetchfilings-microsoft-bootstrap／MSFT-AR2025。
AWS负责实际取得；Spark在既有acquisition/catalog.sqlite、blobs和originals保存永久候选。
源码与真实交付包通过既有私有渠道传送，不公开创建仓库。真实AWS采集、Spark生产首包、受控截断/完整重试及重复零增量已验，connection为receiver_live_file_import；仅上述单源范围，自动调度未启用。

## 范围和口径

候选finance.cashflow.additions_to_ppe保留集团合并范围、财政年度、USD million、现金流负号及不含非现金租赁增加额的限制；不得分配到Abilene或其它园区，也不代表设施/土地/IT完整资本成本。
披露日未知保留null；财政年度截止日不是单笔付款日。原件下载、实际复抓、首次生产到达、归档完成分别记时。
未知对象canonical_id保持null。正式研究采用和模型用途认证由研究端另行执行。

## 执行与保留

AWS在已固定提交的干净fetchdata源码执行：
```sh
python3 fetchdata.py run --team fetchfilings --history-root ~/.local/share/fetchdata/fetchfilings
```
既有旧包先完整保留在history-root/deliveries；相同原件命中返回旧信封，实际当前取得另存acquisitions.jsonl。字节变化另存SHA版本，不覆盖旧包或旧collector_revision。

Spark将完整包置于acquisition/incoming/fetchfilings后执行：
```sh
python3 manage.py collector-receive /绝对路径/完整交付包 --data-root /现有私有数据根 --expected-receiver-revision <实际40位已部署提交>
```
接收仅允许登记队名、source_id、native_id和URL完全匹配；冻结后再核队身份，拒绝中途变化。独立provider目录/锁/台账不接收其它队来源。
到达包持久化后才投影共享原件，原件/候选/来源版本全部核验后保存received_candidate_unreviewed ACK。未完成保持pending/失败，不能返回成功。

## 验收和恢复

1. 真实AWS下载与模块/配置/源码版本回执。
2. 受控截断副本应在到达日志和共享候选写入前拒绝，完整原包重试成功。
3. 原包重放零新原件、来源或候选，首次接收与完成时间不变。
4. 投影部分失败保留到达时间，完整重试补齐；缺失投影可恢复，已存字节损坏保留异常而不覆盖。
5. 校验正式projects/datacenter_model/object_observations/prices/site_model_bridges数据前后SHA相同，Reader入队/采用/填参0。

不安装周期调度或新HTTP入口。单一HTML来源不证明SEC/XBRL、全部财报、附件、所有企业及所有目标已覆盖。fetchreports/fetchquotes保持未接通。

## 实际生产回执

fetchfilings已用Microsoft官方FY2025年报完成AWS真实采集、Spark永久候选接收、受控截断拒绝/完整重试与同包零增量重放；旧ID、版本、原信封和首次接收保留。仅Microsoft年度现金PP&E单源受控文件交付，未启用调度；候选不入Reader、不采用、不填参；fetchreports/fetchquotes仍未接通。

首次生产接收：2026-10-14T15:03:23.556746+00:00；接收器版本：4ee6c353259b334652de38d00a68fd9f9970d0b0。1来源/1版本/1未审核候选，正式5文件SHA不变。共享字节此前是否存在：False，不把共享SHA重复算独立证据。

私有完整证据：/Users/m5/.local/share/inresearch.ai/fetchfilings-production-20261014/spark-audit/。生产失败副本及旧原件保留在Spark，不提交Git。
