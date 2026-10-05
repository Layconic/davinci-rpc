"""Loads the user configuration (config.json) and fills in defaults."""

import json
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULTS = {
    "client_id": "",
    "update_interval": 15,
    "show_project": True,
    "show_timeline": True,
    "show_page": True,
    "show_elapsed_time": True,
    "reset_timer_on_project_change": False,
    "show_render_progress": True,
    "large_image": "davinci",
    "use_page_icons": True,
    "buttons": [],
}

# Discord only accepts updates every 15 seconds, faster is pointless.
MIN_UPDATE_INTERVAL = 15


def app_dir() -> Path:
    """Directory next to the script or the frozen .exe."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def load_config(path: str | None = None) -> dict:
    config_path = Path(path) if path else app_dir() / "config.json"
    config = dict(DEFAULTS)

    if config_path.is_file():
        with open(config_path, encoding="utf-8") as f:
            config.update(json.load(f))
        log.info("Konfiguration geladen: %s", config_path)
    else:
        log.warning("Keine config.json gefunden (%s), nutze Standardwerte.", config_path)

    # Environment variable wins, handy for testing.
    config["client_id"] = os.environ.get("DAVINCI_RPC_CLIENT_ID", config["client_id"])
    config["update_interval"] = max(MIN_UPDATE_INTERVAL, int(config["update_interval"]))
    return config
