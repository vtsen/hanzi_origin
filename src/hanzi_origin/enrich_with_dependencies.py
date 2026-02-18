from pathlib import Path
import json
import sys
from dotenv import load_dotenv
from enum import Enum
from typing import Any, Optional

from src.hanzi_origin.etymology import Etymology
from etymology import load_from_file, Dependencies
from utils.deps import most_frequent_dependency

load_dotenv()

def _enum_serializer(obj: Any) -> Any:
    if isinstance(obj, Enum):
        return obj.value
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def call_dep_enricher(
    instance: Etymology,
    hanzi: str,
    model: str = "gpt-4o-mini",
) -> Optional[Any]:
    from openai import OpenAI
    client = OpenAI()

    response = client.responses.parse(
        model=model,
        input=[
            {
                "role": "system",
                "content": """
                You are a professional linguist specializing in Chinese historical semantics and etymology, and you are given the description of the ogic of initial formation of the character. \n
                Find the dependent Hanzi characters that the target character was originally formed from.\n
                Crucial note: \n
                - Do NOT include the target character itself!\n
                - If a radical is not a common independent characters, use its contemporary conterparty, e.g. use '草' instead of '艹', and use '人' instead of '亻' or '彳'.\n  
                - It is completely possible that no dependency exists (e.g. pure pictograph, unknown origin, etc.), in which case return an EMPTY list.
                - If you are unsure, it is OK to give an EMPTY list as result. Do not hallucinate!\n
                SCHEMA DESCRIPTION:\n\n
                The output JSON must contain only a single array of strings. Each string object in the list represents one distinct charactor it depends on and must be a single charactor.\n\n

                You will be given ONE Chinese character as input. Produce exactly ONE JSON object following the schema above.
                """
            },
            {
                "role": "user",
                "content": f"""What are the upstream dependency of the Chinese character '{hanzi}'?\n
                Provide your answer in JSON format according to the specified schema.
                Below are the initial meaning and logic of formation:\n{instance.formations}""",
            },
        ],
        text_format=Dependencies,
    )

    parsed_results = response.output_parsed
    return parsed_results


def generate_etymology_files(
    input_json: Path | str,
    model: str = "gpt-4o-mini",
    start_index: int = 0,
    end_index: int = 10,
    num_votes: int = 1,
) -> None:
    ip = Path(input_json)
    project_root = Path(__file__).resolve().parent.parent.parent

    if not ip.exists():
        candidate = project_root / "data" / ip
        if candidate.exists():
            ip = candidate
        else:
            raise FileNotFoundError(f"Input file not found: {input_json}")

    task_name = ip.stem
    etym_dir = project_root / "data" / "etymology" / f"etymology_for_{task_name}"

    # load input
    with ip.open("r", encoding="utf-8") as fh:
        rows = json.load(fh)

    if not isinstance(rows, list):
        raise ValueError("Input JSON must be a list of objects")

    output_results = dict()
    for entry in rows:
        idx = entry.get("index")
        ch = entry.get("char")
        if idx is None or not ch:
            print(f"skipping entry without index/char: {entry}", file=sys.stderr)
            continue
        if int(idx) < start_index:
            continue
        if int(idx) > end_index:
            break

        etym_file = etym_dir / f"{idx}.json"
        if not etym_file.exists():
            print(f"skip {idx} {ch} due to missing etymology", file=sys.stderr)
            continue

        try:
            instance = load_from_file(etym_file)
            results = []
            for _ in range(num_votes):
                results.append(call_dep_enricher(instance, ch, model=model).dependencies)
            instance.dependencies = [c for c in most_frequent_dependency(results) if c != ch]
            output_results[ch] = instance.model_dump(by_alias=False, exclude_none=True)
            print(f"Done with {idx} {ch}: {instance.dependencies}", file=sys.stdout)
        except Exception as exc:
            print(f"error calling etymology for {ch} ({idx}): {exc}", file=sys.stderr)
            continue

    out_dir = project_root / "data" / "dep_forest" / f"dep_forest_for_{task_name}" / f"{start_index}_to_{end_index}.json"
    p = Path(out_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(
            output_results,
            f,
            ensure_ascii = False,
            indent = 2,
            default = _enum_serializer,
        )
    print(f"Wrote to {out_dir}", file=sys.stderr)


if __name__ == '__main__':
    for i_chunk in range(34):
        generate_etymology_files("chars.json",
                                 model="gpt-4o",
                                 start_index=200 * i_chunk,
                                 end_index=200 * (i_chunk + 1),
                                 num_votes=3,
                                 )
