import pytest


@pytest.fixture(autouse=True)
def isolate_user_files(tmp_path, monkeypatch):
    config_dir = tmp_path / "gsc-cli"
    monkeypatch.setenv("GSC_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("GSC_APP_CONFIG_FILE", str(config_dir / "config.json"))
    monkeypatch.setenv("GSC_CREDENTIALS_FILE", str(config_dir / "credentials.json"))
