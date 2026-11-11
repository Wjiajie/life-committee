# 节点图：参考答案 epub → 作者目录

## 立项

| 项 | 内容 |
|----|------|
| 任务 | 把 `datasets/参考答案/` 下每本 epub 切分成文章片段，识别每篇文章的作者，按作者汇总，并为每位作者整理「相关信息源」（文章出处的网站、书籍、播客、演讲等） |
| 交付物 | `data/catalog/authors.json`（主产物，供网页使用）、`data/catalog/articles.json`、`data/catalog/authors.csv`、`data/catalog/authors.md`（人读预览）、`data/catalog/fragments/<文章id>.md`（文章片段正文） |
| 验收标准 | 见文末「收尾清单」 |
| 起始材料 | 134 个 epub 文件（1 个 0 字节损坏，2 组重复下载） |
| 变更范围 | 新建 `catalog/`、`tests/`、`data/`、`pyproject.toml`、`ARCHITECTURE.md`、本目录；不修改 `datasets/` |
| 执行上限 | 网络搜索按批次进行，每批约 25 篇文章；单节点最多重试 3 次 |

## 基线（普查结果，2026-11-10）

三种文章头格式：

- A（Vol.0001–0024 前后）：`标题` / `By 作者（年份）` / `主题：…` / `推荐语`
- B（Vol.0025–0094、合集）：`标题` / `作者（年份）` / `专题：…`
- C（Vol.95–130）：`标题` / `原发布于 域名，日期，作者`

需要特殊处理的章节：导读、写在前面、卷首语、扩展阅读（编辑部内容，不计入作者）；`翻译版｜`、`翻译对照版｜`、`中英对照版`（同一文章的不同版本，合并为一篇）；合集与重复下载里的重复文章（去重，保留全部出现位置）。

粗略统计：约 650 个文章章节，约 610 个不重复标题，约 360 种作者原始写法；约 230 篇文内有外链，约 150 篇只有出处域名，约 300 篇没有任何出处线索。

## 节点

| 节点 | 类型 | 输入 | 产物 | 检查 |
|------|------|------|------|------|
| N1 读取 epub | 代码 | `datasets/参考答案/*.epub` | `data/work/chapters.json` | 133 本可读书全部解析；损坏文件进入错误清单而非静默跳过 |
| N2 切分文章 | 代码 | N1 | `data/work/articles_raw.json`、`data/catalog/fragments/` | 每章归类为 文章/编辑部/版本副本；文章头字段（作者、年份、专题、出处域名）解析；单元测试覆盖三种格式与边界 |
| N3 作者补全与别名 | 判断 | N2 中缺作者的文章、作者名列表 | `data/curated/article_overrides.json`、`data/curated/author_aliases.json` | 每条补全附依据（原文摘录或网址）；代码校验所有引用的文章 id 存在 |
| N4 汇总作者 | 代码 | N2 + N3 | `data/work/authors_draft.json`、`data/work/source_todo.json` | 每篇文章恰好归属到至少一位作者；列出缺出处的文章 |
| N5 出处调研 | 判断（并行子代理，按批） | N4 的待办批次 | `data/curated/sources/batch-XX.json` | 每条出处带 URL 或书籍信息、证据链接、置信度；代码校验结构 |
| N6 合并导出 | 代码 | N4 + N5 | `data/catalog/*` | JSON 结构校验；所有文章都有作者；统计未找到出处的条目并明示 |
| N7 抽样核对 | 判断 | N6 + 原 epub | `docs/runs/epub-author-catalog/checks.md` | 随机抽 20 篇文章对照原书核对作者与出处 |

边：N1→N2→N3→N4→N5→N6→N7；N3 与 N5 的结果作为人工可改的「策展数据」存放在 `data/curated/`，代码每次都从原始 epub 重新计算，再叠加策展数据。

代码节点：N1、N2、N4、N6（以及 N3、N5 产物的结构校验）。

## 输出结构（`authors.json`）

```json
[
  {
    "id": "paul-graham",
    "name": "保罗·格雷厄姆",
    "name_en": "Paul Graham",
    "aliases": ["保罗·格雷厄姆", "Paul Graham"],
    "article_count": 3,
    "articles": [
      {
        "id": "vol0003-05",
        "title": "保罗·格雷厄姆：如何独立思考",
        "year": "2020",
        "topic": "思维",
        "appears_in": [{"book": "Vol.0003 …", "chapter": "chapter-5.xhtml"}],
        "fragment": "fragments/vol0003-05.md",
        "source_ids": ["paul-graham-how-to-think-for-yourself"]
      }
    ],
    "sources": [
      {
        "id": "paul-graham-how-to-think-for-yourself",
        "type": "article",
        "title": "How to Think for Yourself",
        "url": "http://paulgraham.com/think.html",
        "site": "paulgraham.com",
        "origin": "web_search",
        "evidence": "https://…",
        "confidence": "high"
      }
    ]
  }
]
```

`type` 取值：`article` / `website` / `book` / `podcast` / `video` / `speech` / `interview` / `paper`。`origin` 取值：`in_text`（文内外链或「原文：」行）/ `in_text_domain`（只有出处域名）/ `web_search`。

## 收尾清单

- [x] 可读 epub 全部解析（132 本 + 1 损坏 + 1 重复），损坏文件列出
- [x] 每个文章章节都归类，编辑部章节和版本副本有明确标记
- [x] 每篇文章都有作者，更正附原因与依据
- [x] 每位作者至少一条信息源，或明确列入「未找到」清单（2 位未找到）
- [x] 输出由代码一次生成；调研结果通过结构校验
- [x] 单元测试与依赖方向检查通过
- [x] 抽样 20 篇核对记录在 `checks.md`

## 实施中的结构调整

- `articles.json` 中的文章另有 `authors_as_labeled`、`year_as_labeled`（原书标注）、`author_note` / `author_evidence` / `year_note`（更正依据）、`research_status` / `research_note`（调研结论）。
- 新增 `sources.json`：全部信息源的登记表，`authors.json` 与 `articles.json` 通过 `source_ids` / `article_ids` 关联。
