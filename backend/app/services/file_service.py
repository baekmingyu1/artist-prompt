import json
from pathlib import Path

from .storage_service import read_text_file
from ..config import PROMPT_GLOB, ROOT_DIR, SAMPLE_PATTERN


def find_prompt_file() -> Path | None:
    files = sorted(ROOT_DIR.glob(PROMPT_GLOB))
    return files[0] if files else None


def list_sample_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT_DIR.glob(SAMPLE_PATTERN)
        if path.is_file() and not path.name.endswith("-preview.json")
    )


def load_sample_content(file_name: str) -> tuple[Path, object]:
    sample_path = ROOT_DIR / file_name
    if sample_path.parent != ROOT_DIR or not sample_path.exists() or sample_path.suffix.lower() != ".json":
        raise FileNotFoundError(file_name)

    return sample_path, json.loads(read_text_file(sample_path))
