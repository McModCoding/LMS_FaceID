"""Run the canonical seed in a checkout or the Docker container."""

import sys
from pathlib import Path
from runpy import run_path


def main() -> None:
    workspace = Path(__file__).resolve().parent.parent
    candidates = (workspace / "backend", workspace)
    for backend_root in candidates:
        canonical_seed = backend_root / "app" / "seed_data.py"
        if canonical_seed.is_file():
            sys.path.insert(0, str(backend_root))
            run_path(str(canonical_seed), run_name="__main__")
            return
    raise FileNotFoundError("Cannot locate app/seed_data.py")


if __name__ == "__main__":
    main()
