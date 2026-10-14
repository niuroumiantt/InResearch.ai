# 四队员工启动包：一个仓库、四个独立模块

2026-10-14采用fetchdata单仓库四模块，替代四独立仓库分别维护公共代码。四模块本地实现已验收；fetchstat已完成EIA单源受控生产交付/接收/重放与故障恢复，未启用调度；其余三队未接通。旧仓库和全部历史保留。唯一采集规范是framework/06_acquisition.md，本页为操作入口。

| 供应方ID（不变） | 新模块 | 现有来源能力与限制 | 旧源码/历史 |
|---|---|---|---|
| fetchstat | collectors/fetchstat | EIA Texas工业YTD电价，非园区合同价 | [旧仓库](https://github.com/niuroumiantt/fetchstat) |
| fetchfilings | collectors/fetchfilings | Microsoft FY2025现金PP&E，非园区分配 | [旧仓库](https://github.com/niuroumiantt/fetchfilings) |
| fetchreports | collectors/fetchreports | LBNL发布页方法；未宣称PDF数值提取 | [旧仓库](https://github.com/niuroumiantt/fetchreports) |
| fetchquotes | collectors/fetchquotes | Lambda H100公开报价；币种代码/地区未知 | [旧仓库](https://github.com/niuroumiantt/fetchquotes) |

**[m5，本地fetchdata源码]**
```sh
cd /Users/m5/code/fetchdata
python3 fetchdata.py check-config --team fetchstat
python3 -m unittest discover -s tests -v
python3 fetchdata.py release --team fetchstat
```

run/verify/release均必须指定team，各模块独立配置和数据/状态根。run的existing+provenance只读复用原件；history-root只读查找已知旧交付，保持其版本和字节。新环境数据在~/.local/share/fetchdata/<team>，日志在~/.local/state/fetchdata/<team>；旧目录不自动搬动。固定完整测试提交+team可独立发布和回滚，本轮不安装任何调度。

公共核心管对象/来源/证据信封和技术校验；专业提取归模块，身份核实、研究采用、模型用途和正式发布归研究端。原件、运行库、凭据保持私有。未知不填零，冲突不覆盖，来源版本、原单位、范围、推导及独立时钟保留。

本地接收入口scripts/receive_collector_local.py只接明确隔离的sandbox-root，保存candidate_unreviewed回执；重复无新增，碰撞/篡改拒绝。此入口不连接正式库、网站、Spark队列或Fetchspec API。fetchstat/fetchfilings/fetchreports/fetchquotes分别已通过独立provider生产入口与真实ACK验证各一来源的受控文件接收；报告仅发布页摘要、报价仅公开标价，不表示全文覆盖/实际成交或自动调度。正式采用/模型自动填参0。

完整字段见[共同交付规范](delivery-contract.md)，验收与未覆盖见[开发与验收](implementation-and-acceptance.md)。本地源码迁移、版本与验收交接见[阶段记录](../../handoff/fetchdata-unified-local.md)。

fetchstat生产阶段见[受控交付与恢复](fetchstat-production.md)；其他三队不启用，源侧取得和研究采用分开。
