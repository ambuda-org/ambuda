import distutils
import subprocess
from pathlib import Path


REPO = "https://github.com/ambuda-org/ambuda-i18n.git"
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data" / "ambuda-i18n"


def fetch_git_repo(url: str, path: Path):
    """Fetch the latest version of the given repo."""
    if not path.exists():
        subprocess.run(f"mkdir -p {path}", shell=True)
        subprocess.run(f"git clone --branch=main {url} {path}", shell=True)

    subprocess.call("git fetch origin", shell=True, cwd=path)
    subprocess.call("git checkout main", shell=True, cwd=path)
    subprocess.call("git reset --hard origin/main", shell=True, cwd=path)


def compile_translations(path: Path):
    subprocess.call(f"pybabel compile -d {path}", shell=True)


def copy_translation_files(src_dir: Path, dest_dir: Path):
    distutils.dir_util.copy_tree(str(src_dir), str(dest_dir))


def main():
    src_dir = DATA_DIR / "translations"
    dest_dir = PROJECT_DIR / "ambuda" / "translations"

    fetch_git_repo(REPO, DATA_DIR)
    compile_translations(src_dir)
    copy_translation_files(src_dir, dest_dir)


if __name__ == "__main__":
    main()
