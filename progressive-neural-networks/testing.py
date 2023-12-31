from collections import deque

import torch
import torch.nn.functional as F
from torch.utils.tensorboard import SummaryWriter
from environment import get_threshold


def test(pid, opt, gmodel):
    torch.manual_seed(opt.seed + pid)
    writer = SummaryWriter(opt.log_path)
    allenvs = create_env(opt)
    lmodel = PNN(allenvs)

    lmodel.eval()

    for cid, env in enumerate(allenvs):
        env.seed(opt.seed + pid)
        state = torch.Tensor(env.reset())
        done = True
        lstep, episode, reward_sum, weighted = 0, 0, 0, 0
        actions = deque(maxlen=opt.max_actions)

        iterator = range(int(opt.ngsteps))
        for gstep in iterator:
            lstep += 1
            if done:
                lmodel.load_state_dict(gmodel.state_dict())
                if not gstep % opt.interval and gstep:
                    torch.save(lmodel.state_dict(), opt.save_path / "pnn")

            with torch.no_grad():
                _, logits = lmodel(state.unsqueeze(0))
            prob = F.softmax(logits, dim=-1)
            action = prob.max(1, keepdim=True)[1].numpy()

            state, reward, done, _ = env.step(action[0, 0])
            state = torch.Tensor(state)
            reward_sum += reward

            actions.append(action[0, 0])
            if gstep > opt.ngsteps or \
               actions.count(actions[0]) == actions.maxlen:
                done = True

            if opt.render:
                env.render()

            if done:
                episode += 1
                weighted = opt.discount * weighted + \
                    (1 - opt.discount) * reward_sum
                writer.add_scalar(f"Eval Column {cid}/Reward", reward_sum,
                                  gstep)
                progress_data = f"step: {lstep}, episode: {episode}, reward: {reward_sum:5.1f}, weighted: {weighted:5.1f}"
                iterator.set_postfix_str(progress_data)

                lstep, reward_sum = 0, 0
                actions.clear()
                state = torch.Tensor(env.reset())

                if weighted > get_threshold(env.unwrapped.spec.id):
                    gmodel.freeze()
                    break

        lmodel.freeze()
