from pathlib import Path

from recipebook.server import run


if __name__ == "__main__":
    base_dir = Path(__file__).parent
    run(base_dir)
