from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSController
from mininet.node import CPULimitedHost, Host, Node
from mininet.node import OVSKernelSwitch, UserSwitch
from mininet.node import IVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink, Intf
from subprocess import call
import time
import json
import sys

json_file =  sys.argv[1] + ".json"

def load_config(filename=json_file):
    with open(filename) as f:
        return json.load(f)
    
config = load_config()

# print config["dpid_to_switchname"].items()


def myNetwork():

    net = Mininet( topo=None,
                   build=False,
                   ipBase='10.0.0.0/8')

    switch_dict = {}
    host_dict = {}

    info( '*** Adding controller\n' )
    c0=net.addController(name='c0',
                      controller=RemoteController,
                      ip='127.0.0.1',
                      protocol='tcp',
                      port=6653)

    info( '*** Add switches\n')
    for index, item in enumerate(config["dpid_to_switchname"].items()):
        switch_dict[item[0]] = net.addSwitch(item[1], cls=OVSKernelSwitch, dpid="000000000000000" + str(index + 1))

    info( '*** Add hosts\n')
    for item in config["host_ips"].items():
        host_dict[item[0]] = net.addHost(item[0], cls=Host, ip=item[1], defaultRoute=None)

    info( '*** Add links\n')
    temp = []
    for item in config["topo"].items():
        for dst in item[1].items():
            if '{}-{}'.format(item[0], dst[0]) not in temp:
                net.addLink(item[0], dst[0], port1=dst[1])
                temp.append('{}-{}'.format(item[0], dst))
                temp.append('{}-{}'.format(dst, item[0]))


    info( '*** Starting network\n')
    net.build()
    info( '*** Starting controllers\n')
    for controller in net.controllers:
        controller.start()

    info( '*** Starting switches\n')

    for item in config["dpid_to_switchname"].items():
        net.get(item[1]).start([c0])

    for item in config["host_ips"].items():
        net.get(item[0]).cmd("route add -net 224.0.0.0 netmask 224.0.0.0 {}-eth0".format(item[0]))
        # net.get(item[0]).cmd("ip route add default via 10.0.0.1")

    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    myNetwork()