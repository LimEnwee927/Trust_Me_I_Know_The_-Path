import socket
import threading
import time


class AckListener(threading.Thread):
    def __init__(
        self, target_ip, on_failure_callback, ack_timeout=0.2, max_missed=3
    ):
        super().__init__(daemon=True)
        self.target_ip = target_ip  
        self.on_failure = on_failure_callback
        self.ack_timeout = ack_timeout
        self.max_missed = max_missed

        self.running = True
        self.failure_triggered = False
        self.missed = 0
        self.lock = threading.Lock()

        self.stats = {
            "acks_received": 0,
            "acks_missed": 0,
            "failures_detected": 0,
            "acks_before_failure": 0,
            "failure_detect_time": None,
            "last_ack_time": None,
        }

    def run(self):
        sock = socket.socket(
            socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP
        )
        sock.settimeout(self.ack_timeout)

        print(
            f"[ACK] Listening ICMP from target_ip={self.target_ip} "
            f"timeout={self.ack_timeout}s max_missed={self.max_missed}"
        )

        while self.running:
            try:
                data, addr = sock.recvfrom(1024)
                if not data:
                    continue

                if addr[0] != self.target_ip:
                    continue

                with self.lock:
                    self.missed = 0
                    self.stats["acks_received"] += 1
                    self.stats["last_ack_time"] = time.time()

            except socket.timeout:
                with self.lock:
                    self.missed += 1
                    self.stats["acks_missed"] += 1
                    missed = self.missed
                    failed = self.failure_triggered

                print(f"[ACK] Probe timeout {missed}/{self.max_missed}")

                if (not failed) and missed >= self.max_missed:
                    with self.lock:
                        self.failure_triggered = True
                        self.stats["failures_detected"] += 1
                        self.stats["acks_before_failure"] = (
                            self.stats["acks_received"]
                        )
                        self.stats["failure_detect_time"] = time.time()

                    print("[ACK] Path failure detected")
                    self.missed = 0
                    self.on_failure()

    def get_stats(self):
        with self.lock:
            return dict(self.stats)
        



# class AckListener(threading.Thread):
#     def __init__(self, listen_port, on_failure_callback, ack_timeout=0.2, max_missed=3):
#         super().__init__(daemon=True)
#         self.port = listen_port
#         self.on_failure = on_failure_callback
#         self.ack_timeout = ack_timeout
#         self.max_missed = max_missed

#         self.running = True
#         self.failure_triggered = False
#         self.missed = 0
#         self.lock = threading.Lock()

#         self.stats = {
#             "acks_received": 0,
#             "acks_missed": 0,
#             "failures_detected": 0,
#             "acks_before_failure": 0,
#             "failure_detect_time": None,
#             "last_ack_time": None,
#         }

#     def run(self):
#         sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#         sock.bind(("0.0.0.0", self.port))
#         sock.settimeout(self.ack_timeout)

#         print(
#             f"[ACK] Listening on port={self.port} "
#             f"timeout={self.ack_timeout}s max_missed={self.max_missed}"
#         )

#         while self.running:
#             try:
#                 data, _ = sock.recvfrom(256)
#                 if not data:
#                     continue

#                 with self.lock:
#                     self.missed = 0
#                     self.stats["acks_received"] += 1
#                     self.stats["last_ack_time"] = time.time()

#             except socket.timeout:
#                 with self.lock:
#                     self.missed += 1
#                     self.stats["acks_missed"] += 1
#                     missed = self.missed
#                     failed = self.failure_triggered

#                 print(f"[ACK] Probe timeout {missed}/{self.max_missed}")

#                 if (not failed) and missed >= self.max_missed:
#                     with self.lock:
#                         self.failure_triggered = True
#                         self.stats["failures_detected"] += 1
#                         self.stats["acks_before_failure"] = self.stats["acks_received"]
#                         self.stats["failure_detect_time"] = time.time()

#                     print("[ACK] Path failure detected")
#                     self.on_failure()

#     def get_stats(self):
#         with self.lock:
#             return dict(self.stats)