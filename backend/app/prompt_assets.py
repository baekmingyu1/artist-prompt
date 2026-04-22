from typing import Any


ARTIST_COLLECTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "artist_name": {"type": "string"},
        "activity_info": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "debut_date": {"type": "string"},
                "debut_song": {"type": "string"},
                "activity_era": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["debut_date", "debut_song", "activity_era"],
        },
        "profile": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "real_name": {"type": "string"},
                "birth_date": {"type": "string"},
                "mbti": {"type": "string"},
                "nationality": {"type": "string"},
            },
            "required": ["real_name", "birth_date", "mbti", "nationality"],
        },
        "performances": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "title": {"type": "string"},
                },
                "required": ["type", "start_date", "end_date", "title"],
            },
        },
    },
    "required": ["artist_name", "activity_info", "profile", "performances"],
}


INTRODUCTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "universe": {"type": "string"},
        "interview": {"type": "string"},
    },
    "required": ["summary", "universe", "interview"],
}
