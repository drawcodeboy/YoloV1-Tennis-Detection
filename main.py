import torch
from torch import nn
from torch.utils.data import Dataset
from torch.utils.data import DataLoader
from torch.utils.data import random_split
import torchvision.transforms as transforms
import torch.nn.functional as F

from models.YOLO import Yolov1, BBBasedYolov1
from models.loss_function.yololoss import YoloLoss
from data_loader.data_loader import Compose, CustomDataset, imgshow

from engine import *

import argparse
import matplotlib.pyplot as plt
import cv2
import numpy as np
import os
import sys
from copy import deepcopy

os.environ['KMP_DUPLICATE_LIB_OK']='True'

def get_args_parser():
    parser = argparse.ArgumentParser(add_help=False)
    
    # Model
    # 1: YoloV1, 2: BBBasedYolov1
    parser.add_argument("--model", type=int, default=2)
    
    # Train or Inference
    parser.add_argument("--mode", type=str, default='train')
    
    # Dataset
    parser.add_argument("--data", type=str, default='tennis')
    
    # Dataset Location
    # 해당 Argument는 코랩에서 실행하다보니 데이터셋의 위치와 코드셋의 위치가 달라졌기 때문에
    # Dataset의 위치를 인자로 받아서 처리하기 위함
    parser.add_argument("--image_dir", type=str)
    parser.add_argument("--label_dir", type=str)
    
    # Video Location
    # Inference Video 위치
    parser.add_argument("--video_loc", type=str)
    
    # Hyperparameter
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--weight_decay", type=float, default=0.)
    parser.add_argument("--iou_threshold", type=float, default=0.5)
    
    # utils
    parser.add_argument("--device", type=str, default='cpu')
    
    # Saved Loss Location
    parser.add_argument("--file_name_loss", type=str)
    
    # Saved Model Location
    parser.add_argument("--file_name", type=str)
    
    # 잘 작동하는지 CPU 상에서 확인하기 위해 데이터셋을 아주 조금 가져오기 위한 Argument
    parser.add_argument("--worktest", type=str, default='N')
    
    return parser


def main(args):
    # Device Utilization
    device = None
    if args.device == 'cuda':
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    else:
        device = 'cpu'
    
    img_size, num_classes = None, None
    # Dataset & num_classees
    if args.data == 'tennis':
        img_size = (960, 540)
        num_classes = 3
    elif args.data == 'pascal':
        img_size = (448, 448)
        num_classes = 20
    
    if args.mode == 'train':
        # Load Model
        model = None
        if args.model == 1:
            model = Yolov1(split_size=7, num_boxes=2, num_classes=num_classes, width=img_size[0], height=img_size[1]).to(device)
        elif args.model == 2:
            model = BBBasedYolov1(split_size=7, num_boxes=2, num_classes=num_classes, width=img_size[0], height=img_size[1]).to(device)
        print('Load Model Complete')
        
        # Load Loss Function
        loss_fn = YoloLoss(C=num_classes).to(device)
        
        # Load Optimizer
        optimizer = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
        
        # Load Dataset
        
        # Minimize Dataset for Test this program on CPU
        length = None
        if args.worktest == 'y':
            print("Minimize Dataset for Test on CPU")
            length = 32
        
        if args.data == 'tennis':
            transform = Compose([transforms.ToTensor(),])
            IMG_DIR = args.image_dir
            LABEL_DIR = args.label_dir
            
            ds = CustomDataset(
                img_dir = IMG_DIR,
                label_dir = LABEL_DIR,
                transform = transform,
                width=img_size[0], 
                height=img_size[1],
                length=length,
                C = num_classes
            )
        
        elif args.data == 'pascal':
            transform = Compose([transforms.ToTensor(),])
            IMG_DIR = args.image_dir
            LABEL_DIR = args.label_dir
            
            ds = CustomDataset(
                img_dir = IMG_DIR,
                label_dir = LABEL_DIR,
                transform = transform,
                width=img_size[0], 
                height=img_size[1],
                length=length,
                C = num_classes
            )
        
        print(f"Dataset Length: {len(ds)}")
        
        # Load DataLoader
        train_dl = DataLoader(ds, batch_size=args.batch_size, shuffle=True)
        print('Load Dataset Complete')
        
        # Train
        loss_list = []
        print('====================')
        for epoch in range(args.epochs):
            loss = train_one_epoch(model, loss_fn, optimizer, train_dl, device, epoch+1, args.epochs)
            loss_list.append(loss)
            print('\n--------------------')
        
        try: 
            np.save(os.path.join('saved/loss', args.file_name_loss), np.array(loss_list))
            print("Saving Loss Success!")
        except:
            print("Saving Loss Failed...")
        
        # Save Model
        if args.file_name:
            try:
                torch.save(model.state_dict(), os.path.join('saved', args.file_name))
                print("Saving Model Success!")
            except:
                print("Saving Model Failed...")

    elif args.mode == 'test':
        # Load Trained Model
        model = None
        if args.model == 1:
            model = Yolov1(split_size=7, num_boxes=2, num_classes=num_classes, width=img_size[0], height=img_size[1]).to(device)
        elif args.model == 2:
            model = BBBasedYolov1(split_size=7, num_boxes=2, num_classes=num_classes, width=img_size[0], height=img_size[1]).to(device)
        
        model.load_state_dict(torch.load(args.file_name, map_location=device))
        model.eval()
        print('Load Model Complete')
        
        # Load Dataset
        length = None
        if args.worktest == 'y':
            print("Minimize Dataset for Test on CPU")
            length = 64
        
        if args.data == 'tennis':
            transform = Compose([transforms.ToTensor(),])
            IMG_DIR = args.image_dir
            LABEL_DIR = args.label_dir
            
            ds = CustomDataset(
                img_dir = IMG_DIR,
                label_dir = LABEL_DIR,
                transform = transform,
                width=img_size[0], 
                height=img_size[1],
                length=length,
                C = num_classes
            )
        
        elif args.data == 'pascal':
            transform = Compose([transforms.ToTensor(),])
            IMG_DIR = args.image_dir
            LABEL_DIR = args.label_dir
            
            ds = CustomDataset(
                img_dir = IMG_DIR,
                label_dir = LABEL_DIR,
                transform = transform,
                width=img_size[0], 
                height=img_size[1],
                length=length,
                C = num_classes
            )
        
        test_dl = DataLoader(ds, batch_size=args.batch_size, shuffle=True)
        
        print(f"Dataset Length: {len(ds)}")
        print('Load Dataset Complete')
        
        # 여기서부터 짜면 된다.
        evaluate(model, test_dl, device, num_classes, iou_threshold=args.iou_threshold)
        
    elif args.mode == 'inference':
        # Load Trained Model
        model = None
        if args.model == 1:
            model = Yolov1(split_size=7, num_boxes=2, num_classes=num_classes, width=img_size[0], height=img_size[1]).to(device)
        elif args.model == 2:
            model = BBBasedYolov1(split_size=7, num_boxes=2, num_classes=num_classes, width=img_size[0], height=img_size[1]).to(device)
        
        model.load_state_dict(torch.load(os.path.join('saved', args.file_name), map_location=device))
        model.eval()
        print('Load Model Complete')
        
        cap = cv2.VideoCapture(args.video_loc)
        
        transform = transforms.ToTensor()
        
        while(cap.isOpened()):
            ret, frame = cap.read()
            frame = cv2.resize(frame, dsize=(960, 540))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            x = transform(frame)
            x = x.reshape(-1, *x.shape)

            pred = model(x).reshape(-1, 7, 7, 13)
            pred[0, ..., 3] = (pred[0,...,3] > 0.3)*1
            pred[0, ..., 8] = (pred[0,...,8] > 0.3)*1
            imgshow(x[0].detach().cpu(), pred[0].detach().cpu())
            
            if cv2.waitKey(1) == ord('q'):
                break
            
        cap.release()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser("Yolo training and evaluation Script", parents=[get_args_parser()])
    args = parser.parse_args()
    
    if torch.cuda.is_available():
        print('You can use GPU')
    else:
        print('There is no GPU')
    
    print('Proceed? [Y/N]: ', end="")
    proceed_ = input()
    if proceed_.lower() == 'y':
        pass
    else:
        print('EXIT')
        sys.exit()
    
    main(args)