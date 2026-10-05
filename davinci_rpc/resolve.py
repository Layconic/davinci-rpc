"""Talks to DaVinci Resolve.

Two layers:
  1. Process detection via psutil (always works, also with Resolve Free).
  2. The official Resolve scripting API (DaVinciResolveScript) for project,
     timeline, page and render state. If it is unavailable we fall back to 1.
"""

import importlib
import logging
import os
import sys
from dataclasses import dataclass

import psutil

log = logging.getLogger(__name__)

PROCESS_NAMES = {"resolve.exe", "resolve"}


@dataclass
class ResolveState:
    running: bool = False
    api_available: bool = False
    product: str = "DaVinci Resolve"
    version: str = ""
    page: str | None = None
    project: str | None = None
    timeline: str | None = None
    rendering: bool = False
    render_progress: int | None = None


def _default_paths() -> tuple[str, str]:
    """Returns (scripting modules dir, fusionscript library) for this OS."""
    if sys.platform.startswith("win"):
        program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        api = os.path.join(program_data, "Blackmagic Design", "DaVinci Resolve",
                           "Support", "Developer", "Scripting")
        lib = os.path.join(program_files, "Blackmagic Design", "DaVinci Resolve",
                           "fusionscript.dll")
    elif sys.platform == "darwin":
        api = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
        lib = ("/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/"
               "Libraries/Fusion/fusionscript.so")
    else:
        api = "/opt/resolve/Developer/Scripting"
        lib = "/opt/resolve/libs/Fusion/fusionscript.so"
    return api, lib


def _load_script_module():
    """Imports DaVinciResolveScript, returns None if that is not possible."""
    api, lib = _default_paths()
    api = os.environ.setdefault("RESOLVE_SCRIPT_API", api)
    os.environ.setdefault("RESOLVE_SCRIPT_LIB", lib)

    modules_dir = os.path.join(api, "Modules")
    if not os.path.isfile(os.path.join(modules_dir, "DaVinciResolveScript.py")):
        log.warning("Resolve-Scripting-Modul nicht gefunden: %s", modules_dir)
        return None
    if modules_dir not in sys.path:
        sys.path.append(modules_dir)
    try:
        # The module replaces itself in sys.modules with fusionscript,
        # so it has to be imported normally (not via a file spec).
        return importlib.import_module("DaVinciResolveScript")
    except Exception as e:  # fusionscript may not support this Python version
        log.warning("Resolve-Scripting-API konnte nicht geladen werden: %s", e)
        return None


def is_resolve_running() -> bool:
    for proc in psutil.process_iter(["name"]):
        name = (proc.info.get("name") or "").lower()
        if name in PROCESS_NAMES:
            return True
    return False


class ResolveClient:
    def __init__(self):
        self._module = _load_script_module()
        self._resolve = None
        self._warned_no_api = False

    def _connect(self):
        if self._module is None:
            return None
        if self._resolve is None:
            try:
                self._resolve = self._module.scriptapp("Resolve")
            except Exception as e:
                log.debug("scriptapp fehlgeschlagen: %s", e)
                self._resolve = None
            if self._resolve is None and not self._warned_no_api:
                log.warning("Keine Verbindung zur Resolve-API. Ist in Resolve unter "
                            "Einstellungen > System > Allgemein > 'Externes Scripting' "
                            "auf 'Lokal' gestellt? Laufe im Basis-Modus weiter.")
                self._warned_no_api = True
        return self._resolve

    def get_state(self) -> ResolveState:
        if not is_resolve_running():
            self._resolve = None
            return ResolveState(running=False)

        state = ResolveState(running=True)
        resolve = self._connect()
        if resolve is None:
            return state

        try:
            state.product = resolve.GetProductName() or state.product
            state.version = resolve.GetVersionString() or ""
            state.page = resolve.GetCurrentPage()

            project = resolve.GetProjectManager().GetCurrentProject()
            if project:
                state.project = project.GetName()
                timeline = project.GetCurrentTimeline()
                if timeline:
                    state.timeline = timeline.GetName()
                state.rendering = bool(project.IsRenderingInProgress())
                if state.rendering:
                    state.render_progress = self._render_progress(project)
            state.api_available = True
        except Exception as e:
            # Resolve was closed or the connection died; reconnect next time.
            log.debug("Resolve-API-Abfrage fehlgeschlagen: %s", e)
            self._resolve = None
        return state

    @staticmethod
    def _render_progress(project) -> int | None:
        for job in project.GetRenderJobList() or []:
            status = project.GetRenderJobStatus(job.get("JobId")) or {}
            if status.get("JobStatus") == "Rendering":
                return int(status.get("CompletionPercentage", 0))
        return None
