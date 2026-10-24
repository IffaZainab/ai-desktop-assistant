import json
import ollama
from core.tools import TOOLS
import re
from core import tools as file_tools
from difflib import SequenceMatcher

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
- open_settings: args {"page": "bluetooth"}. Pages: bluetooth, wifi, display, sound, battery, storage, apps, update.
- search_files: args {"query": "dbms project"}. Lists FILES matching the name.
- search_folders: args {"query": "coal lab"}. Lists FOLDERS matching the name.
- open_file: args {"query": "operating systems"}. Opens a FILE (or shows a numbered list if several match).
- open_folder: args {"query": "coal lab"}. Opens a FOLDER (or shows a numbered list if several match).
- get_weather: args {"city": "Lahore"}. Current weather. Use empty city "" if the user does not name a city.
- get_datetime: no args. Current time and date.
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

IGNORED_TOKENS = {"com", "www", "org", "net", "pk", "edu", "http", "https"}

# Which argument holds the "name" for each tool
NAME_ARGUMENT = {
    "open_app": "app_name",
    "open_website": "url",
    "open_file": "query",
    "open_folder": "query",
    "search_files": "query",
    "search_folders": "query",
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
    return None


def execute(tool: str, args: dict) -> str:
    if not isinstance(args, dict):
        args = {}
    try:
        return TOOLS[tool](**args)
    except TypeError as e:
        return f"Tool '{tool}' got wrong arguments: {args} ({e})"
    except Exception as e:
        return f"Tool '{tool}' failed: {e}"


def run_command(user_text: str, on_announce=None) -> str:
    number = pick_from_list(user_text)
    if number is not None:
        if on_announce:
            on_announce(f"Opening number {number}.")
        reply = execute("open_result", {"number": number})
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

    if tool in (None, "chat", "none") or tool not in TOOLS:
        reply = chat_reply(user_text)
    else:
        message = make_announcement(tool, args)
        if message and on_announce:
            on_announce(message)
        reply = execute(tool, args)

    _remember(user_text, reply)
    return reply