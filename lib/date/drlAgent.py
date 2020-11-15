'''
    DRL agent class
'''

import tensorflow as tf
from actor import ActorNetwork
from critic import CriticNetwork
from replaybuffer import ReplayBuffer
from explorer import Explorer
from flag import FLAGS
import time
import numpy as np

class DrlAgent:
    def __init__(self, sess, is_train, dim_state, dim_action, num_paths, actor_learn_rate, critic_learn_rate, tau, buffer_size, mini_batch, ep_begin, epsilon_end, gamma, max_epoch, seed = 66):
        self.__is_train = is_train
        self.__dim_state = dim_state
        self.__dim_action = dim_action
        self.__mini_batch = mini_batch
        self.__ep_begin = ep_begin
        self.__gamma = gamma
        self.__max_epoch = max_epoch

        self.__actor = ActorNetwork(sess, dim_state, dim_action, 1.0,
                                    actor_learn_rate, tau, num_paths)
        self.__critic = CriticNetwork(sess, dim_state, dim_action,
                                      critic_learn_rate, tau)
                                      
        self.__replay = ReplayBuffer(buffer_size, seed)

        self.__explorer = Explorer(ep_begin, epsilon_end, max_epoch, dim_action, num_paths, seed)
        
        self.__state_curt = np.zeros(dim_state)
        self.__action_curt = self.__explorer.convert_action(np.ones(dim_action))
        
        self.__episode = 0
        self.__step = 0
    
    def target_paras_init(self):
        self.__actor.update_target_paras()
        self.__critic.update_target_paras()
            
    def predict(self, state, reward):
        action_original = self.__actor.predict([state])[0]
        if not self.__is_train:
            return action_original

        action = self.__explorer.get_act(action_original)
        self.__replay.add(self.__state_curt, self.__action_curt, reward, state)
        self.__state_curt = state
        self.__action_curt = action
        
        if len(self.__replay) > self.__mini_batch:
            self.train()
        
        self.__step += 1
        if self.__step >= self.__max_epoch:
            self.__step = 0
            self.__episode += 1
            self.__explorer.reset_ep(self.__ep_begin)
        return action

    def train(self):
        batch_state, batch_action, batch_reward, batch_state_next = self.__replay.sample_batch(self.__mini_batch)
        weights = [1.0]*self.__mini_batch
        weights = np.expand_dims(weights, axis=1)
        target_q = self.__critic.predict_target(
            batch_state_next, self.__actor.predict_target(batch_state_next))
        value_q = self.__critic.predict(batch_state, batch_action)

        batch_y = []
        batch_error = []
        for k in range(len(batch_reward)):
            target_y = batch_reward[k] + self.__gamma * target_q[k]
            batch_error.append(abs(target_y - value_q[k]))
            batch_y.append(target_y)

        predicted_q, _ = self.__critic.train(batch_state, batch_action, batch_y, weights)
        a_outs = self.__actor.predict(batch_state)
        grads = self.__critic.calculate_gradients(batch_state, a_outs)
        weighted_grads = weights * grads[0]
        self.__actor.train(batch_state, weighted_grads)
        self.__actor.update_target_paras()
        self.__critic.update_target_paras()