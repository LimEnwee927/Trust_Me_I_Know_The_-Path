from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI

import link_control_server


def build_network():
    net = Mininet(controller=RemoteController, switch=OVSSwitch, link=TCLink)

    print("*** Adding controller")
    net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)

    print("*** Adding hosts")
    h1 = net.addHost('h1', ip='10.0.0.1/24')
    h2 = net.addHost('h2', ip='10.0.0.2/24')

    print("*** Adding switches")
    s1 = net.addSwitch('s1', protocols='OpenFlow13')
    s2 = net.addSwitch('s2', protocols='OpenFlow13')
    s3 = net.addSwitch('s3', protocols='OpenFlow13')
    s4 = net.addSwitch('s4', protocols='OpenFlow13')
    s5 = net.addSwitch('s5', protocols='OpenFlow13')

    print("*** Adding links with PPT-exact port mapping")

    net.addLink(h1, s1, port1=1, port2=1)
    net.addLink(s4, h2, port1=1, port2=1)

    net.addLink(s1, s2, port1=2, port2=1)
    net.addLink(s2, s3, port1=2, port2=1)
    net.addLink(s3, s4, port1=2, port2=2)

    net.addLink(s1, s5, port1=3, port2=1)
    net.addLink(s5, s4, port1=2, port2=3)

    print("*** Starting network")
    net.start()

    print("*** Hosts config")
    h1.cmd('ifconfig h1-eth1 10.0.0.1/24 up')
    h2.cmd('ifconfig h2-eth1 10.0.0.2/24 up')

    print("=" * 60)
    print("TOPOLOGY READY")
    print("Primary path: S1-S5-S4-H2 ports [3,2,1]")
    print("Backup path : S1-S2-S3-S4-H2 ports [2,2,2,1]")
    print("Manual failure command: link s5 s4 down")
    print("=" * 60)

    link_control_server.start(net)

    CLI(net)
    net.stop()


if __name__ == '__main__':
    build_network()
