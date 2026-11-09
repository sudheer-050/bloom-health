# Bloom food model card

Status: **training pipeline implemented; no real-food model released**.

The implementation-session artifact is a synthetic functional test and is blocked from serving food predictions. Its scores must not be cited as food accuracy.

Complete this card for each real-food model selected for use:

- Model ID, artifact hash and run path:
- Architecture and pretrained weight source:
- Dataset source, image rights, category list and class counts:
- Duplicate removal and meal/source grouping:
- Train/validation/test counts and provenance:
- Checkpoint selection, calibration and abstention rule:
- Baseline and model metrics, including per-class results:
- Coverage and conditional accuracy at the selected threshold:
- External-set performance, collection protocol and overlap checks:
- Warm and first-request latency, hardware and dependency versions:
- Failure cases, absent cuisines and performance gaps:
- Intended use: user-reviewed dominant-food classification for journal entry.
- Excluded capabilities: portion measurement, nutrient inference, multi-food detection, diagnosis and personalized medical recommendations.
- Privacy: local inference; explicit user action for image/label exports; no automatic retraining.
- Limitations of closed-set confidence and duplicate-detection heuristics:
- Author contributions, AI-assisted portions, reproduction commands and next experiments:
