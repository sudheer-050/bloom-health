import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from .data import build_manifest, digest, import_reviews, image_info, load_manifest, write_json
from .inference import LocalRecognizer
from .train import choose_threshold, metrics


class PipelineChecks(unittest.TestCase):
    def test_metrics_and_abstention(self):
        values = metrics([0, 1, 1], [[.9, .1], [.2, .8], [.7, .3]], ['a', 'b'], .8)
        self.assertAlmostEqual(values['accuracy'], 2/3)
        self.assertEqual(values['confusion_matrix'], [[1, 0], [1, 1]])
        self.assertEqual(values['accepted_accuracy'], 1)
        self.assertEqual(choose_threshold(np.array([1, 0]), np.array([[.9, .1], [.1, .9]])), 1)
        self.assertIsNone(metrics([0], [[.6, .4]], ['a', 'b'], 1)['accepted_accuracy'])

    def test_duplicate_groups_leakage_and_integrity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rng = np.random.default_rng(777)
            for label in ['a', 'b']:
                (root/'images'/label).mkdir(parents=True)
                for i in range(8):
                    Image.fromarray(rng.integers(0, 256, (32, 32, 3), dtype=np.uint8)).save(root/'images'/label/f'{i}.png')
            # Re-encoded identical pixels must be removed, not split into train and test.
            with Image.open(root/'images'/'a'/'0.png') as img:
                img.save(root/'images'/'a'/'duplicate.png', compress_level=1)
            manifest_path = root/'manifest.json'
            build_manifest(root/'images', manifest_path, per_class=20, near_distance=0)
            data = load_manifest(manifest_path)
            self.assertEqual(data['duplicates_removed'], 1)
            groups = {}
            for row in data['images']:
                self.assertEqual(groups.setdefault(row['group'], row['split']), row['split'])
            changed = data['images'][0]
            image = root/'images'/changed['path']
            image.write_bytes(b'changed after preparation')
            with self.assertRaises(Exception): load_manifest(manifest_path)
            changed['group'] = data['images'][-1]['group']
            changed['split'] = 'val' if data['images'][-1]['split'] != 'val' else 'test'
            write_json(root/'leaked.json', data)
            with self.assertRaisesRegex(ValueError, 'leakage'): load_manifest(root/'leaked.json', verify=False)

    def test_no_model_does_not_enable_recognition(self):
        self.assertFalse(LocalRecognizer(None).status()['ready'])
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(LocalRecognizer(directory).status()['ready'])

    def test_review_import_requires_consent_and_matching_image(self):
        import base64
        import io
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); source=root/'exports';source.mkdir()
            buffer=io.BytesIO();Image.new('RGB',(32,32),'orange').save(buffer,format='JPEG')
            raw=buffer.getvalue()
            review={'format':'bloom-reviewed-image-v1','consent':True,'label':'Orange',
                    'image':'data:image/jpeg;base64,'+base64.b64encode(raw).decode(), 'image_sha256':digest(raw)}
            path=source/'test.bloom-review.json';write_json(path,review)
            import_reviews(source,root/'reviewed')
            self.assertEqual((root/'reviewed'/'orange'/(digest(raw)+'.jpg')).read_bytes(),raw)
            review['image_sha256']='0'*64;write_json(path,review)
            with self.assertRaisesRegex(ValueError,'hash'):import_reviews(source,root/'reviewed')
            review['consent']=False;write_json(path,review)
            with self.assertRaisesRegex(ValueError,'explicitly'):import_reviews(source,root/'reviewed')


if __name__ == '__main__':
    unittest.main()
