"""Deterministic, non-executing extraction of archived vendor HTML pages."""
from html.parser import HTMLParser
from pathlib import Path
import re


class _Document(HTMLParser):
    OMIT = {"script", "style", "noscript", "svg", "canvas", "iframe", "form"}
    BREAK = {"p", "div", "section", "article", "main", "h1", "h2", "h3", "h4", "li", "tr", "br", "hr", "blockquote"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.omit_stack = []
        self.title_depth = 0
        self.title = []
        self.parts = []
        self.anchor = None
        self.table_cell = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in self.OMIT:
            self.omit_stack.append(tag)
            return
        if self.omit_stack:
            return
        if tag == "title":
            self.title_depth += 1
        if tag in {"header", "footer", "nav"} or any(word in (attrs.get("class", "") + " " + attrs.get("id", "")).lower()
                                                        for word in ("cookie", "consent", "breadcrumb", "navigation")):
            self.omit_stack.append(tag)
            return
        if tag in self.BREAK:
            self.parts.append("\n")
        if tag in {"td", "th"}:
            self.table_cell = True
        if tag == "a":
            self.anchor = (attrs.get("href", ""), [])

    def handle_endtag(self, tag):
        for index in range(len(self.omit_stack) - 1, -1, -1):
            if self.omit_stack[index] == tag:
                del self.omit_stack[index:]
                return
        if self.omit_stack:
            return
        if tag == "title" and self.title_depth:
            self.title_depth -= 1
        if tag in {"td", "th"} and self.table_cell:
            self.parts.append(" | ")
            self.table_cell = False
        if tag == "a" and self.anchor is not None:
            href, label = self.anchor
            text = "".join(label).strip()
            if text and href and not href.startswith(("#", "javascript:")):
                self.parts.append(" [link: " + text + " — " + href[:1000] + "] ")
            self.anchor = None
        if tag in self.BREAK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.omit_stack:
            return
        if self.title_depth:
            self.title.append(data)
        text = re.sub(r"\s+", " ", data).strip()
        if text:
            self.parts.append(text + " ")
            if self.anchor is not None:
                self.anchor[1].append(text)


def extract(path: Path, limit: int = 5_000_000):
    raw = path.read_bytes()
    try:
        source = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        source = raw.decode("windows-1252", errors="replace")
    parser = _Document()
    parser.feed(source)
    text = re.sub(r" *\n *", "\n", "".join(parser.parts))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    truncated = len(text) > limit
    return text[:limit], {"title": " ".join("".join(parser.title).split())[:500],
                          "method": "stdlib_html_semantic_v1", "characters": len(text), "truncated": truncated}
