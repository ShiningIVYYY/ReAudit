"""Configuration and process-local runtime paths."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_config(path=None):
    path = Path(path or ROOT / "config/config.json").resolve()
    config = json.loads(path.read_text())
    if config["appworld"]["dataset"] != "train":
        raise ValueError("Only the official train split is permitted.")
    return config


def runtime_environment(config):
    env = os.environ.copy()
    paths = config["paths"]
    env.update({
        "APPWORLD_ROOT": str(ROOT / paths["appworld_root"]),
        "APPWORLD_CACHE": str(ROOT / paths["appworld_cache"]),
        "TMPDIR": str(ROOT / paths["tmp"]),
        "XDG_CACHE_HOME": str(ROOT / paths["cache"]),
        "IPYTHONDIR": str(ROOT / paths["ipython"]),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(ROOT / "src"),
        "HF_HOME": str(ROOT / paths["hf_cache"]),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "TORCH_HOME": str(ROOT / paths["cache"] / Path("torch")),
        "TRITON_CACHE_DIR": str(ROOT / paths["cache"] / Path("triton")),
        "TORCHINDUCTOR_CACHE_DIR": str(ROOT / paths["cache"] / Path("torchinductor")),
        "VLLM_CACHE_ROOT": str(ROOT / paths["cache"] / Path("vllm")),
        "VLLM_NO_USAGE_STATS": "1",
        "DO_NOT_TRACK": "1",
    })
    for key in ("APPWORLD_ROOT", "APPWORLD_CACHE", "TMPDIR", "XDG_CACHE_HOME",
                "IPYTHONDIR", "HF_HOME", "TORCH_HOME", "TRITON_CACHE_DIR",
                "TORCHINDUCTOR_CACHE_DIR", "VLLM_CACHE_ROOT"):
        Path(env[key]).mkdir(parents=True, exist_ok=True)
    return env
