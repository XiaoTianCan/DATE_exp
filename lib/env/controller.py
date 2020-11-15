# -*-coding:utf-8 -*-
'''
    Description: the routing application of DATE in the Ryu controller
'''

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ether_types
from ryu.lib.packet import ethernet, ipv4, arp
from ryu.lib import hub
from ryu import cfg
from operator import attrgetter

from solver import *
from topo import *
from socket import *
import json
import os
import copy


class FlowScheduler(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(FlowScheduler, self).__init__(*args, **kwargs)
        # original topo info
        self.env = None
        self.node_num = 0
        self.link_num = 0
        self.link_set = []
        self.dem_num = 0
        self.demands = []
        self.total_path_num = 0
        self.path_set = []
        self.dem_rates = []
        self.capa_matrix = []
        self.weigth_matrix = []
        self.MAXWEIGHT = 0
        self.candidatepathspair = []

        # mininet topo
        self.link_port = []
        self.switch_host_port = []
        self.nodeid_datapath = {}
        self.failure_flag = 0
        self.link_ind = 0
        self.rate_ind = 0
        self.failure_test_stop = 0

        # routing polocy
        self.scheme = None
        self.routing_file = ""
        self.routing_weights = []
        self.routing_option_file = ""
        self.max_update_count = None
        self.update_count = 0
        self.TM_window_size = 5

        # status variable
        self.rule_ready_flag = False
        self.monitor_period = None
        self.port_states_reply_count = 0
        self.flow_states_reply_count = 0
        self.edge_bytes_map = []
        self.edge_rates_map = []
        self.dem_bytes_map = []
        self.dem_rates_map = []
        self.last_dem_rates_map = []
        self.in_bytes = []
        self.scale_ratio = None
        self.stop_flag = False
        self.his_TMs = []

        # log variable
        self.logging_stamp = ""
        self.log_maxutil = None
        self.log_rule_update = None
        self.log_edgeutil = None
        self.rule_update_time = 0
        self.last_routing_weights = None

        # connection setting for sim-ddpg or other local agent
        self.local_server_socket = None
        self.local_server_IP = "127.0.0.1"
        self.local_server_port = 50003
        self.agent_socket = None
        self.agent_ready_flag = False
        self.blockSize = 1024
        self.BUFSIZE = 1025
        
        self.set_para()
        self.get_topo_info()
        self.init_vars()
        self.logging_init()
        self.install_rules_thread = hub.spawn(self.install_static_rules)
        self.monitor_thread = hub.spawn(self.monitor_stats)

    '''set_para(): set some basic parameters'''
    def set_para(self):
        CONF = cfg.CONF
        CONF.register_opts([
            cfg.StrOpt('pathPre', default="./", help=("Path prefix")),
            cfg.StrOpt('topoName', default="Cer", help=("Topology name")),
            cfg.StrOpt('scheme', default="SP", help=("Scheme name")),
            cfg.StrOpt('monitorPeriod', default="2.5", help=("Monitor period")),
            cfg.StrOpt('maxUpdateCount', default="20", help=("Maximum update count")),
            cfg.StrOpt('logging_stamp', default="test", help=("Logging directory name")),
            cfg.IntOpt('failureFlag', default=0, help=("Failure flag"))])

        self.path_pre = CONF.pathPre
        self.topo_name = CONF.topoName
        self.scheme = CONF.scheme
        self.failure_flag = CONF.failureFlag
        print("Topology: ", self.topo_name)
        print("Scheme: ", self.scheme)

        if self.scheme == "SMORE" or self.scheme == "LB" or self.scheme == "DATE":
            self.path_type = "racke"
        elif self.scheme == "SP":
            self.path_type = "sp"
        elif self.scheme == "OR":
            self.path_type = "or"
            self.routing_file = "%sinputs/routing/%s_or_routing.txt" % (self.path_pre, self.topo_name)
        else:
            self.path_type = "racke"
        self.rule_priority = 4
        self.monitor_period = float(CONF.monitorPeriod)     # 2.5
        self.scale_ratio = 20.0                             # capacity scale para
        self.max_update_count = int(CONF.maxUpdateCount)    # 288*2*2 + 20 # 20
        self.logging_stamp = CONF.logging_stamp             # "Test"

    def init_vars(self):
        if self.scheme == "SP":
            for i in range(self.dem_num):
                self.routing_weights.append(100)
        elif self.scheme == "SMORE" or self.scheme == "LB" or self.scheme == "DATE":
            routing = []
            for i in range(self.dem_num):
                splitRatio = 1.0/len(self.path_set[i])
                for j in range(len(self.path_set[i])):
                    routing.append(splitRatio)
            self.routing_to_weight(routing)
            self.last_routing_weights = copy.deepcopy(self.routing_weights)
        elif self.scheme == "OR":
            file = open(self.routing_file)
            lines = file.readlines()
            file.close()
            routing = list(map(float, [item.strip() for item in lines]))
            self.routing_to_weight(routing)
        else:
            pass

        if self.scheme == "DATE":
            self.connect_agent()
        for i in range(self.TM_window_size):
            self.his_TMs.append([0.0]*self.dem_num)
        for i in range(self.node_num):
            self.edge_bytes_map.append([0]*self.node_num)
            self.edge_rates_map.append([0.0]*self.node_num)
            self.dem_bytes_map.append([0]*self.node_num)
            self.dem_rates_map.append([0.0]*self.node_num)
        self.in_bytes = [0]*self.node_num
        print("\nReady now!\n")

    def connect_agent(self):
        agentServer = (self.local_server_IP, self.local_server_port)
        self.agent_socket = socket(AF_INET, SOCK_STREAM)
        self.agent_socket.connect(agentServer)
        self.agent_ready_flag = True

    def get_topo_info(self):
        self.env = ReadTopo("%sinputs/" % self.path_pre, self.topo_name, self.path_type)
        self.node_num, self.link_num, self.link_set, self.dem_num, self.demands, self.total_path_num, self.path_set, self.dem_rates, self.capa_matrix, self.weigth_matrix, self.MAXWEIGHT = self.env.read_info()

        # resize capa_matrix !
        for i in range(self.node_num):
            for j in range(self.node_num):
                self.capa_matrix[i][j] /= self.scale_ratio
        # print(self.capa_matrix)

        # get switch port map
        switchPortCount = [1 for i in range(self.node_num)]
        for i in range(self.node_num):
            self.link_port.append([-1]*self.node_num)
        for i in range(self.link_num):
            node1 = self.link_set[i][0]
            node2 = self.link_set[i][1]
            self.link_port[node1][node2] = switchPortCount[node1]
            self.link_port[node2][node1] = switchPortCount[node2]
            switchPortCount[node1] += 1
            switchPortCount[node2] += 1
        for i in range(self.node_num):
            self.switch_host_port.append(switchPortCount[i])

        # failure test 2019.9.23
        for i in range(self.dem_num):
            self.candidatepathspair.append([])
            for j in range(len(self.path_set[i])):
                self.candidatepathspair[i].append([])
                for k in range(len(self.path_set[i][j])-1):
                    enode1 = self.path_set[i][j][k]
                    enode2 = self.path_set[i][j][k+1]
                    self.candidatepathspair[i][j].append((enode1, enode2))


    '''install_static_rules(): install static forwarding rules of each path'''
    def install_static_rules(self):
        while len(self.nodeid_datapath) < self.node_num:
            hub.sleep(5)

        routing_id = 0
        # for all flows
        for i in range(self.dem_num):
            src = self.demands[i][0]
            dst = self.demands[i][1]
            # ingress: goto table
            datapath = self.nodeid_datapath[src]
            ofproto = datapath.ofproto
            parser = datapath.ofproto_parser
            
            # ingress: group table; tag pkts
            weights = []
            actions_set = []
            for j in range(len(self.path_set[i])):
                weights.append(self.routing_weights[routing_id])
                routing_id += 1
                out_port = self.link_port[src][self.path_set[i][j][1]]
                vlan_vid = (src*self.node_num+dst)*10+j
                udp_src = 8000 + (src * self.node_num + dst)*10 + j
                actions = [parser.OFPActionSetField(udp_src = udp_src), parser.OFPActionOutput(out_port)]
                actions_set.append(actions)
            group_id = dst + 1
            self.add_group(datapath, weights, actions_set, group_id)

            # ingress: goto table
            in_port = self.switch_host_port[src]
            match = parser.OFPMatch(in_port=in_port, ipv4_dst="10.0.0."+str(dst+1), eth_type=0x0800)
            actions = [parser.OFPActionGroup(group_id = group_id)]
            self.add_flow(datapath, self.rule_priority, match, actions)

            # middle & egress: match tag
            for j in range(len(self.path_set[i])):
                path = self.path_set[i][j]
                vlan_vid = (src*self.node_num+dst)*10+j
                udp_src = 8000 + (src * self.node_num + dst)*10 + j
                for k in range(1, len(path)):
                    datapath = self.nodeid_datapath[path[k]]
                    ofproto = datapath.ofproto
                    parser = datapath.ofproto_parser
                    in_port = self.link_port[path[k]][path[k-1]]
                    match = parser.OFPMatch(in_port=in_port, udp_src=udp_src, ip_proto=17,
                                ipv4_dst="10.0.0."+str(dst+1), eth_type=0x0800)
                    if k == len(path) - 1:
                        # out_port = self.switch_host_port[path[k]]
                        actions = []
                    else:
                        out_port = self.link_port[path[k]][path[k+1]]
                        actions = [parser.OFPActionOutput(out_port)]
                    self.add_flow(datapath, self.rule_priority, match, actions)

        self.rule_ready_flag = True
        print("Install static flow rules successfully\n")

    '''switch_features_handler(): install static flow rules upon connecting with each switch'''
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        dpid = datapath.id
        nodeid = dpid - 1
        self.nodeid_datapath[nodeid] = datapath
        print("install static flow rules for s"+str(dpid))

        # install packet-in flow rules
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

        in_port = self.switch_host_port[nodeid]
        actions = []
        # ipv6
        match = parser.OFPMatch(in_port=in_port, eth_type=0x86DD)
        self.add_flow(datapath, self.rule_priority + 1, match, actions)
        # dst = 224.*
        match = parser.OFPMatch(in_port=in_port, ipv4_dst="224.0.0.0/255.255.0.0", eth_type=0x0800)
        self.add_flow(datapath, self.rule_priority + 1, match, actions)

    '''add_group(): add a flow rule into a specific switch'''
    def add_group(self, datapath, weights, actions_set, group_id, modify_flag = False):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        watch_port = ofproto_v1_3.OFPP_ANY
        watch_group = ofproto_v1_3.OFPQ_ALL
     
        buckets = []
        for i in range(len(weights)):
            buckets.append(parser.OFPBucket(weight = weights[i], watch_port = watch_port, watch_group = watch_group, actions = actions_set[i]))
            # buckets.append(parser.OFPBucket(actions = actions_set[i]))
        if not modify_flag:
            req = parser.OFPGroupMod(datapath, ofproto.OFPGC_ADD,
                ofproto.OFPGT_SELECT, group_id, buckets)
        else:
            req = parser.OFPGroupMod(datapath, ofproto.OFPGC_MODIFY,
                ofproto.OFPGT_SELECT, group_id, buckets)
     
        datapath.send_msg(req)

    '''add_flow(): add a flow rule into a specific switch'''
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

    '''_packet_in_handler(): deal with arp packet'''
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        if ev.msg.msg_len < ev.msg.total_len:
            self.logger.debug("packet truncated: only %s of %s bytes",
                              ev.msg.msg_len, ev.msg.total_len)
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        pkt = packet.Packet(msg.data)
        arppkt = pkt.get_protocol(arp.arp)

        if arppkt != None:
            # print("Packet in: arp broadcast")
            for nodeid in range(self.node_num):
                actions = [parser.OFPActionOutput(self.switch_host_port[nodeid])]
                datapath = self.nodeid_datapath[nodeid]
                out = parser.OFPPacketOut(
                    datapath=datapath,
                    buffer_id=ofproto.OFP_NO_BUFFER,
                    in_port=ofproto.OFPP_CONTROLLER,
                    actions=actions, data=msg.data)
                datapath.send_msg(out)

    '''monitor_stats(): send stats request to each switch every a few seconds'''
    def monitor_stats(self):
        while True:
            if self.rule_ready_flag:
                break
            hub.sleep(self.monitor_period)
        print("Monitor function is started (%fs)" % self.monitor_period)
        while not self.stop_flag:
            for datapath in self.nodeid_datapath.values():
                ofproto = datapath.ofproto
                parser = datapath.ofproto_parser
                req = parser.OFPFlowStatsRequest(datapath)
                datapath.send_msg(req)
                req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
                datapath.send_msg(req)
            # detection period
            # print("monitor_states requests are sent")
            hub.sleep(self.monitor_period)
            
    '''_port_stats_reply_handler(): parse stats reply packets from each switch'''
    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        body = ev.msg.body
        # store stats, get maps
        nodeid = ev.msg.datapath.id - 1
        for stat in body:
            if stat.port_no == self.switch_host_port[nodeid]:
                inrate = round((stat.rx_bytes - self.in_bytes[nodeid])*8.0/self.monitor_period/1000/1000, 2)
                # print("Enter node %d traffic: %f" % (nodeid, inrate))
                self.in_bytes[nodeid] = stat.rx_bytes
                continue
            for i in range(self.node_num):
                if stat.port_no == self.link_port[nodeid][i]:
                    self.edge_rates_map[nodeid][i] = round((stat.tx_bytes - self.edge_bytes_map[nodeid][i])*8.0/self.monitor_period/1000/1000, 2)
                    self.edge_bytes_map[nodeid][i] = stat.tx_bytes
                    break

        self.port_states_reply_count += 1
        if self.port_states_reply_count == self.node_num:
            self.port_states_reply_count = 0
            # Failure
            if self.failure_flag == 1 and self.update_count >= 10 and self.failure_test_stop <= 1:
                if self.failure_test_stop == 0:
                    self.failure_test_stop = 1
                    print("66.888888", file=self.log_maxutil)
                
                if self.update_count % 10 == 0:
                    updateCount = self.update_count - 10
                    decay_rates = [1, 0.9, 0.7, 0.5, 0.3, 0.1]
                    left = self.link_set[self.link_ind][0]
                    right = self.link_set[self.link_ind][1]
                    self.capa_matrix[left][right] /= decay_rates[self.rate_ind]
                    self.capa_matrix[right][left] /= decay_rates[self.rate_ind]
                    self.rate_ind = updateCount // (10*self.link_num)
                    self.link_ind = (updateCount % (10*self.link_num)) // 10
                    if self.rate_ind >= 6 or self.link_ind >= self.link_num:
                        self.failure_test_stop = 2
                        print("88.888888", file=self.log_maxutil)
                    else:
                        left = self.link_set[self.link_ind][0]
                        right = self.link_set[self.link_ind][1]
                        self.capa_matrix[left][right] *= decay_rates[self.rate_ind]
                        self.capa_matrix[right][left] *= decay_rates[self.rate_ind]

            sess_path_util = []
            for i in range(self.dem_num): 
                sess_path_util.append([])
                for j in range(len(self.path_set[i])):
                    pathutil = []
                    for k in range(len(self.path_set[i][j])-1):
                        enode1 = self.path_set[i][j][k]
                        enode2 = self.path_set[i][j][k+1]
                        pathutil.append(round(self.edge_rates_map[enode1][enode2]/self.capa_matrix[enode1][enode2], 5))
                    sess_path_util[i].append(pathutil)
            
            # calculate edge utils
            net_util = []
            for i in range(self.node_num):
                for j in range(self.node_num):
                    if self.capa_matrix[i][j] > 0:
                        net_util.append(self.edge_rates_map[i][j] / self.capa_matrix[i][j])

            max_util = max(net_util)
            print(max_util, file=self.log_maxutil)
            print(" ".join(list(map(str, net_util))), file=self.log_edgeutil)

            while True:
                if self.flow_states_reply_count == 0:
                    window_TMs = []
                    for i in range(self.TM_window_size):
                        window_TMs += self.his_TMs[i]
                    break
                else:
                    hub.sleep(0.01)

            states = {
                    'max_util': max_util,
                    'sess_path_util': sess_path_util,
                    'net_util': net_util,
                    'window_TMs': window_TMs
                    }
            # update decisions
            if self.scheme in ["DATE"]:
                self.make_decision(states)

    '''_flow_stats_reply_handler(): parse stats reply packets from each switch'''
    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        body = ev.msg.body
        nodeid = ev.msg.datapath.id - 1
        for stat in body:
            if 'in_port' in stat.match and stat.match['in_port'] == self.switch_host_port[nodeid] and 'ipv4_dst' in stat.match:
                if type(stat.match['ipv4_dst']) != type("ip address"):
                    continue
                dst = int(stat.match['ipv4_dst'].split('.')[-1]) - 1
                self.dem_rates_map[nodeid][dst] = round(((stat.byte_count - self.dem_bytes_map[nodeid][dst]))*8.0/self.monitor_period/1000/1000, 2)
                self.dem_bytes_map[nodeid][dst] = stat.byte_count

        self.flow_states_reply_count += 1
        if self.flow_states_reply_count == self.node_num:
            for i in range(1, self.TM_window_size):
                self.his_TMs[i-1] = self.his_TMs[i]
            demrate = []
            for i in range(self.node_num):
                for j in range(self.node_num):
                    if i == j:
                        continue
                    demrate.append(self.dem_rates_map[i][j])
            self.his_TMs[-1] = demrate
            self.flow_states_reply_count = 0

            # update decisions
            if self.scheme not in ["DATE"]:
                self.make_decision()

    def routing_to_weight(self, routing):
        if len(self.routing_weights) == 0:
            self.routing_weights = [0]*len(routing)
        pathId = 0
        for i in range(self.dem_num):
            weigthCum = 0
            for j in range(0, len(self.path_set[i])-1):
                self.routing_weights[pathId] = int(1000*routing[pathId])
                weigthCum += int(1000*routing[pathId])
                pathId += 1
            self.routing_weights[pathId] = 1000 - weigthCum
            pathId += 1

    def make_decision(self, states = None):
        if self.update_count%100 == 0:
            print("update_count: ", self.update_count)
        self.update_count += 1
        if self.update_count > self.max_update_count:
            self.stop_flag = True
            print("Wait to shutdown... (5s)")
            hub.sleep(5)
            if self.scheme == "DATE":
                self.agent_socket.send(("0;").encode())
                self.agent_socket.close()

            self.log_maxutil.close()
            self.log_edgeutil.close()
            print(self.rule_update_time, file=self.log_rule_update)
            self.log_rule_update.close()
            os._exit(0)

        if self.scheme == "SMORE":
            if self.failure_test_stop >= 1:
                return
            pathRates = []
            demId = 0
            for i in range(self.node_num):
                for j in range(self.node_num):
                    if i == j:
                        continue
                    for k in range(len(self.path_set[demId])):
                        pathRates.append(self.dem_rates_map[i][j])
                    demId += 1

            routing, _ = sorsolver(self.node_num, self.dem_num, self.total_path_num, self.path_set, pathRates, self.capa_matrix)
            self.routing_to_weight(routing)
            self.update_decision()

        if self.scheme == "DATE":
            if not self.agent_ready_flag:
                print("no sim_ddpg agent")
                exit()
            if states["max_util"] <= 0.01:
                return
            # call sim-ddpg.py to get actions
            state_encode = json.dumps(states)
            self.send_msg(state_encode, self.agent_socket) 
            recvmsg = self.recv_msg(self.agent_socket)
            routing = json.loads(recvmsg)

            # failure 2019.9.23
            if self.failure_flag == 2 and self.update_count >= 10 and self.failure_test_stop <= 1:
                if self.failure_test_stop == 0:
                    self.failure_test_stop = 1
                    print("66.888888", file=self.log_maxutil)
                routing = self.action_failure(routing)


            self.routing_to_weight(routing)
            self.update_decision()

        
        if self.scheme in ["SMORE", "DATE"]:
            if self.routing_weights != self.last_routing_weights:
                self.rule_update_time += 1
            self.last_routing_weights = copy.deepcopy(self.routing_weights)

    def action_failure(self, action):
        if self.link_ind >= self.link_num:
            self.failure_test_stop = 2
            print("88.888888", file=self.log_maxutil)
            return action
        left = self.link_set[self.link_ind][0]
        right = self.link_set[self.link_ind][1]
        count = 0
        action_res = []
        for i in range(self.dem_num):
            action_tmp = []
            action_flag = []
            split_more = 0.0
            for j in range(len(self.path_set[i])):
                if (left, right) in self.candidatepathspair[i][j] or (right, left) in self.candidatepathspair[i][j]:
                    action_tmp.append(0.0)
                    action_flag.append(0)
                    split_more += action[count]
                else:
                    action_flag.append(1)
                    action_tmp.append(action[count])
                count += 1

            if sum(action_flag) <= 0.0001:
                self.rate_ind += 1
                print("disconnected!!!!!%d" % self.rate_ind, self.link_ind)
                self.link_ind = (self.update_count-9)//10
                return action

            action_res += self.comsum(action_tmp, action_flag, split_more)
        # if self.update_count % 10 == 0:
        #     print(self.link_ind)
        self.link_ind = (self.update_count-9)//10
        return action_res

    def comsum(self, action_tmp, action_flag, split_more):
        sums = 0.0
        for i in range(len(action_flag)):
            if action_flag[i] == 1:
                sums += action_tmp[i]

        res = []
        if sums <= 0.0001:
            w = 1.0/sum(action_flag)
            for i in range(len(action_flag)):
                if action_flag[i] == 1:
                    res.append(w)
                else:
                    res.append(0.0)
        else:
            for i in range(len(action_flag)):
                if action_flag[i] == 1:
                    res.append(action_tmp[i] + (action_tmp[i]/sums)*split_more)
                else:
                    res.append(0.0)

        return res

    '''send_msg(): send a str msg to the dest '''
    def send_msg(self, msg, socket):
        #print("send msg is", msg)
        msg = str(len(msg)) + ';' + msg
        msgTotalLen = len(msg)
        blockNum = int((msgTotalLen - 1) / self.blockSize + 1)
        for i in range(blockNum):
            data = msg[i * self.blockSize : (i + 1) * self.blockSize]
            socket.send(data.encode())
    
    '''recv_msg(): receive the message from src'''
    def recv_msg(self, socket):
        msgTotalLen = 0
        msgRecvLen = 0
        realmsg_ptr = 0
        msg = ""
        while True:
            datarecv = socket.recv(self.BUFSIZE).decode()
            if len(datarecv) > 0:
                if msgTotalLen == 0:
                    totalLenStr = (datarecv.split(';'))[0]
                    msgTotalLen = int(totalLenStr) + len(totalLenStr) + 1#1 is the length of ';'
                    realmsg_ptr = len(totalLenStr) + 1
                msgRecvLen += len(datarecv)
                msg += datarecv
                if msgRecvLen == msgTotalLen: 
                    return msg[realmsg_ptr:]

    def update_decision(self):
        routing_id = 0
        # for all demands
        for i in range(self.dem_num):
            src = self.demands[i][0]
            dst = self.demands[i][1]
            # ingress: goto table
            datapath = self.nodeid_datapath[src]
            ofproto = datapath.ofproto
            parser = datapath.ofproto_parser
            
            # ingress: group table; tag pkts
            weights = []
            actions_set = []
            for j in range(len(self.path_set[i])):
                weights.append(self.routing_weights[routing_id])
                routing_id += 1
                out_port = self.link_port[src][self.path_set[i][j][1]]
                vlan_vid = (src*self.node_num+dst)*10+j
                udp_src = 8000 + (src * self.node_num + dst)*10 + j
                actions = [parser.OFPActionSetField(udp_src = udp_src), parser.OFPActionOutput(out_port)]
                actions_set.append(actions)
            group_id = dst + 1
            self.add_group(datapath, weights, actions_set, group_id, True)

    '''logging_init(): init the logging file'''
    def logging_init(self):
        DIR_LOG = ""
        DIR_LOG = "%soutputs/log/%s_%s_%s" % (self.path_pre, self.logging_stamp, self.topo_name, self.scheme)
        if not os.path.exists(DIR_LOG):
            os.mkdir(DIR_LOG)
        self.log_maxutil = open(DIR_LOG + "/maxutil.log", "w", 1)
        self.log_rule_update = open(DIR_LOG + "/update.log", "w", 1)
        self.log_edgeutil = open(DIR_LOG + "/edgeutil.log", "w", 1)
