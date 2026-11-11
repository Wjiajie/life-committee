# 节点 N5 规格：文章出处与作者信息源调研

仓库根目录：`C:\Users\jiaji\Documents\github-project\life-committee`

## 输入

第一轮使用快照 `data/work/research_round1/todo-XX.json`（`data/work/research_todo/` 会在每次 `build` 时重新生成编号，调研期间不要读它），结构：

- `articles[]`：需要找出处的文章。字段：`article_id`、`title`（中文译名，原文多为英文）、`authors`（已归属的作者 id 与中英文名）、`authors_as_labeled`（原书标注）、`author_note`、`verify_author`、`year`、`topic`、`books`、`known_sources`（原书里已有的出处线索）、`reference_links`（正文里出现过的链接，可作线索，但不一定是出处）、`excerpt`（开头约 900 字）。
- `authors[]`：需要补充作者级信息源的作者。字段：`author_id`、`name`、`name_en`、`kind`、`observed_names`、`article_titles`。

## 任务

1. **文章出处**：为每篇文章找出原文出处，优先级如下：
   1. 原文网页（作者博客、Newsletter、期刊、媒体文章页）；
   2. 演讲、访谈、播客、视频的官方页面或文字稿；
   3. 书籍节选：给出书名和出版信息页（出版社、Goodreads、豆瓣、Amazon 均可）；
   4. 中文原创内容（如国内创业者访谈）：原始报道或节目页面。
   
   用 WebSearch 搜英文原题（根据中文标题、作者和摘录推断）或关键句，必要时用 WebFetch 打开页面核对标题和作者。
2. **作者核对**：`verify_author` 为 true、作者为空、只有单名或化名（如 Ben、Tim、Alex、Mario、Camille、Sascha、julian），或者你找到的原文作者与归属不一致时，填写 `author_check`。
3. **作者信息源**：为每位作者给出 1–3 条作者级信息源。优先给个人网站、博客或 Newsletter；其次给 1–2 本代表作（书名附中文译名，如有）；找不到时可用维基百科。机构和刊物给官网。

## 输出

写入 `data/curated/sources/batch-XX.json`，XX 与输入文件编号相同。只写这一个文件，不要修改仓库里的其他任何文件。

```json
{
  "articles": [
    {
      "article_id": "vol0003-c06",
      "status": "found",
      "note": "英文原题 How to Think for Yourself",
      "sources": [
        {
          "type": "article",
          "title": "How to Think for Yourself",
          "url": "http://paulgraham.com/think.html",
          "site": "paulgraham.com",
          "evidence": "http://paulgraham.com/think.html",
          "confidence": "high",
          "note": null
        }
      ],
      "author_check": {"status": "confirmed", "authors": ["Paul Graham"], "evidence": "http://paulgraham.com/think.html", "note": null}
    }
  ],
  "authors": [
    {
      "author_id": "paul-graham",
      "note": null,
      "sources": [
        {"type": "website", "title": "Paul Graham 个人网站", "url": "http://paulgraham.com/", "site": "paulgraham.com", "evidence": "http://paulgraham.com/", "confidence": "high", "note": null},
        {"type": "book", "title": "Hackers & Painters（《黑客与画家》，O'Reilly，2004）", "url": null, "site": null, "evidence": "<你在搜索结果中看到该书信息的网址>", "confidence": "medium", "note": "示例：找不到可靠的书籍页面时 url 可为 null"}
      ]
    }
  ]
}
```

字段规则（会被 `python -m catalog validate` 机械校验）：

- `status`：`found` 或 `not_found`。没找到时 `sources` 可为空，`note` 写明搜过什么。
- `type`：`article` / `website` / `book` / `podcast` / `video` / `speech` / `interview` / `paper` / `social` 之一。
- `url`：必须是 http(s) 链接；书籍等确实没有链接时可为 null，此时 `title` 必填。
- `evidence`：你确认这条信息的依据，填你实际打开或在搜索结果中看到的网址；不能留空。
- `confidence`：`high`（打开页面核对了标题与作者）/ `medium`（搜索结果高度吻合但未打开核对）/ `low`（合理推断）。尽量不要提交 low；提交时在 `note` 说明理由。
- `author_check.status`：`confirmed`（确认现有归属）/ `corrected`（归属有误，`authors` 填正确作者的英文全名）/ `unknown`。
- 每个输入里的 `article_id` 和 `author_id` 都要在输出中出现恰好一次。

## 纪律

- **绝不编造链接**：只写你在搜索结果或打开的页面中实际见到的 URL。宁可 `not_found`，也不要猜。
- 不要修改 `data/curated/sources/` 以外的文件，不要运行 `python -m catalog build` 或 `extract`（会覆盖共享产物）。
- 完成后在仓库根目录运行：`uv run python -m catalog validate batch-XX.json`（PowerShell 下先设 `$env:PYTHONIOENCODING='utf-8'`），直到输出 `"problems": []`。

## 返回

返回一段简短报告：输出文件路径、文章 found / not_found 数、作者条目数、`author_check` 中 corrected 的条目（文章 id、原作者、更正后作者、依据）、validate 的实际输出。
