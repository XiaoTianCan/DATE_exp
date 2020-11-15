'''
    Description: construct custom Mininet network
'''

from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import Link, Intf, TCLink
from mininet.topo import Topo
from mininet.util import custom, pmonitor
import logging
import os

class CustomTopo(Topo):
    def __init__(self, pathPre = "", nodeNum = 0, linkSet = [], bandwidth = 1000, **opts):
        Topo.__init__(self,**opts)
        self.__pathPre = pathPre

        self.__nodenum = nodeNum
        self.__linkset = linkSet
        self.__bandwidth = bandwidth

        self.__switches = []
        self.__hosts = []

        self.create_net()
        self.add_hosts()

    def create_net(self):
        for i in range(self.__nodenum):
            self.__switches.append(self.addSwitch("s" + str(i+1)))
        for i in range(len(self.__linkset)):
            node1 = self.__linkset[i][0]
            node2 = self.__linkset[i][1]
            self.addLink(self.__switches[node1], self.__switches[node2], bw = self.__bandwidth, delay='5ms')

    def add_hosts(self):
        if self.__nodenum >= 99:
            print("ERROR!!!")
            exit()
        for i in range(self.__nodenum):
            self.__hosts.append(self.addHost("h" + str(i+1), mac = ("00:00:00:00:00:%02d" % (i+1)), ip = "10.0.0." + str(i+1)))
            self.addLink(self.__switches[i], self.__hosts[i], bw = self.__bandwidth)

    def generate_traffic(self, net, TMfilePath, scale = 10.0, TMbegin = 0, TMend = 2, pktsenderPeriod = 0):
        popens = {}
        print("Total host num:", len(net.hosts))
        for host in net.hosts:
            popens[ host ] = host.popen("%slib/env/pkt_sender %d %d %s %f %d %d %d" % (self.__pathPre, int(host.name[1:]) - 1, self.__nodenum, TMfilePath, scale, TMbegin, TMend, pktsenderPeriod))
        return popens
    def set_OF_version(self, net):
        popens = {}
        print(len(net.switches))
        for switch in net.switches:
            switch.popen("ovs-vsctl set Bridge " + switch.name + " -O openflow13")
        for switch, line in pmonitor( popens ):
            if switch:
                print( "<%s>: %s" % ( switch.name, line ) )


