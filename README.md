# PINNs-efficiency

Physics-informed neural networks (PINNs) have emerged as powerful tools for solving differential equations by embedding physical laws in the loss function of deep neural networks. However, their high computational cost remains a significant challenge, largely due to the inherent inefficiencies of traditional multilayer perceptron (MLP) architectures. To address this issue, alternative neural representations such as Kolmogorov-Arnold Networks (KANs), known in this context as Physics-Informed KANs (PIKANs), and Separable Physics-Informed Neural Networks (SPINNs) have been explored while these architectures provide notable increase in accuracy they remain sensitive to high-dimensional PDEs. Therefore, using a recent algorithm that samples dimensions involved in the training process referred as stochastic dimension gradient descent (SDGD) we provide a study that investigates the potential of these architectures to improve the efficiency and computational cost of PINNs for high-dimensional PDEs. In particular, we focus on the analysis of this new optimisation technique for training PINNs and its variants such as SPINNs and PIKANs.
Through these approaches, we aim to develop more computationally efficient PINNs frameworks that maintain accuracy while reducing training time and resources consumption.



- [1] Zheyuan Hu, Khemraj Shukla, George Em Karniadakis, and Kenji Kawaguchi. Tackling the curseof dimensionality with physics-informed neural networks.Neural Networks, page 106369, 2024.
- [2] Junwoo  Cho,  Seungtae  Nam,  Hyunmo  Yang,  Seok-Bae  Yun,  Youngjoon  Hong,  and  EunbyungPark.  Separable physics-informed neural networks.Advances in Neural Information ProcessingSystems, 2023.
- [4] https://github.com/Blealtan/efficient-kan
- [3] Khemraj  Shukla,  Juan  Diego  Toscano,  Zhicheng  Wang,  Zongren  Zou,  and  George  EmKarniadakis.  A comprehensive and fair comparison between mlp and kan representationsfor differential equations and operator networks, 2024
- [5] https://github.com/KindXiaoming/pykan
- [6] https://github.com/Blealtan/efficient-kan


  ## Authors
  - CELANIE Erwan
  - Erraji Kenza
  
