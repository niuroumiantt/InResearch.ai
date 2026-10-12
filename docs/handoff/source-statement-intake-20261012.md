# 普通信息来源登记（2026-10-12）

用户取消普通信息前置真假核验：唯一主体稳定ID为核心，已有信息先登记、按时间展示最新、旧版本保留。现行规范01普通来源登记节取代普通园区信息的强制C3、全文与目标门槛。source-statements写入现有projects.json v3，registration.status=unverified；归档来源复用真实catalog，无网页URL或专用凭证也可登记。原件指针、独立时间、幂等重放和逐条失败隔离保持。公开基础登记待查，不伪造reviewed_at或verified_date；来源登记不是研究核验或模型支持。

同字段同范围按有效时间，未知时依次披露、首次接收、首次登记；selection_time_basis公开说明，effective_at保留null。同时间取后登记并保留分歧。规划与投运、水电不同维度和分期保持独立；原历史不覆盖写入。公司/产品/统计/报价旧审核入口仍待后续贯通。其他格式固定字段可先在Python提取后交本入口，来源原件不删除。

实际首批3园区、3条来源登记、4个数字字段：Heathrow规划IT48MW/设施功率64MW，Dangjin规划IT140MW，HyperDC MBL1规划IT400MW。来自已归档原件，未做真假判断，原133+13园区和原26站点观测不变。Spark隔离登记0.092801秒，重放0.0405秒、全部already_registered且文件不变。数字仅来源陈述，不认定已投运，实际写入与上线回执另计。

私有输入、batch-receipt、CI/生产回执在两机~/.local/state/inresearch.ai/source-statement-intake-20261012/。既有PR843先有published回执，再暂停唯一协调器新接纳；本任务拥有stop-coordinator。上线核网站镜像/API/首页待查标记和Spark版本、无写重放后，移除本任务标记并恢复原ai.inresearch.dcd.publication-queue-20261009 LaunchAgent。代码/规范本批全套CI；v3纯追加当前仍full，后续需严格证明后再分流，不能称已优化。
