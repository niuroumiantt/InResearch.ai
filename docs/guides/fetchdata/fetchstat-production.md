# fetchstat生产接通：受控文件交付

当前阶段只接通已登记EIA Texas工业YTD电价来源。
AWS负责实际取得原件；Spark使用既有acquisition候选台账和originals永久归档。
其他三模块不启用；不安装采集日历、不开放新的HTTP端口、不自动进入Reader或研究采用。

源码以完整已测试Git提交部署；本轮fetchdata使用私有Git包在既有AWS/Spark留存。
公开新仓库创建未获自动审批，因此不公开源码。四个旧仓库和全部旧交付保持。
源码追溯以bundle SHA、Git提交、模块和配置SHA为准，不以缺失的GitHub URL冒充来源。

**[AWS，经已有SSH别名执行]**
```sh
ssh aws 'cd ~/code/fetchdata && python3 fetchdata.py check-config --team fetchstat'
ssh aws 'cd ~/code/fetchdata && python3 fetchdata.py run --team fetchstat --history-root ~/.local/share/fetchdata/fetchstat'
```

独立运行生成的package路径用于后续文件传输。旧包命中原样返回旧信封；每次实际采集仍记录当前代码版本、取得时间和字节SHA。
新原件/新版本另存，不假设来源更新或“最新”等于可覆盖旧值；EIA工业YTD均价不自动变成园区合同电价。

**[Spark，核对生产接收入口]**
```sh
ssh spark 'cd ~/code/inresearch.ai && python3 manage.py collector-receive --help'
```

接收必须明确现有data-root。只允许framework/supply_contract.json登记的fetchstat来源身份、原生ID和URL。
SSH传输先到incoming临时目录，核对完整包后再调用接收器；不能把半包放进raw-materials。
既有原件保留在原址，生产副本与到达记录分别保存；本地沙箱首次接收不倒推到生产。

## 回执及恢复

1. 到达日志保留原包、旧ID和首次有效到达时间，状态candidate_archive_pending。
2. 原生字节入共享acquisition/catalog.sqlite及blobs，另建originals永久投影；候选及证据仍在独立不可变包/候选日志。
3. 完整核验来源版本与投影后才保存received_candidate_unreviewed ACK；未完成不会报成功。
4. 同包重放核对原归档、ACK和共享台账，零新候选、零新原件、首次接收及完成时间不变。
5. 部分入库失败保留到达日志与失败run；原包重试补齐，源身份和观测不重复。缺失投影可从已核原包恢复；已存字节损坏保持异常，不覆盖。

生产目录：~/.local/share/inresearch.ai/acquisition/collectors/fetchstat/，其中receipts.sqlite3分别保存到达日志与production_acks。
共享原件使用既有blobs/originals规则，不把候选直接追加到正式data/*.json。
现场检查须分别记录真实采集、传输失败、接收ACK、重放前后计数、来源/代码版本及实际恢复过程。
受控故障副本只检验传输/接收恢复，不当作真实来源新版本或采用证据。

本阶段不证明更多统计源/税率/水价已采集，不证明26个父目标、3个参数需求已解决；其他队继续not_connected。
