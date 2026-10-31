"""Window control: close, minimize, maximize or restore any open app window."""
import ctypes
import os

import psutil
import win32con
import win32gui
import win32process

from core import tools
from core.tools import APP_ALIASES

# Windows that belong to the desktop itself, not to real apps
IGNORED_CLASSES = {
    "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
    "Windows.UI.Core.CoreWindow",
}

# Words that mean "the app we just worked with" instead of a real app name
GENERIC_WORDS = {"", "this", "it", "that", "current", "active", "app",
                 "application", "window", "program", "front"}

ACTION_WORDS = {
    "close": "close", "exit": "close", "quit": "close",
    "minimize": "minimize", "minimise": "minimize", "hide": "minimize",
    "maximize": "maximize", "maximise": "maximize", "fullscreen": "maximize",
    "restore": "restore", "show": "restore",
}


def _is_cloaked(hwnd) -> bool:
    """Background UWP apps are 'cloaked': Windows lists them, but they are not on screen."""
    cloaked = ctypes.c_int(0)
    try:
        ctypes.windll.dwmapi.DwmGetWindowAttribute(  # 14 = DWMWA_CLOAKED
            hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
        )
    except Exception:
        return False
    return cloaked.value != 0


def list_windows() -> list:
    """All real app windows, top-most first. Our own window is never included."""
    own_pid = os.getpid()
    found = []

    def handler(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd).strip()
            if not title or win32gui.GetClassName(hwnd) in IGNORED_CLASSES:
                return
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if style & win32con.WS_EX_TOOLWINDOW or _is_cloaked(hwnd):
                return
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid == own_pid:
                return
            try:
                process = psutil.Process(pid).name()
            except Exception:
                process = ""
            found.append({"hwnd": hwnd, "title": title, "process": process})
        except Exception:
            return

    win32gui.EnumWindows(handler, None)
    return found


def _label(window: dict) -> str:
    """A short, speakable name for a window."""
    process = window["process"].lower().removesuffix(".exe")
    if process in ("", "applicationframehost"):
        return window["title"][:30]
    return process


def _match(windows: list, query: str):
    """Process name is checked first (more reliable), then the window title."""
    for w in windows:
        if query in w["process"].lower().removesuffix(".exe"):
            return w
    for w in windows:
        if query in w["title"].lower():
            return w
    return None


def _target_window(app_name: str, action: str):
    """Returns (window or None, all windows, was_generic)."""
    windows = list_windows()
    query = app_name.strip().lower()
    query = APP_ALIASES.get(query, query)
    generic = query in GENERIC_WORDS
    if generic:
        remembered = tools.LAST_OPENED          # what the assistant opened last
        if remembered:
            window = _match(windows, remembered)
            if window:
                return window, windows, True
        if action == "close":                   # never guess when closing
            return None, windows, True
        return (windows[0] if windows else None), windows, True
    return _match(windows, query), windows, False


def _bring_to_front(hwnd):
    ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)  # tap Alt so Windows allows the focus change
    ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass


def control_window(action: str, app_name: str = "") -> str:
    act = ACTION_WORDS.get(str(action).strip().lower().replace(" ", ""))
    if act is None:
        return "Should I close, minimize, maximize or restore it?"

    window, windows, generic = _target_window(str(app_name), act)
    if window is None:
        if generic and act == "close":
            return ("I'm not sure which app you mean. "
                    "Please say its name, like 'close chrome'.")
        names = ", ".join(dict.fromkeys(_label(w) for w in windows[:8]))
        if generic:
            return "I couldn't find an open app window."
        return f"I couldn't find an open window for '{app_name}'. Open apps: {names}."

    hwnd, label = window["hwnd"], _label(window)
    try:
        if act == "close":
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)  # polite close request
            return f"Asked {label} to close. If it has unsaved work, it may ask you to save first."
        if act == "minimize":
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            return f"Minimized {label}."
        if act == "maximize":
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            _bring_to_front(hwnd)
            return f"Maximized {label}."
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        _bring_to_front(hwnd)
        return f"Restored {label}."
    except Exception as e:
        return f"I couldn't do that with {label}: {e}"


WINDOW_TOOLS = {
    "control_window": control_window,
}