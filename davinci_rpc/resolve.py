"""Talks to DaVinci Resolve.

Three sources, from least to most detailed:
  1. Process detection via psutil (always works).
  2. Window titles (Windows only, works with Resolve Free): the main window is
     called "DaVinci Resolve - <project>" and the start screen opens an extra
     "Project Manager" window.
  3. The official scripting API (DaVinciResolveScript) for page, timeline and
     render state. External scripting is a Resolve Studio feature, so on the
     free version we stay with 1 and 2.
"""

import importlib
import logging
import os
import re
import sys
from dataclasses import dataclass

import psutil

log = logging.getLogger(__name__)

PROCESS_NAMES = {"resolve.exe", "resolve"}

# "DaVinci Resolve Studio - MyProject" -> product, project
TITLE_RE = re.compile(r"^(DaVinci Resolve(?: Studio)?) - (.+)$")
# Window shown while the start screen / project manager is open.
MENU_TITLES = {"project manager", "projektmanager", "projektverwaltung"}
# Names Resolve uses for the unsaved placeholder project.
PLACEHOLDER_PROJECTS = {"new project", "untitled project", "neues projekt",
                        "unbenanntes projekt"}


@dataclass
class ResolveState:
    running: bool = False
    api_available: bool = False
    # False when we only know that the process runs (no API, no window info).
    has_info: bool = False
    in_main_menu: bool = False
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


def find_resolve_pids() -> set[int]:
    pids = set()
    for proc in psutil.process_iter(["name"]):
        name = (proc.info.get("name") or "").lower()
        if name in PROCESS_NAMES:
            pids.add(proc.pid)
    return pids


def _visible_window_titles(pids: set[int]) -> list[str]:
    """Titles of the visible top-level windows of the given processes (Windows only)."""
    if not sys.platform.startswith("win"):
        return []
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    titles = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in pids:
                length = user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if buf.value:
                    titles.append(buf.value.strip())
        return True

    try:
        user32.EnumWindows(callback, 0)
    except OSError as e:
        log.debug("Fenstertitel konnten nicht gelesen werden: %s", e)
    return titles


def _apply_window_titles(state: "ResolveState", titles: list[str], use_project: bool):
    menu_open = any(t.lower() in MENU_TITLES for t in titles)
    main_title = next((m for m in map(TITLE_RE.match, titles) if m), None)
    if not menu_open and main_title is None:
        return

    state.has_info = True
    state.in_main_menu = menu_open
    if main_title is not None:
        state.product = main_title.group(1)
        project = main_title.group(2).strip()
        if use_project and project.lower() not in PLACEHOLDER_PROJECTS:
            state.project = project


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
                log.info("Keine Verbindung zur Resolve-API (nur mit DaVinci Resolve "
                         "Studio und 'Externes Scripting: Lokal' verfügbar). "
                         "Nutze die Fenstertitel-Erkennung.")
                self._warned_no_api = True
        return self._resolve

    def get_state(self) -> ResolveState:
        pids = find_resolve_pids()
        if not pids:
            self._resolve = None
            return ResolveState(running=False)

        state = ResolveState(running=True)
        titles = _visible_window_titles(pids)
        resolve = self._connect()
        if resolve is None or not self._read_api(resolve, state):
            _apply_window_titles(state, titles, use_project=True)
        else:
            # The API has no notion of the start screen, the window does.
            _apply_window_titles(state, titles, use_project=False)
        return state

    def _read_api(self, resolve, state: ResolveState) -> bool:

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
            state.has_info = True
            return True
        except Exception as e:
            # Resolve was closed or the connection died; reconnect next time.
            log.debug("Resolve-API-Abfrage fehlgeschlagen: %s", e)
            self._resolve = None
            return False

    @staticmethod
    def _render_progress(project) -> int | None:
        for job in project.GetRenderJobList() or []:
            status = project.GetRenderJobStatus(job.get("JobId")) or {}
            if status.get("JobStatus") == "Rendering":
                return int(status.get("CompletionPercentage", 0))
        return None
