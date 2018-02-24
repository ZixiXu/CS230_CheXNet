# encoding: utf-8

"""
The main CheXNet model implementation.
"""

import os
import time
import copy
import logging

import numpy as np
from tqdm import tqdm

import torch
import torch.nn as nn
import torch.backends.cudnn as cudnn
import torchvision
import torch.optim as optim
import torchvision.transforms as transforms
from torch.autograd import Variable
from torch.utils.data import DataLoader
from sklearn.metrics import roc_auc_score

import read_data 
import utils

# import customised model, metric and params
import modelSetting.net as net
from evaluate import evaluate

N_CLASSES = 1
CLASS_NAMES = [ 'Atelectasis', 'Cardiomegaly', 'Effusion', 'Infiltration', 'Mass', 'Nodule', 'Pneumonia',
                'Pneumothorax', 'Consolidation', 'Edema', 'Emphysema', 'Fibrosis', 'Pleural_Thickening', 'Hernia']
# Training data and entry list
#TRAIN_DATA_DIR = 'images/train'
#TRAIN_IMAGE_LIST = 'train_list.txt'
TRAIN_BATCH_SIZE = 11

# Dev data and entry list
#DEV_DATA_DIR = 'images/dev' 
#DEV_IMAGE_LIST = 'dev_list.txt'
DEV_BATCH_SIZE = 4
use_gpu = torch.cuda.is_available()


normalize = transforms.Normalize([0.485, 0.456, 0.406],
                                 [0.229, 0.224, 0.225])


# a general model definition, scheduler: learning rate decay    
def train(model, optimizer, train_loader, loss_fn, metrics):
    since = time.time()

    #scheduler.step()
    model.train(True)  # Set model to training mode

    running_corrects = 0
    running_accuracy = 0.0
    loss_avg = utils.RunningAverage()

    sample_size = 0;
    one_but_zero = np.zeros(14)
    zero_but_one = np.zeros(14)
    # summary for all the mini batch of metrics and loss
    summ = []

    with tqdm(total=len(train_loader)) as t:
        # Iterate over data.
         for data in train_loader:
            # get the inputs

            inputs, labels = data

            # wrap them in Variable
            if use_gpu:
                inputs = Variable(inputs.cuda())
                labels = Variable(labels.cuda())
            else:
                inputs, labels = Variable(inputs), Variable(labels)

            # zero the parameter gradients
            optimizer.zero_grad()

            # forward
            outputs = model(inputs)
            
            # conver the outputs and the labels to feed into BCE_loss function
            loss = loss_fn(outputs, labels)

            loss.backward()

            # performs updates using calculated gradients
            optimizer.step()

            # cutoff by 0.5
            preds = outputs >= 0.5
            preds = preds.type(torch.FloatTensor)

            # Here, we calculate the metrics and the loss for every batch
            # and save them to the summ
            # extract data from torch Variable, move to cpu, convert to
            # numpy
            preds_batch = preds.data.cpu().numpy()
            labels_batch = labels.data.cpu().numpy()
            sample_size += preds_batch.shape[0]

            # Compute all metrics in this batch
            summary_batch = {metric:metrics[metric](preds_batch,labels_batch) for metric in metrics}
            summary_batch['loss'] = loss.data[0]
            summ.append(summary_batch)

            truth_one_but_zero, truth_zero_but_one = each_label(preds_batch, labels_batch)
            one_but_zero += truth_one_but_zero
            zero_but_one += truth_zero_but_one
            # ToDo, we can use the above summary_batch instead of calculate
            # running_loss for every batch
            loss_avg.update(loss.data[0])

            t.set_postfix(loss='{:05.3f}'.format(loss_avg()))
            t.update()

        # Here, when we update all the batch in a certain epoch, we will calculate
        # the mean metrics for this epoch
        # compute mean of all metrics in summary
    metrics_mean = {metric:np.mean([x[metric] for x in summ]) for metric in summ[0]}
    metrics_string = " ; ".join("{}: {:05.3f}".format(k, v) for k, v in metrics_mean.items())
    
    logging.info("- Train metrics: " + metrics_string)

    # if metrics_mean['accuracy'] > best_acc:
    #     best_acc = metrics_mean['accuracy']
    #     best_model_wts = copy.deepcopy(model.state_dict())
    
    logging.info("- Train metrics: " + metrics_string)
    #print(np.array_str(one_but_zero))
    #print(np.array_str(zero_but_one))


    logging.info("\n")

    # print('Best training Acc: {:4f}'.format(best_acc))
    # time_elapsed = time.time() - since
    # print('Training complete in {:.0f}m {:.0f}s'.format(
    #     time_elapsed // 60, time_elapsed % 60))

    # load best model weights
    # model.load_state_dict(best_model_wts)
    return  metrics_mean['ROC_AUC']

def each_label(outputs, label):
    prediction = outputs - label
    truth_zero_but_one = np.count_nonzero(prediction == 1, axis = 0)
    truth_one_but_zero = np.count_nonzero(prediction == -1, axis = 0)
    return truth_one_but_zero, truth_zero_but_one


def train_model(model, optimizer, train_loader, loss_fn, metrics, num_epochs):
    best_model_wts = copy.deepcopy(model.state_dict())
    best_AUC = 0.0

    for epoch in range(num_epochs):
        print('start epco {}'.format(epoch))        
        logging.info('Epoch {}/{}'.format(epoch, num_epochs - 1))
        logging.info('-' * 10)

        ROC_AUC = train(model, optimizer, train_loader, loss_fn, metrics)
        print(ROC_AUC)

        if ROC_AUC > best_AUC:
            best_AUC = ROC_AUC
            print("update model for epoc")
            best_model_wts = copy.deepcopy(model.state_dict())

    model.load_state_dict(best_model_wts)



# set the logger
utils.set_logger(os.path.join(os.getcwd(),'train.log'))
# Create the input data pipeline
logging.info("Loading the datasets...")


# fetch dataloaders
if (not use_gpu):
   dataloaders = read_data.fetch_dataloader(['train', 'dev'], 'images', 'labels')
else:
   dataloaders = read_data.fetch_dataloader(['train', 'dev'], '/home/ubuntu/Data_Processed/images', \
                                           '/home/ubuntu/Data_Processed/labels')
train_dl = dataloaders['train']
dev_dl = dataloaders['dev']

# initialize and load the model
model = net.DenseNet121(N_CLASSES)
if use_gpu:
    model = net.DenseNet121(N_CLASSES).cuda()
    model = torch.nn.DataParallel(model)


#weights_file = os.path.join('/home/ubuntu/Data_Processed/labels/','train_list.txt')
#train_weight = torch.from_numpy(utils.get_loss_weights(weights_file)).float()
#print(train_weight)
#if use_gpu:
#   train_weight = train_weight.cuda()

train_loss = nn.BCELoss()
#train_loss = nn.MultiLabelSoftMarginLoss(weight = train_weight) 
optimizer = optim.Adam(model.parameters(), lr=0.001, weight_decay=5e-5)

# Define the metrics
metrics = net.metrics
eval_metrics = net.eval_metrics
# Decay LR by a factor of 0.1 every 7 epochs
#exp_lr_scheduler = lr_scheduler.StepLR(optimizer, step_size=7, gamma=0.1)


# Train the model in the training set
train_model(model, optimizer, train_dl, train_loss, metrics, num_epochs = 3 )

#utils.save_checkpoint({'state_dict': model.state_dict()}, is_best=None, checkpoint='trial1')
#utils.load_checkpoint(checkpoint = 'trial1/last.pth.tar', model = dev_model)


# evalute the model in the val_dataset
logging.info("Metric Report for the dev set") 
evaluate(model, train_loss, dev_dl, eval_metrics, use_gpu)
