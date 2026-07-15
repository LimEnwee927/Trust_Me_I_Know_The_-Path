"""Serves the GUI page itself plus sender.py's live status JSON over plain HTTP.

Run this in the ROOT namespace (a normal terminal on the Mininet VM, NOT an
`xterm h1`/`xterm h2` window) alongside the controller and topology:

    python3 status_server.py

Then open the URL it prints (e.g. http://10.0.0.5:8090/) in a browser -
on this same machine, or over the network from anywhere that can reach it.
Serving the page itself (rather than opening PCN_Project/index.html as a
local file) matters because index.html's JS talks to this server and to
link_control_server.py using whatever host the page was loaded FROM
(`location.hostname`) - if the page is instead opened as a local file on a
different machine than the one running these servers, every request it
makes silently fails to connect, since 127.0.0.1 in that browser refers to
the wrong machine. Loading the page from here sidesteps that entirely.

CORS is wide open since this only ever serves non-sensitive local telemetry
to whoever can already reach this host.
"""
import json
import os
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer

from status_publisher import STATUS_FILE

HOST = "0.0.0.0"
PORT = 8090

INDEX_HTML = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "PCN_Project", "index.html"
)


def _lan_ip():
    """Best-effort outbound IP (no packets actually sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._serve_index()
        elif self.path == "/status":
            self._serve_status()
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_index(self):
        try:
            with open(INDEX_HTML, "rb") as f:
                body = f.read()
        except FileNotFoundError:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"index.html not found next to PCN_Project/")
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_status(self):
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
    print(f"[STATUS SERVER] Open the GUI at: http://{_lan_ip()}:{PORT}/")
    print(f"[STATUS SERVER] (also reachable at http://127.0.0.1:{PORT}/ on this machine)")
    HTTPServer((HOST, PORT), StatusHandler).serve_forever()
