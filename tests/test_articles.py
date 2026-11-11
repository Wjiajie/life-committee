from catalog.core.articles import articles_from_book, book_id, dedupe_across_books, dedupe_key

BODY = "正文" * 200


def _chapter(index, lines, links=None):
    return {"index": index, "href": f"c{index}.xhtml", "lines": lines, "links": links or []}


def test_book_id():
    assert book_id("Vol.0003 标题.epub") == "vol0003"
    assert book_id("参考周刊｜Vol.85 约束.epub") == "vol0085"
    assert book_id("Vol.130+从刺猬到青蛙.epub") == "vol0130"
    assert book_id("参考答案｜年度十佳文章.epub").startswith("book-")


def test_variants_in_one_book_merge_and_prefer_translation():
    book = {"file": "Vol.130 测试.epub", "chapters": [
        _chapter(0, ["130 期导读｜测试", "原发布于 www.notion.so，参考答案编辑部", BODY]),
        _chapter(1, ["狐狸与刺猬", "原发布于 a.org，以赛亚·伯林", "THERE is a line " * 30],
                 [{"href": "https://a.org/fox", "text": "a.org", "line": 1}]),
        _chapter(2, ["翻译版｜狐狸与刺猬", "原发布于 a.org，以赛亚·伯林", BODY]),
        _chapter(3, ["翻译对照版｜狐狸与刺猬", "原发布于 a.org，以赛亚·伯林", BODY]),
    ]}
    articles, editorials, front = articles_from_book(book)
    assert len(articles) == 1 and len(editorials) == 1
    art = articles[0]
    assert art["id"] == "vol0130-c02"
    assert art["published_url"] == "https://a.org/fox"
    assert art["variants"] == ["原章节", "翻译版", "翻译对照版"]
    assert art["text"][0] == "翻译版｜狐狸与刺猬"


def test_whole_chapter_variant_uses_book_title():
    book = {"file": "深度长文：公司简史.epub", "chapters": [
        _chapter(0, ["中文版", "Venkatesh Rao（2011 年）", "专题：人类和社会", BODY]),
        _chapter(1, ["中英对照版", "原文：", "https://www.ribbonfarm.com/x/", BODY]),
    ]}
    articles, _, _ = articles_from_book(book)
    assert len(articles) == 1
    assert articles[0]["title"] == "深度长文：公司简史"
    assert articles[0]["authors_raw"] == "Venkatesh Rao"
    assert articles[0]["cues"][0]["urls"] == ["https://www.ribbonfarm.com/x/"]


def test_dedupe_key_strips_author_prefix():
    assert dedupe_key("Tim Urban：如何选择职业？", "Tim Urban") == dedupe_key("如何选择职业", "Tim Urban")
    assert dedupe_key("约束理论（上）：原则", "Tiago Forte") != dedupe_key("约束理论（下）：原则", "Tiago Forte")


def test_dedupe_across_books_merges_appearances_and_flags_near_duplicates():
    base = {"year": None, "date": None, "topic": None, "published_site": None, "published_url": None, "cues": []}
    a = {**base, "id": "v1", "title": "如何在有限的生命里，做真正重要的事", "authors_raw": "理查德·汉明",
         "appears_in": [{"book": "A"}]}
    b = {**base, "id": "v2", "title": "如何在有限的生命里，做真正重要的事", "authors_raw": "理查德·汉明",
         "appears_in": [{"book": "B"}]}
    c = {**base, "id": "v3", "title": "如何在有限的生命，做真正重要的事？", "authors_raw": None,
         "appears_in": [{"book": "C"}]}
    result, suspects = dedupe_across_books([a, b, c])
    assert [r["id"] for r in result] == ["v1", "v3"]
    assert [p["book"] for p in result[0]["appears_in"]] == ["A", "B"]
    assert suspects and suspects[0]["a"] == "v1" and suspects[0]["b"] == "v3"
