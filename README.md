# AI Desktop Assistant

A Windows desktop assistant that you control with text or voice commands.
It runs locally: Ollama (Qwen2.5 1.5B) picks the right tool, and the app performs the real action.

## Features
- Open apps, websites and Windows settings
- Search files and folders across the whole computer
- RAM, disk and running-app information
- Weather and time
- Voice input (faster-whisper) and spoken replies (pyttsx3)

## Setup
1. Install Python 3.11 or 3.12 and Ollama
2. Run `ollama pull qwen2.5:1.5b-instruct`
3. Create and activate a virtual environment with `python -m venv venv`, then `venv\Scripts\activate`
4. Run `python -m pip install -r requirements.txt`
5. Run `python main.py`