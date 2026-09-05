"""标题中文化:把 FT 的英文标题翻成中文,给清单页当主标题。

**只翻标题,不翻正文。** 正文是站长自己订阅拿到的原文,它的价值就在于是原话;
标题翻译是为了在四十行清单里一眼扫过去,不是为了替代阅读。

走 Cloudflare Workers AI(站长 2026-08-22 指定)。这里**写死一个出网目标**:
地址不从配置读、不从环境变量读 —— 「能读谁」这件事只随代码审阅变动,
和 ``browser/contract.py`` 那张域名表是同一条规矩,只是这条走 HTTP 不走浏览器。

凭据按本项目已有的约定找:环境变量,或 ``secrets/`` 下的一个文件 ——
那个目录已经被 ``.gitignore`` 和 ``tools/guard_standalone.py`` 双重挡着。
**没配凭据是常态,不是崩溃**:不翻就是不翻,标题保持英文原样,并说清楚缺什么。
"""
from __future__ import annotations

import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

# 唯一的出网目标,写死。account_id 是路径的一部分,由凭据提供。
API_HOST = "https://api.cloudflare.com"
# **指令模型,不是通用翻译模型。** 8-24 站长:「标题翻译的很奇怪,不地道中文」——
# 原来走的 `@cf/meta/m2m100-1.2b` 是 12 亿参数的通用机器翻译模型,逐词直译。
# 而 FT 的标题大量是双关、缩略、行话(the internet's 'OG' / Gen Z / FirstFT),
# 直译出来就是「互联网的OG」「Z代」这种谁也不会那么说的中文。
#
# 换成指令模型,并且**把要求写进提示词**:中文新闻标题的口吻、专有名词留原文、
# 只输出译文。代价是它偶尔会加壳(引号、「翻译:」),所以下面要去壳 —— 那是
# 一次真实的权衡:直译模型不加壳但译不好,指令模型译得好但要收拾。
#
# 选 Qwen 是因为中文是它的母语侧。**出网目标仍然只有 api.cloudflare.com 一个**,
# 凭据也没变 —— 换的只是同一个账号下的模型名。
#
# 9-01 换 Qwen3:Cloudflare 对 qwen1.5-14b-chat-awq 全线回 410(已下架),
# 站长补分时一百篇全灭才暴露出来。qwen3-30b-a3b-fp8 是 2026-04-09 上架的
# 现役目录模型,仍是 Qwen 家。代价:Qwen3 是混合推理模型,回答前可能吐一段
# <think>…</think> —— 所以下面读答案前要先剥思考段,预算也要给足,
# 免得思考把 max_tokens 吃光、答案一个字没出来。
MODEL = "@cf/qwen/qwen3-30b-a3b-fp8"

# 提示词。写死在代码里,不从配置读 —— 它决定页面上每一条标题长什么样,
# 那种东西不该由一个配置文件说改就改。
SYSTEM_PROMPT = (
    "你是财经新闻编辑,把英文新闻标题改写成中文新闻标题。要求:"
    "用中文新闻标题的口吻,简洁、通顺,不要逐词直译;"
    "公司名、人名、产品名等专有名词保留英文原文,不要音译;"
    "不要加书名号、引号、句号,不要解释,不要输出原文,只输出这一条中文标题。"
)
SECRETS_FILENAME = "cloudflare.json"
TIMEOUT_SECONDS = 20


@dataclass(frozen=True)
class Credentials:
    account_id: str
    api_token: str
    origin: str


def _secrets_dir() -> Path:
    custom = os.environ.get("INEWS_SECRETS_DIR", "").strip()
    return Path(custom) if custom else Path.cwd() / "secrets"


def credentials() -> Credentials | None:
    """环境变量优先,然后是 ``secrets/cloudflare.json``。两样缺一就是没有。"""
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if account and token:
        return Credentials(account, token, "环境变量")
    path = _secrets_dir() / SECRETS_FILENAME
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    account = str(payload.get("account_id") or "").strip()
    token = str(payload.get("api_token") or "").strip()
    if account and token:
        return Credentials(account, token, str(path))
    return None


def status() -> dict[str, Any]:
    """**说清楚缺什么、放哪儿。** 一句「翻译不可用」帮不上任何人。"""
    creds = credentials()
    if creds:
        return {"ok": True, "note": f"翻译凭据来自 {creds.origin}"}
    return {
        "ok": False,
        "note": (
            "未配置翻译凭据,标题保持英文原样。"
            f"在 Cloudflare 建一个带 Workers AI 权限的 token,写进 secrets/{SECRETS_FILENAME}"
            '(格式:{"account_id": "...", "api_token": "..."}),'
            "或设环境变量 CLOUDFLARE_ACCOUNT_ID 与 CLOUDFLARE_API_TOKEN"
        ),
    }


def _post(url: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "authorization": f"Bearer {token}",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as error:
        # **原话进错误信息。** 403 是 token 少了权限、429 是额度用完 ——
        # 两者的处置完全不同,一句「翻译失败」会把它们抹平。
        detail = error.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"Cloudflare 返回 {error.code}:{detail}") from error


def translate_one(text: str, creds: Credentials | None = None) -> str:
    creds = creds or credentials()
    if not creds:
        raise RuntimeError(status()["note"])
    url = f"{API_HOST}/client/v4/accounts/{creds.account_id}/ai/run/{MODEL}"
    payload = _post(url, creds.api_token, {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        # 标题不需要发挥。温度压到底,同一条标题每次翻出来应该是同一句。
        "temperature": 0.2,
        # Qwen3 可能先思考再作答,思考也占 token —— 预算按「思考 + 一条标题」给,
        # 否则答案会被思考段挤出窗口。9-02 实测 600 不够:一批 184 条里不少条
        # finish_reason=length、content 直接是 null —— 它想得比我们预想的啰嗦。
        "max_tokens": 1600,
    })
    if not payload.get("success", True):
        raise RuntimeError(f"Cloudflare 拒绝了这次请求:{json.dumps(payload, ensure_ascii=False)[:300]}")
    result = payload.get("result") or {}
    translated = _unwrap(strip_reasoning(str(answer_of(result) or "")))
    if not translated:
        # 空译文照实说。一个空字符串顺着流下去,会在页面上变成一条没有标题的稿子。
        raise RuntimeError(f"Cloudflare 没有给出译文:{json.dumps(payload, ensure_ascii=False)[:300]}")
    if not _has_chinese(translated):
        # 模型有时原样回英文。**那不是译文** —— 当失败处理,标题保持英文原样,
        # 而不是把一句英文冒充成「已翻译」塞进页面。
        raise RuntimeError(f"模型没有给出中文,原样回了:{translated[:120]}")
    return translated


_WRAPPERS = tuple('「」《》"\'') + ("\u201c", "\u201d", "\u2018", "\u2019")
_PREFIXES = ("翻译:", "翻译:", "中文标题:", "中文标题:", "译文:", "译文:")


def answer_of(result: dict) -> Any:
    """从 Workers AI 的应答里取出答案本体。打分那头也用这一个。

    9-02 实测有两种形状:老的 ``result.response``,和 OpenAI 形状的
    ``choices[0].message.content``(此时 response 是空的,思考在单独的
    reasoning 字段里)。两头都空就如实返回 None —— 那通常是思考吃光了
    max_tokens(finish_reason=length),content 是 null,不是我们的解析问题。
    """
    response = result.get("response")
    if response not in (None, ""):
        return response
    choices = result.get("choices") or []
    if choices:
        return (choices[0].get("message") or {}).get("content")
    return None


# 混合推理模型(Qwen3 这类)的思考段。答案在思考**之后** —— 取首行、找 JSON
# 的逻辑都必须先把它整段剥掉,否则拿到的是思考的第一句。打分那头也用这一个。
_THINK_RX = re.compile(r"<think>.*?</think>", re.S)


def strip_reasoning(text: str) -> str:
    return _THINK_RX.sub("", text).strip()


def _unwrap(text: str) -> str:
    """去壳:指令模型偶尔会加引号或「翻译:」。**只去壳,不改字。**

    去壳是有边界的:只剥掉整条首尾成对的引号和这几个固定前缀。标题内部本来就
    带引号的(FT 很爱用),一个字都不动。
    """
    cleaned = text.strip()
    # 多行时只取第一行:加解释的那种回答,解释永远在后面。
    cleaned = cleaned.splitlines()[0].strip() if cleaned else ""
    for prefix in _PREFIXES:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    while len(cleaned) >= 2 and cleaned[0] in _WRAPPERS and cleaned[-1] in _WRAPPERS:
        cleaned = cleaned[1:-1].strip()
    return cleaned


def _has_chinese(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _is_timeout(error: BaseException) -> bool:
    """这次失败是不是「根本没被处理」。

    只认超时。**403 / 429 一律不重试**:重试它们一次都不会成功,只会把一个
    清楚的问题拖成「怎么这么慢」—— 而 429 本来就是额度用完,再问一遍是往
    枪口上撞。超时不同:请求没被处理完,再问一遍不会有第二个副作用。
    """
    if isinstance(error, (TimeoutError, socket.timeout)):
        return True
    return "timed out" in str(error).lower()


def is_quota_exhausted(error: BaseException) -> bool:
    """这次失败是不是「额度用完」。

    9-01 站长撞上:免费档每天一万 neurons,用完后整批一百篇逐个 429 ——
    同一句原话抄一百遍。额度不会在一批之内自己回来,所以它是唯一一种
    该让**整批停下**的失败;别的失败仍然一篇一篇如实记,不连坐。
    判据认 Cloudflare 的错误码 4006 和它的原话,不猜别的 429。
    """
    text = str(error)
    return "4006" in text or "free allocation" in text


RETRY_PAUSE_SECONDS = 2


def fill_titles(
    rows: list[dict[str, Any]],
    *,
    translate_one: Callable[[str], str] = translate_one,
    progress: Callable[[str], None] = lambda _message: None,
) -> int:
    """给还没有译文的标题补上中文,返回补了几条。

    **只翻缺的那些。** 每小时一轮时库里几百篇、新增两三篇 —— 成本必须随
    「新增」走,不随「库存」走,否则每天多花几百次调用买回同一批译文。

    一条失败不中断其余:错误原话记在 ``title_zh_error`` 上,由页面照实显示。
    """
    pending = [
        row for row in rows
        if row.get("title_en") and not str(row.get("title_zh") or "").strip()
    ]
    if not pending:
        return 0
    done = 0
    for index, row in enumerate(pending, start=1):
        title = str(row["title_en"])
        progress(f"翻译标题 {index}/{len(pending)}:{title}")
        try:
            try:
                row["title_zh"] = translate_one(title)
            except Exception as error:  # noqa: BLE001
                if not _is_timeout(error):
                    raise
                progress(f"超时,{RETRY_PAUSE_SECONDS} 秒后重试一次:{error}")
                time.sleep(RETRY_PAUSE_SECONDS)
                row["title_zh"] = translate_one(title)
            row.pop("title_zh_error", None)
            done += 1
        except Exception as error:  # noqa: BLE001 一条失败不该带走整轮
            # 重试之后还是不行就**如实失败**,原话照留,不改说法。
            row["title_zh_error"] = str(error)
            progress(f"翻译失败:{error}")
            if is_quota_exhausted(error):
                # 额度在一批之内不会自己回来。剩下的不再尝试,也不给它们
                # 抄这句它们没收到过的原话 —— 下一轮额度回来会补上。
                progress(f"额度用完,本批剩余 {len(pending) - index} 条不再尝试")
                break
    return done
