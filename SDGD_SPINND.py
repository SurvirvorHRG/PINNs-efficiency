import torch
import torch.nn as nn
import numpy as np
import argparse
from tqdm import tqdm
import pandas as pd
from typing import Sequence
from torch.func import jvp

parser = argparse.ArgumentParser(description='PINN Training')
parser.add_argument('--SEED', type=int, default=0)
parser.add_argument('--dim', type=int, default=3) # dimension of the problem.
parser.add_argument('--dataset', type=str, default="Poisson")
parser.add_argument('--device', type=str, default="cuda")
parser.add_argument('--epochs', type=int, default=1000) # Adam epochs
parser.add_argument('--lr', type=float, default=1e-3) # Adam lr
parser.add_argument('--PINN_h', type=int, default=64) # width of PINN
parser.add_argument('--PINN_L', type=int, default=4) # depth of PINN
parser.add_argument('--save_loss', type=bool, default=True) # save the optimization trajectory?
parser.add_argument('--use_sch', type=int, default=1) # use scheduler?
parser.add_argument('--N_f', type=int, default=int(1000)) # num of residual points
parser.add_argument('--N_test', type=int, default=int(20000)) # num of test points
parser.add_argument('--x_radius', type=float, default=1)
parser.add_argument('--method', type=int, default=3)
parser.add_argument('--batch_size', type=int, default=1)
args = parser.parse_args()
print(args)

device = torch.device(args.device)
torch.manual_seed(args.SEED)
torch.cuda.manual_seed(args.SEED)
np.random.seed(args.SEED)
assert args.dataset == "Poisson"

c = np.random.randn(1, args.dim - 1)
const_2 = 1
def load_data_TwoBody_Poisson(d):
    args.input_dim = d
    args.output_dim = 1
    def func_u(x):
        temp =  args.x_radius**2 - np.sum(x**2, 1)
        temp2 = c * np.sin(x[:, :-1] + const_2 * np.cos(x[:, 1:]) + x[:, 1:] * np.cos(x[:, :-1]))
        temp2 = np.sum(temp2, 1)
        return temp * temp2

    N_test = args.N_test

    x = np.random.randn(N_test, d)
    r = np.random.rand(N_test, 1) * args.x_radius
    x = x / np.linalg.norm(x, axis=1, keepdims=True) * r
    u = func_u(x)
    return x, u

x, u = load_data_TwoBody_Poisson(d=args.dim)
print(x.shape, u.shape)
print(u.mean(), u.std())


class SPINN_D(nn.Module):
    def __init__(self, features, input_dims=args.dim):
        """
        Args:
            features (list or tuple): The layer sizes for each independent network. 
                                      For example, [hidden1, hidden2, ..., hiddenN]
            input_dims (int): The number of independent input dimensions.
        """
        super().__init__()
        self.features = features
        self.input_dims = input_dims
        
        # Create a subnetwork for each dimension
        self.networks = nn.ModuleList([
            self._build_network() for _ in range(input_dims)
        ])
        
        # Create a combine layer for each time we add another dimension.
        # Each combine layer takes a concatenated input of size 2*features[-1] and reduces it to features[-1]
        self.combine_layers = nn.ModuleList([
            nn.Linear(features[-1] * 2, features[-1]) for _ in range(input_dims - 1)
        ])
        
        # Final layer that outputs a single value.
        self.final_layer = nn.Linear(features[-1], 1)
        self.activation = nn.Tanh()

    def _build_network(self):
        layers = []
        # The first layer expects an input of size 1 (each individual input dimension is assumed to be scalar)
        layers.append(nn.Linear(1, self.features[0]))
        layers.append(nn.Tanh())
        
        for i in range(len(self.features) - 2):
            layers.append(nn.Linear(self.features[i], self.features[i + 1]))
            layers.append(nn.Tanh())
            
        layers.append(nn.Linear(self.features[-2], self.features[-1]))
        layers.append(nn.Tanh())
        return nn.Sequential(*layers)
    
    def forward(self, x):
        """
        Args:
            x (Tensor): Input tensor of shape (batch_size, input_dims)
        """
        # Process each dimension separately.
        features_list = [net(x[:, i:i+1]) for i, net in enumerate(self.networks)]
        
        # Sequentially combine the features. Start with the first dimension’s features...
        combined = features_list[0]
        # ...then concatenate and combine with each subsequent dimension.
        for i in range(1, self.input_dims):
            # Concatenate along the feature dimension (dim=1)
            combined = torch.cat([combined, features_list[i]], dim=1)
            combined = self.activation(self.combine_layers[i-1](combined))
        
        # Apply the final layer
        output = self.final_layer(combined)
        return output.squeeze(-1)


class PINN:
    def __init__(self):
        self.epoch = args.epochs
        self.adam_lr = args.lr
        self.dim, self.batch_size = args.dim, args.batch_size
        self.x = torch.tensor(x, dtype=torch.float32, requires_grad=False).to(device)
        self.u = torch.tensor(u, dtype=torch.float32, requires_grad=False).to(device).reshape(-1)
        # Initalize Neural Networks
        #layers = [args.input_dim] + [args.PINN_h] * (args.PINN_L - 1) + [args.output_dim]
        layers =  [args.PINN_h] * (args.PINN_L) 

        self.u_net = SPINN_D(layers).to(device)

        self.net_params_pinn = list(self.u_net.parameters())
        self.saved_loss = []
        self.saved_l2 = []

    def Resample(self): # sample random points at the begining of each iteration
        N_f = args.N_f # Number of collocation points

        xf = np.random.randn(N_f, args.dim)
        rf = np.random.rand(N_f, 1) * args.x_radius
        xf = xf / np.linalg.norm(xf, axis=1, keepdims=True) * rf
        x = xf

        u1 = args.x_radius**2 - np.sum(x**2, 1, keepdims=True)
        du1_dx = -2 * x
        d2u1_dx2 = -2

        x1, x2 = x[:, :-1], x[:, 1:]
        coeffs = c
        u2 = coeffs * np.sin(x1 + const_2 * np.cos(x2) + x2 * np.cos(x1))
        u2 = np.sum(u2, 1, keepdims=True)
        du2_dx_part1 = coeffs * np.cos(x1 + const_2 * np.cos(x2) + x2 * np.cos(x1)) * \
                (1 - x2 * np.sin(x1))
        du2_dx_part2 = coeffs * np.cos(x1 + const_2 * np.cos(x2) + x2 * np.cos(x1)) * \
                (-const_2 * np.sin(x2) + np.cos(x1))
        du2_dx = np.zeros((N_f, args.dim))
        du2_dx[:, :-1] += du2_dx_part1
        du2_dx[:, 1:] += du2_dx_part2
        d2u2_dx2_part1 = -coeffs * np.sin(x1 + const_2 * np.cos(x2) + x2 * np.cos(x1)) * (1 - x2 * np.sin(x1))**2 + \
                coeffs * np.cos(x1 + const_2 * np.cos(x2) + x2 * np.cos(x1)) * (- x2 * np.cos(x1))
        d2u2_dx2_part2 = -coeffs * np.sin(x1 + const_2 * np.cos(x2) + x2 * np.cos(x1)) * (-const_2 * np.sin(x2) + np.cos(x1))**2 + \
                coeffs * np.cos(x1 + const_2 * np.cos(x2) + x2 * np.cos(x1)) * (-const_2 * np.cos(x2))
        d2u2_dx2 = np.zeros((N_f, args.dim))
        d2u2_dx2[:, :-1] += d2u2_dx2_part1
        d2u2_dx2[:, 1:] += d2u2_dx2_part2
        ff = u1 * d2u2_dx2 + 2 * du1_dx * du2_dx + u2 * d2u1_dx2
        ff = np.sum(ff, 1)

        self.xf = torch.tensor(xf, dtype=torch.float32, requires_grad=True).to(device)
        self.ff = torch.tensor(ff, dtype=torch.float32, requires_grad=True).to(device)
        return

    def Method0(self): # Vanilla PINN
        x = self.xf
        x.requires_grad_()
        f = self.u_net(x)
        u_x = torch.autograd.grad(f.sum(), x, create_graph=True)[0]

        u_xx = []
        for i in range(self.dim):
            d2f_dxidxi = torch.autograd.grad(u_x[:, i].sum(), x, create_graph=True)[0][:, i:i+1]
            u_xx.append(d2f_dxidxi)
        # (batch_size, x_dim)
        u_xx = torch.concat(u_xx, dim=1)

        residual_pred = torch.sum(u_xx, dim=1) - self.ff
        loss = residual_pred.square().mean()
        saeved_loss = loss
        return loss, saeved_loss
    
    def Method3(self): #SDGD Algorithm 3
        x = self.xf
        x.requires_grad_()
        f = self.u_net(x)
        u_x = torch.autograd.grad(f.sum(), x, create_graph=True)[0]

        residual_pred = 0
        idx = np.random.choice(self.dim, self.batch_size, replace=False)
        for i in idx:
            d2f_dxidxi = torch.autograd.grad(u_x[:, i].sum(), x, create_graph=True)[0][:, i]
            residual_pred += d2f_dxidxi

        residual_pred = residual_pred * self.dim / self.batch_size - self.ff
        loss = residual_pred.square().mean()
        saeved_loss = loss
        return loss, saeved_loss

    def num_params(self):
        num_pinn = 0
        for p in self.net_params_pinn:
            num_pinn += len(p.reshape(-1))
        return num_pinn

    def train_adam(self):
        optimizer = torch.optim.Adam(self.net_params_pinn, lr=self.adam_lr)
        scheduler = torch.optim.lr_scheduler.ExponentialLR(optimizer, gamma=0.9995)
        lr_lambda = lambda epoch: 1-epoch/args.epochs
        scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda=lr_lambda)
        L2, L1 = self.L2_pinn()
        print('Initialization: l2: %e, l1: %e'%(L2, L1))
        self.saved_loss.append(0)
        self.saved_l2.append([L2, L1])
    
        for n in tqdm(range(self.epoch)):
            self.Resample()
            if args.method == 0:
                loss, saved_loss = self.Method0()
            elif args.method == 3:
                loss, saved_loss = self.Method3()
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            if args.use_sch:
                scheduler.step()
            current_loss = saved_loss.item()
            if n % 100 == 0:
                L2, L1 = self.L2_pinn()
                print('epoch %d, loss: %e, l2: %e, l1: %e'%(n, current_loss, L2, L1))
            if args.save_loss:
                self.saved_loss.append(current_loss)
                if n % 100 != 0:
                    L2, L1 = self.L2_pinn()
                self.saved_l2.append([L2, L1])

    def predict_pinn(self):
        f = self.u_net(self.x).reshape(-1)
        return f
    
    def L2_pinn(self):
        pred_u = self.predict_pinn()
        pred_u = self.u - pred_u
        L2, L1 = torch.norm(pred_u) / torch.norm(self.u), \
            torch.norm(pred_u, p=1) / torch.norm(self.u, 1)
        L2, L1 = L2.item(), L1.item()
        return L2, L1

model = PINN()
print("Num params:", model.num_params())


model.train_adam()

if args.save_loss:
    model.saved_loss = np.asarray(model.saved_loss)
    model.saved_l2 = np.asarray(model.saved_l2)
    info_dict = {"loss": model.saved_loss, "L2": model.saved_l2[:, 0], "L1": model.saved_l2[:, 1]}
    df = pd.DataFrame(data=info_dict, index=None)
    df.to_excel(
        "saved_loss_l2/"+args.dataset+"_dim="+str(args.dim)+\
            "_batch="+str(args.batch_size)+"_N_f="+str(args.N_f)\
            +"_method="+str(args.method)+"_SEED="+str(args.SEED)+".xlsx",
        index=False
    )
