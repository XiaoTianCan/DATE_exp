"""
	Do explorations
"""
import numpy as np

class Explorer:
    def __init__(self, epsilon_begin, epsilon_end, max_epoch, dim_act, num_path, seed):
        np.random.seed(seed)
        self.__ep = epsilon_begin
        self.__ep_decay = pow(epsilon_end, 1/max_epoch)
        self.__max_epoch = max_epoch
        self.__step_num = 0
        self.__num_paths = num_path
        self.__dim_act = dim_act
    
    # The function is to make sum(w_p) == 1.0 for each demand path weight w_p
    def convert_action(self, action):
        act = np.split(action, np.cumsum(self.__num_paths))[:-1]
        for idx, val in enumerate(act):
            if not np.any(val):
                act[idx][0] = 1.
                continue
            act[idx] = val / sum(val.flatten())
        ret = []
        for ary in act:
            for val in ary.flatten():
                ret.append(val.item())
        return ret

    def cut_convert_act(self, act):
        act = np.clip(act, 0.0001, 2.)
        act = self.convert_action(act)
        return act

    def get_act(self, action):
        self.__ep *= self.__ep_decay
        self.__step_num += 1
        if self.__step_num >= self.__max_epoch - 3:
            self.__ep = 0.0
        
        tmp = (2. * np.random.random(self.__dim_act) - 1.)
        act = action + self.__ep * tmp
        return self.cut_convert_act(act)

    def reset_ep(self, ep):
        self.__ep = ep
        self.__step_num = 0

