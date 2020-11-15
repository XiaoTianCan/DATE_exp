import tensorflow as tf
import os

flags = tf.app.flags
FLAGS = flags.FLAGS

flags.DEFINE_integer('server_port', '50003', 'remote server port')
flags.DEFINE_string('server_ip', '127.0.0.1', 'remote server ip address')

flags.DEFINE_string("stamp_type", "", "the stamp style for the name of log directory")
flags.DEFINE_string("agent_type", None, "the TE scheme name")

flags.DEFINE_string('path_pre', "/home", 'the home path of the project')
flags.DEFINE_string("ckpt_path", None, "the checkpoint path, None means not using checkpoints to initialize the paramaters")

flags.DEFINE_string("topo_name", None, "input topo name")
flags.DEFINE_integer("path_num", 3, "the number of candidate paths for each demand")
flags.DEFINE_string("synthesis_type", "", "synthesis_type")
flags.DEFINE_string("path_type", "racke", "the number of candidate paths for each demand")
flags.DEFINE_integer("failure_flag", 0, "failure_flag")
flags.DEFINE_integer("train_start_index", 0, "the start index of input file for training")

flags.DEFINE_boolean("is_train", True, "a parameter for multi_agent mode, False->inference")
flags.DEFINE_boolean('offline_flag', True, 'offline simulation flag')

flags.DEFINE_integer('size_buffer', 300, "the size of replay buffer")
flags.DEFINE_integer('mini_batch', 32, "size of mini batch")

flags.DEFINE_integer('episodes', -1, "training episode")
flags.DEFINE_integer('epochs', 6000, "training epochs for each episode")

flags.DEFINE_float('epsilon_begin', 1., "the begin value of epsilon random")
flags.DEFINE_float('epsilon_end', 0.05, "the end value of epsilon random")

flags.DEFINE_float('learning_rate_actor', 0.0001, "learning rate for actor network")
flags.DEFINE_float('learning_rate_critic', 0.001, "learning rate for critic network")

flags.DEFINE_float('gamma', 0.99, "discount value for reward")
flags.DEFINE_float('tau', 0.001, "tau for target network update")
flags.DEFINE_float('delta', 50, 'trade off in the reward function')