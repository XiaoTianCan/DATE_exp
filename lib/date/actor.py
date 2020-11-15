"""
	Actor of Deep Deterministic policy gradient
"""
import tflearn
import tensorflow as tf


class ActorNetwork:
    def __init__(self, sess, dim_state, dim_action, bound_action, learning_rate, tau, num_path):
        self.__sess = sess
        self.__dim_s = dim_state
        self.__dim_a = dim_action
        self.__max_a = bound_action
        self.__learning_rate = learning_rate
        self.__num_path = num_path
        self.__tau = tau

        # performance network
        cur_para_num = len(tf.trainable_variables())
        self.__input, self.__out, self.__out_scaled = self.buildNetwork()
        self.__paras = tf.trainable_variables()[cur_para_num:]

        # Target network
        self.__target_input, self.__target_out, self.__target_out_scaled = self.buildNetwork()
        self.__target_paras = tf.trainable_variables()[(len(self.__paras) + cur_para_num):]

        # update parameters of target network
        self.__ops_update_target = []
        for i in range(len(self.__target_paras)):
            val = tf.add(tf.multiply(self.__paras[i], self.__tau), tf.multiply(self.__target_paras[i], 1. - self.__tau))
            op = self.__target_paras[i].assign(val)
            self.__ops_update_target.append(op)

        # provided by Critic
        self.__gradient_action = tf.placeholder(tf.float32, [None, self.__dim_a])

        # calculate gradients
        self.__actor_gradients = tf.gradients(self.__out_scaled, self.__paras, -self.__gradient_action)

        self.__optimize = tf.train.AdamOptimizer(self.__learning_rate) \
            .apply_gradients(zip(self.__actor_gradients, self.__paras))

        self.__num_trainable_vars = len(self.__paras) + len(self.__target_paras)

    @property
    def session(self):
        return self.__sess

    @property
    def num_trainable_vars(self):
        return self.__num_trainable_vars

    @property
    def dim_state(self):
        return self.__dim_s

    @property
    def dim_action(self):
        return self.__dim_a

    def buildNetwork(self):
        _inputs = tf.placeholder(tf.float32, [None, self.__dim_s])
        net = _inputs

        net = tf.contrib.layers.fully_connected(net, 64, activation_fn=tf.nn.leaky_relu)
        net = tf.contrib.layers.fully_connected(net, 32, activation_fn=tf.nn.leaky_relu)
        w_init = tflearn.initializations.uniform(minval=-3e-3, maxval=3e-3)

        out_vec = []
        for i in self.__num_path:
            out = tf.contrib.layers.fully_connected(net, i, activation_fn=tf.nn.softmax, weights_initializer=w_init)
            out_vec.append(out)
        out = tf.concat([i for i in out_vec], axis=1)

        out_scaled = tf.multiply(out, self.__max_a)
        return _inputs, out, out_scaled

    def train(self, inputs, gradient_action):
        self.__sess.run(self.__optimize, feed_dict={
            self.__input: inputs,
            self.__gradient_action: gradient_action
        })

    def predict(self, inputs):
        return self.__sess.run(self.__out_scaled, feed_dict={
            self.__input: inputs
        })

    def predict_target(self, inputs):
        return self.__sess.run(self.__target_out_scaled, feed_dict={
            self.__target_input: inputs
        })

    def update_target_paras(self):
        self.__sess.run(self.__ops_update_target)
