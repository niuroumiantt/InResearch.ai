# Solidigm赴美上市背后的技术传承与资本选择

2026年10月7日，彭博报道称，SK海力士旗下Solidigm据报已选定高盛与摩根士丹利，推进可能在2027年进行的美国首次公开募股。次日，《首尔经济》转述了这一消息。承销行选择意味着交易筹备可能进入更具体的阶段，但筹资规模、时间表与发行结构仍在讨论中。几乎同时，另一条资本线索也变得清晰：韩国媒体在8月报道，曾任Solidigm联席首席执行官的Kevin Noh离开SK后，在美国成立私募管理公司TechBridge，拟与Stonebridge一方筹组基金投资Solidigm。一位负责整合业务的管理者，又以潜在投资组织者的身份出现在同一家公司的资本故事里。

> 来源：Bloomberg，2026年10月7日，《SK Hynix’s Solidigm Is Said to Pick Banks for US IPO Next Year》，[首发报道](https://www.bloomberg.com/news/articles/2026-10-07/sk-hynix-s-solidigm-is-said-to-pick-banks-for-us-ipo-next-year)；《首尔经济》，Lee Tae-kyu，2026年10月8日，《SK hynix Picks Goldman, Morgan Stanley for Solidigm IPO》，[实际核阅的转述](https://en.sedaily.com/international/2026/10/08/sk-hynix-picks-goldman-morgan-stanley-for-solidigm-ipo)。Signal／《首尔经济》，李忠熙（이충희），2026年8月21日16:45:51韩国时间，《[단독] 노종원 前 하이닉스 사장, 사모펀드 만들어 솔리다임 兆단위 투자 [시그널]》，[韩文首发原文](https://signal.sedaily.com/article/20081919)。

理解这些变化，需要把视线拉回Intel。当年的NAND研发、SSD控制器与固件、数据中心客户，以及大连晶圆厂的制造能力，并不是在Solidigm成立时才出现的。它们在不同年代形成，又通过一笔分两阶段完成的收购进入SK海力士体系。今天，AI基础设施对存储容量与稳定供货提出新要求，集团也要在HBM、DRAM和企业SSD之间分配资本。<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">拟议上市因而同时涉及技术积累如何变成产品、制造成本如何进入经营账本，以及外部投资者究竟购买哪一层权益。</span>大连工厂贯穿其中：从Intel在中国建设生产基地，到3D NAND转产，再到跨国收购与潜在发行主体的供应关系，它影响的不只是产量，也包括资产、合同和利润的归属。

> 来源：Intel／SK hynix，2020年10月20日，《SK hynix to Acquire Intel NAND Memory Business》，[联合公告原文](https://www.intc.com/filings-reports/all-sec-filings/content/0001193125-20-272580/d76122dex991.htm)；SK hynix，2026年10月1日，《Clarification Regarding Recent Media Reports on Solidigm》，[资本方案说明](https://news.skhynix.com/en/fact-11/)。

本篇覆盖：Intel存储业务的起点、SSD与大连工厂、收购后的跨国产业布局、Kevin Noh的并购与经营经历、TechBridge、AI企业存储，以及独立上市的资产与资金边界。


## 第一章　Intel SSD从哪里来：从存储芯片到计算系统

Intel的存储历史比它作为处理器公司的公众形象更早。公司官方历史记录，1968年成立前，戈登·摩尔与罗伯特·诺伊斯讨论的新事业就以半导体存储器为基础。1970年推出的1103 DRAM，则推动计算机内存从磁芯转向半导体。这段历史的意义在于，Intel后来进入固态存储，能够调动已有的存储单元、工艺和计算平台经验。SSD业务的形成，应当放在这些能力重新组合的过程中理解。

> 来源： Intel官方历史档案，[《Intel的成立》（Establishing Intel）](https://timeline.intel.com/1968/establishing-intel)、[《Intel 1103 DRAM》](https://timeline.intel.com/1970/the-intel-1103-dram)，事件分别发生于1968年7月18日、1970年10月；网页未注明发布日期。


人物照片｜Intel联合创始人Gordon Moore（左）与Robert Noyce（右），1970年历史照片。

> 照片出处：Intel Free Press，网页未标日期，[《Gordon Moore with Robert Noyce at Intel in 1970》](https://www.flickr.com/photos/intelfreepress/8450997579/)；[原图](https://upload.wikimedia.org/wikipedia/commons/3/33/Gordon_Moore_with_Robert_Noyce_at_Intel_in_1970.png)。实际核阅的[图片说明与授权页](https://commons.wikimedia.org/wiki/File:Gordon_Moore_with_Robert_Noyce_at_Intel_in_1970.png)；原Flickr页当前访问受限。授权：[CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0/)，发布版仅缩放与JPEG编码。

在这段历史中，Intel曾经主动调整存储业务的边界。1985年宣布退出DRAM时，公司的内部解释指向价格下跌、需求疲弱和供给过剩，以及集中发展微处理器及相关产品的选择。DRAM是工作内存，NAND是断电后仍能保存数据的闪存，二者服务不同用途；退出某一类存储产品，并不意味着所有存储技术都失去战略价值。此后Intel重新扩大NAND投入，仍需在产品协同之外回答制造规模和资本回报的问题。

> 来源： Intel官方历史档案，[《告别DRAM》（Farewell to DRAM）](https://timeline.intel.com/1985/farewell-to-dram)，记录1985年10月10日事件及当时内部出版物，网页未注明发布日期。

通向后来Intel NAND SSD业务的关键组织节点，是与美光的合作。<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">2005年11月21日，两家公司宣布组建IM Flash Technologies，即IMFT。</span>按照当时披露的安排，美光持有合资公司51%的权益，Intel持有49%；双方计划各以现金、票据和资产投入约12亿美元作为初始出资。公告把美光的NAND开发与晶圆厂运营能力，同Intel的多层存储单元技术和闪存经验结合起来。Intel由此获得进入NAND大规模制造的合作平台。

> 来源： Intel与美光联合公告，[《美光与Intel成立新公司制造NAND闪存》](https://www.intel.com/pressroom/archive/releases/2005/20051121corp.htm)，2005年11月21日。持股为披露事实，初始出资为当时公告的计划安排。

这项合作首先面对的是消费电子需求。苹果同日宣布与海力士、Intel、美光、三星及东芝签订长期NAND供货协议，以支持iPod的生产。由这个客户案例可以看到，闪存的商业机会不只来自电脑升级：音乐播放器等设备需要更紧凑、抗振动的存储，也要求供应商稳定交付。对制造商而言，一个能够长期采购的客户，有助于把尚在建设中的产能同具体需求相连，降低只凭市场预测扩厂的不确定性。



图1｜Intel NAND与SSD业务形成及转手的主要节点。宣布投资、开始生产与交易交割分别列示。

> 图源：[原文1](https://www.intel.com/pressroom/archive/releases/2005/20051121corp.htm)；[原文2](https://www.intc.com/news-events/press-releases/detail/1338/intel-introduces-solid-state-drives-for-notebook-and)；[原文3](https://investors.micron.com/news/press-release/2018/Micron-and-Intel-Announce-Update-to-NAND-Memory-Joint-Development-Program-01-08-2018/default.aspx)；[原文4](https://www.intc.com/filings-reports/all-sec-filings/content/0001193125-20-272580/d76122dex991.htm)；[原文5](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-18-000007/a12302017q4-10kdocument.htm)；[原文6](https://news.skhynix.com/en/sk-hynix-completes-the-first-phase-of-intel-nand-and-ssd-business-acquisition/)；[原文7](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-25-000060/intc-20250327.htm)。


> 来源： 苹果公司公告，[《苹果宣布闪存长期供货协议》](https://www.apple.com/newsroom/2005/11/21Apple-Announces-Long-Term-Supply-Agreements-for-Flash-Memory/)，2005年11月21日。

资金安排也体现了客户与制造商的相互依赖。Intel和美光的合资公告披露，苹果拟分别向两家公司预付2.5亿美元，用于其各自分得的合资公司NAND产出。预付款对应未来供货，与股权投资具有不同性质；它将客户对供应安全的需求，转化为制造商提前获得的资金。随后留存于SEC的供货合同确认，IMFT与Intel的原始供货协议签订于2006年1月6日。宣布合资、建立供货关系、实现生产，是一条逐步落地的业务链。

> 来源： Intel与美光，[《美光与Intel成立新公司制造NAND闪存》](https://www.intel.com/pressroom/archive/releases/2005/20051121corp.htm)，2005年11月21日；Intel与IMFT，[《经修订及重述的供货协议》](https://www.sec.gov/Archives/edgar/data/723125/000072312512000084/a2012q3ex10-110.htm)，2012年4月6日，序言A确认2006年原协议日期。

拥有NAND产出之后，还要决定把闪存卖成什么产品。独立的闪存芯片，需要客户继续完成控制器设计、固件开发和系统验证；SSD则把这些工作集成到可以装入电脑和服务器的产品里。Intel能够从处理器与平台需求出发理解存储瓶颈，SSD成为其把上游介质技术向系统延伸的途径。它既可获得存储产品收入，也可帮助客户提高处理器的有效利用率。这种协同，正是Intel当年产品公告明确强调的卖点。

> 来源： Intel，[《Intel推出笔记本及台式机固态硬盘》](https://www.intc.com/news-events/press-releases/detail/1338/intel-introduces-solid-state-drives-for-notebook-and)，2008年9月8日；关于芯片与完整驱动器的分工为本文机制解释。

<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">2008年9月8日，Intel宣布X18-M和X25-M已经开始出货，面向笔记本和台式机，首批容量为80GB。公告突出并行十通道架构、自有控制器、固件及存储管理算法。</span>后者比单一容量规格更能说明这项业务的技术来源：Intel开始把NAND的物理性能转化为整盘的行为控制。一个SSD品牌能否持续获得企业客户认可，最终取决于介质与这些控制能力能否共同提供可靠、可预测的服务。

> 来源： Intel产品公告，[《Intel推出笔记本及台式机固态硬盘》](https://www.intc.com/news-events/press-releases/detail/1338/intel-introduces-solid-state-drives-for-notebook-and)，2008年9月8日。容量和通道数为产品披露规格。

控制器需要解决的基本问题，是让计算机看到一个稳定的存储地址空间，同时管理内部不断变化的闪存状态。NAND经过反复写入和擦除会逐渐磨损；如果频繁更新的数据总落在同一区域，就可能提前耗尽该区域的寿命。磨损均衡通过调整数据落点分散这一压力，写放大则衡量内部实际写入量相对主机要求写入量的增加。两者共同影响寿命与效率，因此固件的价值不能只用读写峰值来概括。

> 来源： Sam Siewert、Dane Nelson，[《固态硬盘在存储与嵌入式系统中的应用》](https://www.intel.com/content/dam/www/public/us/en/documents/research/2009-vol13-iss-1-intel-technology-journal.pdf)，Intel Technology Journal，2009年3月，印刷页30—33；上述为技术机制归纳。

在此基础上，面向个人电脑与面向数据中心的产品开始形成不同要求。电脑用户常直接感受开机、程序启动和文件打开速度；服务器则需要在长时间运行、并发访问和后台维护同时发生时保持响应。某次测试中速度很高，却在持续负载下出现明显波动的设备，会使系统容量规划更困难。企业采购因而会把数据保护、耐久、故障处理和性能一致性一并纳入评估。SSD业务由此逐步成为与客户系统共同设计和验证的业务。

> 来源： Intel，[《Intel DC S3700固态硬盘服务质量技术简报》](https://www.intel.com/content/dam/www/public/us/en/documents/technology-briefs/ssd-dc-s3700-quality-service-tech-brief.pdf)，2013年7月，页4—6、9—11；企业采购影响为本文分析。



图2｜每个NAND单元存储1、2、3、4 bit时，分别需要区分2、4、8、16种逻辑状态。柱长按状态数绘制，不表示实际阈值电压、速度或耐久。 工程组件为概念性技术插画。

> 图源：[原文1](https://www.solidigm.com/products/technology/qlc-nand-ready-for-mainstream-use-in-data-center.html)。


2012年11月5日发布的DC S3700，集中体现了这一变化。Intel把一致的性能、低延迟、端到端数据保护和高耐久列为核心特征，并通过NAND管理与芯片改进，争取在成本更低的MLC介质上实现较高耐久。<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">这个方向把竞争从“哪一种闪存单元更昂贵”推进到“整套设备能否满足工作负载”。</span>对后来的Solidigm而言，能够把不同介质特征组织成企业客户愿意采购的完整产品，构成重要的技术继承。

> 来源： Intel产品公告，[《Intel发布下一代数据中心固态硬盘DC S3700》](https://www.intc.com/news-events/press-releases/detail/1241/intel-announces-intel-ssd-dc-s3700-series-)，2012年11月5日。HET技术收益为厂商表述。

性能一致性还涉及存储系统的经营约束。假设一个服务需要等待多个存储操作完成，少量较慢请求也可能延长整个任务的完成时间。客户为了保住服务响应，可能减少每台服务器承载的业务，或者购买更多设备分担负载。这是说明性的系统逻辑，并非某款产品的实测收益。它解释了为什么客户会为稳定响应支付费用，也解释了企业SSD供应商为何需要理解应用、固件和服务器之间的关系。

> 来源： Intel，[《Intel DC S3700固态硬盘服务质量技术简报》](https://www.intel.com/content/dam/www/public/us/en/documents/technology-briefs/ssd-dc-s3700-quality-service-tech-brief.pdf)，2013年7月，页4、7、9—11；多请求等待及采购影响为本文说明性分析。

随着产品向企业场景延伸，上游介质也进入结构变化。2015年3月26日，Intel与美光公布采用浮栅单元的3D NAND，将存储单元垂直堆叠；首代公布架构为32层。二维NAND继续缩小单元会遭遇工艺与可靠性限制，垂直堆叠则提供增加单位面积容量的新途径。这个变化影响的不仅是芯片容量，还包括晶圆制造、控制器管理及整盘验证。产业需要把增加的存储密度转化为客户实际可用的容量。

> 来源： Intel与美光联合公告，[《美光与Intel公布新型3D NAND闪存》](https://www.intc.com/news-events/press-releases/detail/349/micron-and-intel-unveil-new-3d-nand-flash-memory)，2015年3月26日，Innovative Process Architecture部分。32层为披露架构，成本与耐久收益为当时厂商预期。

采用浮栅路线，是Intel技术谱系中的一个具体选择。它意味着后来移交的NAND业务带有自身的器件设计、制造工艺和控制经验，收购方需要理解并保留这些能力。不同技术路线的产品不能只按容量标签互换：介质的特征要进入固件管理与验证，才能成为稳定的成品。由此看，<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">Intel SSD的积累同时存在于晶圆端和系统端，既包括制造可用芯片的经验，也包括把芯片交付给企业客户的经验。</span>

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

<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">2015年10月，Intel宣布投资大连并将其转换为3D NAND制造基地；2016年7月，工厂进入3D NAND生产。</span>技术路径承接此前与美光联合开发的浮栅3D NAND：存储密度的提升，不再只依赖平面缩小，也依赖垂直层数与单元设计。对Intel SSD而言，制造端与产品端可以围绕介质特征、控制器及固件共同改进；对经营部门而言，它开始更直接地承担工艺导入与产能爬坡的费用。Intel的2016年报也把大连3D NAND爬坡成本列为影响当年NSG经营结果的因素之一。

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

更直接的依据来自出售公告。时任Intel首席执行官Bob Swan解释，这项交易使公司能够优先投资差异化技术，更深入参与客户成功并争取股东回报；公告列出的长期增长方向包括人工智能、5G网络和智能自主边缘。这里的“差异化”是公司对未来资源配置的判断，不能读成对NAND产品质量的否定。<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">Intel选择减少对NAND制造及其经营周期的直接承担，保留资金和组织空间支持另一些技术方向。</span>

> 来源： Intel与SK海力士，[《SK海力士收购Intel NAND存储业务》](https://www.intc.com/filings-reports/all-sec-filings/content/0001193125-20-272580/d76122dex991.htm)，2020年10月20日，Intel资金用途及Bob Swan发言；战略判断的含义为本文分析。


人物照片｜Bob Swan，2020年Intel出售NAND业务时的首席执行官；历史照片。

> 照片出处：Intel，2019-01-31，[《Intel Names Robert Swan CEO》](https://www.intc.com/news-events/press-releases/detail/96/intel-names-robert-swan-ceo)；[原图](https://d1io3yog0oux5.cloudfront.net/_a0dbd358c0dfe27d139bef6d4198de40/intel/news/96/973/image.jpeg)。

资产边界进一步显示了这项选择的具体性。<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">协议涵盖NAND SSD业务、NAND元件与晶圆业务，以及中国大连工厂，同时明确由Intel保留Optane。</span>这一点尤其重要，因为当年的Intel存储产品经常把两者放在同一个系统愿景中讨论，也都可能采用SSD形态。但技术愿景中的组合不等于交易中的共同出售。Solidigm继承的是被移交的NAND与相关SSD能力，Optane后来如何发展，需要另按Intel的资产与决定解释。

> 来源： Intel与SK海力士，[《SK海力士收购Intel NAND存储业务》](https://www.intc.com/filings-reports/all-sec-filings/content/0001193125-20-272580/d76122dex991.htm)，2020年10月20日，交易范围及Optane排除条款。

从买卖双方的视角看，同一项业务可以具有不同价值。Intel需要把NAND同自身的计算与制造投入比较；以存储为核心的买方，则可以考察企业SSD、技术能力和现有产能与其产品组合的关系。完整驱动器能够使制造商更接近最终客户，也让介质工艺在具体应用中获得定价机会。这样的互补提供了交易的商业理由，但整合能否实现目标，还取决于后续技术衔接、供货与客户保留，不能在签约时提前确认为收益。

> 来源： Intel与SK海力士，[《SK海力士收购Intel NAND存储业务》](https://www.intc.com/filings-reports/all-sec-filings/content/0001193125-20-272580/d76122dex991.htm)，2020年10月20日，双方业务定位及前瞻性声明；不同所有者对资产价值的判断为本文分析。

因此，Intel出售NAND可以沿着当时的证据解释：它已经形成介质和企业产品能力，也承担了制造投入；共同研发的安排转向各自优化，业务回报受到价格周期影响；整个集团随后选择重新排列差异化技术的优先级。这个判断不需要调用之后Intel或Solidigm的经营结果来补写动机。对收购方来说，下一步需要证明的，是接手后能否把制造与解决方案衔接起来，让投入、产品代际和客户需求形成连续的经营结果。

> 来源： 以上依据分别来自Intel历年年报、美光与Intel联合研发公告及2020年交易公告；本段为前述事实的分析归纳。


## 第三章　收购资产在AI时代的布局

到2026年10月，Intel原有的NAND与SSD业务，已经在SK海力士体系内形成跨地区分工：<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">中国大连承担晶圆制造，美国保留NAND与SSD研发及经营组织，销售和客户支持通过全球网络展开；今年的重组又为美国业务增加了面向AI战略投资与解决方案的平台。</span>这一布局的产业意义，在于把闪存生产、存储系统开发和企业客户需求连接起来。SK海力士获得的企业SSD能力，已经能够使用母公司的技术资源形成联合产品，并在AI基础设施中寻找新的需求。

> 来源：SK hynix，2026年8月18日，Form 6-K，《Semi-Annual Business Report》所附《Condensed Consolidated Interim Financial Statements》，附注1（2），印刷第10—12页，[SEC原始申报](https://www.sec.gov/Archives/edgar/data/2120882/000119312526354777/d147827d6k.htm)、[同份文件可读全文数字转写](https://financialfilings.com/filings/sk-hynix-inc/interim-quarterly-report/2026/56530973/)；Solidigm，2026年4月2日，[《Solidigm Expands Sacramento Development, Fueling Global AI Leadership》](https://news.solidigm.com/en-WW/263946-solidigm-expands-sacramento-development-fueling-global-ai-leadership/)；SK hynix，2026年1月28日，[《SK hynix to Establish U.S. Arm Specialized in AI Solutions》](https://news.skhynix.com/en/sk-hynix-to-establish-ai-solutions-arm-in-us/)。本段为当前布局的综合说明。



图3｜收购资产在2026年的布局：大连晶圆制造、美国SSD研发与经营、中国销售网络和美国AI战略投资平台承担不同职能。蓝线表示财报控制关系，虚线表示采访披露的FG晶圆供给；CTF为集团另一条产品协同路径；美国建厂另标为未确定的未来选项。 工程组件为概念性技术插画。

> 图源：[原文1](https://www.sec.gov/Archives/edgar/data/2120882/000119312526354777/d147827d6k.htm)；[原文2](https://news.skhynix.com/en/sk-hynix-to-establish-ai-solutions-arm-in-us/)；[原文3](https://news.solidigm.com/en-WW/263946-solidigm-expands-sacramento-development-fueling-global-ai-leadership/)；[原文4](https://www.marketscreener.com/news/sk-hynix-s-solidigm-unit-is-weighing-nand-memory-chip-factory-in-us-sources-say-ce785adad98cf221)；[原文5](https://www.tomshardware.com/pc-components/ssds/solidigm-vp-talks-pcie-6-0-ssds-next-gen-floating-gate-nand-liquid-cooled-storage-and-more-avi-shetty-vp-of-ai-solutions-and-market-enablement-discusses-the-future-of-enterprise-storage-tech)。


这张布局图首先有清楚的法人基础。半年度财报列明，<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">截至6月末，大连制造公司SK hynix Semiconductor（Dalian）Co., Ltd.由SK hynix Inc.控制，集团权益为100%；</span>美国旧法人SK hynix NAND Product Solutions Corp.也由母公司控制，集团权益为98.16%；新经营公司Solidigm Inc.由旧法人控制，集团权益为96.86%。后两个比例是集团有效权益，图中控制关系与直接持股比例分别处理。制造资产与美国SSD经营业务，处在集团内不同的控制路径。

> 来源：SK hynix，2026年8月18日，Form 6-K，《Semi-Annual Business Report》所附《Condensed Consolidated Interim Financial Statements》，附注1（2），印刷第10—11页，[SEC原始申报](https://www.sec.gov/Archives/edgar/data/2120882/000119312526354777/d147827d6k.htm)、[同份文件可读全文数字转写](https://financialfilings.com/filings/sk-hynix-inc/interim-quarterly-report/2026/56530973/)。比例为财报披露的集团权益口径，时点为2026年6月30日。

大连也不能只用一个公司名称来概括。财报另列Solidigm NAND Product Solutions（Dalian）Co., Ltd.，由英国业务法人控制，业务为半导体销售。它与晶圆制造公司分属不同路径。大连制造公司与旗下制造支持公司的合并，则于7月1日生效，参与方并不包含美国Solidigm。<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">销售法人提供当地交易组织，晶圆厂承担生产责任，客户渠道则覆盖全球市场。</span>把大连制造、当地销售与全球渠道分别呈现，才能看清从晶圆到客户的真实业务环节。

> 来源：SK hynix，2026年8月18日，Form 6-K，《Semi-Annual Business Report》所附《Condensed Consolidated Interim Financial Statements》，附注1（2）印刷第12页、附注36（2）第70页，[SEC原始申报](https://www.sec.gov/Archives/edgar/data/2120882/000119312526354777/d147827d6k.htm)、[同份文件可读全文数字转写](https://financialfilings.com/filings/sk-hynix-inc/interim-quarterly-report/2026/56530973/)；对销售法人职能范围的判断为本文分析。



图4｜大连制造公司、美国经营公司与大连销售公司分别溯源。销售公司由英国公司控制；财报将英国公司的控制方并列为原美国法人及新Solidigm，相关转移仍在进行。各节点百分比是集团有效权益。

> 图源：[原文1](https://www.sec.gov/Archives/edgar/data/2120882/000119312526354777/d147827d6k.htm)。


美国业务则在今年完成了经营主体的调整。<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">SK海力士1月宣布，保留原美国法人，安排其转向暂名AI Company的AI业务平台，将原经营业务移入新设Solidigm Inc.，继续沿用Solidigm品牌。</span>中期财报确认，NAND与SSD销售、研发及相关资产、合同、权利、员工和负债已在上半年转入新公司，部分相关子公司的转移仍在继续。因此，今天说Solidigm继承Intel技术与客户关系，指的是一条业务延续线；谈公司股权、经营责任或财务报表时，则必须辨认重组后的具体法人。

> 来源：SK hynix，2026年1月28日，[《SK hynix to Establish U.S. Arm Specialized in AI Solutions》](https://news.skhynix.com/en/sk-hynix-to-establish-ai-solutions-arm-in-us/)；SK hynix，2026年8月18日，Form 6-K，《Semi-Annual Business Report》所附《Condensed Consolidated Interim Financial Statements》，附注1（2），合并报表印刷第12页脚注4、6及独立报表第49页脚注4、5，[SEC原始申报](https://www.sec.gov/Archives/edgar/data/2120882/000119312526354777/d147827d6k.htm)、[同份文件可读全文数字转写](https://financialfilings.com/filings/sk-hynix-inc/interim-quarterly-report/2026/56530973/)。

美国一端的研发能力，也有今年的具体投入作证。Solidigm于4月2日公告，位于加州Rancho Cordova的总部及周边研发园区持续扩展，并通过NAND实验室和研发中心引入近100台新的NAND工具；公司还明确表示，其最高容量SSD由总部工程师推动设计。介质实验与整盘产品工程共同构成美国团队的研发基础。实验室承担探索、测试和验证，量产晶圆厂承担规模生产与持续交付，两者通过工艺和产品要求相互衔接。

> 来源：Solidigm Corporate Communications，2026年4月2日08:00 PDT，[《Solidigm Expands Sacramento Development, Fueling Global AI Leadership》](https://news.solidigm.com/en-WW/263946-solidigm-expands-sacramento-development-fueling-global-ai-leadership/)，园区、NAND工具及总部工程师段落；研发与量产的功能区分为本文分析。



实景照片｜Solidigm美国研发园区的NAND实验室，公司2026年4月2日公告配图；研发实验室与大连量产晶圆厂承担不同任务。

> 照片出处：Solidigm，2026年4月2日，[《Solidigm Expands Sacramento Development, Fueling Global AI Leadership》](https://news.solidigm.com/en-WW/263946-solidigm-expands-sacramento-development-fueling-global-ai-leadership/)；[官方原图](https://d21buns5ku92am.cloudfront.net/69634/images/664702-Solidigm%20Lab%2004-5316aa-large-1775070037.jpg)。


这一美国研发中心，又是全球工程组织中的重要部分。Solidigm在2023年正式将全球总部设于Rancho Cordova，目前官网仍列出San Jose、Longmont，以及温哥华、格但斯克、上海和台湾等办公地点。中期财报将上海和加拿大业务法人列为半导体研发主体。因此，准确的描述是，美国保留重要的NAND与SSD研发、产品经营能力，全球团队承担其他工程与客户工作；这些分布在不同地区的能力，最终围绕同一套产品研发与交付体系协作。

> 来源：Solidigm Corporate Communications，2023年2月7日，[《Solidigm Names Rancho Cordova Global Headquarters》](https://news.solidigm.com/en-WW/222801-solidigm-names-rancho-cordova-global-headquarters/)；Solidigm，[《Frequently Asked Questions》](https://www.solidigm.com/support/faqs.html)，Company章节，页面未标发布日期，核阅日为2026年10月8日；SK hynix，2026年8月18日，Form 6-K，《Semi-Annual Business Report》所附财务报表，附注1（2）印刷第11—12页，[SEC原始申报](https://www.sec.gov/Archives/edgar/data/2120882/000119312526354777/d147827d6k.htm)、[同份文件可读全文数字转写](https://financialfilings.com/filings/sk-hynix-inc/interim-quarterly-report/2026/56530973/)。

AI Company增加的是另一类能力。半年度财报显示，旧法人下已经设立SHIFTIX HOLDINGS LLC，后者再控制SHIFTIX1 LLC，两者业务均列为海外投资。这说明投资实体的组织建设已经展开。1月公告将其定位为AI战略业务平台，拟通过投资美国创新企业、建立合作关系，为客户提供更优化的AI数据中心方案，并连接SK集团成员企业。它与经营NAND及SSD产品的Solidigm Inc.具有不同任务：<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">一个围绕投资、伙伴和系统方案组织资源，一个围绕介质、驱动器与客户交付经营产品。</span>公告中的100亿美元是集团对AI Company的出资承诺，按实际资金调用方式投入，不能当作SSD工厂已经取得的建设预算。这种分工把成熟产品业务与新的战略探索连接起来，具体项目仍须按各自进展评价。

> 来源：SK hynix，2026年1月28日，[《SK hynix to Establish U.S. Arm Specialized in AI Solutions》](https://news.skhynix.com/en/sk-hynix-to-establish-ai-solutions-arm-in-us/)，AI战略、合作、法人重组及capital-call承诺段；SK hynix，2026年8月18日，Form 6-K，《Semi-Annual Business Report》所附合并财务报表，附注1（2）印刷第12页及脚注5、7，[SEC原始申报](https://www.sec.gov/Archives/edgar/data/2120882/000119312526354777/d147827d6k.htm)、[同份文件可读全文数字转写](https://financialfilings.com/filings/sk-hynix-inc/interim-quarterly-report/2026/56530973/)。业务分工的产业含义为本文分析；新设投资法人不等于全部设想中的合作已经投资完成。



图5｜2026年美国法人重组的已披露进展。新Solidigm承接SSD经营，原美国法人下另有SHIFTIX投资子公司；部分相关子公司转移仍在进行。AI Co.的100亿美元是集团资本承诺，不等于SSD上市募资。

> 图源：[原文1](https://news.skhynix.com/en/sk-hynix-to-establish-ai-solutions-arm-in-us/)；[原文2](https://www.sec.gov/Archives/edgar/data/2120882/000119312526354777/d147827d6k.htm)。


回看交易，当前结构并非一次付款就全部形成。<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">2020年10月公布的原协议总对价为90亿美元，覆盖NAND SSD、NAND组件与晶圆业务及大连设施，明确排除Optane。</span>原定首阶段支付70亿美元，取得SSD业务及相关知识产权、人员与大连有形设施；原定后阶段支付20亿美元，接续其余NAND制造和设计技术、研发人员与工厂员工。这些是签约时的合同安排。它把可以先移交的SSD经营与需要维持生产连续性的晶圆业务分开，让美国团队能够先接续客户和产品，而不是等待全部制造运营完成转换才开始工作。

> 来源：Intel与SK hynix，2020年10月20日，[《SK hynix to Acquire Intel NAND Memory Business》](https://www.intc.com/filings-reports/all-sec-filings/content/0001193125-20-272580/d76122dex991.htm)；Intel，2020年10月20日签署的Form 8-K，协议日期为美国时间10月19日，[《Item 1.01 — Entry into a Material Definitive Agreement》](https://www.sec.gov/Archives/edgar/data/50863/000119312520272580/d76122d8k.htm)。原定金额与分步安排为已披露合同事实，经营意义为本文分析。

两次交割之间，大连设施虽已转让，相关晶圆运营公司仍由Intel持有，并利用这些设施生产和供货。工厂产权、工艺技术、员工雇佣与产品销售，因而可以在过渡期分别归属。首阶段实际交割于2021年12月29日，Solidigm随之接续美国SSD业务，Rob Crooke出任CEO，李锡熙担任执行董事长参与整合。熟悉原产品的人继续经营，买方高层连接集团资源，这种安排为技术、客户与生产责任的逐步移交提供了组织基础。它也解释了为什么收购制造资产与取得完整运营能力，在历史上需要分阶段完成。

> 来源：Intel，2020年10月20日签署的Form 8-K，[《Item 1.01 — Entry into a Material Definitive Agreement》](https://www.sec.gov/Archives/edgar/data/50863/000119312520272580/d76122d8k.htm)，OpCo及制造销售协议段；Intel，2025年3月27日，[《Form 8-K，Item 2.01 — Completion of Acquisition or Disposition of Assets》](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-25-000060/intc-20250327.htm)；SK hynix，2021年12月30日，[《SK hynix completes the First Phase of Intel NAND and SSD Business Acquisition》](https://news.skhynix.com/en/sk-hynix-completes-the-first-phase-of-intel-nand-and-ssd-business-acquisition/)。



人物照片｜Rob Crooke，Solidigm首任CEO；照片来自2022年离任报道。

> 照片出处：Blocks & Files，2022-11-03，[《Solidigm CEO’s departure takes staff by surprise》](https://www.blocksandfiles.com/flash/2022/11/03/solidigm-ceos-departure-takes-staff-by-surprise/1601106)；[原图](https://image.blocksandfiles.com/125162.webp?format=jpg&height=1254&imageId=125162&width=960)。




人物照片｜Seok Hee Lee（李锡熙），首阶段交割时的Solidigm执行董事长；照片来自SK海力士2019年公告。

> 照片出处：SK hynix Newsroom，2019-10-10，[《Interview with SK hynix CEO Seok-hee Lee, “curiosity has shaped me”》](https://news.skhynix.com/en/interview-with-sk-hynix-ceo-seok-hee-lee-curiosity-has-shaped-me/)；[原图](https://d18r0a86za96sg.cloudfront.net/wp-content/uploads/2026/05/27201106/LeeSeok-hee_CEO_of_SK_hynix_interview_1.jpg)。


最终移交在2025年完成。Intel于3月27日披露第二阶段交割，净调整后收到约19亿美元，并终止此前的晶圆制造与销售协议；SK海力士翌日更正公告列明首阶段最终支付66.1亿美元，末阶段最终支付22.4亿美元。买方最终付款、卖方净调整后收款与原始合同价属于不同口径，不能混合计算。对今天布局更关键的是，晶圆业务与美国SSD业务已由同一集团接续，原有Intel过渡安排结束。集团可以重新组织研发、生产和商业合作，但各法人的职能并不因此自然合并。

> 来源：Intel，2025年3月27日，[《Form 8-K，Item 2.01 — Completion of Acquisition or Disposition of Assets》](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-25-000060/intc-20250327.htm)；SK hynix，2025年3月28日，[《주요사항보고서(영업양수결정) — 정정신고》，即《重大事项报告：业务受让决定更正公告》](https://kind.krx.co.kr/external/2025/03/28/000061/20250328000194/11336.htm)，第8及第17项。金额为各方已披露实际交割口径。

同一集团保留两套NAND技术，为这种分工增加了产品选择。SK海力士原有路线采用电荷捕获单元，即CTF，并结合单元下方外围电路等设计；Solidigm延续Intel的浮栅技术积累。2026年6月，Solidigm副总裁Avi Shetty在具名访谈中说明，公司继续为高密度QLC产品开发浮栅NAND，也可通过母公司获得CTF技术，自己研发控制器、固件与SSD，并与制造伙伴合作完成产品。这里的整合首先体现为技术与产品体系能够协同，而不要求全部制造设施、团队和技术立即改成同一种工艺。

> 来源：SK hynix，2022年10月27日，[《NAND Technology Development at SK hynix: Reaching New Heights》](https://news.skhynix.com/en/nand-development-history/)，CTF及PUC技术段；Tom’s Hardware，Anton Shilov，2026年6月26日，[《Solidigm VP talks PCIe 6.0 SSDs, next-gen floating gate NAND, liquid cooled storage and more》](https://www.tomshardware.com/pc-components/ssds/solidigm-vp-talks-pcie-6-0-ssds-next-gen-floating-gate-nand-liquid-cooled-storage-and-more-avi-shetty-vp-of-ai-solutions-and-market-enablement-discusses-the-future-of-enterprise-storage-tech)，对Avi Shetty的访谈。采用其技术与经营陈述，股权比例仍以财报为依据。

浮栅路线的意义也不能只用堆叠层数评价。Solidigm的技术白皮书将单元隔离、电压阈值窗口及控制器管理列为高容量QLC可靠性的重要因素。随着一个单元承载更多数据，介质设计、纠错和固件之间的配合，需要同时满足容量、耐久与数据保持要求。保留原有技术积累，使研发团队能够沿着熟悉的介质特性继续优化整盘，而不是为了形式上的统一就放弃已经形成的验证与工程经验。两种技术各有工程特点，集团可以按产品需求选择并继续改进。

> 来源：Solidigm，2023年7月16日，[《QLC NAND Technology Is Ready for Mainstream Use in the Data Center》](https://www.solidigm.com/products/technology/qlc-nand-ready-for-mainstream-use-in-data-center.html)，QLC架构、耐久与可靠性章节；技术选择的产业意义为本文分析。白皮书为厂商技术说明，不将其性能判断无条件推广至全部产品与负载。

双方已经有可检验的联合产品。2022年公布的P5530，采用SK海力士128层4D NAND，结合Solidigm的控制器和固件，支持PCIe第四代接口。当时属于有限发布，因此不能据此推算销量，但它证明整合能够发生在完整SSD的系统层：不同来源的NAND，经控制器、固件及验证配合，可以进入同一产品设计。对SK海力士而言，收购所补足的企业SSD能力，正是把介质工艺转化为客户可部署的设备；对Solidigm而言，母公司提供了原业务之外的介质与制造资源。

> 来源：SK hynix与Solidigm，2022年4月5日，美国发布日为4月4日，[《SK hynix and Solidigm Introduce First Collaborative Product》](https://news.skhynix.com/en/sk-hynix-and-solidigm-introduce-first-collaborative-product/)。产品规格及有限发布为公司已披露事实，整合意义为本文分析。

大连与美国团队之间的连接，最终要落实在生产和交付上。Shetty在同一访谈中表示，大连浮栅NAND产出用于企业存储，公司在全球保留客户支持、工程与销售组织。这条链条意味着，制造端不仅要提供可用晶圆，SSD团队还要把介质特性、固件版本和客户验证衔接起来。客户采购的是能够稳定运行并持续获得支持的驱动器。工厂制造能力扩大了供给基础，全球产品与服务组织则把这种供给转成企业客户能够接受的交付关系，两者共同构成收购后业务的实际价值。

> 来源：Tom’s Hardware，Anton Shilov，2026年6月26日，[《Solidigm VP talks PCIe 6.0 SSDs, next-gen floating gate NAND, liquid cooled storage and more》](https://www.tomshardware.com/pc-components/ssds/solidigm-vp-talks-pcie-6-0-ssds-next-gen-floating-gate-nand-liquid-cooled-storage-and-more-avi-shetty-vp-of-ai-solutions-and-market-enablement-discusses-the-future-of-enterprise-storage-tech)，Avi Shetty关于大连产出及全球客户支持、工程和销售的陈述；生产至交付的作用机制为本文分析。

分处不同法人，并不会消除生产上的相互依赖。晶圆采购承诺、定价和良率责任，会影响制造公司与SSD经营公司的利润分配；产品研发若改变介质要求，也会改变工厂投入和生产成本。把这些关系画成业务供给箭头，可以说明它们怎样合作，却不能仅凭股权表就写出未公开的采购价格。若某种安排采用成本加成，需要明确成本范围和加成机制；若按市场条件采购，则需考虑价格周期与议价方式。真正有产业意义的协同，是制造、研发和客户需求能够持续配合，并让各方对投入与回报承担清楚的责任。

> 来源：SK hynix，2026年8月18日，Form 6-K，《Semi-Annual Business Report》所附财务报表，附注1（2）印刷第10—12页，[SEC原始申报](https://www.sec.gov/Archives/edgar/data/2120882/000119312526354777/d147827d6k.htm)、[同份文件可读全文数字转写](https://financialfilings.com/filings/sk-hynix-inc/interim-quarterly-report/2026/56530973/)；Tom’s Hardware，Anton Shilov，2026年6月26日，[Avi Shetty访谈原文](https://www.tomshardware.com/pc-components/ssds/solidigm-vp-talks-pcie-6-0-ssds-next-gen-floating-gate-nand-liquid-cooled-storage-and-more-avi-shetty-vp-of-ai-solutions-and-market-enablement-discusses-the-future-of-enterprise-storage-tech)。本段为供货和关联交易机制分析，未将成本加成认定为现行公开合同事实。

现有布局之外，美国制造正在成为新的评估方向。路透社9月18日援引三名知情人报道，Solidigm考虑在美国建设NAND晶圆厂，纽约州北部是主要候选地区之一；这一项目与海力士同Intel讨论的俄亥俄州制造合作分开。SK海力士与Solidigm在报道中均表示尚未决定具体方案。因此，大连制造与美国研发构成当前业务基础，美国晶圆厂则是潜在扩张选项，不能画成已经具备的产能。

> 来源：Reuters，Hyunjoo Jin、Heekyong Yang、Karen Freifeld，2026年9月18日，[《Solidigm评估美国NAND工厂，纽约州北部为候选》路透社原稿转载](https://www.marketscreener.com/news/sk-hynix-s-solidigm-unit-is-weighing-nand-memory-chip-factory-in-us-sources-say-ce785adad98cf221)。MarketScreener保留路透社署名正文与公司回应；建厂仍为评估阶段。

AI时代使这套布局面对更直接的需求。CoreWeave在2026年8月正式公告与Solidigm签订多年协议，取得企业SSD容量的优先供应，说明存储产品开始更深入地进入AI云平台的供给规划。这份需求是在收购完成之后逐步形成的，当前布局的意义可以从今天的产品和客户关系中直接观察。中国制造提供介质供给，美国及全球工程组织提供控制器、固件与整盘产品，销售网络把产品带到数据中心，AI战略平台则扩大集团与系统伙伴合作的范围。这些能力让SK海力士在HBM支撑的计算环节之外，补足了AI数据中心持久存储的重要一环。收购的价值由此从取得一家NAND业务，延伸到能够围绕新需求组织生产、研发和交付。

> 来源：CoreWeave，2026年8月5日，[《CoreWeave Signs Multi-Year Agreement With Solidigm to Strengthen Its Integrated AI Cloud Platform》](https://investors.coreweave.com/news/news-details/2026/CoreWeave-Signs-Multi-Year-Agreement-With-Solidigm-to-Strengthen-Its-Integrated-AI-Cloud-Platform/default.aspx)；SK hynix，2021年12月30日，[《SK hynix completes the First Phase of Intel NAND and SSD Business Acquisition》](https://news.skhynix.com/en/sk-hynix-completes-the-first-phase-of-intel-nand-and-ssd-business-acquisition/)，移动NAND与企业SSD互补说明。协议金额与型号组合未公开，本段未据此估算收入或产能。


## 第四章　Kevin Noh：并购、经营与再次投资

Kevin Noh，即卢钟元（노종원，英文公告亦写Jongwon Noh），与Solidigm的联系早于他出任联席CEO。把他的职业记录放在一起，可以看到一条延续多年的路径：为SK进入半导体产业处理收购实务，参与跨国存储投资，进入海力士统筹战略与财务，再到被收购公司推进整合和经营，最后以外部基金管理人的身份谋求投资。贯穿这些岗位的，是如何把产业判断转化为资本安排，以及如何让取得的资产形成实际业务。Solidigm在2023年的任命公告直接肯定了他在SK电讯、SK海力士制定业务战略和领导并购的经验，这也是理解后续角色变化的起点。

> 来源：Solidigm，2023年5月15日，[《David M. Dixon and Kevin Noh Appointed Co-CEOs of Solidigm》](https://news.solidigm.com/en-WW/226111-david-m-dixon-and-kevin-noh-appointed-co-ceos-of-solidigm/)。



图6｜Kevin Noh从并购实务、集团财务与事业管理，到经营Solidigm，再到拟组织外部基金投资的履历。Intel交易签署在他出任CFO之前；两位President是集团内分工，不是双CEO。拟议基金投资与公司IPO筹备分别列示。

> 图源：[原文1](https://www.thebell.co.kr/front/newsview.asp?code=0401&key=202608101118098120103951)；[原文2](https://www.thebell.co.kr/front/newsview.asp?code=0401&key=201712070100011610000699)；[原文3](https://news.skhynix.com/en/sk-hynix-inc-reports-fiscal-year-2020-and-fourth-quarter-results/)；[原文4](https://news.skhynix.co.kr/executive-personnel-and-organizational-reorganization-2022/)；[原文5](https://news.solidigm.com/en-WW/226111-david-m-dixon-and-kevin-noh-appointed-co-ceos-of-solidigm/)；[原文6](https://signal.sedaily.com/article/20081919)；[原文7](https://www.mk.co.kr/news/stock/12162986)；[原文8](https://biz.chosun.com/stock/market_trend/2026/08/26/R6KUSH2MXREAPKS2Q2Y3B7ANHQ/)；[原文9](https://news.skhynix.com/en/sk-hynix-nominates-kwak-and-noh-as-inside-board-directors-candidates/)。


这条路径最早与海力士本身的易主相交。韩国财经媒体The Bell记者朴完俊在2026年的履历报道中写道，<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">卢钟元2011年仍在SK电讯任职，曾在海力士收购工作组负责实务。</span>SK电讯官方历史则把交易过程分为2011年11月的股权收购签约，以及2012年的收购与海力士更名启动。对原本以移动通信为核心的企业而言，这笔交易意味着进入需要持续研发和巨额设备投入的制造行业。参与交易实务的人面对的，既有股权价格和融资，也有一个更长远的问题：集团能否承接芯片业务的投资周期。卢钟元由此积累的是进入一个产业的交易经验，此时尚未担任海力士CFO。

> 来源：The Bell，朴完俊（박완준），2026年8月10日，[《노종원 사장, 1년만에 SK아메리카스 떠났다》](https://www.thebell.co.kr/front/newsview.asp?code=0401&key=202608101118098120103951)；SK电讯，2024年3月24日，[《[창사 40주년] SK텔레콤 10대 모먼트》](https://news.sktelecom.com/202452)。

到东芝存储出售时，他已经站到战略组织的前台。The Bell记者金一文2017年6月的报道，描绘了SK电讯新设的Portfolio Management组织：卢钟元领导这个负责新业务、投资与并购的部门，团队参与东芝存储交易。同年12月，金一文在其晋升报道中进一步描述，卢钟元作为投资实务人员，为谈判频繁赴日，并参与处理交易推进中的阻力。这些同期记录，比只看后来头衔更能说明其专业形成过程：他需要在不同投资人、产业公司和交易条件之间寻找可执行的方案。决定最终结构的仍是参与交易的企业与董事会，卢钟元的作用体现于谈判和组织落实。

> 来源：The Bell，金一文（김일문），2017年6月21日，[《[도시바 M&A] SK M&A 전략 산실 PM실에 ‘관심 집중’》](https://www.thebell.co.kr/front/newsview.asp?code=0705&key=201706210100038130002311)；同记者，2017年12月7日，[《SKT 전략 핵심 노종원 PM 실장, 전무로 파격승진》](https://m.thebell.co.kr/m/newsview.asp?newskey=201712070100010750000643&svccode=)。

东芝交易的结构，显示了战略投资与取得经营权之间的区别。按SK海力士2017年9月28日披露的投资方案，公司拟出资3950亿日元，其中1290亿日元用于可转换债券，未来可对应最多15%的表决权；另外2660亿日元以有限合伙人身份投入贝恩设立的基金，分享未来上市带来的资本收益。<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">同一公告所列40.2%，是东芝计划保留的表决权份额。海力士参加的是贝恩牵头的联合体，通过不同工具取得经济权益。</span>可转债保留未来转股的可能，基金出资则使产业公司参与资本收益，两者对应的权利和回收方式并不相同。

> 来源：SK海力士，2017年9月28日，[《SK hynix Inc.’s Board Approved a Plan to Invest in Toshiba Memory Corporation》](https://news.skhynix.com/en/sk-hynix-inc-s-board-approved-a-plan-to-invest-in-toshiba-memory-corporation-2/)。

这笔交易在2018年6月1日完成交割，后来成为海力士长期持有的存储投资。其后的回收也沿着不同资本工具分别展开：The Bell记者卢泰民2026年7月报道，SPC1对应的铠侠持仓已于6月出售完毕，海力士从基金投资路径获得回款，同时保留SPC2可转债投资。铠侠自身截至2026年3月末的证券报告也仍列出海力士持有的可转债，说明当时尚未转股。因此，这段经历包含参与交易、长期持有与部分资金回收，截至这一时点，资金回收与继续持有仍在并行。对人物主线而言，关键在于卢钟元曾参与安排一笔以基金和可转债进入存储产业的投资；后续回收则属于海力士这笔长期投资的资本记录。

> 来源：东芝，2018年6月1日，[《Notice Regarding Closing of the Sale of Toshiba Memory Corporation and Change to a Specified Subsidiary Company》](https://www.global.toshiba/content/dam/toshiba/migration/corp/irAssets/about/ir/en/news/20180601_1.pdf)；The Bell，卢泰民（노태민），2026年7月29日，[《[IR Briefing] SK하이닉스, 키옥시아 효과 덕 영업외손익 ‘62조’》](https://www.thebell.co.kr/front/newsview.asp?code=0301&key=202607291104412880106333)；铠侠控股，2026年6月，[《Annual Securities Report for the Fiscal Year Ended March 2026》](https://www.kioxia-holdings.com/content/dam/kioxia-hd/en-jp/ir/library/securities/asset/Annual-Securities-Report-FY2025-EN.pdf)，印刷第99页（PDF第102页）。

卢钟元在2018年末从SK电讯转入海力士，负责未来战略，随后参与Intel NAND业务收购。The Bell记者元忠熙2021年4月对海力士财务团队的报道，将东芝存储投资、Intel NAND收购和代工业务投资连在他的履历里，并指出，他来自寻找未来增长机会的并购战略岗位。Intel交易与东芝投资的差别在于，海力士此次要取得产品、团队、制造资产与技术，直接承担经营和整合结果。前一笔投资主要回答如何进入一家存储企业的资本结构，后一笔收购则需要回答怎样把取得的业务纳入自己的产业能力。对卢钟元而言，资本安排开始更紧密地连接运营责任。

> 来源：The Bell，元忠熙（원충희），2021年4月7日，[《[CFO 워치 | SK하이닉스] M&A부터 ESG채권까지, 화려한 재무전략 주역들》](https://www.thebell.co.kr/front/newsview.asp?key=202104061550525920105633)。

CFO任命进一步把两类责任放到同一个岗位上。The Bell记者金惠兰2021年1月29日报道，年末人事之后，卢钟元开始兼任CFO，接替离任的车镇锡，当天首次以这一身份出席财报电话会议。公司同日财报公告也明确把他列为经营支持负责人及CFO。到当年末晋升社长时，媒体又报道金宇贤被内定为继任者。<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">按公开的人事口径，他担任CFO的阶段约为2020年末至2021年末。这一顺序意味着，Intel收购签约时他主要处于战略岗位，进入等待监管批准和首次交割的阶段后，才把财务职责一并承担起来。</span>

> 来源：The Bell，金惠兰（김혜란），2021年1月29日，[《[CFO 워치 | SK하이닉스] 노종원 부사장, 안살림까지 총괄》](https://www.thebell.co.kr/front/newsview.asp?code=0401&key=202101290930276960105436)；SK海力士，2021年1月29日，[《SK hynix Inc. Reports Fiscal Year 2020 and Fourth Quarter Results》](https://news.skhynix.com/en/sk-hynix-inc-reports-fiscal-year-2020-and-fourth-quarter-results/)；The Bell，元忠熙，2021年12月2日，[《[CFO 워치 | SK하이닉스] 최연소 CFO 노종원 부사장, 최연소 사장 등극》](https://www.thebell.co.kr/front/newsview.asp?code=0705&key=202112021516373840108564)。

这个岗位变化并非只增加一个头衔。大型收购需要把交易付款、日常设备投资、库存占款与债务期限放进同一套安排，买方不能只证明资产值得买，还必须保证付款与持续经营能够衔接。金惠兰的同期报道特别强调，Intel业务分阶段取得，需要跨越数年的时间，因此战略和财务统筹具有实际意义。卢钟元首次以CFO身份公开发言时，同时表达了审慎投资和提高NAND成本竞争力的方向。由此看，他处理的是扩张与资金承受能力之间的关系。交易经验在这里接受的检验，是技术和客户价值是否足以支撑持续投入，以及集团能否为这种价值提供稳定资金。

> 来源：The Bell，金惠兰，2021年1月29日，[《[CFO 워치 | SK하이닉스] 노종원 부사장, 안살림까지 총괄》](https://www.thebell.co.kr/front/newsview.asp?code=0401&key=202101290930276960105436)。

2021年12月2日，海力士宣布郭鲁正与卢钟元共同晋升社长，分别领导新设的安全研发制造总括和业务总括组织。官方公告清楚写明，这些组织设在CEO之下：郭鲁正负责研发、生产与安全，卢钟元负责全球业务、未来增长战略及执行，李锡熙则以CEO身份兼任美洲业务负责人。<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">两位社长意味着经营职责的分工，并非两人同时出任CEO。</span>2022年2月的官方董事候选人公告进一步把卢钟元列为President及CMO，强调市场、客户趋势和新的增长动能。这使他的职责由筹措和使用资本，延伸到寻找能把技术能力转化为收入的市场。

> 来源：SK海力士，2021年12月2日，[《SK하이닉스, 2022년 조직개편 및 임원인사 단행》](https://news.skhynix.co.kr/executive-personnel-and-organizational-reorganization-2022/)；2022年2月24日，[《SK hynix Nominates Kwak and Noh as Inside Board Directors Candidates》](https://news.skhynix.com/en/sk-hynix-nominates-kwak-and-noh-as-inside-board-directors-candidates/)。

随后，卢钟元逐步进入Solidigm的经营体系。2022年4月，双方推出首款联合产品P5530时，他公开解释，合作旨在强化NAND竞争力、推进美国业务，并优化两家公司的运营。到7月，The Bell记者元忠熙报道，他兼任Solidigm的Chief Synergy Officer，即负责协同的高管。这一安排承接了收购后的问题：完成所有权转移后，团队仍需要协调产品、研发、客户和母公司的资源。资本交易让双方具备合作条件，经营整合才决定合作能带来什么结果。卢钟元此时要面对的对象，也从外部卖方与交易伙伴，转为内部团队、客户以及两家公司之间的决策关系。

> 来源：SK海力士与Solidigm，2022年4月5日，[《SK hynix and Solidigm Introduce First Collaborative Product》](https://news.skhynix.com/en/sk-hynix-and-solidigm-introduce-first-collaborative-product/)；The Bell，元忠熙，2022年7月12日，[《노종원 사장, SK하이닉스-솔리다임 통합 전진 배치》](https://www.thebell.co.kr/front/newsview.asp?code=0401&key=202207120720304860107075)。

2022年11月，Solidigm先经历了一次管理层调整：首任CEO Rob Crooke离任，郭鲁正临时接任CEO，董事会成员Woody Young获任President，负责财务、战略、企业发展和相关公司职能，并参与寻找新CEO。公司公告给出了职责安排；次日Blocks & Files的报道则记述员工对此感到意外。

> 来源：Solidigm，2022年11月2日，[《Woody Young Named President of Solidigm》](https://news.solidigm.com/en-WW/219822-woody-young-named-president-of-solidigm/)；Blocks & Files，Chris Mellor，2022年11月3日，[《Solidigm CEO’s departure takes staff by surprise》](https://www.blocksandfiles.com/flash/2022/11/03/solidigm-ceos-departure-takes-staff-by-surprise/1601106)。



人物照片｜Noh-Jung Kwak（郭鲁正），2022年11月临时接管Solidigm；照片刊于当年2月。

> 照片出处：SK hynix Newsroom，2022-02-24，[《SK hynix Nominates Kwak and Noh as Inside Board Directors Candidates》](https://news.skhynix.com/en/sk-hynix-nominates-kwak-and-noh-as-inside-board-directors-candidates/)；[原图](https://d18r0a86za96sg.cloudfront.net/wp-content/uploads/2022/02/14151127/%EA%B3%BD%EB%85%B8%EC%A0%95_CEO_%EB%A9%94%EC%9D%B8_01_%EA%B0%80%EB%A1%9C.jpg)。




人物照片｜Woody Young，2022年获任Solidigm President的董事会成员。

> 照片出处：Solidigm Newsroom，2022-11-02T09:27:00-07:00，[《Woody Young Named President of Solidigm》](https://news.solidigm.com/en-WW/219822-woody-young-named-president-of-solidigm/)；[原图](https://d21buns5ku92am.cloudfront.net/69634/images/449168-woody-young-c6feeb-large-1667347407.jpg)。


2022年末，卢钟元转任美国事业TF负责人，并兼任Solidigm首席业务官。<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">2023年5月15日，Solidigm宣布董事会已任命他与David M. Dixon为联席CEO。</span>公告显示，卢钟元此前已任首席业务官，负责拓展新业务与合作伙伴关系；Dixon则负责数据中心业务，具有Intel工程及SSD经营经验。董事会选人的理由是领导能力，以及对Solidigm业务和技术的熟悉程度，工作目标是加快海力士与Solidigm能力结合及协同。这份安排把熟悉原业务技术与客户的经营者，与熟悉买方战略和跨企业交易的管理者放进同一领导层。卢钟元因此从促成和协调整合，进一步走到对公司整体经营负责的位置，收购资产之后的商业兑现成为他的直接任务。

> 来源：Solidigm，2023年5月15日，[《David M. Dixon and Kevin Noh Appointed Co-CEOs of Solidigm》](https://news.solidigm.com/en-WW/226111-david-m-dixon-and-kevin-noh-appointed-co-ceos-of-solidigm/)；韩国金融新闻，郑恩京（정은경），2023年5月16日，[《[프로필] 노종원 솔리다임 신임 각자대표이사》](https://www.fntimes.com/html/view.php?ud=202305160815543116645ffc9771_18)。



人物照片｜Kevin Noh与David M. Dixon，2023年联席CEO任命公告配图。

> 照片出处：Solidigm，2023-05-15，[《David M. Dixon and Kevin Noh Appointed Co-CEOs of Solidigm》](https://news.solidigm.com/en-WW/226111-david-m-dixon-and-kevin-noh-appointed-co-ceos-of-solidigm/)；[原图](https://d21buns5ku92am.cloudfront.net/69634/images/483983-Kevin%20Noh%20and%20David%20Dixon-3631cc-large-1684099053.jpg)。


这项任务恰逢存储行业下行。海力士2023年度财报说明，NAND恢复较慢，需要优化投资与成本，并通过企业SSD等高附加值产品改善盈利。对收购后的美国团队而言，客户认证、产品开发和资源投入必须与现金承受能力同时考虑：削减开支可以缓解眼前压力，维持研发和客户关系则决定下一轮需求恢复时能卖什么。技术、市场和财务因此更难分别处理。这也解释了为何此前的并购与CFO经验能够成为管理岗位的背景。母公司的财报反映了这一阶段的行业和资本配置环境。

> 来源：SK海力士，2024年1月25日，[《SK hynix Reports Financial Results for 2023, 4Q23》](https://news.skhynix.com/en/sk-hynix-reports-fourth-quarter-2023-financial-results/)。

他退出Solidigm管理层与离开SK集团之间，还有一段美国业务经历。电子新闻记者李镐吉2025年8月27日依据SK半年报报道，卢钟元加入SK Americas任高管，当时描述为兼任。The Bell记者卢泰民同年11月的报道，则把Solidigm代理联席CEO安排与卢钟元转往SK Americas相联系。到2026年5月，Solidigm正式公布Xin Guo与Richard Chin组成的新一届联席CEO。按这些记录，卢钟元的工作重心在此前已经移向集团美国业务，随后才退出集团。这段经历继续涉及半导体业务战略和美国经营环境，构成经营者身份与其后来独立投资活动之间的过渡。

> 来源：电子新闻，李镐吉（이호길），2025年8月27日，[《노종원 솔리다임 사장, SK아메리카스 임원 선임》](https://www.etnews.com/20250827000416)；The Bell，卢泰民，2025年11月17日，[《[AI 훈풍 부는 솔리다임] 경영진 ‘핀셋’ 배치, SK하이닉스 ‘직할 체제’ 본격화》](https://www.thebell.co.kr/front/newsview.asp?key=202511171656425480106567)；Solidigm，2026年5月27日，[《Solidigm Announces New Co-CEOs Xin Guo and Richard Chin》](https://news.solidigm.com/en-WW/266116-solidigm-announces-new-co-ceos-xin-guo-and-richard-chin/)。



人物照片｜Xin Guo，2026年3月获任联席CEO；照片由Solidigm于5月27日发布。

> 照片出处：Solidigm，2026-05-27，[《Solidigm Announces New Co-CEOs Xin Guo and Richard Chin》](https://news.solidigm.com/en-WW/266116-solidigm-announces-new-co-ceos-xin-guo-and-richard-chin/)；[原图](https://d21buns5ku92am.cloudfront.net/69634/images/676920-Xin%20Guo_Solidigm-14f210-medium-1779819303.png)。




人物照片｜Richard Chin，2026年5月1日出任联席CEO；照片由Solidigm于5月27日发布。

> 照片出处：Solidigm，2026-05-27，[《Solidigm Announces New Co-CEOs Xin Guo and Richard Chin》](https://news.solidigm.com/en-WW/266116-solidigm-announces-new-co-ceos-xin-guo-and-richard-chin/)；[原图](https://d21buns5ku92am.cloudfront.net/69634/images/676917-Richard%20Chin_Solidigm-62a6bd-medium-1779818541.png)。


2026年8月，人物线再次回到资本安排。The Bell记者朴完俊8月10日报道，他在月初离开SK Americas，随后设立个人投资公司。8月21日16时45分51秒，《首尔经济》旗下Signal记者李忠熙首发报道，<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">卢钟元在美国成立私募基金管理公司TechBridge，把Solidigm定为首个投资目标，拟与Stonebridge共同组建基金，投资最多2万亿韩元。这是媒体报道的拟议投资上限，由联合基金组织资本，不是卢钟元个人承担全部出资。</span>他曾参与收购、整合和经营的业务，因而可能成为独立投资活动的第一个对象，长期产业经验开始服务于外部出资人的投资判断。

> 来源：The Bell，朴完俊，2026年8月10日，[《노종원 사장, 1년만에 SK아메리카스 떠났다》](https://www.thebell.co.kr/front/newsview.asp?code=0401&key=202608101118098120103951)；《首尔经济》Signal，李忠熙（이충희），2026年8月21日，[《[단독] 노종원 前 하이닉스 사장, 사모펀드 만들어 솔리다임 兆단위 투자 [시그널]》](https://signal.sedaily.com/article/20081919)。

后续报道把这个安排推进到更具体的组织层面。《朝鲜Biz》记者金钟容8月26日确认，讨论中的共同方是Stonebridge Global，拟通过项目基金参加少数股权投资；Bloter记者柳镐承8月31日又报道，TechBridge Investment于8月在加州设立，并招募投资分析人才、筹备联合募资。设立管理公司、募集项目基金、取得公司股份，是依次需要落实的环节，现有报道记录的主要是前两项准备。对出资人而言，卢钟元的产业熟悉度能够帮助判断技术、客户与经营风险，但投资价格、股份权利、追加资本需求和退出条件仍要通过交易结构解决。管理经验在基金中的价值，也需要转化为可检验的投资条件。

> 来源：《朝鲜Biz》，金钟容（김종용），2026年8月26日，[《SK하닉 결단만 나오면... 스톤브릿지, 노종원 전 사장과 솔리다임 공동 투자》](https://biz.chosun.com/stock/market_trend/2026/08/26/R6KUSH2MXREAPKS2Q2Y3B7ANHQ/)；Bloter，柳镐承（유호승），2026年8月31日，[《SK 출신 노종원 펀드, 솔리다임 딜 위해 AI·퀀트 인재 영입》](https://www.bloter.net/news/articleView.html?idxno=672192)。

9月28日，《每日经济》的后续报道把这条线进一步连接起来：记者称卢钟元在SK任内主导了Intel NAND与SSD业务收购，<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">目前又据报通过其在美国设立的私募管理公司组织Solidigm上市前投资，并向中东主权财富基金试探募资。</span>由参与收购到经营，再到组织外部资金进入同一业务，他与Solidigm的关系逐步转向资本市场；具体出资人及投资交割仍待披露。

> 来源：《每日经济》，金正锡（김정석）、禹秀敏（우수민），2026年9月28日17:48发布、19:41更新，[《美상장땐 '몸값 200조' 솔리다임…하닉 주가엔 '글쎄'》](https://www.mk.co.kr/news/stock/12162986)；[用户提供的中文AI翻译页](https://www.mk.co.kr/cn/stock/12162986)。引用记者署名正文；中文页与韩文页为同一报道。该文将共同方写为Stonebridge Capital，与8月《朝鲜Biz》明确的Stonebridge Global名称不同，共同投资法人仍需交易文件核定。

由此再看卢钟元的角色变化，基金计划延续了他处理产业机会与资本结构的经验，同时改变了需要回答问题的对象。在集团内部，他要为收购、整合和业务成长配置资源；成为基金管理人后，他还要为出资人解释买入价格、风险承担和回收路径。海力士10月1日的官方说明仍称，Solidigm资本使用方案尚未决定，需要比较内部现金与外部资本对现有股东的经济影响。这也把故事留在一个具体的交易节点：TechBridge能否完成募资，能否签署并交割股份投资，以及若未来进入上市程序，股东权利和退出安排如何披露。在拟议上市的背景下，外部基金若完成投资，可以为企业股权定价与上市前资本结构增加新的参与者；上市又可能成为基金未来的退出路径。曾经代表产业集团买入、随后承担经营责任的人，如今准备代表外部出资人再作判断，这才是这条人物线在今天的转折。<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">公司IPO的决定与执行，仍属于公司的资本安排，TechBridge能否参与则取决于基金和股份交易的落实。</span>

> 来源：SK海力士，2026年10月1日，[《Clarification Regarding Recent Media Reports on Solidigm》](https://news.skhynix.com/en/fact-11/)。


## 第五章　AI如何改变企业SSD的价值

Solidigm进入AI数据中心，依靠的是一条在Intel时期已经建立的技术路线。它曾面对的难题，是怎样让固态存储以能够接受的成本进入普通电脑和企业服务器；今天面对的难题，是怎样让容量持续扩大的数据集、模型和上下文及时到达计算设备。两者相隔多年，工程问题仍有连续性：处理器能算得更快，并不意味着整个系统能更快完成任务。存储的作用，是让计算设备少等数据，让已经保存的数据可以再次被使用。

这条连续性有明确的产品证据。公司公告显示，Intel与美光在2018年5月宣布生产、交付每单元四比特的3D NAND，采用64层结构。公告中的Intel技术负责人RV Giridhar将其称为浮栅3D NAND技术继续发展的结果，并把价值定位于数据中心和客户端的容量与成本。后来形成Solidigm企业SSD的技术，并非随着AI热潮才被创造出来；AI改变的是它能够进入的系统，以及客户愿意为哪些问题付费。

> 来源：Intel／Micron，2018年5月21日，《Micron and Intel Extend their Leadership in 3D NAND Flash memory》，[公司联合公告原文](https://www.intc.com/news-events/press-releases/detail/153/micron-and-intel-extend-their-leadership-in-3d-nand-flash)。

理解QLC，需要分开看单元密度和整盘表现。SLC、通常所称的双比特MLC、TLC、QLC，每个单元分别存储一、二、三、四个比特；按二进制编码的说明性计算，需要区分的状态数分别是二、四、八、十六，公式为状态数等于二的比特数次方。更多状态意味着读取时必须更精细地判断电荷对应的范围，写入与纠错也更复杂。密度提升不能自动推导出相同比例的整盘降价，更不能推导出所有工作负载下的性能提升：控制器、固件、备用容量、封装和制造良率都进入最后的结果。

> 来源：Solidigm，2023年7月16日，《QLC NAND Technology Is Ready for Mainstream Use in the Data Center》，[技术白皮书网页原文](https://www.solidigm.com/products/technology/qlc-nand-ready-for-mainstream-use-in-data-center.html)。状态数为作者说明性计算，只解释编码关系。

浮栅路线的意义也应放在这一层理解。Solidigm的上述白皮书把电压阈值窗口和单元隔离列为其技术特点，并说明了浮栅结构向高密度QLC发展的路径。企业客户最终购买的是整盘在规定环境下的可靠性和稳定表现，并不直接购买某一种单元名称。技术路线的优势，需要经过纠错、磨损均衡、数据保持和客户验证共同兑现；如果只以层数或者单元比特数判断企业SSD的竞争力，就会漏掉Intel时期积累的控制器与固件能力。

容量变化使这种系统能力更直观。<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">Solidigm于2024年11月13日公布122.88TB版本的D5-P5336，当日的交付状态是向客户提供样品。</span>公告说明这一版本与此前较低容量产品共享控制器，方便客户验证。这一容量规格已经远超早期PC SSD的容量尺度；但从样品到正式采购，仍需跨越服务器兼容、散热、故障处理和应用性能验证。从采样到规模采购，产品还要通过客户验证；这一步的完成时间与实际交付，决定新容量型号何时转化为收入。

> 来源：Solidigm，2024年11月13日，《Solidigm Extends AI Portfolio Leadership with the Introduction of 122TB Drive, the World’s Highest Capacity PCIe SSD》，[产品发布公告原文](https://news.solidigm.com/en-WW/243441-solidigm-extends-ai-portfolio-leadership-with-the-introduction-of-122tb-drive-the-world-s-highest-capacity-pcie-ssd/)。

AI训练中的持久存储，首先承担数据和模型状态的保存。训练过程反复读取输入数据，又需要定期写入检查点，以便故障之后恢复。读取、写入和恢复并非同一种负载：数据读取侧重持续带宽及并发供给，检查点则可能集中产生写入压力。NVIDIA的存储认证文档将这些过程分别纳入测试。因此，容量型QLC适合的读取层，与需要承担频繁写入的缓存层，可以采用不同介质和不同配置。客户要解决的是完整训练任务的等待时间，单盘容量无法概括全部需求。

> 来源：NVIDIA，《NVIDIA-Certified Storage》，官方在线文档，页面未标独立发布日期，2026年10月8日核阅，[认证文档原文](https://docs.nvidia.com/certification-programs/certified-storage/latest/nvidia-certified-storage.html)。

数据流经过的路径同样影响效率。NVIDIA工程师Adam Thompson与CJ Newburn在2019年介绍GPUDirect Storage时，已把本地或远程存储与GPU内存之间的直接数据路径作为问题核心，目标是减少经CPU内存中转产生的额外复制。这个例子说明，把数据存得更密只是基础设施的一部分；驱动、网络、文件系统和应用读取方式决定数据能否及时送达。对Solidigm而言，与系统厂商及软件栈合作，才有机会把闪存产品优势转化为客户可以验证的整体收益。



图7｜AI系统的内存与SSD职责。箭头表示可设计的数据分层关系，不代表每个工作负载都沿同一路径；SSD缓存的收益必须结合软件、访问模式和搬运成本验证。 工程组件为概念性技术插画。

> 图源：[原文1](https://developer.nvidia.com/blog/introducing-nvidia-bluefield-4-powered-inference-context-memory-storage-platform-for-the-next-frontier-of-ai)；[原文2](https://investors.coreweave.com/news/news-details/2026/CoreWeave-Signs-Multi-Year-Agreement-With-Solidigm-to-Strengthen-Its-Integrated-AI-Cloud-Platform/default.aspx)。


> 来源：NVIDIA Technical Blog，Adam Thompson、CJ Newburn，2019年8月6日，《GPUDirect Storage: A Direct Path Between Storage and GPU Memory》，[工程说明原文](https://developer.nvidia.com/blog/gpudirect-storage/)。

推理又带来了新的存储用途。模型生成内容时，KV cache保存注意力机制中已经计算的键和值，便于后续计算复用。正在参与生成的数据需要快速访问，而暂时不活跃但可能再次使用的上下文，可以由系统决定放到其他层。NVIDIA在2025年发布Dynamo时，说明了GPU内存、主机内存、本地SSD及网络存储之间的分层管理。这里的商业机会来自减少重复计算、提高可服务的上下文容量，而不是把所有数据一律迁到SSD。

> 来源：NVIDIA Technical Blog，Amr Elmeleegy、Harry Kim、David Zier等，2025年3月18日，《NVIDIA Dynamo, A Low-Latency Distributed Inference Framework for Scaling Reasoning AI Models》，[框架介绍原文](https://developer.nvidia.com/blog/?p=95274)。

这也划定了SSD与HBM之间的边界。NVIDIA于2026年3月介绍CMX时，将活跃、对延迟敏感的KV放在GPU HBM层，把闪存扩展层作为可复用上下文的补充。<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">SSD的大容量不能替代HBM在当前计算路径中的职责。</span>缓存下放是否划算，取决于数据复用频率、恢复耗时、网络和软件开销，以及重新计算的成本。上下文缓存还是由计算产生、可以重建的数据，不能与必须长期保留的企业原始记录混为一谈。

> 来源：NVIDIA Technical Blog，Moshe Anschel、Einav Zilberstein、Oren Duer、Kirill Shoikhet、Ronil Prasad，2026年3月16日，《Introducing NVIDIA BlueField-4-Powered CMX Context Memory Storage Platform for the Next Frontier of AI》，[分层架构原文](https://developer.nvidia.com/blog/introducing-nvidia-bluefield-4-powered-inference-context-memory-storage-platform-for-the-next-frontier-of-ai)。

Solidigm自己也在推进这种用途。其AI与生态营销负责人Ace Stryker于2026年3月发表的文章，介绍通过SSD保存额外上下文、将活跃KV继续留在GPU内存的实验。这份厂商材料支持的判断，是系统经过软件设计后可以让SSD参与推理性能优化。实验的加速效果需要依附其模型、输入内容、缓存命中和硬件配置；不能将一次上下文恢复的改善直接写成所有AI请求都能获得同样的提速，也不能把高性能SSD实验自动套用于容量型QLC产品。

> 来源：Solidigm，Ace Stryker，2026年3月10日，《KV Cache Data Offload to SSDs as an Active Performance Layer》，[技术文章原文](https://www.solidigm.com/products/technology/ssds-unlock-ai-inference-with-rag-and-kv-cache.html)。

QLC能否承担企业工作负载，还要看写入寿命的口径。Solidigm产品简介列出的122.88TB型号为192层QLC，其五年耐久规格为0.60次每日全盘写入、累计134.3PB写入；这些属于厂商产品规格，脚注明确采用与间接寻址单元对齐的32KB随机写入。它们不能视为任何小块随机写入下都成立的通用承诺。DWPD衡量的是相对于整盘容量的写入量，容量和实际写入模式都会影响客户对寿命的判断。

> 来源：Solidigm，《Solidigm D5-P5336 Product Brief》，2025年版权版本，第3页规格表、第4页脚注17—18，具体发布日期未标，[产品简介PDF原文](https://www.solidigm.com/content/dam/solidigm/en/site/products/technology/p5336-product-brief/documents/Solidigm-D5P5336-ProductBrief.pdf)。

写入放大是另一项约束。主机请求写入的数据量，与闪存内部实际写入的数据量，未必一致。小块更新与设备内部管理粒度不匹配时，会产生额外读取、修改和写入。Solidigm与纬颖合作的CSAL方案，采用较快的TLC SSD承担缓存，再将写入整理后送往容量型QLC SSD。这样的分层意味着高密度介质需要与软件及缓存设计共同工作；客户比较方案时，要把额外设备、软件维护和故障恢复成本一起计入。

> 来源：Solidigm，2025年8月5日，《Platform Optimization for Performance and Endurance》，[与纬颖合作的技术方案原文](https://www.solidigm.com/products/technology/platform-optimization-for-performance-and-endurance-qlc-csal.html)。

功耗和总拥有成本也必须放在一致条件下比较。每块盘的最大功率、每TB功率、机柜供电和整个存储系统的耗电，回答的是不同问题。若高容量盘减少了服务器、线缆和机柜数量，系统成本可能下降；若应用需要更多并发通道或者更严格的冗余配置，盘数则未必按容量同比缩减。上述产品简介中的效率比较是厂商建模，限定了混合HDD与TLC方案、全QLC方案及基础设施配置。它适合说明密度如何影响系统设计，不能脱离条件改写为普遍适用的节电比例。

真正进入采购关系的证据，来自客户公告。<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">CoreWeave于2026年8月5日宣布，与Solidigm签署多年战略协议，取得企业SSD容量的优先供应安排。</span>其运营负责人Sachin Jain将存储放在公司整套AI平台能力之中；公告还把行业供应趋紧列为签订直接协议的背景。公告给出了多年优先供应的框架，合同金额及实际采购量仍待后续披露。它说明客户开始提前规划存储供给，未来收入则取决于实际交付。

> 来源：CoreWeave，2026年8月5日，《CoreWeave Signs Multi-Year Agreement With Solidigm to Strengthen Its Integrated AI Cloud Platform》，[客户投资者关系网站公告原文](https://investors.coreweave.com/news/news-details/2026/CoreWeave-Signs-Multi-Year-Agreement-With-Solidigm-to-Strengthen-Its-Integrated-AI-Cloud-Platform/default.aspx)。

对Solidigm而言，AI将多年积累的容量、固件和验证能力带进了更大的系统预算。接下来能验证这种变化的指标，应包括客户实际采购与交付、产品组合、制造成本、质保表现及现金流。需求增长、优先供应合同和产品容量都提供了线索，盈利能否持续则要看这些线索如何落到业务账本上。也正是在这里，技术故事与融资故事相接：如果公司要扩大供给，谁出钱、钱投到哪个法人，以及新增价值怎样分配，就成为必须回答的问题。


## 第六章　独立上市背后的资本选择

《首尔经济》记者李泰圭于2026年10月8日转述彭博前一日的消息称，Solidigm据报选定高盛与摩根士丹利为赴美上市的主承销行，交易可能在2027年进行，潜在筹资约100亿美元。这些数字与时间属于媒体披露的拟议方案；报道说明讨论仍在继续，细节可能调整，也可能有更多银行加入。承销行的选择使筹备工作更具体，但发行主体、股份结构与最终资金用途仍待正式文件明确。

> 来源：Bloomberg，2026年10月7日，《SK Hynix’s Solidigm Is Said to Pick Banks for US IPO Next Year》，[彭博原始报道链接，全文访问受限](https://www.bloomberg.com/news/articles/2026-10-07/sk-hynix-s-solidigm-is-said-to-pick-banks-for-us-ipo-next-year)；实际核阅：《首尔经济》，Lee Tae-kyu，2026年10月8日07:23:46，《SK hynix Picks Goldman, Morgan Stanley for Solidigm IPO》，[可读英文转述](https://en.sedaily.com/international/2026/10/08/sk-hynix-picks-goldman-morgan-stanley-for-solidigm-ipo)、[该页面提供的韩文原文链接，访问受限](https://www.sedaily.com/article/20099331)。英文页注明采用AI翻译；该转述与彭博消息同源。

在选定承销行消息之前，路透社9月25日已报道，Solidigm当周与竞逐承销角色的投行举行了方案陈述会议，早期讨论涉及最高1500亿美元企业估值及约150亿美元IPO筹资。两项金额分别是权益估值与可能募集的资金，报道明确称方案尚早、可随市场条件变化。10月报道的约100亿美元潜在筹资，是另一个时点的媒体口径；这些数字不能直接合并，也不足以证明公司已经正式调整发行规模。

> 来源：Reuters，Milana Vinn、Echo Wang，2026年9月25日，[《Solidigm讨论IPO，估值或达1500亿美元》路透社原稿转载](https://www.investing.com/news/stock-market-news/exclusivesk-hynixs-solidigm-weighs-ipo-that-could-value-theunit-at-up-to-150-billion-sources-say-4917883)；Investing.com保留路透社记者署名及公司尚未确定具体方案的回应。

上市议题并非在这一报道出现时才开始。SK海力士于2026年9月4日提交SEC的6-K，回应《韩国经济新闻》此前关于Solidigm筹划上市前融资的报道，说明使用Solidigm品牌的海外子公司在研究增强竞争力的多种措施，截至该文件日期尚未确定事项。监管回应确认讨论存在，但没有确认媒体所提方案已签约。因此，第四章中的基金筹组、上市前融资及当前承销行消息，可以组成资本活动的时间线，却不能彼此替代，证明其中任何一步已完成交割。

> 来源：SK hynix，2026年9月4日，Form 6-K，《Clarification Regarding Rumors or Media Reports》，[SEC申报原文](https://www.sec.gov/Archives/edgar/data/2120882/000119312526382688/d111778d6k.htm)。

发行安排尚未确定时，仍可以讨论公司为何考虑外部资金。SK海力士于2026年10月1日的正式说明给出了核心逻辑：<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">集团同时面对HBM、服务器DRAM和企业SSD的投资需求，财务状况较强，不意味着所有项目都应使用内部现金；外部资金与内部资金必须比较对现有股东的经济影响。</span>公司还明确表示，Solidigm的资本方案截至当日没有决定。这份说明把问题放在整个集团的资本配置中，避免了将上市简单解释为公司缺钱。

> 来源：SK hynix，2026年10月1日，《Clarification Regarding Recent Media Reports on Solidigm》，[公司正式说明原文](https://news.skhynix.com/en/fact-11/)。

美国建厂评估也使融资需求有了更具体的产业背景。如果未来确定新增NAND制造基地，投入将覆盖厂房、设备、工艺验证以及量产前的持续开支，资金需求会超出研发园区和产品团队的日常运营。《每日经济》报道提到，市场预期上市前资金可能用于美国生产基地。这一预期把外部资本与未来制造布局连接起来，但正式资金用途仍须融资协议及项目文件确认；目前的大连工厂继续是既有制造能力的组成部分。

> 来源：《每日经济》，金正锡（김정석）、禹秀敏（우수민），2026年9月28日17:48发布、19:41更新，[《美상장땐 '몸값 200조' 솔리다임…하닉 주가엔 '글쎄'》](https://www.mk.co.kr/news/stock/12162986)；[用户提供的中文AI翻译页](https://www.mk.co.kr/cn/stock/12162986)。引用记者署名正文；中文页与韩文页为同一报道。美国建厂评估的更早报道见第三章所列路透社原稿。

这种资本选择可以从业务差异理解。HBM和企业SSD都进入AI基础设施，却由不同产品、制造与客户体系支撑。集团资金投入其中一种业务，就暂时不能以同样方式投入另一种业务。借助外部股权，可能让企业SSD扩张与其他项目同时推进；内部出资，则能保留更多未来收益。前者会引入新股东及其治理要求，后者占用集团现金并增加自身承担的周期风险。是否选择上市，最终要比较项目收益、融资成本与扩张时点，不能只比较集团账上还有多少现金。

第三章所述的大连制造、美国SSD经营和AI战略平台，已经分处不同法人。<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">对潜在上市而言，关键是哪些技术、资产、客户合同及供货权利进入发行范围，以及制造成本怎样进入经营公司的账本。</span>长期供货承诺、良率责任和定价方式，会影响投资者能够分享的利润；设备取得、维护及扩产条件，也会影响这部分利润能否持续。

<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">AI Company的100亿美元资本承诺，与媒体报道的潜在IPO筹资属于两项资本活动。前者按资金调用投入AI战略平台，后者取决于发行主体与新股、老股结构。</span>数字量级相同，并不意味着资金用途或归属相同；分析企业SSD扩张能力，需要回到经营公司的实际到账和资本开支。

重组后账本边界的重要性，在财务分析中尤其突出。旧法人的收入、融资和投资活动，不一定在新经营公司保持原样；集团内部资金往来，也可能随资产转移重新安排。判断未来上市公司的盈利和偿债能力，需要核对分拆财务、债务归属、内部贷款、税务及关联交易。历史亏损或旧实体负债可以解释企业曾经历什么，却不能在没有调整依据时直接当作拟上市公司的当前财务状态。投资者要买的是发行范围中的权益，品牌名称只能帮助识别业务。


大连的生产能力，还需要放在设备取得方式中理解。美国商务部工业与安全局于2025年9月2日公布最终规则，将Intel Semiconductor (Dalian) Ltd等三家公司从中国的“经验证最终用户”名单中移除，2025年12月31日生效。这个名单原本允许符合条件的受控物项使用一般授权出口；移除意味着原有授权路径发生变化，不能据此推导大连工厂被要求全部停产。工厂能否取得某项设备，仍要看物项和许可证条件。厂房、设备、工艺与合法供货条件是不同层次的能力，即使资本已经到位，也不能自动把它们同时取得。

> 来源：美国商务部工业与安全局，2025年9月2日，最终规则《Revocation of Validated End-User Authorizations in the People's Republic of China》，90 FR 42321，文件2025-16735，[规则全文](https://www.federalregister.gov/documents/2025/09/02/2025-16735/revocation-of-validated-end-user-authorizations-in-the-peoples-republic-of-china)。

2026年1月5日，美国人口普查局发布新的C79工厂许可证申报指引，说明此类获授权出口应按照BIS发给工厂的有效许可证办理，并由工厂传达相关条款。该指引证明许可和申报存在新的路径，却没有公开大连某条生产线的全部批准范围。因此，评价其后续扩张时，应分别核对厂房建成、设备采购和安装、工艺验证及量产时间。生产厂房完成，并不等于新增产能已经贡献销售；设备可以进厂，也不等于所有技术升级都已获准。对Solidigm而言，稳定且可持续的晶圆供给，才是把制造基地转化为客户交付能力的关键。

> 来源：美国人口普查局，2026年1月5日，《NEW BIS LICENSE TYPE C79 — Fab License》，[官方申报指引原文](https://content.govdelivery.com/accounts/USCENSUS/bulletins/4008e2b)。


上市能提供的一个功能，是让这部分业务直接接受资本市场定价。外部投资者可以围绕企业SSD的客户、技术、产能和现金流形成判断，公司也可能通过独立股权获得持续融资能力。美国业务与客户关系，为选择美国市场提供商业背景；但客户在美国，不能单独证明美国上市一定获得更高估值。具体证券、交易市场、会计披露要求及投资者需求，还要结合最终发行结构。现阶段可以解释选择的可能理由，不能替发行人宣布既定结论。

募集资金流向是另一个必须拆开的问题。<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">如果公司发行新股，资金进入发行主体，用来支持其业务；如果已有股东出售股份，所得款项首先进入售股股东。</span>两种安排也可能同时出现。扩产、补充运营资金、偿债和集团资本再配置，会对应不同的受益主体。即使报道使用“筹资”一词，尚未披露的新股与老股比例，也会影响这笔钱究竟解决谁的资金需求。新股与老股的比例，要由发行文件说明；它决定资金首先进入经营公司还是原有股东，也决定筹资与扩产之间有多直接的联系。


图8｜内部资金与外部股权融资的经济差别。新股和老股的资金流向是机制示意，不表示Solidigm已公布采用哪一种发行结构。

> 图源：[原文1](https://news.skhynix.com/en/fact-11/)。

韩国现有股东担心的利益分配，也可以由这个结构解释。母公司股东通过母公司持有子公司权益；引入外部股东之后，对同一业务未来收益的分享比例可能变化。<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">若融资使公司获得此前无法完成的扩张，并产生足够新增价值，持股比例下降不一定意味着经济价值下降。</span>若交易定价、关联交易或利益分配失衡，母公司股东也可能承担不利结果。因此，“双重上市”是治理与估值问题，不能仅凭上市层级判定它必然有利或者必然损害原股东。

这里最需要透明的是交易条款。引入私人资本时，普通股之外可能还有优先权、退出安排和治理条款；公开发行时，则需要明确谁发行、谁出售、谁保留控制权。如果此前媒体报道中的投资基金最终参与，投资价格和权利安排也应进入比较。对前管理者参与投资的分析，应落在是否签约、是否披露关联关系、如何定价及怎样处理利益冲突等可核实事项上。熟悉业务能够解释投资兴趣，却不能替代公开程序，也不能证明其与IPO构成已经确定的连续交易。

企业SSD的增长还必须接受存储产业周期检验。高容量产品需求上升，可以改善业务组合；客户提前取得供应安排，也有助于制造商规划生产。新增产能却会形成折旧和持续运营开支，采购节奏、供给扩张与产品切换进度会共同影响利润。上市估值需要回答的是增长能持续多久，以及为了兑现增长还必须投入多少现金。这里的重点从某一时点的需求，转向跨周期的盈利与现金回收能力。

上市也不会自动解决独立运营的问题。拟发行公司是否掌握其技术与客户合同，怎样向集团购买闪存或服务，工厂与知识产权归属何处，都会影响利润留在哪一层。母公司同时经营多种存储业务，还需要说明内部合作如何定价，以及外部小股东怎样获得公平的信息和待遇。所谓“独立”，既包括公司对外拥有自己的名称与产品，也包括经营账本能够被外部股东理解；后者要靠审计、合同和治理结构支撑。

截至本文所依据的2026年10月8日材料，能够确认的是：企业SSD正在被更直接地纳入AI平台的供给规划，集团已在上半年推进美国经营业务转移，并持续讨论内部与外部资金选项；承销行及筹资规模仍属媒体披露的方案。接下来的关键进展，应是正式确定的发行主体、融资协议或注册文件、分拆后的审计财务，以及资金用途与股权变化。只有这些材料出现，才能判断Intel留下的技术资产，在SK海力士体系里创造了多少可持续价值，以及这些价值如何在不同股东之间分配。



## 格洛可点评

Solidigm的历史说明，半导体业务的价值不能只由某个时点的利润判断。Intel留下的制造工艺、固件经验和客户认证，需要长期投入才能形成，也需要新的产品需求和资金条件才能继续发展。SK海力士收购之后，最值得观察的是两套能力如何在产品上结合：谁提供晶圆，谁承担控制器与固件开发，谁完成客户验证，谁保证交付。AI需求提供新的商业机会，但只有持续的产品和供货能力，才能把机会变为经营成果。

大连工厂尤其能检验这种结合是否扎实。工厂产权、技术知识产权与对客户出售SSD的主体，即使同属一个集团，也可能由不同公司承担。<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">外部投资者分享的收益，取决于发行主体的资产与合同边界。</span>如果制造端采用成本加成定价，成本变化和约定加成会影响经营公司的利润；如果采购按市场条件定价，晶圆周期价格则会以另一种方式进入成本。两类机制都需要结合供应保障和技术迁移理解。拥有可用的工厂与拥有可审计、可持续的供应权利，分别回答生产能力和股东收益的问题。

Kevin Noh由管理者走向潜在投资组织者，让这一故事增加了资本层面的观察角度。熟悉技术、客户和组织，可以帮助识别业务机会；基金设立、融资签约、投资交割和公开发行，却仍是不同事件。判断上市是否创造价值，应看资本如何进入、谁承担制造与周期风险、关联交易如何定价，以及新增投资是否改善客户供给。承销行消息只是一个进展节点。<span class="reading-highlight" style="background-color:#FFF2B0;color:inherit">真正决定这笔历史性收购如何被重新评价的，将是独立财务、清楚的资产边界和能够兑现的现金流。</span>

> 点评中的成本加成和市场采购为合同机制分析，不构成对未公开具体合同条款的确认。相关事实基础见SK hynix 2026年1月28日[美国业务重组公告](https://news.skhynix.com/en/sk-hynix-to-establish-ai-solutions-arm-in-us/)、2026年10月1日[资本方案说明](https://news.skhynix.com/en/fact-11/)，以及第四章列示的TechBridge韩文原始报道。


## 原始资料与出处

1. Intel / Micron，2005-11-21，[Micron And Intel Create New Company To Manufacture NAND Flash Memory](https://www.intel.com/pressroom/archive/releases/2005/20051121corp.htm)。

2. Intel，2008-09-08，[Intel Introduces Solid-State Drives for Notebook and Desktop Computers](https://www.intc.com/news-events/press-releases/detail/1338/intel-introduces-solid-state-drives-for-notebook-and)。

3. Micron / Intel，2018-01-08，[后续3D NAND研发分开与3D XPoint边界](https://investors.micron.com/news/press-release/2018/Micron-and-Intel-Announce-Update-to-NAND-Memory-Joint-Development-Program-01-08-2018/default.aspx)。

4. Intel / SK hynix，2020-10-20，[SK hynix to Acquire Intel NAND Memory Business](https://www.intc.com/filings-reports/all-sec-filings/content/0001193125-20-272580/d76122dex991.htm)。

5. Solidigm，2023-05-15，[David M. Dixon and Kevin Noh Appointed Co-CEOs of Solidigm](https://news.solidigm.com/en-WW/226111-david-m-dixon-and-kevin-noh-appointed-co-ceos-of-solidigm/)。

6. Intel / SEC，April Miller Boise (signature)，2025-03-27，[Form 8-K — Item 2.01 Completion of Acquisition or Disposition of Assets](https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-25-000060/intc-20250327.htm)。

7. Solidigm，2026-05-27，[Solidigm Announces New Co-CEOs Xin Guo and Richard Chin](https://news.solidigm.com/en-WW/266116-solidigm-announces-new-co-ceos-xin-guo-and-richard-chin/)。

8. Seoul Economic Daily / Signal，李忠熙（이충희），2026-08-21T16:45:51+09:00，[[단독] 노종원 前 하이닉스 사장, 사모펀드 만들어 솔리다임 兆단위 투자 [시그널]](https://signal.sedaily.com/article/20081919)。

9. CoreWeave，CoreWeave, Inc.，2026-08-05，[CoreWeave Signs Multi-Year Agreement With Solidigm to Strengthen Its Integrated AI Cloud Platform](https://investors.coreweave.com/news/news-details/2026/CoreWeave-Signs-Multi-Year-Agreement-With-Solidigm-to-Strengthen-Its-Integrated-AI-Cloud-Platform/default.aspx)。

10. SK hynix，2026-10-01，[Clarification Regarding Recent Media Reports on Solidigm](https://news.skhynix.com/en/fact-11/)。

11. Bloomberg，2026-10-07，[SK Hynix’s Solidigm Is Said to Pick Banks for US IPO Next Year](https://www.bloomberg.com/news/articles/2026-10-07/sk-hynix-s-solidigm-is-said-to-pick-banks-for-us-ipo-next-year)。

12. Seoul Economic Daily，Lee Tae-kyu，2026-10-08，[SK hynix Picks Goldman, Morgan Stanley for Solidigm IPO](https://en.sedaily.com/international/2026/10/08/sk-hynix-picks-goldman-morgan-stanley-for-solidigm-ipo)。

13. ChosunBiz / 朝鲜Biz，金钟容（김종용），2026-08-26T06:00:00+09:00，[SK하닉 결단만 나오면... 스톤브릿지, 노종원 전 사장과 솔리다임 공동 투자](https://biz.chosun.com/stock/market_trend/2026/08/26/R6KUSH2MXREAPKS2Q2Y3B7ANHQ/)。

14. Bloter，柳镐承（유호승），2026-08-31T11:05:52+09:00，[SK 출신 노종원 펀드, 솔리다임 딜 위해 AI·퀀트 인재 영입](https://www.bloter.net/news/articleView.html?idxno=672192)。

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

35. SK hynix，2021-12-30，[SK hynix completes the First Phase of Intel NAND and SSD Business Acquisition](https://news.skhynix.com/en/sk-hynix-completes-the-first-phase-of-intel-nand-and-ssd-business-acquisition/)。

36. SK hynix，2021-01-29，[SK hynix Inc. Reports Fiscal Year 2020 and Fourth Quarter Results](https://news.skhynix.com/en/sk-hynix-inc-reports-fiscal-year-2020-and-fourth-quarter-results/)。

37. SK hynix Newsroom，SK hynix，2022-02-24，[SK hynix Nominates Kwak and Noh as Inside Board Directors Candidates](https://news.skhynix.com/en/sk-hynix-nominates-kwak-and-noh-as-inside-board-directors-candidates/)。

38. SK hynix / Solidigm，2022-04-05，[SK hynix and Solidigm Introduce First Collaborative Product](https://news.skhynix.com/en/sk-hynix-and-solidigm-introduce-first-collaborative-product/)。

39. SK hynix，2024-01-25，[SK hynix Reports Financial Results for 2023, 4Q23](https://news.skhynix.com/en/sk-hynix-reports-fourth-quarter-2023-financial-results/)。

40. SK hynix，2026-01-28，[SK hynix to Establish U.S. Arm Specialized in AI Solutions](https://news.skhynix.com/en/sk-hynix-to-establish-ai-solutions-arm-in-us/)。

41. The Bell / 더벨，元忠熙（원충희），2021-04-07T07:06:47+09:00，[[CFO 워치 | SK하이닉스] M&A부터 ESG채권까지, 화려한 재무전략 주역들](https://www.thebell.co.kr/front/newsview.asp?key=202104061550525920105633)。

42. Intel / SEC，Susie Giordano (signature)，2020-10-20，[Form 8-K — Item 1.01 Entry into a Material Definitive Agreement](https://www.sec.gov/Archives/edgar/data/50863/000119312520272580/d76122d8k.htm)。

43. SK hynix / Korea Exchange KIND，김우현 / 金佑贤 (preparer)，2025-03-28，[주요사항보고서(영업양수결정) — 정정신고](https://kind.krx.co.kr/external/2025/03/28/000061/20250328000194/11336.htm)。

44. Solidigm Newsroom，Solidigm，2022-11-02T09:27:00-07:00，[Woody Young Named President of Solidigm](https://news.solidigm.com/en-WW/219822-woody-young-named-president-of-solidigm/)。

45. Intel / Micron，2018-05-21，[Micron and Intel Extend their Leadership in 3D NAND Flash memory](https://www.intc.com/news-events/press-releases/detail/153/micron-and-intel-extend-their-leadership-in-3d-nand-flash)。

46. Solidigm，2023-07-16，[QLC NAND Technology Is Ready for Mainstream Use in the Data Center](https://www.solidigm.com/products/technology/qlc-nand-ready-for-mainstream-use-in-data-center.html)。

47. Solidigm，Solidigm Corporate Communications，2024-11-13，[Solidigm Extends AI Portfolio Leadership with the Introduction of 122TB Drive, the World’s Highest Capacity PCIe SSD](https://news.solidigm.com/en-WW/243441-solidigm-extends-ai-portfolio-leadership-with-the-introduction-of-122tb-drive-the-world-s-highest-capacity-pcie-ssd/)。

48. Solidigm，2025 copyright; precise publication date not displayed; retrieved 2026-10-08，[Solidigm D5-P5336 Product Brief](https://www.solidigm.com/content/dam/solidigm/en/site/products/technology/p5336-product-brief/documents/Solidigm-D5P5336-ProductBrief.pdf)。

49. NVIDIA，online documentation; publication date not displayed; retrieved 2026-10-08，[NVIDIA-Certified Storage](https://docs.nvidia.com/certification-programs/certified-storage/latest/nvidia-certified-storage.html)。

50. NVIDIA Technical Blog，Adam Thompson; CJ Newburn，2019-08-06，[GPUDirect Storage: A Direct Path Between Storage and GPU Memory](https://developer.nvidia.com/blog/gpudirect-storage/)。

51. NVIDIA Technical Blog，Amr Elmeleegy; Harry Kim; David Zier; Kyle Kranen; Neelay Shah; Ryan Olson; Omri Kahalon，2025-03-18，[NVIDIA Dynamo, A Low-Latency Distributed Inference Framework for Scaling Reasoning AI Models](https://developer.nvidia.com/blog/?p=95274)。

52. NVIDIA Technical Blog，Moshe Anschel; Einav Zilberstein; Oren Duer; Kirill Shoikhet; Ronil Prasad，2026-03-16，[Introducing NVIDIA BlueField-4-Powered CMX Context Memory Storage Platform for the Next Frontier of AI](https://developer.nvidia.com/blog/introducing-nvidia-bluefield-4-powered-inference-context-memory-storage-platform-for-the-next-frontier-of-ai)。

53. Solidigm，Ace Stryker，2026-03-10，[KV Cache Data Offload to SSDs as an Active Performance Layer](https://www.solidigm.com/products/technology/ssds-unlock-ai-inference-with-rag-and-kv-cache.html)。

54. Solidigm，2025-08-05，[Platform Optimization for Performance and Endurance](https://www.solidigm.com/products/technology/platform-optimization-for-performance-and-endurance-qlc-csal.html)。

55. SK hynix / SEC，SK hynix; signed by Seonghwan Park, Head of Investor Relations，2026-09-04，[Form 6-K: Clarification Regarding Rumors or Media Reports](https://www.sec.gov/Archives/edgar/data/2120882/000119312526382688/d111778d6k.htm)。

56. SK hynix / SEC，SK hynix; Seonghwan Park（IR负责人签署），2026-08-18，[Form 6-K: Semi-Annual Business Report and Condensed Consolidated Interim Financial Statements](https://www.sec.gov/Archives/edgar/data/2120882/000119312526354777/d147827d6k.htm)。

57. Solidigm，Solidigm Corporate Communications，2026-04-02，[Solidigm Expands Sacramento Development, Fueling Global AI Leadership](https://news.solidigm.com/en-WW/263946-solidigm-expands-sacramento-development-fueling-global-ai-leadership/)。

58. Solidigm，Solidigm Corporate Communications，2023-02-07，[Solidigm Names Rancho Cordova Global Headquarters](https://news.solidigm.com/en-WW/222801-solidigm-names-rancho-cordova-global-headquarters/)。

59. Solidigm，原文未注明发布日期，[Frequently Asked Questions](https://www.solidigm.com/support/faqs.html)。

60. SK hynix，2022-10-27，[NAND Technology Development at SK hynix: Reaching New Heights](https://news.skhynix.com/en/nand-development-history/)。

61. Tom’s Hardware，Anton Shilov，2026-06-26，[Solidigm VP talks PCIe 6.0 SSDs, next-gen floating gate NAND, liquid cooled storage and more — Avi Shetty, VP of AI, Solutions & Market Enablement discusses the future of enterprise storage tech](https://www.tomshardware.com/pc-components/ssds/solidigm-vp-talks-pcie-6-0-ssds-next-gen-floating-gate-nand-liquid-cooled-storage-and-more-avi-shetty-vp-of-ai-solutions-and-market-enablement-discusses-the-future-of-enterprise-storage-tech)。

62. The Bell，朴完俊（박완준），2026-08-10T13:48:52+09:00，[노종원 사장, 1년만에 SK아메리카스 떠났다](https://www.thebell.co.kr/front/newsview.asp?code=0401&key=202608101118098120103951)。

63. The Bell，金一文（김일문），2017-06-21T16:41:25+09:00，[[도시바 M&A] SK M&A 전략 산실 PM실에 관심 집중](https://www.thebell.co.kr/front/newsview.asp?code=0705&key=201706210100038130002311)。

64. The Bell，金一文（김일문），2017-12-07T15:07:00+09:00，[SKT 전략 핵심 노종원 PM 실장, 전무로 파격승진](https://m.thebell.co.kr/m/newsview.asp?newskey=201712070100010750000643&svccode=)。

65. SK hynix Newsroom，SK hynix，2017-09-28，[SK hynix Inc.’s Board Approved a Plan to Invest in Toshiba Memory Corporation](https://news.skhynix.com/en/sk-hynix-inc-s-board-approved-a-plan-to-invest-in-toshiba-memory-corporation-2/)。

66. Toshiba Corporation，Toshiba Corporation，2018-06-01，[Notice Regarding Closing of the Sale of Toshiba Memory Corporation and Change to a Specified Subsidiary Company](https://www.global.toshiba/content/dam/toshiba/migration/corp/irAssets/about/ir/en/news/20180601_1.pdf)。

67. The Bell，金惠兰（김혜란），2021-01-29T13:24:22+09:00，[[CFO 워치 | SK하이닉스] 노종원 부사장, 안살림까지 총괄](https://www.thebell.co.kr/front/newsview.asp?code=0401&key=202101290930276960105436)。

68. The Bell，元忠熙（원충희），2021-12-02T15:28:24+09:00，[[CFO 워치 | SK하이닉스] 최연소 CFO 노종원 부사장, 최연소 사장 등극](https://www.thebell.co.kr/front/newsview.asp?code=0705&key=202112021516373840108564)。

69. SK hynix Newsroom，SK hynix，2021-12-02，[SK하이닉스, 2022년 조직개편 및 임원인사 단행](https://news.skhynix.co.kr/executive-personnel-and-organizational-reorganization-2022/)。

70. The Bell，元忠熙（원충희），2022-07-12T08:03:23+09:00，[노종원 사장, SK하이닉스-솔리다임 통합 전진 배치](https://www.thebell.co.kr/front/newsview.asp?code=0401&key=202207120720304860107075)。

71. 电子新闻（ETnews），李镐吉（이호길），2025-08-27T18:10:00+09:00，[노종원 솔리다임 사장, SK아메리카스 임원 선임](https://www.etnews.com/20250827000416)。

72. The Bell，卢泰民（노태민），2025-11-17T17:22:38+09:00，[[AI 훈풍 부는 솔리다임] 경영진 핀셋 배치, SK하이닉스 직할 체제 본격화](https://www.thebell.co.kr/front/newsview.asp?key=202511171656425480106567)。

73. TheBell，노태민，2026-07-29T11:15:24+09:00，[[IR Briefing] SK하이닉스, 키옥시아 효과 덕 영업외손익 '62조'](https://www.thebell.co.kr/front/newsview.asp?code=0301&key=202607291104412880106333)。

74. Kioxia Holdings Corporation，Kioxia Holdings Corporation，2026-06-24，[Annual Securities Report for the Fiscal Year Ended March 2026](https://www.kioxia-holdings.com/content/dam/kioxia-hd/en-jp/ir/library/securities/asset/Annual-Securities-Report-FY2025-EN.pdf)。

75. SK Telecom，2024-03-24，[[창사 40주년] SK텔레콤 10대 모먼트](https://news.sktelecom.com/202452)。

76. TheBell，김일문，2017-12-07T18:08:44+09:00，[SK텔레콤 신설 '유니콘랩스' 의미는?](https://www.thebell.co.kr/front/newsview.asp?code=0401&key=201712070100011610000699)。

77. 韩国金融新闻（한국금융신문），정은경，2023-05-16T08:19:00+09:00，[[프로필] 노종원 솔리다임 신임 각자대표이사](https://www.fntimes.com/html/view.php?ud=202305160815543116645ffc9771_18)。

78. 每日经济（매일경제），金正锡（김정석）、禹秀敏（우수민），2026-09-28，[美상장땐 '몸값 200조' 솔리다임…하닉 주가엔 '글쎄'](https://www.mk.co.kr/news/stock/12162986)。

79. 每日经济，KIM Jeongsuk、WOO Sumin，2026-09-28，[《Solidigm美国上市与海力士股东影响》中文AI翻译页（无正常中文标题）](https://www.mk.co.kr/cn/stock/12162986)。

80. Reuters（MarketScreener全文转载），Hyunjoo Jin、Heekyong Yang、Karen Freifeld，2026-09-18，[SK Hynix's Solidigm unit is weighing NAND memory chip factory in US, sources say](https://www.marketscreener.com/news/sk-hynix-s-solidigm-unit-is-weighing-nand-memory-chip-factory-in-us-sources-say-ce785adad98cf221)。

81. Reuters（Investing.com全文转载），Milana Vinn、Echo Wang，2026-09-25，[Exclusive-SK Hynix’s Solidigm weighs IPO that could value the unit at up to $150 billion, sources say](https://www.investing.com/news/stock-market-news/exclusivesk-hynixs-solidigm-weighs-ipo-that-could-value-theunit-at-up-to-150-billion-sources-say-4917883)。

82. Blocks & Files，Chris Mellor，2022-11-03，[Solidigm CEO’s departure takes staff by surprise](https://www.blocksandfiles.com/flash/2022/11/03/solidigm-ceos-departure-takes-staff-by-surprise/1601106)。

83. SK hynix Newsroom，SK hynix，2019-10-10，[Interview with SK hynix CEO Seok-hee Lee, “curiosity has shaped me”](https://news.skhynix.com/en/interview-with-sk-hynix-ceo-seok-hee-lee-curiosity-has-shaped-me/)。

84. Intel Free Press，原文未注明发布日期，[Gordon Moore with Robert Noyce at Intel in 1970](https://www.flickr.com/photos/intelfreepress/8450997579/)。

85. Intel Corporation，2017-10-03，[Former Intel CEO Paul S. Otellini Dies at Age 66](https://www.intc.com/news-events/press-releases/detail/199/former-intel-ceo-paul-s-otellini-dies-at-age-66)。

86. Intel，2019-01-31，[Intel Names Robert Swan CEO](https://www.intc.com/news-events/press-releases/detail/96/intel-names-robert-swan-ceo)。

87. 美国商务部工业与安全局，2025-09-02，[Revocation of Validated End-User Authorizations in the People’s Republic of China](https://www.federalregister.gov/documents/2025/09/02/2025-16735/revocation-of-validated-end-user-authorizations-in-the-peoples-republic-of-china)。

88. 美国人口普查局，2026-01-05，[NEW BIS LICENSE TYPE C79 — Fab License](https://content.govdelivery.com/accounts/USCENSUS/bulletins/4008e2b)。

## 备注

资料时点为2026年10月8日。公司公告、监管文件与媒体拟议方案分别表述；Signal的TechBridge首发原文及后续韩文报道均已核阅。彭博原报道全文受限，最新承销行消息采用《首尔经济》可读转述，英文页标注AI翻译，未将同源转载计作独立佐证。

金额保留原币种；原始合同价、买方调整后付款、卖方净收款，以及出资承诺与潜在IPO筹资分别采用各来源口径。性能和耐久数据保留规格条件，不以厂商测试推算一般系统收益。首图工程场景为AI生成的概念性示意，Rob Crooke与Kevin Noh肖像均由读者提供的照片合成。Crooke照片来自读者留存的Intel工作档案，拍摄日期未独立核实。Noh原图见SK海力士2022年2月[董事候选人公告](https://news.skhynix.com/en/sk-hynix-nominates-kwak-and-noh-as-inside-board-directors-candidates/)，拍摄日期未披露。正文图统一采用浅底技术图册版式，数据和关系依据原始资料重绘；其中工程组件与系统剖面为概念性插画，不是具名工厂或产品实景。

读者提供的两页未署名初步融资材料使用匿名代称，且缺少脚注、日期和公开原址；正文据其提示展开制造与融资机制分析，没有把其中股权比例、估值或成本加成安排当作已确认交易。


格洛可｜2026年10月8日
