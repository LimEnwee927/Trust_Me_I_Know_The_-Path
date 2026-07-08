from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, vlan


class SourceRoutingController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SourceRoutingController, self).__init__(*args, **kwargs)
        self.logger.info("=== Passive Source Routing Controller started ===")

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