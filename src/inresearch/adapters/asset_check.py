#!/usr/bin/env python3
"""3D 模型登记自检（本机跑）——放完 .glb 先跑这个，再刷页面。

    python3 manage.py asset-check

检查：manifest 能否解析 / 文件在不在 / 是不是真 GLB / 体积是否超线 /
来源与许可是否填了 / 有没有放了文件却忘了登记。零依赖，纯标准库。
"""

from inresearch.paths import project_root
import json
import os
import struct
import sys

ROOT = str(project_root())
MODELS = os.path.join(ROOT, "web/assets", "models")
MANIFEST = os.path.join(MODELS, "manifest.json")
MAX_MB = 10.0
PAGES = {"rack3d", "bom3d"}


def main() -> int:
    if not os.path.isfile(MANIFEST):
        print("✗ 找不到 assets/models/manifest.json")
        return 1
    try:
        mf = json.load(open(MANIFEST, encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"✗ manifest.json 不是合法 JSON：第 {e.lineno} 行 {e.msg}")
        print("  常见原因：最后一项后面多了逗号，或引号用了中文引号")
        return 1

    models = mf.get("models", [])
    errors, warns = [], []
    registered = set()

    for i, m in enumerate(models, 1):
        tag = f"第 {i} 条（{m.get('file', '未填 file')}）"
        fn = m.get("file")
        if not fn:
            errors.append(f"{tag}：缺 file 字段")
            continue
        registered.add(fn)
        path = os.path.join(MODELS, fn)

        if not os.path.isfile(path):
            errors.append(f"{tag}：文件不存在——检查文件名大小写与扩展名是否为 .glb")
            continue
        size_mb = os.path.getsize(path) / 1048576
        with open(path, "rb") as f:
            head = f.read(12)
        if head[:4] != b"glTF":
            errors.append(f"{tag}：不是 GLB 文件（开头不是 glTF）——.gltf/.fbx/.obj 都不行，"
                          f"下载时要选 glTF Binary (.glb)")
            continue
        ver = struct.unpack("<I", head[4:8])[0]
        if ver != 2:
            warns.append(f"{tag}：glTF 版本 {ver}，本项目按 2.0 加载")

        if size_mb > MAX_MB:
            errors.append(f"{tag}：{size_mb:.1f}MB 超过 {MAX_MB}MB 上线（铁律 A3）——"
                          f"用 gltf.report 或 Blender 减面后再导出")
        elif size_mb > MAX_MB * 0.6:
            warns.append(f"{tag}：{size_mb:.1f}MB 偏大，手机端加载会慢")

        page = m.get("page")
        if page not in PAGES:
            errors.append(f"{tag}：page 必须是 rack3d 或 bom3d，现在是 {page!r}")
        if not (m.get("source") or "").strip():
            errors.append(f"{tag}：source 必填（下载页 URL）——来源留痕是纪律")
        if not (m.get("license") or "").strip():
            errors.append(f"{tag}：license 必填（如 CC0 / CC-BY 署名）——未知许可不进库")

        scale = m.get("scale")
        if scale not in (None, "auto") and not isinstance(scale, (int, float)):
            errors.append(f"{tag}：scale 只能是数字或 \"auto\"（留空即自动适配）")

        if not errors or True:
            mode = "自动适配尺寸" if scale in (None, "auto") else f"手动缩放 {scale}"
            extra = "，并隐藏程序化机柜" if m.get("hideRack") else ""
            print(f"  · {fn} → {page}，{mode}{extra}（{size_mb:.1f}MB，{m.get('license')}）")

    on_disk = {f for f in os.listdir(MODELS) if f.lower().endswith(".glb")} if os.path.isdir(MODELS) else set()
    for f in sorted(on_disk - registered):
        warns.append(f"{f}：文件在目录里但 manifest 没登记——页面不会加载它")

    print()
    for w in warns:
        print(f"⚠ {w}")
    for e in errors:
        print(f"✗ {e}")
    if errors:
        print(f"\n不通过：{len(errors)} 个问题要修")
        return 1
    print(f"通过：{len(models)} 条登记，{len(warns)} 个提醒。"
          f"\n下一步：python3 -m http.server 8000 然后开 http://localhost:8000/rack3d.html 看效果")
    return 0


if __name__ == "__main__":
    sys.exit(main())
