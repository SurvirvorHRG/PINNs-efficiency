# PINNs-efficiency

Physics-Informed Neural Networks (PINNs) have emerged as powerful tools for solving differential equations by embedding physical laws into the loss function of deep neural networks. However, their high computational cost remains a significant challenge, largely due to the inherent inefficiencies of traditional multilayer perceptron (MLP) architectures. To address this issue, alternative neural representations such as Kolmogorov–Arnold Networks (KAN), known in this context as Physics-Informed KANs (PIKANs), and Spiking Neural Networks (SNNs) have been explored. This study investigates the potential of these architectures to improve the efficiency of PINNs. Specifically, we focus on converting trained PIKANs into SNNs, furthermore we might explore an approach that combines PINNs with numerical solvers like the finite element method (FEM) for enhanced performance. Through these approaches, we aim to develop more computationally efficient PINN frameworks that retain accuracy while reducing training time and resource consumption.



# References
- [0] Qian  Zhang,  Chenxi  Wu,  Adar  Kahana,  Youngeun  Kim,  Yuhang  Li,  George  Em  Kar-niadakis,  and  Priyadarshini  Panda.   Artificial  to  spiking  neural  networks  conversion  forscientific machine learning, 2023
- [2] Yuhang Li, Shikuang Deng, Xin Dong, and Shi Gu.  Converting artificial neural networksto spiking neural networks via parameter calibration, 2022
- [3] Khemraj  Shukla,  Juan  Diego  Toscano,  Zhicheng  Wang,  Zongren  Zou,  and  George  EmKarniadakis.  A comprehensive and fair comparison between mlp and kan representationsfor differential equations and operator networks, 2024
- [4] [https://github.com/KindXiaoming/pykan](https://github.com/NeuromorphicProcessorProject/snn_toolbox)
- [5] https://github.com/KindXiaoming/pykan
- [6] https://github.com/Blealtan/efficient-kan


  ## Authors
  CELANIE Erwan
  Erraji Kenza
