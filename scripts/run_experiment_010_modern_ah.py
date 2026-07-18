from __future__ import annotations

from pathlib import PurePosixPath

import experiment_010_modern_ah_residual_repricing as experiment


def archive_relative_path(name: str) -> PurePosixPath | None:
    """Accept Kaggle archives with either flat paths or one wrapper directory."""
    path = PurePosixPath(name)
    if not path.parts:
        return None
    if path.parts[0] == "sample":
        return path
    if len(path.parts) >= 2 and path.parts[1] == "sample":
        return PurePosixPath(*path.parts[1:])
    return path


experiment.archive_relative_path = archive_relative_path


if __name__ == "__main__":
    experiment.main()
