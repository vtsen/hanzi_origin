from pathlib import Path
import json
import sys

from src.hanzi_origin.etymology import save_to_file
from utils.meaning import fetch_ziyi
from gpt_etymology import call_etymology


def generate_etymology_files(
    input_json: Path | str,
    model: str = "gpt-4o-mini",
    overwrite: bool = False,
    max_chars: int = 3,
) -> None:
    """
    Read a JSON list (each entry with 'index' and 'char' and optional
    'traditional_chars'), fetch meanings via fetch_ziyi, call
    call_etymology(hanzi, traditional_chars, initial_meaning, contemporary_meanings),
    and save per-index JSON files under data/etymology/etymology_for_<task_name>.
    """
    ip = Path(input_json)
    project_root = Path(__file__).resolve().parent.parent.parent

    if not ip.exists():
        candidate = project_root / "data" / ip
        if candidate.exists():
            ip = candidate
        else:
            raise FileNotFoundError(f"Input file not found: {input_json}")

    task_name = ip.stem
    out_dir = project_root / "data" / "etymology" / f"etymology_for_{task_name}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # load input
    with ip.open("r", encoding="utf-8") as fh:
        rows = json.load(fh)

    if not isinstance(rows, list):
        raise ValueError("Input JSON must be a list of objects")

    n_successful_chars = 0
    for entry in rows:
        idx = entry.get("index")
        ch = entry.get("char")
        if idx is None or not ch:
            print(f"skipping entry without index/char: {entry}", file=sys.stderr)
            continue

        out_file = out_dir / f"{idx}.json"
        if out_file.exists() and not overwrite:
            print(f"skip existing {out_file}", file=sys.stderr)
            continue

        traditional_chars = entry.get("traditional_chars") or []
        print(f"processing {ch} ({idx})...", file=sys.stdout)

        try:
            initial_meaning, contemporary_meanings = fetch_ziyi(ch)
        except Exception as exc:
            print(f"error fetching meanings for {ch} ({idx}): {exc}", file=sys.stderr)
            continue

        try:
            result = call_etymology(ch, traditional_chars, initial_meaning, contemporary_meanings,
                                    model=model)
        except Exception as exc:
            print(f"error calling etymology for {ch} ({idx}): {exc}", file=sys.stderr)
            continue

        try:
            save_to_file(result, out_file)
        except Exception as exc:
            print(f"error saving etymology for {ch} ({idx}) to {out_file}: {exc}", file=sys.stderr)
            continue

        # cap successful count in one call
        n_successful_chars += 1
        if n_successful_chars >= max_chars:
            print(f"reached max_chars={max_chars}, stopping.", file=sys.stderr)
            break

    print(f"wrote etymology files to {out_dir}", file=sys.stderr)


if __name__ == '__main__':
    generate_etymology_files("chars.json",
                             model="gpt-4.1",
                             max_chars=1000,
                             )
