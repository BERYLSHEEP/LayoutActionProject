from ast import arg
from email.policy import default
import os
import argparse
import torch
from dataset import get_dataset
from model import GPT, GPTConfig
from trainer import Trainer, TrainerConfig, Eval
from utils import set_seed

if __name__ == "__main__":
    parser = argparse.ArgumentParser('Layout Transformer')
    parser.add_argument("--exp", default="layout", help="experiment name")
    parser.add_argument("--log_dir", default="./output/logs", help="/path/to/logs/dir")
    parser.add_argument("--dataset", choices=["rico", "publaynet", "infoppt"], default="publaynet", const='bbox',nargs='?')
    parser.add_argument("--device", type=int, default=0)

    # Architecture/training options
    parser.add_argument("--add_shared_representation", action='store_true', default=False)
    parser.add_argument("--consistence_param", type=float, default=10)
    
    parser.add_argument("--seed", type=int, default=42, help="random seed")
    parser.add_argument("--batch_size", type=int, default=5, help="batch size")
    parser.add_argument('--n_layer', default=6, type=int)
    parser.add_argument('--n_embd', default=512, type=int)
    parser.add_argument('--n_head', default=8, type=int)

    parser.add_argument("--epochs", type=int, default=50, help="number of epochs")
    parser.add_argument("--lr", type=float, default=4.5e-06, help="learning rate")
    parser.add_argument('--lr_decay', action='store_true', help="use learning rate decay")
    parser.add_argument('--warmup_iters', type=int, default=0, help="linear lr warmup iters")
    parser.add_argument('--final_iters', type=int, default=0, help="cosine lr final iters")
    parser.add_argument('--sample_every', type=int, default=1, help="sample every epoch")

    # test
    parser.add_argument('--evaluate', action='store_true', help="evaluate only")
    parser.add_argument("--model_path", type=str, default=None)
    
    parser.add_argument("--eval_command", choices=["random_generate", "category_generate", "real_image", "reconstruction"], \
        default="random_generate", const='random_generate',nargs='?', help="real_image indicates to save the real images which labels are given to category_generate or reconstruction.")
    # command args
    parser.add_argument('--save_image', action='store_true', help="save the generated image")
    parser.add_argument('--calculate_coverage', action='store_true', help="calculate the coverage rate")
    parser.add_argument('--save_pkl', action='store_true', 
                        help="save the generated bbox for heuristic metrics (FID, IoU, Align and Overlap)")
    parser.add_argument('--calculate_probability', action='store_true', 
                        help="calculate the grammar correctness and trigger rate of different actions")
    

    args = parser.parse_args()

    log_dir = os.path.join(args.log_dir, args.dataset, args.exp)
    if args.evaluate:
        samples_dir = os.path.join(log_dir, "evaluate_samples")
    else:
        samples_dir = os.path.join(log_dir, "samples")
    ckpt_dir = os.path.join(log_dir, "checkpoints")
    os.makedirs(samples_dir, exist_ok=True)
    os.makedirs(ckpt_dir, exist_ok=True)

    set_seed(args.seed)

    device = torch.device(f"cuda:{args.device}" if torch.cuda.is_available() else "cpu")
    print(f"using device: {device}")

    train_dataset = get_dataset(args.dataset, "train")
    if args.evaluate:
        valid_dataset = get_dataset(args.dataset, "test")
    else:
        valid_dataset = get_dataset(args.dataset, "val")
        
    mconf = GPTConfig(train_dataset.vocab_size, train_dataset.max_length,
                      n_layer=args.n_layer, n_head=args.n_head, n_embd=args.n_embd)  # a GPT-1
    model = GPT(mconf)
    tconf = TrainerConfig(max_epochs=args.epochs,
                          batch_size=args.batch_size,
                          lr_decay=args.lr_decay,
                          learning_rate=args.lr * args.batch_size,
                          warmup_iters=args.warmup_iters,
                          final_iters=args.final_iters,
                          ckpt_dir=ckpt_dir,
                          samples_dir=samples_dir,
                          sample_every=args.sample_every,
                          model_path=args.model_path,
                          device=device,
                          evaluate_layout_path=os.path.join(log_dir, "generated_layout.pth"))


    if args.evaluate:
        print("testing...")
        command = {"name": args.eval_command, "save_image": args.save_image, "calculate_coverage": args.calculate_coverage,
                    "save_pkl": args.save_pkl, "calculate_probability": args.calculate_probability}
        if not (args.save_image or args.calculate_coverage or args.save_pkl or args.calculate_probability):
            print("At least one option of the command args should be set True.")
        else:
            evaler = Eval(model, valid_dataset, tconf)
            evaler.eval(command)
    else:
        print("training...")
        if args.add_shared_representation:
            train_rela_dataset = get_dataset(args.dataset, "train", is_rela=True)
            trainer = Trainer(model, train_dataset, valid_dataset, tconf, args, train_rela_dataset)        
        else:
            trainer = Trainer(model, train_dataset, valid_dataset, tconf, args)
        trainer.train()
