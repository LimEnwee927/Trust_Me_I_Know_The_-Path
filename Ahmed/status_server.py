"""Serves sender.py's live status JSON (status_publisher.STATUS_FILE) over plain HTTP.

Run this in the ROOT namespace (a normal terminal on the Mininet VM, NOT an
`xterm h1`/`xterm h2` window) alongside the controller and topology, then open
PCN_Project/index.html in a browser on the same machine:

    python3 status_server.py

The browser polls http://127.0.0.1:8090/status. CORS is wide open since this
only ever serves non-sensitive local telemetry to a page on the same machine.
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from status_publisher import STATUS_FILE

HOST = "0.0.0.0"
PORT = 8090


class StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/status":
            self.send_response(404)
            self.end_headers()
            return

        try:
            with open(STATUS_FILE, "rb") as f:
                body = f.read()
        except FileNotFoundError:
            body = json.dumps({"error": "no status yet - is sender.py running?"}).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    print(f"[STATUS SERVER] Reading {STATUS_FILE}")
    print(f"[STATUS SERVER] Serving http://127.0.0.1:{PORT}/status")
    HTTPServer((HOST, PORT), StatusHandler).serve_forever()
