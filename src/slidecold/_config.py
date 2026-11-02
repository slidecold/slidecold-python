"""API key and base URL resolution, read from the config file `slidecold login` (Go CLI) writes (`config.json`: {"apiKey", "baseUrl"})."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

DEFAULT_BASE_URL = "https://slidecold.com/api/v1"


def config_path() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "slidecold" / "config.json"


def load_config() -> Dict[str, Any]:
    try:
        data = json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def resolve(api_key: Optional[str] = None, base_url: Optional[str] = None) -> Tuple[Optional[str], str]:
    """Explicit argument, then SLIDECOLD_API_KEY / SLIDECOLD_BASE_URL, then the config file, then prod."""
    config = load_config()
    key = api_key or os.environ.get("SLIDECOLD_API_KEY") or config.get("apiKey") or None
    url = base_url or os.environ.get("SLIDECOLD_BASE_URL") or config.get("baseUrl") or DEFAULT_BASE_URL
    return key, str(url).rstrip("/")
