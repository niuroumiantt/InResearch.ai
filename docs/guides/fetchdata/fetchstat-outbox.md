# fetchstat AWS待交付与Spark ACK

## 范围与现状

本轮只把已登记EIA单源接到持久队列；其它三队仍沿用受控文件接收。源配置scheduled=false不变，不安装定时、不扩来源、不入Reader、不采用、不填参。新传输代码/单元测试与实际生产接通分开验收；真实回执尚待AWS→Spark TCP22网络准入、专用身份及受保护版本部署。

四队本地作业验收见local-operations.md；不能把本地collector-local-receipt当生产ACK。本次复用fetchstat-2d71d12585023e9506bf0bba-v1完整旧包，保留其collector_revision、原信封、来源版本与首次生产接收时间。重放新增0并不等于未交付；它验证旧身份的持久接收与队列确认。

## 传输与权限

AWS通过Tailscale访问Spark的SSH，不开放公网监听。AWS持有新的fetchstat专用密钥；Spark authorized_keys须同时限定AWS精确IP、restrict及固定命令：

```text
from="100.103.118.69",restrict,command="/usr/bin/timeout 100 /usr/bin/python3 /home/spark/code/inresearch.ai/scripts/collector_gateway.py" <专用公钥>
```

不复制现有管理员私钥，不授予交互shell、转发或任意scp。服务端只接受SSH_ORIGINAL_COMMAND=fetchstat-gateway-v1，协议fetchstat-ssh-gateway/1。请求仅含固定操作、fetchstat身份、旧交付ID、部署版本及有上限的文件字节；不能指定服务端命令、磁盘路径或数据库。来源仍按supply_contract白名单验证。源码必须干净且与请求版本完全一致。

AWS私有配置含host=100.100.1.2、user=spark、identity_file、known_hosts及receiver_revision；known_hosts固定一条经M5既有可信连接核对的Spark ed25519公钥。不得用StrictHostKeyChecking=no或盲信ssh-keyscan。私钥/主机身份配置与运行台账不进Git。

## 持久交付与核验

AWS冻结原包到~/.local/share/fetchdata/fetchstat/outbox，作业/事件/尝试存~/.local/state/fetchdata/fetchstat。新作业键与原交付ID分离，发送意图先入账；同一队列绑定目的地/主机公钥/接收版本，不能静默换成本地沙箱或另一接收器。源码升级后更换接收版本必须显式复核队列绑定，保留原台账，不删库强行重绑。

```sh
PYTHONPATH=src python3 -m fetchdata enqueue --team fetchstat /旧包绝对路径
PYTHONPATH=src python3 -m fetchdata dispatch --team fetchstat --production-config /私有配置绝对路径
PYTHONPATH=src python3 -m fetchdata reconcile --team fetchstat --production-config /私有配置绝对路径
PYTHONPATH=src python3 -m fetchdata status --team fetchstat
```

CLI退出0仅代表命令完成；必须查queue.state=confirmed及持久生产ACK。生产ACK须为collector-production-receipt/1、candidate_unreviewed权限、相同旧ID/整包指纹/源码版本/候选数量，并保留原首次接收与归档完成时间。正常发送也需另一次只读查询核实，不能只凭返回JSON确认。

Spark只读查询在既有provider外层锁下核生产ACK、到达日志、不可变归档、候选/来源/原件台账和共享catalog/blob/original投影。pending到达不是完成ACK；缺失投影/损坏/身份冲突不确认且不修复。不存在返回found=false，错误不能当不存在。读取不刷新时钟、初始化库、入Reader或改模型。

## 验收顺序

1. 记录双方干净源码、来源配置SHA、旧包所有文件SHA、原生产ACK和正式数据SHA。
2. AWS单次手动入队，经专用SSH向Spark真实交付；只读核验后确认，重放零增量。
3. 独立验收台账复用同一旧包，实际接收后丢弃返回ACK或退出发送进程；另一个AWS进程查询原ACK确认，发送次数保持1。
4. 独立台账在发送前受控阻断连接；保留失败事件，恢复后先查ACK，未收才同包重试。已有旧包若查到历史ACK则直接确认，不伪称发生新入库。损坏副本独立保留，不损坏永久归档以制造事故。
5. 核对旧ID、原来源字节、原首次接收/归档完成、候选增量、Reader/采用/模型0、无调度及其它队未切换新通道。

网络ACL、专用身份、源码上线和真实ACK均须实机回执；单元测试不证明已完成生产接通，也不证明长期无人值守或硬件断电恢复。
