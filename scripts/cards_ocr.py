#!/usr/bin/env python3
"""对 fulltext 卡片里标记为 n(不可读)的 PDF 重跑 OCR 并重新打分。

读 ~/.local/share/inresearch.ai/fulltext/cards.jsonl, 结果追加写
~/cards-ocr.jsonl。外部依赖 qwen3-vl 与 qwen3:30b-a3b, 所以实际在
Spark 上跑, 不在 CI 里跑。

    python3 scripts/cards_ocr.py          # 干跑, 只定位文件不调模型
    DRY=0 python3 scripts/cards_ocr.py    # 真跑

2026-09-21 从 infra 仓库顶层移来 —— 它处理的是本项目的数据, 放在 infra
里既没人引用也说不清归属(见 infra docs/naming-audit.md)。
"""
import json
import os
import sys
from pathlib import Path
from collections import defaultdict
import subprocess
import tempfile
import shutil

ROOT = Path.home()
FT = ROOT / '.local/share/inresearch.ai/fulltext'
CARDS_FILE = FT / 'cards.jsonl'
PLAN_FILE = ROOT / 'cards-plan.jsonl'
OCR_LOG = ROOT / 'cards-ocr.jsonl'
BATCH_SIZE = 50

ROOTS = {
    ROOT / 'nas-dc-library': '20260906-nas-reports',
    ROOT / '.local/share/inresearch.ai/sorted/20260919-nas-laobing2025': '20260919-nas-laobing2025',
}

def load_cards():
    cards = {}
    if not CARDS_FILE.exists():
        return cards
    with open(CARDS_FILE) as f:
        for line in f:
            c = json.loads(line)
            cards[c['sha']] = c
    return cards

def find_ocr_candidates():
    candidates = []
    cards = load_cards()
    for sha, card in cards.items():
        if card.get('marker') == 'n':
            candidates.append((sha, card))
    return candidates

def locate_file(card):
    fname = None
    for root, batch_name in ROOTS.items():
        batch_dir = root / batch_name
        if not batch_dir.exists():
            continue
        for module_dir in batch_dir.iterdir():
            if not module_dir.is_dir():
                continue
            pdf_path = list(module_dir.glob('*.pdf'))
            if pdf_path:
                for pdf in pdf_path:
                    if card['sha'] in pdf.name:
                        return pdf
    return None

def call_ocr(pdf_path):
    try:
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
            tmp_path = tmp.name

        cmd = [
            'qwen3-vl',
            'ocr',
            str(pdf_path),
            '--output', tmp_path
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            return None, f"qwen3-vl failed: {result.stderr.decode()}"

        with open(tmp_path) as f:
            text = f.read()
        os.unlink(tmp_path)
        return text, None
    except Exception as e:
        return None, str(e)

def rescore_card(card, ocr_text):
    if not ocr_text or len(ocr_text.strip()) < 50:
        return None

    cmd = [
        'qwen3:30b-a3b',
        '--system', 'Score this document 0-10 based on relevance to data center compute capacity, infrastructure, AI/ML workloads, energy efficiency. Output only: score (0-10), language (zh/en/zh+en), module (M01-M15/_review/_unrelated), confidence.',
        '--prompt', ocr_text[:5000]
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=60, text=True)
        if result.returncode != 0:
            return None

        lines = result.stdout.strip().split('\n')
        if len(lines) < 1:
            return None

        parts = lines[0].split(',')
        if len(parts) < 4:
            return None

        score = int(parts[0].strip())
        lang = parts[1].strip().lower()
        module = parts[2].strip()
        conf = parts[3].strip()

        return {
            'score': score,
            'language': lang,
            'module': module,
            'confidence': conf,
            'ocr_text_len': len(ocr_text)
        }
    except Exception as e:
        return None

def process_batch(candidates, start_idx=0, dry_run=True):
    total = len(candidates)
    processed = 0
    succeeded = 0
    failed = 0

    print(f"OCR候选: {total} 张")

    if not candidates:
        print("没有标记为n的文件")
        return

    logs = []

    for i, (sha, card) in enumerate(candidates[start_idx:], start=start_idx):
        print(f"\r处理 {i+1}/{total} ...", end='', flush=True)

        pdf_path = locate_file(card)
        if not pdf_path or not pdf_path.exists():
            log_entry = {
                'sha': sha,
                'status': 'file_not_found',
                'original_path': card.get('path')
            }
            logs.append(log_entry)
            failed += 1
            continue

        if dry_run:
            log_entry = {
                'sha': sha,
                'status': 'dry_run',
                'path': str(pdf_path),
                'original_score': card.get('fulltext_score'),
                'original_module': card.get('module')
            }
            logs.append(log_entry)
            succeeded += 1
        else:
            ocr_text, error = call_ocr(pdf_path)
            if error:
                log_entry = {
                    'sha': sha,
                    'status': 'ocr_failed',
                    'error': error,
                    'path': str(pdf_path)
                }
                logs.append(log_entry)
                failed += 1
                continue

            rescore = rescore_card(card, ocr_text)
            if not rescore:
                log_entry = {
                    'sha': sha,
                    'status': 'rescore_failed',
                    'path': str(pdf_path)
                }
                logs.append(log_entry)
                failed += 1
                continue

            log_entry = {
                'sha': sha,
                'status': 'success',
                'path': str(pdf_path),
                'original_score': card.get('fulltext_score'),
                'ocr_score': rescore['score'],
                'original_module': card.get('module'),
                'ocr_module': rescore['module'],
                'language': rescore['language'],
                'confidence': rescore['confidence'],
                'ocr_text_len': rescore['ocr_text_len']
            }
            logs.append(log_entry)
            succeeded += 1

        processed += 1
        if processed % 10 == 0:
            with open(OCR_LOG, 'a') as f:
                for log in logs:
                    f.write(json.dumps(log, ensure_ascii=False) + '\n')
            logs = []

    print()

    if logs:
        with open(OCR_LOG, 'a') as f:
            for log in logs:
                f.write(json.dumps(log, ensure_ascii=False) + '\n')

    print(f"已处理 {processed} · 成功 {succeeded} · 失败 {failed}")
    if dry_run:
        print(f"日志已写 {OCR_LOG}")
        print("运行 DRY=0 python3 scripts/cards_ocr.py 开始真实OCR处理")

def main():
    dry_run = os.getenv('DRY', '1') == '1'

    if dry_run:
        print("干跑模式 (DRY=0 进行真实OCR)")
    else:
        print("真实OCR模式")

    candidates = find_ocr_candidates()
    process_batch(candidates, dry_run=dry_run)

if __name__ == '__main__':
    try:
        main()
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
