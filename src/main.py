from src.services.question_service import QuestionService
from src.services.tts_service import TTSService
from src.round_control import RoundControl
from src.services.stats_store import StatsStore


def main():
    questions = QuestionService()
    tts = TTSService()
    stats = StatsStore()
    ctrl = RoundControl(tts)

    print("Podium: a Jeopardy training app (console draft)")
    while True:
        user_input = input("Press Enter for a new clue, or q to quit: ").strip().lower()
        if user_input == "q":
            break

        try:
            question = questions.get_random_question()
            attempt = ctrl.run(question)
            stats.save_attempt(attempt)
            print("Saved.\n")
        except Exception as exc:
            print(f"Error: {exc}\n")


if __name__ == "__main__":
    main()