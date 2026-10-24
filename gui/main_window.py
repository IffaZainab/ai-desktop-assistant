from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QPushButton, QLabel
)
from core.agent import run_command
from core.speech import speak, make_spoken
from core.voice import Recorder, transcribe


class CommandWorker(QThread):
    """Command ko alag thread mein chalata hai taake window freeze na ho."""
    announce = Signal(str)              
    finished_with_result = Signal(str)   # final ans

    def __init__(self, text: str):
        super().__init__()
        self.text = text

    def run(self):
        result = run_command(self.text, on_announce=self.announce.emit)
        self.finished_with_result.emit(result)

class TranscribeWorker(QThread):
    """Converts speech to text in a separate thread so the window stays responsive."""
    done = Signal(str)

    def __init__(self, audio):
        super().__init__()
        self.audio = audio

    def run(self):
        try:
            text = transcribe(self.audio)
        except Exception as e:
            print("Transcription error:", e)
            text = ""
        self.done.emit(text)        


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Desktop Assistant")
        self.resize(700, 550)
        self.worker = None
        self.announced = False

        self.recorder = Recorder()
        self.recording = False
        self.stt_worker = None        

        # Conversation block
        self.chat = QTextEdit()
        self.chat.setReadOnly(True)

        self.status = QLabel("")

        #input row
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a command... e.g. open youtube in chrome")
        self.input.returnPressed.connect(self.send_command)

        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_command)

        self.mic_btn = QPushButton("🎤")
        self.mic_btn.setToolTip("Click to speak, click again to stop")
        self.mic_btn.clicked.connect(self.toggle_mic)

        row = QHBoxLayout()
        row.addWidget(self.input)
        row.addWidget(self.mic_btn)
        row.addWidget(self.send_btn)

        layout = QVBoxLayout()
        layout.addWidget(self.chat)
        layout.addWidget(self.status)
        layout.addLayout(row)
        self.setLayout(layout)

        self.add_message("Assistant", "Hi! Tell me what to do on your computer.")

    def toggle_mic(self):
        if self.worker is not None:      # a command is still running
            return
        if not self.recording:
            try:
                self.recorder.start()
            except Exception as e:
                self.status.setText(f"Microphone error: {e}")
                return
            self.recording = True
            self.mic_btn.setText("⏹")
            self.status.setText("Listening... click again when you are done")
        else:
            audio = self.recorder.stop()
            self.recording = False
            self.mic_btn.setText("🎤")
            self.mic_btn.setEnabled(False)
            self.status.setText("Transcribing...")
            self.stt_worker = TranscribeWorker(audio)
            self.stt_worker.done.connect(self.on_transcribed)
            self.stt_worker.start()

    def on_transcribed(self, text: str):
        self.mic_btn.setEnabled(True)
        if not text:
            self.status.setText("I didn't catch that. Please try again.")
            return
        self.status.setText("")
        self.input.setText(text)
        self.send_command()   
   
   
    def add_message(self, sender: str, text: str):
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace("\n", "<br>")
        color = "#1a73e8" if sender == "You" else "#188038"
        self.chat.append(f'<p><b style="color:{color}">{sender}:</b><br>{text}</p>')

    def send_command(self):
        text = self.input.text().strip()
        if not text or self.worker is not None:
            return
        self.add_message("You", text)
        self.input.clear()
        self.input.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.mic_btn.setEnabled(False)        
        self.status.setText("Thinking...")
        self.announced = False

        self.worker = CommandWorker(text)
        self.worker.announce.connect(self.show_announcement)
        self.worker.finished_with_result.connect(self.show_result)
        self.worker.start()

    def show_announcement(self, message: str):
        self.announced = True
        self.status.setText(message)
        speak(message)

    def show_result(self, result: str):
        self.status.setText("")
        self.add_message("Assistant", result)
        if not (self.announced and result.startswith("Opened")):
            speak(make_spoken(result))
        self.worker = None
        self.input.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.mic_btn.setEnabled(True)        
        self.input.setFocus()