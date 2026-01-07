"""
Wingman - AI Coding Assistant
=============================
Your copilot for the terminal.

Run: python -m wingman
Headless: python -m wingman -p "your prompt"
"""

from .app import WingmanApp, main
from .config import APP_NAME, APP_VERSION
from .headless import run_headless

__all__ = ["WingmanApp", "main", "run_headless", "APP_NAME", "APP_VERSION"]
__version__ = APP_VERSION
