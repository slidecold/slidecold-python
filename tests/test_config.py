import json
import os
import types

from slidecold import DEFAULT_BASE_URL, SlideCold, _config


def write_config(data):
    path = _config.config_path()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(data))


def test_config_path_respects_xdg(isolated):
    assert _config.config_path() == isolated / "xdg" / "slidecold" / "config.json"


def test_config_path_windows(isolated, monkeypatch):
    # Patch only the module's view of `os`; pathlib itself must keep using the real OS.
    monkeypatch.setattr(_config, "os", types.SimpleNamespace(name="nt", environ=os.environ))
    path = _config.config_path()
    assert path == isolated / "appdata" / "slidecold" / "config.json"


def test_resolution_order(monkeypatch):
    assert _config.resolve() == (None, DEFAULT_BASE_URL)
    write_config({"apiKey": "cs_config", "baseUrl": "https://config.test/v1/"})
    assert _config.resolve() == ("cs_config", "https://config.test/v1")
    monkeypatch.setenv("SLIDECOLD_API_KEY", "cs_env")
    monkeypatch.setenv("SLIDECOLD_BASE_URL", "https://env.test/v1")
    assert _config.resolve() == ("cs_env", "https://env.test/v1")
    assert _config.resolve("cs_arg", "https://arg.test/v1") == ("cs_arg", "https://arg.test/v1")
    client = SlideCold()
    assert (client.api_key, client.base_url) == ("cs_env", "https://env.test/v1")


def test_invalid_config_is_ignored():
    path = _config.config_path()
    path.parent.mkdir(parents=True)
    path.write_text("{not json")
    assert _config.load_config() == {}
