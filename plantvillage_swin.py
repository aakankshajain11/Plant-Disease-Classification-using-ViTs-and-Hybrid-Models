# -*- coding: utf-8 -*-
"""plantvillage_SWin.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/19vfjSqu7xh3fx0mm9Ttx3QgFZwdno0pd
"""

# Install dependencies
!pip install kaggle timm torchvision matplotlib scikit-learn seaborn --quiet

# Step 1: Upload Kaggle API Key
from google.colab import files
uploaded = files.upload()  # Upload kaggle.json here

import os, zipfile
kaggle_json = list(uploaded.keys())[0]
os.environ['KAGGLE_CONFIG_DIR'] = "/root/.kaggle"
os.makedirs(os.environ['KAGGLE_CONFIG_DIR'], exist_ok=True)
os.rename(kaggle_json, f"{os.environ['KAGGLE_CONFIG_DIR']}/kaggle.json")

# Step 2: Download and Extract PlantVillage dataset
!kaggle datasets download -d emmarex/plantdisease
with zipfile.ZipFile("plantdisease.zip", 'r') as zip_ref:
    zip_ref.extractall("PlantVillage")

# Step 3: Organize dataset into train/val/test
import shutil, os, random
from collections import defaultdict

base_dir = "PlantVillage/PlantVillage"
output_dirs = ['train', 'val', 'test']

for d in output_dirs:
    for cls in os.listdir(base_dir):
        os.makedirs(os.path.join(d, cls), exist_ok=True)

for cls in os.listdir(base_dir):
    cls_path = os.path.join(base_dir, cls)
    images = os.listdir(cls_path)
    random.shuffle(images)
    n = len(images)
    n_train, n_val = int(0.8 * n), int(0.1 * n)

    for i, img in enumerate(images):
        src = os.path.join(cls_path, img)
        if i < n_train:
            dst = os.path.join('train', cls, img)
        elif i < n_train + n_val:
            dst = os.path.join('val', cls, img)
        else:
            dst = os.path.join('test', cls, img)
        shutil.copyfile(src, dst)

# Step 4: Imports
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from timm import create_model
import matplotlib.pyplot as plt
from sklearn.metrics import classification_report, confusion_matrix, roc_curve, auc, roc_auc_score
from sklearn.preprocessing import label_binarize
import seaborn as sns
import numpy as np
import time

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

# Step 5: Data Augmentation
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.RandomHorizontalFlip(),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406],
                         [0.229, 0.224, 0.225])
])

train_data = datasets.ImageFolder("train", transform=transform)
val_data = datasets.ImageFolder("val", transform=transform)
test_data = datasets.ImageFolder("test", transform=transform)

train_loader = DataLoader(train_data, batch_size=32, shuffle=True)
val_loader = DataLoader(val_data, batch_size=32, shuffle=False)
test_loader = DataLoader(test_data, batch_size=32, shuffle=False)

class_names = train_data.classes
num_classes = len(class_names)

# Step 6: Load Swin Transformer
model = create_model(
    'swin_tiny_patch4_window7_224',
    pretrained=True,
    num_classes=num_classes,
    global_pool='avg'
)
model.to(device)

# Freeze backbone, train only classifier head
for param in model.parameters():
    param.requires_grad = False
for param in model.head.parameters():
    param.requires_grad = True

criterion = nn.CrossEntropyLoss()
optimizer = optim.AdamW(model.parameters(), lr=1e-4)
scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', patience=3)

# Step 7: Train
train_losses, val_losses, train_accs, val_accs = [], [], [], []
start = time.time()
epochs = 10

for epoch in range(epochs):
    model.train()
    total_loss, correct = 0.0, 0

    for images, labels in train_loader:
        images, labels = images.to(device), labels.to(device)
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * images.size(0)
        correct += (outputs.argmax(1) == labels).sum().item()

    train_losses.append(total_loss / len(train_loader.dataset))
    train_accs.append(correct / len(train_loader.dataset))

    # Validation
    model.eval()
    val_loss, val_correct = 0.0, 0
    with torch.no_grad():
        for images, labels in val_loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            val_loss += criterion(outputs, labels).item() * images.size(0)
            val_correct += (outputs.argmax(1) == labels).sum().item()

    val_losses.append(val_loss / len(val_loader.dataset))
    val_accs.append(val_correct / len(val_loader.dataset))

    print(f"Epoch {epoch+1}/{epochs} | Train Acc: {train_accs[-1]:.4f} | Val Acc: {val_accs[-1]:.4f}")

end = time.time()
training_time = end - start

# Step 8: Loss and Accuracy Plot
plt.plot(train_losses, label='Train Loss')
plt.plot(val_losses, label='Val Loss')
plt.title('Loss')
plt.legend()
plt.show()

plt.plot(train_accs, label='Train Acc')
plt.plot(val_accs, label='Val Acc')
plt.title('Accuracy')
plt.legend()
plt.show()

# Step 9: Test Evaluation
model.eval()
y_true, y_pred, y_probs = [], [], []
with torch.no_grad():
    for images, labels in test_loader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        y_probs.extend(outputs.cpu().numpy())
        y_pred.extend(outputs.argmax(1).cpu().numpy())
        y_true.extend(labels.cpu().numpy())

test_accuracy = np.mean(np.array(y_true) == np.array(y_pred))
print(f"\n✅ Test Accuracy: {test_accuracy * 100:.2f}%")

# Step 10: Metrics
print("\n📊 Classification Report:")
print(classification_report(y_true, y_pred, target_names=class_names))

cm = confusion_matrix(y_true, y_pred)
plt.figure(figsize=(10, 8))
sns.heatmap(cm, annot=True, fmt='d', xticklabels=class_names, yticklabels=class_names, cmap='Blues')
plt.title("Confusion Matrix")
plt.show()

# AUC-ROC
y_true_bin = label_binarize(y_true, classes=list(range(num_classes)))
y_probs = np.array(y_probs)

plt.figure(figsize=(12, 8))
for i in range(num_classes):
    fpr, tpr, _ = roc_curve(y_true_bin[:, i], y_probs[:, i])
    roc_auc = auc(fpr, tpr)
    plt.plot(fpr, tpr, lw=2, label=f"{class_names[i]} (AUC = {roc_auc:.2f})")

plt.plot([0, 1], [0, 1], 'k--')
plt.title("AUC-ROC Curve")
plt.xlabel("False Positive Rate")
plt.ylabel("True Positive Rate")
plt.legend()
plt.grid(True)
plt.show()

print(f"🧮 Macro AUC: {roc_auc_score(y_true_bin, y_probs, average='macro'):.4f}")
print(f"🧮 Weighted AUC: {roc_auc_score(y_true_bin, y_probs, average='weighted'):.4f}")

# Step 11: Summary
model_size_MB = sum(p.numel() for p in model.parameters()) * 4 / (1024 ** 2)
print(f"\n⏱️ Training Time: {training_time:.2f} seconds")
print(f"📦 Model Size: {model_size_MB:.2f} MB")
print(f"✅ Final Train Accuracy: {train_accs[-1] * 100:.2f}%")
print(f"✅ Final Val Accuracy: {val_accs[-1] * 100:.2f}%")