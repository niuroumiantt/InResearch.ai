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
    # 企业自己的**定级**算，泛用页脚不算。两者的区别是「这份文件被单独判过」：
    # 联通企标封面的「企业内部资料，要求各单位严格保密」、阿里企业文件上的
    # 「B2 密级／商业秘密」，都是该公司按自己的密级体系给这一份定的等级；
    # 而厂商胶片角上印的 Confidential 是模板，一整套材料都带。
    # 定级要挡，页脚不挡——挡了页脚等于把大半个库排除掉，换不来任何东西。
    #
    # 三个判过的边界例（2026-09-14）：
    # · 公开会议上讲过的胶片，角上印着 Proprietary + Confidential：**不挡**。
    #   Hot Chips 是公开会议，这份材料本来就是讲给场外看的，那行字是模板。
    # · 「solely for the use of our client」，同一页又在招媒体合作：**挡**。
    #   自相矛盾时按写明的收件限制算——招媒体合作是发布方自己的市场行为，
    #   不等于解除了对客户那一侧的限制。代理可以收紧不可放宽，所以按紧的那一侧走；
    #   所有者认为可放宽时再取消。
    # · 逐订阅户加水印的下载件（EMIS 那种，水印里带订阅方 IP）：**挡**。
    #   水印能指认是谁下的，就等于「限定收件方」；而且转发它会暴露那个订阅方。
    #   水印里的 IP 属订阅机构不属个人，所以是 confidential 不是 pii，
    #   但**任何引用都不得把水印内容带出去**。
    'confidential': '文件写明限定收件方且不得分发，或带企业密级定级'
                    '（如「内部资料，严格保密」「B2 密级/商业秘密」）——不是泛用的机密页脚',
    # 判据是「这份个人信息在不在我们会抽取的数据区里」，不是「文件里有没有人名」。
    # IDC 那几个工作簿要标：分析师姓名、邮箱、电话就在单元格里，跟着表格一起被抽出来，
    # 一不小心就进了某条事实的 locator。券商报告的分析师联系方式不标：它在封面/封底的
    # 固定版式里，本来就是登出来供人联系的，而且报告作者本身是我们引用时要写明的东西。
    # 这条区分解掉了此前那个「IDC 标了、券商没标」的不一致——两者的差别不在敏感程度，
    # 在于它会不会被误抽进产物。
    # 标了的文件仍然可读可录，只是**抽出来的正文与 notes 里不得带上那些字段**。
    'pii': '会被抽进数据区的个人信息（姓名、电话、邮箱、职级）或内网地址，'
           '这些不该出现在任何被引用的产物里；'
           '券商报告封面那种登出来供联系的作者信息不属此列',
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


def resolve_document(rows, prefix, what='sha', allow_unregistered=False):
    """A sha or prefix -> the one judged document it names.

    allow_unregistered 默认关掉（2026-09-13）：完整哈希原来免检，理由是「已读台账
    认哈希不认判定」。代价出现了——手打错一位的 64 位哈希照样通过，record 收下事实
    并往已读台账里写了一行不对应任何文件的记录。**自证的前提是那串东西真的指向什么**：
    一个不在判定里的完整哈希既进不了队列、也标不了任何文件为已读，只会留一行垃圾。
    """
    if not isinstance(prefix, str) or not prefix or not re.fullmatch(r'[0-9a-f]{1,64}', prefix):
        raise ValueError('%s 要给出小写十六进制 SHA 或前缀' % what)
    matches = [row for sha, row in rows.items() if sha.startswith(prefix)]
    if len(matches) == 1:
        return matches[0]
    if not matches and allow_unregistered and FULL_SHA.fullmatch(prefix):
        return {'sha256': prefix}
    raise ValueError('%s「%s」匹配到 %d 份判定，要正好一份%s' % (
        what, prefix, len(matches),
        '。给长一点的前缀' if matches else
        ('。这是个完整哈希，但库里没有这份文件——抄错了一位，还是这份还没进判定？'
         if FULL_SHA.fullmatch(prefix) else
         '。这个前缀不在 L1 判定里——抄错了，或者这份还没进判定')))


def admission_problems(row):
    return (['本项目产物不能作为独立原始证据'] if self_authored(row) else []) + [
        '材料限制：' + RESTRICTIONS[name] for name in restricted(row)]
