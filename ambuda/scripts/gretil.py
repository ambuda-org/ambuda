from ambuda.scripts.common import fetch_bytes


ZIP_URL = "http://gretil.sub.uni-goettingen.de/gretil/1_sanskr.zip"


def log(*a):
    print(*a)


def fetch_gretil() -> str:
    zip_bytes = fetch_bytes(ZIP_URL)


def run():
    log("Fetching GRETIL data ...")
    fetch_gretil()
