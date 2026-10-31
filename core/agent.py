import json
import ollama
from core.tools import TOOLS
from core.system_controls import SYSTEM_TOOLS
from core.whatsapp import WHATSAPP_TOOLS
TOOLS.update(SYSTEM_TOOLS)
TOOLS.update(WHATSAPP_TOOLS)
from core.window_control import WINDOW_TOOLS
TOOLS.update(WINDOW_TOOLS)
import re
from core import tools as file_tools
from difflib import SequenceMatcher
import inspect
from pathlib import Path

MODEL = "qwen2.5:1.5b-instruct"

# old conversation history(forgotten when program stops)
HISTORY = []
MAX_HISTORY = 8

ROUTER_PROMPT = """You are the brain of a Windows desktop assistant. Pick exactly ONE tool for the user's request.
Reply with JSON only, in this format:
{"tool": "<tool_name>", "args": {<arguments>}}

Available tools:
- get_ram_info: no args. Total/used RAM.
- get_disk_info: args {"drive": "C"}. Free/used storage of a drive.
- list_running_apps: no args. Shows running applications.
- open_app: args {"app_name": "spotify"}. Opens an installed desktop app by name (whatsapp, spotify, word, etc). For websites use open_website instead.
- open_website: args {"url": "google drive"}. Opens a website by its name or address. Optional "browser" (chrome, edge, firefox).
- open_settings: args {"page": "night light"}. Opens ANY Windows Settings page by name (bluetooth, display, night light, battery, hotspot, privacy, update, etc). It does not turn anything on or off.
- search_files: args {"query": "dbms project"}. Lists FILES matching the name.
- search_folders: args {"query": "coal lab"}. Lists FOLDERS matching the name.
- open_file: args {"query": "operating systems"}. Opens a FILE (or shows a numbered list if several match).
- open_folder: args {"query": "coal lab"}. Opens a FOLDER (or shows a numbered list if several match).
- get_weather: args {"city": "Lahore"}. Current weather. Use empty city "" if the user does not name a city.
- get_datetime: no args. Current time and date.
- get_volume: no args. Tells the current volume.
- set_volume: args {"level": 50}. Sets the volume to a percentage from 0 to 100.
- change_volume: args {"direction": "up", "amount": 10}. Makes the volume higher or lower.
- set_mute: args {"state": "on"}. "on" mutes the sound, "off" unmutes it.
- get_brightness: no args. Tells the screen brightness.
- set_brightness: args {"level": 70}. Sets the screen brightness from 0 to 100.
- change_brightness: args {"direction": "down", "amount": 20}. Makes the screen brighter or dimmer.
- set_wifi: args {"state": "on"}. Turns Wi-Fi on or off.
- set_bluetooth: args {"state": "off"}. Turns Bluetooth on or off.
- set_airplane_mode: args {"state": "on"}. Turns airplane mode on or off.
- media_control: args {"action": "play_pause"}. Actions: play_pause, next, previous.
- lock_screen: no args. Locks the computer.
- sleep_computer: no args. Puts the computer to sleep.
- get_battery_info: no args. Battery percentage and charging status.
- take_screenshot: no args. Takes a screenshot.
- set_dark_mode: args {"state": "on"}. Turns dark mode on or off.
- whatsapp_open_chat: args {"contact": "Alishba"}. Opens a person's chat inside the WhatsApp app.
- chat: no args. Use for greetings, small talk, jokes, general knowledge questions, explanations, math, advice, anything that is NOT a computer action.

For "query", use ONLY the name keywords. Remove words like find, open, my, the, file, folder, search.
If the user says "folder" or "directory", use search_folders or open_folder. Otherwise use the file tools.

Examples:
User: Open YouTube in Chrome.
{"tool": "open_website", "args": {"url": "youtube.com", "browser": "chrome"}}
User: How much free space on my D drive?
{"tool": "get_disk_info", "args": {"drive": "D"}}
User: Find my DSA PDF and open it.
{"tool": "open_file", "args": {"query": "dsa"}}
User: Search Downloads for my DBMS project.
{"tool": "search_files", "args": {"query": "dbms project"}}
User: Open Windows Bluetooth settings.
{"tool": "open_settings", "args": {"page": "bluetooth"}}
User: Find my coal lab folder and open it.
{"tool": "open_folder", "args": {"query": "coal lab"}}
User: Show me folders named project.
{"tool": "search_folders", "args": {"query": "project"}}
User: Open Instagram.
{"tool": "open_app", "args": {"app_name": "instagram"}}
User: Open WhatsApp.
{"tool": "open_app", "args": {"app_name": "whatsapp"}}
User: What's the weather in Karachi?
{"tool": "get_weather", "args": {"city": "Karachi"}}
User: Will it rain today?
{"tool": "get_weather", "args": {"city": ""}}
User: What time is it?
{"tool": "get_datetime", "args": {}}
User: Hello
{"tool": "chat", "args": {}}
User: How are you?
{"tool": "chat", "args": {}}
User: Tell me a joke.
{"tool": "chat", "args": {}}
User: What is the capital of France?
{"tool": "chat", "args": {}}
User: Bye
{"tool": "chat", "args": {}}
User: Okay bye
{"tool": "chat", "args": {}}
User: Thanks
{"tool": "chat", "args": {}}
User: Good morning
{"tool": "chat", "args": {}}
User: Open Google Drive.
{"tool": "open_website", "args": {"url": "google drive"}}
User: Open Google Classroom.
{"tool": "open_website", "args": {"url": "google classroom"}}
User: Open LinkedIn.
{"tool": "open_website", "args": {"url": "linkedin"}}
User: Turn the volume up.
{"tool": "change_volume", "args": {"direction": "up", "amount": 10}}
User: Set volume to 40.
{"tool": "set_volume", "args": {"level": 40}}
User: Mute.
{"tool": "set_mute", "args": {"state": "on"}}
User: Unmute the sound.
{"tool": "set_mute", "args": {"state": "off"}}
User: Make the screen dimmer.
{"tool": "change_brightness", "args": {"direction": "down", "amount": 20}}
User: Set brightness to 80 percent.
{"tool": "set_brightness", "args": {"level": 80}}
User: Turn off Wi-Fi.
{"tool": "set_wifi", "args": {"state": "off"}}
User: Turn on Bluetooth.
{"tool": "set_bluetooth", "args": {"state": "on"}}
User: Enable airplane mode.
{"tool": "set_airplane_mode", "args": {"state": "on"}}
User: Pause the music.
{"tool": "media_control", "args": {"action": "play_pause"}}
User: Next song.
{"tool": "media_control", "args": {"action": "next"}}
User: How much battery is left?
{"tool": "get_battery_info", "args": {}}
User: Open Alishba's chat on WhatsApp.
{"tool": "whatsapp_open_chat", "args": {"contact": "Alishba"}}
User: Open night light settings.
{"tool": "open_settings", "args": {"page": "night light"}}
User: Open the Cobra group on WhatsApp.
{"tool": "whatsapp_open_chat", "args": {"contact": "Cobra"}}
"""

CHAT_PROMPT = """You are a friendly voice assistant inside a Windows desktop app.
Keep answers short (1 to 3 sentences), because your replies are read aloud.
Reply in the same language the user writes in (English, Urdu, or Roman Urdu).
You cannot see live information like news or sports scores. If asked, say so honestly instead of guessing.
If the user asks you to do something on the computer that you cannot do, say you can't do that yet."""



def _remember(user_text: str, reply: str):
    HISTORY.append({"role": "user", "content": user_text})
    HISTORY.append({"role": "assistant", "content": reply[:300]})
    del HISTORY[:-MAX_HISTORY]


def decide(user_text: str) -> dict:
    try:
        response = ollama.chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": ROUTER_PROMPT},
                {"role": "user", "content": user_text},
            ],
            format="json",
            options={"temperature": 0},
            keep_alive="10m",
        )
    except Exception as e:
        return {"error": f"Could not reach Ollama. Is it running? ({e})"}

    raw = response["message"]["content"]
    try:
        decision = json.loads(raw)
    except json.JSONDecodeError:
        return {"error": f"Model gave invalid output: {raw}"}
    if not isinstance(decision, dict):
        return {"error": f"Model gave invalid output: {raw}"}
    return decision

# "open <site> on chrome" is always a website. Python handles it directly,
# because the small model often confuses it with an app or a setting.
WEBSITE_ON_BROWSER = re.compile(
    r"^(?:please\s+)?(?:open|launch|start|go to|visit)\s+(.+?)\s+"
    r"(?:on|in|using|with)\s+(chrome|edge|firefox)$",
    re.IGNORECASE,    
)
# "open <name> on WhatsApp" (also "open group named <name> on whatsapp").
# Python handles it directly so the small model cannot confuse it with an app.
WHATSAPP_CHAT = re.compile(
    r"^(?:please\s+)?(?:open|find|go to|show|search)\s+(?:the\s+)?"
    r"(?:(?:group|chat)\s+(?:named\s+|called\s+|of\s+|with\s+)?)?"
    r"(.+?)(?:'s)?(?:\s+(?:chat|group))?\s+(?:on|in)\s+whats?app$",
    re.IGNORECASE,
)

IGNORED_TOKENS = {"com", "www", "org", "net", "pk", "edu", "http", "https"}

# Which argument holds the "name" for each tool
NAME_ARGUMENT = {
    "open_app": "app_name",
    "open_website": "url",
    "open_file": "query",
    "open_folder": "query",
    "search_files": "query",
    "search_folders": "query",
    "whatsapp_open_chat": "contact",    
}


def _words(text: str) -> list:
    return re.findall(r"[a-z0-9]+", text.lower())


def _is_grounded(tool: str, args: dict, user_text: str) -> bool:
    """Check that the name chosen by the model really comes from the user's
    message. If it does not, the model guessed (for example it copied a prompt
    example), so the message should be treated as normal chat."""
    key = NAME_ARGUMENT.get(tool)
    if key is None:
        return True
    tokens = [t for t in _words(str(args.get(key, ""))) if t not in IGNORED_TOKENS]
    if not tokens:
        return False
    user_words = _words(user_text)
    for t in tokens:
        for w in user_words:
            if t == w:
                return True
            if len(w) >= 3 and (t in w or w in t):
                return True
            if SequenceMatcher(None, t, w).ratio() >= 0.75:
                return True
    return False

# Safety guard (not a capability list): a tool that changes the system only runs
# if the user's sentence contains at least one of its trigger words.
# This stops the small model from forcing the "nearest" tool onto a request
# that has no tool (for example "turn off energy saver" -> brightness 0).
TOOL_TRIGGERS = {
    "get_volume": ("volume", "sound", "loud", "audio", "music", "song"),
    "set_volume": ("volume", "sound", "loud", "audio", "music", "song"),
    "change_volume": ("volume", "sound", "loud", "quiet", "audio", "music", "song"),
    "set_mute": ("mute", "silent", "sound", "audio", "volume"),
    "get_brightness": ("bright", "dim"),
    "set_brightness": ("bright", "dim", "screen", "display"),
    "change_brightness": ("bright", "dim", "screen", "display"),
    "set_wifi": ("wifi", "wi-fi", "wi fi", "wireless", "internet"),
    "set_bluetooth": ("bluetooth", "blue tooth"),
    "set_airplane_mode": ("airplane", "aeroplane", "flight"),
    "media_control": ("play", "pause", "music", "song", "track", "next",
                      "skip", "previous", "resume", "video", "back"),
    "lock_screen": ("lock",),
    "sleep_computer": ("sleep", "suspend"),
    "get_battery_info": ("battery", "charge", "charging", "power"),
    "take_screenshot": ("screenshot", "screen shot", "capture", "snap"),
    "set_dark_mode": ("dark", "light mode", "theme", "night mode"),
    "whatsapp_open_chat": ("whatsapp", "whatapp", "whats app", "chat", "group"),
}


def _is_relevant(tool: str, user_text: str) -> bool:
    triggers = TOOL_TRIGGERS.get(tool)
    if triggers is None:        # tools without triggers are always allowed
        return True
    text = user_text.lower()
    return any(word in text for word in triggers)


def _clean_args(tool: str, args: dict):
    """Keeps only the arguments the tool really accepts.
    Returns None if a required argument is missing (the model got it wrong)."""
    signature = inspect.signature(TOOLS[tool])
    cleaned = {k: v for k, v in args.items() if k in signature.parameters}
    try:
        signature.bind(**cleaned)
    except TypeError:
        return None
    return cleaned


def _cannot_do(user_text: str) -> str:
    """Honest answer when no tool really fits. If a Settings page matches the
    request, open it so the user can finish the job there."""
    page = file_tools.find_settings_page(user_text)
    if page:
        file_tools.open_settings(page)
        return (f"I can't change that myself yet, so I opened the {page} "
                f"settings page for you.")
    return "I can't do that yet."

# Window commands ("close chrome", "minimize this app"). Python parses them directly,
# because closing the wrong app could lose someone's unsaved work.
WINDOW_COMMAND = re.compile(
    r"^(close|exit|quit|minimi[sz]e|maximi[sz]e|restore|hide)\s+(.+)$",
    re.IGNORECASE,
)
WINDOW_VERBS = {
    "close": "close", "exit": "close", "quit": "close",
    "minimize": "minimize", "minimise": "minimize", "hide": "minimize",
    "maximize": "maximize", "maximise": "maximize",
    "restore": "restore",
}
WINDOW_ANNOUNCE = {
    "close": "Closing", "minimize": "Minimizing",
    "maximize": "Maximizing", "restore": "Restoring",
}


def _parse_window_command(user_text: str):
    """'close chrome' -> ('close', 'chrome'). 'minimize this app' -> ('minimize', 'app').
    Returns None if the sentence is not a window command."""
    text = user_text.strip().rstrip(".!?").lower()
    text = re.sub(r"^(?:hey\s+)?(?:(?:can|could|will|would)\s+you\s+)?(?:please\s+)?", "", text)
    text = re.sub(r"\s+(?:please|for me|now)$", "", text)
    match = WINDOW_COMMAND.match(text)
    if not match:
        return None
    action = WINDOW_VERBS[match.group(1).lower()]
    target = match.group(2).strip()
    target = re.sub(r"^(?:the|this|that|my)\s+(?=\S)", "", target)
    target = re.sub(r"\s+(?:app|application|window|program)$", "", target)
    return action, target

ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}


def pick_from_list(user_text: str):
    if not file_tools.LAST_RESULTS:
        return None
    text = user_text.strip().lower().rstrip(".!")

    m = re.fullmatch(r"(?:open\s+)?(?:number\s+|no\.?\s*|#\s*)?(\d{1,3})", text)
    if m:
        return int(m.group(1))

    if len(text.split()) <= 6:
        for word, number in ORDINALS.items():
            if re.search(rf"\b{word}\b", text):
                return number
    return None


def chat_reply(user_text: str) -> str:
    """Normal baat cheet (hello, jokes, general sawal)."""
    messages = [{"role": "system", "content": CHAT_PROMPT}]
    messages += HISTORY[-6:]
    messages.append({"role": "user", "content": user_text})
    try:
        response = ollama.chat(
            model=MODEL,
            messages=messages,
            options={"temperature": 0.7},
            keep_alive="10m",
        )
        return response["message"]["content"].strip()
    except Exception as e:
        return f"Could not reach Ollama. Is it running? ({e})"


def make_announcement(tool: str, args: dict):
    if tool == "open_app":
        return f"Opening {args.get('app_name', 'the app')}."
    if tool == "open_website":
        return f"Opening {args.get('url', 'the website')}."
    if tool == "open_settings":
        return f"Opening {args.get('page', '')} settings."
    if tool in ("open_file", "open_folder"):
        kind = "folder" if tool == "open_folder" else "file"
        return f"Looking for the {args.get('query', '')} {kind}."
    if tool in ("search_files", "search_folders"):
        return f"Searching for {args.get('query', '')}."
    if tool == "open_result":
        return f"Opening number {args.get('number', '')}."
    if tool == "get_ram_info":
        return "Checking your RAM."
    if tool == "get_disk_info":
        return f"Checking drive {args.get('drive', 'C')}."
    if tool == "list_running_apps":
        return "Checking running apps."
    if tool == "get_weather":
        return "Checking the weather."
    spoken = {
        "get_volume": "Checking the volume.",
        "set_volume": "Setting the volume.",
        "change_volume": "Changing the volume.",
        "set_mute": "Changing the sound.",
        "get_brightness": "Checking the brightness.",
        "set_brightness": "Setting the brightness.",
        "change_brightness": "Changing the brightness.",
        "set_wifi": "Changing Wi-Fi.",
        "set_bluetooth": "Changing Bluetooth.",
        "set_airplane_mode": "Changing airplane mode.",
        "media_control": "Okay.",
        "lock_screen": "Locking the screen.",
        "sleep_computer": "Going to sleep.",
        "get_battery_info": "Checking the battery.",
        "take_screenshot": "Taking a screenshot.",
        "set_dark_mode": "Changing the theme.",
    }
    if tool in spoken:
        return spoken[tool]
    if tool == "whatsapp_open_chat":
        return f"Opening {args.get('contact', '')}'s chat on WhatsApp."    
    return None


def _note_opened(tool: str, reply: str):
    """Remembers what was just opened, so 'close this app' knows what 'this' means.
    Done in one place, so no individual tool needs to care about it."""
    if tool == "whatsapp_open_chat":
        name = "whatsapp"
    elif tool == "open_settings":
        name = "settings"
    elif reply.startswith("Opened: "):                       # a file or a folder
        name = Path(reply[len("Opened: "):].strip()).stem
    elif tool in ("open_app", "open_website") and reply.startswith("Opened"):
        name = reply[len("Opened"):].strip(" .")
    else:
        return
    file_tools._remember_opened(name)


def execute(tool: str, args: dict) -> str:
    if not isinstance(args, dict):
        args = {}
    try:
        reply = TOOLS[tool](**args)
    except TypeError as e:
        return f"Tool '{tool}' got wrong arguments: {args} ({e})"
    except Exception as e:
        return f"Tool '{tool}' failed: {e}"
    _note_opened(tool, reply)
    return reply


def run_command(user_text: str, on_announce=None) -> str:
    number = pick_from_list(user_text)
    if number is not None:
        if on_announce:
            on_announce(f"Opening number {number}.")
        reply = execute("open_result", {"number": number})
        _remember(user_text, reply)
        return reply

    # Close / minimize / maximize / restore an app window (handled without the model)
    window_command = _parse_window_command(user_text)
    if window_command:
        action, target = window_command
        if on_announce:
            on_announce(f"{WINDOW_ANNOUNCE[action]} {target or 'it'}.")
        reply = execute("control_window", {"action": action, "app_name": target})
        _remember(user_text, reply)
        return reply

    # Chat or group on WhatsApp (handled without the model)
    match = WHATSAPP_CHAT.match(user_text.replace("’", "'").strip().rstrip(".!"))
    if match:
        contact = match.group(1).strip()
        if on_announce:
            on_announce(f"Opening {contact}'s chat on WhatsApp.")
        reply = execute("whatsapp_open_chat", {"contact": contact})
        _remember(user_text, reply)
        return reply

    # Website on a named browser (handled without the model)
    match = WEBSITE_ON_BROWSER.match(user_text.strip().rstrip(".!"))
    if match:
        site, browser = match.group(1), match.group(2).lower()
        if on_announce:
            on_announce(f"Opening {site} in {browser}.")
        reply = execute("open_website", {"url": site, "browser": browser})
        _remember(user_text, reply)
        return reply    

    decision = decide(user_text)
    if "error" in decision:
        return decision["error"]

    tool = decision.get("tool")
    args = decision.get("args", {})
    if not isinstance(args, dict):
        args = {}

    if tool == "open_result":
        tool = "chat"

    # If the name is not found in what the user said, the model guessed
    if tool in TOOLS and not _is_grounded(tool, args, user_text):
        tool = "chat" 

    # Safety checks before touching the system
    if tool in TOOLS:
        cleaned = _clean_args(tool, args)
        if cleaned is None or not _is_relevant(tool, user_text):
            reply = _cannot_do(user_text)
            _remember(user_text, reply)
            return reply
        args = cleaned               

    if tool in (None, "chat", "none") or tool not in TOOLS:
        reply = chat_reply(user_text)
    else:
        message = make_announcement(tool, args)
        if message and on_announce:
            on_announce(message)
        reply = execute(tool, args)

    _remember(user_text, reply)
    return reply