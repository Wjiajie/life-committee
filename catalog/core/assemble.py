"""把文章、作者条目和出处汇总成最终目录，并列出还需要网络调研的对象。"""

from catalog.core import sources as src

NO_RESEARCH_AUTHORS = {"ouranswers-editors"}


def _article_sources(article: dict, research: dict) -> list[dict]:
    records = [{**r, "article_ids": [article["id"]]} for r in src.from_article_text(article)]
    entry = research.get(article["id"])
    if entry:
        records += [{**r, "article_ids": [article["id"]]} for r in entry["sources"]]
    return src.merge(records)


def assemble(articles: list[dict], entries: dict[str, dict], research_articles: dict, research_authors: dict):
    """返回 (作者列表, 文章列表, 出处登记表, 报告)。文章需已带 author_ids。"""
    out_articles, author_articles, author_records, all_records = [], {}, {}, []
    for article in articles:
        records = _article_sources(article, research_articles)
        all_records.extend(records)
        entry = research_articles.get(article["id"]) or {}
        out_articles.append({
            "id": article["id"],
            "title": article["title"],
            "author_ids": article["author_ids"],
            "authors_as_labeled": article["authors_as_labeled"],
            "author_note": article.get("author_note"),
            "author_evidence": article.get("author_evidence"),
            "author_check": entry.get("author_check"),
            "year": article["year"],
            "year_as_labeled": article.get("year_as_labeled"),
            "year_note": article.get("year_note"),
            "date": article["date"],
            "topic": article["topic"],
            "appears_in": article["appears_in"],
            "merged_ids": article.get("merged_ids", []),
            "variants": article["variants"],
            "char_count": article["char_count"],
            "fragment": f"fragments/{article['id']}.md",
            "source_ids": [r["id"] for r in records],
            "has_source_link": src.has_link(records),
            "research_status": entry.get("status"),
            "research_note": entry.get("note"),
        })
        for aid in article["author_ids"]:
            author_articles.setdefault(aid, []).append(out_articles[-1])
            author_records.setdefault(aid, []).extend(records)

    authors = []
    for aid, entry in entries.items():
        own = author_articles.get(aid, [])
        author_level = [{**r, "article_ids": []} for r in research_authors.get(aid, [])]
        all_records.extend(author_level)
        records = src.merge(author_records.get(aid, []) + author_level)
        records.sort(key=lambda r: (not r.get("article_ids"), r["type"], r.get("site") or "", r.get("title") or ""))
        authors.append({
            "id": aid,
            "name": entry["name"],
            "name_en": entry.get("name_en"),
            "kind": entry.get("kind", "unknown"),
            "aliases": sorted(set(entry.get("aliases", [])) | set(entry.get("observed", [])) - {entry["name"]}),
            "curated": not entry.get("uncurated", False),
            "article_count": len(own),
            "articles": [{"id": a["id"], "title": a["title"], "year": a["year"], "topic": a["topic"],
                          "books": [p["book"] for p in a["appears_in"]], "fragment": a["fragment"],
                          "source_ids": a["source_ids"]} for a in own],
            "sources": records,
        })
    authors.sort(key=lambda a: (-a["article_count"], (a["name_en"] or a["name"]).casefold()))

    report = {
        "authors": len(authors),
        "articles": len(out_articles),
        "articles_without_author": [a["id"] for a in out_articles if not a["author_ids"]],
        "articles_without_link": [a["id"] for a in out_articles if not a["has_source_link"]],
        "authors_without_sources": [a["id"] for a in authors if not a["sources"]],
        "authors_with_hash_id": [a["id"] for a in authors if a["id"].startswith("a-")],
        "author_checks_corrected": [
            {"article_id": a["id"], **a["author_check"]} for a in out_articles
            if a["author_check"] and a["author_check"].get("status") == "corrected"],
    }
    registry = sorted(src.merge(all_records, drop_redundant_sites=False), key=lambda r: r["id"])
    return authors, out_articles, registry, report


def research_plan(articles: list[dict], entries: dict[str, dict], research_articles: dict,
                  research_authors: dict, max_articles: int = 20, max_authors: int = 14) -> list[dict]:
    """待调研批次：同一作者的任务放在同一批，每批文章数和作者数有上限。"""
    pending_by_author: dict[str, list[dict]] = {}
    for article in articles:
        if article["id"] in research_articles:
            continue
        records = src.from_article_text(article)
        if src.has_link(records) and not article.get("verify") and article["author_ids"]:
            continue
        owner = article["author_ids"][0] if article["author_ids"] else "_unknown"
        pending_by_author.setdefault(owner, []).append({
            "article_id": article["id"],
            "title": article["title"],
            "authors": [{"id": a, "name": entries[a]["name"], "name_en": entries[a].get("name_en")}
                        for a in article["author_ids"]],
            "authors_as_labeled": article["authors_as_labeled"],
            "author_note": article.get("author_note"),
            "verify_author": bool(article.get("verify")),
            "year": article["year"],
            "topic": article["topic"],
            "books": [p["book"] for p in article["appears_in"]],
            "known_sources": records,
            "reference_links": article.get("reference_links", [])[:8],
            "excerpt": article.get("excerpt", ""),
        })

    authors_todo = {aid for aid in entries if aid not in research_authors and aid not in NO_RESEARCH_AUTHORS}
    order = sorted(set(pending_by_author) | authors_todo)
    batches, current = [], {"articles": [], "authors": []}
    for aid in order:
        tasks = pending_by_author.get(aid, [])
        if current["articles"] and (len(current["articles"]) + len(tasks) > max_articles
                                    or len(current["authors"]) >= max_authors):
            batches.append(current)
            current = {"articles": [], "authors": []}
        current["articles"].extend(tasks)
        if aid in authors_todo:
            entry = entries[aid]
            current["authors"].append({
                "author_id": aid, "name": entry["name"], "name_en": entry.get("name_en"),
                "kind": entry.get("kind", "unknown"), "observed_names": entry.get("observed", []),
                "article_titles": [a["title"] for a in articles if aid in a["author_ids"]][:8],
            })
    if current["articles"] or current["authors"]:
        batches.append(current)
    return batches
