import os

if os.path.isdir("/mnt/hd/ml/hf-cache"):
    os.environ.setdefault("HF_HOME", "/mnt/hd/ml/hf-cache")
