#!/usr/bin/python
#########################################################################
# File Name: run.py
# Discription: parameter setting and system running
#########################################################################
import os, sys
import numpy as np
import time

def get_stamp_type(time_stamp, topo, target, scheme, path_num, synthesis_type, epochs, stamp_tail):
    stamp_type = "%s_%s_%s_%s_p%d_%s" % (time_stamp, topo, target, scheme, path_num, synthesis_type)
    stamp_type += "_epoch%d" % (epochs)
    if stamp_tail != "":
        stamp_type += '_' + stamp_tail
    return stamp_type

def run(path_pre, scheme, epochs, topo, path_num = 3, train_start_index = 0, path_type = "racke", synthesis_type = "exp", train_episodes = 24*4, infer_episodes = 288*7):
    stamp_type = get_stamp_type(time_stamp, topo, target, scheme, path_num, synthesis_type, epochs, stamp_tail)
    print(stamp_type)
    if target == "converge":
        cmd = "python3 date/main.py --path_pre=%s --stamp_type=%s --agent_type=%s --episodes=1 --epochs=%d --topo_name=%s --train_start_index=%d  --synthesis_type=%s --path_type=%s" % (path_pre, stamp_type, scheme, epochs, topo, train_start_index, synthesis_type, path_type)
        print(cmd)
        os.system(cmd)

    elif target == "train":
        cmd = "python3 date/main.py --path_pre=%s --stamp_type=%s --agent_type=%s --episodes=%d --epochs=%d --topo_name=%s --train_start_index=%d  --synthesis_type=%s --path_type=%s" % (path_pre, stamp_type, scheme, train_episodes, epochs, topo, train_start_index, synthesis_type, path_type)
        print(cmd)
        os.system(cmd)

    elif target == "infer":
        infer_stamp_type = get_stamp_type(time_stamp, topo, "train", scheme, path_num, synthesis_type, epochs, stamp_tail)
        ckpt_path = "%soutputs/ckpoint/%s/ckpt" % (path_pre, infer_stamp_type)
        cmd = "python3 date/main.py --path_pre=%s --stamp_type=%s --agent_type=%s --episodes=%d --epochs=5 --topo_name=%s --train_start_index=%d  --synthesis_type=%s --path_type=%s --is_train=False --ckpt_path=%s" % (path_pre, stamp_type, scheme, infer_episodes, topo, train_start_index, synthesis_type, path_type, ckpt_path)
        print(cmd)
        os.system(cmd)

        util_file = open(path_pre + "outputs/log/%s/util.log" % (stamp_type))
        utils = list(map(float, util_file.readlines()))

        result_file = open(path_pre + "outputs/log/%s/maxutils.result" % (stamp_type), "w")
        for i in range(infer_episodes):
            maxutil = np.mean(np.array(utils[i * 5 : (i + 1) * 5]))
            print(maxutil, file=result_file)
        result_file.close()

''' para setting area '''
path_pre = os.getcwd().replace("lib", "")
time_stamp = "1116"             # prefix of the log file name
stamp_tail = ""                 # suffix of the log file name
topo = "Cer"                   # topology name
target = "train"             # chioce: converge, train, infer, failure
scheme = "DATE"                  # chioce: MDA (two-agent design), MSA (one-agent design)
epochs = 8000                   # total update steps for each TM

run(path_pre, scheme, epochs, topo)
