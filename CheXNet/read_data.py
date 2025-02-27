
"""
Read images and corresponding labels.
"""
import os
import random

import torch
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as transforms
import numpy as np
from PIL import Image

# borrowed from http://pytorch.org/tutorials/beginner/data_loading_tutorial.html
# define a training image loader that specifies transforms on images. See documentation for more details.
train_transformer = transforms.Compose([
    transforms.Resize(224),  # resize the image to 64x64 (remove if images are already 64x64)
    transforms.RandomHorizontalFlip(),  # randomly flip image horizontally
    transforms.ToTensor(),  # transform it into a torch tensor
    transforms.Normalize([0.485, 0.456, 0.406],[0.229, 0.224, 0.225])])

# loader for evaluation, no horizontal flip
eval_transformer = transforms.Compose([
    transforms.Resize(224),  # resize the image to 64x64 (remove if images are already 64x64)
    transforms.ToTensor(),    # transform it into a torch tensor
    transforms.Normalize([0.485, 0.456, 0.406],[0.229, 0.224, 0.225])])

TRAIN_BATCH_SIZE = 16
DEV_BATCH_SIZE = 1
class ChestXrayDataSet(Dataset):
    def __init__(self, image_file, label_file, transform=None):
        """
        Args:
            image_file: path to image files.
            label_file: output path to the file containing corresponding labels.
            transform: optional transform to be applied on a sample.
        """
        image_names = []
        labels = []
        with open(label_file, "r") as f:
            for line in f:
                items = line.split()
                image_name= items[0]
                #label = items[1:]
                
                # construct the labels containing no_finding
                finding = np.count_nonzero( np.asarray(items[1:] , dtype = np.int32) )
                if finding == 0:
                    items[0] = 0
                else:
                    items[0] = 1
                label = items
                label = [int(i) for i in label]
                image_name = os.path.join(image_file, image_name)
                image_names.append(image_name)
                labels.append(label)

        self.image_names = image_names
        self.labels = labels
        self.transform = transform

    def __getitem__(self, index):
        """
        Args:
            index: the index of item

        Returns:
            image and its labels
        """
        image_name = self.image_names[index]
        image = Image.open(image_name).convert('RGB')
        label = self.labels[index]
        if self.transform is not None:
            image = self.transform(image)
        return image, torch.Tensor(label)

    def __len__(self):
        return len(self.image_names)


def fetch_dataloader(types, image_dir, label_dir):
    """
    Fetches the DataLoader object for each type in types from data_dir.

    Args:
        types: (list) has one or more of 'train', 'val', 'test' depending on which data is required
        image_dir: (string) directory containing all the images
        label_dir: (string) directory containing all the labels
        params: (Params) hyperparameters

    Returns:
        data: (dict) contains the DataLoader object for each type in types
    """
    dataloaders = {}

    for split in ['train', 'dev', 'test']:
        if split in types:
            label_path = os.path.join(label_dir, "{}_list.txt".format(split))
            image_path = os.path.join(image_dir, "{}".format(split))
            # use the train_transformer if training data, else use eval_transformer without random flip
            if split == 'train':
                ds = ChestXrayDataSet(image_file=image_path, label_file=label_path, transform=train_transformer)
                dataloaders[split] = DataLoader(ds, batch_size=TRAIN_BATCH_SIZE, shuffle=False, num_workers=8, pin_memory=False)
            else:
                ds = ChestXrayDataSet(image_file=image_path, label_file=label_path, transform=eval_transformer)
                dataloaders[split] = DataLoader(ds, batch_size=DEV_BATCH_SIZE, shuffle=False, num_workers=8, pin_memory=False)

    return dataloaders

