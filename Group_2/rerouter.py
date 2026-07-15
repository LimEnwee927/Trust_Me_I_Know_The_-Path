import networkx as nx


class Rerouter:
    def __init__(self, topology, source="S1", destination="S4"):
        self.topo = topology
        self.source = source
        self.destination = destination

    def get_initial_path(self):
        return self._compute()

    def handle_failure(self, node_a, node_b):
        print(f"[REROUTER] Handling failure {node_a}-{node_b}")
        self.topo.remove_link(node_a, node_b)
        return self._compute()

    def _compute(self):
        try:
            path = nx.shortest_path(
                self.topo.graph,
                source=self.source,
                target=self.destination
            )
            print(f"[REROUTER] New path: {path}")
            return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            print("[REROUTER] No path available!")
            return None
