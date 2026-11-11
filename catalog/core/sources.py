"""信息源：从文内线索生成出处记录，校验并合并网络调研结果，按 URL 去重。

调研结果文件（data/curated/sources/*.json）结构：
{
  "articles": [{"article_id", "status": "found"|"not_found", "note",
                "sources": [来源记录...],
                "author_check": {"status": "confirmed"|"corrected"|"unknown", "authors": [...], "evidence", "note"}}],
  "authors":  [{"author_id", "note", "sources": [来源记录...]}]
}
来源记录：{"type", "title", "url", "site", "evidence", "confidence", "note"}
"""

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from catalog.core.chapters import BARE_LINK_LABEL

SOURCE_TYPES = {"article", "website", "book", "podcast", "video", "speech", "interview", "paper", "social"}
CONFIDENCE = {"high", "medium", "low"}
_EDITORIAL_SITES = {"www.notion.so", "notion.so", "ouranswers.notion.site"}
_TRACKING = re.compile(r"^(utm_|ref$|ref_src$|source$|s$|fbclid$|gclid$)")


def canonical_url(url: str) -> str:
    """去掉协议差异、www、末尾斜杠和追踪参数，用于判重。"""
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if not _TRACKING.match(k)])
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("", host, path, query, ""))[2:]


def site_of(url: str) -> str:
    return urlsplit(url).netloc.lower().removeprefix("www.")


def guess_type(url: str) -> str:
    host = site_of(url)
    if any(h in host for h in ("youtube.com", "youtu.be", "vimeo.com", "bilibili.com", "ted.com")):
        return "video"
    if any(h in host for h in ("podcast", "spotify.com", "happyscribe", "lexfridman.com")):
        return "podcast"
    if any(h in host for h in ("amazon.", "goodreads.com", "books.google", "gutenberg.org", "douban.com")):
        return "book"
    if host in ("x.com", "twitter.com"):
        return "social"
    if host.endswith(".pdf") or url.lower().endswith(".pdf") or "arxiv.org" in host:
        return "paper"
    return "article"


def source_id(record: dict) -> str:
    key = canonical_url(record["url"]) if record.get("url") else f"{record['type']}|{record.get('title') or ''}"
    return "s-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]


def from_article_text(article: dict) -> list[dict]:
    """原书里能直接读到的出处：「原发布于」链接、「原文/英文：」等线索行。"""
    records = []
    site = article.get("published_site")
    if article.get("published_url") and site in _EDITORIAL_SITES:
        url = article["published_url"]
        records.append({"type": "website", "title": "参考答案 Notion 原发页", "url": url, "site": site_of(url),
                        "origin": "in_text", "evidence": "原书「原发布于」行的链接", "confidence": "high",
                        "note": "编辑部原创内容首发于会员 Notion 页面，可能需要权限才能访问"})
    elif article.get("published_url"):
        url = article["published_url"]
        records.append({"type": guess_type(url), "title": None, "url": url, "site": site_of(url),
                        "origin": "in_text", "evidence": "原书「原发布于」行的链接", "confidence": "high", "note": None})
    elif site and site not in _EDITORIAL_SITES:
        records.append({"type": "website", "title": None, "url": None, "site": site, "origin": "in_text_domain",
                        "evidence": "原书「原发布于」行只给出站点", "confidence": "medium", "note": None})
    for cue in article.get("cues", []):
        if cue["label"] == BARE_LINK_LABEL:
            continue  # 正文里单独成行的链接多为嵌入视频或参考资料，只作调研线索
        title = None if cue["text"].startswith("http") else cue["text"]
        if cue["urls"]:
            for url in cue["urls"]:
                if site_of(url) in _EDITORIAL_SITES:
                    continue
                records.append({"type": guess_type(url), "title": title, "url": url, "site": site_of(url),
                                "origin": "in_text", "evidence": f"原书「{cue['label']}」行", "confidence": "high",
                                "note": None})
        elif title:
            records.append({"type": "article", "title": title, "url": None, "site": None, "origin": "in_text",
                            "evidence": f"原书「{cue['label']}」行（无链接）", "confidence": "medium", "note": None})
    return records


def has_link(records: list[dict]) -> bool:
    return any(r.get("url") for r in records)


def validate_record(record: dict, where: str) -> list[str]:
    problems = []
    if record.get("type") not in SOURCE_TYPES:
        problems.append(f"{where}: type「{record.get('type')}」不在 {sorted(SOURCE_TYPES)} 中")
    if record.get("confidence") not in CONFIDENCE:
        problems.append(f"{where}: confidence「{record.get('confidence')}」不在 {sorted(CONFIDENCE)} 中")
    url = record.get("url")
    if url is not None and not re.match(r"^https?://", url):
        problems.append(f"{where}: url 不是 http(s) 链接：{url}")
    if not url and not record.get("title"):
        problems.append(f"{where}: 没有 url 时必须有 title")
    if not record.get("evidence"):
        problems.append(f"{where}: 缺少 evidence")
    return problems


def validate_research(files: list[tuple[str, dict]], article_ids: set[str], author_ids: set[str],
                      redirects: dict[str, str] | None = None,
                      merged_articles: dict[str, str] | None = None) -> list[str]:
    """merged_articles：被 same_as 合并掉的文章 id → 保留的文章 id，调研结果随之改挂。"""
    redirects = redirects or {}
    merged_articles = merged_articles or {}
    problems = []
    for name, data in files:
        for i, item in enumerate(data.get("articles", [])):
            where = f"{name} articles[{i}]"
            if merged_articles.get(item.get("article_id"), item.get("article_id")) not in article_ids:
                problems.append(f"{where}: 未知文章 {item.get('article_id')}")
            if item.get("status") not in ("found", "not_found"):
                problems.append(f"{where}: status 应为 found / not_found")
            for j, rec in enumerate(item.get("sources", [])):
                problems += validate_record(rec, f"{where}.sources[{j}]")
            check = item.get("author_check")
            if check and check.get("status") not in ("confirmed", "corrected", "unknown"):
                problems.append(f"{where}: author_check.status 无效")
        for i, item in enumerate(data.get("authors", [])):
            where = f"{name} authors[{i}]"
            if item.get("author_id") in redirects and redirects[item.get("author_id")] is None:
                continue
            aid = redirects.get(item.get("author_id"), item.get("author_id"))
            if aid not in author_ids:
                problems.append(f"{where}: 未知作者 {item.get('author_id')}")
            for j, rec in enumerate(item.get("sources", [])):
                problems += validate_record(rec, f"{where}.sources[{j}]")
    return problems


def research_index(files: list[tuple[str, dict]], redirects: dict[str, str] | None = None,
                   merged_articles: dict[str, str] | None = None) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    """调研结果 → (文章id → 条目, 作者id → 来源列表)。同一对象出现多次时追加；旧 id 按重定向改挂。"""
    redirects = redirects or {}
    merged_articles = merged_articles or {}
    by_article: dict[str, dict] = {}
    by_author: dict[str, list[dict]] = {}
    for _, data in files:
        for item in data.get("articles", []):
            aid = merged_articles.get(item["article_id"], item["article_id"])
            entry = by_article.setdefault(aid, {"sources": [], "status": None, "note": None, "author_check": None})
            entry["sources"] += [{**r, "origin": "web_search"} for r in item.get("sources", [])]
            entry["status"] = "found" if "found" in (entry["status"], item.get("status")) else item.get("status")
            entry["note"] = item.get("note") or entry["note"]
            entry["author_check"] = item.get("author_check") or entry["author_check"]
        for item in data.get("authors", []):
            aid = redirects.get(item["author_id"], item["author_id"])
            if aid is None:
                continue
            by_author.setdefault(aid, []).extend(
                {**r, "origin": "web_search"} for r in item.get("sources", []))
    return by_article, by_author


_ORIGIN_RANK = {"in_text": 0, "web_search": 1, "in_text_domain": 2}


def merge(records: list[dict], drop_redundant_sites: bool = True) -> list[dict]:
    """按 source_id 去重，保留证据最强的一条，并合并 article_ids。

    drop_redundant_sites 为真时，只有站点、没有链接的记录在同站点已有链接时丢弃。
    """
    merged: dict[str, dict] = {}
    for rec in records:
        sid = source_id(rec)
        rec = {**rec, "id": sid}
        if sid not in merged:
            merged[sid] = rec
            continue
        kept = merged[sid]
        ids = sorted(set(kept.get("article_ids", [])) | set(rec.get("article_ids", [])))
        if _ORIGIN_RANK.get(rec["origin"], 9) < _ORIGIN_RANK.get(kept["origin"], 9):
            kept = merged[sid] = rec
        kept["title"] = kept.get("title") or rec.get("title")
        if ids:
            kept["article_ids"] = ids
    if not drop_redundant_sites:
        return list(merged.values())
    linked_sites = {r["site"] for r in merged.values() if r.get("url")}
    return [r for r in merged.values() if r.get("url") or r["origin"] != "in_text_domain"
            or r.get("site") not in linked_sites]
