"""文本处理:把 LLM 输出的 Markdown 精简为纯文本(去掉 *、#、` 等格式符号)。"""
from __future__ import annotations

import re

# 行内模式:成对符号包裹的强调/代码/链接,保留文字去掉符号
_INLINE = [
    (re.compile(r"!\[([^\]]*)\]\([^)]+\)"), r"\1"),      # 图片 ![alt](url)
    (re.compile(r"\[([^\]]+)\]\([^)]+\)"), r"\1"),        # 链接 [text](url)
    (re.compile(r"\*\*([^*]+)\*\*"), r"\1"),              # 加粗 **text**
    (re.compile(r"__([^_]+)__"), r"\1"),                  # 加粗 __text__
    (re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)"), r"\1"),   # 斜体 *text*
    (re.compile(r"(?<!_)_([^_\n]+)_(?!_)"), r"\1"),       # 斜体 _text_
    (re.compile(r"~~([^~]+)~~"), r"\1"),                  # 删除线 ~~text~~
    (re.compile(r"`([^`]+)`"), r"\1"),                    # 行内代码 `text`
]

# 行首模式:去掉标记、保留内容
_LINE = [
    re.compile(r"^#{1,6}\s+", re.M),              # 标题 #
    re.compile(r"^\s{0,3}>\s?", re.M),            # 引用 >
    re.compile(r"^\s*[-*+]\s+", re.M),            # 无序列表 - * +
    re.compile(r"^\s*\d+[.)]\s+", re.M),          # 有序列表 1.
    re.compile(r"^\s*([-*_])\1{2,}\s*$", re.M),   # 分割线 ---
]


def strip_markdown(text: str) -> str:
    if not text:
        return text
    for pattern, repl in _INLINE:
        text = pattern.sub(repl, text)
    for pattern in _LINE:
        text = pattern.sub("", text)
    return text
