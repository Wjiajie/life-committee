"""单个章节的解析：判定章节类别，抽取文章头（作者、日期、专题、出处）和文内出处线索。

支持三种文章头格式：
- A：标题 / By 作者（年份）/ 主题：…
- B：标题 / 作者（年份）/ 专题：…
- C：标题 / 原发布于 站点，日期，作者[，作者…]（站点为指向原文的链接）
"""

import re

EDITORIAL_AUTHORS = {"参考答案编辑部", "参考答案", "编辑部"}
UNKNOWN_AUTHORS = {"未知", "未知的作者", "佚名"}
MIN_ARTICLE_CHARS = 300
HEADER_WINDOW = 8

_EDITORIAL_TITLE = re.compile(
    r"导读|扩展阅读|写在前面|卷首语|^前言$|版权信息|^目录|编者按|编辑部还.{0,2}[看读]了|本周还读了"
)
_VARIANT_PREFIX = re.compile(r"^(翻译对照版|翻译版|中英对照版|中文版|英文版|原文版)\s*[｜|]\s*")
_WHOLE_VARIANT_TITLES = {"中文版", "中英对照版", "英文版", "原文", "原文版", "翻译版", "翻译对照版"}

_PUBLISHED = re.compile(r"^原发布于\s*(\S+?)\s*[，,]\s*(.*)$")
_BY = re.compile(r"^[Bb]y(?:\s+|(?=[^\x00-\x7f]))(.+?)$")
_TOPIC = re.compile(r"^(?:专题|主题)\s*[:：]\s*(.+)$")
_PAREN_YEAR = re.compile(r"\s*[（(]\s*(\d{4})\s*年?\s*[）)]\s*$")
_DATE = re.compile(r"(\d{4})\s*年(?:\s*(\d{1,2})\s*月(?:\s*(\d{1,2})\s*日)?)?")
_SENTENCE_PUNCT = re.compile(r"[。！？!?：:；;“”\"《》]")

_CUE = re.compile(
    r"^(原文链接|原文地址|英文原文|原文标题|英文标题|原文出处|原文|英文|来源|出处|参考译文|译文|"
    r"演讲视频|视频链接|视频|播客|节目链接)\s*[:：]\s*(.*)$"
)
_URL_LINE = re.compile(r"^(https?://\S+)$")
BARE_LINK_LABEL = "链接"


def _parse_date(text: str) -> tuple[str | None, str | None]:
    match = _DATE.search(text)
    if not match:
        return None, None
    year, month, day = match.groups()
    if day:
        return year, f"{year}-{int(month):02d}-{int(day):02d}"
    if month:
        return year, f"{year}-{int(month):02d}"
    return year, year


MAX_AUTHOR_LINE = 80


def _looks_like_name(text: str) -> bool:
    return 0 < len(text) <= MAX_AUTHOR_LINE and not _SENTENCE_PUNCT.search(text)


def _strip_year(text: str) -> tuple[str, str | None]:
    match = _PAREN_YEAR.search(text)
    if match:
        return text[: match.start()].strip(), match.group(1)
    return text.strip(), None


def _variant_of(title: str) -> tuple[str | None, str | None]:
    """返回 (版本名, 基础标题)。整章标题就是版本名时基础标题为 None，由调用方用书名补上。"""
    if title in _WHOLE_VARIANT_TITLES:
        return title, None
    match = _VARIANT_PREFIX.match(title)
    if match:
        return match.group(1), title[match.end():].strip()
    return None, title


def parse_header(lines: list[str], links: list[dict]) -> dict:
    """从章节开头若干行解析文章头。"""
    header = {
        "title": lines[0] if lines else "",
        "authors_raw": None,
        "year": None,
        "date": None,
        "topic": None,
        "published_site": None,
        "published_url": None,
        "header_format": None,
    }
    window = lines[1:HEADER_WINDOW]
    for offset, line in enumerate(window, start=1):
        if header["topic"] is None and (m := _TOPIC.match(line)):
            header["topic"] = m.group(1).strip()
            if header["authors_raw"] is None and offset >= 2:
                candidate, year = _strip_year(lines[offset - 1])
                if candidate != header["title"] and _looks_like_name(candidate):
                    header.update(authors_raw=candidate, header_format="B")
                    header["year"] = header["year"] or year
            continue
        if header["authors_raw"] is not None:
            continue
        if m := _PUBLISHED.match(line):
            site, rest = m.group(1), m.group(2)
            parts = [p.strip() for p in re.split(r"[，,]", rest) if p.strip()]
            names = []
            for part in parts:
                year, date = _parse_date(part)
                if year and re.fullmatch(r"[\d\s年月日]+", part):
                    header["year"], header["date"] = year, date
                else:
                    names.append(part)
            names = [n for n in names if n not in UNKNOWN_AUTHORS]
            header.update(published_site=site, authors_raw="，".join(names) or None, header_format="C")
            on_line = [l for l in links if l["line"] == offset]
            if on_line:
                header["published_url"] = on_line[0]["href"]
            continue
        if m := _BY.match(line):
            name, year = _strip_year(m.group(1))
            header.update(authors_raw=None if name in UNKNOWN_AUTHORS else name, year=year, header_format="A")
            if year is None and offset + 1 < len(lines):
                y, d = _parse_date(lines[offset + 1])
                if y and len(lines[offset + 1]) <= 20:
                    header["year"], header["date"] = y, d
            continue
        if _PAREN_YEAR.search(line):
            name, year = _strip_year(line)
            if name != header["title"] and _looks_like_name(name):
                header.update(authors_raw=name, year=year, header_format="B")
    return header


def source_cues(lines: list[str], links: list[dict]) -> list[dict]:
    """文中明确标注出处的行（如「原文：…」「英文：… (virginia.edu)」）及其链接。"""
    cues = []
    for i, line in enumerate(lines):
        label, content = None, None
        if m := _CUE.match(line):
            label, content = m.group(1), m.group(2).strip()
            if not content and i + 1 < len(lines) and _URL_LINE.match(lines[i + 1]):
                content = lines[i + 1]
        elif _URL_LINE.match(line):
            label, content = BARE_LINK_LABEL, line
        if not content:
            continue
        hrefs = [l["href"] for l in links if l["line"] in (i, i + 1)]
        url_in_text = _URL_LINE.match(content)
        if url_in_text and url_in_text.group(1) not in hrefs:
            hrefs.insert(0, url_in_text.group(1))
        cues.append({"label": label, "text": content, "urls": hrefs, "line": i})
    return cues


def _issue_topic(book_label: str) -> str:
    """书名去掉「Vol.95」「参考周刊｜Vol.85」之类的期号前缀，剩下的是本期主题。"""
    return re.sub(r"^.*?Vol\.?\s*\d+\s*", "", book_label).strip()


def _norm(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", text).lower()


def classify(header: dict, char_count: int, book_label: str = "") -> str:
    """章节类别：front（封面、版权页等）/ editorial（导读、前言、扩展阅读等策展说明）/ article。

    编辑部署名的原创文章算 article；标题就是本期主题的编辑部章节视为导读。
    """
    title = header["title"]
    authors = header["authors_raw"]
    if char_count < MIN_ARTICLE_CHARS and not authors:
        return "front"
    if _EDITORIAL_TITLE.search(title):
        return "editorial"
    by_editors = bool(authors) and all(a.strip() in EDITORIAL_AUTHORS for a in re.split(r"[，,]", authors))
    topic = _issue_topic(book_label)
    if by_editors and topic and _norm(title) == _norm(topic):
        return "editorial"
    return "article"


def parse_chapter(chapter: dict, book_label: str = "") -> dict:
    """章节纯数据 → 解析结果。chapter 需含 lines、links。"""
    lines, links = chapter["lines"], chapter["links"]
    header = parse_header(lines, links)
    variant, base_title = _variant_of(header["title"])
    char_count = sum(len(l) for l in lines)
    return {
        **header,
        "kind": classify(header, char_count, book_label),
        "variant": variant,
        "base_title": base_title,
        "char_count": char_count,
        "cues": source_cues(lines, links),
    }
