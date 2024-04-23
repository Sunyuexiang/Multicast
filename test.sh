sudo ovs-ofctl  -O OpenFlow13 add-group T0m1 "group_id=1,type=all,bucket=output:2"
sudo ovs-ofctl  add-flow T0m1 "ip,nw_src=10.0.0.100,actions=group:1"


ovs-ofctl -O OpenFlow13 add-group T0m0 "group_id=50,type=all,bucket=output:2"
ovs-ofctl -O OpenFlow13 add-flow T0m0  "ip,nw_src=10.0.0.100,actions=group:50"

sudo ovs-ofctl -O OpenFlow13 del-flows T0m1 ip
