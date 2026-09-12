"""Model selection and training: glue from TimeNet `load_torch()` items to the chosen TSLM (OpenTSLM-Flamingo
is the default candidate), LoRA fine-tuning loop, checkpoint export.

Owned by the training person. Configs live in configs/. Checkpoints go to $DATA_DIR/checkpoints (never git).
"""
