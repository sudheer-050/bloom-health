"""Prepare reproducible, group-aware image manifests without copying user data.

python -m ml.data prepare --source path/to/class-folders --output ml/data/manifest.json
python -m ml.data food101 --root ml/data --download --output ml/data/manifest.json
python -m ml.data import-reviews --source path/to/exports --output ml/data/reviewed
"""
import argparse
import base64
import csv
import hashlib
import io
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

CLASSES = ['apple_pie', 'chicken_curry', 'fried_rice', 'grilled_salmon', 'hamburger',
           'omelette', 'pizza', 'spaghetti_bolognese', 'steak', 'sushi']
SUFFIXES = {'.jpg', '.jpeg', '.png', '.webp'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def image_info(path):
    from PIL import Image, ImageOps
    raw = path.read_bytes()
    if len(raw) > 15 * 1024 * 1024:
        raise ValueError(f'Image exceeds 15 MB: {path.name}')
    with Image.open(io.BytesIO(raw)) as opened:
        image = ImageOps.exif_transpose(opened).convert('RGB')
        if min(image.size) < 16:
            raise ValueError(f'Image too small: {path.name}')
        pixels = digest(str(image.size).encode() + image.tobytes())
        thumb_image = image.convert('L').resize((9, 8))
        thumb = [thumb_image.getpixel((x, y)) for y in range(8) for x in range(9)]
        dhash = sum((thumb[y*9+x] > thumb[y*9+x+1]) << (y*8+x)
                    for y in range(8) for x in range(8))
    return {'sha256': digest(raw), 'pixel_sha256': pixels, 'dhash': f'{dhash:016x}'}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def build_manifest(source, output, seed=42, per_class=100, classes=None, groups_file=None,
                   purpose='food_research', near_distance=2):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Manifest exists. Choose a new output to preserve the previous experiment.')
    groups = {}
    if groups_file:
        with Path(groups_file).open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                if not row.get('path') or not row.get('group'):
                    raise ValueError('Groups CSV needs path,group columns.')
                if row['path'] in groups:
                    raise ValueError('Duplicate path in groups CSV.')
                groups[row['path']] = row['group']
    names = sorted(classes or [p.name for p in source.iterdir() if p.is_dir()])
    if len(names) < 2 or len(set(names)) != len(names):
        raise ValueError('Use at least two distinct class folders.')
    rows, rng = [], random.Random(seed)
    for label in names:
        folder = (source / label).resolve()
        if folder.parent != source:
            raise ValueError('Class names must be immediate folder names.')
        paths = sorted(p for p in folder.rglob('*') if p.suffix.lower() in SUFFIXES and p.is_file())
        rng.shuffle(paths)
        for path in paths[:per_class]:
            path = path.resolve()
            if source not in path.parents:
                raise ValueError('Image paths must stay inside the dataset.')
            relative = path.relative_to(source).as_posix()
            rows.append({'path': relative, 'label': label, **image_info(path),
                         'group': groups.get(relative, '')})
    # ponytail: quadratic near-duplicate check for small portfolio subsets.
    # For large datasets, replace this with indexed perceptual similarity search.
    if len(rows) > 5000:
        raise ValueError('Use at most 5,000 images for this subset preparer.')
    parents = list(range(len(rows)))
    def find(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    hashes = [int(r['dhash'], 16) for r in rows]
    for i, row in enumerate(rows):
        for j in range(i):
            other = rows[j]
            same_image = row['pixel_sha256'] == other['pixel_sha256']
            same_group = row['group'] and row['group'] == other['group']
            near = (hashes[i] ^ hashes[j]).bit_count() <= near_distance
            if same_image or near or same_group:
                parents[find(i)] = find(j)
    grouped = defaultdict(list)
    for i, row in enumerate(rows):
        grouped[find(i)].append(row)
    by_class = defaultdict(list)
    for members in grouped.values():
        if len({r['label'] for r in members}) > 1:
            raise ValueError('Duplicate, near-duplicate or same-meal group has conflicting labels: ' +
                             ', '.join(r['path'] for r in members[:5]))
        by_class[members[0]['label']].append(members)
    duplicates = 0
    kept = []
    for label in names:
        buckets = by_class[label]
        if len(buckets) < 6:
            raise ValueError(f'{label}: need at least 6 independent image groups (prefer 50+).')
        rng.shuffle(buckets)
        val_n = max(1, round(len(buckets) * .15))
        test_n = max(1, round(len(buckets) * .15))
        for index, members in enumerate(buckets):
            split = 'val' if index < val_n else 'test' if index < val_n + test_n else 'train'
            group_id = digest('|'.join(sorted(r['sha256'] for r in members)).encode())
            seen = set()
            for row in members:
                if row['pixel_sha256'] in seen:
                    duplicates += 1
                    continue
                seen.add(row['pixel_sha256'])
                kept.append({**row, 'group': group_id, 'split': split})
    if groups and set(groups) - {r['path'] for r in rows}:
        raise ValueError('Some groups CSV paths were not sampled. Raise --per-class or check paths.')
    result = {'format': 'bloom-images-v1', 'purpose': purpose, 'source': str(source),
              'seed': seed, 'classes': names, 'split_policy': '70/15/15 stratified by image/meal group',
              'near_duplicate_hamming_distance': near_distance, 'duplicates_removed': duplicates,
              'counts': dict(Counter(r['split'] for r in kept)), 'images': kept}
    write_json(output, result)
    print(json.dumps({'manifest': str(output), 'counts': result['counts'],
                      'classes': names, 'duplicates_removed': duplicates}), flush=True)
    return result


def load_manifest(path, verify=True):
    path = Path(path)
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('format') != 'bloom-images-v1' or len(data.get('classes', [])) < 2:
        raise ValueError('Invalid Bloom image manifest.')
    root = Path(data['source']).resolve()
    split_groups, hashes = {}, set()
    for row in data['images']:
        image_path = (root / row['path']).resolve()
        if root not in image_path.parents or row['label'] not in data['classes'] or row['split'] not in ('train', 'val', 'test'):
            raise ValueError('Invalid image path, label or split.')
        if row['group'] in split_groups and split_groups[row['group']] != row['split']:
            raise ValueError('Data leakage: an image group appears in multiple splits.')
        split_groups[row['group']] = row['split']
        if row['sha256'] in hashes:
            raise ValueError('Duplicate image in manifest.')
        hashes.add(row['sha256'])
        if verify and image_info(image_path) != {k: row[k] for k in ('sha256', 'pixel_sha256', 'dhash')}:
            raise ValueError(f'Image changed after preparation: {row["path"]}')
    for split in ('train', 'val', 'test'):
        if {r['label'] for r in data['images'] if r['split'] == split} != set(data['classes']):
            raise ValueError(f'Every class needs examples in {split}.')
    return data


def import_reviews(source, output):
    destination = Path(output).resolve()
    count = 0
    for path in sorted(Path(source).glob('*.bloom-review.json')):
        if path.stat().st_size > 4*1024*1024:
            raise ValueError('Review file exceeds 4 MB.')
        review = json.loads(path.read_text(encoding='utf-8'))
        if review.get('format') != 'bloom-reviewed-image-v1' or review.get('consent') is not True:
            raise ValueError('Choose explicitly exported Bloom training examples.')
        label = review.get('label', '')
        if not isinstance(label, str) or not label or len(label) > 90:
            raise ValueError('Missing reviewed label.')
        import re
        label = re.sub(r'[^a-z0-9]+', '_', label.lower()).strip('_')
        if not label:
            raise ValueError('Use a label with letters or numbers.')
        image = review.get('image', '')
        if not isinstance(image, str) or not image.startswith('data:image/jpeg;base64,'):
            raise ValueError('Review needs its explicitly exported JPEG.')
        raw = base64.b64decode(image.split(',', 1)[1], validate=True)
        if digest(raw) != review.get('image_sha256'):
            raise ValueError('Review image hash does not match.')
        target = destination / label / (digest(raw) + '.jpg')
        for other in destination.glob('*/' + target.name):
            if other != target:
                raise ValueError('Same image already has a different label. Resolve the label conflict.')
        target.parent.mkdir(parents=True, exist_ok=True)
        with io.BytesIO(raw) as stream:
            from PIL import Image
            with Image.open(stream) as img:
                if img.width * img.height > 20_000_000:
                    raise ValueError('Reviewed photo exceeds 20 megapixels.')
                img.verify()
        target.write_bytes(raw)
        write_json(target.with_suffix('.review.json'), {k: v for k, v in review.items() if k != 'image'})
        count += 1
    if not count:
        raise ValueError('No *.bloom-review.json files found.')
    print(f'Imported {count} reviewed images. Merge class names deliberately before training.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare')
    prepare.add_argument('--source', required=True)
    prepare.add_argument('--groups', help='Optional CSV path,group; group photos from the same meal together.')
    food = commands.add_parser('food101')
    food.add_argument('--root', default='ml/data')
    food.add_argument('--download', action='store_true', help='Explicitly download the full Food-101 archive (~5 GB).')
    food.add_argument('--classes', nargs='+', default=CLASSES)
    for command in (prepare, food):
        command.add_argument('--output', required=True)
        command.add_argument('--seed', type=int, default=42)
        command.add_argument('--per-class', type=int, default=100)
    reviews = commands.add_parser('import-reviews')
    reviews.add_argument('--source', required=True)
    reviews.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.command == 'import-reviews':
        return import_reviews(args.source, args.output)
    if args.per_class < 6:
        parser.error('--per-class must be at least 6.')
    if args.command == 'food101':
        from torchvision.datasets import Food101
        dataset = Food101(args.root, split='train', download=args.download)
        data_root = Path(args.root).resolve() / 'food-101'
        official_train = json.loads((data_root/'meta'/'train.json').read_text(encoding='utf-8'))
        # Only official training photos are candidates. Official test photos remain untouched.
        # Build a class-folder view using hard links; copy only when the filesystem disallows links.
        import shutil
        selection = json.dumps([args.classes, args.seed, args.per_class])
        staging = Path(args.root).resolve() / ('subset-' + digest(selection.encode())[:10])
        rng = random.Random(args.seed)
        for label in args.classes:
            if label not in dataset.classes:
                raise ValueError('Unknown Food-101 class: ' + label)
            candidates = [data_root/'images'/(name+'.jpg') for name in official_train[label]]
            rng.shuffle(candidates)
            for image in candidates[:args.per_class]:
                target = staging / label / image.name
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    try: target.hardlink_to(image)
                    except OSError: shutil.copyfile(image, target)
        result = build_manifest(staging, args.output, args.seed, args.per_class, args.classes)
        result['provenance'] = {'dataset': 'Food-101', 'upstream_split': 'official train only',
                                'url': 'https://data.vision.ee.ethz.ch/cvl/datasets_extra/food-101/',
                                'benchmark_note': 'Internal subset holdout; not the official Food-101 benchmark.'}
        write_json(args.output, result)
    else:
        build_manifest(args.source, args.output, args.seed, args.per_class, groups_file=args.groups)


if __name__ == '__main__':
    main()
