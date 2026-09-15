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
import re
import sys
from collections import defaultdict, Counter
from datetime import date

ROOT = project_root()
FACTS = ROOT / "data" / "facts.json"
METRICS = ROOT / "framework" / "metrics.json"

from inresearch.knowledge.fact_contract import (check_fact,
                                                forecast_outliers,
                                                UNSTATED_ASSERTER as UNSTATED)
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


def asserter_listing(facts):
    """断言者清单与条数。

    asserter 进 claim_key，所以**同一家写两种名字就是两家**：库里曾同时有「谷歌」3 条
    与「Google」1 条，两者的重复、修订、争议都互相看不见。录入前用
    `manage.py facts --asserters` 看一眼现有写法，比事后扫库便宜得多。
    """
    counts = Counter(f.get("asserter") or "（缺）" for f in facts)
    lines = ["断言者 %d 家（asserter 进键，新名字先对一眼现有写法）" % len(counts)]
    lines += ["  %5d  %s" % (n, name) for name, n in counts.most_common()]
    split = split_asserters(facts)
    if split:
        lines.append("")
        lines.append("以下 %d 家在库里有两种写法——**两种写法就是两家**，先并成一个：" % len(split))
        for canon, spellings in split:
            lines.append("  %s  ←  %s" % (canon, '、'.join(
                '%s（%d 条）' % (name, n) for name, n in spellings)))
    buried = buried_asserters(facts)
    if buried:
        lines.append("")
        lines.append("以下 %d 条 asserter 是「未注明」，但原文里点了名——先核一眼：" % len(buried))
        lines += ["  %-38s %s" % (fid, quote) for fid, quote in buried]
    return lines


# 同一家写两种名字就是两家——这个坑踩过三次了（谷歌/Google、NVIDIA/英伟达，
# 还有 T-Head 被译成天数那次）。asserter 进 claim_key，所以两种写法之间的重复、
# 修订、争议**互相看不见**：不会撞键，也不会被争议分诊捞出来，只会安静地把
# 一家的序列劈成两半。
#
# 这张表只用来**报**，不用来自动改。自动归一的代价太大：表里错一行，两家真正
# 不同的机构就被悄悄并成一家，而那比分裂更难发现——分裂看得见两个名字，
# 错并之后只剩一个。
#
# 收录标准是「同一法人的不同写法」，不是「同一集团的不同子公司」：
# 台积电与 TSMC 是一家，中国移动与中移动信息是两家。
#
# **表里有它不等于库里要改名。** 这张表只回答「这几种写法是不是一家」；
# 至于该用哪一种，只在**真的分裂了**的时候才需要定，而定法是：
#   1. 原件的官方写法优先；
#   2. 其次取库内多数（世邦魏理仕 64 对 CBRE 27 → 世邦魏理仕）；
#   3. 中文/拉丁的偏好只是第 2 条的注脚——库内对有通用中文名的外企多用中文名，
#      但那是描述出来的习惯，不是要去翻译的规定。
# **写法一致、没有分裂的，一律不动**：JLL 309 条全用 JLL，库里没在用「仲量联行」，
# 改名换不来任何东西（没有键被劈开），只换来 309 条 churn 和一次误改的机会。
# 同理 IDC 800 条、TrendForce 276 条、Meta、Dell'Oro 都保持原样。
# 这条限定是 2026-09-15 补的：上一版把偏好写成了「一律用中文名」，
# 照字面执行会触发大批没有必要的改名。
ASSERTER_ALIASES = {
    "英伟达": ("NVIDIA", "Nvidia", "NVDA"),
    "谷歌": ("Google", "Alphabet"),
    "微软": ("Microsoft", "MSFT"),
    "亚马逊": ("Amazon", "AWS", "亚马逊云科技"),
    "戴尔": ("Dell", "Dell Technologies"),
    "英特尔": ("Intel",),
    "台积电": ("TSMC",),
    "三星": ("Samsung", "三星电子"),
    "美光": ("Micron",),
    "施耐德电气": ("Schneider", "Schneider Electric", "施耐德"),
    "维谛": ("Vertiv", "维谛技术"),
    "阿里平头哥": ("T-Head", "平头哥"),
    "中国信通院": ("信通院", "中国信息通信研究院"),
    "科智咨询": ("科智",),
    # 下面几家目前库内写法一致，收在这里只为**日后出现分裂时能被检出**，
    # 不意味着现在要改名（见上面那段）。
    "世邦魏理仕": ("CBRE",),
    "DCByte": ("DC Byte", "DCbyte", "DC byte"),
    "JLL": ("仲量联行",),
    "Omdia": ("欧姆迪亚",),
    "Global Market Insights": ("GMI",),
    "摩根士丹利": ("Morgan Stanley", "大摩", "MS"),
    "TrendForce": ("集邦咨询", "集邦"),
}


def split_asserters(facts):
    """同一家出现了两种以上写法的，连同各自条数报出来。

    只报不改（见 ASSERTER_ALIASES 上面那段）。返回 [(规范名, [(写法, 条数), …]), …]，
    按涉及条数从多到少。
    """
    counts = Counter(f.get("asserter") or "" for f in facts)
    found = []
    for canon, aliases in ASSERTER_ALIASES.items():
        present = [(name, counts[name]) for name in (canon,) + tuple(aliases) if counts[name]]
        if len(present) > 1:
            found.append((canon, sorted(present, key=lambda row: -row[1])))
    return sorted(found, key=lambda row: -sum(n for _, n in row[1]))


# 「据 X 统计」的 X 就是断言者，而它常常只留在 locator 的原文引号里。
# cn-dc-occupancy-2023 就是这样：locator 写着「据中国信通院统计」，asserter 却是
# 「未注明」——那条数因此拿不到它该有的归属，也进不了与科智那条的争议对。
# 「数据中心」里的「据中心」会被这个模式误切，所以先把它挡掉再匹配。
BURIED = re.compile(r"(?<!数)据([\u4e00-\u9fff]{2,12}?|[A-Z][A-Za-z&. ]{1,20}?)"
                    r"(统计|测算|调研|研究表明|的研究|数据)")
VAGUE = ("公开", "各厂商官网", "上述", "本报告", "该报告", "行业", "业内")


def buried_asserters(facts):
    """asserter 是「未注明」而原文点了名的记录。

    只报不改：X 可能是真断言者（清华大学、GTW），也可能是「公开数据」这类
    没有主体的说法，要人看一眼原文才能定。
    """
    found = []
    for fact in facts:
        if (fact.get("asserter") or "") != UNSTATED:
            continue
        blob = str((fact.get("evidence") or {}).get("locator") or "")
        for match in BURIED.finditer(blob):
            who = match.group(1).strip()
            if any(v in who for v in VAGUE):
                continue
            found.append((fact.get("fact_id"), match.group(0)))
            break
    return found


def main():
    args = sys.argv[1:]
    public = "--public" in args
    if "--asserters" in args:
        facts, _ = load()
        for line in asserter_listing(facts):
            print(line)
        return 0
    if "--outliers" in args:
        facts, metrics = load()
        rows = forecast_outliers(facts, metrics)
        print("同一目标年份上离同行中位数 2 倍以上的预测：%d 条" % len(rows))
        print("（只提示不判定。预测按 @vintage 分开是对的——同一家改口不该记成自己跟自己吵，"
              "代价就是同年预测永远不互相指认，这一扫是补那个口子。）")
        for row in rows:
            print("  %s  %s %s（同行中位 %s，偏离 %.2fx，共 %d 家）\n     %s"
                  % (row["about"], row["value"], row["unit"], row["peer_median"],
                     row["off_by"], row["peers"], row["fact_id"] + " ← " + row["asserter"]))
        return 0
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
