from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

from marketlab.action_shadow_schema import sha256


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record exact runtime versions in a completed shadow model bundle."
    )
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()

    bundle_root = Path(args.bundle_root)
    manifest_path = bundle_root / "manifest.json"
    result_path = Path(args.result)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["runtime"] = {
        "python_major_minor": f"{sys.version_info.major}.{sys.version_info.minor}",
        "python_full": sys.version,
        "scikit_learn": sklearn.__version__,
        "joblib": joblib.__version__,
        "numpy": np.__version__,
        "pandas": pd.__version__,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["bundle_manifest_sha256"] = sha256(manifest_path)
    result["runtime"] = manifest["runtime"]
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
