"""
conftest.py at project root — adds the project directory to sys.path so that
pytest can resolve imports like `from agents.fap.models import ...`
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
