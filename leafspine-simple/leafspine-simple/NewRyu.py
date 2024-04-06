import json
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ipv4, igmp
from ryu.controller import dpset
from ipaddress import IPv4Address


def load_netconf(filename='netconf.json'):
    with open(filename) as f:
        return json.load(f)


class MulticastRyuApp(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'dpset': dpset.DPSet}

    def __init__(self, *args, **kwargs):
        super(MulticastRyuApp, self).__init__(*args, **kwargs)
        self.dpset = kwargs['dpset']
        self.netconf = load_netconf()

        self.dpid_to_switchname = self.netconf['dpid_to_switchname']
        self.host_ips = self.netconf['host_ips']
        self.topo = self.netconf['topo']
        self.multicast_groups = self.netconf['multicast_groups']
        self.switchname_to_dpid = {switch_name: dpid for dpid, switch_name in self.dpid_to_switchname.items()}

        # 新增字典，用于将字符串形式的 group_id 映射到整数 ID
        self.group_id_mapping = {}
        self.next_group_id = 1  # 用于分配新的整数 group_id

    def get_group_id(self, string_group_id):
        if string_group_id not in self.group_id_mapping:
            self.group_id_mapping[string_group_id] = self.next_group_id
            self.next_group_id += 1
        print("Assigned Group ID:", self.group_id_mapping[string_group_id])  # 打印分配的组 ID
        return self.group_id_mapping[string_group_id]

    # 在交换机状态变化时处理组播组和流表项的安装
    @set_ev_cls(dpset.EventDP, dpset.DPSET_EV_DISPATCHER)
    def switch_state_change(self, ev):
        datapath = ev.dp
        if ev.enter and str(datapath.id) in self.dpid_to_switchname:
            self.logger.info("Switch %s has entered", self.dpid_to_switchname[str(datapath.id)])
            for group_name, group_info in self.multicast_groups.items():
                self.install_multicast_group(datapath, group_name, group_info)

    # 安装组播组
    def install_multicast_group(self, datapath, group_name, group_info):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # 创建组播组的 buckets
        buckets = []
        for target in group_info['targets']:
            target_ip = self.host_ips[target]
            target_switch_name = self.find_switch_for_host(target)
            target_dpid = self.switchname_to_dpid[target_switch_name]
            if str(datapath.id) != target_dpid:
                continue  # 只在目标主机直接连接的交换机上安装组播组
            out_port = self.topo[target_switch_name][target]
            actions = [parser.OFPActionOutput(out_port)]
            buckets.append(parser.OFPBucket(actions=actions))

        group_id = self.get_group_id(group_name)
        group_mod = parser.OFPGroupMod(datapath, ofproto.OFPGC_ADD, ofproto.OFPGT_ALL, group_id, buckets)
        datapath.send_msg(group_mod)

        # 为源主机到组播地址的流量安装流表项
        source_ip = self.host_ips[group_info['source']]
        multicast_ip = group_info['multicast_address']
        match = parser.OFPMatch(eth_type=0x0800, ipv4_src=source_ip, ipv4_dst=multicast_ip)
        actions = [parser.OFPActionGroup(group_id)]
        self.add_flow(datapath, 50, match, actions)

    # 根据主机名找到其直接连接的交换机名
    def find_switch_for_host(self, host):
        for switch_name, connections in self.topo.items():
            if host in connections:
                return switch_name
        return None

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority, match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        ofp_parser = dp.ofproto_parser
        pkt = packet.Packet(msg.data)

        ipv4_pkt = pkt.get_protocol(ipv4.ipv4)
        igmp_pkt = pkt.get_protocol(igmp.igmp)
        if igmp_pkt is not None:
            return self.igmp_handler.process_igmp(ipv4_pkt, igmp_pkt)
        else:
            if ipv4_pkt and IPv4Address(ipv4_pkt.dst).is_multicast:
                return self.igmp_handler.process_multicast_pktin(ipv4_pkt)

        pass
        # print('get pkt', pkt)


class IGMP_Handler(object):
    def __init__(self, controller):
        self.controller = controller

    def process_igmp(self, ipv4_pkt, igmp_pkt):
        print('# msgtype', igmp_pkt.msgtype)
        print('#xxx src, dst', ipv4_pkt.src, ipv4_pkt.dst)

    def process_multicast_pktin(self, ipv4_pkt):
        print("# src, dst", ipv4_pkt.src, ipv4_pkt.dst)


# Entry point
def main():
    app_mgr = app_manager.AppManager.instance()
    app_mgr.instantiate(MulticastRyuApp)

    try:
        app_mgr.run_apps()
    finally:
        app_mgr.close()


if __name__ == '__main__':
    main()
