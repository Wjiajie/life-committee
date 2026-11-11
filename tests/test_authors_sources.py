import pytest

from catalog.core import assemble, authors, sources


ALIASES = {
    "raw_splits": {"Alex Soojung and Kim Pang": ["Alex Soojung-Kim Pang"]},
    "authors": [
        {"id": "paul-graham", "name": "保罗·格雷厄姆", "name_en": "Paul Graham", "kind": "person", "aliases": ["PG"]},
        {"id": "xiang-biao", "name": "项飙", "name_en": "Xiang Biao", "kind": "person", "aliases": ["项飚"]},
    ],
}


def _article(aid, raw, **extra):
    return {"id": aid, "title": f"文章{aid}", "authors_raw": raw, "year": None, "date": None, "topic": None,
            "published_site": None, "published_url": None, "cues": [], "variants": ["原章节"],
            "char_count": 1000, "appears_in": [{"book": "Vol.1", "chapters": ["c.xhtml"]}], **extra}


def test_split_names():
    assert authors.split_names("James A. Lindsay，Helen Pluckrose", {}) == ["James A. Lindsay", "Helen Pluckrose"]
    assert authors.split_names("Robert Goffee and Gareth Jones", {}) == ["Robert Goffee", "Gareth Jones"]
    assert authors.split_names("陈嘉映✖️项飙", {}) == ["陈嘉映", "项飙"]
    assert authors.split_names("艾伦·凯（未知）", {}) == ["艾伦·凯"]
    assert authors.split_names("John Salvatier.", {}) == ["John Salvatier"]
    assert authors.split_names("Alex Soojung and Kim Pang", ALIASES["raw_splits"]) == ["Alex Soojung-Kim Pang"]


def test_slug():
    assert authors.slug("Agnès Varda") == "agnes-varda"
    assert authors.slug("John O’Donohue") == "john-odonohue"
    assert authors.slug("张三").startswith("a-")


def test_alias_resolution_merges_variants_and_case():
    index = authors.alias_index(ALIASES)
    assert authors.resolve("Paul Graham", index)["id"] == "paul-graham"
    assert authors.resolve("保罗 · 格雷厄姆", index)["id"] == "paul-graham"
    assert authors.resolve("项飚", index)["id"] == "xiang-biao"
    assert authors.resolve("Alex danco", index)["id"] == authors.resolve("Alex Danco", index)["id"]


def test_alias_conflict_is_rejected():
    bad = {"authors": [{"id": "a", "name": "X", "aliases": []}, {"id": "b", "name": "Y", "aliases": ["X"]}]}
    with pytest.raises(ValueError):
        authors.alias_index(bad)


def test_overrides_replace_author_and_merge_duplicates():
    arts = [_article("v1", "Tim Urban"), _article("v2", None)]
    overrides = {"v1": {"authors": ["Paul Graham"], "note": "原书标错"}, "v2": {"same_as": "v1"}, "zz": {}}
    result, problems = authors.apply_overrides(arts, overrides)
    assert [a["id"] for a in result] == ["v1"]
    assert len(result[0]["appears_in"]) == 2
    assert result[0]["authors_as_labeled"] == "Tim Urban"
    result, _ = authors.attribute(result, ALIASES)
    assert result[0]["author_ids"] == ["paul-graham"]
    assert problems == ["策展数据引用了不存在的文章 zz"]


def test_year_override_keeps_labeled_year():
    arts = [_article("v1", "Paul Graham", year="2014")]
    result, _ = authors.apply_overrides(arts, {"v1": {"year": "2021", "year_note": "原文 2021 年发表"}})
    assert (result[0]["year"], result[0]["year_as_labeled"]) == ("2021", "2014")


def test_unlisted_names_default_to_person():
    assert authors.resolve("Someone New", authors.alias_index(ALIASES))["kind"] == "person"


def test_former_ids_redirect_author_research():
    redirects = authors.former_ids({"former_ids": {"john-paul": "jp-koning"}})
    rec = {"type": "website", "title": "Moneyness", "url": "https://www.moneyness.ca/", "site": "moneyness.ca",
           "evidence": "https://www.moneyness.ca/", "confidence": "high", "note": None}
    files = [("b.json", {"authors": [{"author_id": "john-paul", "sources": [rec]}]})]
    assert sources.validate_research(files, set(), {"jp-koning"}, redirects) == []
    _, by_author = sources.research_index(files, redirects)
    assert list(by_author) == ["jp-koning"]


def test_retired_ids_drop_author_research():
    redirects = authors.former_ids({"former_ids": {"the-white-house": None}})
    rec = {"type": "website", "title": "WH", "url": "https://www.whitehouse.gov/", "site": "whitehouse.gov",
           "evidence": "https://www.whitehouse.gov/", "confidence": "high", "note": None}
    files = [("b.json", {"authors": [{"author_id": "the-white-house", "sources": [rec]}]})]
    assert sources.validate_research(files, set(), set(), redirects) == []
    assert sources.research_index(files, redirects)[1] == {}


def test_former_ids_reject_chains():
    with pytest.raises(ValueError):
        authors.former_ids({"former_ids": {"a": "b", "b": "c"}})


def test_canonical_url_ignores_tracking_and_www():
    a = sources.canonical_url("https://www.example.com/post/?utm_source=x")
    b = sources.canonical_url("http://example.com/post")
    assert a == b


def test_sources_from_text_label_editorial_notion_page():
    art = _article("v1", "A", published_site="www.notion.so", published_url="https://www.notion.so/x")
    recs = sources.from_article_text(art)
    assert recs[0]["title"] == "参考答案 Notion 原发页" and recs[0]["type"] == "website"
    art = _article("v2", "A", published_site="ribbonfarm.com", published_url="https://www.ribbonfarm.com/a/")
    recs = sources.from_article_text(art)
    assert recs[0]["url"] == "https://www.ribbonfarm.com/a/" and recs[0]["origin"] == "in_text"


def test_bare_link_lines_are_not_sources():
    cue = {"label": "链接", "text": "https://youtu.be/x", "urls": ["https://youtu.be/x"], "line": 30}
    assert sources.from_article_text(_article("v1", "A", cues=[cue])) == []
    cue = {"label": "原文", "text": "https://a.org/p", "urls": ["https://a.org/p"], "line": 1}
    assert sources.from_article_text(_article("v1", "A", cues=[cue]))[0]["url"] == "https://a.org/p"


def test_validate_research_reports_bad_records():
    files = [("b.json", {"articles": [{"article_id": "v1", "status": "found",
                                       "sources": [{"type": "blog", "url": "x", "confidence": "high"}]}],
                         "authors": [{"author_id": "nobody", "sources": []}]})]
    problems = sources.validate_research(files, {"v1"}, {"paul-graham"})
    assert any("type" in p for p in problems)
    assert any("url" in p for p in problems)
    assert any("evidence" in p for p in problems)
    assert any("未知作者" in p for p in problems)


def test_assemble_and_research_plan():
    arts = [_article("v1", "Paul Graham", published_site="paulgraham.com",
                     published_url="http://paulgraham.com/smart.html"),
            _article("v2", "Paul Graham")]
    arts, _ = authors.apply_overrides(arts, {})
    arts, entries = authors.attribute(arts, ALIASES)
    research_articles = {"v2": {"status": "found", "note": None, "author_check": None, "sources": [
        {"type": "article", "title": "Beyond", "url": "http://paulgraham.com/smart.html", "site": "paulgraham.com",
         "evidence": "搜索", "confidence": "high", "note": None, "origin": "web_search"}]}}
    out_authors, out_articles, registry, report = assemble.assemble(arts, entries, research_articles, {})
    pg = out_authors[0]
    assert pg["article_count"] == 2
    assert len(pg["sources"]) == 1 and pg["sources"][0]["article_ids"] == ["v1", "v2"]
    assert pg["sources"][0]["origin"] == "in_text"
    assert report["articles_without_link"] == []
    plan = assemble.research_plan(arts, entries, research_articles, {})
    assert plan == [{"articles": [], "authors": [plan[0]["authors"][0]]}]
    assert plan[0]["authors"][0]["author_id"] == "paul-graham"
