from mininet.net import Mininet
from mininet.node import OVSKernelSwitch, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.link import TCLink
import json


def run():
    setLogLevel('info')

    net = Mininet(
        switch=OVSKernelSwitch,
        controller=RemoteController,
        link=TCLink
    )

    net.addController(
        'c0',
        controller=RemoteController,
        ip='127.0.0.1',
        port=6633
    )

    h1 = net.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
    h2 = net.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')

    s1 = net.addSwitch('s1', protocols='OpenFlow13')
    s2 = net.addSwitch('s2', protocols='OpenFlow13')
    s3 = net.addSwitch('s3', protocols='OpenFlow13')
    s4 = net.addSwitch('s4', protocols='OpenFlow13')
    s5 = net.addSwitch('s5', protocols='OpenFlow13')

    net.addLink(h1, s1)   # s1-eth1
    net.addLink(s4, h2)   # s4-eth1
    net.addLink(s1, s2)   # s1-eth3, s2-eth1  BACKUP
    net.addLink(s2, s3)   # s2-eth2, s3-eth1  BACKUP
    net.addLink(s3, s4)   # s3-eth2, s4-eth3  BACKUP    
    net.addLink(s1, s5)   # s1-eth2, s5-eth1  PRIMARY
    net.addLink(s5, s4)   # s5-eth2, s4-eth2  PRIMARY


    net.start()

    print("\n" + "=" * 60)
    print("TOPOLOGY READY")
    print("Primary path: S1-S5-S4 ports [2,2]")
    print("Backup path : S1-S2-S3-S4 ports [3,2,2]")
    print("Manual failure command: link s5 s4 down")
    print("=" * 60 + "\n")

    CLI(net)
    net.stop()


if __name__ == '__main__':
    run()
