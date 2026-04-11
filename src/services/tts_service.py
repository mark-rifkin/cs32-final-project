import pyttsx3

class TTSService:
    def __init__(self):
        self.rate_offset = -50

    def speak(self, text: str) -> None:
        engine = None
        try:
            engine = pyttsx3.init()
            rate = engine.getProperty('rate')
            engine.setProperty('rate', rate + self.rate_offset)
            engine.say(text)
            engine.runAndWait()
        finally:
            if engine is not None:
                try:
                    engine.stop()
                except Exception:
                    pass
