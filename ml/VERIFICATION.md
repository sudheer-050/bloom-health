# Implementation verification

Date: 2026-11-08. Final smoke rerun: `.qa/ml-smoke-final/SMOKE-RESULT.json`. Machine: Windows, CPU only; no CUDA available.

## Completed

- `python -m ml.smoke --output .qa/ml-smoke-v1`: two epochs, frozen head stage and full-network stage, checkpoint selection, calibration, baseline comparison, test report, tensor-only artifact reload and inference completed.
- Smoke dataset: 30 synthetic patterned images, three artificial classes, 18 training / 6 validation / 6 test images. These are **not food images** and establish no food accuracy.
- The app refused the synthetic artifact, including after a direct test inference had loaded it into memory.
- Unit checks cover duplicate removal, group leakage rejection, changed-image detection, metrics, abstention, missing artifacts, endpoint origin checks and malformed input.
- Existing journal/nutrition checks cover account isolation, encryption, storage failures, meal math, unknown nutrients and new recognition provenance surviving journal/backup validation.
- Browser integration used a separate loopback port with an explicitly named synthetic UI fixture. The actual synthetic checkpoint ran inference; the user correction form required grams and nutrition values. A corrected 150g Orange entry produced 70.5 kcal and 79.8mg vitamin C, appeared in consumed activity, and survived reload. The test entry was removed afterward.
- The browser explicitly exported a reviewed photo/label file. The importer verified its image hash, restored the reviewed image and label, and retained no journal/account fields. This was a synthetic upload fixture, not a food-accuracy test.
- The ordinary server reports that no real-food model is connected, keeps recognition disabled, and leaves manual/online entry available. The duplicate-server port binding issue on Windows was fixed so updated and old servers cannot silently share the same port.

- Final combined Python test run: 7 tests passed; vault and nutrition Node checks passed. New photo panel inspected at desktop and 390x844, with no horizontal overflow. 21st review found only informational color-token warnings.
- A GitHub Actions workflow is included for journal checks, ML unit checks and synthetic smoke training; it has not been run on GitHub.

## Environment limits

Outbound dataset requests failed in the restricted implementation environment. No real-food dataset or pretrained weights were downloaded. The existing Python installation ran the synthetic training successfully, but emitted a torchvision native-image-extension compatibility warning. The pipeline uses Pillow image loading; a fresh isolated environment from `ml/requirements.txt` is recommended for real training. MLflow was not installed or exercised; JSON/CSV experiment tracking was exercised.

## Required before making ML performance claims

1. Prepare permitted real food images, with independently checked meal/source groups.
2. Run ImageNet-initialized training and inspect baseline comparison, class balance, confusion matrix and failure cases.
3. Evaluate newly collected external photos and unfamiliar-image behavior.
4. Complete MODEL-CARD.md with measured results and limitations.
5. Connect the selected real artifact and test actual meal photos in Bloom.

Real-food recognition accuracy, GPU execution, MLflow integration and cross-platform fresh installs remain unverified. No fabricated metrics are presented as real-food results.
