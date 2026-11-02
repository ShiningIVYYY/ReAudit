#!/usr/bin/env python3
"""Only official train contents are read/extracted from the authorized bundle."""
import argparse
import hashlib
import io
import json
import os
from pathlib import PurePosixPath
import urllib.request
import zipfile
from reaudit.config import ROOT, load_config, runtime_environment
from reaudit.logging import write_json

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--download", action="store_true",
                   help="Use only after approval of the documented bundle download.")
    p.add_argument("--config")
    a = p.parse_args()
    c = load_config(a.config)
    os.environ.update(runtime_environment(c))
    d = c["appworld"]["data"]
    path = ROOT / d["bundle_path"]
    if not path.exists():
        if not a.download:
            raise SystemExit("Bundle missing. Obtain download approval before using --download.")
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(d["url"], timeout=d["download_timeout_seconds"]) as source:
            with path.open("wb") as target:
                while block := source.read(1024 * 1024):
                    target.write(block)
    raw = path.read_bytes()
    if len(raw) != d["bytes"] or hashlib.sha256(raw).hexdigest() != d["sha256"]:
        raise RuntimeError("Official bundle size/SHA256 mismatch.")
    from appworld.common.utils import decrypt_bytes
    from appworld.common.constants import PASSWORD, SALT
    root = ROOT / c["paths"]["appworld_root"]
    written = []
    with zipfile.ZipFile(io.BytesIO(decrypt_bytes(raw, PASSWORD, SALT))) as archive:
        train_ids = set(archive.read("data/datasets/train.txt").decode().split())
        for info in archive.infolist():
            p = PurePosixPath(info.filename)
            parts = p.parts
            if p.is_absolute() or ".." in parts:
                raise ValueError("Unsafe archive member.")
            if info.is_dir():
                continue
            include = info.filename == "data/datasets/train.txt"
            include |= (len(parts) > 2 and parts[:2] == ("data", "tasks")
                        and parts[2] in train_ids)
            include |= (len(parts) > 1 and parts[0] == "data"
                        and parts[1] not in ("datasets", "tasks"))
            if not include:
                continue
            target = root / p
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if target.stat().st_size != info.file_size:
                    raise RuntimeError(f"Existing file differs; refusing overwrite: {target}")
            else:
                target.write_bytes(archive.read(info))
            written.append({"path": str(p), "bytes": info.file_size})
    assert {p.name for p in (root / "data/datasets").iterdir()} == {"train.txt"}
    assert {p.name for p in (root / "data/tasks").iterdir()} == train_ids
    write_json(ROOT / "runtime/train_extraction.json",
               {"train_tasks": len(train_ids), "files": written})
    print(f"Prepared only {len(train_ids)} official train tasks and common resources.")
