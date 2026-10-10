#!/usr/bin/env python3
"""从 Sketchfab 官方 API 下载模型，打包成单文件 .glb 并自动登记（本机跑）。

    export SKETCHFAB_TOKEN=你的令牌      # 只需设一次，见下方「令牌哪里拿」
    python3 manage.py asset-download <模型URL或uid> [--name 文件名] [--page rack3d] [--hide-rack]

做四件事：① 查模型元数据（许可/是否可下载/作者）② 走官方下载接口取 glTF 包
③ 纯 Python 打包成单文件 .glb（Sketchfab 给的是散件 zip，我们的页面要 .glb）
④ 调用共享导入用例，在 web/assets/models/manifest.json 登记 candidate 与内容 SHA；不覆盖既有版本或决定。

令牌哪里拿：登录 Sketchfab → 右上头像 → Settings → Password & API →「API Token」整串复制。
它等同密码，别提交进 git；写进 ~/.zshrc 的 export 里最省事。

零依赖：纯标准库（urllib/zipfile/json/struct）。
"""

from inresearch.paths import project_root
from pathlib import Path
from inresearch.materials import model_assets
from inresearch.workflow.model_assets import import_candidate
import argparse
import json
import os
import re
import struct
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile

ROOT = str(project_root())
API = "https://api.sketchfab.com/v3"


def api_get(url, token=None):
    req = urllib.request.Request(url, headers={"User-Agent": "InResearch-DatacenterHub/1.0"})
    if token:
        req.add_header("Authorization", f"Token {token}")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def uid_from(arg):
    """接受完整 URL 或裸 uid。URL 形如 .../server-v2-console-<32位十六进制>"""
    m = re.search(r"([0-9a-f]{32})", arg)
    if not m:
        sys.exit(f"✗ 认不出模型 uid：{arg}\n  粘完整模型页 URL 即可")
    return m.group(1)


def gltf_to_glb(gltf_path):
    """把散件 glTF（scene.gltf + .bin + 贴图）打包成单文件 GLB。纯标准库实现。"""
    base = os.path.dirname(gltf_path)
    g = json.loads(Path(gltf_path).read_text(encoding="utf-8"))
    blob = bytearray()

    def append(data):
        """写入合并二进制块，返回 (起始偏移, 长度)；每段按 4 字节对齐"""
        off = len(blob)
        blob.extend(data)
        while len(blob) % 4:
            blob.append(0)
        return off, len(data)

    def read_uri(uri):
        if uri.startswith("data:"):
            return None                      # 已内嵌，不动
        p = (Path(base) / urllib.request.url2pathname(uri)).resolve()
        if not p.is_relative_to(Path(base).resolve()) or ":" in uri:
            raise ValueError("external_gltf_resource_forbidden")
        return p.read_bytes()

    # 1) 合并所有 buffer，记下每个 buffer 在合并块里的偏移
    buf_off = []
    for b in g.get("buffers", []):
        data = read_uri(b["uri"]) if "uri" in b else None
        if data is None:
            sys.exit("✗ 该模型的 buffer 是内嵌 data URI，本脚本暂不处理——请手动用 gltf.report 转换")
        off, _ = append(data)
        buf_off.append(off)

    # 2) 原有 bufferView 全部改指向合并后的 buffer 0，偏移整体平移
    for bv in g.get("bufferViews", []):
        bv["byteOffset"] = bv.get("byteOffset", 0) + buf_off[bv.get("buffer", 0)]
        bv["buffer"] = 0

    # 3) 外链贴图转成 bufferView（GLB 不能有外部文件）
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
    for img in g.get("images", []):
        uri = img.get("uri")
        if not uri or uri.startswith("data:"):
            continue
        data = read_uri(uri)
        off, ln = append(data)
        g.setdefault("bufferViews", []).append({"buffer": 0, "byteOffset": off, "byteLength": ln})
        img.pop("uri")
        img["bufferView"] = len(g["bufferViews"]) - 1
        img["mimeType"] = mime.get(os.path.splitext(uri)[1].lower(), "image/png")

    g["buffers"] = [{"byteLength": len(blob)}]

    # 4) 拼 GLB：头 + JSON 块 + BIN 块（两块都按 4 字节对齐）
    js = json.dumps(g, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(blob)
    out = bytearray(b"glTF" + struct.pack("<II", 2, total))
    out += struct.pack("<I", len(js)) + b"JSON" + js
    out += struct.pack("<I", len(blob)) + b"BIN\0" + bytes(blob)
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model", help="Sketchfab 模型页 URL 或 32 位 uid")
    ap.add_argument("--name", help="存成什么文件名（默认按模型名生成）")
    ap.add_argument("--page", default="rack3d", choices=["rack3d", "bom3d"])
    ap.add_argument("--hide-rack", action="store_true", help="记录拟替换机柜的布局；候选不会自动启用")
    ap.add_argument("--token", default=os.environ.get("SKETCHFAB_TOKEN", ""))
    a = ap.parse_args()

    if not a.token:
        sys.exit("✗ 没有 API 令牌。先 export SKETCHFAB_TOKEN=xxx\n"
                 "  取令牌：Sketchfab → Settings → Password & API → API Token")

    uid = uid_from(a.model)
    print(f"查模型 {uid} …")
    try:
        m = api_get(f"{API}/models/{uid}")
    except urllib.error.HTTPError as e:
        sys.exit(f"✗ 查不到该模型（HTTP {e.code}）——链接对吗？私有模型也取不到")

    lic = (m.get("license") or {}).get("label") or "未标注"
    author = (m.get("user") or {}).get("displayName", "?")
    print(f"  名称：{m.get('name')}\n  作者：{author}\n  许可：{lic}\n  可下载：{m.get('isDownloadable')}")

    if not m.get("isDownloadable"):
        sys.exit("✗ 该模型作者未开放下载——换一个（搜索页左侧勾 Downloadable）")
    if not model_assets.permitted_license(lic):
        sys.exit(f"✗ 许可「{lic}」不在白名单（CC0 / Public Domain / CC Attribution）——"
                 f"未知或禁改的许可不进库。")

    print("取下载链接 …")
    try:
        d = api_get(f"{API}/models/{uid}/download", a.token)
    except urllib.error.HTTPError as e:
        sys.exit(f"✗ 下载接口 HTTP {e.code}——令牌无效或已过期就重取一次" if e.code == 401
                 else f"✗ 下载接口 HTTP {e.code}")
    if "gltf" not in d:
        sys.exit(f"✗ 该模型没有 glTF 格式可下（有：{list(d)}）")

    url, size = d["gltf"]["url"], d["gltf"].get("size", 0)
    print(f"下载中（{size / 1048576:.1f}MB）…")
    with tempfile.TemporaryDirectory() as tmp:
        zp = os.path.join(tmp, "m.zip")
        urllib.request.urlretrieve(url, zp)
        with zipfile.ZipFile(zp) as z:
            for item in z.infolist():
                destination = (Path(tmp) / item.filename).resolve()
                if not destination.is_relative_to(Path(tmp).resolve()) or (item.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("unsafe_model_archive_path")
            z.extractall(tmp)
        # 包里可能直接是 .glb，也可能是 scene.gltf 散件
        glb = next((os.path.join(r, f) for r, _, fs in os.walk(tmp) for f in fs if f.endswith(".glb")), None)
        if glb:
            data = Path(glb).read_bytes()
            print("  包内已是 .glb，直接用")
        else:
            gp = next((os.path.join(r, f) for r, _, fs in os.walk(tmp) for f in fs if f.endswith(".gltf")), None)
            if not gp:
                sys.exit("✗ 压缩包里既没有 .glb 也没有 .gltf")
            print("  打包散件 → 单文件 .glb …")
            data = gltf_to_glb(gp)

    slug = a.name or re.sub(r"[^a-z0-9]+", "_", (m.get("name") or uid).lower()).strip("_")[:40]
    if not slug.endswith(".glb"):
        slug += ".glb"
    e = import_candidate(ROOT, slug, data, page=a.page,
        source=m.get("viewerUrl") or m.get("uri", ""),
        license=f"{lic}（作者：{author}）", hide_rack=a.hide_rack)
    print(f"✓ 登记：{e['file']} · {e['status']} · {len(data) / 1048576:.1f}MiB")
    print("下一步：python3 manage.py asset-check；在 compare.html 审阅候选。"
          "采用须在 manifest 中明确记录决定，下载不会使模型进入场景。")


if __name__ == "__main__":
    main()
