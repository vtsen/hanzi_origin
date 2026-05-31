import json
import math
from pathlib import Path
from typing import Dict, List

import numpy as np
from dotenv import load_dotenv

load_dotenv()

EMBEDDING_MODEL = "text-embedding-3-small"
_BATCH_SIZE = 512


def _normalize(v: List[float]) -> np.ndarray:
    arr = np.array(v, dtype=np.float32)
    norm = np.linalg.norm(arr)
    return arr / norm if norm > 0 else arr


def compute_and_save_embeddings(
    char_meanings: Dict[str, str],
    output_path: Path,
    model: str = EMBEDDING_MODEL,
) -> None:
    """
    Call OpenAI embeddings API for all chars and save to output_path as JSON.
    Already-saved chars are skipped if the file exists (incremental).
    """
    from openai import OpenAI
    client = OpenAI()

    # Load any previously saved embeddings so we can resume
    existing: Dict[str, List[float]] = {}
    if output_path.exists():
        with output_path.open("r", encoding="utf-8") as f:
            existing = json.load(f)

    chars_to_embed = [c for c in char_meanings if c not in existing]
    if not chars_to_embed:
        print("  All embeddings already cached.")
        return

    n_batches = math.ceil(len(chars_to_embed) / _BATCH_SIZE)
    for batch_idx in range(n_batches):
        batch_chars = chars_to_embed[batch_idx * _BATCH_SIZE:(batch_idx + 1) * _BATCH_SIZE]
        batch_texts = [char_meanings[c] for c in batch_chars]
        print(f"  Embedding batch {batch_idx + 1}/{n_batches} ({len(batch_chars)} chars)...")

        response = client.embeddings.create(model=model, input=batch_texts)
        for j, item in enumerate(response.data):
            existing[batch_chars[j]] = item.embedding

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False)
    print(f"  Saved {len(existing)} embeddings to {output_path}")


def load_embeddings(path: Path) -> Dict[str, np.ndarray]:
    """Load embeddings JSON and return normalized numpy vectors."""
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return {ch: _normalize(v) for ch, v in raw.items()}
