#!/usr/bin/env python3
"""从 Sketchfab 官方 API 下载模型，打包成单文件 .glb 并自动登记（本机跑）。

    export SKETCHFAB_TOKEN=你的令牌      # 只需设一次，见下方「令牌哪里拿」
    python3 manage.py asset-download <模型URL或uid> [--name 文件名] [--page rack3d] [--hide-rack]

做四件事：① 查模型元数据（许可/是否可下载/作者）② 走官方下载接口取 glTF 包
③ 纯 Python 打包成单文件 .glb（Sketchfab 给的是散件 zip，我们的页面要 .glb）
④ 自动写进 assets/models/manifest.json，source 与 license 从 API 原样带回——来源留痕不靠手填。

令牌哪里拿：登录 Sketchfab → 右上头像 → Settings → Password & API →「API Token」整串复制。
它等同密码，别提交进 git；写进 ~/.zshrc 的 export 里最省事。

零依赖：纯标准库（urllib/zipfile/json/struct）。
"""

from inresearch.paths import project_root
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
MODELS = os.path.join(ROOT, "web/assets", "models")
API = "https://api.sketchfab.com/v3"
MAX_MB = 10.0
# 允许进库的许可（未知许可不进库——铁律）
OK_LICENSE = re.compile(r"CC0|Public Domain|CC Attribution(?!.*NoDeriv)", re.I)


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
    g = json.load(open(gltf_path, encoding="utf-8"))
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
        p = os.path.join(base, urllib.request.url2pathname(uri))
        return open(p, "rb").read()

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


def register(fname, model, page, hide_rack):
    """写进 manifest：source 与 license 从 API 带回，不靠手填"""
    path = os.path.join(MODELS, "manifest.json")
    mf = json.load(open(path, encoding="utf-8"))
    lic = (model.get("license") or {}).get("label") or "未知"
    author = (model.get("user") or {}).get("displayName") or ""
    entry = {
        "file": fname,
        "page": page,
        "source": model.get("viewerUrl") or model.get("uri", ""),
        "license": f"{lic}（作者：{author}）" if author else lic,
    }
    if hide_rack:
        entry["hideRack"] = True
    mf["models"] = [m for m in mf.get("models", []) if m.get("file") != fname] + [entry]
    json.dump(mf, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return entry


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model", help="Sketchfab 模型页 URL 或 32 位 uid")
    ap.add_argument("--name", help="存成什么文件名（默认按模型名生成）")
    ap.add_argument("--page", default="rack3d", choices=["rack3d", "bom3d"])
    ap.add_argument("--hide-rack", action="store_true", help="用它替换程序化机柜")
    ap.add_argument("--token", default=os.environ.get("SKETCHFAB_TOKEN", ""))
    ap.add_argument("--force-license", action="store_true", help="许可不在白名单也强行入库（自担）")
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
    if not OK_LICENSE.search(lic) and not a.force_license:
        sys.exit(f"✗ 许可「{lic}」不在白名单（CC0 / Public Domain / CC Attribution）——"
                 f"未知或禁改的许可不进库。\n  确认可商用可改造再加 --force-license")

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
            z.extractall(tmp)
        # 包里可能直接是 .glb，也可能是 scene.gltf 散件
        glb = next((os.path.join(r, f) for r, _, fs in os.walk(tmp) for f in fs if f.endswith(".glb")), None)
        if glb:
            data = open(glb, "rb").read()
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
    os.makedirs(MODELS, exist_ok=True)
    out = os.path.join(MODELS, slug)
    open(out, "wb").write(data)
    mb = len(data) / 1048576
    print(f"✓ 写入 assets/models/{slug}（{mb:.1f}MB）")
    if mb > MAX_MB:
        print(f"⚠ 超过 {MAX_MB}MB 上线（铁律 A3）——上 gltf.report 减面后替换，或换个模型")

    e = register(slug, m, a.page, a.hide_rack)
    print(f"✓ 已登记：page={e['page']} license={e['license']}")
    print("\n下一步：\n  python3 manage.py asset-check\n"
          "  python3 -m http.server 8000 → http://localhost:8000/rack3d.html")


if __name__ == "__main__":
    main()
