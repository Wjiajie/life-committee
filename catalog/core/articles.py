"""把书的章节组合成文章：同书内合并译文/对照等版本，跨书按「标题 + 作者」去重。"""

import difflib
import hashlib
import re

from catalog.core.chapters import parse_chapter

# 选主版本（片段正文来源）的优先级：中文译文优先，其次原章节，最后是对照版。
_VARIANT_RANK = {"翻译版": 0, "中文版": 0, None: 1, "原文": 2, "原文版": 2, "英文版": 2, "翻译对照版": 3, "中英对照版": 3}
NEAR_DUPLICATE_RATIO = 0.7
EXCERPT_CHARS = 900


def book_id(file_name: str) -> str:
    match = re.search(r"Vol\.?\s*(\d+)", file_name)
    if match:
        return f"vol{int(match.group(1)):04d}"
    return "book-" + hashlib.sha1(file_name.encode("utf-8")).hexdigest()[:6]


def book_label(file_name: str) -> str:
    """书名（去掉扩展名、下载序号和多余的空白、加号）。"""
    name = re.sub(r"\.epub$", "", file_name)
    name = re.sub(r"\s*\(\d+\)\s*$", "", name).replace("+", " ")
    return re.sub(r"\s+", " ", name).strip()


def normalize_title(title: str) -> str:
    return re.sub(r"[\s\W_]+", "", title).lower()


def _strip_author_prefix(title: str, authors_raw: str | None) -> str:
    """「保罗·格雷厄姆：如何独立思考」→「如何独立思考」，仅当前缀与作者名互相包含时。"""
    match = re.match(r"^(.{1,30}?)[：:]\s*(.+)$", title)
    if not match or not authors_raw:
        return title
    prefix, a = normalize_title(match.group(1)), normalize_title(authors_raw)
    if prefix and a and (prefix in a or a in prefix):
        return match.group(2)
    return title


def dedupe_key(title: str, authors_raw: str | None) -> str:
    return normalize_title(_strip_author_prefix(title, authors_raw)) + "|" + normalize_title(authors_raw or "")


def _merge_group(chapters: list[dict]) -> dict:
    """同一篇文章的多个版本章节 → 一篇文章；字段取第一个非空值。"""
    ordered = sorted(chapters, key=lambda c: (_VARIANT_RANK.get(c["parsed"]["variant"], 1), c["index"]))
    primary = ordered[0]
    merged = {}
    for field in ("authors_raw", "year", "date", "topic", "published_site", "published_url", "header_format"):
        merged[field] = next((c["parsed"][field] for c in ordered if c["parsed"][field]), None)
    cues, seen = [], set()
    for c in ordered:
        for cue in c["parsed"]["cues"]:
            key = (cue["text"], tuple(cue["urls"]))
            if key not in seen:
                seen.add(key)
                cues.append(cue)
    return {"primary": primary, "chapters": sorted(chapters, key=lambda c: c["index"]), "fields": merged, "cues": cues}


def _reference_links(chapters: list[dict], exclude: set[str]) -> list[dict]:
    refs, seen = [], set(exclude)
    for c in chapters:
        for link in c["links"]:
            if link["href"] not in seen:
                seen.add(link["href"])
                refs.append({"href": link["href"], "text": link["text"]})
    return refs


def articles_from_book(book: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """一本书 → (文章, 编辑部章节, 其他非文章章节)。文章尚未跨书去重。"""
    bid, label = book_id(book["file"]), book_label(book["file"])
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    editorials, front = [], []
    for chapter in book["chapters"]:
        parsed = parse_chapter(chapter, label)
        item = {**chapter, "parsed": parsed}
        summary = {"book_id": bid, "book": label, "chapter": chapter["href"], "index": chapter["index"],
                   "title": parsed["title"], "char_count": parsed["char_count"]}
        if parsed["kind"] == "front":
            front.append(summary)
            continue
        if parsed["kind"] == "editorial":
            editorials.append({**summary, "authors_raw": parsed["authors_raw"],
                               "links": [{"href": l["href"], "text": l["text"]} for l in chapter["links"]]})
            continue
        base = parsed["base_title"] or label
        key = normalize_title(base)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(item)

    articles = []
    for key in order:
        group = _merge_group(groups[key])
        primary, fields = group["primary"], group["fields"]
        title = primary["parsed"]["base_title"] or label
        cue_urls = {u for cue in group["cues"] for u in cue["urls"]}
        if fields["published_url"]:
            cue_urls.add(fields["published_url"])
        articles.append({
            "id": f"{bid}-c{primary['index']:02d}",
            "title": title,
            **fields,
            "cues": group["cues"],
            "reference_links": _reference_links(group["chapters"], cue_urls),
            "variants": [c["parsed"]["variant"] or "原章节" for c in group["chapters"]],
            "char_count": primary["parsed"]["char_count"],
            "excerpt": " / ".join(primary["lines"][1:14])[:EXCERPT_CHARS],
            "text": primary["lines"],
            "appears_in": [{"book_id": bid, "book": label, "chapters": [c["href"] for c in group["chapters"]]}],
        })
    return articles, editorials, front


def dedupe_across_books(articles: list[dict]) -> tuple[list[dict], list[dict]]:
    """按「去作者前缀的标题 + 作者」精确去重，合并出现位置；返回 (去重后文章, 疑似重复对)。"""
    by_key: dict[str, dict] = {}
    result = []
    for article in articles:
        key = dedupe_key(article["title"], article["authors_raw"])
        if key in by_key:
            kept = by_key[key]
            kept["appears_in"].extend(article["appears_in"])
            for field in ("authors_raw", "year", "date", "topic", "published_site", "published_url"):
                kept[field] = kept[field] or article[field]
            known = {(c["text"], tuple(c["urls"])) for c in kept["cues"]}
            kept["cues"].extend(c for c in article["cues"] if (c["text"], tuple(c["urls"])) not in known)
            continue
        by_key[key] = article
        result.append(article)

    suspects = []
    keys = [(a, normalize_title(_strip_author_prefix(a["title"], a["authors_raw"]))) for a in result]
    for i, (a, ka) in enumerate(keys):
        for b, kb in keys[i + 1:]:
            same_author = normalize_title(a["authors_raw"] or "") == normalize_title(b["authors_raw"] or "")
            either_missing = not a["authors_raw"] or not b["authors_raw"]
            if ka != kb and not (same_author or either_missing):
                continue
            ratio = difflib.SequenceMatcher(None, ka, kb).ratio()
            if ka == kb or ratio >= NEAR_DUPLICATE_RATIO:
                suspects.append({"a": a["id"], "b": b["id"], "title_a": a["title"], "title_b": b["title"],
                                 "authors_a": a["authors_raw"], "authors_b": b["authors_raw"],
                                 "ratio": round(ratio, 3)})
    return result, suspects
