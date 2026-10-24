import sys
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow
import threading
from core.tools import _load_installed_apps
from core.voice import get_model

threading.Thread(target=_load_installed_apps, daemon=True).start()
threading.Thread(target=get_model, daemon=True).start()
app = QApplication(sys.argv)
window = MainWindow()
window.show()
sys.exit(app.exec())