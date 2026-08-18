# GLB 3D 模型库（照片级渲染的资产位）

A3 批复（2026-08-18，方案①）：允许 .glb 模型进 git；**每个模型必须在 manifest.json 登记
file/page/position/scale + source/license**——来源留痕是纪律，未知许可的模型不进库。

## 怎么加模型（本机操作即可，无需会话）

1. 从 Sketchfab（筛 CC0/CC-BY 可下载）、CGTrader 免费区等下载 **glTF Binary (.glb)** 格式，
   服务器机柜搜索词：`server rack 19 inch`、`data center rack`、`GPU server`。
2. 放进本机 `~/code/inresearch.ai/assets/models/`；30 分钟自动同步链会推上 GitHub 与服务器。
3. 在 `manifest.json` 的 `models` 数组登记，例如：

```json
{
  "file": "server_rack.glb",
  "page": "rack3d",
  "position": [0, 0, 0],
  "scale": 2.5,
  "rotationY": 0,
  "hideRack": true,
  "source": "https://sketchfab.com/3d-models/xxxx",
  "license": "CC0 / CC-BY（署名写这里）"
}
```

4. 刷新页面即生效（GLTFLoader 自动装载；`hideRack: true` 时隐藏程序化机柜用模型替身）。

## 约束

- 单文件建议 ≤10MB（手机端加载体验）；大模型先用 gltf.report 或 Blender 减面导出。
- CC-BY 模型的署名写进 manifest 的 license 字段，对外导出图注带上。
