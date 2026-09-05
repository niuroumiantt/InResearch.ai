"""文章价值评分 v2：只衡量“值不值得读”，不再奖励篇幅本身。

旧公式把长度当成独立加分项，结果长 newsletter 能用篇幅补偿低相关性。v2 以
Bloomberg AI 栏目的高价值样本为参照，把主题中心度、具体事件和实质影响放在
最前面；长度只影响模型能看到多少证据，不产生分数。

**打分只标注,不过滤。** 「过滤名单的判据必须是结构性事实」那条边界仍然成立:
分数不进任何过滤逻辑,它是清单上多出来的一列信息,裁决权始终在看页面的人手里。

六个维度由模型判断，总分权重和两道硬封顶写死在代码里，不让模型临时改变编辑
立场。v1 分数继续按旧量尺展示；只有显式重打或新文章才写 v2，避免历史数据被
悄悄改义。

走 translate.py 那条 Cloudflare 通道:同一个出网目标、同一份凭据、同一套
「没配凭据是常态,不打就是不打」的姿态。没配就不打,失败原话留在 ``score_error``。
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable

from inews import translate
from inews.translate import Credentials, credentials

# v1 字段只用于展示历史分；新评分不拿旧维度凑数，避免不同量尺混在一起。
VERSION = 2
LEGACY_DIMENSIONS = (
    ("relevance", "相关"), ("depth", "深度"), ("data", "数据"),
    ("analysis", "分析"), ("impact", "影响"), ("exclusive", "独家"),
)

# 权重总和 100。中心度与事件价值占一半，其他优点不能补偿“不是 AI 新闻”。
DIMENSIONS = (
    ("centrality", "主题中心", 30),
    ("event", "事件", 20),
    ("impact", "影响", 20),
    ("evidence", "证据", 15),
    ("originality", "原创", 10),
    ("timeliness", "时效", 5),
)

# 正文送多少给模型:打分要的是判断,不是复读全文。八千字符足够看清一篇的骨架,
# 也让每次调用的成本有一个不随稿子长度乱飘的上限。
BODY_SAMPLE_CHARS = 8000

# 提示词写死在代码里,和 translate.SYSTEM_PROMPT 同一条规矩:它决定每篇的分数
# 长什么样,不该由配置文件说改就改。「只输出 JSON」必须点名 —— 不点名,
# 指令模型会回「以下是评分:……」,解析就得在散文里捞数字。
SYSTEM_PROMPT = (
    "你是关注 AI 产业的财经科技编辑，以 Bloomberg AI 栏目的硬新闻密度为参照。"
    "只输出一个 JSON 对象，不要任何解释。六个维度各给 0-10 的整数:"
    "centrality(AI 是否是文章主语:0=无关或顺带提及;10=标题、导语、全文都以 AI 为核心)、"
    "event(是否有命名主体、具体动作与对象/后果:0=闲谈汇编;10=明确的新事件)、"
    "impact(对资本、算力、监管、市场结构或采用的实质影响)、"
    "evidence(数字、具名参与方、文件与一手引语的充分度)、"
    "originality(独家性、原创采访或稀缺信息)、timeliness(相对事件发生的时效)。"
    "篇幅本身不加分；观点、问句、综述、newsletter 和仅由 AI 解释股价波动的稿件应降低 event。"
    "另给 notes:一句不超过 80 字的中文评分依据,点明分数高低的原因。"
    '格式:{"centrality":0,"event":0,"impact":0,"evidence":0,'
    '"originality":0,"timeliness":0,"notes":"…"}'
)


def composite(detail: dict[str, int]) -> int:
    """加权总分，并用中心度/事件性硬封顶，防止其他维度补偿跑题。"""
    score = round(sum(detail[name] * weight for name, _label, weight in DIMENSIONS) / 10)
    if detail["centrality"] < 6:
        score = min(score, 49)
    if detail["event"] < 4:
        score = min(score, 64)
    return score


def _parse_reply(reply: Any) -> tuple[dict[str, int], str]:
    """从模型回答里取出六维与依据。

    回答有两种形状,都是 9-01 实测到的:Workers AI 对 qwen3 常把模型的 JSON
    输出**解析好再给我们**(``result.response`` 直接是个对象)—— 那种直接收下;
    是字符串时才当文本处理:先剥 Qwen3 的 <think> 思考段(里面常有花括号草稿),
    再在壳(围栏、解释、前后缀)里找第一段 ``{...}``。
    **缺维度如实失败**:拿 0 补上等于把「模型没答」冒充成「模型判了 0 分」。
    越界的值收进 0-10 —— 界外没有语义,10 分制里不存在 15 分。
    """
    if isinstance(reply, dict):
        payload = reply
        raw = json.dumps(reply, ensure_ascii=False)
    else:
        text = translate.strip_reasoning(str(reply or ""))
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise RuntimeError(f"模型没有给出 JSON,原样回了:{text[:200]}")
        try:
            payload = json.loads(text[start:end + 1])
        except ValueError as error:
            raise RuntimeError(f"模型给的 JSON 解析不了:{text[start:end + 1][:200]}") from error
        raw = text[start:end + 1]
    detail: dict[str, int] = {}
    for name, label, _weight in DIMENSIONS:
        value = payload.get(name)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise RuntimeError(f"模型没给「{label}」({name})这一维:{raw[:200]}")
        detail[name] = max(0, min(10, int(value)))
    return detail, str(payload.get("notes") or "").strip()


def display_dimensions(row: dict[str, Any]) -> list[tuple[str, int]]:
    """新旧分数各按自己的量尺展示，历史分不伪装成 v2。"""
    detail = row.get("score_detail") or {}
    dimensions = DIMENSIONS if row.get("score_version") == VERSION else LEGACY_DIMENSIONS
    pairs = [
        (item[1], int(detail.get(item[0], 0)))
        for item in dimensions
        if item[0] in detail
    ]
    if row.get("score_version") != VERSION and "length" in detail:
        pairs.append(("长度", int(detail["length"])))
    return pairs


def score_one(row: dict[str, Any], creds: Credentials | None = None) -> dict[str, Any]:
    """给一篇打分,返回要并进行里的三个字段;失败抛异常,原话由调用方留档。"""
    creds = creds or credentials()
    if not creds:
        raise RuntimeError(translate.status()["note"])
    body = str(row.get("body") or "")
    content = (
        f"标题:{row.get('title_en', '')}\n\n"
        f"正文(截取):{body[:BODY_SAMPLE_CHARS]}"
    )
    url = f"{translate.API_HOST}/client/v4/accounts/{creds.account_id}/ai/run/{translate.MODEL}"
    payload = translate._post(url, creds.api_token, {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        # 打分要的是稳定的判断,同一篇两次问出两个分会让人不再信任何一个。
        "temperature": 0.2,
        # Qwen3 可能先思考再作答,预算按「思考 + 一段 JSON」给(同 translate;
        # 9-02 标题那头实测思考能吃掉上千 token,这里同步放宽)。
        "max_tokens": 2400,
    })
    if not payload.get("success", True):
        raise RuntimeError(f"Cloudflare 拒绝了这次请求:{json.dumps(payload, ensure_ascii=False)[:300]}")
    # 答案原样交给解析:它可能是字符串,也可能已经是结构化对象 ——
    # 在这里 str() 一下,对象就成了 Python 字典的样子,JSON 解析必死。
    # 取答案走 translate.answer_of:两种应答形状(response / choices)都认。
    detail, notes = _parse_reply(translate.answer_of(payload.get("result") or {}))
    return {
        "score": composite(detail), "score_version": VERSION,
        "score_detail": detail, "score_notes": notes,
    }


def fill_scores(
    rows: list[dict[str, Any]],
    *,
    score_one: Callable[..., dict[str, Any]] = score_one,
    progress: Callable[[str], None] = lambda _message: None,
) -> int:
    """给还没有分的补上,返回打了几篇。

    **只打有正文、还没有分的。** 成本随「新增」走,不随「库存」走 —— 和
    fill_titles 同一条账。一篇失败不中断其余,原话记在 ``score_error``。
    """
    pending = [
        row for row in rows
        if row.get("body") and row.get("score_version") != VERSION
    ]
    done = 0
    for index, row in enumerate(pending, start=1):
        progress(f"打分 {index}/{len(pending)}:{row.get('title_en', '')}")
        try:
            try:
                result = score_one(row)
            except Exception as error:  # noqa: BLE001
                if not translate._is_timeout(error):
                    raise
                progress(f"超时,{translate.RETRY_PAUSE_SECONDS} 秒后重试一次:{error}")
                time.sleep(translate.RETRY_PAUSE_SECONDS)
                result = score_one(row)
            row.update(result)
            row.pop("score_error", None)
            done += 1
        except Exception as error:  # noqa: BLE001 一篇失败不该带走整批
            row["score_error"] = str(error)
            progress(f"打分失败:{error}")
            if translate.is_quota_exhausted(error):
                # 同 fill_titles:额度不会在一批之内回来,剩下的不再撞墙。
                progress(f"额度用完,本批剩余 {len(pending) - index} 篇不再尝试")
                break
    return done
