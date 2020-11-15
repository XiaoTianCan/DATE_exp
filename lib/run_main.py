'''
    Copyright: netlab
    Author: gn
    Date: Nov. 2020
    Description: main codes for DATE experiments
    Notes: run this file in the dir "./DATE_exp/lib"
    ~/DATE_exp/lib$ sudo main.py
    Environment: Ryu, Mininet 2.3, Gurobi, TensorFlow, tflearn
'''
import os
import sys
import time
from subprocess import Popen, PIPE

CONF_PATH = os.getcwd().replace("lib", "")
##############################################################################################################
def write_config(topo, target, monitorPeriod, maxUpdateCount, timestamp, failureFlag):
    file = open(CONF_PATH + "inputs/configures/" + topo + "_" + target + ".config", 'w')
    file.write("[DEFAULT]\n\n")
    file.write('pathPre = "' + CONF_PATH + '"\n')
    file.write('topoName = "' + topo + '"\n')
    file.write('scheme = "' + target + '"\n')
    file.write('monitorPeriod = "' + monitorPeriod + '"\n')
    file.write('maxUpdateCount = "' + maxUpdateCount + '"\n')
    file.write('logging_stamp = "' + timestamp + '"\n')
    file.write('failureFlag = "' + str(failureFlag) + '"\n')
    file.close()

def generate_config(topo_set, schemes, timestamp, monitorPeriod, maxUpdateCount, failureFlag):
    for topo in topo_set:
        for target in schemes:
            write_config(topo, target, monitorPeriod, maxUpdateCount, timestamp, failureFlag)

def run_fun(topo, target, TMbegin, TMend, pktsenderPeriod):
    cmd_controller = "ryu-manager %slib/env/controller.py --config-file %s" % (CONF_PATH, CONF_PATH + "inputs/configures/" + topo + "_" + target + ".config")
    fd_controller = Popen(cmd_controller, shell = True, stdout=PIPE, stderr=PIPE)
    print("cmd_controller:", cmd_controller)
    time.sleep(15)
    cmd_mininet = "python3 %slib/env/simulator.py %s %d %d %d %s" % (CONF_PATH, topo, TMbegin, TMend, pktsenderPeriod, CONF_PATH)
    fd_mininet = Popen(cmd_mininet, shell = True, stdout=PIPE, stderr=PIPE)
    print("cmd_mininet:", cmd_mininet)
    time.sleep(15)
    return fd_controller, fd_mininet

def run_loop(topo_set, schemes, TMbegin, TMend, pktsenderPeriod, ckptDirName):
    for topo in topo_set:
        for target in schemes:
            if target == "DATE":
                cmd_sim_ddpg = "python3 %slib/date/main.py --path_pre=%s --stamp_type=%s_DATE_exp --topo_name=%s --offline_flag=False --agent_type=DATE --is_train=False --synthesis_type=exp --ckpt_path=%soutputs/ckpoint/%s/ckpt" % (CONF_PATH, CONF_PATH, topo, topo, CONF_PATH, ckptDirName)
                fd_sim_ddpg = Popen(cmd_sim_ddpg, shell = True, stdout=PIPE, stderr=PIPE)
                print("cmd_sim_ddpg:", cmd_sim_ddpg)
                time.sleep(15)
            fd_controller, fd_mininet = run_fun(topo, target, TMbegin, TMend, pktsenderPeriod)
            count = 0
            while True:
                if count%30 == 0:
                    print(count, Popen.poll(fd_controller), Popen.poll(fd_mininet))
                count += 1
                if Popen.poll(fd_controller) == 0 and Popen.poll(fd_mininet) == 0:
                    print(topo, target, "finished\n")
                    # print(Popen.poll(fd_controller), Popen.poll(fd_controller))
                    time.sleep(60)
                    break
                time.sleep(10)
##############################################################################################################
# 1) basic var.
topo_setAll = ['Cer']
schemesAll = ['SP', 'LB', 'SMORE', 'OR', 'DATE']

# 2) settings (set your para. here)
topo_set = ['Cer']
schemes = ['SP']
timestamp = "1115_test2"
TMbegin = 288*3
TMend = 288*3 + 1
monitorPeriod = "2.5"
maxUpdateCount = str((TMend - TMbegin)*2 + 20)

failureFlag = 0 # for failure test; not used in the current version
pktsenderPeriod = 0
ckptDirName = "1114_Cer_train_DATE_p3_exp_epoch8000"


# 3) start running
generate_config(topo_setAll, schemesAll, timestamp, monitorPeriod, maxUpdateCount, failureFlag)
print("\nwrite config file over\n")
run_loop(topo_set, schemes, TMbegin, TMend, pktsenderPeriod, ckptDirName)
