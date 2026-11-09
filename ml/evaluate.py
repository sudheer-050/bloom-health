"""Evaluate a trained model on a separate, labeled image-folder dataset.

python -m ml.evaluate --model-dir ml/runs/food-v1/artifact --source path/to/new-photos --output ml/runs/external-v1.json
"""
import argparse
import json
from pathlib import Path

from .data import SUFFIXES, image_info, write_json
from .inference import LocalRecognizer


def evaluate(directory, source, output):
    import numpy as np
    import torch
    from PIL import Image, ImageOps
    from .train import metrics, transform
    if Path(output).exists():
        raise ValueError('Evaluation output exists. Choose a new output.')
    recognizer = LocalRecognizer(directory)
    metadata = recognizer.read_metadata()
    root = Path(source).resolve()
    classes = metadata['classes']
    unknown = [p.name for p in root.iterdir() if p.is_dir() and p.name not in classes]
    if unknown:
        raise ValueError('Unknown class folders: ' + ', '.join(unknown) + '. Evaluate unfamiliar images separately; closed-set scores do not measure OOD detection.')
    paths = sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in SUFFIXES)
    if not paths:
        raise ValueError('No labeled external images found.')
    labels, probabilities, failures, seen = [], [], [], set()
    transform_image = transform(metadata['size'])
    # Reject known training/validation/test images; also compare decoded and perceptual hashes.
    manifest = json.loads((Path(directory).parent/'manifest.json').read_text(encoding='utf-8'))
    known = {r['sha256'] for r in manifest['images']}
    known_pixels = {r['pixel_sha256'] for r in manifest['images']}
    known_dhash = [int(r['dhash'], 16) for r in manifest['images']]
    for path in paths:
        if root not in path.resolve().parents or path.parent.name not in classes:
            raise ValueError('External images must be inside named class folders.')
        info = image_info(path)
        if info['sha256'] in known or info['pixel_sha256'] in known_pixels or any((int(info['dhash'], 16)^h).bit_count() <= 2 for h in known_dhash):
            raise ValueError('External evaluation overlaps with experiment data: ' + path.name)
        if info['pixel_sha256'] in seen:
            raise ValueError('Duplicate external image: ' + path.name)
        seen.add(info['pixel_sha256'])
        recognizer.predict(path.read_bytes())  # Loads the checked artifact; reused below for full class scores.
        with Image.open(path) as image:
            tensor = transform_image(ImageOps.exif_transpose(image).convert('RGB')).unsqueeze(0)
        with torch.inference_mode():
            p = (recognizer.model(tensor)[0]/metadata['temperature']).softmax(0).numpy()
        label = classes.index(path.parent.name)
        labels.append(label); probabilities.append(p)
        if int(p.argmax()) != label:
            failures.append({'path': path.relative_to(root).as_posix(), 'true_label': classes[label],
                             'predicted': classes[int(p.argmax())], 'score': float(p.max())})
    result = {'model_id': metadata['model_id'], 'evaluation': 'external labeled photos',
              'metrics': metrics(np.array(labels), np.array(probabilities), classes, metadata['threshold']),
              'missing_classes': [c for c in classes if classes.index(c) not in labels], 'failures': failures,
              'note': 'Exact/near image overlap rejected. Confirm source/meal separation manually. No OOD detection claim.'}
    write_json(output, result)
    print(json.dumps(result['metrics'], indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    evaluate(args.model_dir, args.source, args.output)
