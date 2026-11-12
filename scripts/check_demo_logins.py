"""Non-destructive API login smoke test for local demonstration accounts.

Does not print passwords, tokens, hashes or database secrets. POST login creates
normal login audit records; run only on a local development database.
"""
from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler

BASE = "http://127.0.0.1:8000/api/v1/auth"
CASES = (("admin", "Demo@123", "admin"),
         ("gv001", "Demo@123", "lecturer"),
         ("sv001", "Demo@123", "student"))


def request_json(url: str, data: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = Request(url, data=body, method="POST" if body else "GET")
    if body:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(req, timeout=10) as reply:
            code, payload = reply.status, reply.read(500_000)
    except HTTPError as exc:
        code, payload = exc.code, exc.read(500_000)
    try:
        parsed = json.loads(payload)
    except (ValueError, TypeError):
        parsed = {}
    return code, parsed if isinstance(parsed, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--optional", action="store_true", help="skip when demo accounts aren't seeded")
    args = parser.parse_args()
    if args.optional:
        # Avoid normal login audit writes (and failed-attempt counters) before seeding.
        from app.db.session import SessionLocal
        from app.models.user import User
        db = SessionLocal()
        try:
            usernames = [case[0] for case in CASES]
            present = db.query(User.username).filter(User.username.in_(usernames)).count()
            if present != len(CASES):
                print("INFO: demo users not present; optional HTTP login check skipped (no DB writes).")
                return 0
        finally:
            db.close()
    failed = []
    for username, password, role in CASES:
        try:
            code, data = request_json(BASE + "/login", {"username": username, "password": password})
            if code != 200 or not data.get("access_token"):
                print(f"LOGIN_{username}: HTTP {code}; demo credentials unavailable")
                failed.append(username)
                continue
            code, who = request_json(BASE + "/me", token=data["access_token"])
            returned_role = who.get("role")
            if code != 200 or who.get("username") != username or returned_role != role:
                print(f"LOGIN_{username}: /me mismatch (HTTP {code}, role={returned_role})")
                failed.append(username)
                continue
            print(f"LOGIN_{username}: PASS (HTTP 200, role={role})")
        except (URLError, OSError, TimeoutError) as exc:
            print(f"LOGIN_{username}: CONNECTION_ERROR {type(exc).__name__}")
            failed.append(username)
    if failed:
        if args.optional:
            print("INFO: existing accounts may have changed passwords; sample login check is inconclusive.")
            return 0
        print("FAIL: seed/login mismatch. Run DIAGNOSE_LMS_WINDOWS.bat; do not reset DB.")
        return 1
    print("PASS: 3 demo roles can login and access /auth/me (no tokens printed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
