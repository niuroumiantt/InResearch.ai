# fetchreports：LBNL发布页单源受控接收

当前范围为fetchreports-lbnl-bootstrap／DOI:10.71468/P1WC7Q:2024，官方发布页HTML与方法摘要候选。HTML completeness=complete只表示这份网页取得完整，不表示整份PDF已取得/读完。PDF正文、表图、计算数据和附件未读，不冒充缺失或已验。

AWS用已固定干净fetchdata提交实际下载，旧两版包先保存在history-root/deliveries；相同SHA返回原信封，实际取得另记acquisitions.jsonl。不同SHA另留版本，不自动覆盖。Spark用同一生产接收器的provider独立锁、到达日志和ACK，精确白名单在supply_contract登记。

```sh
python3 fetchdata.py run --team fetchreports --history-root /绝对路径/旧队数据根
python3 manage.py collector-receive /绝对路径/完整包 --data-root /现有私有数据根 --expected-receiver-revision <实际已部署40位提交>
```

先冻结/验包/持久原件与候选，再核共享catalog/blobs/originals后ACK。半包拒绝，完整重试；同包重放零新增、首收/完成时钟不变。部分归档中断不ACK，保留到达后恢复；已存字节异常不覆盖。

候选study.method是来源自己的全国历史用电估算方法，不是园区实测或模型参数。对象匹配和有效时间未知继续保留；发布日期2024-12-19不能充作有效时点。正文/摘要/附件、来源估算/自有推导、同链/独立证据分开。不自动入Reader、采用或填参；不安装调度，不启用fetchquotes。

当前connection为receiver_live_file_import，仅以上发布页摘要单源；真实首包、历史版本和重复回执已核验。

## 实际生产回执

fetchreports已验LBNL官方发布页/方法摘要单源AWS真实采集、Spark永久候选接收、截断拒绝/完整重试及重复零增量；三个旧版与本次新版并存，不多计独立证据。PDF正文/表图/附件未读，信息有效时间未知；不入Reader、不采用、不填参，不安装调度；fetchquotes仍未接通。

首次接收2026-10-14T15:59:27.218135+00:00；接收器94ac5cd9f25cd2a2049bec53282967b352809226。共享来源/版本：{'new_source_series': 1, 'new_versions': 4, 'receiver': {'deliveries': 4, 'items': 4, 'observations': 4, 'production_acks': 4}}。完整私有回执/Users/m5/.local/share/inresearch.ai/fetchreports-production-20261014/spark-audit，原件和失败副本不进Git。最终网站/架构/源码版本以私有release-status.json为准。
