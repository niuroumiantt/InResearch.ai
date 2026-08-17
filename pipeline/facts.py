#!/usr/bin/env python3
"""事实层校验与可比性判定——core 的守门人。

事实层的原子是「一个事实」（某指标 × 某口径 × 某时点 × 某出处的一个数），
不是「一份文件」。`docs/LIBRARY_SCORES.csv` 是目录，本表才是数据库。

本脚本做两件事：

1. **校验**（`validate`）：指标存在、单位一致、**metrics.json 声明的每个口径维度都填了
   且取值合法**、证据等级合法、depth 只允许「精读」与「据实生成」、派生值必须写清算法。

2. **可比性判定**（`compare`）：两条事实可比 ⟺ `metric_id` 相同 **且** 全部 caliber
   维度取值相同。不可比的**拒绝并列**，并指出是哪一维打架。

第 2 条是这个项目区别于通用 RAG 的地方——**不是知道得多，是知道什么时候不能把两个数放一起**。
六安 4,406 与广州 3,775 摆在一起看着可比，实际一个是施工总包、一个是土建本体；
剥掉室外后才是 3,737 对 3,775。这种判断以前靠人记得，现在靠字段挡。

用法：
  python3 pipeline/facts.py                                  # 校验 + 全指标可比性分组
  python3 pipeline/facts.py dc_construction_cost_per_sqm     # 只看某指标
零依赖。
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FACTS = ROOT / "data" / "facts.json"
METRICS = ROOT / "framework" / "metrics.json"

FACT_DEPTHS = {"精读", "据实生成"}   # 半自动与目录级不得进事实层
GRADES = {"S1", "S2", "S3", "S4", "S5"}

errors = []


def err(m):
    errors.append(m)


def load():
    facts = json.loads(FACTS.read_text(encoding="utf-8"))["records"]
    metrics = {m["metric_id"]: m for m in json.loads(METRICS.read_text(encoding="utf-8"))["metrics"]}
    return facts, metrics


def validate(facts, metrics):
    seen = set()
    for f in facts:
        fid = f.get("fact_id", "?")
        if fid in seen:
            err(f"facts[{fid}]: fact_id 重复")
        seen.add(fid)

        m = metrics.get(f.get("metric_id"))
        if not m:
            err(f"facts[{fid}]: metric_id 不存在于 metrics.json：{f.get('metric_id')}")
            continue

        if f.get("unit") != m["unit"]:
            err(f"facts[{fid}]: 单位与指标声明不符（事实 {f.get('unit')} vs 指标 {m['unit']}）")

        cal = f.get("caliber") or {}
        for dim in m["caliber_dims"]:
            if dim["id"] not in cal:
                err(f"facts[{fid}]: **缺口径维度 `{dim['id']}`（{dim['name']}）**——"
                    f"口径不全的数不许入表，因为它无法判定可比性")
            elif cal[dim["id"]] not in dim["values"]:
                err(f"facts[{fid}]: 口径 `{dim['id']}` 取值非法：{cal[dim['id']]}｜合法值 {dim['values']}")
        for k in cal:
            if k not in {d["id"] for d in m["caliber_dims"]}:
                err(f"facts[{fid}]: 多余的口径维度 `{k}`（该指标未声明）")

        if f.get("depth") not in FACT_DEPTHS:
            err(f"facts[{fid}]: depth={f.get('depth')} 不得进事实层（只收 精读/据实生成）")

        ev = f.get("evidence") or {}
        if ev.get("grade") not in GRADES:
            err(f"facts[{fid}]: 证据等级非法：{ev.get('grade')}")
        if not ev.get("locator"):
            err(f"facts[{fid}]: 缺 locator——**要能让人翻回原文核对那一个数**")

        if f.get("derived") and not f.get("derivation"):
            err(f"facts[{fid}]: derived=true 但没写 derivation（派生算法必须可复现）")
        if f.get("value") is None and not f.get("notes"):
            err(f"facts[{fid}]: value 为 null 时必须在 notes 说明为何留白")


def caliber_key(f, m):
    return tuple(f["caliber"].get(d["id"], "?") for d in m["caliber_dims"])


def compare(facts, metrics, only=None):
    lines = []
    by_metric = defaultdict(list)
    for f in facts:
        by_metric[f["metric_id"]].append(f)

    for mid, fs in sorted(by_metric.items()):
        if only and mid != only:
            continue
        m = metrics.get(mid)
        if not m:
            continue
        lines.append(f"\n=== {mid}  {m['name']}（{m['unit']}）===")
        groups = defaultdict(list)
        for f in fs:
            groups[caliber_key(f, m)].append(f)

        dims = [d["id"] for d in m["caliber_dims"]]
        for key, g in sorted(groups.items(), key=lambda kv: str(kv[0])):
            cal = "｜".join(f"{d}={v}" for d, v in zip(dims, key))
            lines.append(f"  [{cal}]  可比组，{len(g)} 条")
            for f in g:
                mark = "（计算值）" if f.get("derived") else ""
                s = "🔒" if f.get("sensitive") else "  "
                lines.append(f"     {s} {f['value']:>10,.1f} {f['unit']}  {f['entity'].get('label','')[:34]}{mark}")

        if len(groups) > 1:
            lines.append(f"  ⚠️ 本指标下有 {len(groups)} 个互不可比的口径组——**跨组并列即口径事故**：")
            ks = sorted(groups)
            for i in range(len(ks)):
                for j in range(i + 1, len(ks)):
                    diff = [f"{d}（{a} vs {b}）" for d, a, b in zip(dims, ks[i], ks[j]) if a != b]
                    lines.append(f"     ✗ 组{i+1} 与 组{j+1} 不可比，差在：{'、'.join(diff)}")
    return lines


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    facts, metrics = load()
    validate(facts, metrics)

    print(f"事实 {len(facts)} 条｜指标 {len(metrics)} 个")
    if errors:
        print(f"\n校验失败 {len(errors)} 项：")
        for e in errors:
            print(f"  ✗ {e}")
    else:
        print("校验通过（0 errors）")

    for l in compare(facts, metrics, only):
        print(l)

    print("\n提示：🔒 = 敏感待判（业主商业信息），对外产出前须脱敏或聚合。")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
