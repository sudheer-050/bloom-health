"""Offline training/inference verification with synthetic patterns, not food accuracy.

python -m ml.smoke --output .qa/ml-smoke
"""
import argparse
from pathlib import Path
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    root = Path(args.output).resolve()
    if root.exists():
        raise ValueError('Output exists. Use a fresh smoke-test directory.')
    from PIL import Image
    import numpy as np
    from .data import build_manifest, write_json
    from .train import train
    from .inference import LocalRecognizer
    rng = np.random.default_rng(123)
    for index, name in enumerate(['synthetic_red', 'synthetic_green', 'synthetic_blue']):
        folder = root/'images'/name
        folder.mkdir(parents=True)
        for i in range(10):
            pixels = rng.integers(0, 100, (64, 64, 3), dtype=np.uint8)
            pixels[:, :, index] += 140
            Image.fromarray(pixels).save(folder/f'{i}.png')
    manifest = root/'manifest.json'
    build_manifest(root/'images', manifest, per_class=10, purpose='functional_smoke', near_distance=0)
    metadata = train(SimpleNamespace(manifest=str(manifest), output=str(root/'run'), epochs=2,
                                    freeze_epochs=1, batch_size=6, size=64, lr=.001, seed=42,
                                    threads=2, device='cpu', weights='none', smoke=True, mlflow_uri=None))
    classifier = LocalRecognizer(root/'run'/'artifact')
    assert not classifier.status()['ready'], 'Synthetic model must be refused by the app.'
    result = classifier.predict(next((root/'images'/'synthetic_red').glob('*.png')).read_bytes(), allow_smoke=True)
    assert len(result['candidates']) == 3 and all(0 <= r['score'] <= 1 for r in result['candidates'])
    try:
        classifier.predict(next((root/'images'/'synthetic_red').glob('*.png')).read_bytes())
        raise AssertionError('Cached synthetic model escaped the deployment guard.')
    except ValueError:
        pass
    write_json(root/'SMOKE-RESULT.json', {'purpose': 'functional_smoke', 'training_completed': True,
                                        'inference_completed': True, 'app_refuses_synthetic_model': True,
                                        'food_accuracy_measured': False, 'model_id': metadata['model_id']})
    print('PASS: offline training, checkpoint selection, evaluation, artifact reload, inference and synthetic-model deployment guard.')


if __name__ == '__main__':
    main()
