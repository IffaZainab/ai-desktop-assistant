import threading
from pathlib import Path
import pyttsx3

_lock = threading.Lock()


def _speak_worker(text: str):
    # lock prevents overlapping of two voices
    with _lock:
        try:
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print("Speech error:", e)


def make_spoken(result: str) -> str:
    text = result.strip()
    if text.startswith("Opened:"):
        return "Opened " + Path(text[len("Opened:"):].strip()).name
    lines = text.split("\n")
    if len(lines) > 3:      #only first line of long list
        return lines[0]
    return text[:400]


def speak(text: str):
    threading.Thread(target=_speak_worker, args=(text,), daemon=True).start()