"""
Hanzi Learning Plan Generator
==============================
Entry point.  Run as:

    py -m hanzi_learning_plan.run          # full scale (default params)
    py -m hanzi_learning_plan.run --mvp   # MVP: 100 chars, 5 days (passed via __main__ block)
"""

import json
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from .data_loader import build_char_dataset
from .embeddings import compute_and_save_embeddings, load_embeddings
from .graph import build_condensed_graph
from .scheduler import compute_importance, greedy_schedule, local_search, day_coherence, propagate_importance, ImportanceMode

load_dotenv()


def run(
    dep_forest_dir: Path,
    chars_json: Path,
    embeddings_path: Path,
    output_dir: Path,
    M: int = 15,
    N: int = 200,
    w: float = 0.5,
    lambda_val: float = 0.002,
    L_factor: int = 3,
    max_chars: Optional[int] = None,
    embedding_model: str = "text-embedding-3-small",
    freq_json: Optional[Path] = None,
    importance_mode: ImportanceMode = "raw",
    importance_decay: float = 0.5,
) -> dict:
    """
    Full pipeline: load data → embed → build graph → schedule → local search → save.

    Parameters
    ----------
    dep_forest_dir   : directory containing dep_forest chunk JSONs
    chars_json       : path to data/chars.json (fallback rank source)
    embeddings_path  : where to cache/load OpenAI embeddings
    output_dir       : where to write the learning plan JSON
    M                : max chars per day
    N                : number of days to plan
    w                : weight for importance vs. semantic coherence [0,1]
    lambda_val       : decay coefficient for importance = exp(-lambda * rank)
    L_factor         : candidate pool size = L_factor * M
    max_chars        : if set, only use the top-max_chars by frequency rank
    embedding_model  : OpenAI embedding model name
    freq_json        : path to char_freq_rank.json (ordered list of chars by frequency)
    importance_mode  : "raw" | "max_descendant" | "decayed" — how to propagate importance
    importance_decay : decay factor per hop (only used when importance_mode="decayed")
    """
    print("=== Hanzi Learning Plan Generator ===")

    # 1. Load data
    print(f"\n[1] Loading data (max_chars={max_chars}, freq_json={freq_json})...")
    char_deps, char_meanings, char_ranks = build_char_dataset(
        dep_forest_dir, chars_json, max_chars=max_chars, freq_json=freq_json
    )
    print(f"    {len(char_deps)} chars loaded")

    # 2. Embeddings
    print(f"\n[2] Embeddings -> {embeddings_path}")
    if not embeddings_path.exists():
        print("    Computing via OpenAI API...")
        compute_and_save_embeddings(char_meanings, embeddings_path, model=embedding_model)
    else:
        print("    Loading cached embeddings...")
    embeddings = load_embeddings(embeddings_path)
    print(f"    {len(embeddings)} vectors loaded")

    # 3. Importance
    print(f"\n[3] Importance: I = exp(-{lambda_val} * rank)")
    importances = {
        ch: compute_importance(rank, lambda_val)
        for ch, rank in char_ranks.items()
    }

    # 4. Condensed graph
    print(f"\n[4] Building condensed dependency graph...")
    nodes, _ = build_condensed_graph(char_deps, importances, embeddings)
    n_merged = sum(1 for n in nodes if len(n.chars) > 1)
    print(f"    {len(nodes)} nodes ({n_merged} merged SCCs from cycles)")

    # 4b. Importance propagation
    print(f"\n[4b] Importance propagation: mode={importance_mode}" +
          (f", decay={importance_decay}" if importance_mode == "decayed" else ""))
    propagate_importance(nodes, mode=importance_mode, decay=importance_decay)

    # 5. Greedy schedule
    print(f"\n[5] Greedy scheduling (M={M}, N={N}, w={w}, L={L_factor}*M={L_factor*M})...")
    schedule = greedy_schedule(nodes, M=M, N=N, w=w, L_factor=L_factor)
    n_scheduled = sum(len(d) for d in schedule)
    print(f"    {n_scheduled} nodes across {len(schedule)} days")

    # 6. Local search
    print(f"\n[6] Local search improvement...")
    node_map = {n.id: n for n in nodes}
    schedule = local_search(schedule, nodes, M=M, N=N, w=w)

    # 7. Build output
    print(f"\n[7] Building output...")
    output_schedule: dict = {}
    per_day_stats = []

    for d, day_node_ids in enumerate(schedule, 1):
        day_chars = [ch for nid in day_node_ids for ch in node_map[nid].chars]
        output_schedule[str(d)] = day_chars
        coh, _ = day_coherence(day_node_ids, node_map)
        per_day_stats.append({
            "day": d,
            "n_chars": len(day_chars),
            "coherence": round(coh, 4),
        })

    total_chars = sum(len(v) for v in output_schedule.values())
    avg_coh = sum(s["coherence"] for s in per_day_stats) / len(per_day_stats) if per_day_stats else 0.0

    result = {
        "params": {
            "M": M,
            "N": N,
            "w": w,
            "lambda": lambda_val,
            "importance_mode": importance_mode,
            "importance_decay": importance_decay if importance_mode == "decayed" else None,
            "total_chars_available": len(char_deps),
            "embedding_model": embedding_model,
        },
        "stats": {
            "total_chars_scheduled": total_chars,
            "days_used": len(schedule),
            "avg_daily_coherence": round(avg_coh, 4),
            "per_day": per_day_stats,
        },
        "schedule": output_schedule,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    char_part = f"_{max_chars}chars" if max_chars else ""
    mode_tag = f"decayed{importance_decay}" if importance_mode == "decayed" else importance_mode
    out_file = output_dir / f"learning_plan{char_part}_{N}days_{mode_tag}.json"
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nSaved -> {out_file}")

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    # Ensure Chinese characters print correctly on Windows terminals
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    mvp = "--mvp" in sys.argv
    plan30 = "--plan30" in sys.argv

    project_root = Path(__file__).resolve().parent.parent.parent

    if mvp:
        # MVP: 100 chars, 5 days, 15/day
        params = dict(max_chars=100, N=5, M=15)
        emb_file = "embeddings_mvp.json"
        modes = [("raw", 0.5)]
        print("Running MVP (100 chars, 5 days, 15/day)")
    elif plan30:
        # All chars, 30 days, 20/day — run all 3 importance modes for comparison
        params = dict(max_chars=None, N=30, M=20)
        emb_file = "embeddings_full.json"
        modes = [("raw", 0.5), ("max_descendant", 0.5), ("decayed", 0.5)]
        print("Running plan30 (all chars, 30 days, 20/day) — 3 importance modes")
    else:
        # Full scale
        params = dict(max_chars=None, N=200, M=15)
        emb_file = "embeddings_full.json"
        modes = [("raw", 0.5)]
        print("Running full scale (all chars, 200 days, 15/day)")

    common = dict(
        dep_forest_dir=project_root / "data" / "dep_forest" / "dep_forest_for_chars",
        chars_json=project_root / "data" / "chars.json",
        freq_json=project_root / "data" / "char_freq_rank.json",
        embeddings_path=project_root / "data" / "learning_plan" / emb_file,
        output_dir=project_root / "data" / "learning_plan",
        w=0.3,
        lambda_val=0.0005,
        L_factor=200,
        embedding_model="text-embedding-3-small",
    )

    results = {}
    for imp_mode, imp_decay in modes:
        print(f"\n{'='*60}")
        print(f"MODE: {imp_mode}" + (f"  decay={imp_decay}" if imp_mode == "decayed" else ""))
        print('='*60)
        results[imp_mode] = run(**common, **params,
                                importance_mode=imp_mode, importance_decay=imp_decay)

    # --- Comparison summary ---
    print(f"\n{'='*60}")
    print("COMPARISON SUMMARY")
    print('='*60)
    check_chars = ['的', '勺', '日', '一', '是', '不', '了', '在', '人', '有']
    for imp_mode, _ in modes:
        r = results[imp_mode]
        schedule = r["schedule"]
        all_scheduled = {c: d for d, chars in schedule.items() for c in chars}
        print(f"\n[{imp_mode}]  avg_coherence={r['stats']['avg_daily_coherence']}  "
              f"total={r['stats']['total_chars_scheduled']}")
        print("  Key chars — day scheduled (- = not in plan):")
        for c in check_chars:
            day = all_scheduled.get(c, '-')
            print(f"    {c}: day {day}")
        print("  Day 1:", schedule.get("1", []))
        print("  Day 2:", schedule.get("2", []))
