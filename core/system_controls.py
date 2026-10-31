"""Hardware and Windows controls: volume, brightness, Wi-Fi, Bluetooth, media keys, etc."""
import base64
import ctypes
import re
import subprocess
import winreg
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import psutil

NO_WINDOW = subprocess.CREATE_NO_WINDOW


# ---------- helpers ----------

@contextmanager
def _com():
    """COM must be initialised in every thread that uses it.
    Our commands run in worker threads, so we do it here."""
    hr = ctypes.windll.ole32.CoInitialize(None)
    try:
        yield
    finally:
        if hr in (0, 1):  # S_OK or S_FALSE
            ctypes.windll.ole32.CoUninitialize()


def _to_int(value, default=None):
    """Accepts 50, "50" or "50%" and returns an int."""
    match = re.search(r"-?\d+", str(value))
    return int(match.group()) if match else default


def _to_state(value):
    """'on/enable/true' -> True, 'off/disable/false' -> False, anything else -> None."""
    text = str(value).strip().lower()
    if text in ("on", "enable", "enabled", "true", "1", "yes", "start"):
        return True
    if text in ("off", "disable", "disabled", "false", "0", "no", "stop"):
        return False
    return None


def _direction(value) -> int:
    """'up' -> 1, 'down' -> -1, unknown -> 0."""
    text = str(value).strip().lower()
    if text in ("up", "increase", "raise", "higher", "more", "+"):
        return 1
    if text in ("down", "decrease", "lower", "reduce", "less", "-"):
        return -1
    return 0


# ---------- VOLUME ----------

def _volume_endpoint():
    """Returns the speaker volume control (works with new and old pycaw versions)."""
    from pycaw.pycaw import AudioUtilities
    device = AudioUtilities.GetSpeakers()
    try:
        return device.EndpointVolume  # newer pycaw
    except AttributeError:
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import IAudioEndpointVolume
        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))


def get_volume() -> str:
    try:
        with _com():
            vol = _volume_endpoint()
            level = round(vol.GetMasterVolumeLevelScalar() * 100)
            muted = bool(vol.GetMute())
        return f"Volume is {level} percent" + (" and it is muted." if muted else ".")
    except Exception as e:
        return f"I couldn't read the volume: {e}"


def set_volume(level) -> str:
    number = _to_int(level)
    if number is None:
        return "What volume level do you want, from 0 to 100?"
    number = max(0, min(100, number))
    try:
        with _com():
            vol = _volume_endpoint()
            vol.SetMasterVolumeLevelScalar(number / 100, None)
            if number > 0 and vol.GetMute():
                vol.SetMute(0, None)
        return f"Volume set to {number} percent."
    except Exception as e:
        return f"I couldn't change the volume: {e}"


def change_volume(direction="up", amount=10) -> str:
    sign = _direction(direction)
    if sign == 0:
        return "Should I turn the volume up or down?"
    step = _to_int(amount, 10)
    try:
        with _com():
            vol = _volume_endpoint()
            current = round(vol.GetMasterVolumeLevelScalar() * 100)
            new = max(0, min(100, current + sign * step))
            vol.SetMasterVolumeLevelScalar(new / 100, None)
        return f"Volume is now {new} percent."
    except Exception as e:
        return f"I couldn't change the volume: {e}"


def set_mute(state="on") -> str:
    """state 'on' = muted, 'off' = unmuted."""
    muted = _to_state(state)
    if muted is None:
        return "Should I mute or unmute the sound?"
    try:
        with _com():
            _volume_endpoint().SetMute(1 if muted else 0, None)
        return "Sound muted." if muted else "Sound unmuted."
    except Exception as e:
        return f"I couldn't change the mute setting: {e}"


# ---------- BRIGHTNESS ----------

def _brightness_error(e) -> str:
    return f"I couldn't control the brightness. This works on laptop screens that support it. ({e})"


def get_brightness() -> str:
    try:
        import screen_brightness_control as sbc
        with _com():
            level = sbc.get_brightness()
        level = level[0] if isinstance(level, list) else level
        return f"Brightness is {level} percent."
    except Exception as e:
        return _brightness_error(e)


def set_brightness(level) -> str:
    number = _to_int(level)
    if number is None:
        return "What brightness level do you want, from 0 to 100?"
    number = max(5, min(100, number))   # never fully black, so the screen stays visible
    try:
        import screen_brightness_control as sbc
        with _com():
            sbc.set_brightness(number)
        return f"Brightness set to {number} percent."
    except Exception as e:
        return _brightness_error(e)


def change_brightness(direction="up", amount=20) -> str:
    sign = _direction(direction)
    if sign == 0:
        return "Should I make the screen brighter or dimmer?"
    step = _to_int(amount, 20)
    try:
        import screen_brightness_control as sbc
        with _com():
            current = sbc.get_brightness()
            current = current[0] if isinstance(current, list) else current
            new = max(5, min(100, int(current) + sign * step))
            sbc.set_brightness(new)
        return f"Brightness is now {new} percent."
    except Exception as e:
        return _brightness_error(e)


# ---------- WI-FI, BLUETOOTH, AIRPLANE MODE ----------
# Uses the Windows Radio API through PowerShell. No admin rights needed.

_RADIO_SCRIPT = r'''
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}
[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
[Windows.Devices.Radios.RadioAccessStatus,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
[Windows.Devices.Radios.RadioState,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus]) | Out-Null
$radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
$kind = '__KIND__'
$target = '__STATE__'
$found = $false
foreach ($r in $radios) {
    $name = $r.Kind.ToString()
    $wanted = ($kind -eq 'All' -and @('WiFi','Bluetooth','MobileBroadband') -contains $name) -or ($name -eq $kind)
    if ($wanted) {
        $found = $true
        Await ($r.SetStateAsync([Windows.Devices.Radios.RadioState]::$target)) ([Windows.Devices.Radios.RadioAccessStatus]) | Out-Null
        Write-Output ($name + ':' + $target)
    }
}
if (-not $found) { Write-Output 'NOTFOUND' }
'''


def _set_radio(kind: str, turn_on: bool, label: str) -> str:
    target = "On" if turn_on else "Off"
    script = _RADIO_SCRIPT.replace("__KIND__", kind).replace("__STATE__", target)
    encoded = base64.b64encode(script.encode("utf-16-le")).decode()
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-EncodedCommand", encoded],
            capture_output=True, text=True, timeout=40, creationflags=NO_WINDOW,
        )
    except Exception as e:
        return f"I couldn't change {label}: {e}"
    out = result.stdout.strip()
    if "NOTFOUND" in out or not out:
        detail = result.stderr.strip()[:200]
        return f"I couldn't find {label} on this laptop. {detail}".strip()
    return f"{label} turned {target.lower()}."


def set_wifi(state="on") -> str:
    s = _to_state(state)
    if s is None:
        return "Should I turn Wi-Fi on or off?"
    return _set_radio("WiFi", s, "Wi-Fi")


def set_bluetooth(state="on") -> str:
    s = _to_state(state)
    if s is None:
        return "Should I turn Bluetooth on or off?"
    return _set_radio("Bluetooth", s, "Bluetooth")


def set_airplane_mode(state="on") -> str:
    """Airplane mode on = all wireless radios off."""
    s = _to_state(state)
    if s is None:
        return "Should I turn airplane mode on or off?"
    radios_on = not s
    msg = _set_radio("All", radios_on, "Wireless radios")
    return msg.replace("Wireless radios turned on.", "Airplane mode is off.").replace(
        "Wireless radios turned off.", "Airplane mode is on."
    )


# ---------- MEDIA KEYS, LOCK, SLEEP ----------

MEDIA_KEYS = {"play_pause": 0xB3, "next": 0xB0, "previous": 0xB1, "stop": 0xB2}


def media_control(action="play_pause") -> str:
    text = str(action).strip().lower().replace(" ", "_")
    if text in ("play", "pause", "playpause", "resume", "play_pause"):
        text = "play_pause"
    elif text in ("next", "skip", "next_track"):
        text = "next"
    elif text in ("previous", "prev", "back", "previous_track"):
        text = "previous"
    code = MEDIA_KEYS.get(text)
    if code is None:
        return "Which media action: play or pause, next, or previous?"
    ctypes.windll.user32.keybd_event(code, 0, 0, 0)  # key down
    ctypes.windll.user32.keybd_event(code, 0, 2, 0)  # key up
    return {"play_pause": "Toggled play and pause.", "next": "Skipped to the next track.",
            "previous": "Went to the previous track.", "stop": "Stopped the media."}[text]


def lock_screen() -> str:
    ctypes.windll.user32.LockWorkStation()
    return "Locked the screen."


def sleep_computer() -> str:
    # Note: if hibernate is enabled in Windows, this may hibernate instead of sleeping.
    subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
    return "Putting the computer to sleep."


# ---------- BATTERY, SCREENSHOT, THEME ----------

def get_battery_info() -> str:
    battery = psutil.sensors_battery()
    if battery is None:
        return "I couldn't find a battery. This may be a desktop computer."
    status = "charging" if battery.power_plugged else "not charging"
    text = f"Battery is at {round(battery.percent)} percent and {status}."
    if not battery.power_plugged and battery.secsleft and battery.secsleft > 0:
        hours, rest = divmod(battery.secsleft, 3600)
        text += f" About {hours} hours {rest // 60} minutes left."
    return text


def take_screenshot() -> str:
    from PIL import ImageGrab
    folder = Path.home() / "Pictures" / "Screenshots"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / datetime.now().strftime("screenshot_%Y%m%d_%H%M%S.png")
    ImageGrab.grab().save(path)
    return f"Screenshot saved as {path.name} in Pictures\\Screenshots."


def set_dark_mode(state="on") -> str:
    dark = _to_state(state)
    if dark is None:
        return "Should I turn dark mode on or off?"
    value = 0 if dark else 1  # in Windows, 0 = dark theme and 1 = light theme
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, value)
            winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, value)
        return "Dark mode is on." if dark else "Dark mode is off."
    except Exception as e:
        return f"I couldn't change the theme: {e}"


# ---------- REGISTRY OF TOOLS ----------

SYSTEM_TOOLS = {
    "get_volume": get_volume,
    "set_volume": set_volume,
    "change_volume": change_volume,
    "set_mute": set_mute,
    "get_brightness": get_brightness,
    "set_brightness": set_brightness,
    "change_brightness": change_brightness,
    "set_wifi": set_wifi,
    "set_bluetooth": set_bluetooth,
    "set_airplane_mode": set_airplane_mode,
    "media_control": media_control,
    "lock_screen": lock_screen,
    "sleep_computer": sleep_computer,
    "get_battery_info": get_battery_info,
    "take_screenshot": take_screenshot,
    "set_dark_mode": set_dark_mode,
}