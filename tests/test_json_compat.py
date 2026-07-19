from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from marketlab.json_compat import json_default


def test_json_default_converts_numpy_and_pandas_values() -> None:
    payload = {
        "integer": np.int64(7),
        "float": np.float64(1.25),
        "flag": np.bool_(True),
        "array": np.asarray([1, 2, 3], dtype=np.int64),
        "timestamp": pd.Timestamp("2026-07-19T06:00:00Z"),
        "duration": pd.Timedelta(hours=3),
    }
    encoded = json.dumps(payload, default=json_default)
    decoded = json.loads(encoded)
    assert decoded["integer"] == 7
    assert decoded["float"] == 1.25
    assert decoded["flag"] is True
    assert decoded["array"] == [1, 2, 3]
    assert decoded["timestamp"] == "2026-07-19T06:00:00+00:00"
    assert decoded["duration"] == "P0DT3H0M0S"


def test_json_default_rejects_unknown_objects() -> None:
    with pytest.raises(TypeError, match="not JSON serializable"):
        json_default(object())
