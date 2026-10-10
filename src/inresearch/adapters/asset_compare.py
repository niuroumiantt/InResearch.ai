#!/usr/bin/env python3
"""3D 模型体检与横向对比（本机跑）——下载多个候选后，用数据选，不靠眼缘。

    python3 manage.py asset-compare                 # 比 assets/models/ 里所有 .glb
    python3 manage.py asset-compare ~/Downloads     # 比某个目录（选型阶段用这个）

为什么需要它：Sketchfab 页面只写三角面数，**不告诉你模型有没有可分离的子部件**——
而这决定了能不能做爆炸拆解。本工具直接读 GLB 内部结构，给出可拆解性评分。

零依赖：纯标准库。
"""

from inresearch.paths import project_root
import json
from pathlib import Path
import os
import re
import struct
import sys

ROOT = str(project_root())
# 名字里出现这些词 = 该子网格很可能是一个可独立拆出的部件
PART_WORDS = re.compile(
    r"server|node|sled|tray|blade|door|panel|rail|psu|power|fan|switch|shelf|"
    r"drive|disk|cover|side|frame|post|cable|unit|module|rack", re.I)
BRAND_WORDS = re.compile(r"ovh|dell|hpe|hp_|cisco|ibm|lenovo|supermicro|logo|brand", re.I)


def read_glb(path):
    d = Path(path).read_bytes()
    if d[:4] != b"glTF":
        return None, "不是 GLB（可能是 .gltf 散件或别的格式）"
    off, chunks = 12, {}
    while off < len(d) - 8:
        ln, ty = struct.unpack("<I4s", d[off:off + 8])
        chunks[ty.decode(errors="replace").strip("\0")] = (off + 8, ln)
        off += 8 + ln
    if "JSON" not in chunks:
        return None, "GLB 里没有 JSON 块"
    s, ln = chunks["JSON"]
    return json.loads(d[s:s + ln].decode("utf-8", "replace")), None


def tri_count(g):
    """按 accessor count 估算三角形数"""
    acc = g.get("accessors", [])
    total = 0
    for m in g.get("meshes", []):
        for p in m.get("primitives", []):
            mode = p.get("mode", 4)
            if mode != 4:                       # 只算 TRIANGLES
                continue
            i = p.get("indices")
            if i is not None and i < len(acc):
                total += acc[i].get("count", 0) // 3
            else:
                pos = p.get("attributes", {}).get("POSITION")
                if pos is not None and pos < len(acc):
                    total += acc[pos].get("count", 0) // 3
    return total


def inspect(path):
    g, err = read_glb(path)
    size_mb = os.path.getsize(path) / 1048576
    if err:
        return {"file": os.path.basename(path), "error": err, "size": size_mb}

    nodes = g.get("nodes", [])
    meshes = g.get("meshes", [])
    names = [n.get("name", "") for n in nodes] + [m.get("name", "") for m in meshes]
    # 可拆解性：有多少个带"部件味"名字的节点，且网格数够多
    part_named = [n for n in names if PART_WORDS.search(n or "")]
    brands = sorted({b.group(0).lower() for b in (BRAND_WORDS.search(n or "") for n in names) if b})

    # 评分：网格数是硬条件（合并成 1-3 个就基本没法拆）
    n_mesh = len(meshes)
    if n_mesh >= 12 and part_named:
        tear, why = "优", f"{n_mesh} 个网格，{len(part_named)} 个部件名 → 可分网格；物理拆解关系待核对"
    elif n_mesh >= 6:
        tear, why = "中", f"{n_mesh} 个网格 → 存在多个网格；拆解关系待核对"
    else:
        tear, why = "差", f"只有 {n_mesh} 个网格（已合并）→ 网格少；不能据此推定实际装配"

    return {
        "file": os.path.basename(path), "size": size_mb,
        "tris": tri_count(g), "meshes": n_mesh, "nodes": len(nodes),
        "mats": len(g.get("materials", [])), "imgs": len(g.get("images", [])),
        "tear": tear, "why": why, "brands": brands,
        "gen": (g.get("asset") or {}).get("generator", "?")[:22],
        "parts": [n for n in part_named][:6],
    }


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "web/assets", "models")
    d = os.path.expanduser(d)
    files = sorted(f for f in os.listdir(d) if f.lower().endswith(".glb")) if os.path.isdir(d) else []
    if not files:
        sys.exit(f"{d} 里没有 .glb 文件")

    rows = [inspect(os.path.join(d, f)) for f in files]
    print(f"\n{'文件':<30}{'体积':>8}{'三角面':>10}{'网格':>6}{'材质':>6}  {'可拆解':<6} 说明")
    print("─" * 108)
    for r in rows:
        if r.get("error"):
            print(f"{r['file'][:29]:<30}{r['size']:>7.1f}M  ✗ {r['error']}")
            continue
        flag = "⚠" if r["size"] > 10 or r["tris"] > 500000 else " "
        print(f"{r['file'][:29]:<30}{r['size']:>7.1f}M{r['tris']:>10,}{r['meshes']:>6}{r['mats']:>6}  "
              f"{r['tear']:<6} {r['why']}{flag}")
        if r["brands"]:
            print(f"{'':<30}⚠ 疑似品牌标识：{'、'.join(r['brands'])}——对外使用前须确认")
        if r["parts"]:
            print(f"{'':<30}  部件名样例：{'、'.join(r['parts'])}")

    print("\n选型标准（按重要性排序）：")
    print("  1. 可拆解=优  —— 网格 ≥12 且有部件名，仅提供拆解检查线索，实际装配和动画绑定仍待核对")
    print("  2. 无品牌标识 —— 对外材料不能带别家 logo（我们的对外三条）")
    print("  3. 体积 ≤10MB、三角面 ≤50 万 —— 铁律 A3 与手机端体验")
    print("  4. CC0 优于 CC-BY —— CC0 无署名负担")
    print("\n下一步：选定后把它按 docs/local_setup/ADD_3D_MODEL.md 登记候选到 web/assets/models/，或直接 python3 manage.py asset-check")


if __name__ == "__main__":
    main()
