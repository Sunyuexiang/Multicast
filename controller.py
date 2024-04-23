import os
import sys
import time
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import tcp
from ryu.lib.packet import ether_types
from ryu.lib.packet import arp
from ryu.lib.packet import in_proto
from ryu.lib.packet import ipv4
from ryu.lib.packet import icmp
from ryu.lib.packet import tcp
from ryu.lib.packet import udp
from ryu.lib import hub
import json
import group_table


rule_file =  "file" + ".json"

def load_config(filename=rule_file):
    with open(filename) as f:
        return json.load(f)




json_file =  "netconf" + ".json"

config = load_config()


class Controller13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(Controller13, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.info = []
        self.monitor_thread = hub.spawn(self._monitor)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]

        if buffer_id:
          mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                             priority=priority, match=match,
                             instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                             match=match, instructions=inst)
        datapath.send_msg(mod)

    def _monitor(self):
        time.sleep(1)
        group_table.drop()
        while True:
            rule = load_config()
            for item in rule.keys():
                if item not in self.info:
                    print ("add group table:", item)
                    self.info.append(item)
                    group_table.access(item)
                    time.sleep(0.1)
                    group_table.add_group(item)
                    time.sleep(0.1)
                    group_table.add_flow(item)
            time.sleep(3)


    #mac learning
    def mac_learning(self, datapath, src, in_port):
        self.mac_to_port.setdefault((datapath,datapath.id), {})
        if src in self.mac_to_port[(datapath,datapath.id)]:
            if in_port != self.mac_to_port[(datapath,datapath.id)][src]:
                return False
        else:
            self.mac_to_port[(datapath,datapath.id)][src] = in_port
            return True

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            match = parser.OFPMatch(eth_type=eth.ethertype)
            actions = []
            self.add_flow(datapath, 10, match, actions)
            return

        if eth.ethertype == ether_types.ETH_TYPE_IPV6:
            match = parser.OFPMatch(eth_type=eth.ethertype)
            actions = []
            self.add_flow(datapath, 10, match, actions)
            return

        dst = eth.dst
        src = eth.src
        dpid = datapath.id

        self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)
        self.mac_learning(datapath, src, in_port)

        if dst in self.mac_to_port[(datapath,datapath.id)]:
            out_port = self.mac_to_port[(datapath,datapath.id)][dst]
        else:
            if self.mac_learning(datapath, src, in_port) is False:
                out_port = ofproto.OFPPC_NO_RECV
            else:
                out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]
        if eth.ethertype == ether_types.ETH_TYPE_IP:
            ip = pkt.get_protocol(ipv4.ipv4)

        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self.add_flow(datapath, 10, match, actions, msg.buffer_id)
                return
            else:
                self.add_flow(datapath, 10, match, actions)

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)


 