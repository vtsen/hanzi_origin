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
    traditional_char: str = Field(
        description="该释义对应的繁体字（可能与简体字相同）"
    )


class CharacterFormationType(str, Enum):
    # ===== 表意类（semantic formation）=====
    PICTOGRAPH = "pictograph"              # 象形
    SIMPLE_INDICATIVE = "simple_indicative"  # 指事
    COMPOUND_IDEOGRAPH = "compound_ideograph"  # 会意

    # ===== 表音 + 表意类（phonosemantic）=====
    PHONO_SEMANTIC_COMPOUND = "phono_semantic_compound"  # 形声

    # ===== 用字策略类（usage-based, not graphic creation）=====
    LOAN_CHARACTER = "loan_character"      # 假借（用已有字表音）

    UNKNOWN = "unknown"


class CharacterFormation(BaseModel):
    """
    描述单个汉字的造字逻辑（creation-stage analysis）
    """
    formation_type: CharacterFormationType = Field(
        ...,
        description="造字方法（基于六书并经现代语言学修订）"
    )
    original_sense_index: int = Field(
        ...,
        description="该字最初造字时所对应的本意，对应 senses 中的某一个 index"
    )
    note: str | None = Field(
        None,
        description="关于造字过程的补充说明，如部件分析、学界争议等"
    )


class EvolutionType(str, Enum):
    # ===== 语义演变（semantic change）=====
    SEMANTIC_EXTENSION = "semantic_extension"        # 义项扩展（泛化）
    SEMANTIC_NARROWING = "semantic_narrowing"         # 义项收缩（特指化）
    SEMANTIC_SHIFT = "semantic_shift"                 # 义移（中心改变）
    METAPHOR = "metaphor"                             # 隐喻
    METONYMY = "metonymy"                             # 转喻
    SYNECDOCHE = "synecdoche"                         # 提喻
    PEJORATION = "pejoration"                         # 贬义化
    AMELIORATION = "amelioration"                     # 褒义化

    # ===== 语法 / 功能演变（grammatical change）=====
    GRAMMATICALIZATION = "grammaticalization"         # 语法化
    FUNCTION_WORD_DEVELOPMENT = "function_word"       # 实词 → 虚词

    # ===== 其他 =====
    CONVERSION = "conversion"                         # 词类活用
    LOAN_SHIFT = "phonetical_loan_shift"              # 假借义演变
    ANALOGICAL_CHANGE = "analogy"                     # 类推
    REANALYSIS = "reanalysis"                         # 重新分析
    UNKNOWN = "unknown"                               # 无法确定


class EtymologyEdge(BaseModel):
    """
    词源演变图中的一条有向边
    """
    source_index: int = Field(
        ...,
        description="起点释义的 index"
    )
    target_index: int = Field(
        ...,
        description="终点释义的 index"
    )
    evolution_type: EvolutionType = Field(
        ...,
        description="演变类型"
    )
    note: Optional[str] = Field(
        None,
        description="补充说明（如时代、文献、争议等）"
    )


class Etymology(BaseModel):
    """
    一个字或词的整体词源演变结构（DAG）
    """
    senses: List[Sense] = Field(
        ...,
        description="所有释义节点"
    )
    formations: List[CharacterFormation] = Field(
        ...,
        description="最初造字逻辑及对应的含义"
    )
    edges: List[EtymologyEdge] = Field(
        default_factory=list,
        description="演变关系（允许不联通）"
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