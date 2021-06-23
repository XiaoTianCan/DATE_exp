# Description
Distributed and Adaptive Traffic Engineering (DATE) with Deep Reinforcement Learning (implemented on Mininet). 

# Getting Started
### Installation
ubuntu16.04 python3.5
```
apt-get update
pip3 install numpy==1.16.0
pip3 install tensorflow==1.8.0
pip3 install pandas
pip3 install scipy matplotlib h5py
pip3 install tflearn
```
Others that need to be installed: Gurobi, Ryu, and Mininet
### Run codes
clone the codes; go to lib/

To train the DATE system and save the learned paras.
```
python3 train_date_main.py
```

To run the system in Mininet
```
python3 run_main.py
```

To show the results in figures
```
python3 plot_main.py
```

### Parameter setting
set paras. in lib/train_date_main.py or lib/run_main.py

### Results
DATE: outputs/log/

Some baselines: outputs/objvals/

# Paper
Nan Geng, Mingwei Xu, Yuan Yang, Chenyi Liu, Jiahai Yang, Qi Li, and Shize Zhang, "Distributed and Adaptive Traffic Engineering with Deep Reinforcement Learning" (IWQoS 2021)



