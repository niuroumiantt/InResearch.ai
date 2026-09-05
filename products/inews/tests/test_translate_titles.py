"""标题中文化的用例。

8-24 站长:「标题翻译的很奇怪,不地道中文」。查下来是模型选错了 ——
`@cf/meta/m2m100-1.2b` 是通用机器翻译小模型,逐词直译;而 FT 的标题大量是双关、
缩略、行话("the internet's 'OG'"、"Gen Z"、"FirstFT"),正是它最不擅长的。

改走指令模型 + 一段「翻新闻标题」的提示词。这里钉的是**提示词里那些要求真的在**,
以及**失败仍然如实失败** —— 换模型不该顺手把「不猜、不兜底」这两条弄丢。
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from inews import translate


class _Recorder:
    """假装是 Cloudflare:记下请求,回一个指令模型形状的应答。"""

    def __init__(self, reply: str = "雅虎想赢得 Z 世代") -> None:
        self.payload: dict[str, Any] = {}
        self.url = ""
        self.reply = reply

    def __call__(self, url: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.url, self.payload = url, payload
        return {"success": True, "result": {"response": self.reply}}


@pytest.fixture
def creds() -> translate.Credentials:
    return translate.Credentials("acct", "token", "用例")


def test_it_no_longer_uses_the_word_by_word_translation_model():
    """m2m100 是逐词直译的通用翻译模型 —— 标题不地道的根子就在这。"""
    assert "m2m100" not in translate.MODEL
    assert translate.MODEL.startswith("@cf/"), "仍然走同一个 Cloudflare 账号"


def test_the_prompt_asks_for_a_chinese_news_headline(creds, monkeypatch):
    """提示词要说清楚三件事:中文新闻标题的口吻、专有名词留原文、不要加解释。

    不写「只输出译文」的话,指令模型会回「以下是翻译:……」,那一整句会变成标题。
    """
    recorder = _Recorder()
    monkeypatch.setattr(translate, "_post", recorder)
    translate.translate_one("Yahoo, the internet's 'OG', wants to win over Gen Z", creds)
    sent = json.dumps(recorder.payload, ensure_ascii=False)
    assert "新闻标题" in sent
    assert "专有名词" in sent or "人名" in sent
    assert "只输出" in sent or "不要解释" in sent
    assert "Yahoo, the internet's 'OG', wants to win over Gen Z" in sent, "原题要原样送进去"


def test_it_reads_the_answer_shape_of_an_instruct_model(creds, monkeypatch):
    """指令模型的译文在 result.response,不在 result.translated_text。"""
    monkeypatch.setattr(translate, "_post", _Recorder("雅虎想赢得 Z 世代"))
    assert translate.translate_one("whatever", creds) == "雅虎想赢得 Z 世代"


def test_it_strips_the_wrapping_a_chat_model_likes_to_add(creds, monkeypatch):
    """指令模型偶尔还是会加引号或「翻译:」。**去壳,但不改字**。"""
    monkeypatch.setattr(translate, "_post", _Recorder('翻译:「雅虎想赢得 Z 世代」'))
    assert translate.translate_one("whatever", creds) == "雅虎想赢得 Z 世代"


def test_an_empty_answer_is_still_an_honest_failure(creds, monkeypatch):
    """空译文照实报错 —— 顺下去就是页面上一条没有标题的稿子。"""
    monkeypatch.setattr(translate, "_post", _Recorder("   "))
    with pytest.raises(RuntimeError):
        translate.translate_one("whatever", creds)


def test_an_answer_that_is_still_english_is_reported_not_shipped(creds, monkeypatch):
    """模型有时原样回英文。**那不是译文**,当失败处理,标题保持英文原样。"""
    monkeypatch.setattr(translate, "_post", _Recorder("Yahoo wants to win over Gen Z"))
    with pytest.raises(RuntimeError):
        translate.translate_one("Yahoo, the internet's 'OG', wants to win over Gen Z", creds)


def test_the_deprecated_qwen15_model_is_gone():
    """9-01:Cloudflare 对 qwen1.5-14b-chat-awq 全线回 410(已下架)——
    标题翻译和打分共用这一个模型名,它必须换成目录里现役的。"""
    assert "qwen1.5" not in translate.MODEL
    assert translate.MODEL.startswith("@cf/"), "仍然走同一个 Cloudflare 账号"


def test_a_thinking_block_is_stripped_before_unwrapping(creds, monkeypatch):
    """Qwen3 这类混合推理模型会先吐一段 <think>…</think> 再给答案。
    思考段不剥掉,取首行的去壳逻辑拿到的就是思考的第一句。"""
    recorder = _Recorder(reply="<think>标题涉及双关,\n考虑两种译法{草稿}</think>\n雅虎想赢得 Z 世代")
    monkeypatch.setattr(translate, "_post", recorder)
    assert translate.translate_one("t", creds) == "雅虎想赢得 Z 世代"


def test_an_exhausted_quota_stops_the_title_batch_too():
    """翻译那头同一条账:额度用完,剩下的标题这一轮不再尝试。"""
    calls = []

    def quota(text):
        calls.append(text)
        raise RuntimeError("Cloudflare 返回 429:daily free allocation of 10,000 neurons")

    rows = [
        {"title_en": "one", "title_zh": ""},
        {"title_en": "two", "title_zh": ""},
    ]
    done = translate.fill_titles(rows, translate_one=quota)
    assert done == 0
    assert calls == ["one"]
    assert "title_zh_error" not in rows[1]


def test_the_answer_is_found_in_either_reply_shape():
    """9-02 实测:Workers AI 对 qwen3 有时回 OpenAI 形状 ——
    译文在 choices[0].message.content,老的 result.response 是空的。
    两种形状都要认;两头都空(思考吃光预算时 content 是 null)如实返回空。"""
    assert translate.answer_of({"response": "老形状"}) == "老形状"
    assert translate.answer_of(
        {"choices": [{"message": {"content": "新形状"}}]}
    ) == "新形状"
    assert translate.answer_of(
        {"choices": [{"finish_reason": "length", "message": {"content": None}}]}
    ) is None


def test_translate_reads_the_openai_shaped_reply(creds, monkeypatch):
    class _OpenAIShape:
        def __call__(self, url, token, payload):
            return {"success": True, "result": {
                "choices": [{"message": {"content": "雅虎想赢得 Z 世代"}}],
            }}

    monkeypatch.setattr(translate, "_post", _OpenAIShape())
    assert translate.translate_one("t", creds) == "雅虎想赢得 Z 世代"
