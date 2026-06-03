import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def load_radical_map(radical_map_path: Path) -> Dict[str, str]:
    """
    Build a flat {variant -> canonical} replacement dict from radical_map_proposal.json.

    Sources:
      - radical_variants:           variant -> canonical  (skip self-mappings)
      - traditional_simplified_pairs: traditional -> simplified

    Used to normalise dependency strings before phantom injection, so e.g.
    艹 -> 草, 辵/辶 -> 走, 來 -> 来.  After substitution the phantom injector
    only fires for components that are truly absent from the universe.
    """
    with radical_map_path.open(encoding="utf-8") as f:
        data = json.load(f)

    mapping: Dict[str, str] = {}

    for variant, info in data.get("radical_variants", {}).items():
        canonical = info.get("canonical", variant)
        if canonical != variant:
            mapping[variant] = canonical

    for trad, info in data.get("traditional_simplified_pairs", {}).items():
        simplified = info.get("simplified", trad)
        if simplified != trad:
            mapping[trad] = simplified

    return mapping


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


def _inject_phantom_deps(
    char_deps: Dict[str, List[str]],
    char_ranks: Dict[str, int],
    max_bundle_size: int = 3,
) -> int:
    """
    For every dependency referenced in char_deps that is NOT already in the working
    set, inject a phantom node representing that unknown component.

    The phantom gets:
    - rank = median rank of the current universe
    - reverse edges back to dependents ONLY when len(dependents) <= max_bundle_size.
      Small dependent sets: reverse edges create a cycle → same SCC → same day
      (pedagogically: learn an obscure component together with its 1-3 chars).
      Large dependent sets: NO reverse edges — the phantom is a common component
      (like 糸 or 宀) that should be scheduled as a standalone node early, not
      force-bundled with hundreds of chars into one giant SCC.

    Returns the number of phantom nodes injected.
    """
    working_set = set(char_deps.keys())

    sorted_ranks = sorted(char_ranks.values())
    median_rank = sorted_ranks[len(sorted_ranks) // 2] if sorted_ranks else 5000

    missing: Dict[str, List[str]] = {}
    for ch, deps in char_deps.items():
        for dep in deps:
            if dep not in working_set:
                missing.setdefault(dep, []).append(ch)

    n_bundled = 0
    for phantom, dependents in missing.items():
        if len(dependents) <= max_bundle_size:
            # Reverse dep → cycle → same-day SCC bundle
            char_deps[phantom] = dependents
            n_bundled += 1
        else:
            # Common component: standalone phantom, no forced bundling
            char_deps[phantom] = []
        char_ranks[phantom] = median_rank

    return len(missing)


def build_char_dataset(
    dep_forest_dir: Path,
    chars_json: Path,
    max_chars: Optional[int] = None,
    freq_json: Optional[Path] = None,
    add_phantom_deps: bool = True,
    radical_map: Optional[Dict[str, str]] = None,
) -> Tuple[Dict[str, List[str]], Dict[str, str], Dict[str, int]]:
    """
    Load and return:
      char_deps     : {char: [dep_char, ...]}
      char_meanings : {char: meaning_text_for_embedding}
      char_ranks    : {char: int rank (1-based)}

    Characters are selected in rank order (most frequent first).
    If max_chars is given, only the top-max_chars by rank are kept.
    If freq_json is given, ranks come from that frequency list instead of chars.json index.
    If add_phantom_deps is True, missing dependencies are injected as phantom nodes
    bundled (same day) with the chars that need them.
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

    # Apply radical map: normalise variant/traditional dep forms to canonical chars
    # before phantom injection so 艹->草, 辵->走, 來->来, etc. resolve to real chars.
    if radical_map:
        n_replaced = 0
        for ch in list(char_deps.keys()):
            new_deps = []
            for dep in char_deps[ch]:
                mapped = radical_map.get(dep, dep)
                if mapped != dep:
                    n_replaced += 1
                new_deps.append(mapped)
            # Deduplicate while preserving order, and drop self-loops
            seen: set = set()
            char_deps[ch] = [
                d for d in new_deps
                if d != ch and not (d in seen or seen.add(d))  # type: ignore[func-returns-value]
            ]
        print(f"    {n_replaced} dependency references normalised via radical map")

    if add_phantom_deps:
        n_phantoms = _inject_phantom_deps(char_deps, char_ranks)
        print(f"    {len(char_meanings)} real chars + {n_phantoms} phantom deps injected")
    else:
        print(f"    {len(char_meanings)} real chars loaded")

    # Phantom chars: present in char_deps but absent from char_meanings (no freq rank)
    phantom_chars: set = set(char_deps.keys()) - set(char_meanings.keys())

    return char_deps, char_meanings, char_ranks, phantom_chars
