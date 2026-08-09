"""DeepSeek API 客户端(OpenAI 兼容端点,流式)。

- 翻译:其他语言 → 中文,默认关闭思维模式(更快更便宜)。
- 解释:词典+百科式中文释义;可选开启思维模式(深度解释)或联网搜索。
- 联网搜索走 Responses API 的 `web_search` 工具(2026-05 起官方支持);
  端点不支持时自动回退为普通解释并在结果里说明。
"""
from __future__ import annotations

from typing import Callable, Optional

from openai import OpenAI

BASE_URL = "https://api.deepseek.com"

SYSTEM_TRANSLATE = (
    "你是一个专业的翻译引擎。把用户给出的内容翻译成中文,直接输出译文,"
    "不要任何解释、引号或前后缀。若原文已是中文,保持原样输出。"
)
SYSTEM_EXPLAIN = (
    "你是用户阅读时的随身助手。用中文解释用户给出的内容:它表达的含义、"
    "适用的语境,若是词汇或术语请补充常见用法或例句。简洁清楚,不超过300字。"
    "直接输出解释,不要任何前后缀。"
)


class DeepSeekClient:
    def __init__(self, api_key: str, model: str = "deepseek-v4-flash"):
        self._client = OpenAI(api_key=api_key, base_url=BASE_URL)
        self.model = model

    def _thinking_body(self, enabled: bool) -> dict:
        return {"thinking": {"type": "enabled" if enabled else "disabled"}}

    def _stream_chat(
        self,
        system: str,
        text: str,
        thinking: bool,
        on_token: Callable[[str], None],
        stop: Optional[Callable[[], bool]],
    ) -> None:
        stream = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            stream=True,
            extra_body=self._thinking_body(thinking),
        )
        for chunk in stream:
            if stop and stop():
                break
            if not chunk.choices:
                continue
            delta = getattr(chunk.choices[0], "delta", None)
            content = getattr(delta, "content", None) if delta else None
            if content:
                on_token(content)

    def translate(
        self,
        text: str,
        thinking: bool = False,
        on_token: Optional[Callable[[str], None]] = None,
        stop: Optional[Callable[[], bool]] = None,
    ) -> None:
        self._stream_chat(SYSTEM_TRANSLATE, text, thinking, on_token or (lambda _t: None), stop)

    def explain(
        self,
        text: str,
        thinking: bool = False,
        web_search: bool = False,
        on_token: Optional[Callable[[str], None]] = None,
        stop: Optional[Callable[[], bool]] = None,
    ) -> None:
        tok = on_token or (lambda _t: None)
        if web_search:
            try:
                self._stream_responses_search(text, thinking, tok, stop)
                return
            except Exception as exc:  # 端点不支持时回退
                tok(f"\n[联网解释暂不可用: {exc}] 已退回普通解释。\n")
        self._stream_chat(SYSTEM_EXPLAIN, text, thinking, tok, stop)

    def _stream_responses_search(
        self,
        text: str,
        thinking: bool,
        on_token: Callable[[str], None],
        stop: Optional[Callable[[], bool]],
    ) -> None:
        stream = self._client.responses.create(
            model=self.model,
            tools=[{"type": "web_search"}],
            input=[
                {"role": "system", "content": SYSTEM_EXPLAIN},
                {"role": "user", "content": text},
            ],
            stream=True,
            extra_body=self._thinking_body(thinking),  # 深度解释与联网叠加
        )
        for event in stream:
            if stop and stop():
                break
            if getattr(event, "type", None) == "response.output_text.delta":
                delta = getattr(event, "delta", None)
                if delta:
                    on_token(delta)
