"""
state.py
Tracks a hash per article file so main.py can tell, on each daily run,
which files are new, which changed, and which are unchanged (skip).

State is persisted as a small JSON file. In the Dockerized daily job,
mount this path as a volume (see README) so state survives between runs.
"""

import hashlib
import json
import logging
from pathlib import Path

log = logging.getLogger("state")

DEFAULT_STATE_PATH = Path("state/hashes.json")


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_state(state_path: Path = DEFAULT_STATE_PATH) -> dict:
    if state_path.exists():
        return json.loads(state_path.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict, state_path: Path = DEFAULT_STATE_PATH) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def diff_against_state(files: list[Path], state_path: Path = DEFAULT_STATE_PATH):
    """
    Compare current files' hashes against the last saved state.
    Returns (added, updated, skipped, new_state) where added/updated/skipped
    are lists of Path, and new_state is the dict to persist after a successful run.
    """
    old_state = load_state(state_path)
    new_state = dict(old_state)

    added, updated, skipped = [], [], []

    for f in files:
        key = str(f)
        current_hash = _hash_file(f)

        if key not in old_state:
            added.append(f)
        elif old_state[key] != current_hash:
            updated.append(f)
        else:
            skipped.append(f)

        new_state[key] = current_hash

    log.info(
        "Delta: %d added, %d updated, %d skipped (out of %d total)",
        len(added), len(updated), len(skipped), len(files),
    )
    return added, updated, skipped, new_state
