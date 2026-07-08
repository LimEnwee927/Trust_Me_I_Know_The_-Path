import socket

LISTEN_PORT = 5000
ACK_PORT = 9999
HOST_A_IP = "10.0.0.1"
ACK_EVERY_N = 2

received = 0
paths_seen = set()
seq_seen = set()
primary_received = 0
backup_received = 0

PRIMARY_PATH = "S1-S5-S4"
BACKUP_PATH = "S1-S2-S3-S4"

sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_recv.bind(("0.0.0.0", LISTEN_PORT))

sock_ack = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

print(f"[HOST_B] Listening on port {LISTEN_PORT}")
print(f"[HOST_B] ACKing every {ACK_EVERY_N} packets to {HOST_A_IP}:{ACK_PORT}")

try:
    while True:
        data, addr = sock_recv.recvfrom(4096)
        src_ip = addr[0]

        if src_ip != HOST_A_IP:
            continue

        payload = data.decode(errors="ignore").strip()

        pkt_seq = None
        pkt_path = None

        for part in payload.split("|"):
            if part.startswith("seq="):
                try:
                    pkt_seq = int(part.split("=", 1)[1])
                except ValueError:
                    pkt_seq = None
            elif part.startswith("path="):
                pkt_path = part.split("=", 1)[1]

        if pkt_seq is not None:
            if pkt_seq in seq_seen:
                continue
            seq_seen.add(pkt_seq)

        received += 1

        if pkt_path:
            paths_seen.add(pkt_path)
            if pkt_path == PRIMARY_PATH:
                primary_received += 1
            elif pkt_path == BACKUP_PATH:
                backup_received += 1

        if received % 20 == 0:
            print(
                f"[HOST_B] pkt={received} "
                f"seq={pkt_seq} "
                f"path={pkt_path} "
                f"primary_received={primary_received} "
                f"backup_received={backup_received}"
            )

        if received % ACK_EVERY_N == 0:
            sock_ack.sendto(
                f"ACK:{received}".encode(),
                (HOST_A_IP, ACK_PORT)
            )

except KeyboardInterrupt:
    print("\n" + "=" * 60)
    print("[HOST_B FINAL STATS]")
    print(f"received_data={received}")
    print(f"unique_seq_received={len(seq_seen)}")
    print(f"primary_received={primary_received}")
    print(f"backup_received={backup_received}")
    print(f"paths_seen={paths_seen}")
    print("=" * 60)
