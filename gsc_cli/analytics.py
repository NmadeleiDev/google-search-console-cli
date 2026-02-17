"""Search Analytics request and parsing helpers."""

from __future__ import annotations

from datetime import date

ALLOWED_DIMENSIONS = {
    "country",
    "device",
    "page",
    "query",
    "searchAppearance",
    "date",
    "hour",
}

ALLOWED_FILTER_DIMENSIONS = {
    "country",
    "device",
    "page",
    "query",
    "searchAppearance",
}

ALLOWED_OPERATORS = {
    "contains",
    "equals",
    "notContains",
    "notEquals",
    "includingRegex",
    "excludingRegex",
}

ALLOWED_TYPES = {"web", "image", "video", "news", "discover", "googleNews"}
ALLOWED_AGGREGATION_TYPES = {"auto", "byPage", "byProperty", "byNewsShowcasePanel"}
ALLOWED_DATA_STATES = {"final", "all", "hourly_all"}


class ValidationError(ValueError):
    """Raised for invalid user input before API execution."""


def parse_ymd(value: str) -> str:
    """Validate YYYY-MM-DD format and return unchanged string."""
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"Invalid date '{value}'. Use YYYY-MM-DD.") from exc
    return value


def validate_date_range(start_date: str, end_date: str) -> None:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if start > end:
        raise ValidationError("start-date must be <= end-date.")


def parse_filter_expression(filter_expression: str) -> dict:
    """Parse one filter expression in the form dimension:operator:expression."""
    parts = filter_expression.split(":", 2)
    if len(parts) != 3:
        raise ValidationError(
            "Invalid --filter format. Expected dimension:operator:expression"
        )

    dimension, operator, expression = parts
    if dimension not in ALLOWED_FILTER_DIMENSIONS:
        allowed = ", ".join(sorted(ALLOWED_FILTER_DIMENSIONS))
        raise ValidationError(
            f"Unsupported filter dimension '{dimension}'. Allowed: {allowed}"
        )

    if operator not in ALLOWED_OPERATORS:
        allowed = ", ".join(sorted(ALLOWED_OPERATORS))
        raise ValidationError(
            f"Unsupported filter operator '{operator}'. Allowed: {allowed}"
        )

    if expression == "":
        raise ValidationError("Filter expression cannot be empty.")

    return {
        "dimension": dimension,
        "operator": operator,
        "expression": expression,
    }


def build_query_request(
    *,
    start_date: str,
    end_date: str,
    dimensions: tuple[str, ...],
    query_type: str,
    aggregation_type: str,
    row_limit: int,
    start_row: int,
    data_state: str,
    filters: tuple[str, ...],
) -> dict:
    """Build and validate a Search Analytics query request body."""
    parse_ymd(start_date)
    parse_ymd(end_date)
    validate_date_range(start_date, end_date)

    if query_type not in ALLOWED_TYPES:
        raise ValidationError(f"Unsupported type '{query_type}'.")

    if aggregation_type not in ALLOWED_AGGREGATION_TYPES:
        raise ValidationError(f"Unsupported aggregation-type '{aggregation_type}'.")

    if data_state not in ALLOWED_DATA_STATES:
        raise ValidationError(f"Unsupported data-state '{data_state}'.")

    if not (1 <= row_limit <= 25000):
        raise ValidationError("row-limit must be between 1 and 25000.")

    if start_row < 0:
        raise ValidationError("start-row must be >= 0.")

    for dimension in dimensions:
        if dimension not in ALLOWED_DIMENSIONS:
            allowed = ", ".join(sorted(ALLOWED_DIMENSIONS))
            raise ValidationError(
                f"Unsupported dimension '{dimension}'. Allowed: {allowed}"
            )

    parsed_filters = [parse_filter_expression(item) for item in filters]

    uses_page_dimension = "page" in dimensions
    uses_page_filter = any(item["dimension"] == "page" for item in parsed_filters)
    if aggregation_type == "byProperty" and (uses_page_dimension or uses_page_filter):
        raise ValidationError(
            "aggregation-type=byProperty cannot be used with page dimension or page filter."
        )

    body = {
        "startDate": start_date,
        "endDate": end_date,
        "type": query_type,
        "aggregationType": aggregation_type,
        "rowLimit": row_limit,
        "startRow": start_row,
        "dataState": data_state,
    }

    if dimensions:
        body["dimensions"] = list(dimensions)

    if parsed_filters:
        body["dimensionFilterGroups"] = [
            {
                "groupType": "and",
                "filters": parsed_filters,
            }
        ]

    return body


def rows_to_records(response: dict, dimensions: tuple[str, ...]) -> list[dict]:
    """Convert API rows into flat records suitable for output formats."""
    rows = response.get("rows", [])
    records: list[dict] = []

    for row in rows:
        record: dict = {}
        keys = row.get("keys", [])

        for index, dimension in enumerate(dimensions):
            record[dimension] = keys[index] if index < len(keys) else None

        for metric in ("clicks", "impressions", "ctr", "position"):
            if metric in row:
                record[metric] = row[metric]

        records.append(record)

    return records
