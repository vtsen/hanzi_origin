import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def load_dep_forest(dep_forest_dir: Path) -> Dict[str, dict]:
    """Load all dep_forest chunks into {char: etymology_dict}."""
    result: Dict[str, dict] = {}
    for chunk_file in sorted(dep_forest_dir.glob("*.json")):
        with chunk_file.open("r", encoding="utf-8") as f:
            chunk = json.load(f)
        result.update(chunk)
    return result


def load_char_ranks(chars_json: Path, freq_json: Optional[Path] = None) -> Dict[str, int]:
    """Return {char: rank} where rank is 1-based (lower = more frequent).

    If freq_json is given, it should be a JSON list of chars in frequency order
    (most frequent first). Those chars get ranks 1..N; any char not in the list
    falls back to its chars.json index (offset to be worse than all ranked chars).
    """
    with chars_json.open("r", encoding="utf-8") as f:
        data = json.load(f)
    chars_index = {entry["char"]: int(entry["index"]) for entry in data}

    if freq_json is not None and freq_json.exists():
        with freq_json.open("r", encoding="utf-8") as f:
            freq_list = json.load(f)
        freq_ranks = {ch: i + 1 for i, ch in enumerate(freq_list)}
        n_freq = len(freq_list)
        # chars not in freq list get a rank beyond the freq list, preserving chars.json order
        return {
            ch: freq_ranks[ch] if ch in freq_ranks else n_freq + idx
            for ch, idx in chars_index.items()
        }

    return chars_index


def _meaning_text(etymology_dict: dict) -> str:
    return " ".join(
        s.get("meaning", "")
        for s in etymology_dict.get("senses", [])
        if s.get("meaning")
    )


def _dependencies(etymology_dict: dict) -> List[str]:
    return etymology_dict.get("dependencies", [])


def build_char_dataset(
    dep_forest_dir: Path,
    chars_json: Path,
    max_chars: Optional[int] = None,
    freq_json: Optional[Path] = None,
) -> Tuple[Dict[str, List[str]], Dict[str, str], Dict[str, int]]:
    """
    Load and return:
      char_deps     : {char: [dep_char, ...]}
      char_meanings : {char: meaning_text_for_embedding}
      char_ranks    : {char: int rank (1-based)}

    Characters are selected in rank order (most frequent first).
    If max_chars is given, only the top-max_chars by rank are kept.
    If freq_json is given, ranks come from that frequency list instead of chars.json index.
    """
    etym_data = load_dep_forest(dep_forest_dir)
    ranks = load_char_ranks(chars_json, freq_json=freq_json)

    # Sort all available chars by rank; unknown rank goes to the end
    all_chars = sorted(etym_data.keys(), key=lambda c: ranks.get(c, 99999))
    if max_chars is not None:
        all_chars = all_chars[:max_chars]

    char_deps: Dict[str, List[str]] = {}
    char_meanings: Dict[str, str] = {}
    char_ranks: Dict[str, int] = {}

    for ch in all_chars:
        ed = etym_data[ch]
        char_deps[ch] = _dependencies(ed)
        # Use meaning text; fall back to the char itself so embeddings always have input
        text = _meaning_text(ed)
        char_meanings[ch] = text if text else ch
        char_ranks[ch] = ranks.get(ch, 99999)

    return char_deps, char_meanings, char_ranks
