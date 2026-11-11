# 进度交接

## 图状态

- 已完成：N1 读取、N2 切分、N3 作者补全与别名、N4 汇总、N5 出处调研（两轮 + 补充）、N6 合并导出、N7 抽样核对
- 被阻塞：无

## 产物

- 代码：`catalog/`、`tests/`、`pyproject.toml`、`ARCHITECTURE.md`
- 策展数据（判断结果，可人工修改）：
  - `data/curated/author_aliases.json`：作者条目、别名、多作者拆分、`former_ids`（旧 id 重定向 / 作废）
  - `data/curated/article_overrides.json`：作者更正、重复合并（same_as）、年份更正，均附 note / evidence
  - `data/curated/sources/batch-XX.json`、`batch-r2-XX.json`、`batch-r3-01.json`：网络调研结果
- 输出 `data/catalog/`：`authors.json`（主产物）、`articles.json`、`sources.json`、`authors.csv`、`articles.csv`、`authors.md`、`editorials.json`、`fragments/`

## 最终数字（`python -m catalog build`）

- 600 篇文章、439 位作者（个人 434、刊物 3、机构 2），1745 条信息源（原书给出 134、网络调研 1611；high 1468、medium 277）
- 30 条作者更正、27 条年份更正、7 组重复合并
- 未找到出处：3 篇；无信息源作者：2 位（见 checks.md）

## 决策

- 访谈类文章归给受访者，访谈者写在 note；原书本就标访谈者时保留。
- 编辑部原创文章的出处使用原书给出的 Notion 原发页（可能需权限）。
- 正文里单独成行的链接（多为嵌入视频）不当作出处，只作调研线索。
- 更正分层保存：`authors_as_labeled` / `year_as_labeled` 保留原书标注，`author_ids` / `year` 是更正后的值。
- 别名表外的作者默认是个人；机构、刊物显式标注。

## 已知遗留

- `vol0028-c04`「中村修二」一文：正文疑为中文作者托名，真实作者未查到，保留归属并在 note 标明存疑。
- `vol0063-c07` 叔本华 38 种方法：原书年份 1986 无依据，未改年份，出处为第三方英文页面。
- `fragments/` 中保留了 7 篇被合并文章的片段文件（由 extract 生成，未被 articles.json 引用）。
- 少数中文书名为调研子代理的通行译名，未逐一核对出版信息（已在对应来源 note 中注明）。

## 重跑命令

```powershell
$env:PYTHONIOENCODING='utf-8'
uv run python -m catalog extract   # 原书 → 文章与片段
uv run python -m catalog build     # 叠加策展数据与调研 → 输出；同时生成待调研批次
uv run python -m catalog checks    # 汇总调研中的作者核对，供审核
uv run pytest; uv run lint-imports
```
