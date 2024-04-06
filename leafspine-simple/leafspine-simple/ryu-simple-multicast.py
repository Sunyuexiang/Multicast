from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_5 # ofproto_v1_4, 

#from ryu.lib import igmplib
from ryu.lib.dpid import dpid_to_str
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ipv4
from ryu.lib.packet import igmp
from ipaddress import IPv4Address

from ryu.controller import dpset



# ryu run --observe-links ryu/app/gui_topology/gui_topology.py


def load_netconf(filename='netconf.txt'):
    with open(filename, 'r') as f:
        lines = f.readlines()
    return eval(lines[0])


class APP(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_5.OFP_VERSION]
    _CONTEXTS = {
        'dpset': dpset.DPSet,
    }

    def __init__(self, *args, **kwargs):
        super(APP, self).__init__(*args, **kwargs)
        self.igmp_handler = IGMP_Handler(self)
        self.dpset = kwargs['dpset']
        self.netconf = load_netconf()

        netconf = self.netconf
        self.dpid_to_switchname = netconf['dpid_to_switchname']
        self.host_ips = netconf['host_ips']
        self.topo = netconf['topo']
        self.switchname_to_dpid = {}
        for dpid, switch_name in self.dpid_to_switchname.items():
            self.switchname_to_dpid[switch_name] = dpid    

    def install_simple_multicast_tree(self, datapath):        
        # install H0m0m0 -> H0m0m1, H0m0m2 at switch T0m0
        #dpid = self.switchname_to_dpid['T0m0']
        #datapath = self.dpset.get(dpid)

        """
        sudo ovs-ofctl add-group T0m0 -O OpenFlow15 'group_id=1,type=all,bucket=output:3,bucket=output:4,bucket=output:5'
        sudo ovs-ofctl add-flow T0m0 -O OpenFlow15 'table=0,priority=10,ip,nw_src=10.0.0.100,nw_dst=224.1.10.100,actions=group:1'
        """

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        multicast_addr = '224.1.10.100'
        root_ip = self.host_ips['H0m0m0']

        match = parser.OFPMatch(
            eth_type=0x0800, #ip_proto=4,
            ipv4_dst=multicast_addr, # (multicast_addr, '255.255.255.255'), 
            ipv4_src=root_ip,
        )
        
        #  group_id=1,type=all,bucket=bucket_id:0,actions=output:"T0m0-eth3",bucket=bucket_id:1,actions=output:"T0m0-eth4",bucket=bucket_id:2,actions=output:"T0m0-eth5"

        group_id = 2
        buckets = []
        bucket_id = 0
        for i in range(2):
            port = self.topo['T0m0']['H0m0m{0}'.format(i + 1)]
            actions = [parser.OFPActionOutput(port), ]
            buckets.append(parser.OFPBucket(bucket_id=bucket_id, actions=actions))
            bucket_id += 1

        req = parser.OFPGroupMod(datapath, ofproto.OFPGC_ADD, ofproto.OFPGT_ALL, group_id=group_id, buckets=buckets)        
        #print('req', req)
        datapath.send_msg(req)

        actions = [parser.OFPActionGroup(group_id=group_id)]
        print(match)
        print(actions)
        #  out_group=group_id,
        self.add_flow(datapath, 10, match, actions, out_group=group_id, command=ofproto.OFPFC_ADD)
        
        
    @set_ev_cls(dpset.EventDP, dpset.DPSET_EV_DISPATCHER)
    def switch_state_change(self, ev):
        if ev.enter:
            datapath = ev.dp
            #print('ports at dp', datapath.id, datapath.ports)

            #datapath = ev.msg.datapath
            #print('# datapath', datapath.id)
            #print(self.dpset.get_all())

            if datapath.id == self.switchname_to_dpid['T0m0']:
                self.install_simple_multicast_tree(datapath)

            ofproto = datapath.ofproto
            parser = datapath.ofproto_parser

            # install the table-miss flow entry.
            match = parser.OFPMatch()
            actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                            ofproto.OFPCML_NO_BUFFER)]
            self.add_flow(datapath, 0, match, actions)

    """
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        print('# datapath', datapath.id)
        #print(self.dpset.get_all())

        if datapath.id == self.switchname_to_dpid['T0m0']:
            self.install_simple_multicast_tree(datapath)

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # install the table-miss flow entry.
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)
    """
    
    def add_flow(self, datapath, priority, match, actions, **params):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # construct flow_mod message and send it.
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst, **params)
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
        #print('get pkt', pkt)
        


class IGMP_Handler(object):
    def __init__(self, controller):
        self.controller = controller

    def process_igmp(self, ipv4_pkt, igmp_pkt):
        print('# msgtype', igmp_pkt.msgtype)
        print('#xxx src, dst', ipv4_pkt.src, ipv4_pkt.dst)

    def process_multicast_pktin(self, ipv4_pkt):
        print("# src, dst", ipv4_pkt.src, ipv4_pkt.dst)
