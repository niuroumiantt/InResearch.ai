#!/usr/bin/env python3
"""产品资料库管理器：作业计划 → 下载 → 归位 → 索引。零依赖（仅标准库）。

对应 `/admin/product/` 采集看板。资料本体不进 git（铁律），本机落在外置卷上，
仓库里只留一个软链 `product` 指过去——**路径常量因此永远稳定，换盘只重做软链**。

    ~/code/inresearch.ai/product  ──软链──▶  /Volumes/<卷>/<目录>/
                                                ├── library/        终态库（file_path 的根）
                                                ├── _inbox/         下载落地口，原文件名不改
                                                └── _needs_manual/  登录墙/验证码/许可不明

用法：
    python3 pipeline/product_library.py setup --volume "外置卷名" [--dir inresearch-product]
    python3 pipeline/product_library.py plan  [--priority P0,P1]     # 生成/刷新作业计划（不覆盖已填 URL）
    python3 pipeline/product_library.py fetch [--dry-run] [--limit N] [--priority P0] [--retry]
    python3 pipeline/product_library.py adopt [--row KEY --file 路径]  # 人工下的文件归位
    python3 pipeline/product_library.py status [--verify]

**只能在本机（Mac mini）跑**：云端会话的容器是临时的，且二进制不进 git。
外置卷未挂载时所有写操作直接中止——macOS 会在内置盘上凭空造出同名目录，
那才是真正会丢文件的失败方式。
"""
import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = ROOT / "product"                      # 仓库内软链（gitignore）
PLAN = ROOT / "data" / "product_docs_plan.csv"
INDEX = ROOT / "data" / "product_library_index.json"

DOC_TYPES = {"DS": "datasheet 规格书", "PB": "product brief", "BR": "brochure 产品册",
             "WEB": "官网产品页存档", "RA": "参考架构", "UM": "用户手册", "WP": "白皮书"}
STATUSES = {"todo", "downloaded", "needs_manual", "verified", "superseded"}
PLAN_COLS = ["company_id", "company_en", "sheet", "product_line", "model", "bom_part",
             "doc_type", "source_url", "referrer_page", "lang", "version", "pub_date",
             "status", "doc_id", "note"]

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " \
     "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
MAX_BYTES = 300 * 1024 * 1024                # 单份上限；超了多半是抓错了链接
TIMEOUT = 60


# ── 路径与卷 ─────────────────────────────────────────────────────────────

def norm2(s):
    """与 admin/product/index.html 的 norm2() 逐字对应——两边算出的型号 slug 必须一致，
    否则页面的「型号覆盖」永远对不上落盘的文件。"""
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", (s or "").lower()))


def safe(component):
    """目录名安全化：斜杠与冒号在 macOS 路径里是雷，其余（含中文）原样保留。"""
    return re.sub(r"[/:\x00]", "-", (component or "").strip()) or "_"


def store_root(require_write=True):
    """解析软链得到真实库根，并确认外置卷确实挂着。"""
    if not LINK.exists() and not LINK.is_symlink():
        sys.exit(f"没有 {LINK} —— 先跑：python3 pipeline/product_library.py setup --volume \"卷名\"")
    target = Path(os.path.realpath(LINK))
    parts = target.parts
    if len(parts) > 2 and parts[1] == "Volumes":
        vol = Path("/") / parts[1] / parts[2]
        if not os.path.ismount(str(vol)):
            sys.exit(f"外置卷 {vol} 没有挂载。**拒绝写入**：macOS 会在内置盘上凭空造出同名目录，"
                     f"文件看着写成功了，卷挂回来就「消失」。请先挂载再跑。")
    if not target.is_dir():
        if require_write:
            sys.exit(f"库根 {target} 不存在（软链悬空）。挂上卷，或重跑 setup 指向新位置。")
        return None
    return target


def dirs(root):
    return root / "library", root / "_inbox", root / "_needs_manual"


# ── 计划表 ───────────────────────────────────────────────────────────────

def model_tokens(s):
    """与页面 modelTokens() 同口径：把 representative_models 拆成可落盘的型号。

    两边算出的型号集合必须一致——不一致的话，落盘的文件在看板上永远归不进任何一个型号 tab。
    """
    cjk = re.compile(r"[一-鿿]")
    raw = re.sub(r"[（(][^）)]*[）)]", "", s or "")
    out = []
    for t in re.split(r"[、;；]", raw):
        t = t.strip()
        if not t:
            continue
        parts = [x.strip() for x in t.split("/")]
        if "/" in t and len(t) < 40 and all(re.match(r"^[A-Za-z0-9]", x) for x in parts if x):
            m = re.search(r"\s+(.+)$", parts[-1])
            tail = m.group(1) if m else ""
            for x in parts:
                head = re.sub(r"\s+.*$", "", x)
                out.append(head + (" " + tail if tail and tail not in x and not cjk.search(tail) else ""))
        else:
            out.append(t)
    res = []
    for t in out:
        if re.match(r"^[A-Za-z0-9]", t):
            m = cjk.search(t)
            if m and m.start() > 1:
                t = t[:m.start()].strip()
        if 1 < len(t) < 40 and not re.match(r"^(第|全|各|其他|新一?代|主流|重点)", t) \
                and re.search(r"[A-Za-z0-9]{2}", t):
            res.append(t)
    return res


def load_plan():
    if not PLAN.exists():
        return []
    with PLAN.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def save_plan(rows):
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    with PLAN.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=PLAN_COLS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in PLAN_COLS})


def rowkey(r):
    """作业行主键。**必须带 product_line**：一家公司常有多条产品线，而产品线级资料的
    model 一律是 "line"（页面靠这个值把它归到「产品线级资料」区）——不带产品线的话，
    一家公司几条产品线的 BR/WEB 会塌成一行，多出来的产品线永远排不上队。"""
    # 产品线用原文不用 slug：中文产品线 slug 化后是空串（zte 的「通用服务器」与
    # 「数据中心以太网」就这么撞过），撞了就又塌成一行。
    return f"{r.get('company_id')}|{(r.get('product_line') or '').strip()}|{norm2(r.get('model'))}|{r.get('doc_type')}"


def cmd_plan(args):
    """从 data/products.json 生成作业计划：每个型号一行 DS，每条产品线两行（BR/WEB）。

    刷新时**只补不覆盖**——已填的 source_url / status / note 原样保留，
    否则每次刷新都会把人工找到的链接抹掉。"""
    prods = json.loads((ROOT / "data" / "products.json").read_text(encoding="utf-8"))["records"]
    pri = set(args.priority.split(",")) if args.priority else None
    old = {rowkey(r): r for r in load_plan()}
    rows, seen = [], set()
    for p in prods:
        if pri and p.get("priority") not in pri:
            continue
        base = {"company_id": p["company_id"], "company_en": p.get("company_en", ""),
                "sheet": p.get("sheet", ""), "product_line": p.get("product_line", ""),
                "bom_part": (p.get("bom_parts") or [""])[0], "lang": "", "version": "",
                "pub_date": "", "status": "todo", "doc_id": "", "source_url": "",
                "referrer_page": "https://" + (p.get("website", "").split(" ")[0]), "note": ""}
        slots = [(t, "DS") for t in model_tokens(p.get("representative_models", ""))]
        slots += [("line", "BR"), ("line", "WEB")]
        for model, dt in slots:
            r = dict(base, model=model, doc_type=dt)
            k = rowkey(r)
            if k in seen:
                continue
            seen.add(k)
            rows.append(dict(r, **{c: old[k][c] for c in PLAN_COLS if old.get(k, {}).get(c)}) if k in old else r)
    for k, r in old.items():                 # 计划外的人工补行不丢
        if k not in seen:
            rows.append(r)
    save_plan(rows)
    todo = sum(1 for r in rows if r["status"] == "todo")
    withurl = sum(1 for r in rows if r["status"] == "todo" and r["source_url"])
    print(f"作业计划 {PLAN.relative_to(ROOT)}：{len(rows)} 行；待办 {todo}（其中已填来源 URL {withurl}）")
    print("下一步：把 source_url 列填上（官方页面的直链），再跑 fetch。**留空不是缺陷，是还没查到——不许猜链接。**")


# ── 索引 ─────────────────────────────────────────────────────────────────

def load_index():
    if INDEX.exists():
        return json.loads(INDEX.read_text(encoding="utf-8"))
    return {"_note": "产品官方资料落盘索引。资料本体在外置卷（product 软链），不进 git。",
            "version": "1.0", "next_seq": 1, "records": []}


def save_index(doc):
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ext_of(path, ctype):
    head = open(path, "rb").read(5)
    if head.startswith(b"%PDF"):
        return ".pdf"
    if b"html" in (ctype or "").lower() or head[:1] == b"<":
        return ".html"
    return {"application/zip": ".zip", "text/plain": ".txt"}.get((ctype or "").split(";")[0], ".bin")


def place(root, row, src, ext, seq):
    """按 library/<环节>/<公司>/<产品线>/<型号>/<公司>__<型号>__<类型>__<版本>__<日期>__<语言>.<ext> 归位。"""
    model = row["model"] if row["model"] != "line" else "line"
    rel = Path("library") / safe(row["sheet"]) / safe(row["company_en"] or row["company_id"]) \
        / safe(row["product_line"]) / safe(model)
    name = "__".join([row["company_id"], norm2(model), row["doc_type"],
                      row.get("version") or "vNA", row.get("pub_date") or "nd",
                      row.get("lang") or "en"]) + ext
    dest = root / rel / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():                        # 同名不同版：加序号，绝不静默覆盖
        dest = dest.with_name(f"{dest.stem}__{seq}{dest.suffix}")
    shutil.move(str(src), str(dest))
    return (rel / dest.name).as_posix()


def index_record(doc, row, file_path, path_abs, original):
    rec = {"doc_id": f"D{doc['next_seq']:05d}", "company_id": row["company_id"],
           "sheet": row["sheet"], "product_line": row["product_line"], "model": row["model"],
           "bom_part": row["bom_part"], "doc_type": row["doc_type"],
           "title": row.get("note") or f'{row["company_en"]} {row["model"]} {row["doc_type"]}',
           "lang": row.get("lang") or "en", "version": row.get("version") or "vNA",
           "pub_date": row.get("pub_date") or "nd", "source_url": row["source_url"],
           "referrer_page": row.get("referrer_page", ""), "file_path": file_path,
           "original_filename": original, "sha256": sha256_of(path_abs),
           "size_bytes": path_abs.stat().st_size, "collected_date": date.today().isoformat(),
           "status": "downloaded", "superseded_by": None,
           "notes": "product_library.py 自动落盘；内容未核验"}
    doc["next_seq"] += 1
    doc["records"].append(rec)
    return rec


# ── 下载 ─────────────────────────────────────────────────────────────────

def download(url, dest_dir):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        ctype = resp.headers.get("Content-Type", "")
        name = safe(Path(urllib.request.url2pathname(resp.url.split("?")[0])).name) or "download"
        tmp = dest_dir / (name + ".part")
        total = 0
        with open(tmp, "wb") as fh:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_BYTES:
                    fh.close(); tmp.unlink(missing_ok=True)
                    raise ValueError(f"超过 {MAX_BYTES // 1048576}MB 上限，多半抓错了链接")
                fh.write(chunk)
    return tmp, ctype, name


def cmd_fetch(args):
    root = store_root()
    lib, inbox, manual = dirs(root)
    for d in (lib, inbox, manual):
        d.mkdir(parents=True, exist_ok=True)
    rows = load_plan()
    if not rows:
        sys.exit("作业计划是空的——先跑 plan。")
    doc = load_index()
    by_hash = {r["sha256"]: r for r in doc["records"] if r.get("sha256")}
    pri = set(args.priority.split(",")) if args.priority else None
    prods = {p["company_id"]: p for p in
             json.loads((ROOT / "data" / "products.json").read_text(encoding="utf-8"))["records"]}
    want = ("todo", "needs_manual") if args.retry else ("todo",)
    todo = [r for r in rows if r["status"] in want and r["source_url"]
            and (not pri or (prods.get(r["company_id"], {}).get("priority") in pri))]
    if args.limit:
        todo = todo[:args.limit]
    mode = "（干跑，不写盘）" if args.dry_run else ("（试爬：只落 _inbox/，不归位不入索引）"
                                                 if args.stage_only else f" → {root}")
    print(f"待抓 {len(todo)} 行{mode}")
    ok = fail = 0
    for r in todo:
        tag = f'{r["company_id"]}/{r["model"]}/{r["doc_type"]}'
        if args.dry_run:
            print(f"  [干跑] {tag}  ←  {r['source_url'][:90]}")
            continue
        try:
            tmp, ctype, original = download(r["source_url"], inbox)
            ext = ext_of(tmp, ctype)
            if args.stage_only:
                # 试爬期（用户 2026-08-19）：先爬回来自己看资料行不行，再决定要不要入库。
                # 所以停在 _inbox/，不归位、不进索引——**没看过的东西不许进库**。
                staged = inbox / (Path(original).stem + ext)
                staged = staged.with_name(f"{staged.stem}__{rowkey(r).replace('|', '_')}{ext}")
                shutil.move(str(tmp), str(staged))
                r["note"] = f"试爬落 _inbox/{staged.name}（未入库）"
                ok += 1
                print(f"  ⤓ 试爬 {tag} → _inbox/{staged.name}  {staged.stat().st_size // 1024}KB")
                continue
            if r["doc_type"] != "WEB" and ext == ".html":
                shutil.move(str(tmp), str(manual / (original + ".html")))
                r["status"], r["note"] = "needs_manual", "拿到的是 HTML（登录墙/中间页/JS 下载器），需人工"
                fail += 1
                print(f"  需人工 {tag}：拿到 HTML 不是文件")
                continue
            h = sha256_of(tmp)
            if h in by_hash:
                tmp.unlink(missing_ok=True)
                r["status"], r["doc_id"] = "downloaded", by_hash[h]["doc_id"]
                r["note"] = f"与 {by_hash[h]['doc_id']} 同哈希，未重复落盘"
                ok += 1
                print(f"  已有  {tag}（同哈希 {by_hash[h]['doc_id']}）")
                continue
            fp = place(root, r, tmp, ext, doc["next_seq"])
            rec = index_record(doc, r, fp, root / fp, original)
            by_hash[rec["sha256"]] = rec
            r["status"], r["doc_id"], r["note"] = "downloaded", rec["doc_id"], ""
            ok += 1
            print(f"  ✓ {rec['doc_id']} {tag}  {rec['size_bytes'] // 1024}KB")
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError) as e:
            r["status"], r["note"] = "needs_manual", f"抓取失败：{type(e).__name__} {e}"[:200]
            fail += 1
            print(f"  ✗ {tag}：{e}")
    if not args.dry_run:
        save_plan(rows)
        if not args.stage_only:
            save_index(doc)
        if args.stage_only:
            print(f"完成：落 _inbox/ {ok} 份，需人工 {fail}。看过觉得可用的，用 adopt 入库：")
            print("  python3 pipeline/product_library.py adopt "
                  "--row 'nvidia|训练-推理GPU|h200|DS' --file product/_inbox/xxx.pdf")
        else:
            print(f"完成：成功 {ok}，需人工 {fail}。索引 {len(doc['records'])} 条 → {INDEX.relative_to(ROOT)}")
        print("需人工的行留在计划表里带原因，看板会亮黄色 !——**不下的理由要留，别静默跳过**。")


# ── 人工归位 ─────────────────────────────────────────────────────────────

def cmd_adopt(args):
    """把人工下载的文件归位。两种用法：
       --row <company_id|产品线原文|型号slug|doc_type> --file <路径>   指名归位
       裸跑                                                    扫 _inbox/，按同名 .meta.json 侧车归位"""
    root = store_root()
    lib, inbox, manual = dirs(root)
    rows = {rowkey(r): r for r in load_plan()}
    all_rows = load_plan()
    doc = load_index()
    jobs = []
    if args.row:
        if not args.file:
            sys.exit("--row 要配 --file")
        seg = args.row.split("|")
        if len(seg) != 4:
            sys.exit("--row 格式：company_id|产品线原文|型号|doc_type（四段，竖线分隔）")
        seg[2] = norm2(seg[2])           # 型号段照 norm2 归一，手敲大小写/空格都认
        jobs.append(("|".join(seg), Path(args.file)))
    else:
        for f in sorted(inbox.glob("*")):
            side = f.with_suffix(f.suffix + ".meta.json")
            if f.suffix == ".json" or f.name.endswith(".part"):
                continue
            if side.exists():
                m = json.loads(side.read_text(encoding="utf-8"))
                jobs.append((f'{m["company_id"]}|{m["product_line"].strip()}|'
                             f'{norm2(m["model"])}|{m["doc_type"]}', f))
            else:
                print(f"  跳过 {f.name}：没有 {side.name} 侧车，也没给 --row，不猜它是谁的")
    for key, path in jobs:
        r = rows.get(key)
        if not r:
            print(f"  ✗ 计划里没有这一行：{key}（先在 {PLAN.name} 加一行）")
            continue
        if not path.exists():
            print(f"  ✗ 文件不在：{path}")
            continue
        ext = ext_of(path, "")
        staged = inbox / path.name
        if path.resolve() != staged.resolve():
            shutil.copy2(str(path), str(staged))
        fp = place(root, r, staged, ext, doc["next_seq"])
        rec = index_record(doc, r, fp, root / fp, path.name)
        rec["notes"] = "人工下载后 adopt 归位；内容未核验"
        r["status"], r["doc_id"], r["note"] = "downloaded", rec["doc_id"], "人工下载"
        side = staged.with_suffix(staged.suffix + ".meta.json")
        for leftover in (side, Path(str(path) + ".meta.json")):
            if leftover.exists():
                leftover.unlink()          # 侧车用完就删，否则 _inbox 越攒越像垃圾场
        print(f"  ✓ {rec['doc_id']} {key} → {fp}")
    save_plan(all_rows)
    save_index(doc)


# ── 体检 ─────────────────────────────────────────────────────────────────

def cmd_status(args):
    root = store_root(require_write=False)
    doc = load_index()
    rows = load_plan()
    cnt = {}
    for r in rows:
        cnt[r["status"]] = cnt.get(r["status"], 0) + 1
    print(f"作业计划：{len(rows)} 行 " + " ".join(f"{k}={v}" for k, v in sorted(cnt.items())))
    print(f"索引：{len(doc['records'])} 条；库根 {'（外置卷未挂载）' if root is None else root}")
    if not args.verify or root is None:
        return
    miss = bad = tot = 0
    for rec in doc["records"]:
        p = root / rec["file_path"]
        if not p.exists():
            miss += 1
            print(f"  ✗ 文件不在：{rec['doc_id']} {rec['file_path']}")
        elif rec.get("sha256") and sha256_of(p) != rec["sha256"]:
            bad += 1
            print(f"  ✗ 哈希对不上：{rec['doc_id']} {rec['file_path']}")
        else:
            tot += rec.get("size_bytes", 0)
    print(f"核对完毕：缺 {miss}，损 {bad}，在库 {tot / 1073741824:.2f}GB")


# ── 初始化 ───────────────────────────────────────────────────────────────

def cmd_setup(args):
    vol = Path("/Volumes") / args.volume
    if not os.path.ismount(str(vol)):
        avail = ", ".join(sorted(p.name for p in Path("/Volumes").glob("*"))) or "（一个都没有）"
        sys.exit(f"卷 {vol} 没挂载。当前挂着的卷：{avail}")
    target = vol / args.dir
    for sub in ("library", "_inbox", "_needs_manual"):
        (target / sub).mkdir(parents=True, exist_ok=True)
    (target / "README.txt").write_text(
        "InResearch.ai 产品官方资料库（datasheet / product brief / 参考架构 / 手册）。\n"
        "索引在仓库 data/product_library_index.json；本目录只放文件本体，不进 git。\n"
        "由 pipeline/product_library.py 维护，请勿手工重命名——文件名是索引的锚点。\n", encoding="utf-8")
    if LINK.is_symlink() or LINK.exists():
        if LINK.is_symlink():
            LINK.unlink()
        else:
            sys.exit(f"{LINK} 已存在且不是软链——先自行处理，不替你删。")
    LINK.symlink_to(target)
    print(f"库根 {target}\n软链 {LINK} → {target}")
    print("页面常量已按此路径写死（admin/product/index.html）；换盘只需重跑本命令。")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup", help="在外置卷建库并做软链")
    s.add_argument("--volume", required=True, help="外置卷名（/Volumes 下的目录名）")
    s.add_argument("--dir", default="inresearch-product", help="卷内目录名")
    s.set_defaults(func=cmd_setup)
    s = sub.add_parser("plan", help="从 products.json 生成/刷新作业计划")
    s.add_argument("--priority", help="只铺某些优先级，如 P0 或 P0,P1")
    s.set_defaults(func=cmd_plan)
    s = sub.add_parser("fetch", help="按计划下载并归位")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--limit", type=int)
    s.add_argument("--priority")
    s.add_argument("--retry", action="store_true", help="连 needs_manual 的行一起重试")
    s.add_argument("--stage-only", action="store_true",
                   help="试爬：只落 _inbox/，不归位不入索引（看过再 adopt 入库）")
    s.set_defaults(func=cmd_fetch)
    s = sub.add_parser("adopt", help="人工下载的文件归位")
    s.add_argument("--row", help="company_id|产品线原文|型号slug|doc_type（见计划表）")
    s.add_argument("--file")
    s.set_defaults(func=cmd_adopt)
    s = sub.add_parser("status", help="体检")
    s.add_argument("--verify", action="store_true", help="逐份核对文件存在与哈希")
    s.set_defaults(func=cmd_status)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
