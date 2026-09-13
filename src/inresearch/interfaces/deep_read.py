"""Terminal protocol for the L2 reading use cases; no direct business writes."""
import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path
from inresearch.materials import reading_policy as policy
from inresearch.materials.records import result_revision
from inresearch.workflow.deep_read import DeepRead, CompletionPending, now
from inresearch.storage.files import CommitUncertain
from inresearch.materials.reader_contracts import ReaderError


def emit(value):
    print(json.dumps(value, ensure_ascii=False))


def cmd_pack(app, a):
    emit(app.pack(a.sha, a.min_score, a.again, getattr(a, 'since', 0)))


def cmd_record(app, a):
    report = app.record(json.loads(Path(a.facts).read_text(encoding='utf-8')), a.doc, a.partial,
                        getattr(a, 'executor', None), getattr(a, 'model', None))
    errors = report.pop('problems')
    emit(report)
    for row in errors[:a.show]:
        print('  ' + str(row['fact_id']))
        for problem in row['problems']:
            print('     - ' + problem)
    for row in report.get('revisions_relinked', []):
        print('  ↩ 修订链改接：%s 的 supersedes 由 %s 改为 %s（新录的是更早的一版）'
              % (row['fact_id'], row['was'] or '（原为空）', row['now']))
    for pair in report.get('disputes', []):
        mark = '⚖ C3 A 档待审' if pair.get('needs_owner') else '· 已登记（方法离散，不占 A 档）'
        spread = ('极差 %.2fx' % pair['spread']) if pair.get('spread') else '极差未知'
        print('  %s：%s（%s）' % (mark, pair['about'], spread))
        for side in pair['sides']:
            print('     %s %s %s [%s]\n        %s' % (
                side['asserter'], side['value'], side['unit'], side['fact_id'], side['locator']))
    return 1 if errors else 0


def cmd_attribute(app, a):
    emit(app.attribute(a.sha, expected_revision=a.expected_revision, org=a.org,
        unrecoverable=a.unrecoverable, year=a.year, title=a.title, evidence=a.evidence))


def cmd_flag(app, a):
    emit(app.flag(a.sha, expected_revision=a.expected_revision,
        names=[name for name in policy.RESTRICTIONS if getattr(a, name)], clear=a.clear, evidence=a.evidence))


def cmd_skip(app, a):
    emit(app.skip(a.doc, a.gap, a.reason))


def cmd_gaps(app, a):
    if a.filled:
        emit(app.gaps.fill(a.filled, now()))
        return
    rows = app.gaps.open()
    emit(dict(open_gaps=len(rows), documents_waiting=len({r['sha256'] for r in rows})))
    for row in sorted(rows, key=lambda r: (r.get('module') or '', r['at'])):
        print('  %s  %-8s %s' % (row['gap_id'], row.get('module') or '?', row['gap']))
        print('           ' + (row.get('rel') or row['sha256'][:16]))


def cmd_backfill_provenance(app, a):
    report = app.backfill_provenance(a.commit, getattr(a, 'expected_plan', None))
    counts = Counter(method for row in report['candidates'] for method in row['methods'])
    emit({**report, '按前缀补全': counts['prefix'], '按路径补全': counts['path'],
          '按缓存键补全': counts['cache_key'], '前缀撞车（未动）': len(report['ambiguous']),
          '查不到（未动）': len(report['unknown']),
          'note': '已提交已审阅计划；历史缺口继续如实报告，不自动修改测试基线。' if a.commit else
                  '这是干跑；逐项复核候选后用 --commit --expected-plan ' + report['plan_sha256']})
    for row in report['ambiguous']:
        print('  撞车 %s：%s' % (row['fact_id'], row['why']))
    for row in report['unknown'][:a.show]:
        print('  查不到 %s：%s' % (row['fact_id'], row['why']))


def cmd_status(app, a):
    emit(app.status())
    for module, count in app.coverage().most_common():
        print('  %-8s %d' % (module, count))

def cmd_queue(app, a):
    pool = app.eligible(a.min_score, since=a.since)
    by_module = Counter(r.get('category') for r in pool)
    metrics = app.load_metrics()
    covered = Counter(metrics.get(f['metric_id'], {}).get('module')
                      for f in app.load_facts()['records'])
    excluded = sum(1 for r in app.all_results().values()
                   if (r.get('score') or 0) >= a.min_score
                   and r.get('status') == 'ok' and policy.self_authored(r))
    shown = [r for r in pool if policy.matches(r, a.grep)]
    print(json.dumps({'eligible_unprocessed': len(pool), 'min_score': a.min_score,
                      'candidates': [{'sha256': r['sha256'], 'result_revision': result_revision(r),
                                      'name': r.get('proposed_name') or r.get('rel')} for r in shown[:a.show]],
                      'already_processed': len(app.processed_documents()),
                      'processing_scope': 'fact_extraction_receipts_not_full_reading',
                      'self_authored_excluded': excluded,
                      'unattributed': sum(1 for r in pool if policy.unattributed(r)),
                      **({'since': a.since} if a.since else {}),
                      'restricted_excluded': sum(1 for r in app.all_results().values()
                                                 if (r.get('score') or 0) >= a.min_score
                                                 and r.get('status') == 'ok'
                                                 and policy.restricted(r)),
                      'mb': round(sum(r.get('size', 0) for r in pool) / 1e6)},
                     ensure_ascii=False))
    for module, n in by_module.most_common():
        print('  %-8s 待处理 %-4d 已有事实 %d' % (module, n, covered.get(module, 0)))
    if a.grep:
        print('  匹配「%s」%d 条（共 %d 条待处理）' % (a.grep, len(shown), len(pool)))
    for row in shown[:a.show]:
        module = row.get('category') or '?'
        year = policy.document_year(row)
        print('  %s  %-5s 已有事实 %-3d %2s 分 %s %s %s' % (
            row['sha256'][:16], module, covered.get(module, 0), row.get('score'),
            '%4d' % year if year else '  ??', policy.gap_label(row),
            (row.get('proposed_name') or row.get('rel', ''))[:58]))


def main(argv=None, app=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--reader-data-root', help='共享 reader 数据根；缺省使用 READER_DATA_ROOT 或项目默认数据目录')
    sub = ap.add_subparsers(dest='cmd', required=True)
    current = sub.add_parser('current', help='查询唯一当前全文阅读结果，不初始化或改写台账')
    current.add_argument('--sha', required=True, help='完整内容 SHA-256')
    q = sub.add_parser('queue'); q.add_argument('--min-score', type=int, default=policy.MIN_SCORE)
    q.add_argument('--since', type=int, default=0, help='只看这一年及以后的文件')
    q.add_argument('--show', type=int, default=15)
    q.add_argument('--grep', help='只列名字或路径里含这个词的')
    p = sub.add_parser('pack'); p.add_argument('--sha'); p.add_argument('--min-score', type=int, default=policy.MIN_SCORE)
    p.add_argument('--again', action='store_true', help='重新打开已处理材料的任务包，须同时给 --sha；不创建阅读版本')
    p.add_argument('--since', type=int, default=0, help='只取这一年及以后的文件')
    r = sub.add_parser('record'); r.add_argument('--facts', required=True)
    r.add_argument('--executor', help='调用客户端；未提供记 unknown')
    r.add_argument('--model', help='客户端报告的实际模型；未核实时不猜测')
    r.add_argument('--doc', help='处理材料 sha256，前缀即可，记录事实处理回执；不改变全文阅读状态')
    r.add_argument('--partial', action='store_true', help='收下通过校验的，跳过不通过的')
    r.add_argument('--show', type=int, default=10)
    t = sub.add_parser('attribute', help='把 L1 从预览里没看出来的出处补回判定')
    t.add_argument('--expected-revision', required=True, help='queue/pack 给出的 L1 版本')
    t.add_argument('--sha', required=True, help='文件 sha256，前缀即可')
    t.add_argument('--org', help='读全文找到的机构名')
    t.add_argument('--unrecoverable', action='store_true', help='全文翻完确实没有署名')
    t.add_argument('--year', help='四位数字')
    t.add_argument('--title', help='顺带修正标题')
    t.add_argument('--evidence', required=True, help='在哪一页哪一处看到的——出处得有出处')
    fl = sub.add_parser('flag', help='把一份文件挡在事实层之外，并记下理由')
    fl.add_argument('--expected-revision', required=True, help='queue/pack 给出的 L1 版本')
    fl.add_argument('--sha', required=True, help='文件 sha256，前缀即可')
    fl.add_argument('--confidential', action='store_true', help=policy.RESTRICTIONS['confidential'])
    fl.add_argument('--pii', action='store_true', help=policy.RESTRICTIONS['pii'])
    fl.add_argument('--clear', action='store_true', help='解除该标记')
    fl.add_argument('--evidence', required=True, help='在哪一页哪一处看到的')
    sk = sub.add_parser('skip', help='记录菜单缺口及处理回执；不改变全文阅读状态')
    sk.add_argument('--doc', required=True, help='文件 sha256，前缀即可')
    sk.add_argument('--gap', required=True, action='append',
                    help='缺的是什么——指标、维度还是枚举值，可重复给')
    sk.add_argument('--reason', help='除了菜单缺口以外的原因')
    g = sub.add_parser('gaps', help='列出未补的菜单缺口')
    # extend 而不是 append：一批补完常常是几十条，一条一个 --filled 抄错的概率
    # 比打字的成本高。--filled a b c 与 --filled a --filled b 都收。
    g.add_argument('--filled', action='extend', nargs='+', default=[],
                   metavar='GAP_ID',
                   help='菜单已补上，销掉这些 gap_id，可给多个、可重复给')
    bp = sub.add_parser('backfill-provenance',
                        help='把 evidence.source_id 里的 sha256 前缀补成完整哈希')
    bp.add_argument('--expected-plan', help='干跑给出的来源修复计划 SHA')
    bp.add_argument('--commit', action='store_true', help='真写；不给就是干跑')
    bp.add_argument('--show', type=int, default=10)
    sub.add_parser('status')
    a = ap.parse_args(argv)
    app = app if app is not None else DeepRead(reader_data_root=a.reader_data_root)
    try:
        if a.cmd == 'current':
            emit(app.current(a.sha))
            return 0
        return {'queue': cmd_queue, 'pack': cmd_pack, 'record': cmd_record,
         'attribute': cmd_attribute, 'flag': cmd_flag, 'skip': cmd_skip,
         'gaps': cmd_gaps, 'backfill-provenance': cmd_backfill_provenance,
         'status': cmd_status}[a.cmd](app, a)
    except CompletionPending as exc:
        emit(dict(ok=False, error=str(exc), commit_state=exc.authority+'_committed_receipt_pending'))
        return 1
    except CommitUncertain as exc:
        emit(dict(ok=False, error=str(exc), commit_state='visible_durability_unconfirmed'))
        return 1
    except ReaderError as exc:
        emit(dict(ok=False, error=exc.code))
        return 1
    except (ValueError, TypeError, KeyError, OSError, sqlite3.Error) as exc:
        emit(dict(ok=False, error=str(exc)))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
