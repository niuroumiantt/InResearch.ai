"""Deterministic, non-executing extraction of archived vendor HTML pages."""
from html.parser import HTMLParser
from pathlib import Path
import re


class _Document(HTMLParser):
    OMIT = {"script", "style", "noscript", "svg", "canvas", "iframe", "button", "textarea", "select"}
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
        # HTMLParser uses None for valueless attributes such as <div class>.
        attrs = {key: value or "" for key, value in attrs}
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


def srcdoc(path: Path, index: int, limit: int = 2_000_000):
    """Read one archived inline iframe, without scripts or external requests.

    The locator is one-based in document order, counting only iframe[srcdoc].
    Raw source SHA and the selected extracted context are frozen by object_review.
    """
    class Frames(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.frames = []
        def handle_starttag(self, tag, attrs):
            if tag == 'iframe':
                attrs = dict(attrs)
                if 'srcdoc' in attrs:
                    self.frames.append(attrs['srcdoc'] or '')
        handle_startendtag = handle_starttag
    if path.suffix.lower() not in {'.html','.htm'}:
        raise ValueError('html_srcdoc_source_required')
    raw=path.read_bytes()
    if len(raw)>20_000_000:
        raise ValueError('html_srcdoc_source_too_large')
    frames=Frames();frames.feed(raw.decode('utf-8-sig'))
    if type(index) is not int or not 1 <= index <= len(frames.frames):
        raise ValueError('html_srcdoc_locator_required')
    content=frames.frames[index-1]
    if len(content)>limit:
        raise ValueError('html_srcdoc_context_too_large')
    parser=_Document();parser.feed(content)
    text=re.sub(r' *\n *','\n',''.join(parser.parts))
    text=re.sub(r'\n{3,}','\n\n',text).strip()
    if not text or len(text)>limit:
        raise ValueError('html_srcdoc_empty_or_truncated')
    return text
