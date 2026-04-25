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
    question = questions.get_random_question()
    cache_key = question.clue_id or question.clue_text
    audio_path = tts.prepare(question.clue_text, cache_key)
    return question, audio_path


def main():
    questions = QuestionService()
    tts = TTSService()
    stats = StatsStore()
    ctrl = RoundControl(tts)

    with ThreadPoolExecutor(max_workers=1) as executor:
        try:
            next_round_future = executor.submit(_load_round_assets, questions, tts)

            print("Podium: a Jeopardy training app (console draft)")
            while True:
                user_input = input("Press Enter for a new clue, or q to quit: ").strip().lower()
                if user_input == "q":
                    break

                try:
                    question, audio_path = next_round_future.result()
                except Exception as exc:
                    next_round_future = executor.submit(_load_round_assets, questions, tts)
                    print(f"Error: {exc}\n")
                    continue

                next_round_future = executor.submit(_load_round_assets, questions, tts)

                try:
                    attempt = ctrl.run(question, audio_path)
                    stats.save_attempt(attempt)
                    print("Saved.\n")
                except Exception as exc:
                    print(f"Error: {exc}\n")
        finally:
            tts.close()


if __name__ == "__main__":
    main()
