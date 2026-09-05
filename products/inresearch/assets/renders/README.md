# 部件渲染图（拆解海报素材）

九张透明底高清 PNG（1840×1280），供 `poster.html` 拼装 B300 风格拆解海报。

- **来源与版权**：全部由本项目 `bake.html`（内部烘焙工具页）自渲染——three.js 程序化几何 +
  canvas 程序纹理 + assets/hdri/studio.exr（CC0）光照。**自有版权，无第三方素材。**
- **重烘方法**（改了 3D 场景或换了专业 .glb 模型后）：
  ```bash
  python3 -m http.server 8123 &
  for p in chassis fans coldplate gpu-board hbm mobo nic psu ssd; do
    chromium --headless=new --window-size=920,640 --force-device-scale-factor=2 \
      --default-background-color=00000000 --screenshot="assets/renders/$p.png" \
      "http://localhost:8123/bake.html?part=$p"
  done
  ```
- 单图 100-500KB，总量约 3MB（A3 批复的 ≤10MB/文件量级内）。
