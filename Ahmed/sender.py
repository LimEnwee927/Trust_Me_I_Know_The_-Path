import argparse
import queue
import threading
import time
from scapy.all import sendp, conf

from topology import Topology
from path_encoder import PathEncoder
from rerouter import Rerouter
from ack_listener import AckListener
from stats_utils import summarize, jitter, export_run_csv, export_timeseries_csv

PING_FREQUENCY = 0

parser = argparse.ArgumentParser()
parser.add_argument("--src-ip", default="10.0.0.1")
parser.add_argument("--dst-ip", default="10.0.0.2")
parser.add_argument("--iface", default="h1-eth1")
parser.add_argument("--data-rate", type=float, default=0.1)
parser.add_argument("--probe-rate", type=float, default=0.2)
parser.add_argument("--ack-port", type=int, default=9999)
parser.add_argument("--probe-timeout", type=float, default=PING_FREQUENCY+0.2)
parser.add_argument("--max-missed", type=int, default=3)
parser.add_argument("--max-packets", type=int, default=1000)
args = parser.parse_args()

conf.verb = 0

PRIMARY_PATH = ["S1", "S5", "S4", "H2"]
BACKUP_PATH = ["S1", "S2", "S3", "S4", "H2"]
FAILED_LINK = ("S5", "S4")
REROUTE_DESTINATION_SWITCH = "S4"

topo = Topology()
encoder = PathEncoder(topo)
rerouter = Rerouter(topo, source="S1", destination=REROUTE_DESTINATION_SWITCH)

current_path = PRIMARY_PATH[:]
# print(f"current_path: {current_path}")
current_ports = encoder.path_to_ports(current_path)

data_queue = queue.Queue(maxsize=5000)
lock = threading.Lock()

seq = 0
rerouting = False
reroute_done = False
reroute_start_time = None
reroute_end_time = None
first_backup_send_time = None
path_flap_count = 0
producer_done = False
sender_done = False
program_start = time.time()

stats = {
    "built_total": 0,
    "sent_total": 0,
    "dropped_total": 0,
    "packets_affected_by_reroute": 0,
    "primary_sent": 0,
    "backup_sent": 0,
    "send_times": [],
    "general_queue_wait_times": [],
    "reroute_wait_times": [],
    "queue_sizes_during_reroute": [],
}


def build_data_packet(seq_num, path, ports):
    payload = f"type=data|seq={seq_num}|path={'-'.join(path)}".encode()
    return encoder.encode(payload, ports, args.dst_ip, args.src_ip, seq_num, dport=5000, sport=5001)


def build_probe_packet(probe_seq, path, ports):
    payload = f"type=probe|probe={probe_seq}|path={'-'.join(path)}".encode()
    return encoder.encode(payload, ports, args.dst_ip, args.src_ip, probe_seq, dport=6000, sport=6001)


def probe_loop():
    probe_seq = 0
    while not sender_done:
        with lock:
            path = current_path[:]
            ports = current_ports[:]
        pkt = build_probe_packet(probe_seq, path, ports)
        sendp(pkt, iface=args.iface, verbose=0)
        probe_seq += 1
        time.sleep(args.probe_rate)


def producer_loop():
    global seq, producer_done
    while seq < args.max_packets:
        item = {"seq": seq, "enqueue_time": time.time(), "reroute_block_start": None}
        try:
            data_queue.put(item, timeout=1)
            stats["built_total"] += 1
            seq += 1
        except queue.Full:
            stats["dropped_total"] += 1
        time.sleep(args.data_rate)
    producer_done = True


def sender_loop():
    global sender_done, first_backup_send_time
    while True:
        if producer_done and data_queue.empty():
            sender_done = True
            return

        try:
            item = data_queue.get(timeout=0.2)
        except queue.Empty:
            continue

        general_wait = time.time() - item["enqueue_time"]
        stats["general_queue_wait_times"].append(general_wait)
        reroute_marked = False

        while True:
            with lock:
                local_rerouting = rerouting
            if not local_rerouting:
                break
            if not reroute_marked:
                item["reroute_block_start"] = time.time()
                reroute_marked = True
                stats["packets_affected_by_reroute"] += 1
            stats["queue_sizes_during_reroute"].append(data_queue.qsize())
            time.sleep(0.001)

        if item["reroute_block_start"] is not None:
            stats["reroute_wait_times"].append(time.time() - item["reroute_block_start"])

        with lock:
            send_path = current_path[:]
            send_ports = current_ports[:]

        pkt = build_data_packet(item["seq"], send_path, send_ports)
        t0 = time.perf_counter()
        sendp(pkt, iface=args.iface, verbose=0)
        t1 = time.perf_counter()

        stats["send_times"].append(t1 - t0)
        stats["sent_total"] += 1

        if send_path == PRIMARY_PATH:
            stats["primary_sent"] += 1
        elif send_path == BACKUP_PATH:
            stats["backup_sent"] += 1
            if first_backup_send_time is None:
                with lock:
                    if first_backup_send_time is None:
                        first_backup_send_time = time.time()

        print(f"[SENDER] sent_seq={item['seq']} path={'-'.join(send_path)} ports={send_ports}")
        time.sleep(PING_FREQUENCY)


def on_failure():
    global current_path, current_ports
    global rerouting, reroute_done, reroute_start_time, reroute_end_time, path_flap_count

    with lock:
        if rerouting or reroute_done:
            return
        rerouting = True
        reroute_start_time = time.time()

    new_switch_path = rerouter.handle_failure(FAILED_LINK[0], FAILED_LINK[1])

    if new_switch_path:
        new_full_path = new_switch_path + ["H2"]
        new_ports = encoder.path_to_ports(new_full_path)
        with lock:
            current_path = new_full_path
            current_ports = new_ports
            rerouting = False
            reroute_done = True
            reroute_end_time = time.time()
            path_flap_count += 1
        print(f"[SENDER] Rerouted -> {new_full_path} ports={new_ports}")
    else:
        with lock:
            rerouting = False


def print_final_stats():
    ack_stats = ack_listener.get_stats()
    runtime = time.time() - program_start
    send_summary = summarize(stats["send_times"])
    gen_wait_summary = summarize(stats["general_queue_wait_times"])
    reroute_wait_summary = summarize(stats["reroute_wait_times"])
    send_jitter = jitter(stats["send_times"])

    loss_rate = 100.0 * stats["dropped_total"] / stats["built_total"] if stats["built_total"] else 0.0
    throughput_pps = stats["sent_total"] / runtime if runtime > 0 else 0.0

    probe_total = ack_stats["acks_received"] + ack_stats["acks_missed"]
    probe_loss_rate = 100.0 * ack_stats["acks_missed"] / probe_total if probe_total else 0.0

    reroute_time = None
    if reroute_start_time is not None and reroute_end_time is not None:
        reroute_time = reroute_end_time - reroute_start_time

    rto = None
    if ack_stats["failure_detect_time"] is not None and first_backup_send_time is not None:
        rto = first_backup_send_time - ack_stats["failure_detect_time"]

    print("\n" + "=" * 72)
    print("[FINAL STATS — PPT EXACT PORT MAPPING]")
    print(f"runtime_s={runtime:.3f}")
    print(f"built_total={stats['built_total']} sent_total={stats['sent_total']} dropped_total={stats['dropped_total']}")
    print(f"packet_loss_rate_pct={loss_rate:.3f}")
    print(f"throughput_pps={throughput_pps:.2f}")
    print(f"primary_sent={stats['primary_sent']} backup_sent={stats['backup_sent']}")
    print(f"path_flap_count={path_flap_count}")
    print(f"probe_acks_ok={ack_stats['acks_received']} probe_acks_missed={ack_stats['acks_missed']}")
    print(f"probe_loss_rate_pct={probe_loss_rate:.3f}")
    print(f"failures_detected={ack_stats['failures_detected']}")
    print(f"acks_before_failure={ack_stats['acks_before_failure']}")
    print(f"send_time: avg={send_summary['avg']:.6f} p50={send_summary['p50']:.6f} p95={send_summary['p95']:.6f} p99={send_summary['p99']:.6f} max={send_summary['max']:.6f}")
    print(f"send_time_jitter_s={send_jitter:.6f}")
    print(f"general_queue_wait: avg={gen_wait_summary['avg']:.6f} p95={gen_wait_summary['p95']:.6f} max={gen_wait_summary['max']:.6f}")
    print(f"reroute_affected_packets={stats['packets_affected_by_reroute']}")
    print(f"reroute_wait: avg={reroute_wait_summary['avg']:.6f} p95={reroute_wait_summary['p95']:.6f} max={reroute_wait_summary['max']:.6f}")
    print(f"reroute_time_s={reroute_time:.6f}" if reroute_time is not None else "reroute_time_s=None")
    print(f"recovery_time_objective_s={rto:.6f}" if rto is not None else "recovery_time_objective_s=None")
    print("=" * 72)

    extra = {
        "packet_loss_rate_pct": loss_rate,
        "throughput_pps": throughput_pps,
        "probe_loss_rate_pct": probe_loss_rate,
        "path_flap_count": path_flap_count,
        "send_time_jitter_s": send_jitter,
        "send_p50": send_summary["p50"],
        "send_p95": send_summary["p95"],
        "send_p99": send_summary["p99"],
        "reroute_time_s": reroute_time if reroute_time is not None else "",
        "recovery_time_objective_s": rto if rto is not None else "",
    }
    export_run_csv("run_summary.csv", stats, ack_stats, runtime, extra=extra)
    export_timeseries_csv("run_timeseries.csv", stats["send_times"], stats["general_queue_wait_times"], stats["reroute_wait_times"], stats["queue_sizes_during_reroute"])


print("=" * 60)
print("TOPOLOGY READY")
print(f"Primary path: {'-'.join(PRIMARY_PATH)} ports {current_ports}")
print(f"Backup path : {'-'.join(BACKUP_PATH)} ports {encoder.path_to_ports(BACKUP_PATH)}")
print(f"Manual failure command: link {FAILED_LINK[0].lower()} {FAILED_LINK[1].lower()} down")
print("=" * 60)

ack_listener = AckListener(args.dst_ip, on_failure, ack_timeout=args.probe_timeout, max_missed=args.max_missed)
ack_listener.start()

threading.Thread(target=producer_loop, daemon=True).start()
threading.Thread(target=sender_loop, daemon=True).start()
threading.Thread(target=probe_loop, daemon=True).start()

while not sender_done:
    time.sleep(1)

print_final_stats()
