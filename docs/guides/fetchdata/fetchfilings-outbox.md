# fetchfilings AWS待交付与Spark ACK

## 范围

仅既有Microsoft FY2025官方年报年度现金PP&E单源，不扩SEC/XBRL/其他公司或附件。原provider/native/item/observation/delivery ID、collector_revision、原信封、来源版本与交付历史保持。负数现金支出、集团/财年口径、未知披露时间保留；不能分配为某园区资本成本或模型参数。scheduled=false，不安装调度、不入Reader、不采用、不填参。新通道代码准备与真实回执独立；真实验收以私有结果为准。

## 独立身份与固定版本

两队共用有上限的字节传输及只读完成ACK核验，但每个专用公钥固定一个命令、一个provider、一个协议。fetchfilings仅允许fetchfilings-gateway-v1 / fetchfilings-ssh-gateway/1，入口scripts/filings_gateway.py；即使请求改成fetchstat也拒绝。原stat入口、协议、队列与旧ACK不变，reports按独立指南接通；本指南不操作reports，quotes生产队列未启用。

AWS只留本队专用私钥；Spark公钥限定AWS精确Tailscale IP、restrict、100秒timeout与固定脚本。主机ed25519公钥由既有可信连接核对，不关闭host-key校验。只走已批准的AWS→Spark TCP22，不增加公网监听或广泛shell权限。

Spark网关放在~/.worktrees/inresearch.ai/collector-fetchfilings-<提交前缀>的独立固定Git检出中（路径为部署约定，非可直接执行的命令）。只读源码干净且HEAD精确匹配请求receiver_revision。既有主检出与Reader/review服务继续自己的版本，不因主站发布改变网关HEAD；不重启它们。fetchstat已验3c0d2834也固定在对应运行检出，专用公钥仅更换固定脚本路径，旧目标配置/绑定不改。每次升级另核版本与当前队列，不能静默改绑定或删库。

## 手动交付

AWS正常生产队列使用~/.local/share/fetchdata/fetchfilings/outbox；作业/发送意图/尝试/事件在~/.local/state/fetchdata/fetchfilings/operations。生产配置在本队ssh私有目录，不能复制到Git或审计包。配置仅host/user/identity_file/known_hosts/receiver_revision，与stat分开。

**[AWS，统一源码目录]**
```sh
cd /home/ubuntu/code/fetchdata
python3 fetchdata.py enqueue --team fetchfilings /home/ubuntu/.local/share/fetchdata/fetchfilings/deliveries/fetchfilings-564154a15ac28c0f7f72f304-v1
python3 fetchdata.py dispatch --team fetchfilings --production-config /home/ubuntu/.local/state/fetchdata/fetchfilings/ssh/production.json
python3 fetchdata.py reconcile --team fetchfilings --production-config /home/ubuntu/.local/state/fetchdata/fetchfilings/ssh/production.json
python3 fetchdata.py status --team fetchfilings
```

命令退出0不等于交付成功，须queue=confirmed并核持久collector-production-receipt/1。发送返回也需另查归档；查完成ACK、冻结包、来源/候选/原件台账与共享投影，不把pending到达当完成，不刷新原时钟。ACK未知先查，已收只确认，确实未收才同包预算内重试；查询错误不算未收。坏包/权限/身份冲突保留，不靠覆盖修源。

## 验收

先记录两端源码、旧包/来源配置/正式五文件SHA及原ACK；真实交付与两次重放核零新增，已确认队列再执行不重发；隔离故障台账实际接收后丢弃ACK、os._exit(74)和真实SSH受控连接失败，再用新AWS进程只读对账。故障不修改永久库或旧包，不伪造新ID。旧包已有ACK时恢复走已收确认，不能把这说成生产“未收后重试”；后者需要另有真实未收包。独立故障台账不多计资料或独立证据。

同scope真实回执、旧时钟/摘要守恒、原服务状态及stat回归另存~/.local/share/inresearch.ai/fetchfilings-outbox-20261016。日志/操作库在对应state目录；运行材料/数据库/密钥不入Git，不复制ssh私钥到本地备份。未验长期无人值守、硬件断电/灾难恢复、其他来源或采集队。
