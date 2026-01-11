# python
from enum import Enum
from pathlib import Path
from typing import Any

import json
from pydantic import BaseModel, Field


class Mechanism(str, Enum):
    """造字逻辑类别 (mechanism)"""
    glyph_origin = "glyph_origin"
    semantic_extension = "semantic_extension"
    phonetic = "phonetic"
    other = "other"


class Confidence(str, Enum):
    """置信度 (confidence)"""
    low = "low"
    medium = "medium"
    high = "high"


class HanziSchema(BaseModel):
    mechanism: Mechanism = Field(..., description="造字逻辑类别")
    original_meaning: str = Field(..., description="最初的本义")
    description: str = Field(..., description="本义说明和演变解释")
    confidence: Confidence = Field(..., description="置信度")

    class Config:
        extra = "forbid"
        title = "Hanzi JSON Schema"
        use_enum_values = False


def _enum_serializer(obj: Any) -> Any:
    if isinstance(obj, Enum):
        return obj.value
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def load_hanzi_schema_from_file(path: Path | str) -> HanziSchema:
    """Load a HanziSchema from a JSON file."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return HanziSchema.model_validate(data)


def load_hanzi_schema_from_str(s: str) -> HanziSchema:
    """Load a HanziSchema from a JSON string."""
    return HanziSchema.model_validate_json(s)


def save_hanzi_schema_to_file(instance: HanziSchema, path: Path | str) -> None:
    """Save a HanziSchema to a JSON file (UTF-8, pretty-printed)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(
            instance.model_dump(by_alias=False, exclude_none=True),
            f,
            ensure_ascii=False,
            indent=2,
            default=_enum_serializer,
        )


def save_hanzi_schema_to_str(instance: HanziSchema) -> str:
    """Return a pretty JSON string for a HanziSchema."""
    return json.dumps(
        instance.model_dump(by_alias=False, exclude_none=True),
        ensure_ascii=False,
        indent=2,
        default=_enum_serializer,
    )