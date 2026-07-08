import networkx as nx


class Topology:
    def __init__(self):
        self.graph = nx.Graph()
        self._load()

    def _load(self):
        self.graph.add_edge("S1", "S5", port_S1=3, port_S5=1)
        self.graph.add_edge("S5", "S4", port_S5=2, port_S4=2)

        self.graph.add_edge("S1", "S2", port_S1=2, port_S2=1)
        self.graph.add_edge("S2", "S3", port_S2=2, port_S3=1)
        self.graph.add_edge("S3", "S4", port_S3=2, port_S4=3)

        self.graph.add_edge("H1", "S1", port_H1=1, port_S1=1)
        self.graph.add_edge("H2", "S4", port_H2=1, port_S4=1)

    def get_port(self, src, dst):
        return self.graph[src][dst][f"port_{src}"]

    def remove_link(self, a, b):
        if self.graph.has_edge(a, b):
            self.graph.remove_edge(a, b)
            print(f"[TOPOLOGY] Link {a}-{b} removed")
