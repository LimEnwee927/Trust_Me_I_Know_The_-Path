from scapy.all import Dot1Q, IP, UDP, Ether


class PathEncoder:
    def __init__(self, topology):
        self.topo = topology

    def path_to_ports(self, path):
        ports = []
        for i in range(len(path) - 1):
            ports.append(self.topo.get_port(path[i], path[i + 1]))
        print(f"[ENCODER] {path} -> ports {ports}")
        return ports

    def encode(self, payload_bytes, ports, dst_ip, src_ip, dport=5000, sport=5001):
        pkt = IP(src=src_ip, dst=dst_ip) / UDP(dport=dport, sport=sport) / payload_bytes
        for port in reversed(ports):
            pkt = Dot1Q(vlan=port) / pkt
        return Ether() / pkt
