# 核验队列

生成时间：2026-09-14 ｜ P1（必须处理）23 条 ｜ P2（补强来源）24 条

流程：打开来源链接核对 → 有变化改数据+来源，无变化只改 verified_date → `python3 manage.py validate`

## P1

- [ ] **research / M02-F10** — 标记 needs-review（GPU 机架 130kW 但行平均只有 62kW——AI 机…）
      动作：复核证据后改回 current 或修订结论（M02.md）
- [ ] **research / M06-F1** — 标记 needs-review（GB200/GB300 NVL72 是当前可采购代际，比较单…）
      动作：复核证据后改回 current 或修订结论（M06.md）
- [ ] **research / M06-F11** — 标记 needs-review（B300 以牺牲 FP64 换 FP4/FP6：数据中心 G…）
      动作：复核证据后改回 current 或修订结论（M06.md）
- [ ] **research / M06-F2** — 标记 needs-review（AMD 已从单卡竞争转向 Helios 机架级开放方案；Me…）
      动作：复核证据后改回 current 或修订结论（M06.md）
- [ ] **research / M06-F3** — 标记 needs-review（云内 ASIC 与定制芯片分流稳定大批量负载，但不构成对 N…）
      动作：复核证据后改回 current 或修订结论（M06.md）
- [ ] **research / M06-F4** — 标记 needs-review（机柜功率从 5–10kW 跃升到 130kW 级，来自"单芯…）
      动作：复核证据后改回 current 或修订结论（M06.md）
- [ ] **research / M06-F5** — 标记 needs-review（电流是低压配电的物理瓶颈，800VDC 的动因是降电流；高密…）
      动作：复核证据后改回 current 或修订结论（M06.md）
- [ ] **research / M06-F6** — 标记 needs-review（处理器市场三年翻倍超 $350B：GPU 2028 见顶 $…）
      动作：复核证据后改回 current 或修订结论（M06.md）
- [ ] **research / M06-F7** — 标记 needs-review（HBM 已成 DRAM 增长引擎：2024 $17.4B(+…）
      动作：复核证据后改回 current 或修订结论（M06.md）
- [ ] **research / M06-F8** — 标记 needs-review（HBM 挤出效应有硬数据了：占 DRAM 营收 19%→33…）
      动作：复核证据后改回 current 或修订结论（M06.md）
- [ ] **research / M06-F9** — 标记 needs-review（MI300X 五个月实测：纸面规格全面领先、实测训练吞吐仍输…）
      动作：复核证据后改回 current 或修订结论（M06.md）
- [ ] **research / M07-F1** — 标记 needs-review（AI 集群网络不会单一"通吃"：NVLink 管 scale…）
      动作：复核证据后改回 current 或修订结论（M07.md）
- [ ] **research / M07-F3** — 标记 needs-review（网络与 800VDC 供电最终在"每个 token 的设施成…）
      动作：复核证据后改回 current 或修订结论（M07.md）
- [ ] **research / M07-F5** — 标记 needs-review（CPO 从技术选项变成市场主线：scale-out/scal…）
      动作：复核证据后改回 current 或修订结论（M07.md）
- [ ] **research / M07-F6** — 标记 needs-review（UALink 1.0 落地：scale-up 域出现 NVL…）
      动作：复核证据后改回 current 或修订结论（M07.md）
- [ ] **research / M08-F1** — 标记 needs-review（混合冷却是 AI 机柜的实际常态，路径选择由机柜功率分布决定…）
      动作：复核证据后改回 current 或修订结论（M08.md）
- [ ] **research / M08-F6** — 标记 needs-review（GB200 NVL72 捐入 OCP：整机柜液冷从定制工程变…）
      动作：复核证据后改回 current 或修订结论（M08.md）
- [ ] **research / M08-F7** — 标记 needs-review（液冷的真实驱动力是 scale-up 域的 TCO，不是能效…）
      动作：复核证据后改回 current 或修订结论（M08.md）
- [ ] **research / M09-F9** — 标记 needs-review（机架功率 250kW→500kW→1MW，且能效改进跑不赢规…）
      动作：复核证据后改回 current 或修订结论（M09.md）
- [ ] **research / M11-F3** — 标记 needs-review（循环交易已成体系：芯片商投资客户→客户买芯片→计为需求，NV…）
      动作：复核证据后改回 current 或修订结论（M11.md）
- [ ] **research / M13-F4** — 标记 needs-review（算力租价由「每有效 PFLOP 小时成本」与「每百万 tok…）
      动作：复核证据后改回 current 或修订结论（M13.md）
- [ ] **research / M13-F6** — 标记 needs-review（B200 在典型 AI 负载下利用率不足 10%，瓶颈是内存…）
      动作：复核证据后改回 current 或修订结论（M13.md）
- [ ] **research / M15-F2** — 标记 needs-review（GPU 瓶颈没有消失而是变为"代际组合能否兑现"；施工与融资…）
      动作：复核证据后改回 current 或修订结论（M15.md）

## P2

- [ ] **contracts / openai-oracle-2025** — media 级来源
      动作：用财报 RPO/监管文件交叉验证金额与期限
      来源：https://www.wsj.com/
- [ ] **prices / transformer-lead-time@2026-06-30** — 序列最新点为 estimate 级（带假设推算）
      动作：寻找可替代的一手/研究级来源
      来源：https://www.woodmac.com/
- [ ] **projects / cn-gz-guian-tencent** — 仅有低级别来源（estimate/media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.scmp.com/tech/enterprises/article/2144088/tencent-builds-giant-bomb-shelter-remote-chinese-province-house
      来源：http://www.idcnova.com/html/1/59/153/702.html
      来源：https://baike.baidu.com/item/%E8%85%BE%E8%AE%AF%E8%B4%B5%E5%AE%89%E4%B8%83%E6%98%9F%E6%95%B0%E6%8D%AE%E4%B8%AD%E5%BF%83/22428602
- [ ] **projects / cn-nm-ulanqab-alibaba** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://baxtel.com/data-center/alibaba-ulanqab-campus
      来源：http://www.idcnova.com/html/1/59/69/687.html
- [ ] **projects / cn-sx-datong-chindata** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.jiemian.com/article/4959419.html
      来源：https://baike.baidu.com/item/%E7%A7%A6%E6%B7%AE%E6%95%B0%E6%8D%AE%E9%9B%86%E5%9B%A2%E6%8E%A7%E8%82%A1%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8/63858300
- [ ] **projects / de-frankfurt-aws** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.aboutamazon.eu/news/aws/aws-plans-to-invest-8-8-billion-in-germany-supporting-over-15-200-jobs-annually-in-local-businesses
      来源：https://www.datacenterdynamics.com/en/news/aws-to-invest-944bn-in-frankfurt-cloud-region/
- [ ] **projects / ie-dublin-aws** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.irishtimes.com/business/economy/amazon-spends-2bn-building-irish-data-centre-network-1.4474433
      来源：https://www.datacenterdynamics.com/en/news/amazon-gets-ok-for-three-new-data-centers-in-dublin/
- [ ] **projects / ie-dublin-grange-castle** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.datacentermap.com/ireland/dublin/microsoft-dublin/
      来源：https://www.datacenterdynamics.com/en/news/both-microsoft-and-edgeconnex-apply-to-build-more-data-centers-in-dublin-business-park/
- [ ] **projects / in-hyderabad-aws** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.datacenterknowledge.com/hyperscalers/amazon-commits-4-4b-in-data-center-investment-in-hyderabad-india
      来源：https://www.cio.com/article/412923/aws-launches-second-region-in-india-with-a-4-4-billion-commitment.html
- [ ] **projects / kr-haenam-firhills** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.computerweekly.com/news/366619270/South-Korea-plots-to-become-home-to-worlds-largest-AI-datacentre
      来源：https://datacentremagazine.com/articles/the-3gw-promise-south-koreas-mega-ai-data-centre-explained
      来源：https://www.datacenterdynamics.com/en/news/fir-hills-inc-claims-it-plans-to-build-3gw-35bn-ai-data-center-in-south-korea/
- [ ] **projects / mx-queretaro-aws** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://press.aboutamazon.com/2025/1/aws-launches-infrastructure-region-in-mexico
      来源：https://www.datacenterdynamics.com/en/news/aws-plans-5bn-mexican-cloud-region-for-2025/
- [ ] **projects / us-az-el-mirage** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.aztechcouncil.org/microsoft-buys-land-el-mirage-data-center/
      来源：https://www.areadevelopment.com/newsItems/8-1-2019/microsoft-data-centes-el-mirage-goodyear-arizona.shtml
- [ ] **projects / us-ga-atlanta-aws** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.aboutamazon.com/news/aws/aws-investment-georgia-ai-cloud-infrastructure
      来源：https://www.datacenterdynamics.com/en/news/aws-reveals-11bn-data-center-investment-plan-for-georgia/
- [ ] **projects / us-il-northlake** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.datacenterknowledge.com/hyperscalers/microsoft-plans-500m-illinois-data-center
      来源：https://www.datacentermap.com/usa/illinois/chicago/microsoft-northlake/
- [ ] **projects / us-mi-saline** — 单一来源且非一手
      动作：交叉验证，补第二来源
      来源：https://epoch.ai/publications/openai-stargate-where-the-us-sites-stand
- [ ] **projects / us-nm-dona-ana** — 单一来源且非一手
      动作：交叉验证，补第二来源
      来源：https://epoch.ai/publications/openai-stargate-where-the-us-sites-stand
- [ ] **projects / us-oh-columbus-aws** — 仅有低级别来源（estimate/media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.datacenterdynamics.com/en/news/amazon-plans-five-building-data-center-campus-in-new-albany-ohio/
      来源：https://www.datacenterfrontier.com/site-selection/article/33011941/aws-readies-35b-for-5-more-ohio-data-centers-in-booming-columbus-suburb-new-albany
      来源：https://baxtel.com/data-center/aws-us-east-ohio
- [ ] **projects / us-or-boardman-aws** — 仅有低级别来源（estimate/media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.datacenterdynamics.com/en/news/aws-planning-at-least-four-more-data-centers-in-morrow-county-oregon/
      来源：https://www.opb.org/news/article/npr-amazon-to-expand-data-centers-in-northeastern-oregon-reaping-more-tax-breaks/
      来源：https://www.umatillaelectric.com/about-us/2023-annual-report/
- [ ] **projects / us-tx-castroville** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.datacenterdynamics.com/en/news/microsoft-files-to-build-two-more-data-centers-in-san-antonio-texas/
      来源：https://www.blackridgeresearch.com/project-profiles/microsoft-castroville-campus-data-center-san-antonio-texas-location-cost-investment-latest-news-updates
- [ ] **projects / us-tx-milam** — 单一来源且非一手
      动作：交叉验证，补第二来源
      来源：https://epoch.ai/publications/openai-stargate-where-the-us-sites-stand
- [ ] **projects / us-va-ashburn-aws** — 仅有低级别来源（estimate/media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.datacenterfrontier.com/cloud/article/11427911/aws-has-spent-35-billion-on-its-northern-virginia-data-centers
      来源：https://dgtlinfra.com/data-centers-virginia-ashburn-loudoun/
      来源：https://www.datacenterfrontier.com/cloud/article/11430945/amazon-approaches-1-gigawatt-of-cloud-capacity-in-virginia
- [ ] **projects / us-va-dulles-digital** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.datacenterdynamics.com/en/news/digital-realty-submits-plans-large-dulles-data-center-campus/
      来源：https://www.datacenterfrontier.com/cloud/article/11429999/dulles-land-buy-gives-digital-realty-runway-for-data-center-expansion
- [ ] **projects / us-wa-quincy** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.datacentermap.com/usa/washington/quincy/microsoft-columbia-campus/
      来源：https://en.wikipedia.org/wiki/Columbia_Data_Center
- [ ] **projects / us-wi-port-washington** — 单一来源且非一手
      动作：交叉验证，补第二来源
      来源：https://epoch.ai/publications/openai-stargate-where-the-us-sites-stand

