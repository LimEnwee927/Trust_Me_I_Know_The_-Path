"""HTTP control server that lets the browser GUI drive the real backend.

Must run inside the my_topology.py process, since that's the process holding
the live `net` object. Starts on a background thread alongside the Mininet
CLI so `my_topology.py` doesn't need any other changes to its own flow.

    POST /link/down    -> net.configLinkStatus('s5', 's4', 'down')
    POST /link/up      -> net.configLinkStatus('s5', 's4', 'up')
    GET  /link/state   -> {"up": bool}

    POST /sender/start -> opens an xterm on h1 (the same mechanism the Mininet
                           CLI's `xterm h1` command uses) running
                           `python3 sender.py --iface h1-eth1`
    POST /sender/stop  -> closes that xterm if still open
    GET  /sender/state -> {"running": bool}

    POST /sender/send100 -> opens a fresh xterm on h1 running
                             `python3 sender.py --iface h1-eth1 --max-packets 100`
                             The window is left open (drops to a shell) after
                             sender.py exits, independent of /sender/start.

    POST /hostb/start   -> opens an xterm on h2 running `python3 host_b.py`.
                            The window is left open (drops to a shell) after
                            host_b.py exits/is closed.
    GET  /hostb/state   -> {"running": bool}

CORS is wide open since this only ever serves a page on the same machine.
"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from mininet.term import makeTerm

HOST = "0.0.0.0"
PORT = 8091

SENDER_HOST_NAME = "h1"
SENDER_CWD = os.path.dirname(os.path.abspath(__file__))
SENDER_SCRIPT = os.path.join(SENDER_CWD, "run_sender.sh")
SENDER_TERM_CMD = f"bash {SENDER_SCRIPT}"

SEND100_SCRIPT = os.path.join(SENDER_CWD, "run_sender_100.sh")
SEND100_TERM_CMD = f"bash {SEND100_SCRIPT}"

HOSTB_HOST_NAME = "h2"
HOSTB_SCRIPT = os.path.join(SENDER_CWD, "run_host_b.sh")
HOSTB_TERM_CMD = f"bash {HOSTB_SCRIPT}"


def _make_handler(net, link_state, sender_state, sender_lock, hostb_state, hostb_lock):
    class ControlHandler(BaseHTTPRequestHandler):
        def _cors(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

        def _send_json(self, code, payload):
            body = json.dumps(payload).encode()
            self.send_response(code)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            if self.path == "/link/state":
                self._send_json(200, link_state)
            elif self.path == "/sender/state":
                self._send_json(200, {"running": _sender_running(sender_state, sender_lock)})
            elif self.path == "/hostb/state":
                self._send_json(200, {"running": _hostb_running(hostb_state, hostb_lock)})
            else:
                self._send_json(404, {"error": "not found"})

        def do_POST(self):
            try:
                if self.path == "/link/down":
                    net.configLinkStatus("s5", "s4", "down")
                    link_state["up"] = False
                    print("[LINK CONTROL] s5-s4 -> down")
                    self._send_json(200, link_state)
                elif self.path == "/link/up":
                    net.configLinkStatus("s5", "s4", "up")
                    link_state["up"] = True
                    print("[LINK CONTROL] s5-s4 -> up")
                    self._send_json(200, link_state)
                elif self.path == "/sender/start":
                    running = _sender_start(net, sender_state, sender_lock)
                    self._send_json(200, {"running": running})
                elif self.path == "/sender/stop":
                    _sender_stop(sender_state, sender_lock)
                    self._send_json(200, {"running": False})
                elif self.path == "/sender/send100":
                    _sender_send100(net, sender_state, sender_lock)
                    self._send_json(200, {"opened": True})
                elif self.path == "/hostb/start":
                    running = _hostb_start(net, hostb_state, hostb_lock)
                    self._send_json(200, {"running": running})
                else:
                    self._send_json(404, {"error": "not found"})
            except Exception as e:
                print(f"[CONTROL] error handling POST {self.path}: {e!r}")
                self._send_json(500, {"error": str(e), "running": False})

        def log_message(self, fmt, *args):
            pass

    return ControlHandler


def _sender_running(sender_state, sender_lock):
    with sender_lock:
        terms = sender_state.get("terms") or []
        return any(p.poll() is None for p in terms)


def _sender_start(net, sender_state, sender_lock):
    with sender_lock:
        terms = sender_state.get("terms") or []
        if any(p.poll() is None for p in terms):
            return True  # xterm window is already open

        host = net.get(SENDER_HOST_NAME)
        terms = makeTerm(host, title="sender.py", term="xterm", cmd=SENDER_TERM_CMD)
        if not terms:
            raise RuntimeError(
                "makeTerm() returned nothing - is DISPLAY/X11 set up? "
                "(same requirement as running 'xterm h1' in the Mininet CLI)"
            )
        net.terms += terms
        sender_state["terms"] = terms
        print(f"[SENDER CONTROL] opened xterm on {SENDER_HOST_NAME} running sender.py")
        return True


def _sender_stop(sender_state, sender_lock):
    with sender_lock:
        terms = sender_state.get("terms") or []
        for p in terms:
            if p.poll() is None:
                p.terminate()
        sender_state["terms"] = []
        print("[SENDER CONTROL] closed sender.py xterm")


def _sender_send100(net, sender_state, sender_lock):
    with sender_lock:
        host = net.get(SENDER_HOST_NAME)
        terms = makeTerm(host, title="sender.py (100 pkts)", term="xterm", cmd=SEND100_TERM_CMD)
        if not terms:
            raise RuntimeError(
                "makeTerm() returned nothing - is DISPLAY/X11 set up? "
                "(same requirement as running 'xterm h1' in the Mininet CLI)"
            )
        net.terms += terms
        sender_state.setdefault("send100_terms", []).extend(terms)
        print(f"[SENDER CONTROL] opened xterm on {SENDER_HOST_NAME} "
              f"running sender.py --max-packets 100")


def _hostb_running(hostb_state, hostb_lock):
    with hostb_lock:
        terms = hostb_state.get("terms") or []
        return any(p.poll() is None for p in terms)


def _hostb_start(net, hostb_state, hostb_lock):
    with hostb_lock:
        terms = hostb_state.get("terms") or []
        if any(p.poll() is None for p in terms):
            return True  # xterm window is already open

        host = net.get(HOSTB_HOST_NAME)
        terms = makeTerm(host, title="host_b.py", term="xterm", cmd=HOSTB_TERM_CMD)
        if not terms:
            raise RuntimeError(
                "makeTerm() returned nothing - is DISPLAY/X11 set up? "
                "(same requirement as running 'xterm h2' in the Mininet CLI)"
            )
        net.terms += terms
        hostb_state["terms"] = terms
        print(f"[HOSTB CONTROL] opened xterm on {HOSTB_HOST_NAME} running host_b.py")
        return True


def start(net):
    """Start the control server on a daemon thread and return it."""
    link_state = {"up": True}
    sender_state = {"terms": []}
    sender_lock = threading.Lock()
    hostb_state = {"terms": []}
    hostb_lock = threading.Lock()

    handler = _make_handler(net, link_state, sender_state, sender_lock, hostb_state, hostb_lock)
    server = HTTPServer((HOST, PORT), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"[LINK CONTROL] Serving http://127.0.0.1:{PORT} "
          f"(POST /link/down, /link/up, /sender/start, /sender/stop, "
          f"/sender/send100, /hostb/start)")
    return server
