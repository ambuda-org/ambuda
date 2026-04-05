"""Benchmark different PDF splitting strategies for peak memory.

Each strategy runs as a completely separate process via subprocess.run()
so peak RSS measurement is isolated and accurate.

Usage:
    uv run python bench_split.py test.pdf [--pages N] [--dpi 200]
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Worker script template — runs in a fresh process, reports its own peak RSS.
# ---------------------------------------------------------------------------

WORKER_SCRIPT = r'''
import gc
import json
import multiprocessing as mp
import os
import resource
import sys
import tempfile
import time


def strategy_naive(pdf_path, output_dir, num_pages, dpi):
    """Open doc once, render all pages without closing."""
    import fitz
    doc = fitz.open(pdf_path)
    for i in range(num_pages):
        page = doc.load_page(i)
        pix = page.get_pixmap(dpi=dpi)
        pix.pil_save(os.path.join(output_dir, f"{i}.jpg"), optimize=True)
    doc.close()


def strategy_reopen_no_gc(pdf_path, output_dir, num_pages, dpi):
    """Reopen the PDF for every page, no gc.collect()."""
    import fitz
    for i in range(num_pages):
        doc = fitz.open(pdf_path)
        page = doc.load_page(i)
        pix = page.get_pixmap(dpi=dpi)
        pix.pil_save(os.path.join(output_dir, f"{i}.jpg"), optimize=True)
        pix = None
        page = None
        doc.close()
        del doc


def strategy_reopen_gc(pdf_path, output_dir, num_pages, dpi):
    """Reopen the PDF for every page + gc.collect() (current production code)."""
    import fitz
    for i in range(num_pages):
        doc = fitz.open(pdf_path)
        page = doc.load_page(i)
        pix = page.get_pixmap(dpi=dpi)
        pix.pil_save(os.path.join(output_dir, f"{i}.jpg"), optimize=True)
        pix = None
        page = None
        doc.close()
        del doc
        gc.collect()


def _pool_render_page(args):
    import fitz
    pdf_path, page_index, output_dir, dpi = args
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_index)
    pix = page.get_pixmap(dpi=dpi)
    pix.pil_save(os.path.join(output_dir, f"{page_index}.jpg"), optimize=True)
    doc.close()


def strategy_subprocess_pool(pdf_path, output_dir, num_pages, dpi):
    """Each page rendered in a fresh worker (maxtasksperchild=1)."""
    mp.set_start_method("fork", force=True)
    with mp.Pool(processes=1, maxtasksperchild=1) as pool:
        tasks = [(pdf_path, i, output_dir, dpi) for i in range(num_pages)]
        list(pool.imap(_pool_render_page, tasks))


def strategy_pdfium_naive(pdf_path, output_dir, num_pages, dpi):
    """pypdfium2: open once, render all pages."""
    import pypdfium2 as pdfium
    from PIL import Image
    pdf = pdfium.PdfDocument(pdf_path)
    for i in range(num_pages):
        page = pdf[i]
        bitmap = page.render(scale=dpi / 72)
        img = bitmap.to_pil()
        img.save(os.path.join(output_dir, f"{i}.jpg"), optimize=True)
        img.close()
        bitmap.close()
        page.close()
    pdf.close()


def strategy_pdfium_reopen(pdf_path, output_dir, num_pages, dpi):
    """pypdfium2: reopen per page."""
    import pypdfium2 as pdfium
    from PIL import Image
    for i in range(num_pages):
        pdf = pdfium.PdfDocument(pdf_path)
        page = pdf[i]
        bitmap = page.render(scale=dpi / 72)
        img = bitmap.to_pil()
        img.save(os.path.join(output_dir, f"{i}.jpg"), optimize=True)
        img.close()
        bitmap.close()
        page.close()
        pdf.close()


def _pool_render_page_pdfium(args):
    import pypdfium2 as pdfium
    pdf_path, page_index, output_dir, dpi = args
    pdf = pdfium.PdfDocument(pdf_path)
    page = pdf[page_index]
    bitmap = page.render(scale=dpi / 72)
    img = bitmap.to_pil()
    img.save(os.path.join(output_dir, f"{page_index}.jpg"), optimize=True)
    img.close()
    bitmap.close()
    page.close()
    pdf.close()


def strategy_pdfium_subprocess(pdf_path, output_dir, num_pages, dpi):
    """pypdfium2: each page in a fresh worker."""
    mp.set_start_method("fork", force=True)
    with mp.Pool(processes=1, maxtasksperchild=1) as pool:
        tasks = [(pdf_path, i, output_dir, dpi) for i in range(num_pages)]
        list(pool.imap(_pool_render_page_pdfium, tasks))


STRATEGIES = {
    "naive": strategy_naive,
    "reopen_no_gc": strategy_reopen_no_gc,
    "reopen_gc": strategy_reopen_gc,
    "subprocess_pool": strategy_subprocess_pool,
    "pdfium_naive": strategy_pdfium_naive,
    "pdfium_reopen": strategy_pdfium_reopen,
    "pdfium_subprocess": strategy_pdfium_subprocess,
}


def main():
    strategy_name = sys.argv[1]
    pdf_path = sys.argv[2]
    output_dir = sys.argv[3]
    num_pages = int(sys.argv[4])
    dpi = int(sys.argv[5])

    fn = STRATEGIES[strategy_name]
    t0 = time.monotonic()
    fn(pdf_path, output_dir, num_pages, dpi)
    elapsed = time.monotonic() - t0

    # RUSAGE_SELF for in-process strategies
    r = resource.getrusage(resource.RUSAGE_SELF)
    self_rss = r.ru_maxrss
    # RUSAGE_CHILDREN for subprocess_pool's workers
    rc = resource.getrusage(resource.RUSAGE_CHILDREN)
    child_rss = rc.ru_maxrss

    # On macOS ru_maxrss is bytes; on Linux it's KB
    if sys.platform == "linux":
        self_rss *= 1024
        child_rss *= 1024

    peak_rss = max(self_rss, child_rss)
    print(json.dumps({
        "self_rss_mb": round(self_rss / (1024 * 1024), 1),
        "child_rss_mb": round(child_rss / (1024 * 1024), 1),
        "peak_rss_mb": round(peak_rss / (1024 * 1024), 1),
        "wall_time_s": round(elapsed, 1),
    }))


if __name__ == "__main__":
    main()
'''


def run_strategy(strategy_name: str, pdf_path: str, num_pages: int, dpi: int):
    """Run a strategy in a fresh subprocess, return its stats."""
    with tempfile.TemporaryDirectory(prefix=f"bench_{strategy_name}_") as tmpdir:
        # Write worker script
        script_path = Path(tmpdir) / "worker.py"
        script_path.write_text(WORKER_SCRIPT)

        result = subprocess.run(
            [
                sys.executable,
                str(script_path),
                strategy_name,
                pdf_path,
                tmpdir,
                str(num_pages),
                str(dpi),
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )

        if result.returncode != 0:
            print(f"  FAILED: {result.stderr.strip()}", file=sys.stderr)
            return None

        return json.loads(result.stdout.strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--pages", type=int, default=None)
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument(
        "--strategies",
        nargs="+",
        default=[
            "naive",
            "reopen_no_gc",
            "reopen_gc",
            "subprocess_pool",
            "pdfium_naive",
            "pdfium_reopen",
            "pdfium_subprocess",
        ],
    )
    args = parser.parse_args()

    if not args.pdf.exists():
        sys.exit(f"File not found: {args.pdf}")

    import fitz

    doc = fitz.open(str(args.pdf))
    total_pages = doc.page_count
    doc.close()

    num_pages = min(args.pages, total_pages) if args.pages else total_pages
    print(f"PDF: {args.pdf} ({total_pages} pages, benchmarking {num_pages})")
    print(f"DPI: {args.dpi}")
    print()

    results = []
    for name in args.strategies:
        print(f"Running: {name} ...", end=" ", flush=True)
        stats = run_strategy(name, str(args.pdf), num_pages, args.dpi)
        if stats:
            stats["strategy"] = name
            results.append(stats)
            print(
                f"peak={stats['peak_rss_mb']} MB  "
                f"(self={stats['self_rss_mb']}, children={stats['child_rss_mb']})  "
                f"time={stats['wall_time_s']}s"
            )
        else:
            print("FAILED")

    print()
    print(f"{'Strategy':<20} {'Peak RSS (MB)':>14} {'Wall time (s)':>14}")
    print("-" * 50)
    for r in results:
        print(f"{r['strategy']:<20} {r['peak_rss_mb']:>14} {r['wall_time_s']:>14}")


if __name__ == "__main__":
    main()
