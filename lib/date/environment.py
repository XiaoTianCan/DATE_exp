#!/usr/bin/python3
# -*- coding: UTF-8 -*-

'''
    Environment for offline training and test. 
'''

import copy
import pickle
import numpy as np
import time
import multiprocessing as mp


class Env:
    def __init__(self, infile_prefix, topo_name, episode, epoch, start_index, train_flag, path_type = "racke", path_num = 3, synthesis_type = ""):
        self.__topofile = infile_prefix + "topology/" + topo_name + "_topo.txt"
        if path_type == "racke":
            self.__pathfile = infile_prefix + "pathset/" + topo_name + "_path" + str(path_num) + "_" + path_type + ".txt"
        else:
            self.__pathfile = infile_prefix + "pathset/" + topo_name + "_paths_" + path_type + ".txt"
        
        if train_flag and episode == 1:
            traffic_type = "original"
        elif train_flag:
            traffic_type = "fitting"
        else:
            traffic_type = "original"
        if synthesis_type != "":
            synthesis_type = "_" + synthesis_type
        self.__ratefile = infile_prefix + "traffic/" + traffic_type + "/" + topo_name + "_TMset%s.txt" % (synthesis_type)

        
        # store topo info
        self.__toponame = topo_name
        self.__nodenum = 0
        self.__linknum = 0
        self.__linkset = []
        self.__edgemap = []
        self.__wMatrix = []
        self.__cMatrix = []
        self.__MAXWEIGHT = 99999


        # store self.__demands
        self.__demnum = 0
        self.__demands = []

        # store paths and rates
        self.__totalpathnum = 0
        self.__totalTMnum = 0
        self.__candidatepaths = []
        self.__candidatepathspair = []
        self.__demrate = []
        self.__demrates = []
        self.__pathnum = []

        # train
        self.__start_index = start_index
        self.__epoch = epoch
        self.__episode = -1
        self.__link_ind = 0
        self.__rate_ind = 0
        self.__updatenum = 0
        
        self.get_topo()
        self.get_demands()
        self.get_paths()
        self.get_demrates()

    def get_topo(self):
        file = open(self.__topofile)
        lines = file.readlines()
        file.close()
        lineList = lines[0].strip().split()
        self.__nodenum = int(lineList[0])
        self.__linknum = int(lineList[1])
        for i in range(self.__nodenum):
            self.__wMatrix.append([])
            self.__cMatrix.append([])
            for j in range(self.__nodenum):
                if i == j:
                    self.__wMatrix[i].append(0)
                else:
                    self.__wMatrix[i].append(self.__MAXWEIGHT)
                self.__cMatrix[i].append(0)

        for i in range(1, self.__linknum+1):
            lineList = lines[i].strip().split()
            left = int(lineList[0]) - 1
            right = int(lineList[1]) - 1
            capa = float(lineList[3])
            weight = int(lineList[2])
            self.__linkset.append([left, right, weight, capa])
            self.__wMatrix[left][right] = weight
            self.__wMatrix[right][left] = weight
            self.__cMatrix[left][right] = capa 
            self.__cMatrix[right][left] = capa

    def get_demands(self):
        self.__demnum = self.__nodenum*(self.__nodenum - 1)
        for src in range(self.__nodenum):
            for dst in range(self.__nodenum):
                if src == dst:
                    continue
                self.__demands.append([src,dst])

    def get_paths(self):
        file = open(self.__pathfile)
        lines = file.readlines()
        file.close()
        demId = 0
        candidatepaths = []
        self.__totalpathnum = len(lines)
        for i in range(self.__totalpathnum):
            lineList = lines[i].strip().split()
            path = list(map(int, lineList))
            if self.__demands[demId][0] != path[0] or self.__demands[demId][1] != path[-1]:
                self.__candidatepaths.append(candidatepaths)
                demId += 1
                candidatepaths = []
            candidatepaths.append(path)
        self.__candidatepaths.append(candidatepaths)
        for i in range(self.__demnum):
            self.__pathnum.append(len(self.__candidatepaths[i]))

        for i in range(self.__nodenum):
            self.__edgemap.append([])
            for j in range(self.__nodenum):
                self.__edgemap[i].append(0)
        for i in range(self.__demnum):
            self.__candidatepathspair.append([])
            for j in range(self.__pathnum[i]):
                self.__candidatepathspair[i].append([])
                for k in range(len(self.__candidatepaths[i][j])-1):
                    enode1 = self.__candidatepaths[i][j][k]
                    enode2 = self.__candidatepaths[i][j][k+1]
                    self.__edgemap[enode1][enode2] = 1
                    self.__candidatepathspair[i][j].append((enode1, enode2))

    def get_demrates(self):
        file = open(self.__ratefile)
        lines = file.readlines()
        file.close()
        self.__totalTMnum = len(lines)
        for i in range(self.__totalTMnum):
            lineList = lines[i].strip().split(',')
            rates = list(map(float, lineList))
            self.__demrates.append(rates)

    def getFlowMap(self, action):
        if action == []:
            for item in self.__pathnum:
                action += [round(1.0/item, 6) for i in range(item)]
        flowmap = []
        subrates = []
        count = 0
        # get split rates
        for i in range(self.__demnum):
            subrates.append([])
            for j in range(self.__pathnum[i]):
                tmp = 0
                if j == self.__pathnum[i] - 1:
                    tmp = self.__demrate[i] - sum(subrates[i])
                else:
                    tmp = self.__demrate[i]*action[count]
                count += 1
                subrates[i].append(tmp)
        # get flowmap
        for i in range(self.__nodenum):
            flowmap.append([])
            for j in range(self.__nodenum):
                flowmap[i].append(0.0)

        for i in range(self.__demnum): 
            for j in range(self.__pathnum[i]):
                for k in range(len(self.__candidatepaths[i][j])-1):
                    enode1 = self.__candidatepaths[i][j][k]
                    enode2 = self.__candidatepaths[i][j][k+1]
                    flowmap[enode1][enode2] += subrates[i][j]

        return flowmap


    def getUtil(self, flowmap):
        dempathutil = []
        for i in range(self.__demnum): 
            dempathutil.append([])
            for j in range(self.__pathnum[i]):
                pathutil = []
                for k in range(len(self.__candidatepaths[i][j])-1):
                    enode1 = self.__candidatepaths[i][j][k]
                    enode2 = self.__candidatepaths[i][j][k+1]
                    pathutil.append(round(flowmap[enode1][enode2]/self.__cMatrix[enode1][enode2], 4))
                dempathutil[i].append(pathutil)
        netutil = []
        for i in range(self.__nodenum):
            for j in range(self.__nodenum):
                if self.__edgemap[i][j] != 0:
                    netutil.append(round(flowmap[i][j]/self.__cMatrix[i][j], 4))
        maxutil = max(netutil)
        return round(maxutil, 4), dempathutil, netutil

    def update(self, action):
        if self.__updatenum % self.__epoch == 0 and self.__updatenum >= 0:
            self.__episode += 1
            self.getRates()
        
        flowmap = self.getFlowMap(action)
        maxutil, dempathutil, netutil = self.getUtil(flowmap)
        self.__updatenum += 1
        
        return maxutil, dempathutil, netutil

    def getRates(self):
        rate_num = len(self.__demrates)
        self.__demrate = self.__demrates[(self.__episode + self.__start_index) % rate_num]
    
    def getInfo(self):
        return self.__nodenum, self.__demnum, self.__pathnum, self.__candidatepaths

    def showInfo(self):
        print("--------------------------")
        print("----detail information----")
        print("topology:%s" % self.__toponame)
        print("node num:%d" % self.__nodenum)
        print("demand num:%d" % self.__demnum)
        print("path num:", self.__pathnum)
        print("--------------------------")
