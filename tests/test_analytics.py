import pytest

from gsc_cli.analytics import ValidationError, build_query_request, parse_filter_expression


def test_parse_filter_expression_valid():
    parsed = parse_filter_expression("query:contains:brand:term")
    assert parsed == {
        "dimension": "query",
        "operator": "contains",
        "expression": "brand:term",
    }


def test_parse_filter_expression_invalid_format():
    with pytest.raises(ValidationError, match="Invalid --filter format"):
        parse_filter_expression("query:contains")


def test_build_query_request_happy_path():
    body = build_query_request(
        start_date="2026-01-01",
        end_date="2026-01-31",
        dimensions=("date", "query"),
        query_type="web",
        aggregation_type="auto",
        row_limit=100,
        start_row=0,
        data_state="final",
        filters=("query:contains:brand", "device:equals:MOBILE"),
    )

    assert body["startDate"] == "2026-01-01"
    assert body["endDate"] == "2026-01-31"
    assert body["dimensions"] == ["date", "query"]
    assert body["dimensionFilterGroups"][0]["groupType"] == "and"
    assert len(body["dimensionFilterGroups"][0]["filters"]) == 2


def test_build_query_request_invalid_page_by_property_combo():
    with pytest.raises(ValidationError, match="byProperty"):
        build_query_request(
            start_date="2026-01-01",
            end_date="2026-01-31",
            dimensions=("page",),
            query_type="web",
            aggregation_type="byProperty",
            row_limit=100,
            start_row=0,
            data_state="final",
            filters=(),
        )


def test_build_query_request_invalid_date_order():
    with pytest.raises(ValidationError, match="start-date"):
        build_query_request(
            start_date="2026-02-01",
            end_date="2026-01-31",
            dimensions=(),
            query_type="web",
            aggregation_type="auto",
            row_limit=100,
            start_row=0,
            data_state="final",
            filters=(),
        )
