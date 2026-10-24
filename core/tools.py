import os
import shutil
import subprocess
import webbrowser
from pathlib import Path
import time
import json
import re
import difflib
import urllib.request
import urllib.parse
from datetime import datetime

import psutil

# ---------- SYSTEM INFO ----------

def get_ram_info() -> str:
    mem = psutil.virtual_memory()
    gb = 1024 ** 3
    return (
        f"Total RAM: {mem.total / gb:.2f} GB, "
        f"Used: {mem.used / gb:.2f} GB ({mem.percent}%), "
        f"Available: {mem.available / gb:.2f} GB"
    )


def get_disk_info(drive: str = "C") -> str:
    drive = drive.strip().rstrip(":\\/").upper()
    path = f"{drive}:\\"
    try:
        usage = shutil.disk_usage(path)
    except Exception:
        return f"Drive {drive}: not found."
    gb = 1024 ** 3
    return (
        f"Drive {drive}: Total {usage.total / gb:.1f} GB, "
        f"Used {usage.used / gb:.1f} GB, Free {usage.free / gb:.1f} GB"
    )


def list_running_apps() -> str:
    names = set()
    for proc in psutil.process_iter(["name"]):
        name = proc.info["name"]
        if name:
            names.add(name)
    names = sorted(names, key=str.lower)
    return f"{len(names)} running processes:\n" + "\n".join(names[:40])


# ---------- OPEN THINGS ----------

APP_ALIASES = {
    "vscode": "visual studio code",
    "vs code": "visual studio code",
    "cmd": "command prompt",
    "terminal": "windows terminal",
    "ppt": "powerpoint",
    "browser": "chrome",
}

_APP_CACHE = []

def _load_installed_apps() -> list:
    """Windows ki saari installed apps ki list (ek baar load hoti hai)."""
    global _APP_CACHE
    if _APP_CACHE:
        return _APP_CACHE
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
                "Get-StartApps | ConvertTo-Json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=40,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        data = json.loads(result.stdout)
        if isinstance(data, dict):
            data = [data]
        _APP_CACHE = [{"name": a["Name"], "id": a["AppID"]} for a in data]
    except Exception:
        _APP_CACHE = []
    return _APP_CACHE


def _find_app(query: str):
    apps = _load_installed_apps()
    q = query.strip().lower()
    q = APP_ALIASES.get(q, q)
    if not q or not apps:
        return None

    # exact same name
    for a in apps:
        if a["name"].lower() == q:
            return a
    #all words should be in the name
    whole = [a for a in apps if re.search(rf"\b{re.escape(q)}\b", a["name"].lower())]
    if whole:
        return min(whole, key=lambda a: len(a["name"]))
    #a part of the name
    part = [a for a in apps if q in a["name"].lower()]
    if part:
        return min(part, key=lambda a: len(a["name"]))
    # 4) Small spelling mistakes only. The cutoff is strict so that an unknown
    # name like "google drive" never gets matched to "Google Chrome".
    names = {a["name"].lower(): a for a in apps}
    close = difflib.get_close_matches(q, names.keys(), n=1, cutoff=0.85)
    return names[close[0]] if close else None


def open_app(app_name: str, browser: str = "") -> str:
    app = _find_app(app_name)
    if app is None:
        # Not an installed app, so treat the name as a website instead
        return open_website(app_name, browser)
    try:
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app['id']}"])
        return f"Opened {app['name']}."
    except Exception as e:
        return f"Could not open {app['name']}: {e}"


BROWSER_COMMANDS = {"chrome": "chrome", "edge": "msedge", "firefox": "firefox"}
PLACEHOLDER_DOMAINS = ("example.com", "example.org", "yourwebsite.com", "website.com")


def _resolve_url(name: str) -> str:
    """Turn a site name into a URL.
    - full URLs are used as they are
    - names with a dot ("linkedin.com") get https:// added
    - plain names ("google drive") use Google's "I'm Feeling Lucky",
      which opens the top search result directly
    """
    name = name.strip()
    if name.startswith(("http://", "https://")):
        return name
    if "." in name and " " not in name:
        return "https://" + name
    query = urllib.parse.quote_plus(name + " official site")
    return f"https://www.google.com/search?btnI=1&q={query}"


def open_website(url: str, browser: str = "") -> str:
    url = url.strip()
    if not url:
        return "Which website should I open?"
    if any(p in url.lower() for p in PLACEHOLDER_DOMAINS):
        return "I'm not sure which website you mean. Tell me its name, like 'open linkedin on chrome'."
    full_url = _resolve_url(url)
    command = BROWSER_COMMANDS.get(browser.strip().lower())
    try:
        if command:
            subprocess.Popen(f'start "" {command} "{full_url}"', shell=True)
        else:
            webbrowser.open(full_url)
        return f"Opened {url}."
    except Exception as e:
        return f"Could not open website: {e}"


SETTINGS_PAGES = {
    "bluetooth": "ms-settings:bluetooth",
    "wifi": "ms-settings:network-wifi",
    "display": "ms-settings:display",
    "sound": "ms-settings:sound",
    "battery": "ms-settings:batterysaver",
    "storage": "ms-settings:storagesense",
    "apps": "ms-settings:appsfeatures",
    "update": "ms-settings:windowsupdate",
}


def open_settings(page: str) -> str:
    key = page.strip().lower()
    uri = SETTINGS_PAGES.get(key)
    if uri is None:
        return f"Unknown settings page. Available: {', '.join(SETTINGS_PAGES)}"
    os.startfile(uri)
    return f"Opened {key} settings."


# ---------- FILES & FOLDERS ----------

QUICK_FOLDERS = [
    Path.home() / "Desktop",
    Path.home() / "Documents",
    Path.home() / "Downloads",
]

SKIP_DIRS = {
    "node_modules", "venv", ".git", "__pycache__", "site-packages",
    "winlibs", "mingw64",
    "windows", "program files", "program files (x86)", "programdata",
    "appdata", "$recycle.bin", "system volume information",
    "msocache", "recovery", "perflogs",
}

LAST_RESULTS = []


def _get_drives() -> list:
    """Computer ki saari drives khud dhoondta hai (C:\\, D:\\, USB waghera)."""
    drives = []
    for part in psutil.disk_partitions(all=False):
        if part.fstype and "cdrom" not in part.opts.lower():
            drives.append(Path(part.mountpoint))
    return drives


def _walk_search(roots, words, kind, matches, max_results, deadline, skip_paths=()):
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirs, files in os.walk(root):
            if time.time() > deadline:
                return
            dirs[:] = [
                d for d in dirs
                if d.lower() not in SKIP_DIRS
                and not d.startswith(".")
                and str(Path(dirpath) / d).lower() not in skip_paths
            ]
            names = files if kind == "file" else dirs
            for n in names:
                if all(w in n.lower() for w in words):
                    matches.append(str(Path(dirpath) / n))
                    if len(matches) >= max_results:
                        return


def _find_items(query: str, kind: str = "file", folder: str = "",
                max_results: int = 30, max_seconds: int = 25) -> list:
    """kind = 'file' ya 'folder'."""
    words = query.strip().lower().split()
    matches = []
    deadline = time.time() + max_seconds

    
    if folder:
        _walk_search([Path.home() / folder], words, kind, matches, max_results, deadline)
        return matches

  
    _walk_search(QUICK_FOLDERS, words, kind, matches, max_results, deadline)
    if matches:
        return matches

    
    already_scanned = {str(p).lower() for p in QUICK_FOLDERS}
    _walk_search(_get_drives(), words, kind, matches, max_results, deadline, already_scanned)
    return matches


def _format_results(matches: list) -> str:
    return "\n".join(f"{i}. {path}" for i, path in enumerate(matches, start=1))


def _search(query: str, kind: str, folder: str = "") -> str:
    global LAST_RESULTS
    matches = _find_items(query, kind, folder)
    if not matches:
        return f"No {kind}s found matching '{query}'."
    LAST_RESULTS = matches
    return (
        f"Found {len(matches)} {kind}(s):\n"
        + _format_results(matches)
        + "\n\nTell me which one to open, e.g. 'open number 2'."
    )


def _open(query: str, kind: str) -> str:
    global LAST_RESULTS
    matches = _find_items(query, kind)
    if not matches:
        return f"Could not find any {kind} matching '{query}'."
    if len(matches) == 1:
        os.startfile(matches[0])
        return f"Opened: {matches[0]}"
    LAST_RESULTS = matches
    return (
        f"I found {len(matches)} {kind}s matching '{query}':\n"
        + _format_results(matches)
        + "\n\nWhich one should I open? Say e.g. 'open number 2'."
    )


def search_files(query: str, folder: str = "") -> str:
    return _search(query, "file", folder)


def search_folders(query: str, folder: str = "") -> str:
    return _search(query, "folder", folder)


def open_file(query: str) -> str:
    return _open(query, "file")


def open_folder(query: str) -> str:
    return _open(query, "folder")


def open_result(number) -> str:
    """Opens a file or folder from the most recent list by its number."""
    if not LAST_RESULTS:
        return "There is no search list yet. Search first."
    try:
        index = int(number) - 1
    except (TypeError, ValueError):
        return "Please give me a valid number."
    if index < 0 or index >= len(LAST_RESULTS):
        return f"Please choose a number between 1 and {len(LAST_RESULTS)}."
    path = LAST_RESULTS[index]
    os.startfile(path)
    return f"Opened: {path}"

# ---------- WEATHER & TIME ----------

DEFAULT_CITY = "Lahore"   

WEATHER_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "foggy",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    56: "freezing drizzle", 57: "freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    66: "freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "light rain showers", 81: "rain showers", 82: "heavy rain showers",
    85: "snow showers", 86: "snow showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail",
}


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def get_weather(city: str = "") -> str:
    city = city.strip() or DEFAULT_CITY
    try:
        geo = _get_json(
            "https://geocoding-api.open-meteo.com/v1/search?"
            + urllib.parse.urlencode({"name": city, "count": 1})
        )
        results = geo.get("results")
        if not results:
            return f"I couldn't find a city named '{city}'."
        place = results[0]

        data = _get_json(
            "https://api.open-meteo.com/v1/forecast?"
            + urllib.parse.urlencode({
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": "temperature_2m,apparent_temperature,"
                           "relative_humidity_2m,weather_code,wind_speed_10m",
            })
        )
        cur = data["current"]
        desc = WEATHER_CODES.get(cur["weather_code"], "unknown conditions")
        return (
            f"Weather in {place['name']}: {desc}, {cur['temperature_2m']} degrees Celsius "
            f"(feels like {cur['apparent_temperature']}), humidity "
            f"{cur['relative_humidity_2m']} percent, wind {cur['wind_speed_10m']} km/h."
        )
    except Exception as e:
        return f"I couldn't get the weather. Please check your internet connection. ({e})"


def get_datetime() -> str:
    return datetime.now().strftime("It's %I:%M %p on %A, %d %B %Y.")


# ---------- TOOL REGISTRY ----------

TOOLS = {
    "get_ram_info": get_ram_info,
    "get_disk_info": get_disk_info,
    "list_running_apps": list_running_apps,
    "open_app": open_app,
    "open_website": open_website,
    "open_settings": open_settings,
    "search_files": search_files,
    "open_file": open_file,
    "open_result": open_result,  
    "search_folders": search_folders,
    "open_folder": open_folder, 
    "get_weather": get_weather,
    "get_datetime": get_datetime,    
}