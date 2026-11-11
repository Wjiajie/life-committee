"""把目录数据渲染成文本（片段 Markdown、作者表 Markdown、CSV 行）。"""

AUTHOR_CSV_HEADER = ["作者", "英文名", "类型", "文章数", "相关文章", "相关信息源"]
ARTICLE_CSV_HEADER = ["文章id", "文章", "作者", "原书标注作者", "年份", "专题", "出现位置", "出处链接"]
_KIND = {"person": "个人", "organization": "机构", "publication": "刊物/博客", "unknown": "未确认"}


def fragment_markdown(article: dict) -> str:
    places = "；".join(f"{p['book']}（{', '.join(p['chapters'])}）" for p in article["appears_in"])
    meta = [
        f"# {article['title']}",
        "",
        f"- 文章 id：{article['id']}",
        f"- 作者（原书标注）：{article['authors_raw'] or '未标注'}",
        f"- 年份：{article['year'] or '未标注'}",
        f"- 专题：{article['topic'] or '未标注'}",
        f"- 出现位置：{places}",
    ]
    if article.get("published_url"):
        meta.append(f"- 原发布于：{article['published_url']}")
    return "\n".join(meta) + "\n\n---\n\n" + "\n\n".join(article["text"]) + "\n"


def _display_name(author: dict) -> str:
    if author["name_en"] and author["name_en"] != author["name"]:
        return f"{author['name']}（{author['name_en']}）"
    return author["name"]


def _source_label(record: dict) -> str:
    label = record.get("title") or record.get("site") or record["type"]
    return f"{label} <{record['url']}>" if record.get("url") else label


def author_csv_rows(authors: list[dict]) -> list[list]:
    rows = []
    for a in authors:
        articles = "；".join(f"{x['title']}（{x['year']}）" if x["year"] else x["title"] for x in a["articles"])
        sources = "；".join(_source_label(r) for r in a["sources"])
        rows.append([a["name"], a["name_en"] or "", _KIND.get(a["kind"], a["kind"]), a["article_count"],
                     articles, sources])
    return rows


def article_csv_rows(articles: list[dict], authors_by_id: dict[str, dict], sources_by_id: dict[str, dict]) -> list[list]:
    rows = []
    for x in articles:
        names = "、".join(authors_by_id[i]["name"] for i in x["author_ids"])
        books = "；".join(p["book"] for p in x["appears_in"])
        links = "；".join(sources_by_id[s]["url"] for s in x["source_ids"] if sources_by_id[s].get("url"))
        rows.append([x["id"], x["title"], names, x["authors_as_labeled"] or "", x["year"] or "", x["topic"] or "",
                     books, links])
    return rows


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def authors_markdown(authors: list[dict]) -> str:
    lines = [
        "# 参考答案：作者目录",
        "",
        f"共 {len(authors)} 位作者、{sum(a['article_count'] for a in authors)} 篇署名文章（多作者文章在每位作者名下各计一次）。",
        "由 `python -m catalog build` 生成，请勿手工编辑；更正写入 `data/curated/`。",
        "",
        "| 作者 | 相关文章 | 相关信息源 |",
        "|------|----------|------------|",
    ]
    for a in authors:
        arts = "<br>".join(_cell(f"{x['title']}（{x['year']}）" if x["year"] else x["title"]) for x in a["articles"])
        srcs = []
        for r in a["sources"]:
            label = _cell(r.get("title") or r.get("site") or r["type"])
            srcs.append(f"[{label}]({r['url']})" if r.get("url") else label)
        lines.append(f"| {_cell(_display_name(a))} | {arts} | {'<br>'.join(srcs) or '（未找到）'} |")
    return "\n".join(lines) + "\n"
