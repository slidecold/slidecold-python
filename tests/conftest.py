import pytest

from slidecold import _client

BASE = "https://api.test/v1"


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    """No real env, config or sleeping in tests."""
    for var in ("SLIDECOLD_API_KEY", "SLIDECOLD_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(_client.time, "sleep", lambda s: None)

    async def no_sleep(s):
        return None

    monkeypatch.setattr(_client.asyncio, "sleep", no_sleep)
    return tmp_path


@pytest.fixture
def anyio_backend():
    return "asyncio"
