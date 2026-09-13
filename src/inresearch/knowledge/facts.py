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
  python3 manage.py facts                                  # 校验 + 全指标可比性分组
  python3 manage.py facts dc_construction_cost_per_sqm     # 只看某指标
  python3 manage.py facts --public                         # 对外口径预览（区间+时效）
零依赖。
"""

from inresearch.paths import project_root
import json
import sys
from collections import defaultdict
from datetime import date

ROOT = project_root()
FACTS = ROOT / "data" / "facts.json"
METRICS = ROOT / "framework" / "metrics.json"

from inresearch.knowledge.fact_contract import check_fact, DEPTHS, CORROBORATION
FACT_DEPTHS = set(DEPTHS)
CORROB = set(CORROBORATION)
BOUND_SIGN = {"upper": "<", "lower": ">", "point": " "}

errors = []


def err(m):
    errors.append(m)


def load():
    facts = json.loads(FACTS.read_text(encoding="utf-8"))["records"]
    metrics = {m["metric_id"]: m for m in json.loads(METRICS.read_text(encoding="utf-8"))["metrics"]}
    return facts, metrics


def validate(facts, metrics):
    """Audit stored facts against the same contract used by new submissions.

    Existing provenance gaps are reported; no hash or source is invented to
    make legacy records pass. This audit does not rewrite or adopt anything.
    """
    errors.clear()
    seen = set()
    for fact in facts:
        for problem in check_fact(fact, metrics, seen):
            err("facts[%s]: %s" % (fact.get('fact_id', '?'), problem))
        seen.add(fact.get('fact_id'))


WITHHELD = "受分发限制，不对外给值"


def restricted(f):
    """本条是否因分发限制而不得对外。

    由来（2026-09-13，C3 A 档复审）：中国联通 IDC 建设标准那 34 条的原件封面写着
    「企业内部资料，严格保密」。此前 sensitive 只在内部视图里显示一个 🔒，而
    --public 照样把它们打出来——**金额转区间挡不住这件事**：泄露的是「某运营商
    企标里 2000kW 柴发的概算价位大约在四百万这个量级」这个事实本身，不是它的第二位
    有效数字。band 改的是精度，改不了这份材料本不该由我们转发。

    所以 sensitive 在对外一侧是硬门，不是标记。内部仍然全留全实名——高敏感数据
    是内部信心与校验基线的来源，这一条没变。
    """
    return bool(f.get("sensitive"))


def public_view(f, m, today_year=None):
    """对外呈现（2026-08-17 用户拍板的规则）。

    三条：
      1. **实体与项目名照实输出，不隐瞒** —— 都是真实 entity，遮遮掩掩反而不专业；
      2. **涉及钱财的只给区间不给精确值** —— 精确的招标控制价既不合规也没必要；
      3. **必须标明数据年份与距今年数** —— 这些本就是老数据，直接拿来用没有现实价值，
         说清"引用的是某年的数据、大概在哪个区间"，既够用又诚实。

    第四条（2026-09-13 加）：**受分发限制的条目在这里就被挡住**，不靠调用方自觉。
    这个函数是对外呈现的唯一出口，门放在出口上才关得住。
    """
    if restricted(f):
        yr = str(f.get("as_of", ""))[:4]
        return f"{f['entity'].get('label','')}：**{WITHHELD}**（{yr} 年数据；原件标注内部资料）"
    v = f.get("value")
    value_range = f.get("value_range")
    unit = f.get("unit", "")
    band = m.get("public_band") or {}
    step = band.get("step")
    # 已披露区间与未披露是两种状态；沿用内部显示精度，不另行取整。
    if value_range is not None:
        lo, hi = value_range
        rng = f"{fmt_value(lo, unit)}–{fmt_value(hi, unit)}"
    elif v is None:
        rng = "未披露（留白）"
    elif step:
        lo = int(v // step) * step
        rng = f"{fmt_value(lo, unit)}–{fmt_value(lo + step, unit)}"
    else:
        rng = fmt_value(v, unit)
    bd = f.get("bound", "point")
    if bd == "upper":
        rng = f"不高于 {rng}"
    elif bd == "lower":
        rng = f"不低于 {rng}"
    yr = str(f.get("as_of", ""))[:4]
    if today_year is None:
        today_year = date.today().year
    age = (today_year - int(yr)) if yr.isdigit() else None
    vintage = f"{yr} 年数据" + (f"，距今约 {age} 年" if age and age > 0 else "")
    cal = "｜".join(f"{k}={v2}" for k, v2 in (f.get("caliber") or {}).items())
    return f"{f['entity'].get('label','')}：**{rng} {f['unit']}**（{vintage}；口径：{cal}）"


def fmt_value(v, unit=""):
    """按原值的小数位显示，不做统一四舍五入。

    由来（2026-08-17）：原先固定 `.1f`，于是 PUE 1.63 与 1.41 显示成 1.6 与 1.4，
    **而 PUE 这个域的差别恰恰在第二位小数上**——1.05 与 1.076 会双双显示成 1.1。
    渲染层把区分度抹掉，等于事实层存得精确、读出来是糊的。
    做法：整数不带小数点，其余保留原值实际的小数位（上限 4 位，防浮点尾巴）。
    """
    if isinstance(v, int) or (isinstance(v, float) and v.is_integer()):
        n = int(v)
        # 年份不加千位分隔符——「2,027 年」读起来像个数量而不是年份。
        # 判据用「单位是年 且 落在合理年份区间」，避免误伤「5 年」这类时长。
        if unit == "年" and 1900 <= n <= 2200:
            return str(n)
        return f"{n:,}"
    s = f"{v:.4f}".rstrip("0")
    dec = len(s.split(".")[1])
    return f"{v:,.{dec}f}"


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
                # 「已交叉验证」才是可以拿去推算的；其余默认待验证
                c = f.get("corroboration", "待交叉验证")
                mark += {"已交叉验证": " ✓双源", "孤证已知": " ⚠孤证",
                         "同源转述": " ⚠同源"}.get(c, " ·待验")
                s = "🔒" if f.get("sensitive") else "  "
                # value 允许为 null——「已知该指标存在但值未披露」是留白纪律的一部分，
                # 渲染必须显式处理，不能崩（本行曾因未处理 None 报 TypeError）
                b = BOUND_SIGN.get(f.get("bound", "point"), " ")
                u = f.get("unit", "")
                if f.get("value") is not None:
                    v = f"{b}{fmt_value(f['value'], u):>9}"
                elif f.get("value_range"):
                    lo, hi = f["value_range"]
                    v = f" {fmt_value(lo, u)}–{fmt_value(hi, u):<4}".rjust(10)
                else:
                    v = f"{'留白':>9} "
                lines.append(f"     {s} {v} {f['unit']}  {f['entity'].get('label','')[:34]}{mark}")

        if len(groups) > 1:
            lines.append(f"  ⚠️ 本指标下有 {len(groups)} 个互不可比的口径组——**跨组并列即口径事故**：")
            ks = sorted(groups)
            for i in range(len(ks)):
                for j in range(i + 1, len(ks)):
                    diff = [f"{d}（{a} vs {b}）" for d, a, b in zip(dims, ks[i], ks[j]) if a != b]
                    lines.append(f"     ✗ 组{i+1} 与 组{j+1} 不可比，差在：{'、'.join(diff)}")
    return lines


def main():
    args = sys.argv[1:]
    public = "--public" in args
    only = next((a for a in args if not a.startswith("-")), None)
    facts, metrics = load()
    validate(facts, metrics)

    print(f"事实 {len(facts)} 条｜指标 {len(metrics)} 个")
    if errors:
        print(f"\n校验失败 {len(errors)} 项：")
        for e in errors:
            print(f"  ✗ {e}")
    else:
        print("校验通过（0 errors）")

    if public:
        print("\n=== 对外口径预览 ===")
        print("规则：实体与项目名照实；涉及钱财只给区间；必标数据年份与距今年数。")
        by = defaultdict(list)
        for f in facts:
            by[f["metric_id"]].append(f)
        for mid, fs in sorted(by.items()):
            m = metrics.get(mid)
            if not m or (only and mid != only):
                continue
            print(f"\n{m['name']}（{m['unit']}）")
            held = 0
            for f in fs:
                if f.get("derived"):
                    continue          # 派生值不单独对外，避免同一笔钱出现两次
                if restricted(f):
                    held += 1         # 不给值，但承认它存在——见下
                    continue
                print("  · " + public_view(f, m))
            if held:
                # **不给值，但对外承认存在。**假装库里没有这些数是另一种不诚实，
                # 而且会让读者以为这个指标只有这么几条可比数据。
                print(f"  · 另有 {held} 条受分发限制未列出")
        print("\n（派生值已从对外视图剔除，避免同一笔钱以两种口径重复出现。）")
        print("（受分发限制的条目只报条数不报值：原件标注内部资料，"
              "转区间也不构成可以转发的理由。）")
        return 1 if errors else 0

    for l in compare(facts, metrics, only):
        print(l)

    print("\n提示：🔒 = 敏感（业主商业信息或原件标注内部资料）。**内部全留全实名**——"
          "高敏感数据是内部信心与校验基线的来源；")
    print("      对外走 --public：实名照旧，金额转区间并标明是哪年的老数据，"
          "🔒 只报条数不报值。")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
