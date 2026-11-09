"""Train a baseline and ResNet18, select on validation, then evaluate held-out test.

python -m ml.train --manifest ml/data/manifest.json --output ml/runs/food-v1
"""
import argparse
import csv
import importlib.metadata
import json
import platform
import random
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support, log_loss
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms

from .data import digest, load_manifest, write_json

NORMALIZE = {'mean': [.485, .456, .406], 'std': [.229, .224, .225]}


def transform(size, augment=False):
    ops = [transforms.Resize((size, size))]
    if augment:
        ops += [transforms.RandomHorizontalFlip(), transforms.RandomRotation(10)]
    return transforms.Compose(ops + [transforms.ToTensor(), transforms.Normalize(**NORMALIZE)])


class Images(Dataset):
    def __init__(self, manifest, split, size, augment=False):
        self.rows = [r for r in manifest['images'] if r['split'] == split]
        self.root = Path(manifest['source'])
        self.labels = manifest['classes']
        self.transform = transform(size, augment)

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        with Image.open(self.root / row['path']) as image:
            tensor = self.transform(ImageOps.exif_transpose(image).convert('RGB'))
        return tensor, self.labels.index(row['label'])


def color_features(manifest, split):
    """Intentionally simple baseline: per-channel 16-bin normalized histograms."""
    features, labels = [], []
    for row in manifest['images']:
        if row['split'] != split:
            continue
        with Image.open(Path(manifest['source']) / row['path']) as image:
            image = np.asarray(ImageOps.exif_transpose(image).convert('RGB').resize((64, 64)))
        features.append(np.concatenate([np.histogram(image[:, :, c], bins=16, range=(0, 256))[0] / 4096 for c in range(3)]))
        labels.append(manifest['classes'].index(row['label']))
    return np.array(features), np.array(labels)


def metrics(labels, probabilities, classes, threshold):
    labels, probabilities = np.array(labels), np.array(probabilities)
    predicted = probabilities.argmax(axis=1)
    confidence = probabilities.max(axis=1)
    precision, recall, f1, support = precision_recall_fscore_support(
        labels, predicted, labels=list(range(len(classes))), zero_division=0)
    accepted = confidence >= threshold
    ece = 0.
    for i in range(10):
        selected = (confidence >= i/10) & (confidence < (i+1)/10 if i < 9 else confidence <= 1)
        if selected.any():
            ece += float(selected.mean()) * abs(float(confidence[selected].mean()) - float((predicted[selected] == labels[selected]).mean()))
    return {'accuracy': float(accuracy_score(labels, predicted)), 'macro_f1': float(f1.mean()),
            'top3_accuracy': float(np.mean([y in np.argsort(p)[-min(3, len(classes)):] for y, p in zip(labels, probabilities)])),
            'log_loss': float(log_loss(labels, probabilities, labels=list(range(len(classes))))),
            'expected_calibration_error_10_bins': ece, 'threshold': float(threshold),
            'coverage': float(accepted.mean()),
            'accepted_accuracy': float((predicted[accepted] == labels[accepted]).mean()) if accepted.any() else None,
            'count': len(labels), 'confusion_matrix': confusion_matrix(labels, predicted, labels=list(range(len(classes)))).tolist(),
            'per_class': {name: {'precision': float(precision[i]), 'recall': float(recall[i]),
                                 'f1': float(f1[i]), 'support': int(support[i])} for i, name in enumerate(classes)}}


def choose_threshold(labels, probabilities, target=.8):
    confidence, prediction = probabilities.max(axis=1), probabilities.argmax(axis=1)
    for threshold in (.5, .6, .7, .8, .9, .95, .99):
        selected = confidence >= threshold
        if selected.mean() >= .1 and (prediction[selected] == labels[selected]).mean() >= target:
            return threshold
    return 1.0  # No validation threshold met the target: abstain, rather than claim confidence.


@torch.inference_mode()
def logits_for(model, loader, device):
    model.eval()
    logits, labels = [], []
    for inputs, targets in loader:
        logits.append(model(inputs.to(device)).cpu())
        labels.append(targets)
    return torch.cat(logits), torch.cat(labels)


def table_report(run, baseline, validation, test, metadata):
    def row(name, values):
        return f'| {name} | {values["accuracy"]:.3f} | {values["macro_f1"]:.3f} | {values["top3_accuracy"]:.3f} |'
    lines = ['# Bloom food model experiment', '', f'Purpose: **{metadata["purpose"]}**.', '',
             'Validation selected the checkpoint, temperature and abstention threshold. Test data was evaluated afterward.',
             'The test split is an internal subset holdout, not the official Food-101 benchmark.', '',
             '| Held-out test model | Accuracy | Macro F1 | Top-3 accuracy |', '|---|---:|---:|---:|',
             row('Color histogram + logistic regression', baseline), row('ResNet18', test), '',
             f'Validation macro F1: {validation["macro_f1"]:.3f}. Selected epoch: {metadata["best_epoch"]}.',
             f'Test coverage at threshold {test["threshold"]}: {test["coverage"]:.3f}.',
             f'Accuracy on accepted predictions: {test["accepted_accuracy"]}.',
             'Coverage and conditional accuracy must be read together; confidence is not a guarantee on unfamiliar images.', '',
             f'Inference latency, batch 1 on {metadata["device"]}: median {metadata["latency_ms"]["median"]:.1f} ms, p95 {metadata["latency_ms"]["p95"]:.1f} ms.', '',
             '## Limitations', '', 'Single dominant dish only; no multi-food detection, portion estimation or nutrient inference.',
             'Internal data may not reflect real user photos. Near-duplicate hashes are a heuristic; meal/source groups must also be provided when known.',
             'ImageNet pretraining may contain visually related data; this is transfer learning, not training from scratch.',
             'External photos and out-of-distribution behavior still need independent evaluation.', '',
             'Inspect failures.json, confusion-matrix.csv, metrics.json, config.json and history.json.']
    if metadata['purpose'] == 'functional_smoke':
        lines.insert(3, '**SYNTHETIC FUNCTIONAL TEST. These scores are not food recognition evidence. Not eligible for app deployment.**')
    (run / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def train(args):
    run = Path(args.output).resolve()
    if run.exists():
        raise ValueError('Run directory exists. Use a new output for each experiment.')
    if args.epochs < 1 or not 0 <= args.freeze_epochs <= args.epochs or args.batch_size < 1 or not 32 <= args.size <= 512 or args.threads < 1 or args.lr <= 0:
        raise ValueError('Check epochs, freeze epochs, batch size, size (32-512), threads and learning rate.')
    manifest = load_manifest(args.manifest)
    if (manifest['purpose'] == 'functional_smoke') != args.smoke:
        raise ValueError('Synthetic manifests require --smoke; real data must not use --smoke.')
    if not args.smoke and args.weights == 'none':
        print('Training from random initialization; label this separately from transfer learning.', flush=True)
    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    torch.set_num_threads(args.threads)
    torch.use_deterministic_algorithms(True)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
        torch.backends.cudnn.benchmark = False
    device = torch.device('cuda' if args.device == 'auto' and torch.cuda.is_available() else 'cpu' if args.device == 'auto' else args.device)
    datasets = {split: Images(manifest, split, args.size, split == 'train') for split in ('train', 'val', 'test')}
    # workers=0 also keeps Windows execution and exact reruns predictable.
    generator = torch.Generator().manual_seed(args.seed)
    loaders = {split: DataLoader(ds, batch_size=args.batch_size, shuffle=split == 'train', num_workers=0, generator=generator)
               for split, ds in datasets.items()}
    if len(datasets['train']) < 2:
        raise ValueError('Need at least two training images.')
    weights = models.ResNet18_Weights.IMAGENET1K_V1 if args.weights == 'imagenet' else None
    model = models.resnet18(weights=weights)
    model.fc = nn.Linear(model.fc.in_features, len(manifest['classes']))
    model.to(device)
    run.mkdir(parents=True)
    artifact = run / 'artifact'; artifact.mkdir()
    config = vars(args).copy()
    write_json(run / 'config.json', config)
    write_json(run / 'manifest.json', manifest)
    tracker = None
    completed = False
    if args.mlflow_uri:
        import mlflow
        tracker = mlflow
        tracker.set_tracking_uri(args.mlflow_uri)
        tracker.set_experiment('bloom-food-recognition')
        tracker.start_run(run_name=run.name)
        tracker.log_params({k: v for k, v in config.items() if v is not None})
    try:
        history, best, best_epoch = [], -1., 0
        for epoch in range(args.epochs):
            frozen = epoch < args.freeze_epochs
            for name, parameter in model.named_parameters():
                parameter.requires_grad = not frozen or name.startswith('fc.')
            if epoch == 0 or epoch == args.freeze_epochs:
                optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=args.lr if frozen else args.lr/10)
            model.train()
            if frozen:
                # Keep backbone BatchNorm running statistics frozen too.
                model.eval(); model.fc.train()
            loss_sum, count = 0., 0
            for inputs, targets in loaders['train']:
                # BatchNorm cannot train on a final one-image 1x1 feature map.
                if len(targets) == 1 and not frozen:
                    model.eval()
                else:
                    model.train(not frozen)
                    if frozen: model.fc.train()
                inputs, targets = inputs.to(device), targets.to(device)
                optimizer.zero_grad(set_to_none=True)
                loss = nn.functional.cross_entropy(model(inputs), targets)
                loss.backward(); optimizer.step()
                loss_sum += float(loss.detach()) * len(targets); count += len(targets)
            val_logits, val_labels = logits_for(model, loaders['val'], device)
            score = metrics(val_labels.numpy(), val_logits.softmax(1).numpy(), manifest['classes'], .5)
            record = {'epoch': epoch+1, 'train_loss': loss_sum/count, 'val_macro_f1': score['macro_f1'],
                      'val_accuracy': score['accuracy'], 'frozen_backbone': frozen}
            history.append(record)
            write_json(run / 'history.json', history)
            print(json.dumps(record), flush=True)
            if tracker:
                tracker.log_metrics({k: float(v) for k, v in record.items() if k != 'epoch'}, step=epoch+1)
            if score['macro_f1'] > best:
                best, best_epoch = score['macro_f1'], epoch+1
                torch.save({k: v.detach().cpu() for k, v in model.state_dict().items()}, artifact / 'weights.pt')
        model.load_state_dict(torch.load(artifact / 'weights.pt', map_location=device, weights_only=True))
        val_logits, val_labels = logits_for(model, loaders['val'], device)
        temperatures = [.5, .75, 1., 1.5, 2., 3., 5.]
        temperature = min(temperatures, key=lambda t: float(nn.functional.cross_entropy(val_logits/t, val_labels)))
        val_probabilities = (val_logits/temperature).softmax(1).numpy()
        threshold = choose_threshold(val_labels.numpy(), val_probabilities)
        validation = metrics(val_labels.numpy(), val_probabilities, manifest['classes'], threshold)
        test_logits, test_labels = logits_for(model, loaders['test'], device)
        test_probabilities = (test_logits/temperature).softmax(1).numpy()
        test = metrics(test_labels.numpy(), test_probabilities, manifest['classes'], threshold)
        baseline_x, baseline_y = color_features(manifest, 'train')
        baseline = LogisticRegression(max_iter=1000, random_state=args.seed).fit(baseline_x, baseline_y)
        test_x, test_y = color_features(manifest, 'test')
        baseline_result = metrics(test_y, baseline.predict_proba(test_x), manifest['classes'], .5)
        durations = []
        model.eval()
        sample = datasets['test'][0][0].unsqueeze(0).to(device)
        with torch.inference_mode():
            for i in range(23):
                if device.type == 'cuda': torch.cuda.synchronize()
                started = time.perf_counter(); model(sample)
                if device.type == 'cuda': torch.cuda.synchronize()
                if i >= 3: durations.append((time.perf_counter()-started)*1000)
        metadata = {'format': 'bloom-resnet18-v1', 'model_id': run.name, 'purpose': manifest['purpose'],
                    'architecture': 'resnet18', 'classes': manifest['classes'], 'size': args.size,
                    'normalization': NORMALIZE, 'temperature': temperature, 'threshold': threshold,
                    'best_epoch': best_epoch, 'weights': args.weights, 'seed': args.seed,
                    'weights_sha256': digest((artifact/'weights.pt').read_bytes()),
                    'manifest_sha256': digest(Path(args.manifest).read_bytes()),
                    'code_sha256': digest(b''.join(p.read_bytes() for p in sorted(Path(__file__).parent.glob('*.py')))),
                    'device': str(device), 'latency_ms': {'median': float(np.median(durations)), 'p95': float(np.percentile(durations, 95))},
                    'versions': {p: importlib.metadata.version(p) for p in ('torch', 'torchvision', 'Pillow', 'numpy', 'scikit-learn')},
                    'python': platform.python_version(), 'test_metrics': test,
                    'class_counts': {s: dict(Counter(r['label'] for r in manifest['images'] if r['split'] == s)) for s in datasets},
                    'training_image_hashes': [r['sha256'] for r in manifest['images']],
                    'scope': 'Single dominant food classification. No portion or nutrient estimation.'}
        write_json(artifact/'metadata.json', metadata)
        write_json(run/'metrics.json', {'baseline_test': baseline_result, 'validation': validation, 'test': test})
        failures = [{'path': r['path'], 'true_label': r['label'], 'predicted': manifest['classes'][int(p.argmax())],
                     'confidence': float(p.max())} for r, p in zip(datasets['test'].rows, test_probabilities)
                    if manifest['classes'][int(p.argmax())] != r['label']]
        write_json(run/'failures.json', failures)
        with (run/'confusion-matrix.csv').open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream); writer.writerow(['true / predicted'] + manifest['classes'])
            writer.writerows([name] + counts for name, counts in zip(manifest['classes'], test['confusion_matrix']))
        table_report(run, baseline_result, validation, test, metadata)
        if tracker:
            tracker.log_metrics({'test_'+k: v for k, v in test.items() if isinstance(v, (int, float))})
            for name in ('REPORT.md', 'metrics.json', 'history.json', 'failures.json', 'config.json', 'confusion-matrix.csv'):
                tracker.log_artifact(str(run/name))
            tracker.log_artifacts(str(artifact), artifact_path='model')
        print(f'Completed {run}. Read REPORT.md before selecting an artifact.', flush=True)
        completed = True
        return metadata
    finally:
        if tracker: tracker.end_run(status='FINISHED' if completed else 'FAILED')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--epochs', type=int, default=5)
    parser.add_argument('--freeze-epochs', type=int, default=1)
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--size', type=int, default=160)
    parser.add_argument('--lr', type=float, default=.001)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--device', choices=['auto', 'cpu', 'cuda'], default='auto')
    parser.add_argument('--weights', choices=['imagenet', 'none'], default='imagenet')
    parser.add_argument('--smoke', action='store_true', help='Synthetic functional verification only; artifact cannot serve Bloom.')
    parser.add_argument('--mlflow-uri', help='Optional MLflow tracking URI; install mlflow separately. Explicit opt-in upload of experiment artifacts.')
    train(parser.parse_args())


if __name__ == '__main__':
    main()
