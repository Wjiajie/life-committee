# ARCHITECTURE.md

## 模块地图

| 模块 | 负责的领域 | 公开接口 | 允许依赖 | 规则文档 |
|------|------------|----------|----------|----------|
| `catalog` | 参考资料目录：把「参考答案」epub 切分成文章，归属作者，汇总信息源 | `catalog.build` 的阶段函数（`extract` / `names` / `build` / `validate`）；命令行 `python -m catalog <阶段>` | 标准库 | `docs/runs/epub-author-catalog/graph.md` |

`catalog` 内部分三圈：

| 位置 | 职责 |
|------|------|
| `catalog/core/` | 领域核心，纯函数，只收发普通数据：`chapters`（章节分类与文章头解析）、`articles`（版本合并与跨书去重）、`authors`（作者拆分、别名归并、文章级更正）、`sources`（出处抽取、调研结果校验、按 URL 去重）、`assemble`（汇总目录、生成待调研批次）、`render`（Markdown / CSV 文本） |
| `catalog/adapters/` | 读 epub（`epub`）、读写 JSON / CSV / 文本（`store`） |
| `catalog/build.py`、`catalog/__main__.py` | 编排：每个阶段读取上一阶段产物和策展数据，调用核心，写出产物 |

## 依赖方向

```
__main__ → build → core
                 → adapters
```

`core` 不依赖 `adapters`、`build`；`adapters` 不依赖 `build`。由 `uv run lint-imports`（`pyproject.toml` 中的 import-linter 合约）强制检查。

## 数据流与目录

```
datasets/参考答案/*.epub                 原始资料（只读）
  └─ extract → data/work/*.json          中间产物，可随时重算
               data/catalog/fragments/    文章片段正文
data/curated/                             策展数据（判断结果，可人工修改，每条附依据）
  ├─ author_aliases.json                  作者别名、中英文名、多作者拆分
  ├─ article_overrides.json               文章级更正：改作者、合并重复
  └─ sources/batch-XX.json                网络调研得到的出处与作者信息源
  └─ build → data/catalog/                最终产物：authors.json / articles.json / sources.json / *.csv / authors.md
```

确定性步骤（切分、解析、去重、汇总、导出、校验）全部在代码里；需要判断的结论只存在于 `data/curated/`，代码每次从原书重新计算再叠加它们。

## 新功能放在哪里

| 功能类型 | 归属 |
|----------|------|
| 新的文章头格式、章节分类规则 | `catalog/core/chapters.py` |
| 作者归并、更正规则 | `catalog/core/authors.py` + `data/curated/` |
| 出处类型、去重规则、调研结果结构 | `catalog/core/sources.py` |
| 新的导出格式（如网页用的数据） | `catalog/core/render.py` + `catalog/build.py` |
| 网页本身 | 新顶层模块，届时先提方案 |

## 已知例外

| 位置 | 违反的原则 | 原因 | 计划 |
|------|------------|------|------|
| 无 | | | |
