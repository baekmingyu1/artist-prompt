import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..config import DATA_DIR, HISTORY_FILE


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _default_usage() -> dict[str, int]:
    return {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0,
    }


def _default_pricing() -> dict[str, Any]:
    return {
        "currency": "USD",
        "estimated_cost_usd": None,
        "estimated_cost_krw": None,
        "input_cost_usd": None,
        "cached_input_cost_usd": None,
        "output_cost_usd": None,
        "price_reference": "unknown",
        "price_table": None,
    }


def _merge_usage(value: Any) -> dict[str, Any]:
    merged = _default_usage()
    if isinstance(value, dict):
        merged.update({key: value.get(key, default) for key, default in merged.items()})
    return merged


def _merge_pricing(value: Any) -> dict[str, Any]:
    merged = _default_pricing()
    if isinstance(value, dict):
        for key, default in merged.items():
            merged[key] = value.get(key, default)
    return merged


def _normalize_web_sources(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    normalized_sources: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        normalized_sources.append(
            {
                "type": item.get("type"),
                "title": item.get("title"),
                "url": item.get("url"),
            }
        )
    return normalized_sources


def _normalize_stage_results(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    normalized_results: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        normalized_results.append(
            {
                "stage": item.get("stage", ""),
                "model": item.get("model", ""),
                "duration_ms": item.get("duration_ms", 0),
                "output_text": item.get("output_text", ""),
                "parsed_json": item.get("parsed_json"),
                "usage": _merge_usage(item.get("usage")),
                "pricing": _merge_pricing(item.get("pricing")),
                "web_sources": _normalize_web_sources(item.get("web_sources")),
            }
        )
    return normalized_results


def ensure_history_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not HISTORY_FILE.exists():
        HISTORY_FILE.write_text("[]", encoding="utf-8")


def load_history() -> list[dict[str, Any]]:
    ensure_history_storage()
    try:
        records = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    normalized_records: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue

        normalized_records.append(
            {
                "run_id": record.get("run_id", str(uuid4())),
                "created_at": record.get(
                    "created_at",
                    datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                ),
                "model": record.get("model", ""),
                "stage_models": record.get("stage_models", {}),
                "artist_name": record.get("artist_name", ""),
                "reasoning_effort": record.get("reasoning_effort", "medium"),
                "use_web_search": record.get("use_web_search", False),
                "duration_ms": record.get("duration_ms", 0),
                "usage": _merge_usage(record.get("usage")),
                "pricing": _merge_pricing(record.get("pricing")),
                "stage_results": _normalize_stage_results(record.get("stage_results")),
                "web_source_count": record.get("web_source_count", 0),
                "output_preview": record.get("output_preview", ""),
                "parsed_json": record.get("parsed_json"),
            }
        )

    return normalized_records


def save_history(records: list[dict[str, Any]]) -> None:
    ensure_history_storage()
    HISTORY_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def append_history(record: dict[str, Any]) -> None:
    records = load_history()
    records.insert(0, record)
    save_history(records[:100])
