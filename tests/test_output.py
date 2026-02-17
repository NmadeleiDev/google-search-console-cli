from pathlib import Path

from gsc_cli.output import render_records


def test_render_records_json():
    text = render_records([{"query": "x", "clicks": 1.0}], output_format="json")
    assert '"query": "x"' in text


def test_render_records_table():
    text = render_records(
        [{"query": "shoes", "clicks": 10, "impressions": 100}],
        output_format="table",
    )
    assert "query" in text
    assert "shoes" in text


def test_render_records_csv(tmp_path: Path):
    out = tmp_path / "rows.csv"
    msg = render_records(
        [{"query": "hat", "clicks": 5}],
        output_format="csv",
        csv_path=str(out),
    )
    assert "Wrote 1 row(s)" in msg
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "query,clicks" in content
    assert "hat,5" in content
