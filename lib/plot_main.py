import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

LOG_PATH = os.getcwd().replace("lib", "") + "outputs/"

def read_file(filename, start_index, end_index):
    infile = open(filename, "r")
    ret = []
    for i in infile.readlines()[start_index:end_index]:
        ret.append(float(i.strip()))
    infile.close()
    return ret

def single(topo, start, synthesis_type = "", DATEinfo = []):
    length = 12000
    filename = LOG_PATH + "objvals/" + topo + "_mcf_obj_vals%s.txt" % (synthesis_type)
    mcf_ret = read_file(filename, start, start+1)[0]

    res = []
    for stamp_type in DATEinfo:
        filename = LOG_PATH + "log/" + stamp_type + "/util.log"
        date_ret = read_file(filename, 0, length)
        res.append([item/mcf_ret for item in date_ret])

    outfile = open("./dat/%s_converge%s.dat" % (topo, synthesis_type), 'w')
    for i in range(length):
        for j in range(len(DATEinfo)):
            outfile.write(str(res[j][i]) + ' ')
        outfile.write('\n')
    outfile.close()

def infer(topo, schemeList, start, end, synthesis_type = "", DATEinfo = []):
    if "MCF" not in schemeList or len(schemeList) < 2:
        return
    utils = {}
    for scheme in schemeList:
        if scheme[0:4] == "DATE":
            stamp_type = DATEinfo[int(scheme[-1])-1]
            filename = LOG_PATH + "log/" + stamp_type + "/maxutils.result"
        else:
            filename = LOG_PATH + "objvals/" + topo + "_" + scheme.lower() + "_obj_vals%s.txt" % (synthesis_type)
        ret = read_file(filename, start, end)
        utils[scheme] = ret
        print(scheme, len(ret))


    schemeList.remove('MCF')
    length = len(utils["MCF"])
    for scheme in schemeList:
        result = [utils[scheme][i]/utils["MCF"][i] for i in range(length)]
        plt.plot([i for i in range(length)], result, linewidth=1.5, label=scheme)
    plt.xlabel("Time")
    plt.ylabel("Performance Ratio")
    plt.legend(fontsize=6)
    plt.savefig(LOG_PATH + "figure/%s_eff_normal%s.png" % (topo, synthesis_type))
    print(LOG_PATH + "figure/%s_eff_normal%s.png" % (topo, synthesis_type))
    plt.clf()

    
    filedat = []
    for scheme in schemeList:
        result = [utils[scheme][i]/utils["MCF"][i] for i in range(length)]
        result.sort()
        filedat.append(result)
        plt.plot(result, [(i+1)/length for i in range(length)], linewidth=0.5, label=scheme)
    plt.xlabel("Performance Ratio")
    plt.ylabel("CDF")
    plt.legend(fontsize=6)
    plt.savefig(LOG_PATH + "figure/%s_eff_normal%s_cdf.png" % (topo, synthesis_type))
    print(LOG_PATH + "figure/%s_eff_normal%s_cdf.png" % (topo, synthesis_type))
    plt.clf()

def exp(topo, schemeList, start, end, Schemeinfo = []):
    utils = {}
    for i in range(len(schemeList)):
        scheme = schemeList[i]
        stamp_type = Schemeinfo[i]
        filename = LOG_PATH + "log/" + stamp_type + "/maxutil.log"
        ret = read_file(filename, start, end)
        utils[scheme] = ret
        print(scheme, len(ret))

    stamp_type = "%s_exp_eff" % (topo)
    length = end - start
    for scheme in schemeList:
        result = utils[scheme]
        plt.plot([i for i in range(length)], result, linewidth=0.5, label=scheme)

    plt.xlabel("Time")
    plt.ylabel("Max. Edge Util.")
    plt.legend(fontsize=6)
    plt.savefig(LOG_PATH + "figure/%s.png" % (stamp_type))
    print(LOG_PATH + "figure/%s.png" % (stamp_type))
    plt.clf()

    for scheme in schemeList:
        result = utils[scheme]
        result.sort()
        utils[scheme] = result
        plt.plot(result, [(i+1)/length for i in range(length)], linewidth=0.5, label=scheme)

    plt.xlabel("Max. Edge Util.")
    plt.ylabel("CDF")
    plt.legend(fontsize=6)
    plt.savefig(LOG_PATH + "figure/%s_cdf.png" % (stamp_type))
    print(LOG_PATH + "figure/%s_cdf.png" % (stamp_type))
    plt.clf()

line = "-----------normal------------"
## Cer eff normal
# DATEinfo = ["1114_Cer_infer_DATE_p3_exp_epoch8000"]
# infer("Cer", ["MCF", "LB", "OR", "SMORE", "SP", "DATE1"], 288*3, 288*7, synthesis_type = "_exp", DATEinfo = DATEinfo)


line = "-------------converge------------"
## Abi converge ""
# DATEinfo = ["0903_Abi_single_p3", "0905_Abi_single_p3_B9000", "0905_Abi_single_p3_eps1000", "0905_Abi_single_p3_eps5000"]
# single("Abi", 0, synthesis_type = "", DATEinfo = DATEinfo)

line = "-------------design------------"
## Abi design ""
# DATEinfo = ["0902_Abi_infer_p3", "0907_Abi_infer_p3_fit1dayepi96", "0906_Abi_infer_p3_fit3dayepi24", "0907_Abi_infer_p3_nofit", "0904_Abi_infer_p2", "0906_Abi_infer_p4"]
# DRLTEinfo = [""]
# infer("Abi", ["MCF", "DATE1", "DATE2", "DATE4", "DATE5", "DATE6"], 288*3, 288*7, synthesis_type = "", DATEinfo = DATEinfo, DRLTEinfo = DRLTEinfo)

line = "-------------exp eff------------"
## Cer exp eff ""
Schemeinfo = ["1115_Cer_LB", "1115_Cer_OR", "1115_Cer_SMORE", "1115_Cer_SP", "1115_Cer_DATE"]
exp("Cer", ["LB", "OR", "SMORE", "SP", "DATE"], 10, 290, Schemeinfo = Schemeinfo)
