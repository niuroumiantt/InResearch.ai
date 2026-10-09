# TA17 来源与复用边界

- 尺度/身份/类别总数：本次基线14da1b8e的 `framework/bom.json`，逐ID的scale/system与资源原字节见[61绑定](scale-asset-bindings-v1.json)。尺度是现行骨架中的分类，不认证实物尺寸或特定设备只适用于该空间。
- 47详细类别的官方类别资料、原生生成/编辑过程、具体支持范围和未知项：沿用[TA16来源](../TA-16/SOURCES.md)、[原制作登记](../TA-16/candidate-asset-manifest-v2.json)及[实际发布](../TA-16/publication-20261010.json)。本次没有新增对应技术主张或修改它们。
- 原14类别：SSD TA01，服务器 TA11，GPU TA04，CPU/DRAM TA06，HBM TA05，NIC TA07，PSU TA08，风扇 TA09，冷板 TA10，建筑 TA36，消防 TA37，安防 TA38，空柜架 TA39。各项原acceptance/publication与master保持，整柜系统图为TA16明确复用TA13的通用示例，空柜架仍是TA39，不误合并对象。
- R1：`docs/design/technical-atlas/references/01-chain.png` 实际查看，SHA826f87b7d3ce998f96c8a6f244a4bf7124feae4ea59067dfe9db5273b4726486。仅风格与跨尺度可辨细节参考；不取得参考图中的型号、制造/安装路径或真实比例。
- 本项[五代表受控合成](overview-composition-v1.json)实际复用已验PNG，不调用新imagegen、不重采样覆盖原件；五输入原字节保持，新增1536×1024画布不冒称这些设备按共同尺度摆放。

选型、接口/连接、电压/容量/功率、材料/化学相容、内部结构、尺寸/载荷、供应者与项目实装数量仍以各原图范围为准。五尺度图示不把替代设备串联、不授予维护或热插拔步骤。软件/基型/权利入口不变成物理零件或可采购权利。
