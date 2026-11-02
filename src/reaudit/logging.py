"""Append-only events; clocks remain real while AppWorld freezes task time."""
import hashlib
import json
import os
import time
from datetime import datetime, timezone


def monotonic():
    return time.clock_gettime(time.CLOCK_MONOTONIC)


def utc_now():
    seconds = time.clock_gettime(time.CLOCK_REALTIME)
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                               allow_nan=False) + "\n")


class Journal:
    def __init__(self, path, api_key_env=None):
        self.path = path
        self.secret = os.environ.get(api_key_env, "") if api_key_env else ""

    def append(self, kind, **fields):
        record = {"event": kind, "timestamp": utc_now(), **fields}
        text = canonical(record)
        if self.secret:
            text = text.replace(self.secret, "[REDACTED]")
        with self.path.open("a") as output:
            output.write(text + "\n")
            output.flush()
            os.fsync(output.fileno())


def read_events(path):
    if not path.exists():
        return []
    events = []
    for line in path.read_text().splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            # A worker killed while writing may leave one partial final line.
            continue
    return events
