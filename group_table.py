import json
import os

json_file =  "netconf" + ".json"

def load_config(filename=json_file):
    with open(filename) as f:
        return json.load(f)

config = load_config()


def get_switch_port(local):
    for item in config["topo"].items():
        if local in item[1].keys():
            return item[0], item[1][local]


def get_host_ip(local):
    return config["host_ips"][local]



def add_group(group):
    for item in config["multicast_groups"][group]["targets"]:
        s, p = get_switch_port(item)
        os.system("sudo ovs-ofctl -O OpenFlow13 add-group {} group_id={},type=all,bucket=output:{}".format(s, group[-1], p))
        print ("sudo ovs-ofctl -O OpenFlow13 add-group {} group_id={},type=all,bucket=output:{}".format(s, group[-1], p))


def add_flow(group):
    sip =  get_host_ip(config["multicast_groups"][group]["source"])
    for item in config["multicast_groups"][group]["targets"]:
        s, p = get_switch_port(item)
        os.system("sudo ovs-ofctl  -O OpenFlow13 add-flow {} ip,priority=65535,nw_src={},nw_dst=224.1.10.100,actions=group:{}".format(s, sip, group[-1]))
        print ("sudo ovs-ofctl  -O OpenFlow13 add-flow {} ip,priority=65535,nw_src={},nw_dst=224.1.10.100,actions=group:{}".format(s, sip, group[-1]))


def drop():
    for item in range(1,5):
        host =  config["multicast_groups"]["group" + str(item)]["source"]
        s, p = get_switch_port(host)
        os.system("sudo ovs-ofctl add-flow {} in_port={},actions=drop".format(s, p))

def access(group):
    host =  config["multicast_groups"][group]["source"]
    s, p = get_switch_port(host)
    os.system("sudo ovs-ofctl del-flows {} in_port={}".format(s, p))