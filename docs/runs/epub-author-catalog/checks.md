# 门控记录

节点 | 要求 | 结论 | 证据
---|---|---|---
N1 | 可读 epub 全部解析，损坏与重复文件列出 | 通过 | `extract`：books=132、read_errors=2；`data/work/read_errors.json` 列出 `Vol.0077 傻瓜和他们的金钱隐喻.epub`（0 字节，BadZipFile）与 `参考月刊·特别篇｜热尔韦原则 .epub`（与 `(1)` 版字节相同）
N2 | 三种文章头格式解析正确 | 通过 | `tests/test_chapters.py`；全量「标题 / 作者」清单逐条过目，修正了 `By` 前缀误截（Byrne Hobart）、作者行长度上限、编辑部原创文章误归导读
N2 | 每个章节都有归类 | 通过 | article_chapters=627、editorial=64、front=316；导读/前言/扩展阅读清单输出到 `data/catalog/editorials.json`
N2 | 版本副本合并、跨书去重 | 通过 | `tests/test_articles.py`；代码精确去重后 607 篇，加上 `article_overrides.json` 中 7 组人工确认的 same_as，最终 600 篇
N3 | 每篇文章都有作者，更正附依据 | 通过 | `build` 报告 `articles_without_author: []`；30 条调研更正经 `python -m catalog checks` 汇总、逐条审核后写入 `article_overrides.json`，每条含 note 与 evidence
N3 | 推断性更正已核实 | 通过 | 4 条 `verify` 更正（超越智力、Julian×2、Lars Doucet）均被调研确认，已移除 verify 标记并补证据链接
N3 | 别名表无冲突、旧 id 正确改挂 | 通过 | `alias_index` 冲突即抛错；`former_ids` 禁止链式跳转、禁止重定向仍在使用的 id；`authors_with_hash_id`=0
N5 | 调研结果结构合法 | 通过 | `python -m catalog validate`：36 个文件（第一轮 33、第二轮 2、补充 1），`"problems": []`
N5 | 不编造链接 | 通过（抽样） | 规格明令只写实际见到的 URL；N7 抽样打开 3 个链接全部吻合
N6 | 每篇文章有出处链接 | 未解决（3 篇） | `vol0076-c06`（Mark Marchenko）、`vol0094-c05`（Jovana）、`vol0094-c06`（Yanik）多轮搜索未找到，研究记录为 not_found；编辑部原创 9 篇以原书给出的 Notion 原发页作出处
N6 | 每位作者至少一条信息源 | 未解决（2 位） | `jovana`、`yanik` 只有单名且原文未找到，无法确认身份
N6 | 导出物一致 | 通过 | `authors.json` / `articles.json` / `sources.json` / CSV / MD 均由 `build` 一次生成；`articles.json` 中每个 source_id 都能在 `sources.json` 找到（CSV 生成时按 id 查表，缺失即报错）
N7 | 随机抽 20 篇核对 | 通过 | 种子 20261110 抽取的 20 篇：作者均与原文署名或已记录的更正一致，来源标题均与文章对应；其中 3 篇打开原文逐段比对：`vol0089-c06`（ribbonfarm《The Strategy of No Strategy》，署名 Adam Elkus，首段与图注一致）、`vol0037-c03`（grahamduncan.blog，开篇 Appiah 引语一致）、`vol0028-c07`（jamesclear.com/saying-no，署名 James Clear）。其余 17 篇只核对了标题与作者对应关系，未逐段比对
架构 | 依赖方向 | 通过 | `uv run lint-imports`：2 kept, 0 broken
测试 | 单元测试 | 通过 | `uv run pytest`：35 passed
