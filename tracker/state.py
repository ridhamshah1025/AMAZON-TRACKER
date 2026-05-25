"""Persist tracker state for deduplication."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DEFAULT_STATE_PATH = Path(__file__).resolve().parent.parent / ".tracker-state.json"


@dataclass
class AsinState:
    had_used: bool = False
    last_checked: Optional[str] = None
    last_notified: Optional[str] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state(path: Path = DEFAULT_STATE_PATH) -> dict[str, AsinState]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        asin: AsinState(**data) if isinstance(data, dict) else AsinState()
        for asin, data in raw.items()
    }


def save_state(state: dict[str, AsinState], path: Path = DEFAULT_STATE_PATH) -> None:
    serializable = {asin: asdict(s) for asin, s in state.items()}
    path.write_text(json.dumps(serializable, indent=2) + "\n", encoding="utf-8")


def should_notify(asin: str, has_used: bool, path: Path = DEFAULT_STATE_PATH) -> bool:
    """Notify only on transition from no-used to used."""
    state = load_state(path)
    prev = state.get(asin, AsinState())
    return has_used and not prev.had_used


def update_state(
    asin: str,
    has_used: bool,
    notified: bool = False,
    path: Path = DEFAULT_STATE_PATH,
) -> None:
    state = load_state(path)
    entry = state.get(asin, AsinState())
    entry.had_used = has_used
    entry.last_checked = _now_iso()
    if notified:
        entry.last_notified = _now_iso()
    state[asin] = entry
    save_state(state, path)
