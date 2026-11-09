# Bloom: food recognition with human review

Bloom now includes a reproducible computer vision project as well as the health journal. It compares a color-histogram/logistic-regression baseline with a PyTorch ResNet18, evaluates unseen images, serves a versioned artifact locally, and lets users correct predictions.

**Current evidence:** the pipeline has completed training, checkpoint selection, calibration, evaluation, artifact reload and inference on synthetic functional fixtures. This does not establish food recognition accuracy. A real-food model has not been trained: dataset downloads were unavailable in the implementation environment. Bloom therefore shows the local model as unavailable rather than serving a synthetic model. Online OpenAI analysis and manual entry remain available.

## 1. Set up an isolated ML environment

The journal itself still needs only Python 3.10+. Use Python 3.11+ for a fresh ML environment. From the Bloom folder in PowerShell:

```powershell
py -3.11 -m venv ml/.venv
ml/.venv/Scripts/python -m pip install -r ml/requirements.txt
```

Substitute an installed Python 3.11+ version if needed. The CPU environment and model dependencies take several GB. GPU training is optional; use the appropriate PyTorch build for your GPU. Existing system packages are left untouched.

## 2. Prepare real food images

The default scope is ten dominant-dish categories: apple pie, chicken curry, fried rice, grilled salmon, hamburger, omelette, pizza, spaghetti bolognese, steak and sushi. These are classification labels, not nutrient profiles.

Put your own permitted images in folders named by class:

```text
my-food-photos/
  pizza/
    image-001.jpg
  sushi/
    image-002.jpg
  ...
```

Use at least six independent image groups per class; 50–100+ is a better first experiment. The default cap is 100 images/class. Keep a separate folder of new personal/test photos for external evaluation. Include different lighting, cameras and preparations.

```powershell
ml/.venv/Scripts/python -m ml.data prepare --source C:/datasets/my-food-photos --output ml/data/food-v1.json --per-class 100
```

If several photos show the same meal, provide `--groups C:/datasets/groups.csv`. The CSV needs `path,group`, with paths relative to the dataset root, such as `pizza/image-001.jpg,meal-001`. Use the same group for the same meal/source session. Group conflicts across class labels are rejected for manual resolution.

Preparation hashes file bytes and decoded pixels, removes exact duplicates, groups near duplicates using perceptual hashes, and assigns whole groups to stratified train/validation/test splits (approximately 70/15/15). Groups never cross splits. Hashes are heuristics, not proof of independence; inspect source/meal groups yourself. Image content is rechecked before training so modified data cannot silently reuse the same manifest. This preparer caps datasets at 5,000 images.

Alternatively, use [Food-101](https://data.vision.ee.ethz.ch/cvl/datasets_extra/food-101/). The following command explicitly downloads its full archive, roughly 5 GB, before preparing a small subset:

```powershell
ml/.venv/Scripts/python -m ml.data food101 --root ml/data --download --output ml/data/food-v1.json --per-class 100
```

Without `--download`, an existing torchvision Food-101 installation is required. Only official **training** images are sampled and internally split; official test images remain untouched. These results must be described as an internal subset experiment, not the official Food-101 benchmark. The source images are not included in Bloom's share ZIP. Review the upstream dataset's image rights before redistributing data or using it commercially.

## 3. Train and compare

```powershell
ml/.venv/Scripts/python -m ml.train --manifest ml/data/food-v1.json --output ml/runs/food-v1 --epochs 5 --freeze-epochs 1 --device cpu
```

The first run downloads ImageNet ResNet18 weights (roughly 45 MB). The first epoch trains the classification head with a frozen backbone and BatchNorm statistics; later epochs fine-tune the full network at a lower learning rate. Training is seeded; deterministic operations are requested. Exact numerical reproducibility still depends on hardware and library versions. Each run records those versions and the source/data hashes.

The checkpoint is selected by validation macro F1. Temperature scaling and the abstention threshold also use validation only. The threshold targets at least 80% validation accuracy on accepted predictions with at least 10% coverage; if no candidate threshold qualifies, the model abstains. This is a selection rule, not a guaranteed accuracy level. Test images are evaluated afterward. Do not repeatedly tune on the test results; keep an independent external set.

Run outputs:

| Artifact | What to inspect |
|---|---|
| `REPORT.md` | Baseline versus ResNet18, scope and limitations |
| `metrics.json` | Accuracy, macro F1, top-3 accuracy, log loss, calibration error, coverage and accepted accuracy |
| `confusion-matrix.csv` | True classes versus predictions |
| `failures.json` | Incorrect held-out predictions and scores |
| `history.json`, `config.json` | Learning curves, settings, epochs and seed |
| `manifest.json` | Image hashes, groups, class counts and split membership |
| `artifact/metadata.json` | Model version, preprocessing, calibration, latency, dependency versions and hashes |
| `artifact/weights.pt` | Tensor-only checkpoint, loaded with `weights_only=True` |

Use a new output directory for each experiment. To compare changes, keep the same manifest and change one training setting at a time. Inspect errors before increasing model size. Top-3 accuracy is uninformative for datasets with three or fewer classes. Latency in the report measures warmed-up model forward passes at batch size one; the application reports total request inference time including preprocessing and first-load overhead.

JSON/CSV experiment records work without an extra service. For an optional MLflow UI:

```powershell
ml/.venv/Scripts/python -m pip install mlflow
ml/.venv/Scripts/python -m ml.train --manifest ml/data/food-v1.json --output ml/runs/food-v2 --mlflow-uri sqlite:///ml/mlflow.db
ml/.venv/Scripts/python -m mlflow ui --backend-store-uri sqlite:///ml/mlflow.db
```

MLflow is explicitly opt-in. A remote tracking URI uploads experiment artifacts (including relative image paths in failure reports), so choose a local URI when those should stay private.

## 4. Evaluate external photos

Place new photos in the same named class folders, then run:

```powershell
ml/.venv/Scripts/python -m ml.evaluate --model-dir ml/runs/food-v1/artifact --source C:/datasets/new-food-photos --output ml/runs/food-v1-external.json
```

Keep the full run directory alongside the artifact. The evaluator rejects exact and perceptual overlap with the experiment manifest, reports absent classes, and produces per-class metrics and failure examples. Independently confirm that photographs of the same meal do not appear in both datasets. Unfamiliar classes are rejected rather than silently assigned a known ground truth. This evaluation does not measure out-of-distribution detection.

## 5. Connect a real model to Bloom

Stop the previous Bloom server first, then run with the same browser address to retain your existing local journal:

```powershell
ml/.venv/Scripts/python server.py --model-dir ml/runs/food-v1/artifact
```

Or set `BLOOM_MODEL_DIR` before launching. Open `http://localhost:4317`, choose Guest or sign in, then open **Photo meal**. **Check model** shows the connected version, supported classes and actual held-out results. No model is downloaded or retrained by the app.

Choose a photo, press **Recognize food locally**, then select a suggestion or **None of these — enter the correct food**. Review the label and supply portion grams and label/recipe nutrition values. There is deliberately no automatic calorie estimate from a classification score. Add other foods manually, then log the meal. Totals and the consumed-food activity feed use the reviewed ingredients.

The server checks the artifact format and weights hash, loads on CPU without downloading weights, and validates image/request limits. Synthetic functional models are refused. A high closed-set score can still be wrong on unfamiliar images. The model identifies one dominant food; it cannot detect everything on a mixed plate, identify hidden oil, estimate weight, or measure vitamins.

## 6. Collect corrections deliberately

Before logging/resetting the photo draft, choose **Export reviewed training example**. This explicitly downloads one `*.bloom-review.json` containing the selected resized JPEG, its hash, the reviewed label and model provenance. It contains no account, password, API key or rest of the journal. It is an ordinary unencrypted file; export only photos you intend to keep for training.

Photos otherwise remain in memory. Nothing is saved to the server or used for automatic retraining. The logged meal and its backup retain small prediction provenance (model, suggested label, score and image hash), without the image.

```powershell
ml/.venv/Scripts/python -m ml.data import-reviews --source C:/datasets/bloom-exports --output ml/data/reviewed
```

Review imports and normalize class names deliberately (`fried rice` becomes `fried_rice`). Resolve ambiguous labels and same-image label conflicts before combining with a training set. Corrections require images to learn visual features: label-only logs are insufficient. Keep newly collected photos in an external holdout before using later collections for retraining.

## 7. Verify the implementation

```powershell
node check-vault.cjs
node check-nutrition.cjs
python -m unittest test_server.py
ml/.venv/Scripts/python -m unittest ml.test_pipeline
ml/.venv/Scripts/python -m ml.smoke --output .qa/ml-smoke-new
```

The smoke command generates colored patterns, trains two epochs from random initialization, evaluates, reloads the checkpoint and verifies that Bloom refuses that artifact. It is a functional test only. See [ml/VERIFICATION.md](ml/VERIFICATION.md) for the implementation-session evidence and remaining acceptance work.

## Present this honestly in your portfolio

You can demonstrate data preparation, leakage controls, a classical baseline, transfer-learning code, validation-based checkpoint/calibration selection, reproducibility, inference APIs, human correction, privacy-aware data export and an integrated product.

Before claiming model accuracy, complete a real-food run and external evaluation. Replace all résumé placeholders with measured results. Be able to explain the split policy, why macro F1 matters, confidence versus correctness, where the model fails, and which code or decisions were assisted by AI tools.

An eventual résumé bullet:

> Built an end-to-end food classification system using PyTorch and ResNet18, compared it with a classical baseline, achieved [measured macro F1] on [clearly described held-out set], and integrated reviewed predictions into a local nutrition journal.

The bracketed claims are not established yet.

References: [PyTorch transfer learning](https://docs.pytorch.org/tutorials/beginner/transfer_learning_tutorial.html), [torchvision Food101](https://docs.pytorch.org/vision/stable/generated/torchvision.datasets.Food101.html), [MLflow tracking](https://mlflow.org/docs/latest/tracking/).
