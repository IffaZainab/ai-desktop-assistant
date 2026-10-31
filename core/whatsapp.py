"""WhatsApp Desktop automation: open a person's chat by searching their name."""
import ctypes
import time

import pyautogui
import pyperclip
from pywinauto import Desktop

from core.tools import _find_app, open_app

pyautogui.FAILSAFE = True   # moving the mouse to a screen corner aborts the automation
pyautogui.PAUSE = 0.15

# If pressing Enter alone does not open the first search result,
# set this to True so the script presses Down first.
PRESS_DOWN_BEFORE_ENTER = False


def _find_window():
    """Finds the WhatsApp window by its exact title."""
    for window in Desktop(backend="uia").windows():
        try:
            if window.window_text().strip().lower() == "whatsapp":
                return window
        except Exception:
            continue
    return None


def _paste(text: str):
    """Pastes text through the clipboard (works for any name, even non-English)."""
    try:
        old = pyperclip.paste()
    except Exception:
        old = None
    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.3)
    if old is not None:
        pyperclip.copy(old)


def _bring_to_front():
    """Starts WhatsApp if needed and focuses it. Returns (window, error_message)."""
    window = _find_window()
    if window is None:
        if _find_app("whatsapp") is None:
            return None, "WhatsApp does not seem to be installed on this laptop."
        open_app("whatsapp")
        for _ in range(30):                 # wait up to 15 seconds
            time.sleep(0.5)
            window = _find_window()
            if window is not None:
                break
        if window is None:
            return None, "WhatsApp did not open in time."
        time.sleep(2)                       # let the interface finish loading
    try:
        window.restore()                    # in case it is minimised
    except Exception:
        pass
    try:
        window.set_focus()
    except Exception:
        pass
    time.sleep(0.7)
    # Safety check: never type unless WhatsApp is really the front window
    if ctypes.windll.user32.GetForegroundWindow() != window.handle:
        return None, ("I couldn't bring WhatsApp to the front, so I stopped "
                      "to avoid typing into the wrong window.")
    return window, None


def whatsapp_open_chat(contact: str) -> str:
    contact = str(contact).strip()
    if not contact:
        return "Whose chat should I open?"
    window, error = _bring_to_front()
    if error:
        return error
    pyautogui.hotkey("ctrl", "f")           # focus the search box
    time.sleep(0.5)
    pyautogui.hotkey("ctrl", "a")           # select the old search text...
    pyautogui.press("backspace")            # ...and delete it
    time.sleep(0.2)
    _paste(contact)
    time.sleep(1.5)                         # wait for the search results
    if PRESS_DOWN_BEFORE_ENTER:
        pyautogui.press("down")
        time.sleep(0.2)
    pyautogui.press("enter")                # open the top result  
    return (f"I opened the top WhatsApp search result for '{contact}'. "
            f"Please check that it is the right chat.")


WHATSAPP_TOOLS = {
    "whatsapp_open_chat": whatsapp_open_chat,
}