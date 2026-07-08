import statistics
import csv


def percentile(data, p):
    if not data:
        return 0.0
    data = sorted(data)
    k = (len(data) - 1) * (p / 100)
    f, c = int(k), min(int(k) + 1, len(data) - 1)
    if f == c:
        return data[f]
    return data[f] + (data[c] - data[f]) * (k - f)


def jitter(values):
    if len(values) < 2:
        return 0.0
    diffs = [abs(values[i] - values[i - 1]) for i in range(1, len(values))]
    return statistics.mean(diffs)


def summarize(values):
    if not values:
        return {"avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0, "min": 0.0, "stdev": 0.0}
    return {
        "avg": statistics.mean(values),
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "p99": percentile(values, 99),
        "max": max(values),
        "min": min(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def export_run_csv(filename, stats, ack_stats, runtime, extra=None):
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        writer.writerow(["runtime_s", runtime])
        for k, v in stats.items():
            if isinstance(v, list):
                continue
            writer.writerow([k, v])
        for k, v in ack_stats.items():
            writer.writerow([f"ack_{k}", v])
        if extra:
            for k, v in extra.items():
                writer.writerow([k, v])


def export_timeseries_csv(filename, send_times, general_waits, reroute_waits, qsizes):
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["index", "send_time_s", "general_wait_s", "reroute_wait_s", "queue_size"])
        n = max(len(send_times), len(general_waits), len(reroute_waits), len(qsizes))
        for i in range(n):
            writer.writerow([
                i,
                send_times[i] if i < len(send_times) else "",
                general_waits[i] if i < len(general_waits) else "",
                reroute_waits[i] if i < len(reroute_waits) else "",
                qsizes[i] if i < len(qsizes) else "",
            ])
