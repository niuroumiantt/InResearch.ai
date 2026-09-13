# HDR 环境贴图（IBL 光照源）

A3 批复（2026-08-18，方案①）：3D 可视化二进制资产允许进 git，来源与许可必须留痕。

| 文件 | 用途 | 来源 | 许可 |
|---|---|---|---|
| studio.exr | rack3d 机柜拆解台环境光照 | Poly Haven（经 npm @pmndrs/assets v1.7.0 打包分发） | CC0 1.0 |
| warehouse.exr | bom3d 数据中心全景环境光照 | 同上 | CC0 1.0 |
| lab.exr | 备用（实验室内景） | 同上 | CC0 1.0 |

- 均为低分辨率压缩 EXR（110-166KB/个），只作 PMREM 光照卷积，不作背景图。
- 加载失败时页面自动回退程序化摄影棚环境（proceduralEnv），不会黑屏。
- 换新 HDR：放文件进本目录 + 改页面里 EXRLoader 的路径 + 在本表登记来源。
