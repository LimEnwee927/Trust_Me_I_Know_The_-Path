import socket
from scapy.all import sniff, sendp, Raw
from scapy.layers.l2 import Ether, Dot1Q
from scapy.layers.inet import IP, ICMP, UDP
import signal
import sys
from topology import Topology
from path_encoder import PathEncoder


topo = Topology()
encoder = PathEncoder(topo)


# LISTEN_PORT = 5000
# PROBE_PORT = 6000
# ACK_PORT = 9999
HOST_A_IP = "10.0.0.1"
ACK_EVERY_N = 2

received = 0
probe_received = 0
paths_seen = set()
seq_seen = set()
primary_received = 0
backup_received = 0

iface_name = "h2-eth1" 
host_ip = "10.0.0.2"

PRIMARY_PATH = "S1-S5-S4-H2"
BACKUP_PATH = "S1-S2-S3-S4-H2"

# sock_data = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# sock_data.bind(("0.0.0.0", LISTEN_PORT))

# sock_probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# sock_probe.bind(("0.0.0.0", PROBE_PORT))

# sock_ack = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# print(f"[HOST_B] Listening data on port {LISTEN_PORT}")
# print(f"[HOST_B] Listening probe on port {PROBE_PORT}")
# print(f"[HOST_B] ACKing to {HOST_A_IP}:{ACK_PORT}")


def get_sender_name(ip):
    if ip == "10.0.0.1":
        return "H1"


# def handle_packet(data, addr, is_probe=False):
#     global received, probe_received, primary_received, backup_received

#     if addr[0] != HOST_A_IP:
#         return
#     print("recieve pkt!")
#     payload = data.decode(errors="ignore").strip()
#     pkt_seq = None
#     pkt_path = None

#     for part in payload.split("|"):
#         if part.startswith("seq="):
#             try:
#                 pkt_seq = int(part.split("=", 1)[1])
#             except ValueError:
#                 pkt_seq = None
#         elif part.startswith("path="):
#             pkt_path = part.split("=", 1)[1]

#     if not is_probe and pkt_seq is not None:
#         if pkt_seq in seq_seen:
#             return
#         seq_seen.add(pkt_seq)

#     if is_probe:
#         probe_received += 1
#         sock_ack.sendto(f"ACK:probe:{probe_received}".encode(), (HOST_A_IP, ACK_PORT))
#         return

#     received += 1

#     if pkt_path:
#         paths_seen.add(pkt_path)
#         if pkt_path == PRIMARY_PATH:
#             primary_received += 1
#         elif pkt_path == BACKUP_PATH:
#             backup_received += 1

#     if received % 20 == 0:
#         print(f"[HOST_B] pkt={received} seq={pkt_seq} path={pkt_path}")

#     if received % ACK_EVERY_N == 0:
#         sock_ack.sendto(f"ACK:data:{received}".encode(), (HOST_A_IP, ACK_PORT))


def handle_and_reply(pkt):
    global received, probe_received, primary_received, backup_received
    # Only process ICMP Echo Request (type=8)
    if pkt.haslayer(ICMP) and pkt[ICMP].type == 8:
        payload = pkt[Raw].load.decode('utf-8')
        print(f"Receive ICMP Pkt from IP: {pkt[IP].src}, \npayload: {payload}")
        sender_name = get_sender_name(pkt[IP].src)

        pkt_seq = pkt[ICMP].seq
        pkt_path = None
        is_probe = False

        for part in payload.split("|"):
            if part.startswith("path="):
                pkt_path = part.split("=", 1)[1]
            if part == "type=probe":
                is_probe = True

        # Reverse path: "S1-S5-S4-H2" -> ['S4', 'S5', 'S1', 'H1']
        current_path = pkt_path.split('-')[:-1][::-1] + [sender_name]

        print(f"current_path: {current_path}")
        # path array to ports array
        return_ports = encoder.path_to_ports(current_path)
        print(f"return_ports: {return_ports}")

        
        # reverse mac addr
        reply_pkt = Ether(src=pkt[Ether].dst, dst=pkt[Ether].src)
        
        # nest 802.1Q headers with vlan tag
        for vlan_port in return_ports:
            reply_pkt = reply_pkt / Dot1Q(vlan=vlan_port)
            
        # Add reversed IP header and ICMP Echo Reply (type=0)
        # Keep pkt ID and sequence same as request
        reply_pkt = (reply_pkt / 
                     IP(src=pkt[IP].dst, dst=pkt[IP].src) / 
                     ICMP(type=0, id=pkt[ICMP].id, seq=pkt_seq))
        
        # Send reply
        try:
            sendp(reply_pkt, iface=iface_name, verbose=False)
            print(f"ICMP reply with ports {return_ports} sent!")
        except Exception as e:
            print(f"Reply error: {e}")
        

        # print(pkt_path)
        if not is_probe and pkt_seq is not None:
            if not pkt_seq in seq_seen:
                seq_seen.add(pkt_seq)

        if is_probe:
            probe_received += 1
            # sock_ack.sendto(f"ACK:probe:{probe_received}".encode(), (HOST_A_IP, ACK_PORT))

        received += 1

        if pkt_path:
            paths_seen.add(pkt_path)
            if pkt_path == PRIMARY_PATH:
                primary_received += 1
            elif pkt_path == BACKUP_PATH:
                backup_received += 1


        if received % 20 == 0:
            print(f"[HOST_B] pkt={received} seq={pkt_seq} path={pkt_path}")


def print_final_stats():
    print("\n" + "=" * 60)
    print("[HOST_B FINAL STATS]")
    print(f"received={received}")
    print(f"received_probe={probe_received}")
    print(f"unique_seq_received={len(seq_seen)}")
    print(f"primary_received={primary_received}")
    print(f"backup_received={backup_received}")
    print(f"paths_seen={paths_seen}")
    print("=" * 60)
    
def hard_exit_handler(sig, frame):
    print_final_stats()
    sys.exit(0)

signal.signal(signal.SIGINT, hard_exit_handler)


print("h2 start monitoring ping request...")
# start monitoring icmp flow on h2-eth1
sniff(iface=iface_name, filter="icmp", prn=handle_and_reply, store=0)
    


