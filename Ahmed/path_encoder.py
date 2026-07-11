from scapy.all import Dot1Q, IP, UDP, Ether, ICMP


class PathEncoder:
    def __init__(self, topology):
        self.topo = topology

    def path_to_ports(self, path):
        ports = []
        for i in range(len(path) - 1):
            ports.append(self.topo.get_port(path[i], path[i + 1]))
        print(f"[ENCODER] {path} -> ports {ports}")
        return ports

    def encode(self, payload_bytes, ports, dst_ip, src_ip, seq_num, dport=5000, sport=5001):
        # Construct ethertype header. 
        # Mac addrs are not important, we can randomly choose two
        pkt = Ether(src="11:11:11:11:11:11", dst="22:22:22:22:22:22")

        # nest 802.1Q headers with vlan tag
        for port in ports:
            pkt = pkt / Dot1Q(vlan=port)
        
        # add IPv4 header and icmp payload
        pkt = pkt / IP(src=src_ip, dst=dst_ip) / ICMP(seq=seq_num) / payload_bytes

        # # Print header structure
        # print("--- source routing header structure ---")
        # pkt.show()

        return pkt
