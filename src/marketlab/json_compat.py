from __future__ import annotations

import json
from typing import Any, Callable

import numpy as np
import pandas as pd


def json_default(value: Any) -> Any:
    """Convert scientific Python scalar/container types to plain JSON values."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (pd.Timestamp, pd.Timedelta)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def install_numpy_safe_json_dumps() -> Callable[..., str]:
    """Patch json.dumps for a legacy script and return the original function."""
    original = json.dumps

    def safe_dumps(obj: Any, *args: Any, **kwargs: Any) -> str:
        kwargs.setdefault("default", json_default)
        return original(obj, *args, **kwargs)

    json.dumps = safe_dumps  # type: ignore[assignment]
    return original
