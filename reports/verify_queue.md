# 核验队列

生成时间：2026-08-15 ｜ P1（必须处理）9 条 ｜ P2（补强来源）28 条

流程：打开来源链接核对 → 有变化改数据+来源，无变化只改 verified_date → `python3 pipeline/validate.py`

## P1

- [ ] **prices / dc-rent-index-na@2026-06-30** — 价格点已 46 天未更新（阈值 30）
      动作：抓取/查询最新值，新增一条 as_of 记录
      来源：https://www.jll.com/en-us/insights/market-dynamics/north-america-data-centers
- [ ] **prices / transformer-lead-time@2026-06-30** — 价格点已 46 天未更新（阈值 30）
      动作：抓取/查询最新值，新增一条 as_of 记录
      来源：https://www.woodmac.com/
- [ ] **prices / vacancy-rate-na@2026-06-30** — 价格点已 46 天未更新（阈值 30）
      动作：抓取/查询最新值，新增一条 as_of 记录
      来源：https://www.jll.com/en-us/newsroom/data-center-availability-crisis-deepens-as-vacancy-hits-historic-low
- [ ] **research / M02-F7** — 标记 needs-review（Neocloud 把电力、芯片、网络、软件和资本组合成可用算…）
      动作：复核证据后改回 current 或修订结论（M02.md）
- [ ] **research / M02-F8** — 标记 needs-review（Neocloud 是 Hyperscaler 的弹性层而非简…）
      动作：复核证据后改回 current 或修订结论（M02.md）
- [ ] **research / M02-F9** — 标记 needs-review（公开信息不足以算出四大厂统一的"自用/出租 MW 比例"，可…）
      动作：复核证据后改回 current 或修订结论（M02.md）
- [ ] **research / M03-F2** — 标记 needs-review（Anthropic 以 AWS 为主云与训练基础，Googl…）
      动作：复核证据后改回 current 或修订结论（M03.md）
- [ ] **research / M04-F2** — 标记 needs-review（核电分"现役共址/重启/SMR"三条时间表：重启本十年可供数…）
      动作：复核证据后改回 current 或修订结论（M04.md）
- [ ] **research / M15-F7** — 标记 needs-review（单指标会被宣传误导：三色判断要求至少三个同向信号，资本指标识…）
      动作：复核证据后改回 current 或修订结论（M15.md）

## P2

- [ ] **contracts / openai-oracle-2025** — media 级来源
      动作：用财报 RPO/监管文件交叉验证金额与期限
      来源：https://www.wsj.com/
- [ ] **prices / gpu-hourly-h100-spot@2026-07-31** — estimate 级（带假设推算）
      动作：寻找可替代的一手/研究级来源
      来源：https://cloud-gpus.com/
- [ ] **prices / transformer-lead-time@2026-06-30** — estimate 级（带假设推算）
      动作：寻找可替代的一手/研究级来源
      来源：https://www.woodmac.com/
- [ ] **projects / cn-gz-guian-tencent** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.scmp.com/tech/enterprises/article/2144088/tencent-builds-giant-bomb-shelter-remote-chinese-province-house
      来源：http://www.idcnova.com/html/1/59/153/702.html
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
- [ ] **projects / mx-queretaro-aws** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://press.aboutamazon.com/2025/1/aws-launches-infrastructure-region-in-mexico
      来源：https://www.datacenterdynamics.com/en/news/aws-plans-5bn-mexican-cloud-region-for-2025/
- [ ] **projects / us-az-el-mirage** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.aztechcouncil.org/microsoft-buys-land-el-mirage-data-center/
      来源：https://www.areadevelopment.com/newsItems/8-1-2019/microsoft-data-centes-el-mirage-goodyear-arizona.shtml
- [ ] **projects / us-az-goodyear** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.datacenterdynamics.com/en/news/microsoft-purchases-100-acres-next-to-existing-data-center-campus-in-goodyear-arizona/
      来源：https://www.blackridgeresearch.com/project-profiles/microsoft-goodyear-data-center-arizona-az-project-location-cost-storage-capacity-current-status-details
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
- [ ] **projects / us-oh-columbus-aws** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.datacenterdynamics.com/en/news/amazon-plans-five-building-data-center-campus-in-new-albany-ohio/
      来源：https://www.datacenterfrontier.com/site-selection/article/33011941/aws-readies-35b-for-5-more-ohio-data-centers-in-booming-columbus-suburb-new-albany
- [ ] **projects / us-or-boardman-aws** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.datacenterdynamics.com/en/news/aws-planning-at-least-four-more-data-centers-in-morrow-county-oregon/
      来源：https://www.opb.org/news/article/npr-amazon-to-expand-data-centers-in-northeastern-oregon-reaping-more-tax-breaks/
- [ ] **projects / us-pa-salem-township-aws** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.datacenterdynamics.com/en/news/aws-acquires-talens-nuclear-data-center-campus-in-pennsylvania/
      来源：https://www.utilitydive.com/news/talen-amazon-aws-susquehanna-nuclear-data-centert/750440/
- [ ] **projects / us-tx-castroville** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.datacenterdynamics.com/en/news/microsoft-files-to-build-two-more-data-centers-in-san-antonio-texas/
      来源：https://www.blackridgeresearch.com/project-profiles/microsoft-castroville-campus-data-center-san-antonio-texas-location-cost-investment-latest-news-updates
- [ ] **projects / us-tx-milam** — 单一来源且非一手
      动作：交叉验证，补第二来源
      来源：https://epoch.ai/publications/openai-stargate-where-the-us-sites-stand
- [ ] **projects / us-va-ashburn-aws** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.datacenterfrontier.com/cloud/article/11427911/aws-has-spent-35-billion-on-its-northern-virginia-data-centers
      来源：https://dgtlinfra.com/data-centers-virginia-ashburn-loudoun/
- [ ] **projects / us-va-boydton** — 仅有低级别来源（media）
      动作：补一手来源（公司披露/监管文件）
      来源：https://www.datacenterdynamics.com/en/news/microsoft-to-add-21mw-at-virginia-data-center-site/
      来源：https://www.datacenterknowledge.com/hyperscalers/microsoft-s-1-billion-data-center
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

