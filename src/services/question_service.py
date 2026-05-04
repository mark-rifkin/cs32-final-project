'''Retrieves question from online API and converts into 
Question class format
'''
import requests
from datetime import datetime
import re
from ..models import Question

class QuestionService:
    URL = "https://jeopardy.drun.sh/api/v1/random_question"

    ''' Removes backslashes before close quote
    '''
    @staticmethod
    def _clean_text(text: str) -> str:
        return text.replace('\\"', '"')

    def get_random_question(self) -> Question:
        # Retrieve dictionary from API 
        response = requests.get(self.URL, timeout=10)
        response.raise_for_status()
        data = response.json()

        air_date_str = data.get("air_date")
        air_date = None

        if air_date_str: # check that API actually returned 
            try:
                air_date = datetime.fromisoformat(
                    air_date_str.replace("Z", "+00:00")
                ).date()
            except ValueError: # if not in valid date format
                pass 

        # clean question value
        value_str = data.get("value")
        value = None
        if value_str: # remove $ and convert to int
            match = re.search(r"\d+", value_str)
            value = int(match.group()) if match else None

        category = self._clean_text(data.get("category", ""))
        clue_text = self._clean_text(data.get("answer", ""))

        return Question(
            clue_id=str(data.get("id", "")),
            air_date=air_date,
            round=data.get("round", ""),
            category=category,
            value=value,
            clue_text=clue_text,
            correct_response=data.get("question", ""),
            )
    
