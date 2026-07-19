from __future__ import annotations

from marketlab.json_compat import install_numpy_safe_json_dumps

install_numpy_safe_json_dumps()

from experiment_015_execution_stress import main  # noqa: E402


if __name__ == "__main__":
    main()
