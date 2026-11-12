"""Host-side HTTP smoke checks; Python standard library, no DB writes."""
from __future__ import annotations

import argparse
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler

ENDPOINTS = (
    ("FastAPI health", "http://127.0.0.1:8001/health", "GET", 200),
    ("Swagger", "http://127.0.0.1:8001/api/docs", "GET", 200),
    ("OpenAPI", "http://127.0.0.1:8001/openapi.json", "GET", 200),
    ("Frontend", "http://127.0.0.1:5174/", "GET", 200),
    ("No public signup", "http://127.0.0.1:8001/api/v1/auth/register", "POST", 404),
)


def check(label: str, url: str, method: str, expected: int) -> tuple[bool, str]:
    opener = build_opener(ProxyHandler({}))
    request = Request(url, method=method, data=b"{}" if method == "POST" else None)
    if method == "POST":
        request.add_header("Content-Type", "application/json")
    try:
        with opener.open(request, timeout=4) as response:
            code, body = response.status, response.read(1_000_000)
    except HTTPError as exc:
        code, body = exc.code, exc.read(1_000_000)
    except (URLError, OSError) as exc:
        return False, f"{label}: FAIL ({type(exc).__name__}: {str(exc)[:100]})"
    if code != expected:
        return False, f"{label}: FAIL (HTTP {code}, expected {expected})"
    if label == "FastAPI health":
        try:
            if json.loads(body).get("status") != "ok":
                return False, f"{label}: FAIL (health payload invalid)"
        except (ValueError, TypeError, AttributeError):
            return False, f"{label}: FAIL (health JSON invalid)"
    if label == "Swagger" and b"swagger" not in body.lower():
        return False, f"{label}: FAIL (unexpected page)"
    if label == "OpenAPI":
        try:
            paths = json.loads(body).get("paths", {})
            if "/api/v1/auth/login" not in paths or "/api/v1/auth/register" in paths:
                return False, f"{label}: FAIL (auth API shape mismatch)"
        except (ValueError, TypeError, AttributeError):
            return False, f"{label}: FAIL (OpenAPI JSON invalid)"
    return True, f"{label}: OK (HTTP {code})"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", type=int, default=0)
    args = parser.parse_args()
    deadline = time.monotonic() + max(0, args.wait)
    while True:
        results = [check(*spec) for spec in ENDPOINTS]
        if all(ok for ok, _ in results):
            for _, msg in results:
                print(msg)
            print("PASS: all HTTP checks. NOTE: not FaceID accuracy or end-to-end database tests.")
            return 0
        if time.monotonic() >= deadline:
            for _, msg in results:
                print(msg)
            print("FAIL: see DIAGNOSE_LMS_WINDOWS.bat / backend logs.")
            return 1
        time.sleep(3)


if __name__ == "__main__":
    raise SystemExit(main())
