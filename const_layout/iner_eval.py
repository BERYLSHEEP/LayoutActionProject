import pickle
import argparse
import numpy as np
from pathlib import Path
from collections import defaultdict

import torch
from torch_geometric.data import Data, Batch, DataLoader
from torch_geometric.utils import to_dense_batch

from datas import get_dataset
from metric import LayoutFID, compute_maximum_iou, \
    compute_overlap, compute_alignment


def average(scores):
    return sum(scores) / len(scores)


def print_scores(score_dict):
    for k, v in score_dict.items():
        if k in ['Alignment', 'Overlap']:
            v = [_v * 100 for _v in v]
        if len(v) > 1:
            mean, std = np.mean(v), np.std(v)
            print(f'\t{k}: {mean:.2f} ({std:.2f})')
        else:
            print(f'\t{k}: {v[0]:.2f}')


def eval(args, dataset='rico', batch_size=64, compute_real=False):
    dataset = get_dataset(dataset, 'test')
    dataloader = DataLoader(dataset,
                            batch_size=batch_size,
                            num_workers=4,
                            pin_memory=True,
                            shuffle=False)
    test_layouts = [(data.x.numpy(), data.y.numpy()) for data in dataset]

    # prepare for evaluation
    # fid_test = LayoutFID(args.dataset, device)

    # real layouts
    alignment, overlap = [], []
    for i, data in enumerate(dataloader):
        data = data.to(args.device)
        label, mask = to_dense_batch(data.y, data.batch)
        bbox, _ = to_dense_batch(data.x, data.batch)
        padding_mask = ~mask

        # fid_test.collect_features(bbox, label, padding_mask,
                                #   real=True)

        if compute_real:
            alignment += compute_alignment(bbox, mask).tolist()
            overlap += compute_overlap(bbox, mask).tolist()

    if compute_real:
        dataset = get_dataset(dataset, 'val')
        dataloader = DataLoader(dataset,
                                batch_size=args.batch_size,
                                num_workers=4,
                                pin_memory=True,
                                shuffle=False)
        val_layouts = [(data.x.numpy(), data.y.numpy()) for data in dataset]

        for i, data in enumerate(dataloader):
            data = data.to(args.device)
            label, mask = to_dense_batch(data.y, data.batch)
            bbox, _ = to_dense_batch(data.x, data.batch)
            padding_mask = ~mask

            # fid_test.collect_features(bbox, label, padding_mask)

        # fid_score = fid_test.compute_score()
        max_iou = compute_maximum_iou(test_layouts, val_layouts)
        alignment = average(alignment)
        overlap = average(overlap)

        print('Real data:')
        print_scores({
            # 'FID': [fid_score],
            'Max. IoU': [max_iou],
            'Alignment': [alignment],
            'Overlap': [overlap],
        })
        print()

    # generated layouts
    scores = defaultdict(list)
    # for pkl_path in args.evaluate_layout_path:
    alignment, overlap = [], []
    with Path(args.evaluate_layout_path).open('rb') as fb:
        generated_layouts = pickle.load(fb)

    for i in range(0, len(generated_layouts), args.batch_size):
        i_end = min(i + args.batch_size, len(generated_layouts))

        # get batch from data list
        data_list = []
        for b, l in generated_layouts[i:i_end]:
            bbox = torch.tensor(b, dtype=torch.float)
            label = torch.tensor(l, dtype=torch.long)
            data = Data(x=bbox, y=label)
            data_list.append(data)
        data = Batch.from_data_list(data_list)

        data = data.to(args.device)
        label, mask = to_dense_batch(data.y, data.batch)
        bbox, _ = to_dense_batch(data.x, data.batch)
        padding_mask = ~mask

        # fid_test.collect_features(bbox, label, padding_mask)
        alignment += compute_alignment(bbox, mask).tolist()
        overlap += compute_overlap(bbox, mask).tolist()

    # fid_score = fid_test.compute_score()
    max_iou = compute_maximum_iou(test_layouts, generated_layouts)
    alignment = average(alignment)
    overlap = average(overlap)

    # scores['FID'].append(fid_score)
    scores['Max. IoU'].append(max_iou)
    scores['Alignment'].append(alignment)
    scores['Overlap'].append(overlap)

    return scores