# 产品制造商归属修正（2026-10-07）

用户指出 Supermicro 企业窗口混入 Kioxia、Samsung。官网 `products/storage/pci-e/` 页面明确分开 SMCI P/N、Manufacturer P/N 和 Description；`products/nvme/vroc` 是兼容表。来源在 Supermicro 官网、使用SMCI料号或经过认证，不取得Supermicro自有产品身份。同一边界涵盖 Intel、HGST、Micron 和支持路径中的其他厂商。

Fetchspec 与本仓库使用相同的 `2026-10-07.1` 路径判定。新交付拒绝明确误归属，已接收条目在只读投影中排除：首页计数/代表型号、产品索引、分类搜索、详情、系列、CSV及文档型号链接使用同一判定。原表里的CPU/GPU/SSD/内存品牌不改变整机归属。既有SQLite、原件、来源版本均保留；重跑historical_supplement不能删除旧条目，所以本修正同时覆盖接收端读取。

只读全公司审计读取当前批次的ID、标题、来源和产品URL、源SHA，不读取规格单元格或私人路径。已核对的支持路径和显式公司ID冲突列为conflict；标题开头的异厂品牌列为review_required，不自动重新归属。未命中不是身份验证通过；无数据库明确available=false，全部为空则ok=false并退出失败。

本地已审阅Fetchspec两批保存记录：16家公司、169条目，19个公司/批次记录，已知规则未命中。16家为 AMD、Ampere、壁仞、寒武纪、昇腾、鲲鹏、海光、天数智芯、Intel、龙芯、沐曦、摩尔线程、飞腾、SK hynix、Supermicro、兆芯。该审计包含历史批次重叠，不能当作当前线上型号总数；其他公司实际生产目录及本次线上排除数量尚未取得。原件不在当前云环境，不能从夹具推定全量无错。

回归以真实接收器创建隔离库，再模拟旧策略已接收支持页，检查所有投影与CSV共用五款合法服务器，原库和版本字节不变、只读审计仍找到旧误归属。新支持页交付拒绝、整机部件品牌保留、其他公司审查候选和全空失败分别测试。

**[m5 → AWS]** 合并并由现有部署服务发布后，在m5执行只读审计：

```bash
ssh inews 'sudo docker exec -w /app -e PYTHONPATH=/app/src inresearch-host-inresearch-1 python3 -m inresearch.workflow.catalog_ownership_audit --root /app'
```

此命令不写生产库。保存实际JSON回执并逐条核对review_required；另验status/applied和公司首页、分类、索引计数及资料搜索。本地测试与PR不代表已上线；当前云环境无该SSH连接及生产库。

本轮本地验收：完整1843项单元测试通过；相关55项通过；governance、validate --strict（0 warnings）与registry通过；company_catalog_map、company_window、catalog_materials、product_catalog、compute_catalog、company_page六组浏览器回归通过。浏览器采用当前环境`/usr/bin/chromium`（151），测试进程通过Git外的Playwright启动适配读取该可执行文件，仓库测试及应用源码未修改浏览器选择。Fetchspec239项测试及跨仓库历史增补5项通过，双方判定文件逐字一致。真实线上全量复核与发布仍待生产回执。
