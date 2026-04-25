import time
from pathlib import Path

from src.models import Attempt, Question
from src.services.tts_service import TTSService


class RoundControl:
    EARLY_LOCKOUT_MS = 250
    ANSWER_TIME_S = 5

    def __init__(self, tts: TTSService):
        self.tts = tts

    def run(self, question: Question, audio_path: Path) -> Attempt:
        print()
        print("=" * 60)
        print(f"{question.category}")
        print(f"{question.clue_text}")
        print("=" * 60)
        print()

        self.tts.play_file(audio_path)

        print("\nBuzzer unlocked (press enter to buzz, or type s+enter to skip)")
        unlock_time = time.perf_counter()
        buzz_input = input().strip().lower()
        
        if buzz_input == "s":
            print(f"Skipped. Correct response: {question.correct_response}")
            return Attempt(
                clue_id=question.clue_id,
                category=question.category,
                clue_text=question.clue_text,
                correct_response=question.correct_response,
                buzz_delta_ms=None,
                early_buzz=False,
                correct=None,
            )
        
        buzz_time = time.perf_counter()
        buzz_delta_ms = (buzz_time - unlock_time) * 1000.0

        print(f"Buzz time: {buzz_delta_ms:.1f} ms")

        print(f"\nYou have {self.ANSWER_TIME_S} seconds to answer out loud.")
        for remaining in range(self.ANSWER_TIME_S, 0, -1):
            print(f"{remaining}...")
            time.sleep(1)

        print(f"Correct response: What is {question.correct_response}?")

        correct_raw = input("Were you correct? (y/n/skip): ").strip().lower()
        if correct_raw == "y":
            correct = True
        elif correct_raw == "n":
            correct = False
        else:
            correct = None

        return Attempt(
            clue_id=question.clue_id,
            category=question.category,
            clue_text=question.clue_text,
            correct_response=question.correct_response,
            buzz_delta_ms=buzz_delta_ms,
            early_buzz=False,
            correct=correct,
        )
