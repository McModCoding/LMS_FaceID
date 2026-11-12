"""Run original 42 FaceID tests WITHOUT backend/tests/conftest.py or DB effects.

The backend/conftest is designed for MySQL/SQLite integration tests; these 42
algorithm/evaluation tests require no database and are copied into a temp folder
so they can run independently even on machines without a test database.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend" if Path(__file__).resolve().parents[1].name != "backend" else Path(__file__).resolve().parents[1]
# In the Docker image scripts/ is mounted at /app/scripts and backend lives at /app.
if not (BACKEND / "tests" / "test_opencv_engine.py").exists():
    BACKEND = Path(__file__).resolve().parents[1]
TESTS = ("test_opencv_engine.py", "test_face_eval.py")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="faceid_test_") as tmp:
        temp = Path(tmp)
        dest = temp / "tests"
        dest.mkdir()
        (dest / "__init__.py").touch()
        for name in TESTS:
            shutil.copy2(BACKEND / "tests" / name, dest / name)
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join((str(BACKEND), str(temp), env.get("PYTHONPATH", "")))
        # Fail if any test fails; no live database/real identity photos required.
        cmd = [sys.executable, "-m", "pytest", "-q", "-c", os.devnull, str(dest / TESTS[0]), str(dest / TESTS[1])]
        print("Testing original 42 YuNet/SFace logic and evaluation cases (DB isolated)...", flush=True)
        result = subprocess.run(cmd, cwd=temp, env=env, check=False)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
