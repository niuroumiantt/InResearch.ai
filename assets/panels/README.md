# 真实设备面板图（机柜拆解台的贴图来源）

**全部来自 [NetBox devicetype-library](https://github.com/netbox-community/devicetype-library)，
许可 CC0 1.0（公共领域，可自由商用与改造）。** 该库收录 310 家厂商 5,655 款真实设备的
规格定义与机架正面图，是 DCIM 生态的公共资产。

| 本库文件 | 原始设备 | 厂商 | 用在哪 |
|---|---|---|---|
| server_nvme.png | AS-1114S-WN10RT（1U，10× NVMe） | Supermicro | 计算托盘正面 |
| server_gpu.png | SYS-620BT-CHASSIS（2U 多节点） | Supermicro | 明星托盘正面 |
| server_storage.png | SSG-610P-ACR12N4H（1U 存储） | Supermicro | 存储节点正面 |
| switch_tor.png | SSE-G3648B（48 口交换机） | Supermicro | TOR 交换机正面 |
| switch_ib.png | SN2100（高速交换机） | Mellanox | 高速互联层正面 |

**为什么用这些而不是厂商官网的产品照**：官网宣传照受版权保护，不能进库、不能商用改造；
这个库是 CC0，且图片是标准化的机架正面视图（等比、无背景、可直接当贴图）。

**换图/加图**：从上述库的 `elevation-images/<厂商>/<slug>.front.png` 取，
拷进本目录并在上表登记（**来源与许可留痕是纪律**），再改 rack3d.html 的 PANELS 表。
