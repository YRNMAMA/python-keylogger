"""
Logging module for the keylogger.
Provides structured logging with file rotation and console output.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

from .config import KeyloggerConfig


class KeyloggerLogger:
    """Structured logger with file rotation."""

    def __init__(self, config: KeyloggerConfig) -> None:
        self.logger = logging.getLogger("keylogger")
        self.logger.setLevel(getattr(logging, config.log_level.upper()))
        self.logger.propagate = False

        # Clear existing handlers
        self.logger.handlers.clear()

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, config.log_level.upper()))
        console_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # File handler with rotation (if log_file specified)
        if config.log_file:
            log_path = Path(config.log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.handlers.RotatingFileHandler(
                config.log_file,
                maxBytes=config.log_max_bytes,
                backupCount=config.log_backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(getattr(logging, config.log_level.upper()))
            file_formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

    def get_logger(self) -> logging.Logger:
        return self.logger


def get_logger(name: str = "keylogger", level: int = logging.INFO) -> logging.Logger:
    """Get a simple logger instance for modules that don't need full config."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(level)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        )
        logger.addHandler(handler)
    return logger