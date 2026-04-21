"""Tests for HTML and table parsers."""

from __future__ import annotations

import pytest

from scrapekit.models.config import ParserConfig, FieldConfig
from scrapekit.parsers import HTMLParser, TableParser

SAMPLE_HTML = """
<html>
<body>
  <ul>
    <li class="item">
      <a href="/product/1" class="title">Widget A</a>
      <span class="price">$9.99</span>
      <span class="rating" data-score="4">★★★★</span>
    </li>
    <li class="item">
      <a href="/product/2" class="title">Widget B</a>
      <span class="price">$14.50</span>
      <span class="rating" data-score="5">★★★★★</span>
    </li>
  </ul>
</body>
</html>
"""

TABLE_HTML = """
<html><body>
<table>
  <tr><th>Name</th><th>Score</th></tr>
  <tr><td>Alice</td><td>95</td></tr>
  <tr><td>Bob</td><td>87</td></tr>
</table>
</body></html>
"""


class TestHTMLParser:
    @pytest.fixture()
    def parser(self) -> HTMLParser:
        config = ParserConfig(
            item_selector="li.item",
            fields={
                "title": FieldConfig(selector="a.title"),
                "price": FieldConfig(selector="span.price"),
                "href": FieldConfig(selector="a.title", attribute="href"),
                "score": FieldConfig(selector="span.rating", attribute="data-score"),
            },
        )
        return HTMLParser(config)

    def test_record_count(self, parser: HTMLParser) -> None:
        records = parser.parse(SAMPLE_HTML)
        assert len(records) == 2

    def test_text_extraction(self, parser: HTMLParser) -> None:
        records = parser.parse(SAMPLE_HTML)
        assert records[0]["title"] == "Widget A"
        assert records[1]["price"] == "$14.50"

    def test_attribute_extraction(self, parser: HTMLParser) -> None:
        records = parser.parse(SAMPLE_HTML)
        assert records[0]["score"] == "4"
        assert records[1]["score"] == "5"

    def test_href_extraction(self, parser: HTMLParser) -> None:
        records = parser.parse(SAMPLE_HTML)
        assert records[0]["href"] == "/product/1"

    def test_missing_selector_returns_none(self) -> None:
        config = ParserConfig(
            item_selector="li.item",
            fields={"missing": FieldConfig(selector="span.nonexistent")},
        )
        records = HTMLParser(config).parse(SAMPLE_HTML)
        assert records[0]["missing"] is None

    def test_find_next_page_exists(self) -> None:
        html = '<html><body><ul><li class="next"><a href="/page/2">next</a></li></ul></body></html>'
        result = HTMLParser.find_next_page(html, "li.next a")
        assert result == "/page/2"

    def test_find_next_page_none(self) -> None:
        result = HTMLParser.find_next_page("<html><body></body></html>", "li.next a")
        assert result is None


class TestTableParser:
    def test_parse_all(self) -> None:
        tables = TableParser().parse_all(TABLE_HTML)
        assert len(tables) == 1
        assert len(tables[0]) == 2

    def test_parse_by_index(self) -> None:
        df = TableParser().parse_by_index(TABLE_HTML, index=0)
        assert list(df.columns) == ["Name", "Score"]
        assert df.iloc[0]["Name"] == "Alice"

    def test_parse_by_index_out_of_range(self) -> None:
        with pytest.raises(IndexError):
            TableParser().parse_by_index(TABLE_HTML, index=5)

    def test_no_tables_raises(self) -> None:
        with pytest.raises((ValueError, Exception)):
            TableParser().parse_by_index("<html><body><p>no tables</p></body></html>")
