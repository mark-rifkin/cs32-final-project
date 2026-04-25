import msvcrt
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.models import Attempt, Question
from src.services.tts_service import TTSService


class RoundControl:
    EARLY_LOCKOUT_MS = 250 # lockout time if early buzz
    ANSWER_TIME_S = 5 # time to answer after buzzing
    NO_BUZZ_TIMEOUT_S = 5 # time before auto-neg
    POLL_INTERVAL_S = 0.01 # time between console input checks

    def __init__(self, tts: TTSService):
        self.tts = tts

    def _drain_keyboard_buffer(self) -> None:
        """ Clear keyboard presses by looping
            through and reading keypresses. 
            Called before round
        """
        while msvcrt.kbhit():
            msvcrt.getwch()

    def _maybe_print_countdown(
          
            self,
            label: str,
            deadline: float,
            last_displayed: int | None,
        ) -> int | None:
            '''Prints countdown time if integer value
            '''
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                return last_displayed

            displayed = int(remaining + 0.999)  # 4.2 -> 5, 3.0 -> 3
            if displayed != last_displayed:
                print(f"{label}: {displayed}")
                return displayed

            return last_displayed

    def run(self, question: Question, audio_path: Path) -> Attempt:
        ''' Main logic for round running
            question: question object with clue and respons
            audio_path: path to pre-generated audio file
        '''
        # Show clue
        print()
        print("=" * 60)
        print(question.category)
        print(question.clue_text)
        print("=" * 60)
        print()

        self._drain_keyboard_buffer()

        # State variables for round
        early_buzzed = False
        unlock_time = None
        buzz_time = None
        locked_until = 0.0
        buzz_deadline = None
        buzz_countdown = None

        with ThreadPoolExecutor(max_workers=1) as executor:
            # Play audio in background thread, so it doesn't block buzzing
            # Can call .done() to check status
            play_future = executor.submit(self.tts.play_file, audio_path)

            print("Reading clue... press Enter to buzz.")
            print("After unlock: Enter = buzz, s = skip.")

            # Buzzer loop
            while True:
                now = time.perf_counter()

                # Check if audio is finished playing and unlock
                if unlock_time is None and play_future.done():
                    play_future.result() # raise any exceptions
                    unlock_time = now
                    buzz_deadline = unlock_time + self.NO_BUZZ_TIMEOUT_S
                    print("\nBuzzer unlocked!")

                # Print buzz countdown if unlocked
                if buzz_deadline is not None:
                    buzz_countdown = self._maybe_print_countdown(
                        "Buzz window",
                        buzz_deadline,
                        buzz_countdown,
                    )

                # Poll for key presses 
                if msvcrt.kbhit():
                    key = msvcrt.getwch().lower()
                    now = time.perf_counter()

                    # check for enter key (buzz)
                    if key == "\r":
                        # check for early buzz
                        if unlock_time is None:
                            early_buzzed = True
                            locked_until = now + self.EARLY_LOCKOUT_MS / 1000.0
                            print(f"Too early. Locked out for {self.EARLY_LOCKOUT_MS} ms.")
                            continue

                        # check for early re-buzz
                        if now < locked_until:
                            remaining_ms = (locked_until - now) * 1000.0
                            print(f"Still locked out for {remaining_ms:.0f} ms.")
                            continue

                        buzz_time = now
                        break
                    
                    # check for skip
                    if key == "s" and unlock_time is not None:
                        print(f"Skipped. Correct response: What is {question.correct_response}?")
                        return Attempt(
                            clue_id=question.clue_id,
                            category=question.category,
                            clue_text=question.clue_text,
                            correct_response=question.correct_response,
                            buzz_delta_ms=None,
                            early_buzz=early_buzzed,
                            correct=False,
                        )

                # check for buzz timeout
                if buzz_deadline is not None and now >= buzz_deadline:
                    print("\nNo buzz within 5 seconds.")
                    print(f"Correct response: What is {question.correct_response}?")
                    return Attempt(
                        clue_id=question.clue_id,
                        category=question.category,
                        clue_text=question.clue_text,
                        correct_response=question.correct_response,
                        buzz_delta_ms=None,
                        early_buzz=early_buzzed,
                        correct=None,
                    )

                time.sleep(self.POLL_INTERVAL_S)
                # restart buzz loop

        buzz_delta_ms = (buzz_time - unlock_time) * 1000.0
        print(f"Buzz time: {buzz_delta_ms:.1f} ms")

        print(f"\nYou have {self.ANSWER_TIME_S} seconds to answer out loud.")
        answer_deadline = time.perf_counter() + self.ANSWER_TIME_S
        answer_countdown = None

        # run answer countdown
        while time.perf_counter() < answer_deadline:
            answer_countdown = self._maybe_print_countdown(
                "Answer time",
                answer_deadline,
                answer_countdown,
            )
            time.sleep(self.POLL_INTERVAL_S)

        print(f"Correct response: What is {question.correct_response}?")

        # ask user to self-check answer
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
            early_buzz=early_buzzed,
            correct=correct,
        )