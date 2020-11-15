# -*-coding:utf-8 -*-
'''
    Main file of the DATE system
'''

from drlAgent import *
from environment import Env
from socket import *
import sys,os,json

if not hasattr(sys, 'argv'):
    sys.argv  = ['']

SERVER_PORT = getattr(FLAGS, 'server_port')
SERVER_IP = getattr(FLAGS, 'server_ip')

IS_TRAIN = getattr(FLAGS, "is_train")
OFFLINE_FLAG = getattr(FLAGS, 'offline_flag')
ACTOR_LEARNING_RATE = getattr(FLAGS, 'learning_rate_actor')
CRITIC_LEARNING_RATE = getattr(FLAGS, 'learning_rate_critic')

GAMMA = getattr(FLAGS, 'gamma')
TAU = getattr(FLAGS, 'tau')
DELTA = getattr(FLAGS, 'delta')

EP_BEGIN = getattr(FLAGS, 'epsilon_begin')
EP_END = getattr(FLAGS, 'epsilon_end')

BUFFER_SIZE = getattr(FLAGS, 'size_buffer')
MINI_BATCH = getattr(FLAGS, 'mini_batch')

MAX_EPISODES = getattr(FLAGS, 'episodes')
MAX_EP_STEPS = getattr(FLAGS, 'epochs')

if getattr(FLAGS, 'stamp_type') == '':
    REAL_STAMP = str(datetime.datetime.now())
else:
    REAL_STAMP = getattr(FLAGS, 'stamp_type')
PATHPRE = getattr(FLAGS, 'path_pre')

AGENT_TYPE = getattr(FLAGS, "agent_type")

CKPT_PATH = getattr(FLAGS, "ckpt_path")
TOPO_NAME = getattr(FLAGS, "topo_name")
PATH_NUM = getattr(FLAGS, "path_num")
SYNT_TYPE = getattr(FLAGS, "synthesis_type")
PATH_TYPE = getattr(FLAGS, "path_type")
FAILURE_FLAG = getattr(FLAGS, "failure_flag")
START_INDEX = getattr(FLAGS, "train_start_index")

SESS_NUM = None
SESS_SRC = None
NUM_PATHS = None
AGENT_NUM = None
SESS_PATHS = None

initActions = []
def init_action(pathNumList):
    action = []
    for item in pathNumList:
        action += [round(1.0/item, 6) for i in range(item)]
    return action

def update_step(maxutil, sess_path_util, agents):
    sess_util_tmp = [{} for i in range(AGENT_NUM)]
    sess_util = [[] for i in range(AGENT_NUM)]
    maxsess_util = [[] for i in range(AGENT_NUM)]
    for i in range(SESS_NUM):
        for j in range(NUM_PATHS[i]):
            for k in range(len(SESS_PATHS[i][j])-1):
                enode1 = SESS_PATHS[i][j][k]
                enode2 = SESS_PATHS[i][j][k+1]
                id_tmp = str(enode1) + "," + str(enode2)
                if id_tmp not in sess_util_tmp[SESS_SRC[i]]:
                    sess_util_tmp[SESS_SRC[i]][id_tmp] = sess_path_util[i][j][k]
                    sess_util[SESS_SRC[i]].append(sess_path_util[i][j][k])
    
    # get maxsess_util
    for i in range(SESS_NUM):
        temp_sessmax = 0.
        for j in sess_path_util[i]:
            temp_sessmax = max(temp_sessmax, max(j))
        maxsess_util[SESS_SRC[i]].append(temp_sessmax)
    
    # calculate state and reward for each agent
    state_list = []
    reward_list = []
    for i in range(AGENT_NUM):
        if(agents[i] == None):
            state = None
            reward = None
        else:
            state = list(np.array(sess_util[i]) / maxutil)
            reward = - 0.05 * (np.mean(maxsess_util[i]) + DELTA / len(maxsess_util[i]) * maxutil)

        state_list.append(state)
        reward_list.append(reward)
        
    ret_c_t = []
    ret_c = []
    for i in range(len(agents)):
        if agents[i] != None:
            result = agents[i].predict(state_list[i], reward_list[i])
            ret_c_t.append(list(result))
        else:
            ret_c_t.append([])
    for i in range(SESS_NUM):
        ret_c += ret_c_t[SESS_SRC[i]][0:NUM_PATHS[i]]
        ret_c_t[SESS_SRC[i]] = ret_c_t[SESS_SRC[i]][NUM_PATHS[i]:]
    return ret_c

def init_multi_agent(globalSess):
    global SESS_NUM
    global SESS_SRC
    global NUM_PATHS
    global AGENT_NUM
    global SESS_PATHS
    env = Env(PATHPRE + "inputs/", TOPO_NAME, MAX_EPISODES, MAX_EP_STEPS, START_INDEX, IS_TRAIN, path_type = PATH_TYPE, path_num = PATH_NUM, synthesis_type = SYNT_TYPE)
    NODE_NUM, SESS_NUM, NUM_PATHS, SESS_PATHS = env.getInfo() # SESS_PATHS shows the nodes in each path of each session
    SESS_SRC = [SESS_PATHS[i][0][0] for i in range(SESS_NUM)]

    # init routing/scheduling policy
    agents = []
    AGENT_NUM = max(SESS_SRC) + 1 # here AGENT_NUM is not equal to the real valid "agent number"
    srcSessNum = [0] * AGENT_NUM
    srcPathNum = [0] * AGENT_NUM
    srcUtilNum = [0] * AGENT_NUM # sum util num for each src (sum util for each path)
    srcPaths = [[] for i in range(AGENT_NUM)]
    for i in range(len(SESS_SRC)):
        srcSessNum[SESS_SRC[i]] += 1
        srcPathNum[SESS_SRC[i]] += NUM_PATHS[i]
        srcPaths[SESS_SRC[i]].append(NUM_PATHS[i])
    
    #calculate srcUtilNum(unique)
    sess_util_tmp = [{} for i in range(AGENT_NUM)]
    for i in range(SESS_NUM):
        for j in range(NUM_PATHS[i]):
            for k in range(len(SESS_PATHS[i][j])-1):
                enode1 = SESS_PATHS[i][j][k]
                enode2 = SESS_PATHS[i][j][k+1]
                id_tmp = str(enode1) + "," + str(enode2)
                if id_tmp not in sess_util_tmp[SESS_SRC[i]]:
                    sess_util_tmp[SESS_SRC[i]][id_tmp] = 0
    for i in range(AGENT_NUM):
        srcUtilNum[i] = len(sess_util_tmp[i].values())
    
    # construct the distributed agents
    print("\nConstructing distributed agents ... \n")
    for i in range(AGENT_NUM):
        print("agent %d" % i)
        if (srcSessNum[i] > 0):
            dimState = srcUtilNum[i]
            dimAction = srcPathNum[i]
            agent = DrlAgent(globalSess, IS_TRAIN, dimState, dimAction, srcPaths[i], ACTOR_LEARNING_RATE, CRITIC_LEARNING_RATE, TAU, BUFFER_SIZE, MINI_BATCH, EP_BEGIN, EP_END, GAMMA, MAX_EP_STEPS)
        else:
            agent = None
        agents.append(agent)

    # parameters init   
    print("Running global_variables initializer ...")
    globalSess.run(tf.global_variables_initializer())
    
    # init target actor and critic para
    print("Building target network ...")
    for i in range(AGENT_NUM):
        if agents[i] != None: #valid agent
            agents[i].target_paras_init()
    
    # parameters restore
    mSaver = tf.train.Saver(tf.trainable_variables()) 
    if CKPT_PATH != None and CKPT_PATH != "":
        print("restore paramaters...")
        mSaver.restore(globalSess, CKPT_PATH)
    
    initActions = init_action(NUM_PATHS)
    return env, agents, initActions

def log_to_file(maxutil, fileUtilOut, netutilList, fileEdgeOut):
    print(maxutil, file=fileUtilOut)
    if fileEdgeOut != None:
        netutils = []
        for item in netutilList:
            netutils += item
        print(netutils, file=fileEdgeOut)

def init_output_file():
    dirLog = PATHPRE + "outputs/log/" + REAL_STAMP
    dirCkpoint = PATHPRE + "outputs/ckpoint/" + REAL_STAMP
    if not os.path.exists(dirLog):
        os.mkdir(dirLog)
    fileUtilOut = open(dirLog + '/util.log', 'w', 1)
    if IS_TRAIN:
        if not os.path.exists(dirCkpoint):
            os.mkdir(dirCkpoint)
    if not IS_TRAIN and MAX_EPISODES == 1:
        fileEdgeOut = open(dirLog + '/edge.log', 'w', 1)
    else:
        fileEdgeOut = None
    return dirLog, dirCkpoint, fileUtilOut, fileEdgeOut

def log_time_file(timeRecord, dirLog):
    print('\n' + REAL_STAMP)
    logfile = open(dirLog + "/runtime.log", 'w')
    runtimeType = ["inital time", "training time", "running time"]
    timeRecordPair = [[timeRecord[0], timeRecord[1]], 
                    [timeRecord[1], timeRecord[2]], 
                    [timeRecord[0], timeRecord[2]]]
    for t in range(len(timeRecordPair)):
        start_time = timeRecordPair[t][0]
        end_time = timeRecordPair[t][1]
        interval = int((end_time-start_time)*1000)
        timeMs = interval%1000
        timeS = int(interval/1000)%60
        timeMin = int((interval/1000-timeS)/60)%60
        timeH = int(interval/1000)/3600
        runtime = "%dh-%dmin-%ds-%dms" % (timeH, timeMin, timeS, timeMs)
        print("%s: %s" % (runtimeType[t], runtime))
        logfile.write("%s: %s\n" % (runtimeType[t], runtime))
    logfile.close()

def parse_msg(msg):
    env_msg = msg.split(';')[1]
    env_states = json.loads(env_msg)
    max_util = env_states['max_util']
    sess_path_util = env_states['sess_path_util']
    return max_util, sess_path_util, None

if __name__ == "__main__":
    '''initial part'''
    print("\n----Information list----")
    print("agent_type: %s" % (AGENT_TYPE))
    print("stamp_type: %s" % (REAL_STAMP))
    timeRecord = []
    timeRecord.append(time.time())
    globalSess = tf.Session()
    env, agents, initActions = init_multi_agent(globalSess)
    timeRecord.append(time.time())

    update_count = 0
    routing = initActions
    if OFFLINE_FLAG:
        dirLog, dirCkpoint, fileUtilOut, fileEdgeOut = init_output_file()
        for _ in range(MAX_EPISODES * MAX_EP_STEPS):
            maxutil, sess_path_util, netutil = env.update(routing)
            log_to_file(maxutil, fileUtilOut, netutil, fileEdgeOut)
            routing = update_step(maxutil, sess_path_util, agents)
            if update_count % 8000 == 0:
                print("update_count:", update_count, "  max_util:", maxutil)
            update_count += 1
        timeRecord.append(time.time())
        fileUtilOut.close()
        if fileEdgeOut != None:
            fileEdgeOut.close()
        log_time_file(timeRecord, dirLog)
    else:
        server_socket = socket()
        server_socket.bind((SERVER_IP, SERVER_PORT))
        print("listen ...")
        server_socket.listen(1)
        tcpSocket, addr = server_socket.accept()
        print("Connected with controller successfully!")
        blockSize = 1024
        BUFSIZE = 1025
        while True:
            msgTotalLen = 0
            msgRecvLen = 0
            msg = ""
            finish_flag = False
            # recv environment state
            while True:
                datarecv = tcpSocket.recv(BUFSIZE).decode()
                if len(datarecv) > 0:
                    if msgTotalLen == 0:
                        totalLenStr = (datarecv.split(';'))[0]
                        msgTotalLen = int(totalLenStr) + len(totalLenStr) + 1 #1 is the length of ';'
                        if msgTotalLen == 2: # stop signal
                            print("simulation is over!")
                            finish_flag = True
                            break
                    msgRecvLen += len(datarecv)
                    msg += datarecv
                    if msgRecvLen == msgTotalLen: 
                        break
            
            if finish_flag:
                server_socket.close()
                break
            
            # calculate the action
            maxutil, sess_path_util, netutil = parse_msg(msg)
            routing = update_step(maxutil, sess_path_util, agents)
            # if update_count % 1000 == 0:
            #     print("update_count:", update_count, "  max_util:", maxutil)
            update_count += 1
            
            routing = [round(item, 4) for item in routing]
            # msg = json.dumps(str(routing))
            msg = str(routing)
            msg = str(len(msg)) + ';' + msg

            msgTotalLen = len(msg)
            blockNum = int((msgTotalLen + blockSize - 1)/blockSize)
            for i in range(blockNum):
                data = msg[i*blockSize : i*blockSize + blockSize]
                tcpSocket.send(data.encode())
    
    # store global variables
    if IS_TRAIN:
        print("saving checkpoint...")
        mSaver = tf.train.Saver(tf.global_variables())        
        mSaver.save(globalSess, dirCkpoint + "/ckpt")
        print("save checkpoint over")
    
    
