import matplotlib.pyplot as plt
import csv

rows = list(csv.DictReader(open("run_timeseries.csv")))

send_times = [float(r["send_time_s"]) for r in rows if r["send_time_s"]]
plt.figure(figsize=(10, 4))
plt.plot(send_times)
plt.xlabel("Packet index")
plt.ylabel("Send time (s)")
plt.title("Per-packet send latency over the experiment")
plt.tight_layout()
plt.savefig("send_latency.png", dpi=150)
plt.close()

qsizes = [int(r["queue_size"]) for r in rows if r["queue_size"]]
plt.figure(figsize=(10, 4))
plt.plot(qsizes)
plt.xlabel("Sample index during reroute")
plt.ylabel("Queue size")
plt.title("Queue backlog growth during failover window")
plt.tight_layout()
plt.savefig("queue_backlog.png", dpi=150)
plt.close()

reroute_waits = [float(r["reroute_wait_s"]) for r in rows if r["reroute_wait_s"]]
plt.figure(figsize=(8, 4))
plt.hist(reroute_waits, bins=20)
plt.xlabel("Reroute wait time (s)")
plt.ylabel("Packet count")
plt.title("Distribution of packet delay caused by reroute")
plt.tight_layout()
plt.savefig("reroute_wait_hist.png", dpi=150)
plt.close()

print("Saved: send_latency.png, queue_backlog.png, reroute_wait_hist.png")
