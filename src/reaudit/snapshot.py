"""Fingerprint actual initial live DBs and persist a reloadable official snapshot."""
import hashlib
from .logging import canonical, digest, write_json


def fingerprint(world, directory, config):
    directory.mkdir(parents=True, exist_ok=False)
    world.models.save(db_home_path=str(directory), format="full",
                      save_model_hashes=True, delete_if_exists=False)
    files = []
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            files.append({"path": str(path.relative_to(directory)),
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                          "bytes": path.stat().st_size})
    snapshot = {"task_id": world.task_id, "files": files,
                "task_datetime": str(world.task.datetime),
                "environment_seed": config["agent"]["environment_seed"],
                "appworld_version": config["appworld"]["version"]}
    write_json(directory.parent / "initial_snapshot.json", snapshot)
    return digest(canonical(snapshot))
