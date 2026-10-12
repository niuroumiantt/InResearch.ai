# 存量园区基础信息扩批（2026-10-12）

本批接续 `initial-physical-site-intake-20261012.md`，上一批7园区不重复计数。使用既有目标无关的局部证据入口，逐条审核13份归档HTML，登记13个园区、13条站点观测、39个采用字段（名称、报道阶段、备注）。原133条园区记录逐值保持不变；对象观测545条/152对象不变，不能把园区观测混入这个账本计数。

地址和行政区有依据则登记，缺失保留空。QGroup House的4月29日是转述帖文日期，未当作揭幕确切日；披露日2026-05-05独立保存。全部13条事件日期未明确，不以披露日替代。首次接收来自Spark真实目录记录。容量不是首次身份登记前提；正文数字的不同口径、上下限、其他站点与企业总量在备注区分，未增加任何IT容量汇总。Almaden报道同时称已收购/可能年底交割，冲突保留，未认定产权已转移；计划上线日期不认定为已投运。

## 本批对象与来源

- `us-va-tysons-vienna-cloud-quantum`：[Serverfarm Vienna Cloud 园区](https://www.datacenterdynamics.com/en/news/serverfarm-enters-virginia-targets-data-center-in-tysons-corner/)，披露 2026-02-04。
- `gb-london-hounslow-heathrow-estate`：[Haslemere Heathrow Estate 园区](https://www.datacenterdynamics.com/en/news/data-center-spanning-up-to-50000-sqm-gets-approval-for-construction-in-west-london-the-uk/)，披露 2026-08-14。
- `in-west-bengal-kolkata-new-town-ctrls`：[CtrlS Kolkata New Town 园区](https://www.datacenterdynamics.com/en/news/indias-ctrls-datacenters-to-build-data-center-campus-in-kolkata/)，披露 2024-06-28。
- `kr-dangjin-nfd-campus`：[NFD Korea Dangjin 园区](https://www.datacenterdynamics.com/en/news/data-center-company-nfd-korea-to-build-300mw-campus-south-of-seoul/)，披露 2026-06-16。
- `gb-scotland-chapelcross-cx-technology`：[CX Technology Campus Chapelcross 园区](https://www.datacenterdynamics.com/en/news/plans-filed-for-1gw-data-center-campus-at-former-nuclear-plant-in-scotland/)，披露 2026-10-02。
- `se-skelleftea-finnfors-kraft-ndc`：[Skellefteå Kraft Finnfors 园区](https://www.datacenterdynamics.com/en/news/swedish-utility-plans-120mw-wholesale-colo-campus-northern-sweden/)，披露 2019-04-01。
- `pk-sindh-al-nahal-it-park-xds`：[Al Nahal IT Park XDS 园区](https://www.datacenterdynamics.com/en/news/xds-to-build-liquid-cooled-data-center-at-pakistan-tech-park/)，披露 2025-10-17。
- `fi-hanko-eastern-industrial-tloop`：[T.Loop Hanko Eastern Industrial Area 园区](https://www.datacenterdynamics.com/en/news/tloop-looks-to-develop-data-center-in-hanko-finland/)，披露 2026-05-06。
- `au-victoria-moorabool-hyperdc-mbl1`：[HyperDC MBL1 Moorabool 园区](https://www.datacenterdynamics.com/en/news/plans-filed-for-400mw-data-center-campus-outside-melbourne-australia/)，披露 2026-09-29。
- `us-ga-lovejoy-stillwater-panhandle`：[Stillwater Technology Park Lovejoy 园区](https://www.datacenterdynamics.com/en/news/gigawatt-scale-data-center-campus-planned-outside-atlanta-georgia/)，披露 2026-07-27。
- `gm-kairaba-avenue-qgroup-house`：[QGroup House Kairaba Avenue 园区](https://www.datacenterdynamics.com/en/news/qgroup-launches-data-center-in-the-gambia-claims-it-is-the-countrys-first/)，披露 2026-05-05。
- `us-ca-san-jose-almaden-650-harry`：[Almaden Research Center 650 Harry Road 园区](https://www.datacenterdynamics.com/en/news/former-ibm-research-campus-in-silicon-valley-set-to-be-acquired-by-data-center-firm/)，披露 2026-10-05。
- `gb-scotland-fife-auchtertool-cato`：[ILI Cato Auchtertool 园区](https://www.datacenterdynamics.com/en/news/ili-files-to-develop-600mw-stoic-data-center-in-fife-scotland/)，披露 2026-06-03。

## 实际验收与接续

具名提案、原件SHA/原生引文、隔离写入及无写重放回执位于M5与Spark的私有状态目录 `~/.local/state/inresearch.ai/stock-sites-next-20261012/`。首次接收、披露、有效时间独立保存；本批不要求整篇Reader完成或模型需求绑定。原件不删除，不修改Reader队列。

提交前运行治理、严格校验、registry、固定研究回归与industry/research浏览器。本批还修复industry历史样例从有限首页窗口消失后的验收缺陷，并拆分technical_atlas/chip_package重型作业，因此本批按全套CI验收。后续纯资料CI必须通过精确base/head完整JSON差异证明，旧记录或规范改动仍走全套。实际CI、镜像、公开API、首页与Spark重放以私有acceptance.json最终回执为准，本文不冒充上线证明。

发布时先完成已有PR840实际网站回执，再接纳本批；只暂停原协调器新接纳，不启动另一个发布器。网站/Spark实际验收后移除本批拥有的stop-coordinator并恢复同一LaunchAgent。尚未采用的容量独立字段、角色、未唯一定位线索继续后补；171来源和17模型输入不得据本批记为闭环。
