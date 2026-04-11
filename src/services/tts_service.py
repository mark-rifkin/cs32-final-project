import pyttsx3

class TTSService:
    def __init__(self):
        self.engine = pyttsx3.init()
        rate = self.engine.getProperty('rate')
        self.engine.setProperty('rate', rate-50)

    def speak(self, text: str) -> None:
        preview = text if len(text) <= 80 else f"{text[:77]}..."
        print(f"[TTS] speak() start: {preview}")
        try:
            self.engine.say(text)
            print("[TTS] queued utterance")
            self.engine.runAndWait()
            print("[TTS] runAndWait() completed")
        except Exception as exc:
            print(f"[TTS] ERROR: {type(exc).__name__}: {exc}")
            raise
