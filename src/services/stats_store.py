import json
from pathlib import Path
from dataclasses import asdict
from datetime import datetime

from src.models import Attempt


class StatsStore:
    def __init__(self, path: str | None = None):
        """Initializes and creates JSON stats storage if nonexistent."""
        if path is None:
            path = Path(__file__).resolve().parents[2] / "data" / "stats.json"
        else:
            path = Path(path)

        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

        if not self.path.exists():
            self.path.write_text(json.dumps({"sessions": []}, indent=2), encoding="utf-8")

        self.current_session_id: int | None = None

    def load(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def start_session(self) -> int:
        '''Start a stats session. Assigns a new id and adds a new dict to 
        JSON file for the active session'''

        data = self.load()
        sessions = data.get("sessions", [])

        # assign next id. robust to skips in session id if json is corrupted or changed (does not re-assign ids)
        next_id = 1 if not sessions else max(session["id"] for session in sessions) + 1

        session = {
            "id": next_id,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "attempts": [],
        }
        sessions.append(session)
        data["sessions"] = sessions
        self.save(data)

        self.current_session_id = next_id
        return next_id

    
    def save_attempt(self, attempt: Attempt) -> None:
        '''Adds a single attempt to the current session'''
        if self.current_session_id is None:
            raise RuntimeError("No active session. Call start_session() first.")

        data = self.load()

        for session in data.get("sessions", []):
            if session["id"] == self.current_session_id:
                session["attempts"].append(asdict(attempt))
                self.save(data)
                return

        raise RuntimeError(f"Active session {self.current_session_id} not found.")

    def _get_attempts(self, scope: str = "overall") -> list[dict]:
        '''Internal helper for collecting all session or overall attempts'''
        data = self.load()
        sessions = data.get("sessions", [])

        if scope == "current":
            if self.current_session_id is None:
                return []

            for session in sessions:
                if session["id"] == self.current_session_id:
                    return session.get("attempts", [])
            return []

        if scope == "overall":
            all_attempts = []
            for session in sessions:
                all_attempts.extend(session.get("attempts", []))
            return all_attempts

        raise ValueError("scope must be 'current' or 'overall'")

    def summary_stats(self, scope: str = "overall") -> dict:
        '''Summary statistics for current or overall attempts'''
        attempts = self._get_attempts(scope)

        total_clues = len(attempts)
        buzzed = [a for a in attempts if a.get("buzz_delta_ms") is not None]
        skipped = [a for a in attempts if a.get("buzz_delta_ms") is None]
        answered = [a for a in attempts if a.get("correct") is not None]
        correct_attempts = [a for a in attempts if a.get("correct") is True]
        early_buzzes = [a for a in attempts if a.get("early_buzz") is True]
        buzz_times = [a["buzz_delta_ms"] for a in buzzed if a.get("buzz_delta_ms") is not None]

        accuracy = None
        if answered:
            accuracy = 100.0 * len(correct_attempts) / len(answered)

        avg_buzz_ms = None
        if buzz_times:
            avg_buzz_ms = sum(buzz_times) / len(buzz_times)

        fastest_buzz_ms = min(buzz_times) if buzz_times else None
        slowest_buzz_ms = max(buzz_times) if buzz_times else None

        return {
            "scope": scope,
            "total_clues": total_clues,
            "buzzed": len(buzzed),
            "skipped": len(skipped),
            "answered": len(answered),
            "correct": len(correct_attempts),
            "early_buzzes": len(early_buzzes),
            "accuracy_pct": accuracy,
            "avg_buzz_ms": avg_buzz_ms,
            "fastest_buzz_ms": fastest_buzz_ms,
            "slowest_buzz_ms": slowest_buzz_ms,
        }

    def summary_text(self, scope: str = "overall") -> str:
        '''Formatted summary of overall or current session attempts'''
        summary = self.summary_stats(scope)
        title = "Current session summary" if scope == "current" else "Overall summary"

        lines = [
            "",
            title,
            "-" * 40,
            f"Total clues seen: {summary['total_clues']}",
            f"Buzzed:           {summary['buzzed']}",
            f"Skipped:          {summary['skipped']}",
            f"Answered:         {summary['answered']}",
            f"Correct:          {summary['correct']}",
            f"Early buzzes:     {summary['early_buzzes']}",
        ]

        if summary["accuracy_pct"] is None:
            lines.append("Accuracy:         n/a")
        else:
            lines.append(f"Accuracy:         {summary['accuracy_pct']:.1f}%")

        if summary["avg_buzz_ms"] is None:
            lines.append("Average buzz:     n/a")
            lines.append("Fastest buzz:     n/a")
            lines.append("Slowest buzz:     n/a")
        else:
            lines.append(f"Average buzz:     {summary['avg_buzz_ms']:.1f} ms")
            lines.append(f"Fastest buzz:     {summary['fastest_buzz_ms']:.1f} ms")
            lines.append(f"Slowest buzz:     {summary['slowest_buzz_ms']:.1f} ms")

        return "\n".join(lines)