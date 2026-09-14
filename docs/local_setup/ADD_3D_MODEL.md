# 登记、比较和采用 3D 模型

现行产品规则见 [03 对象与协作](../../framework/03_bom_and_collaboration.md)，实现职责见 [09 软件契约](../../framework/09_software_contracts.md)。本指南适用于作者工作区；网站只读发布结果。

## 一份登记，三种状态

`web/assets/models/manifest.json` 是唯一登记入口，`schema_version` 为 1。

- `candidate`：已接收、供选型比较，尚不进入研究场景。
- `adopted`：已核对内容、来源许可、物理身份、位置及用途；明确记录 `decision`，进入指定页面。
- `rejected`：明确未采用，保留原文件和决定，只在比较台按身份显示。

下载成功、许可字段存在、模型外观精细或网格多，都不是采用结论。现有 `server_v2_console.glb` 延续原登记中的不采用决定，不能因为曾作联调参照就重新加载到研究场景。

## 导入候选

在 `~/code/inresearch.ai` 的干净作者工作区或独立工作树中操作。原始下载材料保留；上传 Git 的小体积 GLB 仍须遵守已有来源、许可及 10 MiB 限制。

已配置 Sketchfab 令牌时，原下载命令继续可用：

```bash
python3 manage.py asset-download '模型来源页 URL' --name rack_reference --page rack3d
python3 manage.py asset-check
```

令牌由本机环境 `SKETCHFAB_TOKEN` 提供，不写进仓库。下载器适配外部 API，共享导入用例验证独立 GLB、体积、SHA、来源许可并登记 candidate。`--hide-rack` 仅声明拟采用后的替换布局，不授予采用状态。许可不在项目允许范围时停止；旧 `--force-license` 绕过入口已退出。

同名同内容的重试复用原条目，保留已有决定和变换；同名不同内容拒绝，使用新文件名。原文件成功落盘但登记提交前中断时，完整文件保留，使用同一输入重试可恢复登记。提交可见但持久性未确认时先检查登记；不可盲目删除、覆盖或回滚文件。

手工接收的 GLB 也须复制到新的 `web/assets/models/<文件名>.glb`，按同一字段登记 candidate，并用 `shasum -a 256` 取得真实内容 SHA。不得填示例哈希或覆盖已有文件。文件名只用小写字母、数字、下划线、连字符和点，以 `.glb` 结尾；所有贴图和缓冲区必须内嵌。

## 登记字段与审阅

| 字段 | 责任 |
|---|---|
| `file` / `sha256` | 文件名与确切字节的 SHA-256；版本变化重新审阅 |
| `page` | `rack3d` 或 `bom3d` |
| `status` | `candidate`、`adopted` 或 `rejected` |
| `decision` | adopted/rejected 必填：采用或拒绝依据、用途和审阅范围；不编造审阅人或已验证内容 |
| `source` / `license` | 来源页 HTTP(S) URL、明确许可及必要作者署名；字段验证不代替许可核对 |
| `scale` | 省略/null/auto 按高度适配；数字必须为正且有限 |
| `fitHeight` | 自动适配目标高度；正且有限。默认由场景提供 |
| `position` / `rotationY` | 有限的三维偏移与 Y 轴弧度；自动适配先居中落地再加偏移 |
| `hideRack` | 布尔值，仅 rack3d 可为 true；整批模型就绪后才隐藏程序化机柜 |

明确采用前，在比较台核对可见模型、署名、比例和网格信息，再在真实场景核对位置、遮挡及物理语义。网格数量和名称仅是线索，不能证明内部装配真实或爆炸动画已绑定。没有依据的具体型号、内部结构和研究结论保持未知。

本地服务使用项目路由与 API：

```bash
python3 manage.py serve --help
python3 manage.py serve
```

按命令输出地址打开 `/compare.html`；可用 `?f=a.glb,b.glb` 过滤已登记文件。未登记名称仅显示提示，不发起模型请求。旧 `python3 -m http.server` 无法承接项目 API，不再作为验收入口。

## 验证与发布

运行 `asset-check` 核对登记、实际 GLB 内容、SHA、许可标签和变换；运行治理、严格数据校验与相关测试。登记变化必须与规范、清单及审阅依据一并提交，通过 CI 后按仓库发布流程上线。没有“下载后自动采用”或“每 30 分钟自动 commit/push”的保证。

网站 API 由同一登记投影：场景只接收 adopted，比较台接收全部身份。已登记 GLB 的静态 URL 也从此登记解析，无需再复制一条 routes 记录。浏览器核对内容 SHA 后解析；失败可重试，旧模型保留到新批全部成功。移除采用状态后，新批为空会撤下旧加载组并恢复程序化机柜。

模型导入/加载不修改研究证据、原件库、模型推理配置或 Spark 服务。HDR、面板纹理和场景构图按各自后续验收处理。
