"""Google Search Console API client helpers."""

from __future__ import annotations

from googleapiclient.discovery import build

from gsc_cli.auth import load_credentials


def build_search_console_service(write: bool = False):
    """Create a Search Console API service client."""
    credentials = load_credentials(write=write)
    return build(
        "searchconsole",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )
