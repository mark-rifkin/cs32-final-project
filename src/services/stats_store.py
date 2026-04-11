import json
from pathlib import Path
from dataclasses import asdict
from src.models import Attempt

class StatsStore:
    def __init__(self, path: str = "data/stats.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        if not self.path.exists():
            self.path.write_text(json.dumps({"attempts": []}, indent=2), encoding="utf-8")

    def load(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save_attempt(self, attempt: Attempt) -> None:
        data = self.load()
        data["attempts"].append(asdict(attempt))
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")