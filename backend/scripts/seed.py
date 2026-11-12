"""Compatibility entrypoint for the canonical seed script."""

import sys
from pathlib import Path
from runpy import run_path


def main() -> None:
    backend_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(backend_root))
    run_path(str(backend_root / "app" / "seed_data.py"), run_name="__main__")


if __name__ == "__main__":
    main()
