#!/usr/bin/env python3
"""M4 triage L1 via the local ollama model.  No API, no network beyond localhost.

The judgement contract is identical to the in-session path (m4_triage_pack.py),
so rows from both land in the same l1_results.jsonl and are told apart by the
`model` field.  Examples scored in-session are replayed as few-shot anchors so
the small model inherits the calibration rather than inventing its own.

  calibrate --limit N   re-score files already scored in-session, report agreement
  run [--limit N]       score pending files

`run --workers N` keeps N requests in flight. The local server answers them in
parallel only when it is started with OLLAMA_NUM_PARALLEL >= N; otherwise the
extra requests just queue there and nothing gets faster.
"""
from __future__ import annotations
import argparse, json, random, re, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import m4_triage_l1 as L1
import m4_triage_pack as PK

MODEL = 'qwen3:8b'
MAX_WORKERS = 16
ENDPOINT = 'http://127.0.0.1:11434/api/chat'
FEWSHOT = 8


def call(system: str, user: str, timeout: int = 180) -> dict:
    body = json.dumps({'model': MODEL, 'messages': [{'role': 'system', 'content': system},
                                                    {'role': 'user', 'content': user}],
                       'stream': False, 'format': 'json', 'think': False,
                       'options': {'temperature': 0, 'num_ctx': 8192, 'num_predict': 700}}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        out = json.load(res)
    if out.get('model') != MODEL:
        raise RuntimeError('model_identity_unverified')
    msg = out['message']
    return json.loads(msg.get('content') or msg.get('thinking') or '')


def scored_rows():
    rows = []
    if L1.RESULTS.exists():
        for line in L1.RESULTS.open(encoding='utf-8'):
            try: r = json.loads(line)
            except ValueError: continue
            if r.get('status') == 'ok' and r.get('model') == 'claude-code-session':
                rows.append(r)
    return rows


def system_prompt() -> str:
    # Anchors are stratified across the score range.  An unstratified sample is
    # dominated by 1-3 (most of the corpus is vendor material) and the small
    # model then collapses everything onto 2.
    buckets = {}
    for r in scored_rows():
        buckets.setdefault(r['score'], []).append(r)
    lines = []
    for score in sorted(buckets, reverse=True):
        for r in sorted(buckets[score], key=lambda x: x['rel'])[:2]:
            lines.append('%s → score=%d module=%s：%s' % (Path(r['rel']).name[:48], r['score'], r['category'], (r.get('rationale') or '')[:55]))
    examples = '\n'.join(lines)
    return L1.task_card() + """

以下是已由资深分拣员判定的样例，请以同样的尺度打分：
""" + examples + """

判分要点：
1. 不要把所有文件都判成 2 分。上面的样例覆盖 0 到 8 分，请用满整个区间。
2. 文件名里的“数据中心”常指企业数据平台、数据仓库、BI 或某行业信息系统，不是物理数据中心机房；这类判 0–1 分。
3. 运营商或国家的正式标准与技术规范书、一手项目容量与造价数据、行业年鉴名录、头部厂商的实测实践：6–8 分。
4. 厂商产品方案、投标交付文档、通用架构演示：2–3 分。
5. 设备产品手册若含具体技术参数（UPS、精密空调、微模块规格），判 5 分，归 M09。
6. 模块判断看主题实体：机房土建运营归 M10，供电与电气设备归 M09，制冷与液冷归 M08，网络设备与光模块归 M07，芯片服务器归 M06，中国市场与政策归 M14，市场规模数据归 M01。
只输出 JSON，字段：score, module, title, org, year, keep_original_name, doc_type, language, rationale, evidence, confidence。"""


def judge(rec, system):
    text = PK.clean_preview(rec['preview'])[:PK.PREVIEW_CHARS]
    head = {'path': rec['rel'], 'suffix': rec['suffix'], 'kb': round(rec['size'] / 1024)}
    user = '文件元数据：\n' + json.dumps(head, ensure_ascii=False) + '\n\n文本预览：\n<<<\n' + (text or '（无可提取文本，只能按文件名判断）') + '\n>>>'
    v = call(system, user)
    v.setdefault('language', ''); v.setdefault('evidence', ''); v.setdefault('doc_type', 'other')
    v.setdefault('confidence', 'medium'); v.setdefault('org', '未知'); v.setdefault('year', '未知')
    v.setdefault('rationale', ''); v.setdefault('keep_original_name', True); v.setdefault('title', Path(rec['rel']).stem)
    v['score'] = max(0, min(10, int(v.get('score', 0))))
    if v.get('module') not in {'M%02d' % i for i in range(1, 16)} | {'unrelated', 'unknown'}:
        v['module'] = 'unknown'
    return v


def cmd_calibrate(a):
    system = system_prompt(); rows = scored_rows()
    random.Random(11).shuffle(rows); rows = rows[:a.limit]
    inv = {i['sha256']: i for i in L1.load_inventory()}
    agree = diff = 0; big = []; t0 = time.time()
    for r in rows:
        item = inv.get(r['sha256'])
        if not item: continue
        rec = L1.prepare(item)
        try: v = judge(rec, system)
        except Exception as exc:
            print(json.dumps({'rel': r['rel'][-50:], 'error': str(exc)[:80]}, ensure_ascii=False)); continue
        d = abs(v['score'] - r['score'])
        same_mod = v['module'] == r['category']
        if d <= 2 and same_mod: agree += 1
        else:
            diff += 1; big.append((r['rel'][-55:], r['score'], r['category'], v['score'], v['module']))
        print(json.dumps({'mine': [r['score'], r['category']], 'local': [v['score'], v['module']], 'f': r['rel'][-45:]}, ensure_ascii=False))
    n = agree + diff
    print(json.dumps({'compared': n, 'agree(±2分且同模块)': agree, 'disagree': diff,
                      'rate': round(agree / n, 2) if n else 0, 'sec_per_file': round((time.time() - t0) / max(n, 1), 1)}, ensure_ascii=False))


def cmd_run(a):
    """Score pending files, `a.workers` model requests in flight.

    Rows are appended under a lock, so an interrupted run keeps every row it
    already wrote and `pending()` skips them next time.  `--limit` still counts
    only files that reach the model: a file whose preview needs no model is
    written without spending the budget, and once the budget is gone the
    remaining files are left pending rather than written half-judged."""
    if not isinstance(a.workers, int) or not 1 <= a.workers <= MAX_WORKERS:
        raise SystemExit('workers must be 1..%d' % MAX_WORKERS)
    system = system_prompt()
    items = PK.pending()
    counts = {'scored': 0, 'errors': 0, 'no_model': 0, 'dispatched': 0}
    guard = threading.Lock()
    t0 = time.time()

    with L1.RESULTS.open('a', encoding='utf-8') as f:
        def emit(row, key):
            with guard:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
                counts[key] += 1
                judged = counts['scored'] + counts['errors']
                if key != 'no_model' and judged % 25 == 0:
                    f.flush()
                    print(json.dumps({'done': counts['scored'], 'errors': counts['errors'],
                                      'sec_per_file': round((time.time() - t0) / judged, 1)}), flush=True)

        def budget_gone():
            with guard:
                return bool(a.limit) and counts['dispatched'] >= a.limit

        def take_slot():
            """Reserve the budget before the call, not after it returns: several
            threads would otherwise all pass the check while none has finished."""
            with guard:
                if a.limit and counts['dispatched'] >= a.limit:
                    return False
                counts['dispatched'] += 1
                return True

        def work(item):
            if budget_gone():
                return
            rec = L1.prepare(item)
            if not rec['needs_model']:
                o = L1.finalize(rec, None, None, None)
                o['proposed_name'] = L1.proposed_name(o)
                emit(o, 'no_model')
                return
            if not take_slot():  # the preview may have taken a while
                return
            try:
                v = judge(rec, system)
            except Exception as exc:
                o = L1.finalize(rec, None, None, 'local_model:' + str(exc)[:80])
                o['proposed_name'] = L1.proposed_name(o)
                emit(o, 'errors')
                return
            o = L1.finalize(rec, v, {'judge': MODEL}, None)
            o['proposed_name'] = L1.proposed_name(o); o['model'] = MODEL
            emit(o, 'scored')

        with ThreadPoolExecutor(a.workers) as ex:
            list(ex.map(work, items))

    judged = counts['scored'] + counts['errors']
    print(json.dumps({'scored': counts['scored'], 'errors': counts['errors'],
                      'no_model': counts['no_model'], 'workers': a.workers,
                      'sec_per_file': round((time.time() - t0) / max(judged, 1), 1)}))


def main():
    ap = argparse.ArgumentParser(); s = ap.add_subparsers(dest='cmd', required=True)
    c = s.add_parser('calibrate'); c.add_argument('--limit', type=int, default=25)
    r = s.add_parser('run'); r.add_argument('--limit', type=int, default=0)
    r.add_argument('--workers', type=int, default=1,
                   help='model requests in flight (1..%d); needs OLLAMA_NUM_PARALLEL >= this on the server' % MAX_WORKERS)
    a = ap.parse_args()
    {'calibrate': cmd_calibrate, 'run': cmd_run}[a.cmd](a)


if __name__ == '__main__':
    main()
