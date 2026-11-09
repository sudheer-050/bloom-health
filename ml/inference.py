"""Optional local classifier. Importing this module does not import PyTorch."""
import hashlib
import importlib.util
import io
import json
import math
import threading
import time
from pathlib import Path


class LocalRecognizer:
    def __init__(self, directory):
        self.directory = Path(directory).resolve() if directory else None
        self.model = None
        self.metadata = None
        self.lock = threading.Lock()

    def read_metadata(self, allow_smoke=False):
        if not self.directory or not (self.directory/'metadata.json').is_file() or not (self.directory/'weights.pt').is_file():
            raise ValueError('No trained food model is connected. Follow ML-PROJECT.md, then restart Bloom with --model-dir pointing to its artifact folder.')
        if (self.directory/'metadata.json').stat().st_size > 2*1024*1024:
            raise ValueError('Model metadata is too large.')
        data = json.loads((self.directory/'metadata.json').read_text(encoding='utf-8'))
        classes = data.get('classes', [])
        valid_classes = isinstance(classes, list) and 2 <= len(classes) <= 101 and all(isinstance(c, str) and 0 < len(c) <= 90 for c in classes)
        if data.get('format') != 'bloom-resnet18-v1' or not valid_classes or len(set(classes)) != len(classes):
            raise ValueError('Invalid Bloom model metadata.')
        if data.get('purpose') not in (('food_research', 'functional_smoke') if allow_smoke else ('food_research',)):
            raise ValueError('Synthetic test models cannot recognize food in Bloom. Train on real food photos first.')
        if data.get('architecture') != 'resnet18' or type(data.get('size')) is not int or not 32 <= data['size'] <= 512:
            raise ValueError('Unsupported model architecture or input size.')
        if data.get('normalization') != {'mean': [.485, .456, .406], 'std': [.229, .224, .225]}:
            raise ValueError('Unsupported model normalization.')
        for field, low, high in [('temperature', .01, 100), ('threshold', 0, 1)]:
            v = data.get(field)
            if type(v) not in (int, float) or not math.isfinite(v) or not low <= v <= high:
                raise ValueError('Invalid model calibration.')
        if not isinstance(data.get('model_id'), str) or not 0 < len(data['model_id']) <= 90:
            raise ValueError('Invalid model version.')
        from .data import digest
        if data.get('weights_sha256') != digest((self.directory/'weights.pt').read_bytes()):
            raise ValueError('Model weights have changed. Re-export or retrain the artifact.')
        return data

    def status(self):
        try:
            data = self.read_metadata()
            missing = [p for p in ('torch', 'torchvision', 'PIL', 'numpy', 'sklearn') if importlib.util.find_spec(p) is None]
            if missing:
                raise ValueError('Install the optional ML requirements in ML-PROJECT.md: ' + ', '.join(missing))
            test = data.get('test_metrics', {})
            return {'ready': True, 'model_id': data['model_id'], 'classes': data['classes'],
                    'threshold': data['threshold'], 'test_accuracy': test.get('accuracy'),
                    'test_macro_f1': test.get('macro_f1'), 'test_count': test.get('count'),
                    'scope': 'Single dominant food only. Confirm the food, portion and nutrient values.'}
        except (ValueError, OSError, KeyError, TypeError) as error:
            return {'ready': False, 'message': str(error)}

    def predict(self, raw, allow_smoke=False):
        with self.lock:
            started = time.perf_counter()
            if self.model is None:
                data = self.read_metadata(allow_smoke)
                import torch
                from torch import nn
                from torchvision.models import resnet18
                torch.set_num_threads(4)
                model = resnet18(weights=None)
                model.fc = nn.Linear(model.fc.in_features, len(data['classes']))
                model.load_state_dict(torch.load(self.directory/'weights.pt', map_location='cpu', weights_only=True))
                self.model, self.metadata = model.eval(), data
            if self.metadata['purpose'] == 'functional_smoke' and not allow_smoke:
                raise ValueError('Synthetic test models cannot serve food predictions.')
            import torch
            from PIL import Image, ImageOps
            from .train import transform
            with Image.open(io.BytesIO(raw)) as opened:
                if opened.width * opened.height > 20_000_000:
                    raise ValueError('Choose a photo under 20 megapixels.')
                tensor = transform(self.metadata['size'])(ImageOps.exif_transpose(opened).convert('RGB')).unsqueeze(0)
            with torch.inference_mode():
                probabilities = (self.model(tensor)[0] / self.metadata['temperature']).softmax(0)
            values, indices = torch.topk(probabilities, min(3, len(probabilities)))
            candidates = [{'label': self.metadata['classes'][index], 'score': float(value)} for value, index in zip(values, indices)]
            return {'model_id': self.metadata['model_id'], 'candidates': candidates,
                    'abstained': candidates[0]['score'] < self.metadata['threshold'],
                    'threshold': self.metadata['threshold'], 'image_sha256': hashlib.sha256(raw).hexdigest(),
                    'latency_ms': round((time.perf_counter()-started)*1000, 1),
                    'scope': 'Model scores are not guarantees. This classifier cannot measure grams or nutrients and does not detect all foods on a plate.'}
