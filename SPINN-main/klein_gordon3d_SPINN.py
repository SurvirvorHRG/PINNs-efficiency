import argparse
import os
import time

import jax
import numpy as np
import optax
from networks.hessian_vector_products import *
from tqdm import trange
from utils.data_generators import generate_test_data, generate_train_data
from utils.eval_functions import setup_eval_function
from utils.training_utils import *
from utils.visualizer import show_solution


@partial(jax.jit, static_argnums=(0,))
def apply_model_spinn(apply_fn, params, *train_data):
    def residual_loss(params, t, x, y, source_term):
        # calculate u
        u = apply_fn(params, t, x, y)
        # tangent vector dx/dx
        v_t = jnp.ones(t.shape)
        v_x = jnp.ones(x.shape)
        v_y = jnp.ones(y.shape)
        # 2nd derivatives of u
        utt = hvp_fwdfwd(lambda t: apply_fn(params, t, x, y), (t,), (v_t,))
        sum = 0.
        idx = np.random.choice(2, 1, replace=False)
        if idx == 0:
            sum += hvp_fwdfwd(lambda x: apply_fn(params, t, x, y), (x,), (v_x,))
        else:
            sum += hvp_fwdfwd(lambda y: apply_fn(params, t, x, y), (y,), (v_y,))

        return jnp.mean((utt - sum + u**2 - source_term)**2)

    def initial_loss(params, t, x, y, u):
        return jnp.mean((apply_fn(params, t, x, y) - u)**2)

    def boundary_loss(params, t, x, y, u):
        loss = 0.
        for i in range(4):
            loss += jnp.mean((apply_fn(params, t[i], x[i], y[i]) - u[i])**2)
        return loss

    # unpack data
    tc, xc, yc, uc, ti, xi, yi, ui, tb, xb, yb, ub = train_data

    # isolate loss func from redundant arguments
    loss_fn = lambda params: residual_loss(params, tc, xc, yc, uc) + \
                        initial_loss(params, ti, xi, yi, ui) + \
                        boundary_loss(params, tb, xb, yb, ub)

    loss, gradient = jax.value_and_grad(loss_fn)(params)

    return loss, gradient


@partial(jax.jit, static_argnums=(0,))
def apply_model_pinn(apply_fn, params, *train_data):
    def residual_loss(params, t, x, y, source_term):
        # compute u
        u = apply_fn(params, t, x, y)
        # tangent vector du/du
        v = jnp.ones(u.shape)
        # 2nd derivatives of u
        utt = hvp_fwdrev(lambda t: apply_fn(params, t, x, y), (t,), (v,))
        sum = 0.
        idx = np.random.choice(2, 1, replace=False)
        if idx == 0:
            sum += hvp_fwdrev(lambda x: apply_fn(params, t, x, y), (x,), (v,))
        else:
            sum += hvp_fwdrev(lambda y: apply_fn(params, t, x, y), (y,), (v,))

        return jnp.mean((utt - sum + u**2 - source_term)**2)

    def initial_boundary_loss(params, t, x, y, u):
        return jnp.mean((apply_fn(params, t, x, y) - u)**2)

    # unpack data
    tc, xc, yc, uc, ti, xi, yi, ui, tb, xb, yb, ub = train_data

    # isolate loss function from redundant arguments
    loss_fn = lambda params: residual_loss(params, tc, xc, yc, uc) + \
                        initial_boundary_loss(params, ti, xi, yi, ui) + \
                        initial_boundary_loss(params, tb, xb, yb, ub)

    loss, gradient = jax.value_and_grad(loss_fn)(params)

    return loss, gradient


if __name__ == '__main__':
    # config
    parser = argparse.ArgumentParser(description='Training configurations')

    # model and equation
    parser.add_argument('--model', type=str, default='spinn', choices=['spinn', 'pinn'], help='model name (pinn; spinn)')
    parser.add_argument('--equation', type=str, default='klein_gordon3d', help='equation to solve')
    
    # input data settings
    parser.add_argument('--nc', type=int, default=16, help='the number of input points for each axis')
    parser.add_argument('--nc_test', type=int, default=100, help='the number of test points for each axis')

    # training settings
    parser.add_argument('--seed', type=int, default=111, help='random seed')
    parser.add_argument('--lr', type=float, default=1e-3, help='learning rate')
    parser.add_argument('--epochs', type=int, default=1000, help='training epochs')

    # model settings
    parser.add_argument('--mlp', type=str, default='modified_mlp', choices=['mlp', 'modified_mlp'], help='type of mlp')
    parser.add_argument('--n_layers', type=int, default=3, help='the number of layer')
    parser.add_argument('--features', type=int, default=64, help='feature size of each layer')
    parser.add_argument('--r', type=int, default=32, help='rank of the approximated tensor')
    parser.add_argument('--out_dim', type=int, default=1, help='size of model output')
    parser.add_argument('--pos_enc', type=int, default=0, help='size of the positional encoding (zero if no encoding)')

    # PDE settings
    parser.add_argument('--k', type=int, default=2, help='temporal frequency of the solution')
    
    # log settings
    parser.add_argument('--log_iter', type=int, default=1, help='print log every...')
    parser.add_argument('--plot_iter', type=int, default=25000, help='plot result every...')

    args = parser.parse_args()

    # random key
    key = jax.random.PRNGKey(args.seed)

    # make & init model forward function
    key, subkey = jax.random.split(key, 2)
    apply_fn, params = setup_networks(args, subkey)

    # count total params
    args.total_params = sum(x.size for x in jax.tree_util.tree_leaves(params))

    # name model
    name = name_model(args)

    # result dir
    root_dir = os.path.join(os.getcwd(), 'results', args.equation, args.model)
    result_dir = os.path.join(root_dir, name)

    # make dir
    os.makedirs(result_dir, exist_ok=True)

    # optimizer
    optim = optax.adam(learning_rate=args.lr)
    state = optim.init(params)

    # dataset
    key, subkey = jax.random.split(key, 2)
    train_data = generate_train_data(args, subkey, result_dir=result_dir)
    test_data = generate_test_data(args, result_dir)

    # evaluation function
    eval_fn = setup_eval_function(args.model, args.equation)

    # save training configuration
    save_config(args, result_dir)

    # log
    logs = []
    if os.path.exists(os.path.join(result_dir, 'log (loss, error).csv')):
        os.remove(os.path.join(result_dir, 'log (loss, error).csv'))
    if os.path.exists(os.path.join(result_dir, 'best_error.csv')):
        os.remove(os.path.join(result_dir, 'best_error.csv'))
    best = 100000.

    # start training
    for e in trange(1, args.epochs + 1):
        if e == 2:
            # exclude compiling time
            start = time.time()

        if e % 100 == 0:
            # sample new input data
            key, subkey = jax.random.split(key, 2)
            train_data = generate_train_data(args, subkey)

        if args.model == 'spinn':
            loss, gradient = apply_model_spinn(apply_fn, params, *train_data)
        elif args.model == 'pinn':
            loss, gradient = apply_model_pinn(apply_fn, params, *train_data)
        params, state = update_model(optim, gradient, params, state)

        best_error = best
        if e % 10 == 0:
            if loss < best:
                best = loss
                best_error = eval_fn(apply_fn, params, *test_data)

        # log
        if e % args.log_iter == 0:
            error = eval_fn(apply_fn, params, *test_data)
            print(f'Epoch: {e}/{args.epochs} --> total loss: {loss:.8f}, error: {error:.8f}, best error {best_error:.8f}')
            with open(os.path.join(result_dir, 'log (loss, error).csv'), 'a') as f:
                f.write(f'{loss}, {error}, {best_error}\n')

        # visualization
        if e % args.plot_iter == 0:
            show_solution(args, apply_fn, params, test_data, result_dir, e, resol=50)


    # training done
    runtime = time.time() - start
    print(f'Runtime --> total: {runtime:.2f}sec ({(runtime/(args.epochs-1)*1000):.2f}ms/iter.)')
    jnp.save(os.path.join(result_dir, 'params.npy'), params)
        
    # save runtime
    runtime = np.array([runtime])
    np.savetxt(os.path.join(result_dir, 'total runtime (sec).csv'), runtime, delimiter=',')

    # save total error
    with open(os.path.join(result_dir, 'best_error.csv'), 'a') as f:
        f.write(f'best error: {best_error}\n')