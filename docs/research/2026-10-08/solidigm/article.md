# Solidigm赴美上市背后的技术传承与资本选择

> 2026年10月8日专题研究归档；不是当期报价或投资建议，也不是当前执行指令。

2026年10月7日，彭博报道称，SK海力士旗下Solidigm据报已选定高盛与摩根士丹利，推进可能在2027年进行的美国首次公开募股。次日，《首尔经济》转述了这一消息。承销行选择意味着交易筹备可能进入更具体的阶段，但筹资规模、时间表与发行结构仍在讨论中。几乎同时，另一条资本线索也变得清晰：韩国媒体在8月报道，曾任Solidigm联席首席执行官的Kevin Noh离开SK后，在美国成立私募管理公司TechBridge，拟与Stonebridge一方筹组基金投资Solidigm。一位负责整合业务的管理者，又以潜在投资组织者的身份出现在同一家公司的资本故事里。

> 来源：Bloomberg，2026年10月7日，《SK Hynix’s Solidigm Is Said to Pick Banks for US IPO Next Year》，[首发报道](https://www.bloomberg.com/news/articles/2026-10-07/sk-hynix-s-solidigm-is-said-to-pick-banks-for-us-ipo-next-year)；《首尔经济》，Lee Tae-kyu，2026年10月8日，《SK hynix Picks Goldman, Morgan Stanley for Solidigm IPO》，[实际核阅的转述](https://en.sedaily.com/international/2026/10/08/sk-hynix-picks-goldman-morgan-stanley-for-solidigm-ipo)。Signal／《首尔经济》，李忠熙（이충희），2026年8月21日16:45:51韩国时间，《[단독] 노종원 前 하이닉스 사장, 사모펀드 만들어 솔리다임 兆단위 투자 [시그널]》，[韩文首发原文](https://signal.sedaily.com/article/20081919)。

理解这些变化，需要把视线拉回Intel。当年的NAND研发、SSD控制器与固件、数据中心客户，以及大连晶圆厂的制造能力，并不是在Solidigm成立时才出现的。它们在不同年代形成，又通过一笔分两阶段完成的收购进入SK海力士体系。今天，AI基础设施对存储容量与稳定供货提出新要求，集团也要在HBM、DRAM和企业SSD之间分配资本。拟议上市因而同时涉及技术积累如何变成产品、制造成本如何进入经营账本，以及外部投资者究竟购买哪一层权益。大连工厂贯穿其中：从Intel在中国建设生产基地，到3D NAND转产，再到跨国收购与潜在发行主体的供应关系，它影响的不只是产量，也包括资产、合同和利润的归属。

> 来源：Intel／SK hynix，2020年10月20日，《SK hynix to Acquire Intel NAND Memory Business》，[联合公告原文](https://www.intc.com/filings-reports/all-sec-filings/content/0001193125-20-272580/d76122dex991.htm)；SK hynix，2026年10月1日，《Clarification Regarding Recent Media Reports on Solidigm》，[资本方案说明](https://news.skhynix.com/en/fact-11/)。

本篇覆盖：Intel存储业务的起点、SSD与大连工厂、两阶段收购、Kevin Noh与TechBridge、AI企业存储，以及独立上市的资产与资金边界。


## 第一章　Intel SSD从哪里来：从存储芯片到计算系统

Intel的存储历史比它作为处理器公司的公众形象更早。公司官方历史记录，1968年成立前，戈登·摩尔与罗伯特·诺伊斯讨论的新事业就以半导体存储器为基础。1970年推出的1103 DRAM，则推动计算机内存从磁芯转向半导体。这段历史的意义在于，Intel后来进入固态存储，能够调动已有的存储单元、工艺和计算平台经验。SSD业务的形成，应当放在这些能力重新组合的过程中理解。

> 来源： Intel官方历史档案，[《Intel的成立》（Establishing Intel）](https://timeline.intel.com/1968/establishing-intel)、[《Intel 1103 DRAM》](https://timeline.intel.com/1970/the-intel-1103-dram)，事件分别发生于1968年7月18日、1970年10月；网页未注明发布日期。

人物照片｜Intel联合创始人Gordon Moore（左）与Robert Noyce（右），1970年历史照片。

> 照片出处：Intel Free Press，网页未标日期，[《Gordon Moore with Robert Noyce at Intel in 1970》](https://www.flickr.com/photos/intelfreepress/8450997579/)；[原图](https://upload.wikimedia.org/wikipedia/commons/3/33/Gordon_Moore_with_Robert_Noyce_at_Intel_in_1970.png)。实际核阅的[图片说明与授权页](https://commons.wikimedia.org/wiki/File:Gordon_Moore_with_Robert_Noyce_at_Intel_in_1970.png)；原Flickr页当前访问受限。授权：[CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0/)，发布版仅缩放与JPEG编码。

在这段历史中，Intel曾经主动调整存储业务的边界。1985年宣布退出DRAM时，公司的内部解释指向价格下跌、需求疲弱和供给过剩，以及集中发展微处理器及相关产品的选择。DRAM是工作内存，NAND是断电后仍能保存数据的闪存，二者服务不同用途；退出某一类存储产品，并不意味着所有存储技术都失去战略价值。此后Intel重新扩大NAND投入，仍需在产品协同之外回答制造规模和资本回报的问题。

> 来源： Intel官方历史档案，[《告别DRAM》（Farewell to DRAM）](https://timeline.intel.com/1985/farewell-to-dram)，记录1985年10月10日事件及当时内部出版物，网页未注明发布日期。

通向后来Intel NAND SSD业务的关键组织节点，是与美光的合作。2005年11月21日，两家公司宣布组建IM Flash Technologies，即IMFT。按照当时披露的安排，美光持有合资公司51%的权益，Intel持有49%；双方计划各以现金、票据和资产投入约12亿美元作为初始出资。公告把美光的NAND开发与晶圆厂运营能力，同Intel的多层存储单元技术和闪存经验结合起来。Intel由此获得进入NAND大规模制造的合作平台。

> 来源： Intel与美光联合公告，[《美光与Intel成立新公司制造NAND闪存》](https://www.intel.com/pressroom/archive/releases/2005/20051121corp.htm)，2005年11月21日。持股为披露事实，初始出资为当时公告的计划安排。

这项合作首先面对的是消费电子需求。苹果同日宣布与海力士、Intel、美光、三星及东芝签订长期NAND供货协议，以支持iPod的生产。由这个客户案例可以看到，闪存的商业机会不只来自电脑升级：音乐播放器等设备需要更紧凑、抗振动的存储，也要求供应商稳定交付。对制造商而言，一个能够长期采购的客户，有助于把尚在建设中的产能同具体需求相连，降低只凭市场预测扩厂的不确定性。


图1｜Intel NAND与SSD业务形成及转手的主要节点。宣布投资、开始生产与交易交割分别列示。

> 图源：[原文1](https://www.intel.com/pressroom/archive/releases/2005/20051121corp.htm)；[原文2](https://www.intc.com/news-events/press-releases/detail/1338/intel-introduces-solid-state-drives-for-notebook-and)；[原文3](https://investors.micron.com/news/press-release/2018/Micron-and-Intel-Announce-Update-to-NAND-Memory-Joint-Development-Program-01-08-2018/default.aspx)；[原文4](https://www.intc.com/filings-reports/all-sec-filings/content/0001193125-20-272580/d76122dex991.htm)；[原文5](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-18-000007/a12302017q4-10kdocument.htm)；[原文6](https://news.skhynix.com/en/sk-hynix-completes-the-first-phase-of-intel-nand-and-ssd-business-acquisition/)；[原文7](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-25-000060/intc-20250327.htm)。


> 来源： 苹果公司公告，[《苹果宣布闪存长期供货协议》](https://www.apple.com/newsroom/2005/11/21Apple-Announces-Long-Term-Supply-Agreements-for-Flash-Memory/)，2005年11月21日。

资金安排也体现了客户与制造商的相互依赖。Intel和美光的合资公告披露，苹果拟分别向两家公司预付2.5亿美元，用于其各自分得的合资公司NAND产出。预付款对应未来供货，与股权投资具有不同性质；它将客户对供应安全的需求，转化为制造商提前获得的资金。随后留存于SEC的供货合同确认，IMFT与Intel的原始供货协议签订于2006年1月6日。宣布合资、建立供货关系、实现生产，是一条逐步落地的业务链。

> 来源： Intel与美光，[《美光与Intel成立新公司制造NAND闪存》](https://www.intel.com/pressroom/archive/releases/2005/20051121corp.htm)，2005年11月21日；Intel与IMFT，[《经修订及重述的供货协议》](https://www.sec.gov/Archives/edgar/data/723125/000072312512000084/a2012q3ex10-110.htm)，2012年4月6日，序言A确认2006年原协议日期。

拥有NAND产出之后，还要决定把闪存卖成什么产品。独立的闪存芯片，需要客户继续完成控制器设计、固件开发和系统验证；SSD则把这些工作集成到可以装入电脑和服务器的产品里。Intel能够从处理器与平台需求出发理解存储瓶颈，SSD成为其把上游介质技术向系统延伸的途径。它既可获得存储产品收入，也可帮助客户提高处理器的有效利用率。这种协同，正是Intel当年产品公告明确强调的卖点。

> 来源： Intel，[《Intel推出笔记本及台式机固态硬盘》](https://www.intc.com/news-events/press-releases/detail/1338/intel-introduces-solid-state-drives-for-notebook-and)，2008年9月8日；关于芯片与完整驱动器的分工为本文机制解释。

2008年9月8日，Intel宣布X18-M和X25-M已经开始出货，面向笔记本和台式机，首批容量为80GB。公告突出并行十通道架构、自有控制器、固件及存储管理算法。后者比单一容量规格更能说明这项业务的技术来源：Intel开始把NAND的物理性能转化为整盘的行为控制。一个SSD品牌能否持续获得企业客户认可，最终取决于介质与这些控制能力能否共同提供可靠、可预测的服务。

> 来源： Intel产品公告，[《Intel推出笔记本及台式机固态硬盘》](https://www.intc.com/news-events/press-releases/detail/1338/intel-introduces-solid-state-drives-for-notebook-and)，2008年9月8日。容量和通道数为产品披露规格。

控制器需要解决的基本问题，是让计算机看到一个稳定的存储地址空间，同时管理内部不断变化的闪存状态。NAND经过反复写入和擦除会逐渐磨损；如果频繁更新的数据总落在同一区域，就可能提前耗尽该区域的寿命。磨损均衡通过调整数据落点分散这一压力，写放大则衡量内部实际写入量相对主机要求写入量的增加。两者共同影响寿命与效率，因此固件的价值不能只用读写峰值来概括。

> 来源： Sam Siewert、Dane Nelson，[《固态硬盘在存储与嵌入式系统中的应用》](https://www.intel.com/content/dam/www/public/us/en/documents/research/2009-vol13-iss-1-intel-technology-journal.pdf)，Intel Technology Journal，2009年3月，印刷页30—33；上述为技术机制归纳。

在此基础上，面向个人电脑与面向数据中心的产品开始形成不同要求。电脑用户常直接感受开机、程序启动和文件打开速度；服务器则需要在长时间运行、并发访问和后台维护同时发生时保持响应。某次测试中速度很高，却在持续负载下出现明显波动的设备，会使系统容量规划更困难。企业采购因而会把数据保护、耐久、故障处理和性能一致性一并纳入评估。SSD业务由此逐步成为与客户系统共同设计和验证的业务。

> 来源： Intel，[《Intel DC S3700固态硬盘服务质量技术简报》](https://www.intel.com/content/dam/www/public/us/en/documents/technology-briefs/ssd-dc-s3700-quality-service-tech-brief.pdf)，2013年7月，页4—6、9—11；企业采购影响为本文分析。


图2｜每个NAND单元存储1、2、3、4 bit时，分别需要区分2、4、8、16种逻辑状态。柱长按状态数绘制，不表示实际阈值电压、速度或耐久。

> 图源：[原文1](https://www.solidigm.com/products/technology/qlc-nand-ready-for-mainstream-use-in-data-center.html)。


2012年11月5日发布的DC S3700，集中体现了这一变化。Intel把一致的性能、低延迟、端到端数据保护和高耐久列为核心特征，并通过NAND管理与芯片改进，争取在成本更低的MLC介质上实现较高耐久。这个方向把竞争从“哪一种闪存单元更昂贵”推进到“整套设备能否满足工作负载”。对后来的Solidigm而言，能够把不同介质特征组织成企业客户愿意采购的完整产品，构成重要的技术继承。

> 来源： Intel产品公告，[《Intel发布下一代数据中心固态硬盘DC S3700》](https://www.intc.com/news-events/press-releases/detail/1241/intel-announces-intel-ssd-dc-s3700-series-)，2012年11月5日。HET技术收益为厂商表述。

性能一致性还涉及存储系统的经营约束。假设一个服务需要等待多个存储操作完成，少量较慢请求也可能延长整个任务的完成时间。客户为了保住服务响应，可能减少每台服务器承载的业务，或者购买更多设备分担负载。这是说明性的系统逻辑，并非某款产品的实测收益。它解释了为什么客户会为稳定响应支付费用，也解释了企业SSD供应商为何需要理解应用、固件和服务器之间的关系。

> 来源： Intel，[《Intel DC S3700固态硬盘服务质量技术简报》](https://www.intel.com/content/dam/www/public/us/en/documents/technology-briefs/ssd-dc-s3700-quality-service-tech-brief.pdf)，2013年7月，页4、7、9—11；多请求等待及采购影响为本文说明性分析。

随着产品向企业场景延伸，上游介质也进入结构变化。2015年3月26日，Intel与美光公布采用浮栅单元的3D NAND，将存储单元垂直堆叠；首代公布架构为32层。二维NAND继续缩小单元会遭遇工艺与可靠性限制，垂直堆叠则提供增加单位面积容量的新途径。这个变化影响的不仅是芯片容量，还包括晶圆制造、控制器管理及整盘验证。产业需要把增加的存储密度转化为客户实际可用的容量。

> 来源： Intel与美光联合公告，[《美光与Intel公布新型3D NAND闪存》](https://www.intc.com/news-events/press-releases/detail/349/micron-and-intel-unveil-new-3d-nand-flash-memory)，2015年3月26日，Innovative Process Architecture部分。32层为披露架构，成本与耐久收益为当时厂商预期。

采用浮栅路线，是Intel技术谱系中的一个具体选择。它意味着后来移交的NAND业务带有自身的器件设计、制造工艺和控制经验，收购方需要理解并保留这些能力。不同技术路线的产品不能只按容量标签互换：介质的特征要进入固件管理与验证，才能成为稳定的成品。由此看，Intel SSD的积累同时存在于晶圆端和系统端，既包括制造可用芯片的经验，也包括把芯片交付给企业客户的经验。

> 来源： Intel与美光，[《美光与Intel公布新型3D NAND闪存》](https://www.intc.com/news-events/press-releases/detail/349/micron-and-intel-unveil-new-3d-nand-flash-memory)，2015年3月26日；技术路线对整合与验证的影响为本文分析。

随后，Intel将QLC纳入这一体系。2018年8月8日的官方公告已经列出数据中心产品D5-P4320，并称腾讯在初期生产环境中采用了它。公告将QLC放在大容量存储位置，将Optane放在高频数据访问位置，体现不同介质共同构建存储层级的思路。本文采用这一产品与客户节点，不把厂商宣传的收益推广到其他系统。今天Solidigm围绕大容量企业SSD形成的叙事，在Intel阶段已有可追溯的产品基础。

> 来源： Intel，[《Intel以Optane与QLC布局存储未来》](https://download.intel.com/newsroom/2021/archive/2018-08-08-news-intel-poised-shape-future-memory-storage-optane-qlc.pdf)，2018年8月8日，官方归档PDF页1—2。腾讯部署为厂商披露案例。

这条发展路径把一个看似简单的固态硬盘品牌，展开为相互依赖的产业能力：介质设计决定基础特征，制造决定成本与供货，控制器和固件决定整盘行为，客户验证决定能否进入业务系统。沿着这些层次审视后来出售的资产，就能理解收购方为何同时需要工厂、知识产权和人员。也可以留下一个持续可核验的问题：新的产品代际能否延续客户认证与稳定交付，使历史积累成为可持续的业务，而不只保留在旧产品名称里。

> 来源： Intel与SK海力士联合公告，[《SK海力士收购Intel NAND存储业务》](https://www.intc.com/filings-reports/all-sec-filings/content/0001193125-20-272580/d76122dex991.htm)，2020年10月20日，列明SSD与NAND制造相关知识产权及员工的移交安排；产业能力之间的联系为本文分析。


## 第二章　Intel为何出售NAND：技术协同与资本回报的分岔

Intel已经建立NAND制造和SSD产品能力，为何仍选择出售？理解这一决定，需要同时看业务本身和整个集团的投资排序。SSD改善计算系统的性能，可以增强处理器平台的吸引力；经营NAND晶圆厂，则要求持续投入设备、工艺和产能，并承受存储价格的变化。产品之间存在协同，资本回报仍需分别成立。当NAND业务需要独立承担越来越多的投入，它在集团内获得资源的理由也必须随之更新。

> 来源： Intel，[《2017年度报告》](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-18-000007/a12302017q4-10kdocument.htm)，2018年2月16日，页11、29—30；协同与投资排序的关系为本文分析。

大连Fab 68提供了这种变化的实物载体，但它最初服务的是逻辑芯片。2007年3月26日，Intel宣布在大连建设300毫米晶圆厂，初始生产用途是支持核心微处理器业务的芯片组。时任首席执行官保罗·欧德宁强调，中国是公司增长最快的主要市场，制造投资旨在贴近未来客户。建设公告提出25亿美元投资，这属于当时宣布的项目安排；同年9月，Intel宣布工厂正式破土动工。大连的起点，是Intel全球计算平台制造网络在中国的延伸。

> 来源： Intel，[《Intel将在中国建设300毫米晶圆厂》](https://www.intc.com/news-events/press-releases/detail/1050/intel-to-build-300mm-wafer-fabrication-facility-in-china)，2007年3月26日；[《Intel大连晶圆厂破土动工》](https://www.intel.com/pressroom/archive/releases/2007/20070907corp_b.htm)，2007年9月8日。25亿美元为建设公告所列投资安排。

人物照片｜Paul Otellini，Intel建设大连工厂时的首席执行官；历史照片。

> 照片出处：Intel Corporation，2017-10-03，[《Former Intel CEO Paul S. Otellini Dies at Age 66》](https://www.intc.com/news-events/press-releases/detail/199/former-intel-ceo-paul-s-otellini-dies-at-age-66)；[原图](https://d1io3yog0oux5.cloudfront.net/_a0dbd358c0dfe27d139bef6d4198de40/intel/news/199/1816/image.jpeg)。

工厂的建设与NAND业务的成长，最初沿着不同路径推进。Intel的2010年度报告确认，中国晶圆厂在当年第四季度开始晶圆制造，而同一报告把NAND产品制造归于IMFT。这个时间差解释了大连后来为何需要转换用途：Intel已经拥有厂房、公用设施、制造人员及运营体系，新的存储投资可以在既有基地上展开，但生产对象发生变化，工艺设备与产品验证仍须重新配套。晶圆厂沿用原有名称，并不意味着原来的逻辑芯片生产线可以直接制造NAND。

> 来源： Intel，[《2010年度报告》](https://www.intc.com/filings-reports/all-sec-filings/content/0000950123-11-015783/f56033e10vk.htm)，2011年2月18日，页6，Manufacturing and Assembly and Test；转换用途涉及的工程工作为机制解释。

2015年10月，Intel宣布投资大连并将其转换为3D NAND制造基地；2016年7月，工厂进入3D NAND生产。技术路径承接此前与美光联合开发的浮栅3D NAND：存储密度的提升，不再只依赖平面缩小，也依赖垂直层数与单元设计。对Intel SSD而言，制造端与产品端可以围绕介质特征、控制器及固件共同改进；对经营部门而言，它开始更直接地承担工艺导入与产能爬坡的费用。Intel的2016年报也把大连3D NAND爬坡成本列为影响当年NSG经营结果的因素之一。

> 来源： Intel，[《Intel推出面向云存储的数据中心3D NAND SSD》](https://download.intel.com/newsroom/2021/archive/2017-05-02-news-intel-launches-cloud-inspired-3d-nand-ssds-data-centers.pdf)，2017年5月2日，页1，确认2015年10月投资与转换；Intel与美光，[《美光与Intel公布新型3D NAND闪存》](https://www.intc.com/news-events/press-releases/detail/349/micron-and-intel-unveil-new-3d-nand-flash-memory)，2015年3月26日；Intel，[《2016年度报告》](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-17-000012/a10kdocument12312016q4.htm)，2017年2月17日，页37。投产月份见下段年报原图。

到2017年末，Intel供应的3D NAND中，超过一半由大连工厂制造。同一份报告披露，2017年Fab 68相关投资约占Intel全年资本开支的20%。这组已披露事实说明，Intel当时确实在建立规模化制造基础。大连改变了NAND业务的制造供给，也加深了它同集团资金的联系。后来出售NAND，应当理解为对已经投入较多资源的业务重新作出资本安排。

> 来源： Intel，[《2017年度报告》](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-18-000007/a12302017q4-10kdocument.htm)，2018年2月16日，页11与30。2016年7月节点见页30[原始年报图](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-18-000007/a044nsgf68a01.jpg)。比例分母分别为Intel供应的3D NAND和Intel全年资本开支。

制造能力扩大之后，产品部门能够更紧密地掌握介质供给，却也需要承担制造经营的约束。晶圆厂的设备与人员难以随销售价格立即收缩；新工艺进入生产后，还要改善良率，使可销售产出逐渐覆盖投入。当市场价格下降，降低单位成本只能缓解压力，未必足以抵消价格损失。企业SSD的软件与客户能力可以提供差异化，但业务仍会受到上游介质市场影响。Intel年报对制造费用和NAND价格的解释，正反映这种双重属性。

> 来源： Intel，[《2018年度报告》](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-19-000007/a12292018q4-10kdocument.htm)，2019年2月1日，页34；固定投入与价格变化的关系为本文机制解释。

与此同时，维持共同研发的组织基础也发生变化。2018年1月8日，美光与Intel宣布，将完成第三代3D NAND的联合开发，之后各自研发后续代际，以更好地适配各自的业务需求。公告当时仍明确保留双方在3D XPoint上的联合研发和制造。因此，NAND研发分开是一个具体技术平台的安排，不能概括为当天所有存储合作终止。它使双方能够选择各自的产品方向，也改变了未来技术投入的分担方式。

> 来源： 美光与Intel联合公告，[《美光与Intel更新NAND联合研发计划》](https://www.sec.gov/Archives/edgar/data/723125/000072312518000007/ex991pr01082018.htm)，2018年1月8日，SEC保存的公告原文。

这里的业务需求，涉及芯片用途和产品组合的差异。适用于某种大容量企业SSD的介质设计，需要同对应的控制器、固件和客户负载共同优化；服务更广泛市场的公司，则可能选择不同的性能、成本和制造组合。独立研发使调整更加灵活，却需要各自维持完整的工程能力。这是由组织安排可以理解的经济后果，不代表公告已经证明双方发生技术冲突。就Intel而言，更大的自主性与更完整的投入责任同时出现。

> 来源： 美光与Intel，[《美光与Intel更新NAND联合研发计划》](https://www.sec.gov/Archives/edgar/data/723125/000072312518000007/ex991pr01082018.htm)，2018年1月8日；产品优化、工程投入及组织后果为本文分析。

Intel自己的产品方向逐渐清晰。其QLC产品宣传把大容量存储同高频访问数据分层处理，而企业SSD部门进一步推动PCIe、NVMe以及适合数据中心散热和维护的形态。对客户来说，介质、接口、系统空间和运维必须一起考虑；对Intel来说，单纯提高晶圆产出还不足以完成这一业务。NAND部门既要跟上介质制造的节奏，又要保持企业产品与系统的适配能力，这使它成为一项需要持续独立经营的业务。

> 来源： Intel，[《Intel以Optane与QLC布局存储未来》](https://download.intel.com/newsroom/2021/archive/2018-08-08-news-intel-poised-shape-future-memory-storage-optane-qlc.pdf)，2018年8月8日，页1—2；[《2018年度报告》](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-19-000007/a12292018q4-10kdocument.htm)，2019年2月1日，页33。

讨论这项业务的盈利时，最容易发生的错误是把整个非易失性存储事业部NSG与NAND等同。Intel公布的历史NSG结果同时包含NAND和Optane。按公司已披露财务，2019年NSG收入为43.62亿美元，经营亏损为11.76亿美元。这里的利润是事业部经营口径，不能直接写成后来出售NAND业务的独立亏损，更不能当作Solidigm在独立运营期间的结果。不同资产边界的财务，需要先划清范围才能解释。

> 来源： Intel，[《2020年度报告》](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-21-000010/intc-20201226.htm)，2021年1月22日，页28—30、85。2019年数据为已披露事实，NSG范围包含NAND及Optane。

这份报告对历史结果的解释，突出NAND价格下降带来的影响，即使产品数量增加、制造成本改善，也可能被更低的平均售价抵消。这对收购价值有直接启示：销售数量增加与利润增长之间，隔着价格、产品组合和单位成本。存储厂商持续投资，往往是在下一轮价格下跌前降低成本；与此同时，新产出进入市场也可能加剧供需压力。单看某一年营业收入，难以判断一项NAND业务是否形成稳定回报。

> 来源： Intel，[《2020年度报告》](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-21-000010/intc-20201226.htm)，2021年1月22日，页30；存储投资与价格循环的联系为本文分析。

出售公告披露的独立NAND范围，提供了另一幅图景。截至2020年6月27日的六个月，相关业务贡献约28亿美元收入和约6亿美元经营利润。两项数据均为Intel在交易公告中披露的NAND业务口径，期间也只覆盖半年。它们表明，签约时的资产包含能够盈利的业务。一次周期改善不能保证未来回报，但也足以阻止把这笔交易简化为放弃一项完全失去竞争力的业务。

> 来源： Intel与SK海力士联合公告，[《SK海力士收购Intel NAND存储业务》](https://www.intc.com/filings-reports/all-sec-filings/content/0001193125-20-272580/d76122dex991.htm)，2020年10月20日。收入与经营利润贡献均为截至2020年6月27日六个月的已披露事实。

对集团决策而言，能够盈利仍只是判断的一部分。已有产能带来的当期利润，同继续更新工艺需要支付的现金，具有不同时间分布。管理层还要比较同一笔资本投入处理器、网络、加速器或存储之后的预期回报，以及公司在各市场能够形成的差异。如果一个业务对客户有价值，却由另一家制造规模和产品组合更适合的公司经营，出售也可以成为资源调整的途径。这个解释必须由当时管理层的表述支撑，而不能只依据后来的成败。

> 来源： Intel与SK海力士，[《SK海力士收购Intel NAND存储业务》](https://www.intc.com/filings-reports/all-sec-filings/content/0001193125-20-272580/d76122dex991.htm)，2020年10月20日，Bob Swan关于投资差异化技术的表述；现金时间分布与资本比较为本文分析。

当时处理器制造方面的压力已有公开证据。2020年7月23日，Intel在季度业绩公告中披露，7纳米CPU产品时间相对原预期推迟，原因主要涉及制造良率；公司同时推进10纳米产品转换。这个同期背景说明，Intel的核心计算业务也需要工程和制造资源。不过，公告并未把制程延迟宣布为NAND出售的直接原因。两件事可以共同解释投资排序所处的环境，不能把时间先后自动写成因果关系。

> 来源： Intel，[《Intel公布2020年第二季度财务业绩》](https://www.intc.com/news-events/press-releases/detail/1402/intel-reports-second-quarter-2020-financial-results)，2020年7月23日，产品与工艺转换部分。

更直接的依据来自出售公告。时任Intel首席执行官Bob Swan解释，这项交易使公司能够优先投资差异化技术，更深入参与客户成功并争取股东回报；公告列出的长期增长方向包括人工智能、5G网络和智能自主边缘。这里的“差异化”是公司对未来资源配置的判断，不能读成对NAND产品质量的否定。Intel选择减少对NAND制造及其经营周期的直接承担，保留资金和组织空间支持另一些技术方向。

> 来源： Intel与SK海力士，[《SK海力士收购Intel NAND存储业务》](https://www.intc.com/filings-reports/all-sec-filings/content/0001193125-20-272580/d76122dex991.htm)，2020年10月20日，Intel资金用途及Bob Swan发言；战略判断的含义为本文分析。

人物照片｜Bob Swan，2020年Intel出售NAND业务时的首席执行官；历史照片。

> 照片出处：Intel，2019-01-31，[《Intel Names Robert Swan CEO》](https://www.intc.com/news-events/press-releases/detail/96/intel-names-robert-swan-ceo)；[原图](https://d1io3yog0oux5.cloudfront.net/_a0dbd358c0dfe27d139bef6d4198de40/intel/news/96/973/image.jpeg)。

资产边界进一步显示了这项选择的具体性。协议涵盖NAND SSD业务、NAND元件与晶圆业务，以及中国大连工厂，同时明确由Intel保留Optane。这一点尤其重要，因为当年的Intel存储产品经常把两者放在同一个系统愿景中讨论，也都可能采用SSD形态。但技术愿景中的组合不等于交易中的共同出售。Solidigm继承的是被移交的NAND与相关SSD能力，Optane后来如何发展，需要另按Intel的资产与决定解释。

> 来源： Intel与SK海力士，[《SK海力士收购Intel NAND存储业务》](https://www.intc.com/filings-reports/all-sec-filings/content/0001193125-20-272580/d76122dex991.htm)，2020年10月20日，交易范围及Optane排除条款。

从买卖双方的视角看，同一项业务可以具有不同价值。Intel需要把NAND同自身的计算与制造投入比较；以存储为核心的买方，则可以考察企业SSD、技术能力和现有产能与其产品组合的关系。完整驱动器能够使制造商更接近最终客户，也让介质工艺在具体应用中获得定价机会。这样的互补提供了交易的商业理由，但整合能否实现目标，还取决于后续技术衔接、供货与客户保留，不能在签约时提前确认为收益。

> 来源： Intel与SK海力士，[《SK海力士收购Intel NAND存储业务》](https://www.intc.com/filings-reports/all-sec-filings/content/0001193125-20-272580/d76122dex991.htm)，2020年10月20日，双方业务定位及前瞻性声明；不同所有者对资产价值的判断为本文分析。

因此，Intel出售NAND可以沿着当时的证据解释：它已经形成介质和企业产品能力，也承担了制造投入；共同研发的安排转向各自优化，业务回报受到价格周期影响；整个集团随后选择重新排列差异化技术的优先级。这个判断不需要调用之后Intel或Solidigm的经营结果来补写动机。对收购方来说，下一步需要证明的，是接手后能否把制造与解决方案衔接起来，让投入、产品代际和客户需求形成连续的经营结果。

> 来源： 以上依据分别来自Intel历年年报、美光与Intel联合研发公告及2020年交易公告；本段为前述事实的分析归纳。


## 第三章　SK海力士买下了什么

Intel决定把NAND业务交给另一家存储厂商时，SK海力士首先面对的并不是如何接收一条产线，而是如何把既有的芯片制造能力延伸到企业级存储系统。买方已经有自己的NAND业务，交易因此不能简单理解为进入一个陌生行业。它要解决的，是产品组合、技术积累与客户覆盖之间的不平衡。SK海力士在首阶段交割公告中给出的解释很具体：自身在移动NAND方面有优势，Solidigm在企业SSD方面有优势，希望合并后的NAND竞争力向其DRAM业务靠拢。这是买方当时公开的产业目的，也比后来用AI行情解释当年的决定更符合时间顺序。

> 来源：SK海力士，2021年12月30日，[《SK hynix completes the First Phase of Intel NAND and SSD Business Acquisition》](https://news.skhynix.com/en/sk-hynix-completes-the-first-phase-of-intel-nand-and-ssd-business-acquisition/)。

企业SSD把闪存颗粒变成客户可以部署、维护和长期使用的存储设备，中间需要控制器、固件、系统验证和业务支持。对已经能够制造NAND的公司来说，追加晶圆产能可以增加可出售的比特，却不会自动增加能够进入数据中心采购名单的产品。由此观察这次收购，企业SSD能力的价值在于把供给端与需求端接起来：买方获得的不只是生产存储介质的能力，也包括围绕特定客户要求组织研发与交付的能力。这是从交易资产组合得出的机制解释，具体效果仍要由后续产品与经营记录检验。

交易的价格与资产边界在签约时已经写明。2020年10月20日，双方公开宣布协议，原定总对价为90亿美元，属于已披露的合同金额。范围包括Intel的NAND SSD业务、NAND组件与晶圆业务，以及中国大连的NAND制造设施。Intel保留Optane，因此Solidigm的前身应当准确写成Intel的NAND与相关SSD业务，不能把Intel曾经经营过的所有存储业务一并装入这个名称。Optane与NAND SSD同样服务于数据中心，也曾共享管理与销售背景，但在这份交易中属于不同资产边界。

> 来源：Intel与SK海力士，2020年10月20日，[《SK hynix to Acquire Intel NAND Memory Business》](https://www.intc.com/filings-reports/all-sec-filings/content/0001193125-20-272580/d76122dex991.htm)。

两阶段安排决定了此后整合的节奏。原协议规定，先支付70亿美元取得NAND SSD业务，包括相关知识产权与人员，以及大连设施；后续再按原计划支付20亿美元，取得NAND晶圆制造与设计相关知识产权、研发人员及大连工厂员工。这里的金额都是签约时披露的计划对价。过渡期内，Intel仍在大连制造NAND晶圆，并保留相关制造与设计知识产权。资产所有权、产品经营与工厂生产责任由此分步转移，不能把第一笔付款理解为所有技术、人员与运营职责都已移交。

> 来源：SK海力士与Intel，2020年10月20日，[《SK hynix to Acquire Intel NAND Memory Business》](https://news.skhynix.com/en/sk-hynix-to-acquire-intel-nand-memory-business/)。

大连因此不是一个可以用“工厂买过来了”概括的单一资产。Intel向SEC提交的签约文件，把大连设施及相关设备等有形资产称为Fab Assets，同时规定把晶圆业务相关人员、知识产权与其他资产装入分别设在美国和中国的OpCo。在两次交割之间，这些运营公司仍由Intel全资持有，继续使用已经转让给买方的大连设施生产晶圆，并根据制造与销售协议向SK海力士供货；最终再出售运营公司的股份。工厂的资产所有权、承担生产的公司股权、工艺知识产权与员工雇佣关系，是可以分步转移的不同权利。

> 来源：Intel，2020年10月20日签署提交文件，协议日期为美国时间10月19日，[《Form 8-K，Item 1.01 — Entry into a Material Definitive Agreement》](https://www.sec.gov/Archives/edgar/data/50863/000119312520272580/d76122d8k.htm)。

过渡生产也不是一个没有商业约束的临时安排。Intel在2022年第一季度财报附注中披露，制造与销售协议包含与运营成本及产出挂钩的奖励和惩罚机制。这说明交易双方除了安排谁生产，还通过合同分配成本控制与产量达成的责任。工厂产权已经转移，生产仍需维持既有技术和团队的连续性，供货责任则由协议衔接。对后来研究Solidigm的供应关系而言，这段历史尤其重要：能够采购大连晶圆、能够使用某种技术、以及直接拥有晶圆工厂，并不是同一种法律或经济关系。

> 来源：Intel，2022年4月28日，[《Form 10-Q，季度截至2022年4月2日》，附注7、印刷页13（PDF第15页）](https://www.intc.com/filings-reports/quarterly-reports/content/0000050863-22-000020/0000050863-22-000020.pdf)。

首阶段实际交割发生在2021年12月29日；SK海力士在翌日发布完成公告。这个日期区别由Intel最终交割文件明确记录，也与Solidigm自己的公司成立回顾相符。新公司作为美国子公司运营，接续SSD业务。英文名称来自“solid”与“paradigm”的组合，表达固态存储新范式的意图。品牌是新的，产品研发、人员经验和客户关系却不是从零开始。它更接近把Intel已经形成的业务组织移入新的资本体系，而不是买方重新创建一家没有历史的SSD公司。

> 来源：Intel，2025年3月27日，[《Form 8-K，Item 2.01》](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-25-000060/intc-20250327.htm)；Solidigm，2022年11月22日，[《A New Paradigm at One Year》](https://news.solidigm.com/en-WW/220582-a-new-paradigm-at-one-year/)。


图3｜90亿美元及70亿／20亿美元分期额为原始合同安排。SK海力士2025年更正披露的最终付款为66.1亿／22.4亿美元；Intel披露末阶段净调整后收款约19亿美元，口径不同。Optane不在收购内。

> 图源：[原文1](https://kind.krx.co.kr/external/2025/03/28/000061/20250328000194/11336.htm)；[原文2](https://www.intc.com/filings-reports/all-sec-filings/content/0001193125-20-272580/d76122dex991.htm)；[原文3](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-25-000060/intc-20250327.htm)；[原文4](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-25-000074/intc-20250329.htm)。


最初的管理安排也体现了延续与整合并行。Solidigm由Rob Crooke出任CEO，他此前在Intel担任非易失性存储解决方案事业部高级副总裁兼总经理。SK海力士总裁及联席CEO李锡熙则担任执行董事长，负责首阶段交割后的整合。这意味着日常经营由熟悉原业务的管理者接续，集团整合由买方高层参与。Kevin Noh并不是Solidigm成立时的首任CEO。先把这一点说明白，才能解释他后来任职所对应的不同阶段。

> 来源：Solidigm，2021年12月30日，[《Introducing Solidigm — A Market Leader in NAND Flash Technology》](https://d21buns5ku92am.cloudfront.net/69634/pdf/campaigns/212941-20220401092445000000000-introducing-solidigm-a-market-leader-in-n.pdf)；SK海力士，2021年12月30日，[首阶段交割公告](https://news.skhynix.com/en/sk-hynix-completes-the-first-phase-of-intel-nand-and-ssd-business-acquisition/)。

人物照片｜Rob Crooke，Solidigm首任CEO；照片来自2022年离任报道。

> 照片出处：Blocks & Files，2022-11-03，[《Solidigm CEO’s departure takes staff by surprise》](https://www.blocksandfiles.com/flash/2022/11/03/solidigm-ceos-departure-takes-staff-by-surprise/1601106)；[原图](https://image.blocksandfiles.com/125162.webp?format=jpg&height=1254&imageId=125162&width=960)。

人物照片｜Seok Hee Lee（李锡熙），首阶段收购交割时担任Solidigm执行董事长；照片来自SK海力士2019年公告。

> 照片出处：SK hynix Newsroom，2019-10-10，[《Interview with SK hynix CEO Seok-hee Lee, “curiosity has shaped me”》](https://news.skhynix.com/en/interview-with-sk-hynix-ceo-seok-hee-lee-curiosity-has-shaped-me/)；[原图](https://d18r0a86za96sg.cloudfront.net/wp-content/uploads/2026/05/27201106/LeeSeok-hee_CEO_of_SK_hynix_interview_1.jpg)。

保留美国业务组织的意义，可以从客户支持与研发协作两方面理解。母公司希望获得美国企业SSD业务的能力，就需要让原来的工程师能够继续解决原来的客户问题，同时逐渐获得新的资源与技术选项。整合得过快，可能使产品计划与客户验证失去连续性；整合停留在股权层面，则难以发挥买方的制造优势。这不是对某一位管理者行为的推测，而是这类跨国技术收购所面对的组织问题。独立子公司的形式为两种要求提供了协调空间，但协调是否有效，需要在联合产品上寻找证据。

联合产品很快给出了一个可见例子。2022年4月5日，SK海力士与Solidigm宣布首款合作企业SSD P5530，把SK海力士的128层4D NAND与Solidigm的控制器、固件结合，支持PCIe第四代接口。公告强调产品针对具体数据中心使用场景进行了优化，并明确属于有限发布。层数与接口是厂商披露的产品规格，不能据此直接推算商业销量。这个例子却清楚说明，收购双方可以在不立即统一全部晶圆技术的情况下，先在SSD系统层完成组合。

> 来源：SK海力士与Solidigm，2022年4月5日；美国发布日为4月4日，[《SK hynix and Solidigm Introduce First Collaborative Product》](https://news.skhynix.com/en/sk-hynix-and-solidigm-introduce-first-collaborative-product/)。

它也纠正了一个容易出现的误解：技术整合并不只有把某种闪存工艺替换成另一种工艺这条路径。SSD既可以延续原有介质与控制器组合，也可以在完成兼容、验证和优化后使用另一来源的介质。控制器与固件因此成为连接两边技术的关键环节。对买方而言，企业SSD团队能够把不同晶圆来源的特点转化为完整产品，价值便不只依附于某一代闪存颗粒。对客户而言，则要看新组合在性能一致性、耐久与服务方面能否达到要求，不能只因供应商属于同一个集团，就假定替换完全没有验证成本。

最终交割在2025年3月27日发生，Intel向SEC提交的文件确认，第二阶段收到的对价约为19亿美元，已经扣除相关调整。文件同时说明，首阶段建立的NAND晶圆制造与销售协议终止。19亿美元是已披露的净调整后实际收款口径，与签约时20亿美元的原定尾款口径不同；不应把两者写成彼此矛盾，更不能在没有调整明细的情况下臆测差额原因。文件把最后阶段的意义落在制造与技术业务的完成移交，而不是Solidigm品牌再次诞生。

> 来源：Intel，2025年3月27日，[《Form 8-K，Item 2.01 — Completion of Acquisition or Disposition of Assets》](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-25-000060/intc-20250327.htm)。

买方的最终付款披露还提供了另一套必须分开的口径。SK海力士在2025年3月28日向韩国交易所提交更正报告，列明首阶段最终支付66.1亿美元，末阶段最终支付22.4亿美元，属于买方已披露实际支付金额。原协议金额、买方最终付款与Intel净调整后收款，因此不能混在一起相加。更正报告还确认，首阶段通过全资海外子公司接收大连生产设施与SSD业务，最后阶段取得承载其余NAND知识产权与工厂运营人员的Intel子公司股份。美韩文件分别采用各自的交割日期记录，但均确认第二阶段已完成，不能因日期差一天就把它们当成两笔交易。

> 来源：SK海力士，2025年3月28日，[《주요사항보고서(영업양수결정) — 정정신고》，即《重大事项报告：业务受让决定更正公告》，第8及第17项](https://kind.krx.co.kr/external/2025/03/28/000061/20250328000194/11336.htm)。

两次交割之间的多年经营，也提醒人们不要用原始交易金额直接评价后来IPO的回报。收购价格购买的是当时约定的资产与权利；后来经营需要研发、资本投入、库存与组织成本，也可能发生融资和结构调整。潜在上市估值又取决于上市实体装入什么业务、承担什么负债、获得什么供应安排。没有这些信息，把历史价格与媒体报道的未来估值相除，得到的只是两个不同口径金额的比值，无法说明母公司真正实现了多少收益。

这种边界问题在2026年变得更具体。SK海力士1月28日公告拟通过Solidigm重组建立美国AI Company：原有法人保留并改为AI Company，业务运营转入新设、继续使用Solidigm名称的子公司。公告描述的是集团宣布的重组方案，不能只凭品牌沿用就把新旧法人当成同一份账。以后研究赴美融资，需要核对的是新公司的实际资产、关联交易与承担的投资职责。原来收购大连设施的事实，也不自动证明该设施必然完整进入拟上市主体。韩国交易所的更正报告列出的收购及付款主体包括SK hynix Semiconductor (Dalian) Co., Ltd.与SK hynix NAND Product Solutions Corp.，已经显示制造设施与美国业务需要分别辨认。若未来上市的是经营SSD的公司，投资者就必须知道它是否直接持有制造资产，或者主要依靠关联供应合同取得晶圆；这将影响折旧、资本开支、库存与生产成本落在哪一份财务报表上。

> 来源：SK海力士，2026年1月28日，[《SK hynix to Establish U.S. Arm Specialized in AI Solutions》](https://news.skhynix.com/en/sk-hynix-to-establish-ai-solutions-arm-in-us/)。 另见SK海力士，2025年3月28日，[《业务受让决定更正公告》，第17项](https://kind.krx.co.kr/external/2025/03/28/000061/20250328000194/11336.htm)。

因此，这次收购的产业故事可以分成三个相互衔接的环节：先取得能够经营企业SSD的业务组织，再逐步完成制造技术与人员的转移，最后在新需求下重设业务和资本边界。前两个环节已经有交割文件与产品公告可查，美国经营业务转移也已在2026年上半年执行；拟上市主体最终包含哪些资产与合同，仍需后续发行文件确认。接下来判断整合是否创造持续价值，应当看联合技术能否形成稳定产品、企业客户能否持续采购、业务自身能否承担研发与供货所需现金投入。IPO若继续推进，正式披露的关联供应协议与独立财务，将比“收购成功”或“资产升值”这样笼统的表述提供更可检验的答案。


## 第四章　Kevin Noh的经营与投资角色

Kevin Noh的角色，把Solidigm的收购、经营与融资几段历史连接起来。公司公告使用Kevin（Jongwon）Noh这一英文姓名，韩文为노종원，中文通常译作卢钟元。他在2023年接手公司时的正式职务是联席CEO。要回答他为什么去管理Solidigm，应当先看他在SK体系里处理过什么问题，再看董事会如何解释任命，最后看离职后的投资报道。仅凭他出任CEO，无法反推最初收购就是为了后来上市，更无法据此解释尚未披露的私人动机。

在Noh获任联席CEO之前，Solidigm经历过一次临时领导层调整。公司于2022年11月2日宣布，董事会成员Woody Young获任President，负责财务、战略、企业发展、人力、法务和信息技术，并参与寻找新CEO；公告同时将SK海力士高管郭鲁正（Noh-Jung Kwak）列为代理CEO。次日，Blocks & Files记者Chris Mellor报道Rob Crooke已经离职，并刊出公司对临时领导层安排的确认。这段过渡补全了管理层时间线：公司成立时由原Intel负责人接续，随后由母公司高层暂时负责，再进入2023年的联席CEO阶段。

> 来源：Solidigm，2022年11月2日09:27 PDT，《Woody Young Named President of Solidigm》，[官方任命公告](https://news.solidigm.com/en-WW/219822-woody-young-named-president-of-solidigm/)；Blocks & Files，Chris Mellor，2022年11月3日08:56 UTC，《Solidigm CEO’s departure takes staff by surprise》，[原始报道](https://www.blocksandfiles.com/flash/2022/11/03/solidigm-ceos-departure-takes-staff-by-surprise/1601106)。

该报道还援引接近事件的人士称，员工是在公司对外声明发布时同步得知消息。对离任原因，文章提出过技术独立性与资本开支分歧的可能解释，却明确将其列为推测。能够纳入人物履历的是离任与临时管理安排；对技术路线和组织权责的讨论，应回到正式产品、交易及任命公告。2023年董事会强调熟悉业务与加速双方协同，正是在上述管理交接之后给出的新阶段目标。

> 来源：Blocks & Files，Chris Mellor，2022年11月3日，[离任报道原文](https://www.blocksandfiles.com/flash/2022/11/03/solidigm-ceos-departure-takes-staff-by-surprise/1601106)；Solidigm，2023年5月15日，《David M. Dixon and Kevin Noh Appointed Co-CEOs of Solidigm》，[董事会任命公告](https://news.solidigm.com/en-WW/226111-david-m-dixon-and-kevin-noh-appointed-co-ceos-of-solidigm/)。

人物照片｜Noh-Jung Kwak（郭鲁正），2022年11月临时接管Solidigm；照片刊于当年2月。

> 照片出处：SK hynix Newsroom，2022-02-24，[《SK hynix Nominates Kwak and Noh as Inside Board Directors Candidates》](https://news.skhynix.com/en/sk-hynix-nominates-kwak-and-noh-as-inside-board-directors-candidates/)；[原图](https://d18r0a86za96sg.cloudfront.net/wp-content/uploads/2022/02/14151127/%EA%B3%BD%EB%85%B8%EC%A0%95_CEO_%EB%A9%94%EC%9D%B8_01_%EA%B0%80%EB%A1%9C.jpg)。

人物照片｜Woody Young，2022年获任Solidigm President的董事会成员。

> 照片出处：Solidigm Newsroom，2022-11-02T09:27:00-07:00，[《Woody Young Named President of Solidigm》](https://news.solidigm.com/en-WW/219822-woody-young-named-president-of-solidigm/)；[原图](https://d21buns5ku92am.cloudfront.net/69634/images/449168-woody-young-c6feeb-large-1667347407.jpg)。

Noh的公开职业记录，首先指向战略、财务和资本配置。SK海力士2021年1月29日发布上年度财报时，明确把他列为执行副总裁、企业中心负责人及CFO，由他解释市场与经营情况。这是一份与收购进程同期的公司文件，证明他当时处于集团财务管理的位置。韩国财经媒体The Bell记者원충희在当年4月7日的报道，则将其描述为同时处理财务与战略的并购负责人，回顾了海力士收购、东芝存储投资及Intel NAND收购等经历。官方文件确认其财务岗位，记者同期报道补足其并购背景，两种来源共同显示，他的经验涉及技术业务选择与交易安排。

> 来源：SK海力士，2021年1月29日，[《SK hynix Inc. Reports Fiscal Year 2020 and Fourth Quarter Results》](https://news.skhynix.com/en/sk-hynix-inc-reports-fiscal-year-2020-and-fourth-quarter-results/)；The Bell，원충희，2021年4月7日，[《[CFO 워치 | SK하이닉스] M&A부터 ESG채권까지, 화려한 재무전략 주역들》](https://www.thebell.co.kr/front/newsview.asp?key=202104061550525920105633)，即《从并购到ESG债券，SK海力士财务战略的主要负责人》。

此后的公司公告显示，他的职责继续向市场与公司价值延伸。SK海力士在2022年2月的董事候选人公告中，把Noh列为总裁及首席营销官，说明他负责分析市场与客户趋势、寻找新的增长动能，并推动公司的“Financial Story”。这里的官方职务是CMO，不能因为他此前当过CFO，就在整个后续时间线中继续使用旧头衔。财务与客户视角相继集中到同一个人身上，也为理解他后来参与跨公司业务协调提供了背景。

> 来源：SK海力士，2022年2月24日，网页元数据显示2月23日，[《SK hynix Nominates Kwak and Noh as Inside Board Directors Candidates》](https://news.skhynix.com/en/sk-hynix-nominates-kwak-and-noh-as-inside-board-directors-candidates/)。


图4｜Kevin Noh相关任职与拟投资线索。2026年公告的任命日期与公告日期不同，正文分别说明；橙色节点是媒体报道，不是投资成交公告。

> 图源：[原文1](https://news.solidigm.com/en-WW/226111-david-m-dixon-and-kevin-noh-appointed-co-ceos-of-solidigm/)；[原文2](https://news.solidigm.com/en-WW/266116-solidigm-announces-new-co-ceos-xin-guo-and-richard-chin/)；[原文3](https://signal.sedaily.com/article/20081919)；[原文4](https://biz.chosun.com/stock/market_trend/2026/08/26/R6KUSH2MXREAPKS2Q2Y3B7ANHQ/)；[原文5](https://www.bloter.net/news/articleView.html?idxno=672192)。


Noh与Solidigm的联系在联席CEO任命前已经公开出现。首款联合企业SSD发布时，他代表SK海力士解释，这种合作既要增强NAND竞争力，也要推进集团的“Inside America”战略，并通过优化双方运营创造协同。这个同期表态说明，美国业务与技术合作本来就在他的工作范围内。它没有证明他个人发明了整个收购计划，却比事后根据职位升迁推测他的作用更有解释力：他参与的事情，是让制造厂商与美国SSD团队形成具体业务合作。

> 来源：SK海力士与Solidigm，2022年4月5日，[《SK hynix and Solidigm Introduce First Collaborative Product》](https://news.skhynix.com/en/sk-hynix-and-solidigm-introduce-first-collaborative-product/)。

2023年5月15日，Solidigm董事会宣布由David M. Dixon与Noh共同出任CEO。任命时，Dixon是Solidigm高级副总裁兼数据中心事业部总经理；Noh已经担任Solidigm首席业务官，同时是SK海力士总裁。董事会公开给出的理由，是两人具有已证明的领导能力，熟悉Solidigm的业务与技术，接下来的工作要加速两家公司能力的结合与协同。任命对应的是收购之后加速能力结合的阶段。

> 来源：Solidigm，2023年5月15日，[《David M. Dixon and Kevin Noh Appointed Co-CEOs of Solidigm》](https://news.solidigm.com/en-WW/226111-david-m-dixon-and-kevin-noh-appointed-co-ceos-of-solidigm/)。

人物照片｜Kevin Noh与David M. Dixon，2023年联席CEO任命公告配图。

> 照片出处：Solidigm，2023-05-15，[《David M. Dixon and Kevin Noh Appointed Co-CEOs of Solidigm》](https://news.solidigm.com/en-WW/226111-david-m-dixon-and-kevin-noh-appointed-co-ceos-of-solidigm/)；[原图](https://d21buns5ku92am.cloudfront.net/69634/images/483983-Kevin%20Noh%20and%20David%20Dixon-3631cc-large-1684099053.jpg)。

两人的履历体现出一种互补。Dixon来自Intel，长期从事工程与业务管理，经历覆盖SSD、NAND与Optane产品开发；Noh在SK电讯和SK海力士的经历集中于业务战略与并购，担任Solidigm首席业务官时负责探索新机会、扩展业务伙伴关系。这里需要保留一个边界：Dixon参与过Optane开发，是个人职业经历，不能据此改变第三章已经划明的收购资产范围。从这些履历与官方协同目标看，董事会希望把原业务的技术经营经验与母公司的战略、商业连接能力放到同一个领导层。

> 来源：Solidigm，2023年5月15日，[《David M. Dixon and Kevin Noh Appointed Co-CEOs of Solidigm》](https://news.solidigm.com/en-WW/226111-david-m-dixon-and-kevin-noh-appointed-co-ceos-of-solidigm/)。

这样的组合面对的工作，既包括内部资源协调，也包括外部客户信任。技术团队需要决定哪些项目继续投入、哪些产品与母公司的NAND组合；母公司需要知道追加资源会怎样影响集团回报；客户则关心产品路线是否稳定。联席CEO安排可以让两种经验参与同一决策，但不必然意味着两人按“技术归一人、财务归一人”机械划分。公告没有公布这样的正式分工，因而能够提出的解释是能力互补，不能进一步把内部权限或管理摩擦写成已经确认的事实。

任命发生时的存储周期尤其严峻。SK海力士后来披露，2023年全年集团营业亏损约7.73万亿韩元，这是公司按K-IFRS公布的集团口径，并非Solidigm的独立亏损。财报说明，NAND复苏相对缓慢，需要控制投资与成本，并通过增加企业SSD等高附加值产品改善盈利。把这个背景放到Noh任命旁边，可以看出整合任务需要同时回应技术和经营压力。但仅凭母公司财报，无法把Solidigm各年的亏损、现金缺口或转盈幅度具体量化。

> 来源：SK海力士，2024年1月25日，英文网页元数据显示1月24日，[《SK hynix Reports Financial Results for 2023, 4Q23》](https://news.skhynix.com/en/sk-hynix-reports-fourth-quarter-2023-financial-results/)。

周期低谷会使收购时的协同目标接受更严厉的检验。销售增长不能只靠增加产量，库存与售价下降可能使新增产量占用更多现金；降低成本也不能无差别削减验证与研发，否则会影响下一代产品。企业SSD团队必须把有希望转化为客户需求的技术保留下来，母公司则必须在短期压力与长期投入之间分配资源。这些是由行业商业模式推导出的管理要求，并非对Noh某项未披露措施的报道。判断他任内的经营贡献，仍需能够区分售价恢复、产品结构变化与具体管理措施的财务和产品记录。

人物叙事到这里还不能直接跳到赴美上市。2026年5月27日，Solidigm已经正式公告新一届联席CEO：Xin Guo在3月获任命，Richard Chin于5月1日上任。公告分别强调技术与工程执行，以及业务表现、流程和增长；Guo此前担任代理联席CEO与数据中心工程负责人，Chin具有SK集团投资、海力士商业整合及营销经验。新管理层的存在是已披露事实，Noh此时已不是现任负责人。公告没有详述他离开原岗位的完整过程，也没有公布完整的离职原因。

> 来源：Solidigm，2026年5月27日，[《Solidigm Announces New Co-CEOs Xin Guo and Richard Chin》](https://news.solidigm.com/en-WW/266116-solidigm-announces-new-co-ceos-xin-guo-and-richard-chin/)。

人物照片｜Xin Guo，2026年3月获任联席CEO；照片由Solidigm于5月27日发布。

> 照片出处：Solidigm，2026-05-27，[《Solidigm Announces New Co-CEOs Xin Guo and Richard Chin》](https://news.solidigm.com/en-WW/266116-solidigm-announces-new-co-ceos-xin-guo-and-richard-chin/)；[原图](https://d21buns5ku92am.cloudfront.net/69634/images/676920-Xin%20Guo_Solidigm-14f210-medium-1779819303.png)。

人物照片｜Richard Chin，2026年5月1日出任联席CEO；照片由Solidigm于5月27日发布。

> 照片出处：Solidigm，2026-05-27，[《Solidigm Announces New Co-CEOs Xin Guo and Richard Chin》](https://news.solidigm.com/en-WW/266116-solidigm-announces-new-co-ceos-xin-guo-and-richard-chin/)；[原图](https://d21buns5ku92am.cloudfront.net/69634/images/676917-Richard%20Chin_Solidigm-62a6bd-medium-1779818541.png)。

随后出现了使这条人物线更复杂的消息。《首尔经济》旗下Signal于2026年8月21日16时45分51秒发布李忠熙（이충희）的韩文独家报道，称Noh离开SK集团后，在美国成立私募基金管理公司TechBridge，并把Solidigm选为首个投资目标。报道援引投行与半导体行业人士，称该管理公司拟与Stonebridge共同组建基金，投资最多2万亿韩元。这个金额是媒体披露的拟议投资上限，不是已到账资金。报道同时回顾其参与Intel NAND收购的经历，从而把原来的收购与经营角色，连接到新的财务投资角色。

> 来源：《首尔经济》Signal，李忠熙，2026年8月21日，[《[단독] 노종원 前 하이닉스 사장, 사모펀드 만들어 솔리다임 兆단위 투자 [시그널]》](https://signal.sedaily.com/article/20081919)，即《独家：前SK海力士社长卢钟元成立私募管理公司，拟对Solidigm进行万亿韩元级投资》。

这则报道把Solidigm的融资讨论推进到具体的管理公司、共同投资方和项目基金。管理公司是组织投资、募集基金的经营主体，基金是出资者承诺与资产投资的载体，Solidigm股份交易则是基金最终使用资本的对象。设立管理公司、确定首个目标、招募投资者和完成股份交割，是不同阶段。只要其中一个阶段还没有完成，人物角色就应写成“拟参与投资”。把这些环节区分开，也才能看清此后IPO究竟是否成为基金回收资本的预期路径。

共同投资方随后得到更精确的报道。《朝鲜Biz》记者金钟容（김종용）8月26日公开的文章称，讨论中的主体是Stonebridge Holdings在美国的子公司Stonebridge Global，它与Stonebridge Capital属于不同投资主体。文章描述的是与Noh所设管理公司通过项目基金共同投资、取得少数股权的可能安排，并明确指出，当时SK海力士尚未最终确定外部融资，投资规模、结构与参与者也没有落实。文章注明曾于8月25日在Money Move栏目先行刊出。由此，不能把首发报道里的Stonebridge简写任意改成另一家同名关联机构，也不能把讨论中的俱乐部交易写成签署完成。

> 来源：《朝鲜Biz》，金钟容，2026年8月26日，[《SK하닉 결단만 나오면... 스톤브릿지, 노종원 전 사장과 솔리다임 공동 투자》](https://biz.chosun.com/stock/market_trend/2026/08/26/R6KUSH2MXREAPKS2Q2Y3B7ANHQ/)，即《等待SK海力士决定：Stonebridge拟与前社长卢钟元共同投资Solidigm》。

Bloter记者柳镐承（유호승）8月31日11时05分52秒的跟进报道，把进展放在团队与募集准备上：TechBridge Investment在当年8月于加州设立，并招聘具有并购、财务与量化分析背景的人才，筹备Solidigm项目基金，拟与Stonebridge Global共同募资。这些信息说明报道中的安排已经出现组织与人员层面的准备，却仍不能证明出资者完成认缴或股份已经交割。招聘分析人才也不能直接等同于AI技术团队加入Solidigm；这里需要处理的是投资分析、风险评估与基金募集。

> 来源：Bloter，柳镐承，2026年8月31日，9月1日更新，[《SK 출신 노종원 펀드, 솔리다임 딜 위해 AI·퀀트 인재 영입》](https://www.bloter.net/news/articleView.html?idxno=672192)，即《卢钟元创办的基金管理公司为Solidigm交易招募AI与量化人才》。

从管理者转向拟议投资者，会让同一家公司的评价问题发生变化。经营负责人需要确保产品、客户与现金周转能够持续；基金管理人还需要说明以什么价格取得什么权利，以及基金出资人通过分红、股份出售或未来上市如何退出。熟悉业务可以帮助识别技术和商业风险，但不会消除存储周期，也不会保证上市时点。假如投资最终落地，最有解释力的将是认购协议、股份权利、退出条款和关联安排。现有报道既不能据此推出私人利益动机，也不能证明任何未披露的利益输送。

到2026年10月1日，SK海力士正式说明，Solidigm的资本使用方案仍未决定，后续方案需要比较内部现金与外部资本对集团及现有股东的经济影响。这为人物故事划定了当前能够确认的终点：Noh曾处于集团财务和商业管理岗位，曾任Solidigm联席CEO，韩国媒体随后报道其创办管理公司并拟参与投资；但其基金是否募集完成、是否取得股份、条件如何，都仍需要正式文件。下一步要观察的不是他是否再次出现在报道标题中，而是投资是否签约和交割，以及若有上市申请，招股文件如何披露股东、关联交易与退出安排。

> 来源：SK海力士，2026年10月1日，[《Clarification Regarding Recent Media Reports on Solidigm》](https://news.skhynix.com/en/fact-11/)。


## 第五章　AI如何改变企业SSD的价值

Solidigm进入AI数据中心，依靠的是一条在Intel时期已经建立的技术路线。它曾面对的难题，是怎样让固态存储以能够接受的成本进入普通电脑和企业服务器；今天面对的难题，是怎样让容量持续扩大的数据集、模型和上下文及时到达计算设备。两者相隔多年，工程问题仍有连续性：处理器能算得更快，并不意味着整个系统能更快完成任务。存储的作用，是让计算设备少等数据，让已经保存的数据可以再次被使用。

这条连续性有明确的产品证据。公司公告显示，Intel与美光在2018年5月宣布生产、交付每单元四比特的3D NAND，采用64层结构。公告中的Intel技术负责人RV Giridhar将其称为浮栅3D NAND技术继续发展的结果，并把价值定位于数据中心和客户端的容量与成本。后来形成Solidigm企业SSD的技术，并非随着AI热潮才被创造出来；AI改变的是它能够进入的系统，以及客户愿意为哪些问题付费。

> 来源：Intel／Micron，2018年5月21日，《Micron and Intel Extend their Leadership in 3D NAND Flash memory》，[公司联合公告原文](https://www.intc.com/news-events/press-releases/detail/153/micron-and-intel-extend-their-leadership-in-3d-nand-flash)。

理解QLC，需要分开看单元密度和整盘表现。SLC、通常所称的双比特MLC、TLC、QLC，每个单元分别存储一、二、三、四个比特；按二进制编码的说明性计算，需要区分的状态数分别是二、四、八、十六，公式为状态数等于二的比特数次方。更多状态意味着读取时必须更精细地判断电荷对应的范围，写入与纠错也更复杂。密度提升不能自动推导出相同比例的整盘降价，更不能推导出所有工作负载下的性能提升：控制器、固件、备用容量、封装和制造良率都进入最后的结果。

> 来源：Solidigm，2023年7月16日，《QLC NAND Technology Is Ready for Mainstream Use in the Data Center》，[技术白皮书网页原文](https://www.solidigm.com/products/technology/qlc-nand-ready-for-mainstream-use-in-data-center.html)。状态数为作者说明性计算，只解释编码关系。

浮栅路线的意义也应放在这一层理解。Solidigm的上述白皮书把电压阈值窗口和单元隔离列为其技术特点，并说明了浮栅结构向高密度QLC发展的路径。企业客户最终购买的是整盘在规定环境下的可靠性和稳定表现，并不直接购买某一种单元名称。技术路线的优势，需要经过纠错、磨损均衡、数据保持和客户验证共同兑现；如果只以层数或者单元比特数判断企业SSD的竞争力，就会漏掉Intel时期积累的控制器与固件能力。

容量变化使这种系统能力更直观。Solidigm于2024年11月13日公布122.88TB版本的D5-P5336，当日的交付状态是向客户提供样品。公告说明这一版本与此前较低容量产品共享控制器，方便客户验证。这一容量规格已经远超早期PC SSD的容量尺度；但从样品到正式采购，仍需跨越服务器兼容、散热、故障处理和应用性能验证。从采样到规模采购，产品还要通过客户验证；这一步的完成时间与实际交付，决定新容量型号何时转化为收入。

> 来源：Solidigm，2024年11月13日，《Solidigm Extends AI Portfolio Leadership with the Introduction of 122TB Drive, the World’s Highest Capacity PCIe SSD》，[产品发布公告原文](https://news.solidigm.com/en-WW/243441-solidigm-extends-ai-portfolio-leadership-with-the-introduction-of-122tb-drive-the-world-s-highest-capacity-pcie-ssd/)。

AI训练中的持久存储，首先承担数据和模型状态的保存。训练过程反复读取输入数据，又需要定期写入检查点，以便故障之后恢复。读取、写入和恢复并非同一种负载：数据读取侧重持续带宽及并发供给，检查点则可能集中产生写入压力。NVIDIA的存储认证文档将这些过程分别纳入测试。因此，容量型QLC适合的读取层，与需要承担频繁写入的缓存层，可以采用不同介质和不同配置。客户要解决的是完整训练任务的等待时间，单盘容量无法概括全部需求。

> 来源：NVIDIA，《NVIDIA-Certified Storage》，官方在线文档，页面未标独立发布日期，2026年10月8日核阅，[认证文档原文](https://docs.nvidia.com/certification-programs/certified-storage/latest/nvidia-certified-storage.html)。

数据流经过的路径同样影响效率。NVIDIA工程师Adam Thompson与CJ Newburn在2019年介绍GPUDirect Storage时，已把本地或远程存储与GPU内存之间的直接数据路径作为问题核心，目标是减少经CPU内存中转产生的额外复制。这个例子说明，把数据存得更密只是基础设施的一部分；驱动、网络、文件系统和应用读取方式决定数据能否及时送达。对Solidigm而言，与系统厂商及软件栈合作，才有机会把闪存产品优势转化为客户可以验证的整体收益。


图5｜AI系统的内存与SSD职责。箭头表示可设计的数据分层关系，不代表每个工作负载都沿同一路径；SSD缓存的收益必须结合软件、访问模式和搬运成本验证。

> 图源：[原文1](https://developer.nvidia.com/blog/introducing-nvidia-bluefield-4-powered-inference-context-memory-storage-platform-for-the-next-frontier-of-ai)；[原文2](https://investors.coreweave.com/news/news-details/2026/CoreWeave-Signs-Multi-Year-Agreement-With-Solidigm-to-Strengthen-Its-Integrated-AI-Cloud-Platform/default.aspx)。


> 来源：NVIDIA Technical Blog，Adam Thompson、CJ Newburn，2019年8月6日，《GPUDirect Storage: A Direct Path Between Storage and GPU Memory》，[工程说明原文](https://developer.nvidia.com/blog/gpudirect-storage/)。

推理又带来了新的存储用途。模型生成内容时，KV cache保存注意力机制中已经计算的键和值，便于后续计算复用。正在参与生成的数据需要快速访问，而暂时不活跃但可能再次使用的上下文，可以由系统决定放到其他层。NVIDIA在2025年发布Dynamo时，说明了GPU内存、主机内存、本地SSD及网络存储之间的分层管理。这里的商业机会来自减少重复计算、提高可服务的上下文容量，而不是把所有数据一律迁到SSD。

> 来源：NVIDIA Technical Blog，Amr Elmeleegy、Harry Kim、David Zier等，2025年3月18日，《NVIDIA Dynamo, A Low-Latency Distributed Inference Framework for Scaling Reasoning AI Models》，[框架介绍原文](https://developer.nvidia.com/blog/?p=95274)。

这也划定了SSD与HBM之间的边界。NVIDIA于2026年3月介绍CMX时，将活跃、对延迟敏感的KV放在GPU HBM层，把闪存扩展层作为可复用上下文的补充。SSD的大容量不能替代HBM在当前计算路径中的职责。缓存下放是否划算，取决于数据复用频率、恢复耗时、网络和软件开销，以及重新计算的成本。上下文缓存还是由计算产生、可以重建的数据，不能与必须长期保留的企业原始记录混为一谈。

> 来源：NVIDIA Technical Blog，Moshe Anschel、Einav Zilberstein、Oren Duer、Kirill Shoikhet、Ronil Prasad，2026年3月16日，《Introducing NVIDIA BlueField-4-Powered CMX Context Memory Storage Platform for the Next Frontier of AI》，[分层架构原文](https://developer.nvidia.com/blog/introducing-nvidia-bluefield-4-powered-inference-context-memory-storage-platform-for-the-next-frontier-of-ai)。

Solidigm自己也在推进这种用途。其AI与生态营销负责人Ace Stryker于2026年3月发表的文章，介绍通过SSD保存额外上下文、将活跃KV继续留在GPU内存的实验。这份厂商材料支持的判断，是系统经过软件设计后可以让SSD参与推理性能优化。实验的加速效果需要依附其模型、输入内容、缓存命中和硬件配置；不能将一次上下文恢复的改善直接写成所有AI请求都能获得同样的提速，也不能把高性能SSD实验自动套用于容量型QLC产品。

> 来源：Solidigm，Ace Stryker，2026年3月10日，《KV Cache Data Offload to SSDs as an Active Performance Layer》，[技术文章原文](https://www.solidigm.com/products/technology/ssds-unlock-ai-inference-with-rag-and-kv-cache.html)。

QLC能否承担企业工作负载，还要看写入寿命的口径。Solidigm产品简介列出的122.88TB型号为192层QLC，其五年耐久规格为0.60次每日全盘写入、累计134.3PB写入；这些属于厂商产品规格，脚注明确采用与间接寻址单元对齐的32KB随机写入。它们不能视为任何小块随机写入下都成立的通用承诺。DWPD衡量的是相对于整盘容量的写入量，容量和实际写入模式都会影响客户对寿命的判断。

> 来源：Solidigm，《Solidigm D5-P5336 Product Brief》，2025年版权版本，第3页规格表、第4页脚注17—18，具体发布日期未标，[产品简介PDF原文](https://www.solidigm.com/content/dam/solidigm/en/site/products/technology/p5336-product-brief/documents/Solidigm-D5P5336-ProductBrief.pdf)。

写入放大是另一项约束。主机请求写入的数据量，与闪存内部实际写入的数据量，未必一致。小块更新与设备内部管理粒度不匹配时，会产生额外读取、修改和写入。Solidigm与纬颖合作的CSAL方案，采用较快的TLC SSD承担缓存，再将写入整理后送往容量型QLC SSD。这样的分层意味着高密度介质需要与软件及缓存设计共同工作；客户比较方案时，要把额外设备、软件维护和故障恢复成本一起计入。

> 来源：Solidigm，2025年8月5日，《Platform Optimization for Performance and Endurance》，[与纬颖合作的技术方案原文](https://www.solidigm.com/products/technology/platform-optimization-for-performance-and-endurance-qlc-csal.html)。

功耗和总拥有成本也必须放在一致条件下比较。每块盘的最大功率、每TB功率、机柜供电和整个存储系统的耗电，回答的是不同问题。若高容量盘减少了服务器、线缆和机柜数量，系统成本可能下降；若应用需要更多并发通道或者更严格的冗余配置，盘数则未必按容量同比缩减。上述产品简介中的效率比较是厂商建模，限定了混合HDD与TLC方案、全QLC方案及基础设施配置。它适合说明密度如何影响系统设计，不能脱离条件改写为普遍适用的节电比例。

真正进入采购关系的证据，来自客户公告。CoreWeave于2026年8月5日宣布，与Solidigm签署多年战略协议，取得企业SSD容量的优先供应安排。其运营负责人Sachin Jain将存储放在公司整套AI平台能力之中；公告还把行业供应趋紧列为签订直接协议的背景。公告给出了多年优先供应的框架，合同金额及实际采购量仍待后续披露。它说明客户开始提前规划存储供给，未来收入则取决于实际交付。

> 来源：CoreWeave，2026年8月5日，《CoreWeave Signs Multi-Year Agreement With Solidigm to Strengthen Its Integrated AI Cloud Platform》，[客户投资者关系网站公告原文](https://investors.coreweave.com/news/news-details/2026/CoreWeave-Signs-Multi-Year-Agreement-With-Solidigm-to-Strengthen-Its-Integrated-AI-Cloud-Platform/default.aspx)。

对Solidigm而言，AI将多年积累的容量、固件和验证能力带进了更大的系统预算。接下来能验证这种变化的指标，应包括客户实际采购与交付、产品组合、制造成本、质保表现及现金流。需求增长、优先供应合同和产品容量都提供了线索，盈利能否持续则要看这些线索如何落到业务账本上。也正是在这里，技术故事与融资故事相接：如果公司要扩大供给，谁出钱、钱投到哪个法人，以及新增价值怎样分配，就成为必须回答的问题。


## 第六章　独立上市背后的资本选择

《首尔经济》记者李泰圭于2026年10月8日转述彭博前一日的消息称，Solidigm据报选定高盛与摩根士丹利为赴美上市的主承销行，交易可能在2027年进行，潜在筹资约100亿美元。这些数字与时间属于媒体披露的拟议方案；报道说明讨论仍在继续，细节可能调整，也可能有更多银行加入。承销行的选择使筹备工作更具体，但发行主体、股份结构与最终资金用途仍待正式文件明确。

> 来源：Bloomberg，2026年10月7日，《SK Hynix’s Solidigm Is Said to Pick Banks for US IPO Next Year》，[彭博原始报道链接，全文访问受限](https://www.bloomberg.com/news/articles/2026-10-07/sk-hynix-s-solidigm-is-said-to-pick-banks-for-us-ipo-next-year)；实际核阅：《首尔经济》，Lee Tae-kyu，2026年10月8日07:23:46，《SK hynix Picks Goldman, Morgan Stanley for Solidigm IPO》，[可读英文转述](https://en.sedaily.com/international/2026/10/08/sk-hynix-picks-goldman-morgan-stanley-for-solidigm-ipo)、[该页面提供的韩文原文链接，访问受限](https://www.sedaily.com/article/20099331)。英文页注明采用AI翻译；该转述与彭博消息同源。

上市议题并非在这一报道出现时才开始。SK海力士于2026年9月4日提交SEC的6-K，回应《韩国经济新闻》此前关于Solidigm筹划上市前融资的报道，说明使用Solidigm品牌的海外子公司在研究增强竞争力的多种措施，截至该文件日期尚未确定事项。监管回应确认讨论存在，但没有确认媒体所提方案已签约。因此，第四章中的基金筹组、上市前融资及当前承销行消息，可以组成资本活动的时间线，却不能彼此替代，证明其中任何一步已完成交割。

> 来源：SK hynix，2026年9月4日，Form 6-K，《Clarification Regarding Rumors or Media Reports》，[SEC申报原文](https://www.sec.gov/Archives/edgar/data/2120882/000119312526382688/d111778d6k.htm)。

发行安排尚未确定时，仍可以讨论公司为何考虑外部资金。SK海力士于2026年10月1日的正式说明给出了核心逻辑：集团同时面对HBM、服务器DRAM和企业SSD的投资需求，财务状况较强，不意味着所有项目都应使用内部现金；外部资金与内部资金必须比较对现有股东的经济影响。公司还明确表示，Solidigm的资本方案截至当日没有决定。这份说明把问题放在整个集团的资本配置中，避免了将上市简单解释为公司缺钱。

> 来源：SK hynix，2026年10月1日，《Clarification Regarding Recent Media Reports on Solidigm》，[公司正式说明原文](https://news.skhynix.com/en/fact-11/)。

这种资本选择可以从业务差异理解。HBM和企业SSD都进入AI基础设施，却由不同产品、制造与客户体系支撑。集团资金投入其中一种业务，就暂时不能以同样方式投入另一种业务。借助外部股权，可能让企业SSD扩张与其他项目同时推进；内部出资，则能保留更多未来收益。前者会引入新股东及其治理要求，后者占用集团现金并增加自身承担的周期风险。是否选择上市，最终要比较项目收益、融资成本与扩张时点，不能只比较集团账上还有多少现金。

要讨论这些权衡，先要问清“Solidigm”到底指哪一个法人。SK海力士在2026年1月28日宣布设立美国AI解决方案公司时，已经披露了重组方向：旧Solidigm法人，即SK hynix NAND Product Solutions Corp.，保留法人身份并转为AI Company；原有经营业务转入新设子公司Solidigm Inc.，继续使用Solidigm品牌。品牌延续与法人延续并非同一件事。拟上市主体究竟包含哪些资产、子公司、合同和负债，仍应由具体发行文件确认。

> 来源：SK hynix，2026年1月28日，《SK hynix to Establish U.S. Arm Specialized in AI Solutions》，[重组公告原文](https://news.skhynix.com/en/sk-hynix-to-establish-ai-solutions-arm-in-us/)。

图6｜SK海力士2026年1月公告的重组安排。原法人拟保留并更名，经营业务转给新Solidigm子公司；该示意不证明全部步骤已完成，也不预判最终IPO资产范围。

> 图源：[原文1](https://news.skhynix.com/en/sk-hynix-to-establish-ai-solutions-arm-in-us/)。

大连工厂的股权位置，在随后公开的财报中更加明确。SK海力士于2026年8月提交的半年度报告，将截至6月末从事半导体制造的SK hynix Semiconductor（Dalian）Co., Ltd.列为SK hynix Inc.直接控制、集团持股100%的公司；美国Solidigm Inc.则由SK hynix NAND Product Solutions Corp.控制。同表另有Solidigm NAND Product Solutions（Dalian）Co., Ltd.，位于英国子公司之下，业务为半导体销售。两家名称带有大连的公司承担不同职能，不能把销售法人当作晶圆工厂，也不能仅凭Solidigm品牌就把制造资产纳入美国经营公司的持股链。

这份报告还确认，NAND与SSD销售、研发及相关资产负债已经在上半年转入新Solidigm Inc.，部分相关子公司转移仍在继续。随后事项注明，大连制造公司与其制造支持子公司的合并于7月1日生效。这是大连两家法人之间的合并，参与方并不包含美国Solidigm，不能把这一变化写成大连工厂并入拟上市公司。历史收购将这些能力带入集团，当前资本安排则必须重新辨认每项资产所在的法人。

> 来源：SK hynix，2026年8月18日，Form 6-K，《Semi-Annual Business Report》及所附《Condensed Consolidated Interim Financial Statements》，附注1（2）第10—12页及脚注4、6，附注36（2）第70页；[SEC原始申报链接](https://www.sec.gov/Archives/edgar/data/2120882/000119312526354777/d147827d6k.htm)、[实际核阅的同份原文件数字转写](https://financialfilings.com/filings/sk-hynix-inc/interim-quarterly-report/2026/56530973/)。原站正文超出读取端单页大小限制，数字转写可读；持股关系以财报日期为准。

图7｜截至2026年6月30日，SK海力士合并财报所列控制关系。百分比为集团有效权益，不能当作各条直接持股比例。大连销售法人另列，图中省略；现有结构不预设未来IPO资产范围。

> 图源：[原文1](https://www.sec.gov/Archives/edgar/data/2120882/000119312526354777/d147827d6k.htm)。

工厂与经营公司分处不同股权路径，也不意味着经营公司可以脱离制造。长期供货安排仍可能把它们的经济利益连接起来：谁获得产出、采购价格如何调整、良率下降和设备折旧由谁承担，会决定产品利润留在哪本账。若采购按成本加成定价，需要核对成本定义及加成方式；若按市场条件采购，则要核对价格周期和议价机制。设备取得、维护及扩产条件又会影响供货数量和制造成本。这些是关联交易机制的分析，具体采用哪一种安排，仍须供货合同或发行文件证明。

这次重组还带有一笔面向AI Company的资金承诺。SK海力士在1月28日公告中宣布承诺100亿美元，按照capital call，即项目实际资金调用方式投入，支持AI投资与解决方案业务。这是集团对AI Company的出资安排；媒体最新报道的相同量级潜在IPO融资，则对应另一项拟议交易。两笔资金的接受主体、调用条件与用途需要分别辨认，现有公告没有把全部承诺列为Solidigm企业SSD的资本开支。

> 来源：SK hynix，2026年1月28日，《SK hynix to Establish U.S. Arm Specialized in AI Solutions》，[重组与出资公告原文](https://news.skhynix.com/en/sk-hynix-to-establish-ai-solutions-arm-in-us/)。

重组后账本边界的重要性，在财务分析中尤其突出。旧法人的收入、融资和投资活动，不一定在新经营公司保持原样；集团内部资金往来，也可能随资产转移重新安排。判断未来上市公司的盈利和偿债能力，需要核对分拆财务、债务归属、内部贷款、税务及关联交易。历史亏损或旧实体负债可以解释企业曾经历什么，却不能在没有调整依据时直接当作拟上市公司的当前财务状态。投资者要买的是发行范围中的权益，品牌名称只能帮助识别业务。


大连的生产能力，还需要放在设备取得方式中理解。美国商务部工业与安全局于2025年9月2日公布最终规则，将Intel Semiconductor (Dalian) Ltd等三家公司从中国的“经验证最终用户”名单中移除，2025年12月31日生效。这个名单原本允许符合条件的受控物项使用一般授权出口；移除意味着原有授权路径发生变化，不能据此推导大连工厂被要求全部停产。工厂能否取得某项设备，仍要看物项和许可证条件。厂房、设备、工艺与合法供货条件是不同层次的能力，即使资本已经到位，也不能自动把它们同时取得。

> 来源：美国商务部工业与安全局，2025年9月2日，最终规则《Revocation of Validated End-User Authorizations in the People's Republic of China》，90 FR 42321，文件2025-16735，[规则全文](https://www.federalregister.gov/documents/2025/09/02/2025-16735/revocation-of-validated-end-user-authorizations-in-the-peoples-republic-of-china)。

2026年1月5日，美国人口普查局发布新的C79工厂许可证申报指引，说明此类获授权出口应按照BIS发给工厂的有效许可证办理，并由工厂传达相关条款。该指引证明许可和申报存在新的路径，却没有公开大连某条生产线的全部批准范围。因此，评价其后续扩张时，应分别核对厂房建成、设备采购和安装、工艺验证及量产时间。生产厂房完成，并不等于新增产能已经贡献销售；设备可以进厂，也不等于所有技术升级都已获准。对Solidigm而言，稳定且可持续的晶圆供给，才是把制造基地转化为客户交付能力的关键。

> 来源：美国人口普查局，2026年1月5日，《NEW BIS LICENSE TYPE C79 — Fab License》，[官方申报指引原文](https://content.govdelivery.com/accounts/USCENSUS/bulletins/4008e2b)。


上市能提供的一个功能，是让这部分业务直接接受资本市场定价。外部投资者可以围绕企业SSD的客户、技术、产能和现金流形成判断，公司也可能通过独立股权获得持续融资能力。美国业务与客户关系，为选择美国市场提供商业背景；但客户在美国，不能单独证明美国上市一定获得更高估值。具体证券、交易市场、会计披露要求及投资者需求，还要结合最终发行结构。现阶段可以解释选择的可能理由，不能替发行人宣布既定结论。

募集资金流向是另一个必须拆开的问题。如果公司发行新股，资金进入发行主体，用来支持其业务；如果已有股东出售股份，所得款项首先进入售股股东。两种安排也可能同时出现。扩产、补充运营资金、偿债和集团资本再配置，会对应不同的受益主体。即使报道使用“筹资”一词，尚未披露的新股与老股比例，也会影响这笔钱究竟解决谁的资金需求。新股与老股的比例，要由发行文件说明；它决定资金首先进入经营公司还是原有股东，也决定筹资与扩产之间有多直接的联系。

图8｜内部资金与外部股权融资的经济差别。新股和老股的资金流向是机制示意，不表示Solidigm已公布采用哪一种发行结构。

> 图源：[原文1](https://news.skhynix.com/en/fact-11/)。

韩国现有股东担心的利益分配，也可以由这个结构解释。母公司股东通过母公司持有子公司权益；引入外部股东之后，对同一业务未来收益的分享比例可能变化。若融资使公司获得此前无法完成的扩张，并产生足够新增价值，持股比例下降不一定意味着经济价值下降。若交易定价、关联交易或利益分配失衡，母公司股东也可能承担不利结果。因此，“双重上市”是治理与估值问题，不能仅凭上市层级判定它必然有利或者必然损害原股东。

这里最需要透明的是交易条款。引入私人资本时，普通股之外可能还有优先权、退出安排和治理条款；公开发行时，则需要明确谁发行、谁出售、谁保留控制权。如果此前媒体报道中的投资基金最终参与，投资价格和权利安排也应进入比较。对前管理者参与投资的分析，应落在是否签约、是否披露关联关系、如何定价及怎样处理利益冲突等可核实事项上。熟悉业务能够解释投资兴趣，却不能替代公开程序，也不能证明其与IPO构成已经确定的连续交易。

企业SSD的增长还必须接受存储产业周期检验。高容量产品需求上升，可以改善业务组合；客户提前取得供应安排，也有助于制造商规划生产。新增产能却会形成折旧和持续运营开支，采购节奏、供给扩张与产品切换进度会共同影响利润。上市估值需要回答的是增长能持续多久，以及为了兑现增长还必须投入多少现金。这里的重点从某一时点的需求，转向跨周期的盈利与现金回收能力。

上市也不会自动解决独立运营的问题。拟发行公司是否掌握其技术与客户合同，怎样向集团购买闪存或服务，工厂与知识产权归属何处，都会影响利润留在哪一层。母公司同时经营多种存储业务，还需要说明内部合作如何定价，以及外部小股东怎样获得公平的信息和待遇。所谓“独立”，既包括公司对外拥有自己的名称与产品，也包括经营账本能够被外部股东理解；后者要靠审计、合同和治理结构支撑。

截至本文所依据的2026年10月8日材料，能够确认的是：企业SSD正在被更直接地纳入AI平台的供给规划，集团已公布美国业务重组方向，并持续讨论内部与外部资金选项；承销行及筹资规模仍属媒体披露的方案。接下来的关键进展，应是正式确定的发行主体、融资协议或注册文件、分拆后的审计财务，以及资金用途与股权变化。只有这些材料出现，才能判断Intel留下的技术资产，在SK海力士体系里创造了多少可持续价值，以及这些价值如何在不同股东之间分配。



## 格洛可点评

Solidigm的历史说明，半导体业务的价值不能只由某个时点的利润判断。Intel留下的制造工艺、固件经验和客户认证，需要长期投入才能形成，也需要新的产品需求和资金条件才能继续发展。SK海力士收购之后，最值得观察的是两套能力如何在产品上结合：谁提供晶圆，谁承担控制器与固件开发，谁完成客户验证，谁保证交付。AI需求提供新的商业机会，但只有持续的产品和供货能力，才能把机会变为经营成果。

大连工厂尤其能检验这种结合是否扎实。工厂产权、技术知识产权与对客户出售SSD的主体，即使同属一个集团，也可能由不同公司承担。外部投资者分享的收益，取决于发行主体的资产与合同边界。如果制造端采用成本加成定价，成本变化和约定加成会影响经营公司的利润；如果采购按市场条件定价，晶圆周期价格则会以另一种方式进入成本。两类机制都需要结合供应保障和技术迁移理解。拥有可用的工厂与拥有可审计、可持续的供应权利，分别回答生产能力和股东收益的问题。

Kevin Noh由管理者走向潜在投资组织者，让这一故事增加了资本层面的观察角度。熟悉技术、客户和组织，可以帮助识别业务机会；基金设立、融资签约、投资交割和公开发行，却仍是不同事件。判断上市是否创造价值，应看资本如何进入、谁承担制造与周期风险、关联交易如何定价，以及新增投资是否改善客户供给。承销行消息只是一个进展节点。真正决定这笔历史性收购如何被重新评价的，将是独立财务、清楚的资产边界和能够兑现的现金流。

> 点评中的成本加成和市场采购为合同机制分析，不构成对未公开具体合同条款的确认。相关事实基础见SK hynix 2026年1月28日[美国业务重组公告](https://news.skhynix.com/en/sk-hynix-to-establish-ai-solutions-arm-in-us/)、2026年10月1日[资本方案说明](https://news.skhynix.com/en/fact-11/)，以及第四章列示的TechBridge韩文原始报道。


## 原始资料与出处

1. Intel / Micron，2005-11-21，[Micron And Intel Create New Company To Manufacture NAND Flash Memory](https://www.intel.com/pressroom/archive/releases/2005/20051121corp.htm)。

2. Intel，2008-09-08，[Intel Introduces Solid-State Drives for Notebook and Desktop Computers](https://www.intc.com/news-events/press-releases/detail/1338/intel-introduces-solid-state-drives-for-notebook-and)。

3. Micron / Intel，2018-01-08，[后续3D NAND研发分开与3D XPoint边界](https://investors.micron.com/news/press-release/2018/Micron-and-Intel-Announce-Update-to-NAND-Memory-Joint-Development-Program-01-08-2018/default.aspx)。

4. Intel / SK hynix，2020-10-20，[SK hynix to Acquire Intel NAND Memory Business](https://www.intc.com/filings-reports/all-sec-filings/content/0001193125-20-272580/d76122dex991.htm)。

5. Solidigm，2023-05-15，[David M. Dixon and Kevin Noh Appointed Co-CEOs of Solidigm](https://news.solidigm.com/en-WW/226111-david-m-dixon-and-kevin-noh-appointed-co-ceos-of-solidigm/)。

6. Intel / SEC，April Miller Boise (signature)，2025-03-27，[Form 8-K — Item 2.01 Completion of Acquisition or Disposition of Assets](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-25-000060/intc-20250327.htm)。

7. Solidigm，2026-05-27，[Solidigm Announces New Co-CEOs Xin Guo and Richard Chin](https://news.solidigm.com/en-WW/266116-solidigm-announces-new-co-ceos-xin-guo-and-richard-chin/)。

8. Seoul Economic Daily / Signal，이충희 / 李忠熙，2026-08-21，[[단독] 노종원 前 하이닉스 사장, 사모펀드 만들어 솔리다임 兆단위 투자 [시그널]](https://signal.sedaily.com/article/20081919)。

9. CoreWeave，CoreWeave, Inc.，2026-08-05，[CoreWeave Signs Multi-Year Agreement With Solidigm to Strengthen Its Integrated AI Cloud Platform](https://investors.coreweave.com/news/news-details/2026/CoreWeave-Signs-Multi-Year-Agreement-With-Solidigm-to-Strengthen-Its-Integrated-AI-Cloud-Platform/default.aspx)。

10. SK hynix，2026-10-01，[Clarification Regarding Recent Media Reports on Solidigm](https://news.skhynix.com/en/fact-11/)。

11. Bloomberg，2026-10-07，[SK Hynix’s Solidigm Is Said to Pick Banks for US IPO Next Year](https://www.bloomberg.com/news/articles/2026-10-07/sk-hynix-s-solidigm-is-said-to-pick-banks-for-us-ipo-next-year)。

12. Seoul Economic Daily，Lee Tae-kyu，2026-10-08，[SK hynix Picks Goldman, Morgan Stanley for Solidigm IPO](https://en.sedaily.com/international/2026/10/08/sk-hynix-picks-goldman-morgan-stanley-for-solidigm-ipo)。

13. ChosunBiz / 朝鲜Biz，김종용 / 金钟容，2026-08-26，[SK하닉 결단만 나오면... 스톤브릿지, 노종원 전 사장과 솔리다임 공동 투자](https://biz.chosun.com/stock/market_trend/2026/08/26/R6KUSH2MXREAPKS2Q2Y3B7ANHQ/)。

14. Bloter，유호승 / 柳镐承，2026-08-31，[SK 출신 노종원 펀드, 솔리다임 딜 위해 AI·퀀트 인재 영입](https://www.bloter.net/news/articleView.html?idxno=672192)。

15. Intel，原文未注明发布日期，[Establishing Intel](https://timeline.intel.com/1968/establishing-intel)。

16. Intel，原文未注明发布日期，[The Intel 1103 DRAM](https://timeline.intel.com/1970/the-intel-1103-dram)。

17. Intel，原文未注明发布日期，[Farewell to DRAM](https://timeline.intel.com/1985/farewell-to-dram)。

18. Apple，2005-11-21，[Apple Announces Long-Term Supply Agreements for Flash Memory](https://www.apple.com/newsroom/2005/11/21Apple-Announces-Long-Term-Supply-Agreements-for-Flash-Memory/)。

19. Intel / IM Flash Technologies / Micron SEC exhibit，2012-04-06，[Amended and Restated Supply Agreement](https://www.sec.gov/Archives/edgar/data/723125/000072312512000084/a2012q3ex10-110.htm)。

20. Intel Technology Journal / Atrato，Sam Siewert / Dane Nelson，2009-03，[Solid State Drive Applications in Storage and Embedded Systems](https://www.intel.com/content/dam/www/public/us/en/documents/research/2009-vol13-iss-1-intel-technology-journal.pdf)。

21. Intel，2012-11-05，[Intel Announces Intel SSD DC S3700 Series – Next-Generation Data Center Solid-State Drive](https://www.intc.com/news-events/press-releases/detail/1241/intel-announces-intel-ssd-dc-s3700-series-)。

22. Intel，2013-07，[Intel Solid-State Drive DC S3700 Series – Quality of Service](https://www.intel.com/content/dam/www/public/us/en/documents/technology-briefs/ssd-dc-s3700-quality-service-tech-brief.pdf)。

23. Intel / Micron，2015-03-26，[Micron and Intel Unveil New 3D NAND Flash Memory](https://www.intc.com/news-events/press-releases/detail/349/micron-and-intel-unveil-new-3d-nand-flash-memory)。

24. Intel / SEC，2018-02-16，[Intel Corporation 2017 Form 10-K](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-18-000007/a12302017q4-10kdocument.htm)。

25. Intel / SEC，2019-02-01，[Intel Corporation 2018 Form 10-K](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-19-000007/a12292018q4-10kdocument.htm)。

26. Micron / Intel / SEC，2018-01-08，[Micron and Intel Announce Update to NAND Memory Joint Development Program](https://www.sec.gov/Archives/edgar/data/723125/000072312518000007/ex991pr01082018.htm)。

27. Intel，2018-08-08，[Intel Poised to Shape the Future of Memory and Storage with Optane + QLC](https://download.intel.com/newsroom/2021/archive/2018-08-08-news-intel-poised-shape-future-memory-storage-optane-qlc.pdf)。

28. Intel，2020-07-23，[Intel Reports Second-Quarter 2020 Financial Results](https://www.intc.com/news-events/press-releases/detail/1402/intel-reports-second-quarter-2020-financial-results)。

29. Intel / SEC，2021-01-22，[Intel Corporation 2020 Form 10-K](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-21-000010/intc-20201226.htm)。

30. Intel，2007-03-26，[Intel to Build 300mm Wafer Fabrication Facility in China](https://www.intc.com/news-events/press-releases/detail/1050/intel-to-build-300mm-wafer-fabrication-facility-in-china)。

31. Intel，2007-09-08，[Intel Breaks Ground on Wafer Fabrication Facility in Dalian](https://www.intel.com/pressroom/archive/releases/2007/20070907corp_b.htm)。

32. Intel，2011-02-18，[Intel Corporation 2010 Form 10-K](https://www.intc.com/filings-reports/all-sec-filings/content/0000950123-11-015783/f56033e10vk.htm)。

33. Intel，2017-05-02，[Intel Launches Cloud-Inspired 3D NAND SSDs for Data Centers](https://download.intel.com/newsroom/2021/archive/2017-05-02-news-intel-launches-cloud-inspired-3d-nand-ssds-data-centers.pdf)。

34. Intel，2017-02-17，[Intel Corporation 2016 Form 10-K](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-17-000012/a10kdocument12312016q4.htm)。

35. SK hynix / Intel，2020-10-20，[SK hynix to Acquire Intel NAND Memory Business](https://news.skhynix.com/en/sk-hynix-to-acquire-intel-nand-memory-business/)。

36. SK hynix，2021-12-30，[SK hynix completes the First Phase of Intel NAND and SSD Business Acquisition](https://news.skhynix.com/en/sk-hynix-completes-the-first-phase-of-intel-nand-and-ssd-business-acquisition/)。

37. Solidigm，2021-12-30，[Introducing Solidigm - A Market Leader in NAND Flash Technology](https://d21buns5ku92am.cloudfront.net/69634/pdf/campaigns/212941-20220401092445000000000-introducing-solidigm-a-market-leader-in-n.pdf)。

38. Solidigm，2022-11-22，[A New Paradigm at One Year](https://news.solidigm.com/en-WW/220582-a-new-paradigm-at-one-year/)。

39. SK hynix，2021-01-29，[SK hynix Inc. Reports Fiscal Year 2020 and Fourth Quarter Results](https://news.skhynix.com/en/sk-hynix-inc-reports-fiscal-year-2020-and-fourth-quarter-results/)。

40. SK hynix Newsroom，SK hynix，2022-02-24，[SK hynix Nominates Kwak and Noh as Inside Board Directors Candidates](https://news.skhynix.com/en/sk-hynix-nominates-kwak-and-noh-as-inside-board-directors-candidates/)。

41. SK hynix / Solidigm，2022-04-05，[SK hynix and Solidigm Introduce First Collaborative Product](https://news.skhynix.com/en/sk-hynix-and-solidigm-introduce-first-collaborative-product/)。

42. SK hynix，2024-01-25，[SK hynix Reports Financial Results for 2023, 4Q23](https://news.skhynix.com/en/sk-hynix-reports-fourth-quarter-2023-financial-results/)。

43. SK hynix，2026-01-28，[SK hynix to Establish U.S. Arm Specialized in AI Solutions](https://news.skhynix.com/en/sk-hynix-to-establish-ai-solutions-arm-in-us/)。

44. The Bell / 더벨，원충희，2021-04-07，[[CFO 워치 | SK하이닉스] M&A부터 ESG채권까지, 화려한 재무전략 주역들](https://www.thebell.co.kr/front/newsview.asp?key=202104061550525920105633)。

45. Intel / SEC，Susie Giordano (signature)，2020-10-20，[Form 8-K — Item 1.01 Entry into a Material Definitive Agreement](https://www.sec.gov/Archives/edgar/data/50863/000119312520272580/d76122d8k.htm)。

46. SK hynix / Korea Exchange KIND，김우현 / 金佑贤 (preparer)，2025-03-28，[주요사항보고서(영업양수결정) — 정정신고](https://kind.krx.co.kr/external/2025/03/28/000061/20250328000194/11336.htm)。

47. Intel / SEC，David Zinsner (signature)，2022-04-28，[Form 10-Q — Quarter ended April 2, 2022; Note 7 Acquisitions and Divestitures](https://www.intc.com/filings-reports/quarterly-reports/content/0000050863-22-000020/0000050863-22-000020.pdf)。

48. Solidigm Newsroom，Solidigm，2022-11-02T09:27:00-07:00，[Woody Young Named President of Solidigm](https://news.solidigm.com/en-WW/219822-woody-young-named-president-of-solidigm/)。

49. Intel / Micron，2018-05-21，[Micron and Intel Extend their Leadership in 3D NAND Flash memory](https://www.intc.com/news-events/press-releases/detail/153/micron-and-intel-extend-their-leadership-in-3d-nand-flash)。

50. Solidigm，2023-07-16，[QLC NAND Technology Is Ready for Mainstream Use in the Data Center](https://www.solidigm.com/products/technology/qlc-nand-ready-for-mainstream-use-in-data-center.html)。

51. Solidigm，Solidigm Corporate Communications，2024-11-13，[Solidigm Extends AI Portfolio Leadership with the Introduction of 122TB Drive, the World’s Highest Capacity PCIe SSD](https://news.solidigm.com/en-WW/243441-solidigm-extends-ai-portfolio-leadership-with-the-introduction-of-122tb-drive-the-world-s-highest-capacity-pcie-ssd/)。

52. Solidigm，2025 copyright; precise publication date not displayed; retrieved 2026-10-08，[Solidigm D5-P5336 Product Brief](https://www.solidigm.com/content/dam/solidigm/en/site/products/technology/p5336-product-brief/documents/Solidigm-D5P5336-ProductBrief.pdf)。

53. NVIDIA，online documentation; publication date not displayed; retrieved 2026-10-08，[NVIDIA-Certified Storage](https://docs.nvidia.com/certification-programs/certified-storage/latest/nvidia-certified-storage.html)。

54. NVIDIA Technical Blog，Adam Thompson; CJ Newburn，2019-08-06，[GPUDirect Storage: A Direct Path Between Storage and GPU Memory](https://developer.nvidia.com/blog/gpudirect-storage/)。

55. NVIDIA Technical Blog，Amr Elmeleegy; Harry Kim; David Zier; Kyle Kranen; Neelay Shah; Ryan Olson; Omri Kahalon，2025-03-18，[NVIDIA Dynamo, A Low-Latency Distributed Inference Framework for Scaling Reasoning AI Models](https://developer.nvidia.com/blog/?p=95274)。

56. NVIDIA Technical Blog，Moshe Anschel; Einav Zilberstein; Oren Duer; Kirill Shoikhet; Ronil Prasad，2026-03-16，[Introducing NVIDIA BlueField-4-Powered CMX Context Memory Storage Platform for the Next Frontier of AI](https://developer.nvidia.com/blog/introducing-nvidia-bluefield-4-powered-inference-context-memory-storage-platform-for-the-next-frontier-of-ai)。

57. Solidigm，Ace Stryker，2026-03-10，[KV Cache Data Offload to SSDs as an Active Performance Layer](https://www.solidigm.com/products/technology/ssds-unlock-ai-inference-with-rag-and-kv-cache.html)。

58. Solidigm，2025-08-05，[Platform Optimization for Performance and Endurance](https://www.solidigm.com/products/technology/platform-optimization-for-performance-and-endurance-qlc-csal.html)。

59. SK hynix / SEC，SK hynix; signed by Seonghwan Park, Head of Investor Relations，2026-09-04，[Form 6-K: Clarification Regarding Rumors or Media Reports](https://www.sec.gov/Archives/edgar/data/2120882/000119312526382688/d111778d6k.htm)。

60. SK hynix / SEC，SK hynix; signed by Seonghwan Park, Head of Investor Relations，2026-08-18，[Form 6-K: Semi-Annual Business Report and Condensed Consolidated Interim Financial Statements](https://www.sec.gov/Archives/edgar/data/2120882/000119312526354777/d147827d6k.htm)。

61. Blocks & Files，Chris Mellor，2022-11-03，[Solidigm CEO’s departure takes staff by surprise](https://www.blocksandfiles.com/flash/2022/11/03/solidigm-ceos-departure-takes-staff-by-surprise/1601106)。

62. SK hynix Newsroom，SK hynix，2019-10-10，[Interview with SK hynix CEO Seok-hee Lee, “curiosity has shaped me”](https://news.skhynix.com/en/interview-with-sk-hynix-ceo-seok-hee-lee-curiosity-has-shaped-me/)。

63. Intel Free Press，原文未注明发布日期，[Gordon Moore with Robert Noyce at Intel in 1970](https://www.flickr.com/photos/intelfreepress/8450997579/)。

64. Intel Corporation，2017-10-03，[Former Intel CEO Paul S. Otellini Dies at Age 66](https://www.intc.com/news-events/press-releases/detail/199/former-intel-ceo-paul-s-otellini-dies-at-age-66)。

65. Intel，2019-01-31，[Intel Names Robert Swan CEO](https://www.intc.com/news-events/press-releases/detail/96/intel-names-robert-swan-ceo)。

66. 美国商务部工业与安全局，2025-09-02，[Revocation of Validated End-User Authorizations in the People’s Republic of China](https://www.federalregister.gov/documents/2025/09/02/2025-16735/revocation-of-validated-end-user-authorizations-in-the-peoples-republic-of-china)。

67. 美国人口普查局，2026-01-05，[NEW BIS LICENSE TYPE C79 — Fab License](https://content.govdelivery.com/accounts/USCENSUS/bulletins/4008e2b)。

## 备注

资料时点为2026年10月8日。公司公告、监管文件与媒体拟议方案分别表述；Signal的TechBridge首发原文及后续韩文报道均已核阅。彭博原报道全文受限，最新承销行消息采用《首尔经济》可读转述，英文页标注AI翻译，未将同源转载计作独立佐证。

金额保留原币种；原始合同价、买方调整后付款、卖方净收款，以及出资承诺与潜在IPO筹资分别采用各来源口径。性能和耐久数据保留规格条件，不以厂商测试推算一般系统收益。总览图为AI生成的概念性工程示意，其他图由本文依据原始资料重绘。

读者提供的两页未署名初步融资材料使用匿名代称，且缺少脚注、日期和公开原址；正文据其提示展开制造与融资机制分析，没有把其中股权比例、估值或成本加成安排当作已确认交易。

格洛可｜2026年10月8日
