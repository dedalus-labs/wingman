"""
Wingman - AI Coding Assistant
=============================
Your copilot for the terminal.

Run: python -m wingman
"""

from .app import WingmanApp, main
from .config import APP_NAME, APP_VERSION

__version__ = APP_VERSION

__all__ = ["WingmanApp", "main", "APP_NAME", "APP_VERSION", "__version__"]
