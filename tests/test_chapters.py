from catalog.adapters.epub import chapter_from_html
from catalog.core.chapters import classify, parse_chapter, parse_header, source_cues

BODY = "正文" * 200


def test_format_a_by_line_with_year():
    h = parse_header(["可测量性和可放大性", "By 保罗·格雷厄姆（2011年）", "主题：财富"], [])
    assert h["authors_raw"] == "保罗·格雷厄姆"
    assert h["year"] == "2011"
    assert h["topic"] == "财富"
    assert h["header_format"] == "A"


def test_format_a_date_on_next_line():
    h = parse_header(["永远假设自己是错的", "By 埃隆·马斯克 ", "2022年11月14日", "推荐语："], [])
    assert h["authors_raw"] == "埃隆·马斯克"
    assert (h["year"], h["date"]) == ("2022", "2022-11-14")


def test_format_a_by_without_space_before_cjk():
    h = parse_header(["标题", "By张一鸣（2014年）"], [])
    assert h["authors_raw"] == "张一鸣"


def test_name_starting_with_by_is_not_a_by_line():
    h = parse_header(["选择性", "Byrne Hobart（2018 年）", "专题：投资"], [])
    assert h["authors_raw"] == "Byrne Hobart"
    assert h["header_format"] == "B"


def test_format_a_topic_before_by_line():
    h = parse_header(["Julian：如何构建你的心智模型", "主题：思维", "By Julian"], [])
    assert h["authors_raw"] == "Julian"
    assert h["topic"] == "思维"


def test_format_b_author_with_year():
    h = parse_header(["如何应对不断变化的世界秩序", "瑞·达利欧（2022年）", "专题：世界是如何运转的？"], [])
    assert h["authors_raw"] == "瑞·达利欧"
    assert h["year"] == "2022"


def test_format_b_author_without_year_before_topic():
    h = parse_header(["你应该拥有系统而非目标", "Scott Adams", "专题：思维方式"], [])
    assert h["authors_raw"] == "Scott Adams"
    assert h["year"] is None


def test_format_b_title_is_not_taken_as_author():
    h = parse_header(["短标题", "专题：思维方式"], [])
    assert h["authors_raw"] is None


def test_format_c_published_line_with_link_and_multiple_authors():
    html = (
        "<h2>现代性正在被左右两边吞噬</h2><blockquote><p>原发布于 "
        '<a href="https://example.org/a">example.org</a>，2017 年 8 月 22 日，'
        "James A. Lindsay，Helen Pluckrose</p></blockquote><p>正文</p>"
    )
    ch = chapter_from_html(html)
    h = parse_header(ch["lines"], ch["links"])
    assert h["published_site"] == "example.org"
    assert h["published_url"] == "https://example.org/a"
    assert h["authors_raw"] == "James A. Lindsay，Helen Pluckrose"
    assert h["date"] == "2017-08-22"


def test_format_c_unknown_author_becomes_none():
    h = parse_header(["标题", "原发布于 www.notion.so，未知"], [])
    assert h["authors_raw"] is None


def test_classify_front_editorial_and_article():
    article = {"title": "某文章", "authors_raw": "某人"}
    assert classify({"title": "", "authors_raw": None}, 50) == "front"
    assert classify({"title": "110 期导读｜内耗", "authors_raw": "参考答案编辑部"}, 3000) == "editorial"
    assert classify({"title": "前言", "authors_raw": None}, 3000) == "editorial"
    assert classify({"title": "130 期编辑部本周还读了啥", "authors_raw": None}, 400) == "editorial"
    assert classify(article, 3000) == "article"


def test_editorial_original_essay_is_an_article():
    h = {"title": "读弗洛姆《逃避自由》：身份是牢笼还是船票？", "authors_raw": "参考答案编辑部"}
    assert classify(h, 10000, "Vol.102 身份背后是什么？") == "article"


def test_editorial_chapter_titled_as_issue_topic_is_editorial():
    h = {"title": "我的身体，谁的身体？", "authors_raw": "参考答案编辑部"}
    assert classify(h, 10000, "Vol.95 我的身体，谁的身体？") == "editorial"


def test_variant_prefix_is_detected():
    parsed = parse_chapter({"lines": ["翻译版｜狐狸与刺猬", "原发布于 x.org，以赛亚·伯林", BODY], "links": []})
    assert parsed["variant"] == "翻译版"
    assert parsed["base_title"] == "狐狸与刺猬"


def test_source_cue_lines():
    lines = ["正文", "英文：You and Your Research (virginia.edu)", "原文：", "https://www.ribbonfarm.com/x/"]
    links = [{"href": "https://www.cs.virginia.edu/~robins/YouAndYourResearch.html", "text": "virginia.edu", "line": 1}]
    cues = source_cues(lines, links)
    assert cues[0]["label"] == "英文"
    assert cues[0]["urls"] == ["https://www.cs.virginia.edu/~robins/YouAndYourResearch.html"]
    assert cues[1]["label"] == "原文"
    assert cues[1]["urls"][0] == "https://www.ribbonfarm.com/x/"
