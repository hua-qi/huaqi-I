from pathlib import Path


def is_first_run(telos_dir: Path) -> bool:
    if not telos_dir.exists():
        return True
    return len(list(telos_dir.glob("*.md"))) == 0
