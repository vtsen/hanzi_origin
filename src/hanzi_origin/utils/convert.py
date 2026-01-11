from pathlib import Path
from typing import List, Dict, Optional
import json
import re

MINIMAL_SUBSET = "人上木本明好休信看从来发后干面学国说情河"


def _parse_line(line: str) -> Optional[Dict]:
    line = line.rstrip("\n")
    if not line.strip():
        return None

    parts = line.split("\t")
    if len(parts) < 3:
        return None

    index = parts[0].strip()
    char = parts[1].strip()
    rest = "\t".join(parts[2:]) if len(parts) > 2 else ""

    # extract parenthesis and bracket contents
    paren_matches = re.findall(r"\((.*?)\)", rest)
    bracket_matches = re.findall(r"\[(.*?)\]", rest)

    def _split_alt(s: str) -> List[str]:
        # split on pipe and strip each item
        return [it.strip() for it in re.split(r"\|", s) if it.strip()]

    traditional: List[str] = []
    for m in paren_matches:
        traditional.extend(_split_alt(m))

    variant: List[str] = []
    for m in bracket_matches:
        variant.extend(_split_alt(m))

    # remove annotations from rest to isolate pinyin
    rest_clean = re.sub(r"\(.*?\)", "", rest)
    rest_clean = re.sub(r"\[.*?\]", "", rest_clean)
    rest_clean = rest_clean.replace("\t", " ").strip()

    # split pinyin by comma (the source uses comma-separated pinyin)
    pinyin_list: List[str] = []
    if rest_clean:
        pinyin_list = [p.strip() for p in rest_clean.split(",") if p.strip()]

    entry: Dict = {"index": index, "char": char, "pinyin": pinyin_list}
    if traditional:
        entry["traditional_chars"] = traditional
    if variant:
        entry["variant_chars"] = variant

    return entry


def parse_chars_file(path: Path) -> List[Dict]:
    """
    Parse `data/chars.txt` into a list of dicts.
    """
    results: List[Dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for ln in fh:
            parsed = _parse_line(ln)
            if parsed:
                results.append(parsed)
    return results


def save_as_json(data: List[Dict], out: Path) -> None:
    """
    Save parsed data as JSON with UTF-8 output (Chinese kept readable).
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def convert():
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    src = project_root / "data" / "chars.txt"
    # https://github.com/lqfeng/ChineseCharacters/blob/master/%E9%80%9A%E7%94%A8%E8%A7%84%E8%8C%83%E6%B1%89%E5%AD%97%E8%A1%A8(2013)%E5%85%A8%E9%83%A8(8105%E5%AD%97)%E5%90%AB%E6%8B%BC%E9%9F%B3%E3%80%81%E7%B9%81%E4%BD%93%E5%AD%97%E3%80%81%E5%BC%82%E4%BD%93%E5%AD%97.txt
    dst = project_root / "data" / "chars.json"

    parsed = parse_chars_file(src)
    save_as_json(parsed, dst)


def make_subset():
    """
    Make a subset of chars.json containing only characters in MINIMAL_SUBSET.
    """
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    src = project_root / "data" / "chars.json"
    dst = project_root / "data" / "chars_subset.json"

    with src.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    subset = [entry for entry in data if entry["char"] in MINIMAL_SUBSET]

    save_as_json(subset, dst)


if __name__ == "__main__":
    # convert()
    make_subset()
