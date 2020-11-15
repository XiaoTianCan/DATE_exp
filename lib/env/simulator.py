# -*- coding: UTF-8 -*-
'''
    Description: network construction for DATE experiments based on Mininet
'''

import sys
from testbed import *
from topo import *
import time
from functools import partial
from subprocess import Popen

def experiment(topoName, TMbegin = 0, TMend = 2, pktsenderPeriod = 0, pathPre = ""):
    # Step 1: get topo
    print("Step 1: get information of topology " + topoName + "\n")
    env = ReadTopo(pathPre + "inputs/", topoName)
    nodeNum, linkNum, linkSet, demNum, demands, totalPathNum, pathSet, demRates, cMatrix, wMatrix, MAXWEIGHT = env.read_info()

    # Step 2: create mininet topo
    print("Step 2: create mininet topo\n")
    topo = CustomTopo(pathPre, nodeNum, linkSet)
    CONTROLLER_IP = "127.0.0.1"
    CONTROLLER_PORT = 6633
    OVSSwitch13 = partial(OVSSwitch, protocols='OpenFlow13')
    net = Mininet(topo=topo, switch=OVSSwitch13, link=TCLink, controller=None)
    net.addController('controller', controller=RemoteController, ip=CONTROLLER_IP, port=CONTROLLER_PORT)
    net.start()
    
    # Step 3: generate traffic
    os.system("gcc %slib/env/pkt_sender.c -lpthread -o %slib/env/pkt_sender" % (pathPre, pathPre))
    print("wait for rules being installed... (8s)")
    time.sleep(8)
    

    TMfilePath = "%sinputs/traffic/original/%s_TMset.txt" % (pathPre, topoName)
    if topoName == "Cer":
        TMscale = 20.0
    else:
        TMscale = 1.0
        
    popens = topo.generate_traffic(net, TMfilePath, scale = TMscale, TMbegin = TMbegin, TMend = TMend, pktsenderPeriod = pktsenderPeriod)
    stopFlag = False
    while True:
        time.sleep(10)
        if stopFlag:
            break
        stopFlag = False
        for host in net.hosts:
            returncode = Popen.poll(popens[ host ])
            if returncode == 0:
                stopFlag = True
                break

    # Step 4: stop test
    print("wait to close net ... (90)")
    time.sleep(90)
    net.stop()


# Main code
if __name__ == '__main__':
    print("##### Experiments begin! #####")
    topoName = sys.argv[1]
    TMbegin = int(sys.argv[2])
    TMend = int(sys.argv[3])
    pktsenderPeriod = int(sys.argv[4])
    pathPre = sys.argv[5]
    print(topoName, "**")
    experiment(topoName = topoName, TMbegin = TMbegin, TMend = TMend, pktsenderPeriod = pktsenderPeriod, pathPre = pathPre)
