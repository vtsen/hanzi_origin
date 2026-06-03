"""
Generate data/char_info.json from dep_forest chunk files.
Maps each char to: all senses with edges (full meaning forest), formation note, deps.
"""
import json
import os
import glob

INPUT_DIR = os.path.join(os.path.dirname(__file__), 'data', 'dep_forest', 'dep_forest_for_chars')
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), 'data', 'char_info.json')
MAX_FORMATION_LEN = 300

def extract_entry(char_data):
    """Extract display fields from a single character's dep_forest entry."""
    # All senses with short keys to keep file size down
    senses = []
    for sense in char_data.get('senses', []):
        m = sense.get('meaning', '').strip()
        if not m:
            continue
        entry = {
            'i': sense.get('index', len(senses)),
            'pos': sense.get('part_of_speech', ''),
            'm': m,
        }
        # Only include examples if non-empty
        exs = [e for e in sense.get('examples', []) if e.strip()]
        if exs:
            entry['ex'] = exs
        senses.append(entry)

    # Edges: semantic evolution links between senses (short keys)
    edges = []
    for edge in char_data.get('edges', []):
        e = {
            's': edge.get('source_index'),
            't': edge.get('target_index'),
            'type': edge.get('evolution_type', ''),
        }
        note = edge.get('note', '').strip()
        if note:
            e['note'] = note
        edges.append(e)

    # Formation: note from formations[0], truncated to keep file compact
    formation = ''
    formations = char_data.get('formations', [])
    if formations:
        note = formations[0].get('note', '').strip()
        if len(note) > MAX_FORMATION_LEN:
            note = note[:MAX_FORMATION_LEN] + '…'
        formation = note

    # Dependencies
    deps = char_data.get('dependencies', [])

    return {'senses': senses, 'edges': edges, 'formation': formation, 'deps': deps}


def main():
    char_info = {}

    chunk_files = sorted(glob.glob(os.path.join(INPUT_DIR, '*.json')))
    print(f'Found {len(chunk_files)} chunk files')

    for fpath in chunk_files:
        with open(fpath, encoding='utf-8') as f:
            chunk = json.load(f)
        for char, data in chunk.items():
            char_info[char] = extract_entry(data)

    print(f'Extracted {len(char_info)} characters')

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(char_info, f, ensure_ascii=False, separators=(',', ':'))

    size_kb = os.path.getsize(OUTPUT_PATH) / 1024
    print(f'Written to {OUTPUT_PATH} ({size_kb:.0f} KB)')


if __name__ == '__main__':
    main()
