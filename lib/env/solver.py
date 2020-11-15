'''
    Description: mcf solver based on Gurobi
'''

from gurobipy import *

# semi-oblivious routing; OR with path limitations
def sorsolver(nodeNum, demNum, totalPathNum, pathSet, pathRates, cMatrix):
    model = Model('netflow')
    model.setParam("OutputFlag", 0)

    # 1) generate path variable constraints
    pathVarNum = totalPathNum
    Maps = [[[] for i in range(nodeNum)] for i in range(nodeNum)]
    pathVarID = 0
    for i in range(demNum):
        for j in range(len(pathSet[i])):
            pathlen = len(pathSet[i][j])
            for k in range(pathlen - 1):
                Maps[pathSet[i][j][k]][pathSet[i][j][k + 1]].append(pathVarID)
            pathVarID += 1

    # 2) add capacaity and objective constraints
    sum0 = 0
    sum1 = 0
    sum2 = 0
    fpath = []
    for i in range(pathVarNum):
        fpath.append(model.addVar(0, GRB.INFINITY, 0, GRB.CONTINUOUS, "path"))
    phi = model.addVar(0, GRB.INFINITY, 0, GRB.CONTINUOUS, "phi")

    pathVarID = 0
    for h in range(demNum):
        sum0 = 0
        sum1 = 0
        for k in range(len(pathSet[h])):
            sum0 += fpath[pathVarID]
            sum1 = fpath[pathVarID]
            pathVarID += 1
            model.addConstr(sum1 >= 0)
        model.addConstr(sum0 == 1)
    
    for i in range(nodeNum):
        for j in range(nodeNum):
            tmp = len(Maps[i][j])
            if tmp == 0:
                continue
            sum2 = 0
            for k in range(tmp):
                sum2 += fpath[Maps[i][j][k]] * pathRates[Maps[i][j][k]]
            
            model.addConstr(sum2 <= phi*cMatrix[i][j])

    # 3) set objective and solve the problem
    model.setObjective(phi, GRB.MINIMIZE)
    model.optimize()
    ratios = []
    if model.status == GRB.Status.OPTIMAL:
        pathVarID = 0
        for h in range(demNum):
            for k in range(len(pathSet[h])):
                splitRatio = fpath[pathVarID].getAttr(GRB.Attr.X)
                ratios.append(splitRatio)
                pathVarID += 1
    else:
        print("\n!!!!!!!!!!! No solution !!!!!!!!!!!!!!\n")
                
    return ratios, model.objVal
