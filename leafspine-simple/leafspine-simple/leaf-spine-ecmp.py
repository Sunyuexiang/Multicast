from __future__ import print_function
# Copyright (C) 2016 Huang MaChi at Chongqing University
# of Posts and Telecommunications, China.
# Copyright (C) 2016 Li Cheng at Beijing University of Posts
# and Telecommunications. www.muzixing.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from mininet.net import Mininet
from mininet.node import Controller, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.link import Link, Intf, TCLink
from mininet.topo import Topo
from mininet.util import dumpNodeConnections

import logging
import os
import time


class LeafSpine(Topo):
	"""
		Class of Leaf Spine Topology.
	"""
	def __init__(self, 
			leaf_num, spine_num, rack_per_leaf, host_per_rack, 
			core_link_config, aggr_link_config, access_link_config, 
			of_version='OpenFlow15',
			controller_ip="127.0.0.1",
			controller_port=6653):

		self.of_version = of_version
		self.controller_ip = controller_ip
		self.controller_port = controller_port

		self.leaf_num = leaf_num
		self.spine_num = spine_num
		self.rack_per_leaf = rack_per_leaf
		self.host_per_rack = host_per_rack

		self.leaf_names = []
		self.spine_names = []
		self.tor_names = []
		self.host_names = []

		self.dpid_to_switchname = {}
		self.switchname_to_dpid = {}

		# Init Topo
		#Topo.__init__(self)
		super(LeafSpine, self).__init__()

		# add spine switches
		for i in range(self.spine_num):
			spine_name = 'S' +  self.ijk_tuple_to_str(i)
			self.spine_names.append(spine_name)
			self.addSwitch(spine_name)

		# add leaf switches		
		for i in range(self.leaf_num):
			leaf_name = 'L' + self.ijk_tuple_to_str(i)
			self.leaf_names.append(leaf_name)
			self.addSwitch(leaf_name)
			# add core links
			for spine_name in self.spine_names:
				self.addLink(leaf_name, spine_name, **core_link_config)
		
		for i, leaf_name in enumerate(self.leaf_names):
			for j in range(self.rack_per_leaf):
				# add tor switches
				tor_name = 'T' + self.ijk_tuple_to_str(i, j)
				self.tor_names.append(tor_name)
				self.addSwitch(tor_name)

				# add aggre link
				self.addLink(leaf_name, tor_name, **aggr_link_config)   # use_htb=False

				# add hosts
				for k in range(self.host_per_rack):
					host_name = 'H' + self.ijk_tuple_to_str(i, j, k) # cpu=1.0/NUMBER)
					self.host_names.append(host_name)
					self.addHost(host_name)
					self.addLink(tor_name, host_name, **access_link_config)

		self.net = None

	def addSwitch(self, switch_name):
		dpid = len(self.dpid_to_switchname) + 1
		self.dpid_to_switchname[dpid] = switch_name
		#return Topo.addSwitch(self, switch_name, dpid=str(dpid))
		return super(LeafSpine, self).addSwitch(switch_name, dpid=str(dpid))

	def sys_shell(self, cmd):
		cmd = cmd.replace('\t', "").replace('\n', "")
		print('# debug, cmd:', cmd)
		return os.system(cmd)

	def ijk_tuple_to_str(self, *ijk):
		return 'm'.join(map(str, ijk))

	def ijk_str_to_tuple(self, s):
		return eval(s.replace('m', ','))

	def set_ovs_protocol(self):
		for sw_name in self.switches():
			cmd = "sudo ovs-vsctl set bridge %s protocols=%s" % (sw_name, self.of_version)
			self.sys_shell(cmd)

	def set_host_ip(self, net=None, offset=100):
		if net is None:
			net = self.net

		for host_name in self.host_names:
			h = net.get(host_name)
			i, j, k = self.ijk_str_to_tuple(host_name[1:])
			h.setIP("10.%d.%d.%d" % (i, j, k + offset))
	
	def configure_default_multicast_routes(self, net=None):
		if net is None:
			net = self.net
		for host_name in self.host_names:
			h = net.get(host_name)
			cmd_str = "route add -net 224.0.0.0 netmask 224.0.0.0 " + host_name + '-eth0'
			h.cmd(cmd_str)
	
	def get_host_ip(self, host_name):
		h = self.net.get(host_name)
		return h.IP()

	def install_ecmp_routes(self, net=None):
		"""
			Install ECMP routes proactively.
		"""
		if net is None:
			net = self.net

		# Down: spine --> leaf --> tor --> host
		# spine to leaf
		for spine_name in self.spine_names:
			for i, leaf_name in enumerate(self.leaf_names):
				subnet = "10.{0}.0.0/16".format(i)
				port = self.port(spine_name, leaf_name)[0]
				#print(port, '---------')
				assert isinstance(port, int)

				for pro in ('ip', 'arp'):
					cmd = "ovs-ofctl add-flow %s -O %s \
						'table=0,idle_timeout=0,hard_timeout=0,priority=10,%s, \
						nw_dst=%s, actions=output:%d'" % (spine_name, self.of_version, pro, subnet, port)
					self.sys_shell(cmd)
				
		# leaf to tor
		for i, leaf_name in enumerate(self.leaf_names):
			for j in range(self.rack_per_leaf):
				subnet = "10.{0}.{1}.0/24".format(i, j)
				tor_name = 'T' + self.ijk_tuple_to_str(i, j)
				port = self.port(leaf_name, tor_name)[0]
				assert isinstance(port, int)

				for pro in ('ip', 'arp'):
					cmd = "ovs-ofctl add-flow %s -O %s \
						'table=0,idle_timeout=0,hard_timeout=0,priority=40,%s, \
						nw_dst=%s,actions=output:%d'" % (leaf_name, self.of_version, pro, subnet, port)
					self.sys_shell(cmd)

				# tor to host
				for k in range(self.host_per_rack):
					host_name = 'H' + self.ijk_tuple_to_str(i, j, k)
					hostip = self.get_host_ip(host_name)
					port = self.port(tor_name, host_name)[0]
					assert isinstance(port, int)

					for pro in ('ip', 'arp'):
						cmd = "ovs-ofctl add-flow %s -O %s \
							'table=0,idle_timeout=0,hard_timeout=0,priority=40,%s, \
							nw_dst=%s,actions=output:%d'" % (tor_name, self.of_version, pro, hostip, port)
						self.sys_shell(cmd)

		# Up: host --> tor --> leaf --> spine
		# host: setdefault routes
		# tor to leaf
		for tor_name in self.tor_names:
			i, j = self.ijk_str_to_tuple(tor_name[1:])
			leaf_name = 'L' + self.ijk_tuple_to_str(i)
			# default route for ....
			subnet = "10.0.0.0/8"
			port = self.port(tor_name, leaf_name)[0]
			assert isinstance(port, int)

			for pro in ('ip', 'arp'):
				cmd = "ovs-ofctl add-flow %s -O %s \
					'table=0,idle_timeout=0,hard_timeout=0,priority=20,%s, \
					nw_dst=%s,actions=output:%d'" % (tor_name, self.of_version, pro, subnet, port)
				self.sys_shell(cmd)

		# leaf to spine, with ECMP
		for i, leaf_name in enumerate(self.leaf_names):
			lst = []
			for spine_name in self.spine_names:
				port = self.port(leaf_name, spine_name)[0]
				assert isinstance(port, int)
				lst.append('bucket=output:{0}'.format(port))
			bucket_s = ','.join(lst)
			
			cmd = "ovs-ofctl add-group %s -O %s \
			'group_id=1,type=select,%s'" % (leaf_name, self.of_version, bucket_s)
			self.sys_shell(cmd)
			subnet = "10.0.0.0/8"
			for pro in ('ip', 'arp'):
				cmd = "ovs-ofctl add-flow %s -O %s \
					'table=0,priority=10,%s,actions=group:1'" % (leaf_name, self.of_version, pro) # TODO
				self.sys_shell(cmd)


	def dump_netconf(self, filename='netconf.txt'):
		topo = {}
		for u, v in self.iterLinks():
			topo.setdefault(u, {})[v] = self.port(u, v)[0]
		host_ips = {}
		for hostname in self.hosts():
			host_ips[hostname] = self.get_host_ip(hostname)
		
		netconfig = {}
		netconfig['dpid_to_switchname'] = self.dpid_to_switchname
		netconfig['topo'] = topo
		netconfig['host_ips'] = host_ips

		with open(filename, 'w') as f:
			print(netconfig, file=f)
		self.netconfig = netconfig
		time.sleep(1)


	def build_net(self, ryu_app='./sdm_app.py'):	
		# Start Mininet.
		net = Mininet(topo=self, link=TCLink, autoSetMacs=True, autoStaticArp=True, controller=None)
		net.addController(
			'controller', controller=RemoteController,
			ip=self.controller_ip, port=self.controller_port)
		#c0 = net.addController('c0')
		net.start()

		self.net = net

		# Set OVS's protocol as OF13.
		self.set_ovs_protocol()
		# Set hosts IP addresses.
		self.set_host_ip()
		time.sleep(1)
		self.configure_default_multicast_routes()
		# Install proactive flow entries
		self.install_ecmp_routes()

		self.dump_netconf()
		#c0.cmdPrint('ryu-manager --verbose {0} &'.format(ryu_app))
		return net

	def cli(self):
		net = self.net

		for s in net.switches:
			print('switch', s.name, s.dpid, s.datapath, s.protocols, )
		CLI(net)
		net.stop()

	def run(self):
		if self.net is None:
			self.build_net()
		return self.cli()



def run_exmaple():
	core_link_config = dict(
		bw=10,
		max_queue_size=1000,
	)
	aggr_link_config = dict(
		bw=40,
		max_queue_size=1000,
	)
	access_link_config = dict(
		bw=100,
		max_queue_size=1000,
	)
	spine_num = 2
	leaf_num = 2
	rack_per_leaf = 2
	host_per_rack = 4

	dcn = LeafSpine(
		leaf_num, spine_num, rack_per_leaf, host_per_rack, 
		core_link_config, aggr_link_config, access_link_config)
	
	print('dcn created!')
	dcn.run()
		

if __name__ == '__main__':
	setLogLevel('info')
	if os.getuid() != 0:
		logging.debug("You are NOT root")
	elif os.getuid() == 0:
		run_exmaple()
		