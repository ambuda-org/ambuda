#!/usr/bin/env python3

"""A basic test suite to ensure that prod is loading correctly."""

import requests


URLS_200 = [
    "/",
    "/api/dict/vacaspatyam/nara",
    "/dictionaries/",
    "/dictionaries/apte/nara",
    "/dictionaries/mw/nara",
    "/dictionaries/shabdakalpadruma/nara",
    "/dictionaries/vacaspatyam/nara",
    "/texts/",
    "/texts/mahabharata/1.1",
    "/texts/mahabharata/18.5",
]

URLS_404 = [
    "/dictionaries/unknown",
    "/texts/mahabharata/unknown",
    "/texts/unknown",
]


def _ok(s) -> str:
    print(f"\033[92m[  OK  ] {s}\033[0m")


def _fail(s) -> str:
    print(f"\033[91m[ FAIL ] {s}\033[0m")


def check_200():
    for path in URLS_200:
        url = f"https://ambuda.org{path}"
        resp = requests.get(url)
        if resp.status_code == 200:
            _ok(f"HTTP 200 {url}")
        else:
            _fail(f"HTTP 200 {url}")


def check_404():
    for path in URLS_404:
        url = f"https://ambuda.org{path}"
        resp = requests.get(url)
        if resp.status_code == 404:
            _ok(f"HTTP 404 {url}")
        else:
            _fail(f"HTTP 404 {url}")


if __name__ == "__main__":
    check_200()
    check_404()
