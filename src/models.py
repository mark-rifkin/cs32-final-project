from dataclasses import dataclass, asdict
from typing import Optional
from datetime import date

'''Class for question information, dataclass automatically adds init'''
@dataclass
class Question:
    clue_id: str
    air_date: date | None
    round: str
    category: str
    value: int
    clue_text: str
    correct_response: str


@dataclass
class Attempt:
    clue_id: str
    category: str
    clue_text: str
    correct_response: str
    buzz_delta_ms: float
    early_buzz: bool
    correct: bool