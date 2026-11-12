"""Wait for actual backend -> MySQL TCP/login/query readiness before Alembic.

Designed for the V3.2 Windows setup; does NOT write or alter DB data.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

import aiomysql


async def check_once() -> None:
    connection = await aiomysql.connect(
        host=os.getenv("DB_HOST", "mysql"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        db=os.environ["DB_NAME"],
        connect_timeout=5,
        autocommit=True,
    )
    try:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT 1")
            row = await cursor.fetchone()
            if not row or row[0] != 1:
                raise RuntimeError("Unexpected database readiness result")
    finally:
        connection.close()


def main() -> int:
    deadline = time.monotonic() + 120
    last_error = None
    attempt = 0
    while True:
        attempt += 1
        try:
            asyncio.run(check_once())
        except Exception as exc:
            code = exc.args[0] if exc.args and isinstance(exc.args[0], int) else None
            # Authentication and nonexistent DB errors will not be fixed by retrying.
            if code in (1044, 1045, 1049):
                print(
                    f"MYSQL_CONNECTION_ERROR: {type(exc).__name__} code={code}; "
                    "verify .env vs existing MySQL volume (do not delete volume).",
                    flush=True,
                )
                return 2
            error = f"{type(exc).__name__}" + (f" code={code}" if code is not None else "")
            if error != last_error or attempt % 5 == 0:
                print(f"MYSQL_NOT_READY: {error}; checking internal Docker TCP connection...", flush=True)
                last_error = error
            if time.monotonic() >= deadline:
                print(
                    "MYSQL_CONNECTION_TIMEOUT: Backend cannot access database on "
                    f"{os.getenv('DB_HOST','mysql')}:{os.getenv('DB_PORT','3306')}. "
                    "Inspect docker compose ps and docker compose logs mysql.",
                    flush=True,
                )
                return 1
            time.sleep(3)
        else:
            print("MYSQL_BACKEND_CONNECTION_OK: SELECT 1 succeeded via TCP and app credentials.", flush=True)
            return 0


if __name__ == "__main__":
    sys.exit(main())
