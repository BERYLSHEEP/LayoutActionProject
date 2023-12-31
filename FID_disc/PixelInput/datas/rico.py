import json
from pathlib import Path

import torch
from torch_geometric.data import Data

from datas.base import BaseDataset


def append_child(element, elements):
    if 'children' in element.keys():
        for child in element['children']:
            elements.append(child)
            elements = append_child(child, elements)
    return elements


class Rico(BaseDataset):
    labels = [
        'Toolbar',
        'Image',
        'Text',
        'Icon',
        'Text Button',
        'Input',
        'List Item',
        'Advertisement',
        'Pager Indicator',
        'Web View',
        'Background Image',
        'Drawer',
        'Modal',
    ]

    def __init__(self, split, json_dir=None, transform=None):
        self.json_dir = json_dir
        self.split = split
        super().__init__('rico', split, transform)
        
    def download(self):
        if self.json_dir is None:
            super().download()

    def process(self):
        # train_dir = Path("/home/v-hyang/github/LayoutGeneration/DeepLayout/data/Rico/train")
        # val_dir = Path("/home/v-hyang/github/LayoutGeneration/DeepLayout/data/Rico/val")
        # test_dir = Path("/home/v-hyang/github/LayoutGeneration/DeepLayout/data/Rico/test")
        # # raw_dir = Path(self.raw_dir) / 'semantic_annotations'

        # dir_list = [train_dir, val_dir, test_dir]
        if self.json_dir is not list:
            self.json_dir = [Path(self.json_dir)]
        else:
            for idx, dir in enumerate(self.json_dir):
                if dir is not Path:
                    self.json_dir[idx] = Path(dir)

        for idx, raw_dir in enumerate(self.json_dir):
            data_list = []
            for json_path in sorted(raw_dir.glob('*.json')):
                with json_path.open() as f:
                    ann = json.load(f)

                B = ann['bounds']
                W, H = float(B[2]), float(B[3])
                if B[0] != 0 or B[1] != 0 or H < W:
                    continue

                def is_valid(element):
                    if element['componentLabel'] not in set(self.labels):
                        return False

                    x1, y1, x2, y2 = element['bounds']
                    if x1 < 0 or y1 < 0 or W < x2 or H < y2:
                        return False

                    if x2 <= x1 or y2 <= y1:
                        return False

                    return True

                elements = append_child(ann, [])
                _elements = list(filter(is_valid, elements))
                filtered = len(elements) != len(_elements)
                elements = _elements

                N = len(elements)
                if N == 0 or 9 < N:
                    continue

                boxes = []
                labels = []

                for element in elements:
                    # bbox
                    x1, y1, x2, y2 = element['bounds']
                    xc = (x1 + x2) / 2.
                    yc = (y1 + y2) / 2.
                    width = x2 - x1
                    height = y2 - y1
                    b = [xc / W, yc / H,
                        width / W, height / H]
                    boxes.append(b)

                    # label
                    l = element['componentLabel']
                    labels.append(self.label2index[l])

                boxes = torch.tensor(boxes, dtype=torch.float)
                labels = torch.tensor(labels, dtype=torch.long)

                data = Data(x=boxes, y=labels)
                data.attr = {
                    'name': json_path.name,
                    'width': W,
                    'height': H,
                    'filtered': filtered,
                    'has_canvas_element': False,
                }
                data_list.append(data)

            # shuffle with seed
            generator = torch.Generator().manual_seed(0)
            indices = torch.randperm(len(data_list), generator=generator)
            data_list = [data_list[i] for i in indices]
            N = len(data_list)
            print(idx, N)

            idx = self.processed_file_names.index('{}.pt'.format(self.split))
            torch.save(self.collate(data_list), self.processed_paths[idx])

        # train 85% / val 5% / test 10%
        # N = len(data_list)
        # s = [int(N * .85), int(N * .90)]
        # torch.save(self.collate(data_list[:s[0]]), self.processed_paths[0])
        # torch.save(self.collate(data_list[s[0]:s[1]]), self.processed_paths[1])
        # torch.save(self.collate(data_list[s[1]:]), self.processed_paths[2])
