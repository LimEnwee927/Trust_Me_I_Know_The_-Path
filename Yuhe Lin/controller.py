from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet, ipv4
from ryu.lib import hub

import json
from ryu.topology import api as topo_api
from ryu.lib.packet import packet, ethernet, udp, ipv4


class Switch13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(Switch13, self).__init__(*args, **kwargs)

        # start asynchronous task _timer_loop
        hub.spawn(self._timer_loop)
    
    

    # do something every n seconds
    def _timer_loop(self):
        hub.sleep(2) 
        self.logger.info("Start notificating hosts via Packet-Out")
        # topo1 = {
        #     "10.0.0.1": {
        #         "10.0.0.2": [3, 2, 1]
        #     },
        #     "10.0.0.2": {
        #         "10.0.0.1": [3, 1, 1]
        #     }
        # }
        
        while True:

            # TODO: find out actual topo, pack it in a json and replace topo2
            topo2 = {
                "10.0.0.1": {
                    "10.0.0.2": [2, 2, 2, 1]
                },
                "10.0.0.2": {
                    "10.0.0.1": [2, 1, 1, 1]
                }
            }

            try:
                # find the sw s1, which connects h1 with s1-eth1
                switches = topo_api.get_all_switch(self)
                s1_datapath = None
                s4_datapath = None
                
                for sw in switches:
                    if sw.dp.id == 1: # find s1
                        s1_datapath = sw.dp
                    elif sw.dp.id == 4: # find s4
                        s4_datapath = sw.dp
                
                if s1_datapath is not None:
                    # send to s1-eth1
                    self.notify_host_new_route(s1_datapath, host_port=1, path_list=topo2)
                    self.logger.info(f"Sent s{s1_datapath.id} new topo list: {topo2}")

                if s4_datapath is not None:
                    # send to s4-eth1
                    self.notify_host_new_route(s4_datapath, host_port=1, path_list=topo2)
                    self.logger.info(f"Sent s{s4_datapath.id} new topo list: {topo2}")
                
            except Exception as e:
                self.logger.error(f"Loop error: {e}")
            
            # set loop time
            hub.sleep(5)
            
    # Controller send msg to h1 and h2
    def notify_host_new_route(self, datapath, host_port, path_list):
        # OpenFlow Packet-Out 
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        pkt = packet.Packet()
        
        # create ethertype header
        eth_pkt = ethernet.ethernet(dst='08:00:00:00:00:11', src='00:00:00:00:00:11', ethertype=0x0800)
        
        # create udp header, port: 9999
        udp_pkt = udp.udp(dst_port=9999, src_port=5555, csum=0)
        
        # add payload(information), transform in json
        payload_bytes = json.dumps(path_list).encode('utf-8')

        tot_len = 20 + 8 + len(payload_bytes)

        # create ipv4 header
        ip_pkt = ipv4.ipv4(dst='10.0.0.1', src='10.0.0.254', proto=17, total_length=tot_len, csum=0)

        # deparse
        pkt.add_protocol(eth_pkt)
        pkt.add_protocol(ip_pkt)
        pkt.add_protocol(udp_pkt)
        pkt.add_protocol(payload_bytes)
        pkt.serialize()
        
        actions = [parser.OFPActionOutput(host_port)]
        
        # pack it into Packet-Out message
        out = parser.OFPPacketOut(
            datapath=datapath, 
            buffer_id=ofproto.OFP_NO_BUFFER, 
            in_port=ofproto.OFPP_CONTROLLER,
            actions=actions, 
            data=pkt.data
        )
        datapath.send_msg(out)





    def add_flow(self, dp, table, priority, match, actions=None, buffer_id=None, i_tout=0, h_tout=0):
        ofproto = dp.ofproto
        parser = dp.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        if buffer_id:
            mod = parser.OFPFlowMod(datapath=dp, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst, table_id=table,
                                    idle_timeout=i_tout, hard_timeout=h_tout)
        else:
            mod = parser.OFPFlowMod(datapath=dp, priority=priority,
                                    match=match, instructions=inst, table_id=table,
                                    idle_timeout=i_tout, hard_timeout=h_tout)

        dp.send_msg(mod)


    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # set maximum of physical ports for sw
        MAX_PORTS = 3
        
        # set flow entries for forwarding source routing pkts and popping outer vlan tag
        for port_num in range(1, MAX_PORTS + 1):
            # out port = outer vlan id
            match_vlan = parser.OFPMatch(vlan_vid=(ofproto.OFPVID_PRESENT | port_num))
            
            # pop outer vlan tag, forward pkt to out port
            actions_vlan = [
                parser.OFPActionPopVlan(),
                parser.OFPActionOutput(port_num)
            ]
            # add flow with high priority
            self.add_flow(dp=datapath, table=0, priority=2000, match=match_vlan, actions=actions_vlan)  

        self.logger.info(f"Switch s{datapath.id} source routing forwarding flow added.")

