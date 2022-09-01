#!/usr/bin/env python3

"""A basic test suite to ensure that prod is loading correctly.

We use this in our deploy script to check the basic health of the site.
"""

import sys

import requests


URLS_200 = [
    "/",
    "/api/dictionaries/vacaspatyam/nara",
    "/texts/",
    "/texts/mahabharatam/1.1",
    "/texts/mahabharatam/18.5",
    "/tools/dictionaries/",
    "/tools/dictionaries/apte/nara",
    "/tools/dictionaries/mw/nara",
    "/tools/dictionaries/shabdakalpadruma/nara",
    "/tools/dictionaries/vacaspatyam/nara",
    "/proofing/",
    "/tools/dictionaries/",
]


def _ok(s) -> str:
    print(f"\033[92m[  OK  ] {s}\033[0m")


def _fail(s) -> str:
    print(f"\033[91m[ FAIL ] {s}\033[0m")


def check_200() -> bool:
    ok = True
    for path in URLS_200:
        url = f"https://ambuda.org{path}"
        resp = requests.get(url)
        if resp.status_code == 200:
            _ok(f"HTTP 200 {url}")
        else:
            _fail(f"HTTP 200 {url}")
            ok = False
    return ok


if __name__ == "__main__":
    ok = check_200()
    if not ok:
        sys.exit(1)
