"""
Python Keylogger Package - Educational purposes only.
Use only on systems you own or have permission to test.
"""

from .config import KeyloggerConfig, load_config_from_env
from .core import Keylogger
from .client import KeyloggerClient
from .buffer import KeyBuffer
from .logger import KeyloggerLogger

__version__ = "2.0.0"
__all__ = [
    "KeyloggerConfig",
    "load_config_from_env",
    "Keylogger",
    "KeyloggerClient",
    "KeyBuffer",
    "KeyloggerLogger",
]