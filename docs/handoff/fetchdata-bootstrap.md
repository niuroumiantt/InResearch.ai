# 四个独立采集仓库启动入口

现行员工包见[四队启动包](../guides/fetchdata/README.md)，现行规范见[06](../../framework/06_acquisition.md)。用户已将一个fetchdata四目录方案替换为fetchstat、fetchfilings、fetchreports、fetchquotes四个独立仓库。各仓库已实际采集一条来源、保存原件、提取一条候选并通过离线校验及重放；生产接收与定时运行待联调。合同名fetchdata-handoff/1保留兼容，不能冒充Fetchspec。

原件按原格式、候选JSONL；目标可空、缺项后补、冲突保留、身份不明留线索。接收、采用、上线分别计量；不能把建仓库当171项需求已完成。旧设计由Git历史保留，不恢复退役SEC/GPU服务。
