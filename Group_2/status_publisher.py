import json
import os
import tempfile
import time

STATUS_FILE = os.path.join(tempfile.gettempdir(), "pcn_status.json")


def publish(flow, stats, dest_cfg):
    """Write the sender's current routing/traffic state as JSON for status_server.py to serve.

    Mininet hosts are separate network namespaces but share the host filesystem,
    so writing to STATUS_FILE here makes it visible outside h1's namespace too.
    """
    full_path = ["H1"] + flow["current_path"]
    payload = {
        "current_path": [node.lower() for node in full_path],
        "on_backup": flow["current_path"] == dest_cfg["backup_path"],
        "rerouting": flow["rerouting"],
        "reroute_done": flow["reroute_done"],
        "path_flap_count": flow["path_flap_count"],
        "sent_total": stats["sent_total"],
        "primary_sent": stats["primary_sent"],
        "backup_sent": stats["backup_sent"],
        "dropped_total": stats["dropped_total"],
        "last_update": time.time(),
    }

    # Write to a temp file then rename, so the HTTP server never reads a half-written file.
    tmp_path = STATUS_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(payload, f)
    os.replace(tmp_path, STATUS_FILE)
