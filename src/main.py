from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.models import Question
from src.round_control import RoundControl
from src.services.question_service import QuestionService
from src.services.stats_store import StatsStore
from src.services.tts_service import TTSService


def _load_round_assets(
    questions: QuestionService, tts: TTSService
) -> tuple[Question, Path]:
    '''Loads audio file for a random question into cache'''
    question = questions.get_random_question()
    cache_key = question.clue_id or question.clue_text
    audio_path = tts.prepare(question.clue_text, cache_key)
    return question, audio_path


def main():
    questions = QuestionService()
    tts = TTSService()
    stats = StatsStore()
    ctrl = RoundControl(tts)
    stats.start_session()

    with ThreadPoolExecutor(max_workers=1) as executor:
        try:
            # Create thread to pre-load audio file for next round
            next_round_future = executor.submit(_load_round_assets, questions, tts)

            print("Podium: a Jeopardy training app (console draft)")
            # Main loop
            while True:
                user_input = input("Press Enter for a new clue, or q to quit: ").strip().lower()
                if user_input == "q": # session ended, print summary statistics
                    print(stats.summary_text("current"))
                    print(stats.summary_text("overall"))
                    break

                try:
                    # retrieve pre-loaded audio
                    question, audio_path = next_round_future.result()
                except Exception as exc:
                    next_round_future = executor.submit(_load_round_assets, questions, tts)
                    print(f"Error: {exc}\n")
                    continue

                # pre-load next round audio
                next_round_future = executor.submit(_load_round_assets, questions, tts)

                try:
                    # run round
                    attempt = ctrl.run(question, audio_path)
                    stats.save_attempt(attempt)
                    print("Saved.\n")
                except Exception as exc:
                    print(f"Error: {exc}\n")
        finally:
            tts.close()


if __name__ == "__main__":
    main()
