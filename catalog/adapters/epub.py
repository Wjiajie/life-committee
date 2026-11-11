"""读取 epub 文件，按 spine 顺序产出章节的纯文本行和外部链接。"""

import hashlib
import posixpath
import re
import zipfile
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

_BLOCK_TAGS = {
    "p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "br", "blockquote",
    "section", "tr", "figcaption", "pre", "hr", "dt", "dd", "title",
}
_SKIP_TAGS = {"script", "style", "head"}


class _ChapterParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.links: list[dict] = []
        self._buf: list[str] = []
        self._skip = 0
        self._link: dict | None = None

    def _flush(self):
        text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
        self._buf = []
        if text:
            self.lines.append(text)

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip += 1
            return
        if tag in _BLOCK_TAGS:
            self._flush()
        if tag == "a":
            href = dict(attrs).get("href") or ""
            if href.startswith(("http://", "https://")):
                self._link = {"href": href, "text": []}

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
            return
        if tag == "a" and self._link is not None:
            self.links.append({
                "href": self._link["href"],
                "text": re.sub(r"\s+", " ", "".join(self._link["text"])).strip(),
                "line": len(self.lines),
            })
            self._link = None
        if tag in _BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        if self._skip:
            return
        self._buf.append(data)
        if self._link is not None:
            self._link["text"].append(data)

    def close(self):
        super().close()
        self._flush()


def chapter_from_html(html: str) -> dict:
    """XHTML → {"lines": [...], "links": [{"href", "text", "line"}]}；line 为链接所在行的下标。"""
    parser = _ChapterParser()
    parser.feed(html)
    parser.close()
    return {"lines": parser.lines, "links": parser.links}


def _opf_path(z: zipfile.ZipFile) -> str:
    container = z.read("META-INF/container.xml").decode("utf-8", "replace")
    match = re.search(r'full-path="([^"]+)"', container)
    if not match:
        raise ValueError("container.xml 中没有 rootfile")
    return match.group(1)


def _attr(tag: str, name: str) -> str | None:
    match = re.search(rf'\b{name}="([^"]*)"', tag)
    return unescape(match.group(1)) if match else None


def read_book(path: Path) -> dict:
    """读取一本 epub。损坏文件抛出异常，由调用方记录。"""
    data = path.read_bytes()
    with zipfile.ZipFile(path) as z:
        opf_name = _opf_path(z)
        opf = z.read(opf_name).decode("utf-8", "replace")
        base = posixpath.dirname(opf_name)
        manifest = {}
        for tag in re.findall(r"<item\b[^>]*>", opf):
            item_id, href = _attr(tag, "id"), _attr(tag, "href")
            if item_id and href:
                manifest[item_id] = href
        chapters = []
        for tag in re.findall(r"<itemref\b[^>]*>", opf):
            href = manifest.get(_attr(tag, "idref") or "")
            if not href or not re.search(r"\.x?html?$", href, re.I):
                continue
            name = posixpath.normpath(posixpath.join(base, href))
            try:
                html = z.read(name).decode("utf-8", "replace")
            except KeyError:
                continue
            chapters.append({"index": len(chapters), "href": href, **chapter_from_html(html)})
    title = re.search(r"<dc:title[^>]*>([\s\S]*?)</dc:title>", opf)
    creators = re.findall(r"<dc:creator[^>]*>([\s\S]*?)</dc:creator>", opf)
    return {
        "file": path.name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "title": unescape(title.group(1)).strip() if title else path.stem,
        "creators": [unescape(c).strip() for c in creators],
        "chapters": chapters,
    }


def read_library(directory: Path) -> tuple[list[dict], list[dict]]:
    """读取目录下全部 epub。返回 (书列表, 错误列表)；字节完全相同的重复文件记为错误项而不重复读取。"""
    books, errors, seen = [], [], {}
    for path in sorted(directory.glob("*.epub")):
        try:
            book = read_book(path)
        except (zipfile.BadZipFile, KeyError, ValueError) as exc:
            errors.append({"file": path.name, "error": f"{type(exc).__name__}: {exc}"})
            continue
        if book["sha256"] in seen:
            errors.append({"file": path.name, "error": f"与 {seen[book['sha256']]} 字节完全相同，已跳过"})
            continue
        seen[book["sha256"]] = path.name
        books.append(book)
    return books, errors
