# 真实设备面板图（机柜拆解台的贴图来源）

2026-10-08 图册迁移：五张来源贴图仍保留为原件，按 [白底技术图册规范](../../../framework/10_visual_atlas.md) 调整显示材质/光照；需要改画时另建来源关联展示版本，不覆写真实面板。逐项工作在 [迁移计划](../../../docs/design/technical-atlas/MIGRATION_PLAN.md) 登记。

**全部来自 [NetBox devicetype-library](https://github.com/netbox-community/devicetype-library)，
许可 CC0 1.0（公共领域，可自由商用与改造）。** 本项目保存五张来源原件；库规模不是本次核验结论。该库属于DCIM生态，图片仍为硬件外观资料，不是软件实体。

| 本库文件 | 原始设备 | 厂商 | 用在哪 |
|---|---|---|---|
| server_nvme.png | AS-1114S-WN10RT（1U，10× NVMe） | Supermicro | 计算托盘正面 |
| server_gpu.png | SYS-620BT-CHASSIS（多节点机箱） | Supermicro | 明星托盘正面 |
| server_storage.png | SSG-610P-ACR12N4H（1U 存储） | Supermicro | 存储节点正面 |
| switch_tor.png | SSE-G3648B（48 口交换机） | Supermicro | TOR 交换机正面 |
| switch_ib.png | SN2100（Ethernet交换机，旧文件名ib保留） | Mellanox | 高速互联层正面 |

**为什么用这些而不是厂商官网的产品照**：官网宣传照受版权保护，不能进库、不能商用改造；
这个库是 CC0，且图片是标准化的机架正面视图（等比、无背景、可直接当贴图）。

交互场景用 `scene-resources.js` 把图片画入稳定 CanvasTexture；网络、解码失败或重试期间保留机柜页声明的程序化设备前脸，材质不会收到空 Texture。页面退出时由纹理池统一释放。

**换图/加图**：从上述库的 `elevation-images/<厂商>/<slug>.front.png` 取，
拷进本目录并在上表登记（**来源与许可留痕是纪律**），再改 rack3d.html 的 PANEL 配置。

## 2026-10-10 来源显示批次 TA30–34

五张原件PNG保持字节、标识、可见端口/托架与原比例。实际本地Git blob哈希与官方目录metadata一致；精确官方图/YAML路径及许可核读见 [逐项来源复核](../../../docs/design/technical-atlas/TA-30/independent-provenance-original-review-v1.json)。官方 [CC0](https://github.com/netbox-community/devicetype-library/blob/master/LICENSE.txt) 原许可保留；不以许可取得型号精度或商标/专利认证。

显示版本 `display/*-contain.svg` 内嵌完整原PNG，等比居中于旧三维示例前脸，空白不补画接口。三维CanvasTexture以实际前脸宽高比留白，并补偿整数画布高的取整，原PNG不写回。声明的是外观来源，三维机箱尺寸/安装/数量、内部配置与来源设备相符性均未知。旧legacy入口保留，现代已采用场景不加载这五贴图。

原图分别为966×88、400×70、814×72、1820×180和999×211；低分辨率原件放大不成为高清母图。`server_gpu`是多节点机箱来源，文件名不证明GPU数量；`server_storage`不证明介质/RAID/阵列。SN2100由 [NVIDIA原产品资料](https://network.nvidia.com/files/doc-2020/pb-sn2100.pdf) 确认为Ethernet，`switch_ib`只保留历史文件名，不认证InfiniBand或现场协议/速率。

旧机柜界面“保留来源面板”显示同一CanvasTexture、来源就绪/程序化占位状态，并分别下载原PNG和来源关联等比SVG。失败/重试不是硬件状态；释放后的handle不能重新启动，替代/失败/退出清理其自有资源，不释放借用的模型。
