from scapy.layers.l2 import Ether, Dot1Q
from scapy.layers.inet import IP, ICMP, UDP
from scapy.all import sendp, sniff, Raw, Ether
import time
import socket
import json
import threading

# host ip
host_ip = "10.0.0.1"

# default topo path list
topo = {
    "10.0.0.1": {
        "10.0.0.2": [3, 2, 1]
    },
    "10.0.0.2": {
        "10.0.0.1": [3, 1, 1]
    }
}


def control_plane_listener():
    global topo
    print("Start listening...")
    
    def process_packet(pkt):
        global topo
        # get pkt with raw payload from port 9999
        if pkt.haslayer(Raw) and pkt.haslayer(UDP) and pkt[UDP].dport == 9999:
            try:
                # get payload information
                raw_data = pkt[Raw].load.decode('utf-8').strip()
                new_topo = json.loads(raw_data)
                
                print(f"\nReceive: {new_topo}")
                topo = new_topo
            except Exception as e:
                pass

    # start monitoring port 9999
    sniff(iface="h1-eth1", filter="udp port 9999", prn=process_packet, store=0)


def start_continuous_ping(dst_ip):
    global topo
    print("start ping ", dst_ip)
    seq_num = 1

    while True:
        # Get port path from the whole topo dict
        port_path = topo.get(host_ip, {}).get(dst_ip, [])

        # Construct ethertype header. 
        # Mac addrs are not important, we can randomly choose two
        pkt = Ether(src="11:11:11:11:11:11", dst="22:22:22:22:22:22")
        # Actual mac addr:
        # "h1": {"ip": "10.0.0.1/24", "mac": "08:00:00:00:00:01"},
        # "h2": {"ip": "10.0.0.2/24", "mac": "08:00:00:00:00:02"}

        # nest 802.1Q headers with vlan tag
        for port in port_path:
            pkt = pkt / Dot1Q(vlan=port)

        # add IPv4 header and icmp payload
        pkt = pkt / IP(src=host_ip, dst=dst_ip) / ICMP(seq=seq_num)

        # # Print header structure
        # print("--- source routing header structure ---")
        # pkt.show()
        
        try:
            # Send pkt
            sendp(pkt, iface="h1-eth1", verbose=True)
            print(f"\nSource routing pkt with path: {port_path} sent, seq={seq_num}")
            seq_num += 1
        except Exception as e:
            print(f"\nPing error: {e}")
            
        # ping frequency
        time.sleep(1)

# start main function
if __name__ == "__main__":

    t = threading.Thread(target=control_plane_listener, daemon=True)
    t.start()

    dst_ip = "10.0.0.2"
    start_continuous_ping(dst_ip)