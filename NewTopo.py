import json
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.link import TCLink
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI


class CustomSwitch(OVSSwitch):
    """Custom OVSSwitch class that uses OpenFlow 1.3."""

    def __init__(self, *args, **kwargs):
        kwargs['protocols'] = 'OpenFlow13'
        super(CustomSwitch, self).__init__(*args, **kwargs)


class JSONBasedTopo(Topo):
    def __init__(self, config, **kwargs):
        self.config = config
        super(JSONBasedTopo, self).__init__(**kwargs)

    def build(self):
        # 添加交换机和主机
        for dpid, switch_name in self.config['dpid_to_switchname'].items():
            self.addSwitch(switch_name, dpid=str(dpid))

        for host_name, ip in self.config['host_ips'].items():
            self.addHost(host_name, ip=ip)

        # 添加链接
        for node1, connections in self.config['topo'].items():
            for node2, port in connections.items():
                self.addLink(node1, node2)


def install_multicast_flow_entries(net, config):
    created_groups = {}  # 记录已创建的组播组

    for group_name, group_info in config['multicast_groups'].items():
        source_ip = config['host_ips'][group_info['source']]
        multicast_ip = group_info['multicast_address']
        group_id = int(group_name.replace("group", ""))

        # 构建组播组配置
        group_configs = {}
        for target in group_info['targets']:
            target_ip = config['host_ips'][target]
            for sw_name, connections in config['topo'].items():
                if target in connections:
                    port = connections[target]
                    if sw_name not in group_configs:
                        group_configs[sw_name] = []
                    group_configs[sw_name].append(f"bucket=output:{port}")

        # 创建组播组
        for sw_name, buckets in group_configs.items():
            # 检查组播组是否已创建
            if sw_name in created_groups and group_id in created_groups[sw_name]:
                continue  # 如果已存在，则跳过创建

            switch = net.get(sw_name)
            buckets_str = ','.join(buckets)
            cmd_add_group = f'ovs-ofctl add-group {sw_name} group_id={group_id},type=all,{buckets_str}'
            switch.cmd(cmd_add_group)
            print(f'Added multicast group {group_id} to {sw_name} with {buckets_str}')

            # 更新已创建的组播组记录
            if sw_name not in created_groups:
                created_groups[sw_name] = set()
            created_groups[sw_name].add(group_id)

            # 为组播流量创建流表项
            cmd_add_flow = f'ovs-ofctl add-flow {sw_name} priority=500,ip,nw_dst={multicast_ip},actions=group:{group_id}'
            switch.cmd(cmd_add_flow)
            print(f'Added multicast flow to {sw_name}: *,nw_dst={multicast_ip}, actions=group:{group_id}')

    # 添加ARP和ICMP处理规则
    for sw in net.switches:
        switch = net.get(sw.name)
        switch.cmd(f'ovs-ofctl add-flow {sw.name} priority=400,arp,actions=flood')
        switch.cmd(f'ovs-ofctl add-flow {sw.name} priority=400,icmp,actions=flood')


def configure_default_multicast_routes(net):
    for host in net.hosts:
        # 为每个主机添加默认多播路由
        cmd = "route add -net 224.0.0.0 netmask 240.0.0.0 dev %s-eth0" % host.name
        print(f"为 {host.name} 添加多播路由: {cmd}")  # 打印即将执行的命令
        host.cmd(cmd)


def load_config(filename='simple.json'):
    with open(filename) as f:
        return json.load(f)


def create_network(config):
    topo = JSONBasedTopo(config=config)
    net = Mininet(topo=topo, link=TCLink, controller=None, switch=CustomSwitch)
    net.addController('c0', controller=RemoteController, ip="127.0.0.1", port=6653)
    net.start()

    install_multicast_flow_entries(net, config)  # 安装多播流表项

    configure_default_multicast_routes(net)  # 配置默认多播路由

    CLI(net)
    net.stop()


if __name__ == '__main__':
    config = load_config()
    create_network(config)