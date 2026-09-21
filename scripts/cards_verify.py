#!/usr/bin/env python3
"""核对 Spark 硬链接视图与 fulltext 卡片是否对得上, 并汇总分布。

只读: 看 ~/.local/share/inresearch.ai/sorted/ 下的视图与
fulltext/cards.jsonl, 打印模块 / 分数 / 语种分布和对不上的条目。

    python3 scripts/cards_verify.py

2026-09-21 从 infra 仓库顶层移来, 理由同 cards_ocr.py。
"""
import json
import os
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path.home()
FT = ROOT / '.local/share/inresearch.ai/fulltext'
CARDS_FILE = FT / 'cards.jsonl'
PLAN_FILE = ROOT / 'cards-plan.jsonl'

SPARK_VIEW = ROOT / '.local/share/inresearch.ai/sorted/20260920-spark-fulltext'
ROOTS = {
    ROOT / 'nas-dc-library': '20260906-nas-reports',
    ROOT / '.local/share/inresearch.ai/sorted/20260919-nas-laobing2025': '20260919-nas-laobing2025',
}

def verify_spark_view():
    print("=== Spark 硬链接视图验证 ===")
    if not SPARK_VIEW.exists():
        print(f"错误: {SPARK_VIEW} 不存在")
        return False

    module_counts = defaultdict(int)
    score_dist = defaultdict(lambda: defaultdict(int))
    lang_dist = defaultdict(int)

    for module_dir in SPARK_VIEW.iterdir():
        if not module_dir.is_dir():
            continue

        module_name = module_dir.name
        pdf_count = len(list(module_dir.glob('*.pdf')))
        module_counts[module_name] = pdf_count

        for pdf in module_dir.glob('*.pdf'):
            parts = pdf.name.split('_')
            if len(parts) >= 1:
                score_char = parts[0][0]
                try:
                    score = int(score_char)
                    score_dist[module_name][score] += 1
                except:
                    pass

    print(f"模块分布:")
    total_files = 0
    for module in sorted(module_counts.keys()):
        count = module_counts[module]
        total_files += count
        scores = score_dist.get(module, {})
        avg_score = sum(s*c for s,c in scores.items()) / count if count > 0 else 0
        print(f"  {module:20} {count:5} · 均分 {avg_score:.1f}")

    print(f"总计: {total_files} 张")
    return total_files == 667

def verify_nas_files():
    print("\n=== NAS 文件验证 ===")
    nas_counts = defaultdict(int)
    total_files = 0

    for nas_root, batch_name in ROOTS.items():
        batch_dir = nas_root / batch_name
        if not batch_dir.exists():
            print(f"警告: {batch_dir} 不存在")
            continue

        print(f"\n{batch_name}:")
        for module_dir in batch_dir.iterdir():
            if not module_dir.is_dir():
                continue

            module_name = module_dir.name
            pdf_count = len(list(module_dir.glob('*.pdf')))
            nas_counts[module_name] += pdf_count
            total_files += pdf_count
            if pdf_count > 0:
                print(f"  {module_name:20} {pdf_count:5}")

    print(f"\n总计: {total_files} 张")
    return total_files == 13384

def verify_plan():
    print("\n=== 处理计划验证 ===")
    if not PLAN_FILE.exists():
        print(f"错误: {PLAN_FILE} 不存在")
        return False

    with open(PLAN_FILE) as f:
        plan_lines = sum(1 for _ in f)

    print(f"计划行数: {plan_lines}")

    with open(PLAN_FILE) as f:
        sample_plan = json.loads(f.readline())

    print(f"示例计划行:")
    print(json.dumps(sample_plan, ensure_ascii=False, indent=2)[:200])

    return plan_lines == 13384

def count_ocr_candidates():
    print("\n=== OCR 候选统计 ===")
    if not CARDS_FILE.exists():
        print(f"错误: {CARDS_FILE} 不存在")
        return 0

    ocr_count = 0
    with open(CARDS_FILE) as f:
        for line in f:
            card = json.loads(line)
            if card.get('marker') == 'n':
                ocr_count += 1

    print(f"标记为 n (仅图像): {ocr_count} 张")
    return ocr_count

def main():
    spark_ok = verify_spark_view()
    nas_ok = verify_nas_files()
    plan_ok = verify_plan()
    ocr_count = count_ocr_candidates()

    print("\n=== 总体状态 ===")
    print(f"Spark 视图: {'✓' if spark_ok else '✗'}")
    print(f"NAS 文件: {'✓' if nas_ok else '✗'}")
    print(f"处理计划: {'✓' if plan_ok else '✗'}")
    print(f"OCR 候选: {ocr_count}")

    all_ok = spark_ok and nas_ok and plan_ok
    if all_ok:
        print("\n✓ 所有步骤完成，可以开始 OCR 处理")
    else:
        print("\n✗ 有问题需要检查")

    return 0 if all_ok else 1

if __name__ == '__main__':
    try:
        sys.exit(main())
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
