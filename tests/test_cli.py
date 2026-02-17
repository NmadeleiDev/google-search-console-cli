from pathlib import Path

from click.testing import CliRunner

from gsc_cli.auth import AuthError
from gsc_cli.cli import cli


class ExecuteResult:
    def __init__(self, payload=None):
        self.payload = payload or {}

    def execute(self):
        return self.payload


class FakeSitesResource:
    def __init__(self, entries=None, get_item=None):
        self.entries = entries or []
        self.get_item = get_item
        self.last_get = None
        self.last_add = None

    def list(self):
        return ExecuteResult({"siteEntry": self.entries})

    def get(self, siteUrl):
        self.last_get = siteUrl
        return ExecuteResult(self.get_item or {"siteUrl": siteUrl})

    def add(self, siteUrl):
        self.last_add = siteUrl
        return ExecuteResult({})


class FakeSearchAnalyticsResource:
    def __init__(self, response=None):
        self.response = response or {"rows": []}
        self.last_query = None

    def query(self, siteUrl, body):
        self.last_query = {"siteUrl": siteUrl, "body": body}
        return ExecuteResult(self.response)


class FakeService:
    def __init__(self, sites_resource=None, analytics_resource=None):
        self._sites_resource = sites_resource or FakeSitesResource()
        self._analytics_resource = analytics_resource or FakeSearchAnalyticsResource()

    def sites(self):
        return self._sites_resource

    def searchanalytics(self):
        return self._analytics_resource


def test_site_list_table(monkeypatch):
    runner = CliRunner()
    fake_service = FakeService(
        sites_resource=FakeSitesResource(
            entries=[
                {
                    "siteUrl": "sc-domain:example.com",
                    "permissionLevel": "siteOwner",
                }
            ]
        )
    )

    monkeypatch.setattr(
        "gsc_cli.cli.build_search_console_service",
        lambda write=False: fake_service,
    )

    result = runner.invoke(cli, ["site", "list"])

    assert result.exit_code == 0
    assert "sc-domain:example.com" in result.output
    assert "siteOwner" in result.output


def test_site_add_uses_write_scope(monkeypatch):
    runner = CliRunner()
    fake_service = FakeService()
    write_flags = []

    def fake_builder(write=False):
        write_flags.append(write)
        return fake_service

    monkeypatch.setattr("gsc_cli.cli.build_search_console_service", fake_builder)

    result = runner.invoke(
        cli,
        ["site", "add", "--site", "sc-domain:example.com"],
    )

    assert result.exit_code == 0
    assert write_flags == [True]
    assert fake_service.sites().last_add == "sc-domain:example.com"


def test_site_get_uses_default_site(monkeypatch):
    runner = CliRunner()
    fake_service = FakeService()

    monkeypatch.setattr("gsc_cli.cli.get_default_site", lambda: "sc-domain:example.com")
    monkeypatch.setattr("gsc_cli.cli.build_search_console_service", lambda write=False: fake_service)

    result = runner.invoke(cli, ["site", "get"])

    assert result.exit_code == 0
    assert fake_service.sites().last_get == "sc-domain:example.com"


def test_site_get_without_site_or_default(monkeypatch):
    runner = CliRunner()

    monkeypatch.setattr("gsc_cli.cli.get_default_site", lambda: None)

    result = runner.invoke(cli, ["site", "get"])

    assert result.exit_code == 2
    assert "No site specified" in result.output


def test_analytics_query_builds_request(monkeypatch):
    runner = CliRunner()
    analytics_resource = FakeSearchAnalyticsResource(
        response={
            "rows": [
                {
                    "keys": ["brand term"],
                    "clicks": 2,
                    "impressions": 20,
                    "ctr": 0.1,
                    "position": 3.2,
                }
            ]
        }
    )
    fake_service = FakeService(analytics_resource=analytics_resource)

    monkeypatch.setattr(
        "gsc_cli.cli.build_search_console_service",
        lambda write=False: fake_service,
    )

    result = runner.invoke(
        cli,
        [
            "analytics",
            "query",
            "--site",
            "sc-domain:example.com",
            "--start-date",
            "2026-01-01",
            "--end-date",
            "2026-01-31",
            "--dimension",
            "query",
            "--filter",
            "query:contains:brand",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"query": "brand term"' in result.output

    assert analytics_resource.last_query is not None
    assert analytics_resource.last_query["siteUrl"] == "sc-domain:example.com"
    assert analytics_resource.last_query["body"]["dimensions"] == ["query"]
    assert analytics_resource.last_query["body"]["dimensionFilterGroups"][0]["filters"][0] == {
        "dimension": "query",
        "operator": "contains",
        "expression": "brand",
    }


def test_analytics_query_uses_default_site(monkeypatch):
    runner = CliRunner()
    analytics_resource = FakeSearchAnalyticsResource(response={"rows": []})
    fake_service = FakeService(analytics_resource=analytics_resource)

    monkeypatch.setattr("gsc_cli.cli.get_default_site", lambda: "sc-domain:example.com")
    monkeypatch.setattr("gsc_cli.cli.build_search_console_service", lambda write=False: fake_service)

    result = runner.invoke(
        cli,
        [
            "analytics",
            "query",
            "--start-date",
            "2026-01-01",
            "--end-date",
            "2026-01-31",
        ],
    )

    assert result.exit_code == 0
    assert analytics_resource.last_query is not None
    assert analytics_resource.last_query["siteUrl"] == "sc-domain:example.com"


def test_analytics_query_invalid_filter(monkeypatch):
    runner = CliRunner()
    fake_service = FakeService()

    monkeypatch.setattr(
        "gsc_cli.cli.build_search_console_service",
        lambda write=False: fake_service,
    )

    result = runner.invoke(
        cli,
        [
            "analytics",
            "query",
            "--site",
            "sc-domain:example.com",
            "--start-date",
            "2026-01-01",
            "--end-date",
            "2026-01-31",
            "--filter",
            "invalid:equals:value",
        ],
    )

    assert result.exit_code == 2
    assert "Unsupported filter dimension" in result.output


def test_config_set_and_get_default_site():
    runner = CliRunner()

    set_result = runner.invoke(cli, ["config", "set", "default-site", "sc-domain:example.com"])
    get_result = runner.invoke(cli, ["config", "get", "default-site"])

    assert set_result.exit_code == 0
    assert "Set default-site" in set_result.output
    assert get_result.exit_code == 0
    assert get_result.output.strip() == "sc-domain:example.com"


def test_auth_login_invokes_helper(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    client_secret = tmp_path / "client_secret.json"
    client_secret.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "gsc_cli.cli.login_with_client_secret",
        lambda client_secret, write, launch_browser: tmp_path / "credentials.json",
    )

    result = runner.invoke(
        cli,
        [
            "auth",
            "login",
            "--client-secret",
            str(client_secret),
            "--no-launch-browser",
        ],
    )

    assert result.exit_code == 0
    assert "Saved credentials" in result.output


def test_auth_whoami_missing(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr("gsc_cli.cli.stored_credentials_info", lambda: None)

    result = runner.invoke(cli, ["auth", "whoami"])

    assert result.exit_code == 2
    assert "No local OAuth credentials" in result.output


def test_doctor_success(monkeypatch):
    runner = CliRunner()
    fake_service = FakeService(sites_resource=FakeSitesResource(entries=[{"siteUrl": "a"}]))

    monkeypatch.setattr("gsc_cli.cli.get_default_site", lambda: "sc-domain:example.com")
    monkeypatch.setattr(
        "gsc_cli.cli.stored_credentials_info",
        lambda: {
            "path": "/tmp/creds.json",
            "scopes": ["https://www.googleapis.com/auth/webmasters"],
            "has_refresh_token": True,
            "client_id": "x",
        },
    )
    monkeypatch.setattr("gsc_cli.cli.load_credentials", lambda write=False: object())
    monkeypatch.setattr("gsc_cli.cli.build_search_console_service", lambda write=False: fake_service)

    result = runner.invoke(cli, ["doctor"])

    assert result.exit_code == 0
    assert "api-connectivity" in result.output
    assert "sites.list succeeded" in result.output


def test_doctor_failure(monkeypatch):
    runner = CliRunner()

    monkeypatch.setattr("gsc_cli.cli.get_default_site", lambda: None)
    monkeypatch.setattr("gsc_cli.cli.stored_credentials_info", lambda: None)

    def fail_load(write=False):
        raise AuthError("bad creds")

    monkeypatch.setattr("gsc_cli.cli.load_credentials", fail_load)
    monkeypatch.setattr(
        "gsc_cli.cli.build_search_console_service",
        lambda write=False: (_ for _ in ()).throw(RuntimeError("no network")),
    )

    result = runner.invoke(cli, ["doctor"])

    assert result.exit_code == 1
    assert "auth-refresh" in result.output
    assert "bad creds" in result.output
