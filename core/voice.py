import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000     # Whisper expects 16 kHz audio
LANGUAGE = "en"         # fixed language is more reliable than auto-detect on short clips

_model = None


def get_model():
    """Load the Whisper model once (the first time it also downloads, ~150 MB)."""
    global _model
    if _model is None:
        _model = WhisperModel("base", device="cpu", compute_type="int8")
    return _model


class Recorder:
    """Records from the default microphone until stop() is called."""

    def __init__(self):
        self._chunks = []
        self._stream = None

    def _callback(self, indata, frames, time_info, status):
        self._chunks.append(indata.copy())

    def start(self):
        self._chunks = []
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if not self._chunks:
            return np.zeros(0, dtype="float32")
        return np.concatenate(self._chunks).flatten()


def transcribe(audio) -> str:
    """Convert recorded audio to text."""
    if audio.size < SAMPLE_RATE * 0.5:      # shorter than half a second
        return ""
    segments, _info = get_model().transcribe(
        audio, language=LANGUAGE, beam_size=1, vad_filter=True
    )
    return " ".join(s.text.strip() for s in segments).strip()