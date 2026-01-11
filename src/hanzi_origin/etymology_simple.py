# python
from enum import Enum
from pathlib import Path
from typing import Any

import json
from pydantic import BaseModel, Field
from typing import List, Optional


class Sense(BaseModel):
    """
    单一释义节点（图中的一个点）
    """
    index: int = Field(
        ...,
        description="释义的唯一索引，用于在词源图中引用"
    )
    part_of_speech: str = Field(
        ...,
        description="词性，如：名词、动词、形容词、助词等"
    )
    meaning: str = Field(
        ...,
        description="该释义的简要定义"
    )
    examples: List[str] = Field(
        default_factory=list,
        description="例句列表，可为空"
    )
    traditional_chars: List[str] = Field(
        default_factory=list,
        description="该释义对应的繁体字列表（如果有），可为空"
    )


class Etymology(BaseModel):
    """
    一个字或词的整体词源演变结构（DAG）
    """
    senses: List[Sense] = Field(
        ...,
        description="所有释义节点"
    )


def _enum_serializer(obj: Any) -> Any:
    if isinstance(obj, Enum):
        return obj.value
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def load_from_file(path: Path | str) -> Etymology:
    """Load Etymology from a JSON file."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return Etymology.model_validate(data)


def load_from_str(s: str) -> Etymology:
    """Load Etymology from a JSON string."""
    return Etymology.model_validate_json(s)


def save_to_file(instance: Etymology, path: Path | str) -> None:
    """Save Etymology to a JSON file (UTF-8, pretty-printed)."""
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


def save_to_str(instance: Etymology) -> str:
    """Return a pretty JSON string for Etymology."""
    return json.dumps(
        instance.model_dump(by_alias=False, exclude_none=True),
        ensure_ascii=False,
        indent=2,
        default=_enum_serializer,
    )