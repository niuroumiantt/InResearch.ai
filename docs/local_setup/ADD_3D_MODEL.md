# 给 3D 页面加一个真实模型（D4 本机作业）

**在 Mac mini（hermes）上做，全程约 10 分钟。** 做完 30 分钟内自动同步上站。

---

## 第 1 步：下模型

**去哪下**（按推荐顺序）：

| 站点 | 怎么筛 | 备注 |
|---|---|---|
| **Sketchfab** sketchfab.com | 搜索后左侧筛选勾 **Downloadable**，License 选 **CC0** 或 **CC Attribution** | 要注册免费账号；模型最多 |
| **Poly Haven** polyhaven.com/models | 全站 CC0，无需登录 | 数量少，但质量高、体积规范 |
| **Fab** fab.com | 筛 Free + 允许商用 | Epic 的站，需账号 |

**搜什么词**（英文，按用途）：
- 替换整柜 → `server rack`、`19 inch rack`、`data center rack`、`rack cabinet`
- 单台服务器 → `rack server 1U`、`GPU server`、`blade server`
- 场景点缀 → `data center`、`server room`

**下载格式必须选 `glTF Binary (.glb)`** ——单文件、自带贴图。
不要下 `.gltf`（会散成一堆文件）、`.fbx`、`.obj`、`.blend`，这三种页面加载不了。

**挑选标准**：文件 **≤10MB**（铁律 A3 的线）。Sketchfab 的模型页会写三角面数，
**50 万面以内**比较稳妥，再高手机会卡。

---

## 第 2 步：放文件

```bash
cd ~/code/inresearch.ai
mv ~/Downloads/你下载的文件.glb assets/models/server_rack.glb
```

文件名建议全小写、用下划线，别带空格和中文（`server_rack.glb`、`gpu_server.glb`）。

---

## 第 3 步：登记

编辑 `assets/models/manifest.json`，把 `"models": []` 改成：

```json
{
  "note": "……（这行别动）",
  "models": [
    {
      "file": "server_rack.glb",
      "page": "rack3d",
      "hideRack": true,
      "source": "https://sketchfab.com/3d-models/你下载的那一页地址",
      "license": "CC0"
    }
  ]
}
```

**五个字段就够了**，其余全部可以不填：

| 字段 | 填什么 |
|---|---|
| `file` | 文件名，跟你放进去的一模一样（区分大小写） |
| `page` | `rack3d`（机柜拆解台）或 `bom3d`（数据中心全景） |
| `hideRack` | `true` = 用这个模型替换我程序化搭的机柜；不想替换就删掉这行 |
| `source` | 下载页 URL——**来源留痕是纪律**，不填自检不过 |
| `license` | `CC0`，或 `CC-BY（作者名）`。**未知许可不进库** |

**不用填 `scale`。** 页面会自动量出模型高度并缩放到机柜等高、坐在地面上——
不管模型是用米、厘米还是英寸建的。想手动控制再看下面的进阶字段。

多个模型就在数组里加多条，**注意每条之间用逗号隔开、最后一条后面不要有逗号**。

---

## 第 4 步：自检（关键，别跳）

```bash
python3 pipeline/check_models.py
```

它会告诉你：JSON 写没写错、文件在不在、是不是真 GLB、体积超没超线、来源许可填没填。
**通过了再往下走**，否则你会对着一个空页面猜半天。

常见报错与解法：
- `不是 GLB 文件` → 你下的是 .gltf 或 .fbx，重下选 glTF Binary
- `文件不存在` → 文件名大小写对不上
- `不是合法 JSON` → 多半是最后一项后面多了个逗号，或者引号被输入法变成了中文引号
- `超过 10MB` → 上 gltf.report 拖进去用 Simplify 减面，或换个模型

---

## 第 5 步：本地看效果

```bash
python3 -m http.server 8000
```

浏览器开 **http://localhost:8000/rack3d.html** 。模型应该已经站在场地中央。
按 `Cmd+Option+I` 打开控制台能看到一行 `[模型] xxx.glb 自动适配：原高 x.xx → 缩放 x.xxxx`。

**如果位置/朝向不对**，回 manifest 加这几个字段微调（改完刷新即可）：

```json
{
  "file": "server_rack.glb", "page": "rack3d", "hideRack": true,
  "rotationY": 1.5708,          // 转 90°（弧度：90°=1.5708，180°=3.1416，270°=4.7124）
  "position": [2, 0, -3],       // 在自动落位基础上偏移 [左右, 上下, 前后]
  "fitHeight": 8,               // 想让它矮一点/高一点（默认≈11 = 整柜高）
  "source": "...", "license": "CC0"
}
```

想完全手动控制尺寸，就把 `scale` 填成数字（如 `0.05`），自动适配即关闭。

---

## 第 6 步：上站

不用做任何事。本机 launchd 每 30 分钟自动 `validate` + commit + push，
服务器 autopull 接力。想立刻上线就手动推一次：

```bash
git add assets/models/ && git commit -m "3D 模型入库：机柜（CC0）" && git push
```

---

## 做完告诉我，我接着做两件事

1. **爆炸动画绑定**：把拆解阶段的锚点绑到模型的子网格上，让专业模型也能逐级拆开
   （现在自动适配只是把模型摆进去，拆解动画还认的是程序化几何体）。
2. **海报重烘**：用新模型重跑 `bake.html` 九张渲染图，`poster.html` 自动升级。

---

## 一次性的提醒

- **CC-BY 的模型要署名**：`license` 字段写全 `CC-BY（作者名）`，对外导出图注要带上。
- **别下 "editorial use only" 或 "no derivatives" 的**，我们要商用+改造，许可不合。
- 模型是二进制，进 git 是 A3 方案①放开的例外——**≤10MB、来源许可登记齐全**这两条不能破。

---

## 附：Sketchfab 下载框里选哪个？

模型页点 Download 会列出四种，**选 `GLB`（Converted format）**：

| 格式 | 选不选 | 为什么 |
|---|---|---|
| **GLB** | ✅ **选这个** | 单文件，几何+贴图全打包，页面直接能用 |
| glTF | ❌ | 散件（scene.gltf + .bin + textures/），还得转 |
| obj | ❌ | 原始格式，页面加载不了 |
| usdz | ❌ | 苹果 AR 格式，页面加载不了 |

旁边的 `Texture size` 选 **1k** 就够（2k/4k 会让文件超过 10MB 线）。

## 附：用脚本自动下（批量加模型时省事）

`pipeline/fetch_sketchfab.py` 走官方 API，一条命令完成下载+转格式+登记，
**license 与 source 从 API 原样带回，不用手填**：

```bash
export SKETCHFAB_TOKEN=你的令牌      # 取令牌：Sketchfab → Settings → Password & API → API Token
python3 pipeline/fetch_sketchfab.py "https://sketchfab.com/3d-models/xxx-<uid>" --hide-rack
```

它会先查许可，**不在白名单（CC0 / Public Domain / CC Attribution）就拒绝下载**——
未知或禁改的许可不进库，这条纪律由脚本把关，不靠人记。
包里若是散件 glTF，脚本用内置的纯 Python 打包器转成单文件 .glb（已实测：
外部 .bin 几何与外部 PNG 贴图都能正确内嵌）。

一次性的：`--name` 指定文件名、`--page bom3d` 放到全景页、`--force-license` 强行放行（自担）。
