"""Click CLI for Google Search Console."""

from __future__ import annotations

import json
import sys
from functools import wraps

import click
from googleapiclient.errors import HttpError

from gsc_cli import __version__
from gsc_cli.analytics import (
    ALLOWED_AGGREGATION_TYPES,
    ALLOWED_DATA_STATES,
    ALLOWED_DIMENSIONS,
    ALLOWED_TYPES,
    ValidationError,
    build_query_request,
    rows_to_records,
)
from gsc_cli.auth import AuthError, load_credentials, login_with_client_secret, stored_credentials_info
from gsc_cli.client import build_search_console_service
from gsc_cli.config import ConfigError, get_default_site, set_default_site
from gsc_cli.output import render_records
from gsc_cli.paths import app_config_file, credentials_file

USER_INPUT_EXIT_CODE = 2
AUTH_EXIT_CODE = 3
API_EXIT_CODE = 4


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """Google Search Console CLI."""


def command_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (ValidationError, ValueError, ConfigError) as exc:
            click.echo(f"Error: {exc}", err=True)
            raise click.exceptions.Exit(USER_INPUT_EXIT_CODE) from exc
        except AuthError as exc:
            click.echo(f"Auth error: {exc}", err=True)
            raise click.exceptions.Exit(AUTH_EXIT_CODE) from exc
        except HttpError as exc:
            status = getattr(exc.resp, "status", "unknown")
            click.echo(f"API error ({status}): {_extract_http_error(exc)}", err=True)
            raise click.exceptions.Exit(API_EXIT_CODE) from exc

    return wrapper


def _extract_http_error(exc: HttpError) -> str:
    content = getattr(exc, "content", None)
    if not content:
        return str(exc)

    try:
        payload = json.loads(content.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return str(exc)

    if isinstance(payload, dict):
        error = payload.get("error", {})
        message = error.get("message")
        if message:
            return message

    return str(exc)


def _resolve_site(site_url: str | None) -> str:
    if site_url:
        return site_url

    default_site = get_default_site()
    if default_site:
        return default_site

    raise ValidationError(
        "No site specified. Pass --site or set one with "
        "`gsc config set default-site <siteUrl>`."
    )


def _sitemap_to_record(item: dict, *, stringify_contents: bool) -> dict:
    contents = item.get("contents")
    if stringify_contents and isinstance(contents, list):
        contents_value: list | str = json.dumps(contents, separators=(",", ":"))
    else:
        contents_value = contents

    return {
        "path": item.get("path"),
        "type": item.get("type"),
        "isPending": item.get("isPending"),
        "isSitemapsIndex": item.get("isSitemapsIndex"),
        "lastSubmitted": item.get("lastSubmitted"),
        "lastDownloaded": item.get("lastDownloaded"),
        "warnings": item.get("warnings"),
        "errors": item.get("errors"),
        "contents": contents_value,
    }


def _inspection_to_record(
    inspection_result: dict,
    *,
    inspection_url: str,
    site_url: str,
    stringify_nested: bool,
) -> dict:
    index_status = inspection_result.get("indexStatusResult", {})
    if not isinstance(index_status, dict):
        index_status = {}

    amp_result = inspection_result.get("ampResult", {})
    if not isinstance(amp_result, dict):
        amp_result = {}

    mobile_result = inspection_result.get("mobileUsabilityResult", {})
    if not isinstance(mobile_result, dict):
        mobile_result = {}

    rich_results = inspection_result.get("richResultsResult", {})
    if not isinstance(rich_results, dict):
        rich_results = {}

    sitemap = index_status.get("sitemap")
    referring_urls = index_status.get("referringUrls")
    amp_issues = amp_result.get("issues")
    mobile_issues = mobile_result.get("issues")
    rich_items = rich_results.get("detectedItems")

    if stringify_nested:
        if isinstance(sitemap, list):
            sitemap = json.dumps(sitemap, separators=(",", ":"))
        if isinstance(referring_urls, list):
            referring_urls = json.dumps(referring_urls, separators=(",", ":"))
        if isinstance(amp_issues, list):
            amp_issues = json.dumps(amp_issues, separators=(",", ":"))
        if isinstance(mobile_issues, list):
            mobile_issues = json.dumps(mobile_issues, separators=(",", ":"))
        if isinstance(rich_items, list):
            rich_items = json.dumps(rich_items, separators=(",", ":"))

    return {
        "siteUrl": site_url,
        "inspectionUrl": inspection_url,
        "inspectionResultLink": inspection_result.get("inspectionResultLink"),
        "verdict": index_status.get("verdict"),
        "coverageState": index_status.get("coverageState"),
        "indexingState": index_status.get("indexingState"),
        "robotsTxtState": index_status.get("robotsTxtState"),
        "pageFetchState": index_status.get("pageFetchState"),
        "lastCrawlTime": index_status.get("lastCrawlTime"),
        "crawledAs": index_status.get("crawledAs"),
        "googleCanonical": index_status.get("googleCanonical"),
        "userCanonical": index_status.get("userCanonical"),
        "sitemap": sitemap,
        "referringUrls": referring_urls,
        "ampVerdict": amp_result.get("verdict"),
        "ampIssues": amp_issues,
        "mobileUsabilityVerdict": mobile_result.get("verdict"),
        "mobileUsabilityIssues": mobile_issues,
        "richResultsVerdict": rich_results.get("verdict"),
        "richResultsItems": rich_items,
    }


@cli.group()
def auth() -> None:
    """Authenticate and inspect credentials."""


@auth.command("login")
@click.option(
    "--client-secret",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=str),
    help="Path to OAuth client secret JSON.",
)
@click.option("--readonly", is_flag=True, help="Request readonly scope only.")
@click.option("--no-launch-browser", is_flag=True, help="Do not auto-open browser.")
@command_errors
def auth_login(client_secret: str, readonly: bool, no_launch_browser: bool) -> None:
    """Run OAuth login and save local credentials."""
    output_path = login_with_client_secret(
        client_secret,
        write=not readonly,
        launch_browser=not no_launch_browser,
    )
    click.echo(f"Saved credentials to {output_path}")


@auth.command("whoami")
@click.option("--output", "output_format", type=click.Choice(["table", "json"]), default="table")
@command_errors
def auth_whoami(output_format: str) -> None:
    """Show locally stored credential details."""
    info = stored_credentials_info()
    if info is None:
        raise ValidationError(
            "No local OAuth credentials found. Run `gsc auth login --client-secret <path>` first."
        )

    record = {
        "path": info["path"],
        "has_refresh_token": info["has_refresh_token"],
        "scopes": ",".join(info["scopes"]),
        "client_id": info.get("client_id") or "",
    }
    click.echo(render_records([record], output_format=output_format))


@cli.group()
def config() -> None:
    """Manage CLI configuration."""


@config.group("set")
def config_set() -> None:
    """Set config values."""


@config_set.command("default-site")
@click.argument("site_url")
@command_errors
def config_set_default_site(site_url: str) -> None:
    """Set default site used when --site is omitted."""
    path = set_default_site(site_url)
    click.echo(f"Set default-site to {site_url}")
    click.echo(f"Config file: {path}")


@config.group("get")
def config_get() -> None:
    """Get config values."""


@config_get.command("default-site")
@command_errors
def config_get_default_site() -> None:
    """Get default site."""
    site_url = get_default_site()
    if not site_url:
        raise ValidationError("default-site is not set.")
    click.echo(site_url)


@cli.command("doctor")
def doctor() -> None:
    """Run diagnostics for environment, auth, and API connectivity."""
    checks: list[dict] = []
    failures = 0

    checks.append(
        {
            "check": "python",
            "status": "ok",
            "detail": sys.version.split()[0],
        }
    )

    checks.append(
        {
            "check": "config-path",
            "status": "ok",
            "detail": str(app_config_file()),
        }
    )

    default_site = get_default_site()
    checks.append(
        {
            "check": "default-site",
            "status": "ok" if default_site else "warn",
            "detail": default_site or "not set",
        }
    )

    info = None
    try:
        info = stored_credentials_info()
    except AuthError as exc:
        checks.append(
            {
                "check": "stored-credentials",
                "status": "fail",
                "detail": str(exc),
            }
        )
        failures += 1

    if info is None:
        checks.append(
            {
                "check": "stored-credentials",
                "status": "warn",
                "detail": f"not found at {credentials_file()} (ADC fallback may still work)",
            }
        )
    elif info:
        checks.append(
            {
                "check": "stored-credentials",
                "status": "ok",
                "detail": info["path"],
            }
        )

    try:
        load_credentials(write=False)
        checks.append(
            {
                "check": "auth-refresh",
                "status": "ok",
                "detail": "credentials load and refresh succeeded",
            }
        )
    except AuthError as exc:
        checks.append(
            {
                "check": "auth-refresh",
                "status": "fail",
                "detail": str(exc),
            }
        )
        failures += 1

    try:
        service = build_search_console_service(write=False)
        response = service.sites().list().execute()
        count = len(response.get("siteEntry", []))
        checks.append(
            {
                "check": "api-connectivity",
                "status": "ok",
                "detail": f"sites.list succeeded ({count} properties)",
            }
        )
    except (AuthError, HttpError, Exception) as exc:  # noqa: BLE001
        checks.append(
            {
                "check": "api-connectivity",
                "status": "fail",
                "detail": str(exc),
            }
        )
        failures += 1

    click.echo(render_records(checks, output_format="table"))
    if failures:
        raise click.exceptions.Exit(1)


@cli.group()
def site() -> None:
    """Manage Search Console properties."""


@site.command("list")
@click.option("--output", "output_format", type=click.Choice(["table", "json", "csv"]), default="table")
@click.option("--csv-path", type=click.Path(dir_okay=False, writable=True, path_type=str), default=None)
@command_errors
def site_list(output_format: str, csv_path: str | None) -> None:
    """List accessible Search Console properties."""
    service = build_search_console_service(write=False)
    response = service.sites().list().execute()
    entries = response.get("siteEntry", [])

    records = [
        {
            "siteUrl": item.get("siteUrl"),
            "permissionLevel": item.get("permissionLevel"),
        }
        for item in entries
    ]

    click.echo(render_records(records, output_format=output_format, csv_path=csv_path))


@site.command("get")
@click.option("--site", "site_url", required=False, help="Site URL, e.g. sc-domain:example.com")
@click.option("--output", "output_format", type=click.Choice(["table", "json", "csv"]), default="json")
@click.option("--csv-path", type=click.Path(dir_okay=False, writable=True, path_type=str), default=None)
@command_errors
def site_get(site_url: str | None, output_format: str, csv_path: str | None) -> None:
    """Get one Search Console property."""
    resolved_site = _resolve_site(site_url)
    service = build_search_console_service(write=False)
    item = service.sites().get(siteUrl=resolved_site).execute()
    records = [item]
    click.echo(render_records(records, output_format=output_format, csv_path=csv_path))


@site.command("add")
@click.option("--site", "site_url", required=False, help="Site URL, e.g. sc-domain:example.com")
@command_errors
def site_add(site_url: str | None) -> None:
    """Add a Search Console property."""
    resolved_site = _resolve_site(site_url)
    service = build_search_console_service(write=True)
    service.sites().add(siteUrl=resolved_site).execute()
    click.echo(f"Added site: {resolved_site}")


@cli.group()
def sitemap() -> None:
    """Manage Search Console sitemaps."""


@sitemap.command("list")
@click.option("--site", "site_url", required=False, help="Site URL, e.g. sc-domain:example.com")
@click.option(
    "--sitemap-index",
    default=None,
    help="Optional sitemap index URL/path filter passed to the API.",
)
@click.option("--output", "output_format", type=click.Choice(["table", "json", "csv"]), default="table")
@click.option("--csv-path", type=click.Path(dir_okay=False, writable=True, path_type=str), default=None)
@command_errors
def sitemap_list(
    site_url: str | None,
    sitemap_index: str | None,
    output_format: str,
    csv_path: str | None,
) -> None:
    """List sitemaps for a property."""
    resolved_site = _resolve_site(site_url)
    service = build_search_console_service(write=False)

    request_params = {"siteUrl": resolved_site}
    if sitemap_index:
        request_params["sitemapIndex"] = sitemap_index

    response = service.sitemaps().list(**request_params).execute()
    entries = response.get("sitemap", [])
    records = [
        _sitemap_to_record(item, stringify_contents=output_format != "json")
        for item in entries
    ]
    click.echo(render_records(records, output_format=output_format, csv_path=csv_path))


@sitemap.command("get")
@click.option("--site", "site_url", required=False, help="Site URL, e.g. sc-domain:example.com")
@click.option(
    "--feedpath",
    "--path",
    "feedpath",
    required=True,
    help="Sitemap URL/path, e.g. https://example.com/sitemap.xml",
)
@click.option("--output", "output_format", type=click.Choice(["table", "json", "csv"]), default="json")
@click.option("--csv-path", type=click.Path(dir_okay=False, writable=True, path_type=str), default=None)
@command_errors
def sitemap_get(site_url: str | None, feedpath: str, output_format: str, csv_path: str | None) -> None:
    """Get one sitemap by feed path."""
    resolved_site = _resolve_site(site_url)
    service = build_search_console_service(write=False)
    item = service.sitemaps().get(siteUrl=resolved_site, feedpath=feedpath).execute()
    records = [_sitemap_to_record(item, stringify_contents=output_format != "json")]
    click.echo(render_records(records, output_format=output_format, csv_path=csv_path))


@sitemap.command("submit")
@click.option("--site", "site_url", required=False, help="Site URL, e.g. sc-domain:example.com")
@click.option(
    "--feedpath",
    "--path",
    "feedpath",
    required=True,
    help="Sitemap URL/path, e.g. https://example.com/sitemap.xml",
)
@command_errors
def sitemap_submit(site_url: str | None, feedpath: str) -> None:
    """Submit (or resubmit) a sitemap."""
    resolved_site = _resolve_site(site_url)
    service = build_search_console_service(write=True)
    service.sitemaps().submit(siteUrl=resolved_site, feedpath=feedpath).execute()
    click.echo(f"Submitted sitemap: {feedpath}")


@sitemap.command("delete")
@click.option("--site", "site_url", required=False, help="Site URL, e.g. sc-domain:example.com")
@click.option(
    "--feedpath",
    "--path",
    "feedpath",
    required=True,
    help="Sitemap URL/path, e.g. https://example.com/sitemap.xml",
)
@command_errors
def sitemap_delete(site_url: str | None, feedpath: str) -> None:
    """Delete a sitemap from a property."""
    resolved_site = _resolve_site(site_url)
    service = build_search_console_service(write=True)
    service.sitemaps().delete(siteUrl=resolved_site, feedpath=feedpath).execute()
    click.echo(f"Deleted sitemap: {feedpath}")


@cli.group()
def url() -> None:
    """Inspect URL index status in Search Console."""


@url.command("inspect")
@click.option("--site", "site_url", required=False, help="Site URL, e.g. sc-domain:example.com")
@click.option(
    "--url",
    "inspection_url",
    required=True,
    help="Fully-qualified URL to inspect, e.g. https://example.com/page",
)
@click.option(
    "--language-code",
    default="en-US",
    show_default=True,
    help="BCP-47 language code for issue messages.",
)
@click.option("--output", "output_format", type=click.Choice(["table", "json", "csv"]), default="table")
@click.option("--csv-path", type=click.Path(dir_okay=False, writable=True, path_type=str), default=None)
@command_errors
def url_inspect(
    site_url: str | None,
    inspection_url: str,
    language_code: str,
    output_format: str,
    csv_path: str | None,
) -> None:
    """Inspect index status of one URL."""
    resolved_site = _resolve_site(site_url)
    service = build_search_console_service(write=False)
    body = {
        "inspectionUrl": inspection_url,
        "siteUrl": resolved_site,
        "languageCode": language_code,
    }
    response = service.urlInspection().index().inspect(body=body).execute()
    inspection_result = response.get("inspectionResult", {})
    if not isinstance(inspection_result, dict):
        inspection_result = {}

    if output_format == "json":
        record = dict(inspection_result)
        record["siteUrl"] = resolved_site
        record["inspectionUrl"] = inspection_url
        click.echo(render_records([record], output_format=output_format, csv_path=csv_path))
        return

    record = _inspection_to_record(
        inspection_result,
        inspection_url=inspection_url,
        site_url=resolved_site,
        stringify_nested=True,
    )
    click.echo(render_records([record], output_format=output_format, csv_path=csv_path))


@cli.group()
def analytics() -> None:
    """Query Search Analytics."""


@analytics.command("query")
@click.option("--site", "site_url", required=False, help="Site URL, e.g. sc-domain:example.com")
@click.option("--start-date", required=True, help="Start date in YYYY-MM-DD")
@click.option("--end-date", required=True, help="End date in YYYY-MM-DD")
@click.option("--dimension", "dimensions", multiple=True, type=click.Choice(sorted(ALLOWED_DIMENSIONS)))
@click.option("--type", "query_type", default="web", type=click.Choice(sorted(ALLOWED_TYPES)))
@click.option(
    "--aggregation-type",
    default="auto",
    type=click.Choice(sorted(ALLOWED_AGGREGATION_TYPES)),
)
@click.option("--row-limit", type=click.IntRange(1, 25000), default=1000)
@click.option("--start-row", type=click.IntRange(min=0), default=0)
@click.option("--data-state", type=click.Choice(sorted(ALLOWED_DATA_STATES)), default="final")
@click.option(
    "--filter",
    "filters",
    multiple=True,
    help="Filter expression in dimension:operator:expression format.",
)
@click.option("--output", "output_format", type=click.Choice(["table", "json", "csv"]), default="table")
@click.option("--csv-path", type=click.Path(dir_okay=False, writable=True, path_type=str), default=None)
@command_errors
def analytics_query(
    site_url: str | None,
    start_date: str,
    end_date: str,
    dimensions: tuple[str, ...],
    query_type: str,
    aggregation_type: str,
    row_limit: int,
    start_row: int,
    data_state: str,
    filters: tuple[str, ...],
    output_format: str,
    csv_path: str | None,
) -> None:
    """Run a Search Analytics query."""
    resolved_site = _resolve_site(site_url)
    request_body = build_query_request(
        start_date=start_date,
        end_date=end_date,
        dimensions=dimensions,
        query_type=query_type,
        aggregation_type=aggregation_type,
        row_limit=row_limit,
        start_row=start_row,
        data_state=data_state,
        filters=filters,
    )

    service = build_search_console_service(write=False)
    response = service.searchanalytics().query(siteUrl=resolved_site, body=request_body).execute()

    records = rows_to_records(response, dimensions)
    click.echo(render_records(records, output_format=output_format, csv_path=csv_path))


if __name__ == "__main__":
    cli()
