"""Admission and identity rules shared by the L2 queue, packet and fact writer."""
from __future__ import annotations
import re
MIN_SCORE = 7
FULL_SHA = re.compile(r'[0-9a-f]{64}')
UNKNOWN = '未知'
YEAR = re.compile(r'^\d{4}$')
SELF_AUTHORED_ORGS = {'本项目', 'inresearch', 'inresearch.ai', '内部研究'}
SELF_AUTHORED_PREFIXES = ('要删/reader/', 'docs/', 'data/', 'framework/', 'reports/')
RESTRICTIONS = {
    # NOT for the word "Confidential" on its own.  In this corpus a machine
    # footer reading 机密 / Confidential is boilerplate - most vendor decks
    # carry one - and gating on it would exclude most of the library for no
    # gain.  This flag is for an explicit restriction naming a recipient:
    # "Confidential for X Corp. / Not to be distributed".  Nothing sets it
    # automatically; a person decides, per file, and says where they saw it.
    'confidential': '文件写明限定收件方且不得分发——不是泛用的机密页脚',
    'pii': '含个人信息（姓名、电话、邮箱、职级）或内网地址，'
           '这些不该出现在任何被引用的产物里',
}
YEAR4 = re.compile(r'(19|20)\d{2}')


def self_authored(row: dict) -> bool:
    if str(row.get('org') or '').strip() in SELF_AUTHORED_ORGS:
        return True
    return str(row.get('rel') or '').startswith(SELF_AUTHORED_PREFIXES)


def restricted(row: dict) -> list[str]:
    """Explicit material restrictions are independent of quality score."""
    return [name for name in RESTRICTIONS if row.get(name)]


def unattributed(row: dict) -> list[str]:
    """Per-field attribution gaps not resolved by a full-text inspection."""
    missing = [field for field in ('org', 'year')
               if str(row.get(field) or UNKNOWN).strip() in ('', UNKNOWN)]
    # Saying the publisher cannot be found silences the publisher ask, not the
    # year one: they are looked for in different places and found separately.
    searched = set(row.get('unrecoverable') or ())
    if row.get('org_unrecoverable'):
        searched.add('org')
    return [field for field in missing if field not in searched]


def gap_label(row: dict) -> str:
    """Name the missing field without mislabelling a known publisher."""
    missing = unattributed(row)
    if 'org' in missing:
        return '出处未知'
    return '年份未知' if 'year' in missing else '    '


def document_year(row: dict) -> int:
    """Queue sorting hint only; recency does not grant replacement authority."""
    for field in ('year', 'proposed_name', 'rel'):
        found = YEAR4.search(str(row.get(field) or ''))
        if found:
            return int(found.group(0))
    return 0


def matches(row: dict, needle: str | None) -> bool:
    if not needle:
        return True
    hay = '%s %s %s' % (row.get('proposed_name') or '', row.get('rel') or '',
                        row.get('title') or '')
    return needle.lower() in hay.lower()


def resolve_document(rows, prefix, what='sha', allow_unregistered=True):
    if not isinstance(prefix, str) or not prefix or not re.fullmatch(r'[0-9a-f]{1,64}', prefix):
        raise ValueError('%s 要给出小写十六进制 SHA 或前缀' % what)
    matches = [row for sha, row in rows.items() if sha.startswith(prefix)]
    if len(matches) == 1:
        return matches[0]
    if not matches and allow_unregistered and FULL_SHA.fullmatch(prefix):
        return {'sha256': prefix}
    raise ValueError('%s 前缀「%s」匹配到 %d 份判定，要正好一份' % (what, prefix, len(matches)))


def admission_problems(row):
    return (['本项目产物不能作为独立原始证据'] if self_authored(row) else []) + [
        '材料限制：' + RESTRICTIONS[name] for name in restricted(row)]
