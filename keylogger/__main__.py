"""
Main entry point for the basic keylogger.
This provides a simple interface for running the keylogger directly.
Supports both: python -m keylogger AND python keylogger/__main__.py
"""

import sys
import os

# Add parent directory to path to allow direct execution
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from keylogger.core import main
else:
    from .core import main

if __name__ == "__main__":
    main()