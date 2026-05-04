# install_and_run.py

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"

if os.name == "nt":
    PYTHON = VENV / "Scripts" / "python.exe"
else:
    PYTHON = VENV / "bin" / "python"

if not PYTHON.exists():
    subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])

subprocess.check_call([str(PYTHON), "-m", "pip", "install", "--upgrade", "pip"])
subprocess.check_call([str(PYTHON), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])

