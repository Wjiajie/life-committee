"""目录构建的公开接口：每个阶段读取上一阶段产物与策展数据，写出本阶段产物。"""

from pathlib import Path

from catalog.adapters import epub, store
from catalog.core import articles as articles_core
from catalog.core import assemble as assemble_core
from catalog.core import authors as authors_core
from catalog.core import render
from catalog.core import sources as sources_core

ROOT = Path(__file__).resolve().parent.parent
EPUB_DIR = ROOT / "datasets" / "参考答案"
WORK = ROOT / "data" / "work"
CURATED = ROOT / "data" / "curated"
OUT = ROOT / "data" / "catalog"


def extract(epub_dir: Path = EPUB_DIR) -> dict:
    """N1 + N2：读取 epub，切分文章，写出文章清单与片段正文。"""
    books, errors = epub.read_library(epub_dir)
    all_articles, editorials, front = [], [], []
    for book in books:
        a, e, f = articles_core.articles_from_book(book)
        all_articles.extend(a)
        editorials.extend(e)
        front.extend(f)
    articles, suspects = articles_core.dedupe_across_books(all_articles)

    store.clear_dir(OUT / "fragments", "*.md")
    for article in articles:
        store.write_text(OUT / "fragments" / f"{article['id']}.md", render.fragment_markdown(article))
    store.write_json(WORK / "articles_raw.json", [{k: v for k, v in a.items() if k != "text"} for a in articles])
    store.write_json(WORK / "editorials.json", editorials)
    store.write_json(WORK / "front_matter.json", front)
    store.write_json(WORK / "read_errors.json", errors)
    store.write_json(WORK / "duplicate_suspects.json", suspects)
    return {
        "books": len(books),
        "read_errors": len(errors),
        "article_chapters": len(all_articles),
        "articles": len(articles),
        "editorial_chapters": len(editorials),
        "front_chapters": len(front),
        "missing_author": sum(1 for a in articles if not a["authors_raw"]),
        "with_published_url": sum(1 for a in articles if a["published_url"]),
        "with_cue": sum(1 for a in articles if a["cues"]),
        "duplicate_suspects": len(suspects),
    }


def _curated_articles() -> tuple[list[dict], dict, list[str]]:
    articles = store.read_json(WORK / "articles_raw.json")
    overrides = store.read_json(CURATED / "article_overrides.json", default={})
    aliases = store.read_json(CURATED / "author_aliases.json", default={"authors": [], "raw_splits": {}})
    articles, problems = authors_core.apply_overrides(articles, overrides)
    return articles, aliases, problems


def names() -> dict:
    """N3 辅助：列出拆分后的全部作者名，标明哪些还没有别名条目。"""
    articles, aliases, problems = _curated_articles()
    listing = authors_core.distinct_names(articles, aliases)
    store.write_json(WORK / "author_names.json", listing)
    return {
        "names": len(listing),
        "uncurated": sum(1 for n in listing if not n["curated"]),
        "missing_author_articles": [a["id"] for a in articles if not a["authors_raw"] and not a["author_names"]],
        "problems": problems,
    }


def _load(only_file: str | None = None) -> tuple[list[dict], dict, list, dict, list[str]]:
    """读取并校验全部策展数据：返回 (文章, 作者条目, 调研文件, 重定向, 问题列表)。

    重定向：{"authors": 旧作者 id → 新 id 或 None, "articles": 被合并的文章 id → 保留的文章 id}。
    """
    articles, aliases, problems = _curated_articles()
    try:
        redirects = authors_core.former_ids(aliases)
        articles, entries = authors_core.attribute(articles, aliases)
    except ValueError as exc:
        return [], {}, [], {}, problems + [str(exc)]
    problems += [f"former_ids 中的旧 id {old} 仍被文章使用，不能重定向" for old in redirects if old in entries]
    files = store.read_json_dir(CURATED / "sources")
    if only_file:
        files = [(n, d) for n, d in files if n == Path(only_file).name]
        if not files:
            problems.append(f"找不到 {CURATED / 'sources' / Path(only_file).name}")
    merged = {old: a["id"] for a in articles for old in a.get("merged_ids", [])}
    problems += sources_core.validate_research(files, {a["id"] for a in articles}, set(entries), redirects, merged)
    return articles, entries, files, {"authors": redirects, "articles": merged}, problems


def validate(file: str | None = None) -> dict:
    """只读校验调研结果文件（不写任何产物），供调研子代理自检。"""
    _, _, files, _, problems = _load(file)
    counts = {n: {"articles": len(d.get("articles", [])), "authors": len(d.get("authors", []))} for n, d in files}
    return {"files": counts, "problems": problems}


def checks() -> dict:
    """汇总调研里的作者核对：更正项，以及确认归属但给出了不同（通常更完整）名字的项，供策展审核。"""
    articles, entries, files, redirects, problems = _load()
    by_id = {a["id"]: a for a in articles}
    corrected, renamed = [], []
    for name, data in files:
        for item in data.get("articles", []):
            check = item.get("author_check")
            article = by_id.get(item["article_id"])
            if not check or not article:
                continue
            current = [entries[i]["name_en"] or entries[i]["name"] for i in article["author_ids"]]
            row = {"file": name, "article_id": article["id"], "title": article["title"],
                   "labeled": article["authors_as_labeled"], "current": current,
                   "proposed": check.get("authors") or [], "evidence": check.get("evidence"),
                   "note": check.get("note")}
            if check.get("status") == "corrected":
                corrected.append(row)
            elif check.get("status") == "confirmed" and row["proposed"] and \
                    sorted(map(authors_core.name_key, row["proposed"])) != sorted(map(authors_core.name_key, current)):
                renamed.append(row)
    store.write_json(WORK / "author_checks.json", {"corrected": corrected, "confirmed_with_other_names": renamed})
    return {"corrected": len(corrected), "confirmed_with_other_names": len(renamed), "problems": problems}


def build() -> dict:
    """N4 + N6：叠加策展数据与调研结果，写出最终目录和待调研批次。策展数据有错时不写产物。"""
    articles, entries, research_files, redirects, problems = _load()
    if problems:
        store.write_json(WORK / "report.json", {"problems": problems})
        return {"problems": problems}

    research_articles, research_authors = sources_core.research_index(
        research_files, redirects["authors"], redirects["articles"])
    authors, out_articles, registry, report = assemble_core.assemble(
        articles, entries, research_articles, research_authors)
    sources_by_id = {r["id"]: r for r in registry}
    authors_by_id = {a["id"]: a for a in authors}

    store.write_json(OUT / "authors.json", authors)
    store.write_json(OUT / "articles.json", out_articles)
    store.write_json(OUT / "sources.json", registry)
    store.write_json(OUT / "editorials.json", store.read_json(WORK / "editorials.json"))
    store.write_csv(OUT / "authors.csv", render.AUTHOR_CSV_HEADER, render.author_csv_rows(authors))
    store.write_csv(OUT / "articles.csv", render.ARTICLE_CSV_HEADER,
                    render.article_csv_rows(out_articles, authors_by_id, sources_by_id))
    store.write_text(OUT / "authors.md", render.authors_markdown(authors))

    batches = assemble_core.research_plan(articles, entries, research_articles, research_authors)
    todo = WORK / "research_todo"
    store.clear_dir(todo, "*.json")
    done = {name for name, _ in research_files}
    for i, batch in enumerate(batches, start=1):
        name = f"todo-{i:02d}.json"
        store.write_json(todo / name, batch)
    report["research_files_done"] = sorted(done)
    report["research_batches_pending"] = len(batches)
    report["research_articles_pending"] = sum(len(b["articles"]) for b in batches)
    report["research_authors_pending"] = sum(len(b["authors"]) for b in batches)
    store.write_json(WORK / "report.json", report)
    return {k: (len(v) if isinstance(v, list) else v) for k, v in report.items()}
