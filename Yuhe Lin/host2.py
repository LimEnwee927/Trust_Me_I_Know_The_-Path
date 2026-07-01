import json
from scapy.all import sniff, sendp, Raw
from scapy.layers.l2 import Ether, Dot1Q
from scapy.layers.inet import IP, ICMP, UDP
import threading


iface_name = "h2-eth1" 
host_ip = "10.0.0.2"
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
    sniff(iface=iface_name, filter="udp port 9999", prn=process_packet, store=0)

def handle_and_reply(pkt):
    # Only process ICMP Echo Request (type=8)
    if pkt.haslayer(ICMP) and pkt[ICMP].type == 8:
        print(f"Receive ICMP Pkt from IP: {pkt[IP].src}")
        
        # Read return port path from topo dict
        return_path = topo.get(host_ip, {}).get(pkt[IP].src, [])
        
        # reverse mac addr
        reply_pkt = Ether(src=pkt[Ether].dst, dst=pkt[Ether].src)
        
        # nest 802.1Q headers with vlan tag
        for vlan_port in return_path:
            reply_pkt = reply_pkt / Dot1Q(vlan=vlan_port)
            
        # Add reversed IP header and ICMP Echo Reply (type=0)
        # Keep pkt ID and sequence same as request
        reply_pkt = (reply_pkt / 
                     IP(src=pkt[IP].dst, dst=pkt[IP].src) / 
                     ICMP(type=0, id=pkt[ICMP].id, seq=pkt[ICMP].seq))
        
        # Send reply
        try:
            sendp(reply_pkt, iface=iface_name, verbose=False)
            print(f"ICMP reply with path {return_path} sent!")
        except Exception as e:
            print(f"Reply error: {e}")

if __name__ == "__main__":
    print("h2 start monitoring topo dict from controller...")
    t = threading.Thread(target=control_plane_listener, daemon=True)
    t.start()

    print("h2 start monitoring ping request...")
    # start monitoring icmp flow on h2-eth1
    sniff(iface=iface_name, filter="icmp", prn=handle_and_reply, store=0)