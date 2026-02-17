from gsc_cli.config import get_default_site, load_config, set_default_site


def test_default_config_is_empty():
    assert load_config() == {}
    assert get_default_site() is None


def test_set_and_get_default_site():
    path = set_default_site("sc-domain:example.com")
    assert path.exists()
    assert get_default_site() == "sc-domain:example.com"
