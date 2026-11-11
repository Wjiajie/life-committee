"""作者名的拆分、规范化，以及按策展别名表把文章归到作者名下。

策展数据（data/curated/）：
- author_aliases.json：{"authors": [{"id", "name", "name_en", "kind", "aliases": [...]}],
                        "raw_splits": {"原书写法": ["作者1", "作者2"]}}
- article_overrides.json：{"文章id": {"authors": [...], "same_as": "文章id", "note", "evidence"}}
"""

import hashlib
import re
import unicodedata

_SPLIT = re.compile(r"\s*(?:[，,、&]|✖️|✖|×|\s(?:and|And|AND)\s)\s*")
_DROP_SUFFIX = re.compile(r"\s*[（(](?:未知|公司)[）)]\s*$")
_DOTS = re.compile(r"[·•・‧∙.\-_'’]")


def name_key(name: str) -> str:
    """别名匹配用的键：忽略大小写、空白、间隔点与连字符。"""
    return _DOTS.sub("", re.sub(r"\s+", "", name)).casefold()


def clean_name(name: str) -> str:
    name = _DROP_SUFFIX.sub("", name.strip())
    return name.rstrip(".。 ").strip()


def split_names(raw: str, raw_splits: dict[str, list[str]]) -> list[str]:
    raw = raw.strip()
    if raw in raw_splits:
        return list(raw_splits[raw])
    return [n for n in (clean_name(p) for p in _SPLIT.split(raw)) if n]


_CJK = re.compile(r"[\u3000-\u9fff\uac00-\ud7af\uff00-\uffef]")


def slug(text: str) -> str:
    """西文名（含重音字母）转成可读 id；含中日韩文字时用哈希，由别名表给出正式 id。"""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    ascii_slug = re.sub(r"[^a-z0-9]+", "-", folded.replace("’", "").replace("'", "").casefold()).strip("-")
    if ascii_slug and not _CJK.search(text):
        return ascii_slug
    return "a-" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


def alias_index(aliases: dict) -> dict[str, dict]:
    """别名键 → 作者条目。同一别名指向两位作者时报错。"""
    index = {}
    for entry in aliases.get("authors", []):
        for alias in {entry["name"], entry.get("name_en") or entry["name"], *entry.get("aliases", [])}:
            key = name_key(alias)
            if key in index and index[key]["id"] != entry["id"]:
                raise ValueError(f"别名「{alias}」同时指向 {index[key]['id']} 与 {entry['id']}")
            index[key] = entry
    return index


def resolve(name: str, index: dict[str, dict]) -> dict:
    """别名表外的名字视为个人；机构、刊物须在别名表中显式标注。"""
    entry = index.get(name_key(name))
    if entry:
        return entry
    return {"id": slug(name), "name": name, "name_en": None if _CJK.search(name) else name,
            "kind": "person", "aliases": [name], "uncurated": True}


def former_ids(aliases: dict) -> dict[str, str | None]:
    """作者更正后不再使用的旧 id → 新 id。调研文件里挂在旧 id 上的作者级来源据此改挂。

    值为 null 表示换成了另一个人，旧 id 的作者级来源作废。
    """
    redirects = dict(aliases.get("former_ids", {}))
    for old, new in redirects.items():
        if new is not None and new in redirects:
            raise ValueError(f"former_ids 不能链式跳转：{old} → {new} → {redirects[new]}")
    return redirects


def apply_overrides(articles: list[dict], overrides: dict) -> tuple[list[dict], list[str]]:
    """应用文章级更正：same_as 合并出现位置；authors 替换原书标注。返回 (文章, 问题列表)。"""
    by_id = {a["id"]: a for a in articles}
    problems = [f"策展数据引用了不存在的文章 {aid}" for aid in overrides if aid not in by_id]
    result = []
    for article in articles:
        rule = overrides.get(article["id"], {})
        target = rule.get("same_as")
        if target:
            if target not in by_id:
                problems.append(f"{article['id']} 的 same_as 指向不存在的 {target}")
            else:
                by_id[target]["appears_in"].extend(article["appears_in"])
                by_id[target].setdefault("merged_ids", []).append(article["id"])
                continue
        result.append(article)
    for article in result:
        rule = overrides.get(article["id"], {})
        article["authors_as_labeled"] = article["authors_raw"]
        article["author_names"] = rule.get("authors")
        article["author_note"] = rule.get("note")
        article["author_evidence"] = rule.get("evidence")
        article["verify"] = bool(rule.get("verify"))
        article["year_as_labeled"] = article["year"]
        article["year_note"] = rule.get("year_note")
        if rule.get("year"):
            article["year"] = rule["year"]
    return result, problems


def attribute(articles: list[dict], aliases: dict) -> tuple[list[dict], dict[str, dict]]:
    """为每篇文章确定作者 id 列表；返回 (文章, 作者条目表)。"""
    index = alias_index(aliases)
    raw_splits = aliases.get("raw_splits", {})
    entries: dict[str, dict] = {}
    for article in articles:
        names = article.get("author_names")
        if names is None:
            names = split_names(article["authors_raw"], raw_splits) if article["authors_raw"] else []
        ids = []
        for name in names:
            entry = resolve(name, index)
            kept = entries.setdefault(entry["id"], {**entry, "observed": []})
            if name not in kept["observed"]:
                kept["observed"].append(name)
            if entry["id"] not in ids:
                ids.append(entry["id"])
        article["author_ids"] = ids
    return articles, entries


def distinct_names(articles: list[dict], aliases: dict) -> list[dict]:
    """所有拆分后的作者名及其出现次数、是否已有别名条目（供策展使用）。"""
    index = alias_index(aliases)
    raw_splits = aliases.get("raw_splits", {})
    counts: dict[str, dict] = {}
    for article in articles:
        names = article.get("author_names")
        if names is None:
            names = split_names(article["authors_raw"], raw_splits) if article["authors_raw"] else []
        for name in names:
            item = counts.setdefault(name, {"name": name, "count": 0, "raw": set(), "titles": []})
            item["count"] += 1
            item["raw"].add(article["authors_raw"] or "")
            if len(item["titles"]) < 3:
                item["titles"].append(article["title"])
    return [
        {**v, "raw": sorted(v["raw"]), "curated": name_key(v["name"]) in index}
        for v in sorted(counts.values(), key=lambda v: name_key(v["name"]))
    ]
