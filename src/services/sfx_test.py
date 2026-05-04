"""Testing class for sound effects
Edit to play desired SFX and run with python-m src.services.sfx_test. 
"""

from src.services.sfx_service import SFXService
import time


sfx = SFXService()
sfx.reset_assets()

sfx.play_intro_theme()
time.sleep(5)

