#!/usr/bin/env python3
"""盲区体检：找出「库里有、但我们的分类器看不见」的材料。

由来（2026-08-17 M11 事故）：M11 资本与金融在打分表里命中数为 0，云端据此判断
「根因是没有信源跑口声明，不知道该去哪找」——**判断错了**。本地会话查出真正的
原因是 auto_batch 的关键词表里**根本没有 M11 这一档**，等于系统性看不见资本与
金融类材料；补上关键词全库重扫，命中 1,407 份。**材料一直在库里，是我们瞎。**

这是一类特殊的未知：不是「我们缺数据」，而是「我们有数据却看不见」。
前者靠采集解决，后者靠采集永远解决不了——只会越采越多、越看不见。

体检方法：模块在 framework/modules.json 里声明自己的 keywords；本脚本扫全表，
统计「文本命中该模块关键词、但没有被标成该模块」的行数。该数远大于已命中数，
就是盲区信号。

⚠ 这是烟雾报警器不是分类器：关键词匹配必然有假阳性（如 M02 的「供给」、
M04 的「电力」在中文语料里到处都是）。它的用处是**报出异常比值让人去查**，
不能拿它的绝对数当结论，更不能拿它自动改分。

用法：python3 manage.py coverage         # → reports/blindspot.md + stdout
      python3 manage.py coverage M11     # 只看某模块，并列出样本
零依赖。
"""

from inresearch.paths import project_root
import csv
import json
import re
import sys
from datetime import date

ROOT = project_root()
OUT = ROOT / "reports" / "blindspot.md"
OUT_JSON = ROOT / "reports" / "blindspot.json"   # 供仪表盘等机器消费方

SUSPECT_RATIO = 3.0   # 强信号疑似/已命中 超过此倍数即报警
MIN_SUSPECT = 30      # 强信号疑似数低于此值不报警（避免小样本噪声）
STRONG_KWS = 2        # 命中 ≥2 个**不同**关键词才算强信号——单词命中假阳性太高
                      # （一份结构计算书里出现一次「制冷」不代表它是 M08 材料）


def load():
    rows = list(csv.DictReader((ROOT / "docs" / "LIBRARY_SCORES.csv").open(encoding="utf-8")))
    mods = json.loads((ROOT / "framework" / "modules.json").read_text(encoding="utf-8"))["modules"]
    return rows, mods


def kw_pattern(k):
    """纯 ASCII 关键词加词边界，否则 ABS 会命中 GPUCommunication 里的 abs；
    中日韩文字没有词边界概念，加了 \b 反而永不匹配，故原样使用。"""
    e = re.escape(k)
    return rf"\b{e}\b" if k.isascii() else e


def tagged(row, mid):
    return mid in re.split(r"[/、,，]", row.get("module") or "")


def scan(rows, mods):
    out = []
    for m in mods:
        mid, kws = m["id"], m.get("keywords") or []
        if not kws:
            out.append(dict(mid=mid, name=m["name"], kws=0, hit=0, blind=0, ratio=None,
                            note="**未声明 keywords——本模块无法体检**，这本身就是盲区。"))
            continue
        pats = [(k, re.compile(kw_pattern(k), re.I)) for k in kws]
        hit = blind = weak = 0
        samples = []
        for r in rows:
            text = r["new_path"] + " " + r["summary"]
            got = [k for k, rx in pats if rx.search(text)]
            if not got:
                continue
            if tagged(r, mid):
                hit += 1
            elif len(got) >= STRONG_KWS:
                blind += 1
                if len(samples) < 12:
                    samples.append((r, got))
            else:
                weak += 1
        ratio = (blind / hit) if hit else float("inf")
        out.append(dict(mid=mid, name=m["name"], kws=len(kws), hit=hit, blind=blind,
                        weak=weak, ratio=ratio, samples=samples, note=""))
    return out


def alarming(e):
    if e["ratio"] is None:
        return True
    return e["blind"] >= MIN_SUSPECT and e["ratio"] >= SUSPECT_RATIO


def render(res):
    lines = [
        "# 盲区体检 — 库里有、但分类器看不见的材料",
        "",
        f"生成时间：{date.today().isoformat()}",
        "",
        "> **这是烟雾报警器，不是分类器。** 关键词匹配必然有假阳性"
        "（「供给」「电力」在中文语料里到处都是），所以**绝对数不可当结论，更不可据此自动改分**。",
        "> 它唯一的用处是报出异常比值，让人去抽查——判断仍然是人的。",
        "",
        f"报警线：疑似数 ≥ {MIN_SUSPECT} 且 疑似/已命中 ≥ {SUSPECT_RATIO}×。",
        "",
        f"强信号 = 命中 ≥{STRONG_KWS} 个不同关键词；只命中 1 个的算弱信号，单列不计入报警。",
        "",
        "| 模块 | 关键词 | 已命中 | 强信号疑似 | 弱信号 | 倍数 | 状态 |",
        "|---|---:|---:|---:|---:|---:|:--|",
    ]
    for e in sorted(res, key=lambda x: -(x["ratio"] if x["ratio"] not in (None, float("inf")) else 1e9)):
        r = "—" if e["ratio"] is None else ("∞" if e["ratio"] == float("inf") else f"{e['ratio']:.1f}×")
        lines.append(f"| {e['mid']} {e['name']} | {e['kws']} | {e['hit']} | {e['blind']} | "
                     f"{e.get('weak', 0)} | {r} | {'⚠️ 报警' if alarming(e) else '正常'} |")
    lines.append("")

    for e in sorted(res, key=lambda x: -(x["ratio"] if x["ratio"] not in (None, float("inf")) else 1e9)):
        if not alarming(e):
            continue
        lines += [f"## ⚠️ {e['mid']} {e['name']}", ""]
        if e["note"]:
            lines += [e["note"], ""]
            continue
        lines += [f"文本命中本模块关键词但未被标成本模块的有 **{e['blind']}** 行，"
                  f"而已标成本模块的只有 **{e['hit']}** 行。抽样：", ""]
        for s, got in e.get("samples", []):
            lines.append(f"- `{s['importance']}{s['confidence']}` {s['depth']} ｜ 现标 `{s['module'] or '—'}` "
                         f"｜ 命中 {'、'.join(got[:4])} ｜ {s['new_path'].split('/')[-1][:60]}")
        lines.append("")
    return "\n".join(lines) + "\n"


def main():
    only = sys.argv[1] if len(sys.argv) > 1 and re.fullmatch(r"M\d\d", sys.argv[1]) else None
    rows, mods = load()
    if only:
        mods = [m for m in mods if m["id"] == only]
    res = scan(rows, mods)
    OUT.write_text(render(res), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(
        {"generated": date.today().isoformat(),
         "modules": [{k: e[k] for k in ("mid", "name", "kws", "hit", "blind")}
                     | {"ratio": (None if e["ratio"] in (None, float("inf")) else round(e["ratio"], 1)),
                        "alarm": alarming(e)} for e in res]},
        ensure_ascii=False, indent=1), encoding="utf-8")

    alarms = [e for e in res if alarming(e)]
    print(f"体检 {len(res)} 个模块｜报警 {len(alarms)} 个")
    for e in sorted(alarms, key=lambda x: -(x["ratio"] if x["ratio"] not in (None, float("inf")) else 1e9)):
        r = "—" if e["ratio"] is None else ("∞" if e["ratio"] == float("inf") else f"{e['ratio']:.1f}x")
        print(f"  ⚠️ {e['mid']} {e['name']}：已命中 {e['hit']}，疑似看不见 {e['blind']}（{r}）")
    print(f"完整报告已写入 {OUT.relative_to(ROOT)} 与 {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
