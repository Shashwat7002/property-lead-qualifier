"""
Central settings loader (P0-03).

Secrets are NEVER stored in tracked source. Resolution order per field:
    1. environment variable (or .env via python-dotenv if installed)
    2. local_settings.json   (gitignored — written by the Settings panel)
    3. legacy config.py      (gitignored — back-compat for existing installs)
    4. built-in default

`settings` is a singleton with attributes (so existing `cfg.FMLS_API_KEY` /
`cfg.DEMO_MODE` access keeps working) plus `.reload()` and `.save_local()`.
The Settings panel writes to local_settings.json — JSON, never executable Python.
"""

import json
import os
from pathlib import Path

try:                                   # optional — .env support if python-dotenv present
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

_BASE = Path(__file__).resolve().parent
_LOCAL_JSON = _BASE / "local_settings.json"

_SECRET_FIELDS = (
    "FMLS_API_KEY", "FMLS_USERNAME", "FMLS_PASSWORD",
    "FRED_API_KEY", "CENSUS_API_KEY",
    "GSCCCA_USERNAME", "GSCCCA_PASSWORD",
)


def _truthy(v) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


class Settings:
    def __init__(self):
        self.reload()

    def reload(self):
        legacy = self._load_legacy_config()
        local = self._load_local_json()

        def pick(key, default=""):
            env = os.getenv(key)
            if env not in (None, ""):
                return env
            if local.get(key) not in (None, ""):
                return local[key]
            if legacy.get(key) not in (None, ""):
                return legacy[key]
            return default

        for k in _SECRET_FIELDS:
            setattr(self, k, pick(k))

        # DEMO_MODE: env > local > legacy > True (safe default).
        if os.getenv("DEMO_MODE") not in (None, ""):
            self.DEMO_MODE = _truthy(os.getenv("DEMO_MODE"))
        elif "DEMO_MODE" in local:
            self.DEMO_MODE = bool(local["DEMO_MODE"])
        elif "DEMO_MODE" in legacy:
            self.DEMO_MODE = bool(legacy["DEMO_MODE"])
        else:
            self.DEMO_MODE = True

        try:
            self.FMLS_PRICE_CEILING = int(os.getenv("FMLS_PRICE_CEILING", "0")) or None
        except ValueError:
            self.FMLS_PRICE_CEILING = None

    @staticmethod
    def _load_legacy_config() -> dict:
        """Back-compat: read a local (gitignored) config.py if one exists."""
        try:
            import importlib
            import config as _c
            importlib.reload(_c)
            out = {k: getattr(_c, k, "") for k in _SECRET_FIELDS}
            out["DEMO_MODE"] = getattr(_c, "DEMO_MODE", True)
            return out
        except Exception:
            return {}

    @staticmethod
    def _load_local_json() -> dict:
        if _LOCAL_JSON.exists():
            try:
                return json.loads(_LOCAL_JSON.read_text())
            except Exception:
                return {}
        return {}

    def save_local(self, updates: dict):
        """Persist config to the gitignored local_settings.json (JSON, not Python).
        Only keys with non-None values are written; existing values are preserved."""
        data = self._load_local_json()
        for key, value in updates.items():
            if value is not None:
                data[key] = value
        _LOCAL_JSON.write_text(json.dumps(data, indent=2) + "\n")
        self.reload()


settings = Settings()
