import json
from time import sleep
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import OVSSwitch, Host, RemoteController


class ExerciseRunner:

    def __init__(self, topo_file):
        print('Reading topology file.')
        with open(topo_file, 'r') as f:
            topo = json.load(f)
        self.hosts = topo['hosts']
        self.switches = topo['switches']
        self.links = topo['links']

    def run_exercise(self):
        # Initialize mininet with the topology specified by the config
        self.create_network()
        self.net.start()
        sleep(1)

        self.do_net_cli()
        # stop right after the CLI is exited
        self.net.stop()

    def create_network(self):
        # TODO 2. Creating the topology
        print("Building mininet topology.")
        self.topo = ExerciseTopo(hosts=self.hosts, switches=self.switches, links=self.links)
        self.controller = RemoteController(name="controller", ip="127.0.0.1", port=6653)
        self.net = Mininet(topo=self.topo, link=TCLink, host=Host, switch=OVSSwitch, controller=self.controller)

    def program_hosts(self):
        for host_name, host_info in list(self.hosts.items()):
            h = self.net.get(host_name)
            if "commands" in host_info:
                for cmd in host_info["commands"]:
                    h.cmd(cmd)

    def do_net_cli(self):
        print("Starting mininet CLI")
        print('')
        print('======================================================================')
        print('Welcome to Mininet CLI!')
        print('======================================================================')
        print('You can interact with the network using the mininet CLI below.')
        print('')
        CLI(self.net)


class ExerciseTopo(Topo):

    def __init__(self, hosts, switches, links, **opts):
        Topo.__init__(self, **opts)
        host_links = []
        switch_links = []

        # assumes host always comes second for switch <--> host links
        for link in links:
            if link['node2'][0] == 'm' or link['node2'][0] == 'g':
                host_links.append(link)
            else:
                switch_links.append(link)

        for sw, params in switches.items():
            print(f"Adding switch: {sw} with id: {params['device_id']}")
            self.addSwitch(name=sw, dpid=params['device_id'], cls=OVSSwitch)

        for link in host_links:
            host_name, host_port = self.parse_name_port(link['node2'])
            sw_name, sw_port = self.parse_name_port(link['node1'])
            print(f"Adding link between host: {host_name} and switch: {sw_name}")
            host_ip = hosts[host_name]['ip']
            host_mac = hosts[host_name]['mac']
            self.addHost(host_name, ip=host_ip, mac=host_mac)
            self.addLink(host_name, sw_name, port1=host_port, port2=sw_port)

        for link in switch_links:
            sw1_name, sw1_port = self.parse_name_port(link['node1'])
            sw2_name, sw2_port = self.parse_name_port(link['node2'])
            print(f"Adding link between switch: {sw1_name} and switch: {sw2_name}")
            self.addLink(sw1_name, sw2_name, port1=sw1_port, port2=sw2_port)

    def parse_name_port(self, node):
        assert (len(node.split('-')) == 2)
        name, port = node.split('-')
        try:
            # ethX
            port = int(port[3:])
        except:
            raise Exception('Invalid switch node in topology file: {}'.format(node))
        return name, port


if __name__ == '__main__':
    exercise = ExerciseRunner('/home/student/t1/tutorial2/tutorial2/topo.json')
    exercise.run_exercise()
