# GB300机架规格与Grace缓存：存量追加

从已上线433条、143对象接续。本批为既有GB300 NVL72追加9项整架内存、CPU核数和不同精度算力，为既有Grace CPU Superchip追加3项缓存，共12条，累计445条、143对象。433条旧记录和全部对象身份保留，不修订历史结论。

GB300 Fast Memory 37TB是合计，不能与CPU/GPU内存重复相加；CPU内存17TB LPDDR5X及14TB/s保留同一配置。CPU核数2592是整架。已有配置字段含36颗CPU，故不重复新增CPU数量。FP4原单元格1440/1080及脚注2保留：前者稀疏，后者非稀疏，不构成区间。INT8、FP16/BF16、TF32按Tensor Core稀疏脚注；普通FP32不添加稀疏条件；FP64/FP64 Tensor Core按原组合标签，不拆造独立测量。

Grace取Superchip列：L1为每核64KB指令加64KB数据，L2每核1MB，L3整颗228MB，不串用C1列114MB。全部为厂商规格，不冒充实测站点或工作负载性能。有效/披露时间未知留空，保留既有首次接收时间。

两份原生HTML SHA为83a7bb71ac47368970d82dde1ec7859b4506b58620f4389dd34cf5adda93d206、c2953f81fa3fdf2886aea0cd83f3a599dda0c225f4b55aea455f200a3350fd4e。准备时间2026-10-11T21:44:48.710821Z，具名审核采用21:45:18.957039Z；固定提取与prepare0.050秒，采用加无写重放0.213秒，提取模型调用0。审核、CI、部署和公网耗时分开计。

Spark及M5私有目录`~/.local/state/inresearch.ai/stock-compute-caches-20261012/`保留原生字段、冻结上下文、提案及实际回执。普通新增不要求模型需求或全文阅读；不因此关闭171项来源、17个输入或HBM待核项。

唯一发布队列先完成既有PR805实际发布，再提交本批；维护标记owner为stock-compute-caches-20261012。实际生产镜像、API、首页及Spark验收后移除本批标记并恢复原LaunchAgent。源码提交与合并不证明上线，真实结果读私有acceptance.json。
