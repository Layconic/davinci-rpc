"""Turns a ResolveState into a Discord Rich Presence activity."""

import logging
import time

from pypresence import Presence
from pypresence.exceptions import DiscordNotFound, InvalidID, PipeClosed

from .resolve import ResolveState

log = logging.getLogger(__name__)

PAGE_LABELS = {
    "media": "Media",
    "cut": "Cut",
    "edit": "Edit",
    "fusion": "Fusion",
    "color": "Color",
    "fairlight": "Fairlight",
    "deliver": "Deliver",
}

PAGE_VERBS = {
    "media": "Organisiert Medien",
    "cut": "Schneidet",
    "edit": "Schneidet",
    "fusion": "Erstellt Effekte",
    "color": "Color Grading",
    "fairlight": "Bearbeitet Audio",
    "deliver": "Exportiert",
}


def _limit(text: str) -> str:
    """Discord requires 2-128 characters per field."""
    text = text.strip()
    if len(text) > 128:
        text = text[:125] + "..."
    return text.ljust(2)


class PresenceBuilder:
    def __init__(self, config: dict):
        self.config = config
        self._start: int | None = None
        self._last_project: str | None = None

    def reset(self):
        self._start = None
        self._last_project = None

    def build(self, state: ResolveState) -> dict:
        cfg = self.config
        now = int(time.time())
        if self._start is None:
            self._start = now
        if (cfg["reset_timer_on_project_change"] and state.project
                and state.project != self._last_project):
            self._start = now
        self._last_project = state.project

        large_text = f"{state.product} {state.version}".strip()
        activity = {"large_image": cfg["large_image"], "large_text": _limit(large_text)}

        if state.rendering and cfg["show_render_progress"]:
            details = "Rendert"
            if state.render_progress is not None:
                details += f" ({state.render_progress}%)"
        elif state.page and cfg["show_page"]:
            details = PAGE_VERBS.get(state.page, "Bearbeitet")
        else:
            details = "Bearbeitet ein Projekt" if state.project else "Im Projektmanager"
        if not state.api_available:
            details = "DaVinci Resolve geöffnet"
        activity["details"] = _limit(details)

        parts = []
        if cfg["show_project"] and state.project:
            parts.append(state.project)
        if cfg["show_timeline"] and state.timeline:
            parts.append(state.timeline)
        if parts:
            activity["state"] = _limit(" · ".join(parts))

        if state.page and cfg["show_page"] and cfg["use_page_icons"]:
            activity["small_image"] = f"page_{state.page}"
            activity["small_text"] = f"{PAGE_LABELS.get(state.page, state.page)} Page"

        if cfg["show_elapsed_time"]:
            activity["start"] = self._start

        buttons = [b for b in cfg.get("buttons", []) if b.get("label") and b.get("url")][:2]
        if buttons:
            activity["buttons"] = buttons
        return activity


class DiscordPresence:
    def __init__(self, client_id: str):
        self.client_id = client_id
        self._rpc: Presence | None = None
        self._last_activity: dict | None = None

    @property
    def connected(self) -> bool:
        return self._rpc is not None

    def connect(self) -> bool:
        try:
            rpc = Presence(self.client_id)
            rpc.connect()
            self._rpc = rpc
            log.info("Mit Discord verbunden.")
            return True
        except DiscordNotFound:
            log.debug("Discord läuft nicht.")
        except InvalidID:
            log.error("Ungültige Discord client_id: %s", self.client_id)
        except Exception as e:
            log.debug("Discord-Verbindung fehlgeschlagen: %s", e)
        self._rpc = None
        return False

    def update(self, activity: dict):
        if activity == self._last_activity:
            return
        if not self._rpc and not self.connect():
            return
        try:
            self._rpc.update(**activity)
            self._last_activity = activity
            log.info("Status aktualisiert: %s | %s",
                     activity.get("details"), activity.get("state", ""))
        except (PipeClosed, InvalidID, ConnectionError, OSError) as e:
            log.warning("Verbindung zu Discord verloren (%s), verbinde neu...", e)
            self._drop()

    def clear(self):
        if self._rpc and self._last_activity is not None:
            try:
                self._rpc.clear()
                log.info("Status entfernt (Resolve geschlossen).")
            except Exception:
                self._drop()
        self._last_activity = None

    def close(self):
        if self._rpc:
            try:
                self._rpc.clear()
                self._rpc.close()
            except Exception:
                pass
        self._rpc = None

    def _drop(self):
        try:
            if self._rpc:
                self._rpc.close()
        except Exception:
            pass
        self._rpc = None
        self._last_activity = None
