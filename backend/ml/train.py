#!/usr/bin/env python3
"""Entraîne un classifieur de condition de jeu vidéo (loose/cib/new/graded).

Utilise MobileNetV2 pré-entraîné avec fine-tuning de la dernière couche.
Dataset attendu dans dataset/{loose,cib,new,graded}/*.jpg

Usage :
    python ml/train.py --data dataset --epochs 15 --batch-size 32
    python ml/train.py --data dataset --epochs 15 --unfreeze 30  # fine-tune plus de couches

Produit :
    ml/condition_model.pth     — poids du modèle
    ml/class_names.txt         — mapping index → classe
    ml/training_log.txt        — historique loss/accuracy
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split
from torchvision import datasets, models, transforms

CLASSES = ["loose", "cib", "new", "graded"]
IMG_SIZE = 224
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def get_transforms(train: bool):
    if train:
        return transforms.Compose([
            transforms.Resize((IMG_SIZE + 32, IMG_SIZE + 32)),
            transforms.RandomCrop(IMG_SIZE),
            transforms.RandomHorizontalFlip(),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
            transforms.RandomRotation(10),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
    return transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])


def build_model(num_classes: int, unfreeze_last: int = 0) -> nn.Module:
    model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.DEFAULT)

    # Geler toutes les couches
    for param in model.parameters():
        param.requires_grad = False

    # Dégeler les N dernières couches du backbone si demandé
    if unfreeze_last > 0:
        features = list(model.features.children())
        for layer in features[-unfreeze_last:]:
            for param in layer.parameters():
                param.requires_grad = True

    # Remplacer le classifieur
    model.classifier = nn.Sequential(
        nn.Dropout(0.3),
        nn.Linear(model.last_channel, num_classes),
    )

    return model


def compute_class_weights(dataset) -> torch.Tensor:
    """Poids inversement proportionnels à la fréquence de chaque classe."""
    counts = [0] * len(dataset.classes)
    for _, label in dataset.samples:
        counts[label] += 1
    total = sum(counts)
    weights = [total / (len(counts) * c) if c > 0 else 1.0 for c in counts]
    return torch.FloatTensor(weights).to(DEVICE)


def train_one_epoch(model, loader, criterion, optimizer):
    model.train()
    total_loss = 0
    correct = 0
    total = 0

    for images, labels in loader:
        images, labels = images.to(DEVICE), labels.to(DEVICE)
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * images.size(0)
        _, predicted = outputs.max(1)
        correct += predicted.eq(labels).sum().item()
        total += labels.size(0)

    return total_loss / total, correct / total


def evaluate(model, loader, criterion):
    model.eval()
    total_loss = 0
    correct = 0
    total = 0

    with torch.no_grad():
        for images, labels in loader:
            images, labels = images.to(DEVICE), labels.to(DEVICE)
            outputs = model(images)
            loss = criterion(outputs, labels)

            total_loss += loss.item() * images.size(0)
            _, predicted = outputs.max(1)
            correct += predicted.eq(labels).sum().item()
            total += labels.size(0)

    return total_loss / total, correct / total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="dataset", help="Dossier dataset")
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--val-split", type=float, default=0.2)
    parser.add_argument("--unfreeze", type=int, default=0,
                        help="Nombre de couches backbone à dégeler (0=head only)")
    parser.add_argument("--output-dir", default="ml", help="Dossier de sortie du modèle")
    parser.add_argument("--model-name", default="condition", help="Préfixe des fichiers de sortie (condition, console)")
    args = parser.parse_args()

    data_dir = Path(args.data)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Dataset complet avec transforms train
    full_dataset = datasets.ImageFolder(str(data_dir), transform=get_transforms(train=True))
    print(f"Classes: {full_dataset.classes}")
    print(f"Total images: {len(full_dataset)}")

    for cls, idx in full_dataset.class_to_idx.items():
        count = sum(1 for _, l in full_dataset.samples if l == idx)
        print(f"  {cls}: {count}")

    # Split train/val
    val_size = int(len(full_dataset) * args.val_split)
    train_size = len(full_dataset) - val_size
    train_dataset, val_dataset = random_split(
        full_dataset, [train_size, val_size],
        generator=torch.Generator().manual_seed(42),
    )

    # Appliquer les transforms val au val_dataset
    val_dataset.dataset = datasets.ImageFolder(str(data_dir), transform=get_transforms(train=False))

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=2)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=2)

    print(f"\nTrain: {train_size}, Val: {val_size}")
    print(f"Device: {DEVICE}")

    # Modèle
    model = build_model(len(full_dataset.classes), unfreeze_last=args.unfreeze).to(DEVICE)

    # Poids de classe pour gérer le déséquilibre loose >> cib >> new >> graded
    class_weights = compute_class_weights(full_dataset)
    print(f"Class weights: {class_weights.tolist()}")

    criterion = nn.CrossEntropyLoss(weight=class_weights)
    optimizer = optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=args.lr)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=5, gamma=0.5)

    # Training loop
    best_val_acc = 0
    log_lines = []

    for epoch in range(1, args.epochs + 1):
        train_loss, train_acc = train_one_epoch(model, train_loader, criterion, optimizer)
        val_loss, val_acc = evaluate(model, val_loader, criterion)
        scheduler.step()

        line = (
            f"Epoch {epoch:02d}/{args.epochs} — "
            f"train_loss={train_loss:.4f} train_acc={train_acc:.4f} — "
            f"val_loss={val_loss:.4f} val_acc={val_acc:.4f}"
        )
        print(line)
        log_lines.append(line)

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            model_file = output_dir / f"{args.model_name}_model.pth"
            torch.save(model.state_dict(), model_file)
            print(f"  → Meilleur modèle sauvé (val_acc={val_acc:.4f})")

    # Sauver les noms de classes
    classes_file = output_dir / f"{args.model_name}_class_names.txt" if args.model_name != "condition" else output_dir / "class_names.txt"
    classes_file.write_text("\n".join(full_dataset.classes) + "\n")
    (output_dir / f"{args.model_name}_training_log.txt").write_text("\n".join(log_lines) + "\n")

    print(f"\nEntraînement terminé. Best val_acc: {best_val_acc:.4f}")
    print(f"Modèle: {output_dir / f'{args.model_name}_model.pth'}")
    print(f"Classes: {classes_file}")


if __name__ == "__main__":
    main()
