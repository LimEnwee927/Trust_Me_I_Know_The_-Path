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
from status_publisher import publish as publish_status


parser = argparse.ArgumentParser()
parser.add_argument("--src-ip", default="10.0.0.1")
parser.add_argument("--dst-ip", default="10.0.0.2")
parser.add_argument("--iface", default="h1-eth0")
parser.add_argument("--data-rate", type=float, default=0.1)
parser.add_argument("--probe-rate", type=float, default=0.2)
parser.add_argument("--probe-timeout", type=float, default=0.2)
parser.add_argument("--max-missed", type=int, default=3)
parser.add_argument("--max-packets", type=int, default=1000)
args = parser.parse_args()

conf.verb = 0

# ---------------------------------------------------------------------------
# DESTINATION TABLE — add new hosts here later without touching any logic
# ---------------------------------------------------------------------------
DEST_CONFIG = {
    "10.0.0.2": {
        "primary_path": ["S1", "S5", "S4", "H2"],
        "backup_path": ["S1", "S2", "S3", "S4", "H2"],
        "failed_link": ("S5", "S4"),
        "ack_port": 9999,
        "data_port": 5000,
        "data_sport": 5001,
        "probe_port": 6000,
        "probe_sport": 6001,
    },
    # Example for future extension — just uncomment and fill in when h3 exists:
    # "10.0.0.3": {
    #     "primary_path": ["S1", "S5", "S6"],
    #     "backup_path": ["S1", "S2", "S3", "S6"],
    #     "failed_link": ("S5", "S6"),
    #     "ack_port": 9998,
    #     "data_port": 5010,
    #     "data_sport": 5011,
    #     "probe_port": 6010,
    #     "probe_sport": 6011,
    # },
}

if args.dst_ip not in DEST_CONFIG:
    raise SystemExit(f"[SENDER] No route configuration found for destination {args.dst_ip}")

dest_cfg = DEST_CONFIG[args.dst_ip]

topo = Topology()
encoder = PathEncoder(topo)
rerouter = Rerouter(topo, source="S1", destination=dest_cfg["primary_path"][-1])

# ---------------------------------------------------------------------------
# Per-destination flow state — keyed by dst_ip so multiple flows can coexist
# ---------------------------------------------------------------------------
flow = {
    "dst_ip": args.dst_ip,
    "current_path": dest_cfg["primary_path"][:],
    "current_ports": encoder.path_to_ports(dest_cfg["primary_path"]),
    "rerouting": False,
    "reroute_done": False,
    "reroute_start_time": None,
    "reroute_end_time": None,
    "first_backup_send_time": None,
    "path_flap_count": 0,
}

data_queue = queue.Queue(maxsize=5000)
lock = threading.Lock()

seq = 0
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


def avg(values):
    return sum(values) / len(values) if values else 0.0


def build_data_packet(seq_num, path, ports):
    payload = f"type=data|seq={seq_num}|dst={flow['dst_ip']}|path={'-'.join(path)}".encode()
    return encoder.encode(
        payload,
        ports,
        flow["dst_ip"],
        args.src_ip,
        dport=dest_cfg["data_port"],
        sport=dest_cfg["data_sport"]
    )


def build_probe_packet(probe_seq, path, ports):
    payload = f"type=probe|probe={probe_seq}|dst={flow['dst_ip']}|path={'-'.join(path)}".encode()
    return encoder.encode(
        payload,
        ports,
        flow["dst_ip"],
        args.src_ip,
        dport=dest_cfg["probe_port"],
        sport=dest_cfg["probe_sport"]
    )


def probe_loop():
    probe_seq = 0
    while not sender_done:
        with lock:
            path = flow["current_path"][:]
            ports = flow["current_ports"][:]

        pkt = build_probe_packet(probe_seq, path, ports)
        sendp(pkt, iface=args.iface, verbose=0)
        probe_seq += 1
        time.sleep(args.probe_rate)


def status_loop():
    while not sender_done:
        with lock:
            publish_status(flow, stats, dest_cfg)
        time.sleep(0.3)
    with lock:
        publish_status(flow, stats, dest_cfg)


def producer_loop():
    global seq, producer_done

    while seq < args.max_packets:
        item = {
            "seq": seq,
            "enqueue_time": time.time(),
            "reroute_block_start": None,
        }

        try:
            data_queue.put(item, timeout=1)
            stats["built_total"] += 1
            seq += 1
        except queue.Full:
            stats["dropped_total"] += 1
            print("[SENDER] Queue full — packet dropped")

        time.sleep(args.data_rate)

    producer_done = True
    print(f"[SENDER] Producer finished after generating {args.max_packets} packets")


def sender_loop():
    global sender_done

    while True:
        if producer_done and data_queue.empty():
            sender_done = True
            print("[SENDER] Queue drained, sender finished")
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
                local_rerouting = flow["rerouting"]

            if not local_rerouting:
                break

            if not reroute_marked:
                item["reroute_block_start"] = time.time()
                reroute_marked = True
                stats["packets_affected_by_reroute"] += 1

            stats["queue_sizes_during_reroute"].append(data_queue.qsize())
            time.sleep(0.001)

        if item["reroute_block_start"] is not None:
            reroute_wait = time.time() - item["reroute_block_start"]
            stats["reroute_wait_times"].append(reroute_wait)

        with lock:
            send_path = flow["current_path"][:]
            send_ports = flow["current_ports"][:]

        pkt = build_data_packet(item["seq"], send_path, send_ports)

        t0 = time.perf_counter()
        sendp(pkt, iface=args.iface, verbose=0)
        t1 = time.perf_counter()

        send_duration = t1 - t0
        stats["send_times"].append(send_duration)
        stats["sent_total"] += 1

        if send_path == dest_cfg["primary_path"]:
            stats["primary_sent"] += 1
        elif send_path == dest_cfg["backup_path"]:
            stats["backup_sent"] += 1
            if flow["first_backup_send_time"] is None:
                with lock:
                    if flow["first_backup_send_time"] is None:
                        flow["first_backup_send_time"] = time.time()

        print(
            f"[SENDER] dst={flow['dst_ip']} sent_seq={item['seq']} "
            f"path={'-'.join(send_ports)} "
            f"general_wait={general_wait:.6f}s"
        )


def on_failure():
    with lock:
        if flow["rerouting"] or flow["reroute_done"]:
            return
        flow["rerouting"] = True
        flow["reroute_start_time"] = time.time()

    failed_link = dest_cfg["failed_link"]
    print(f"[SENDER] Failure assumed on link {failed_link[0]}-{failed_link[1]} for dst={flow['dst_ip']}")

    new_path = rerouter.handle_failure(failed_link[0], failed_link[1])

    if new_path:
        new_ports = encoder.path_to_ports(new_path)

        with lock:
            flow["current_path"] = new_path
            flow["current_ports"] = new_ports
            flow["rerouting"] = False
            flow["reroute_done"] = True
            flow["reroute_end_time"] = time.time()
            flow["path_flap_count"] += 1

        print(f"[SENDER] Rerouted -> {new_path} ports={new_ports}")
        print(f"[SENDER] Reroute time = {flow['reroute_end_time'] - flow['reroute_start_time']:.6f}s")
    else:
        with lock:
            flow["rerouting"] = False
        print("[SENDER] No backup path available")


def print_final_stats():
    ack_stats = ack_listener.get_stats()
    runtime = time.time() - program_start

    send_summary = summarize(stats["send_times"])
    gen_wait_summary = summarize(stats["general_queue_wait_times"])
    reroute_wait_summary = summarize(stats["reroute_wait_times"])
    send_jitter = jitter(stats["send_times"])

    loss_rate = 0.0
    if stats["built_total"] > 0:
        loss_rate = 100.0 * stats["dropped_total"] / stats["built_total"]

    throughput_pps = stats["sent_total"] / runtime if runtime > 0 else 0.0

    probe_loss_rate = 0.0
    total_probe_attempts = ack_stats["acks_received"] + ack_stats["acks_missed"]
    if total_probe_attempts > 0:
        probe_loss_rate = 100.0 * ack_stats["acks_missed"] / total_probe_attempts

    reroute_time = None
    if flow["reroute_start_time"] is not None and flow["reroute_end_time"] is not None:
        reroute_time = flow["reroute_end_time"] - flow["reroute_start_time"]

    rto = None
    if ack_stats["failure_detect_time"] is not None and flow["first_backup_send_time"] is not None:
        rto = flow["first_backup_send_time"] - ack_stats["failure_detect_time"]

    print("\n" + "=" * 72)
    print(f"[FINAL STATS — dst={flow['dst_ip']}]")
    print(f"runtime_s={runtime:.3f}")
    print(f"built_total={stats['built_total']} sent_total={stats['sent_total']} dropped_total={stats['dropped_total']}")
    print(f"packet_loss_rate_pct={loss_rate:.3f}")
    print(f"throughput_pps={throughput_pps:.2f}")
    print(f"primary_sent={stats['primary_sent']} backup_sent={stats['backup_sent']}")
    print(f"path_flap_count={flow['path_flap_count']}")
    print(f"probe_acks_ok={ack_stats['acks_received']} probe_acks_missed={ack_stats['acks_missed']}")
    print(f"probe_loss_rate_pct={probe_loss_rate:.3f}")
    print(f"failures_detected={ack_stats['failures_detected']}")
    print(f"acks_before_failure={ack_stats['acks_before_failure']}")
    print(
        f"send_time: avg={send_summary['avg']:.6f} p50={send_summary['p50']:.6f} "
        f"p95={send_summary['p95']:.6f} p99={send_summary['p99']:.6f} "
        f"max={send_summary['max']:.6f} stdev={send_summary['stdev']:.6f}"
    )
    print(f"send_time_jitter_s={send_jitter:.6f}")
    print(
        f"general_queue_wait: avg={gen_wait_summary['avg']:.6f} "
        f"p95={gen_wait_summary['p95']:.6f} max={gen_wait_summary['max']:.6f}"
    )
    print(f"reroute_affected_packets={stats['packets_affected_by_reroute']}")
    print(
        f"reroute_wait: avg={reroute_wait_summary['avg']:.6f} "
        f"p95={reroute_wait_summary['p95']:.6f} max={reroute_wait_summary['max']:.6f}"
    )
    print(f"reroute_time_s={reroute_time:.6f}" if reroute_time is not None else "reroute_time_s=None")
    print(f"recovery_time_objective_s={rto:.6f}" if rto is not None else "recovery_time_objective_s=None")
    print("=" * 72)

    extra = {
        "dst_ip": flow["dst_ip"],
        "packet_loss_rate_pct": loss_rate,
        "throughput_pps": throughput_pps,
        "probe_loss_rate_pct": probe_loss_rate,
        "path_flap_count": flow["path_flap_count"],
        "send_time_jitter_s": send_jitter,
        "send_p50": send_summary["p50"],
        "send_p95": send_summary["p95"],
        "send_p99": send_summary["p99"],
        "reroute_time_s": reroute_time if reroute_time is not None else "",
        "recovery_time_objective_s": rto if rto is not None else "",
    }
    export_run_csv(f"run_summary_{flow['dst_ip'].replace('.', '_')}.csv", stats, ack_stats, runtime, extra=extra)
    export_timeseries_csv(
        f"run_timeseries_{flow['dst_ip'].replace('.', '_')}.csv",
        stats["send_times"],
        stats["general_queue_wait_times"],
        stats["reroute_wait_times"],
        stats["queue_sizes_during_reroute"],
    )
    print("[SENDER] Exported per-destination CSV files")


print("=" * 72)
print(f"[SENDER] src={args.src_ip} dst={flow['dst_ip']}")
print(f"[SENDER] iface={args.iface}")
print(f"[SENDER] Primary path = {dest_cfg['primary_path']}")
print(f"[SENDER] Backup path  = {dest_cfg['backup_path']}")
print(f"[SENDER] Initial ports = {flow['current_ports']}")
print(f"[SENDER] Data rate = {1 / args.data_rate:.1f} pkt/s")
print(f"[SENDER] Probe rate = {1 / args.probe_rate:.1f} probe/s")
print(f"[SENDER] Max packets = {args.max_packets}")
print("[SENDER] Queued packets are re-encoded at send time")
print(f"[SENDER] Manual failure trigger: Mininet CLI -> link {dest_cfg['failed_link'][0]} {dest_cfg['failed_link'][1]} down")
print("=" * 72)

ack_listener = AckListener(
    dest_cfg["ack_port"],
    on_failure,
    ack_timeout=args.probe_timeout,
    max_missed=args.max_missed
)
ack_listener.start()

producer_thread = threading.Thread(target=producer_loop, daemon=True)
sender_thread = threading.Thread(target=sender_loop, daemon=True)
probe_thread = threading.Thread(target=probe_loop, daemon=True)
status_thread = threading.Thread(target=status_loop, daemon=True)

producer_thread.start()
sender_thread.start()
probe_thread.start()
status_thread.start()

while not sender_done:
    time.sleep(1)

print_final_stats()