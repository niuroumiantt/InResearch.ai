# fetchreports：LBNL发布页单源受控接收

当前范围为fetchreports-lbnl-bootstrap／DOI:10.71468/P1WC7Q:2024，官方发布页HTML与方法摘要候选。HTML completeness=complete只表示这份网页取得完整，不表示整份PDF已取得/读完。PDF正文、表图、计算数据和附件未读，不冒充缺失或已验。

AWS用已固定干净fetchdata提交实际下载，旧两版包先保存在history-root/deliveries；相同SHA返回原信封，实际取得另记acquisitions.jsonl。不同SHA另留版本，不自动覆盖。Spark用同一生产接收器的provider独立锁、到达日志和ACK，精确白名单在supply_contract登记。

```sh
python3 fetchdata.py run --team fetchreports --history-root /绝对路径/旧队数据根
python3 manage.py collector-receive /绝对路径/完整包 --data-root /现有私有数据根 --expected-receiver-revision <实际已部署40位提交>
```

先冻结/验包/持久原件与候选，再核共享catalog/blobs/originals后ACK。半包拒绝，完整重试；同包重放零新增、首收/完成时钟不变。部分归档中断不ACK，保留到达后恢复；已存字节异常不覆盖。

候选study.method是来源自己的全国历史用电估算方法，不是园区实测或模型参数。对象匹配和有效时间未知继续保留；发布日期2024-12-19不能充作有效时点。正文/摘要/附件、来源估算/自有推导、同链/独立证据分开。不自动入Reader、采用或填参；不安装调度，不启用fetchquotes。

当前connection保持not_connected；真实AWS下载、Spark ACK、受控截断恢复、重复及正式数据SHA守恒另验，完成后再登记接通。
