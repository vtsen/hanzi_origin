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

from .data_loader import build_char_dataset, load_radical_map
from .embeddings import compute_and_save_embeddings, load_embeddings
from .graph import build_condensed_graph
from .scheduler import compute_importance, greedy_schedule, jit_greedy_schedule, local_search, swap_local_search, day_coherence, propagate_importance, ImportanceMode

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
    add_phantom_deps: bool = True,
    jit_gamma: float = 1.0,
    freq_threshold: float = 0.135,
    radical_map_path: Optional[Path] = None,
    freq_boost_cap: int = 3000,
    dep_beta: float = 0.1,
    deadline_factor: float = 5.0,
    deadline_weight: float = 0.5,
    freq_early_weight: float = 0.0,
) -> dict:
    """
    Full pipeline: load data → embed → build graph → schedule → local search → save.

    Parameters
    ----------
    dep_forest_dir    : directory containing dep_forest chunk JSONs
    chars_json        : path to data/chars.json (fallback rank source)
    embeddings_path   : where to cache/load OpenAI embeddings
    output_dir        : where to write the learning plan JSON
    M                 : max chars per day (phantoms are free and don't count)
    N                 : number of days to plan
    w                 : importance vs. coherence balance [0,1]; higher → prioritise
                        frequent chars over same-topic clustering
    lambda_val        : exponential decay for base importance = exp(-λ × rank)
    L_factor          : greedy candidate pool = L_factor × M nodes per day
    max_chars         : if set, only use the top-max_chars by frequency rank
    embedding_model   : OpenAI embedding model name
    freq_json         : path to char_freq_rank.json (ordered list of chars by frequency)
    importance_mode   : "raw" | "max_descendant" | "decayed" | "additive" |
                        "additive_freq_gated" | "additive_gap" | "jit"
    importance_decay  : decay factor / α coefficient for propagation modes
    add_phantom_deps  : inject phantom nodes for deps missing from the universe
    freq_threshold    : base-importance gate for additive_freq_gated
                        (default ≈ exp(-0.001×2000) ≈ 0.135)
    freq_boost_cap    : top-N linear ramp bonus: I += max(0, (cap-rank)/cap)
                        gives rank-1 chars an extra +1.0 tapering to 0 at cap;
                        set to 0 to disable
    dep_beta          : dependency-overlap weight in coherence [0, 1]
                        coherence = (1-dep_beta)×embedding_sim + dep_beta×dep_overlap_sim
                        0.5 gives equal weight to structural and semantic similarity
    freq_early_weight : swap bias that rewards moving high-importance chars earlier:
                        Δ = (imp_B − imp_A) × (d2 − d1) / D added to swap score.
                        Values in [0.1, 0.5] are effective; 0 disables the term.
    """
    print("=== Hanzi Learning Plan Generator ===")

    # 1. Load data
    radical_map = None
    if radical_map_path and radical_map_path.exists():
        radical_map = load_radical_map(radical_map_path)
        print(f"\n[1] Loading data (max_chars={max_chars}, phantoms={add_phantom_deps}, "
              f"radical_map={len(radical_map)} entries)...")
    else:
        print(f"\n[1] Loading data (max_chars={max_chars}, phantoms={add_phantom_deps})...")
    char_deps, char_meanings, char_ranks, phantom_chars = build_char_dataset(
        dep_forest_dir, chars_json, max_chars=max_chars, freq_json=freq_json,
        add_phantom_deps=add_phantom_deps, radical_map=radical_map,
    )

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
    boost_desc = f" + max(0, ({freq_boost_cap}-rank)/{freq_boost_cap})" if freq_boost_cap > 0 else ""
    print(f"\n[3] Importance: I = exp(-{lambda_val} * rank){boost_desc}")
    importances = {
        ch: compute_importance(rank, lambda_val, freq_boost_cap=freq_boost_cap)
        for ch, rank in char_ranks.items()
    }

    # 4. Condensed graph
    print(f"\n[4] Building condensed dependency graph...")
    nodes, _ = build_condensed_graph(char_deps, importances, embeddings,
                                     char_ranks=char_ranks, phantom_chars=phantom_chars)
    n_merged = sum(1 for n in nodes if len(n.chars) > 1)
    print(f"    {len(nodes)} nodes ({n_merged} merged SCCs from cycles)")

    # 4b. Importance propagation (not used in JIT mode — urgency is dynamic)
    if importance_mode != "jit":
        print(f"\n[4b] Importance propagation: mode={importance_mode}" +
              (f", decay={importance_decay}" if importance_mode == "decayed" else ""))
        propagate_importance(nodes, mode=importance_mode, decay=importance_decay,
                             freq_threshold=freq_threshold)
    else:
        print(f"\n[4b] JIT mode: skipping static propagation (urgency computed dynamically)")

    # 5. Greedy schedule
    print(f"\n[5] Greedy scheduling (M={M}, N={N}, w={w}, L={L_factor}*M={L_factor*M})...")
    if importance_mode == "jit":
        print(f"    JIT mode: gamma={jit_gamma}, dep_beta={dep_beta}")
        schedule = jit_greedy_schedule(nodes, M=M, N=N, w=w, L_factor=L_factor,
                                       gamma=jit_gamma, dep_beta=dep_beta,
                                       deadline_factor=deadline_factor, deadline_weight=deadline_weight)
    else:
        schedule = greedy_schedule(nodes, M=M, N=N, w=w, L_factor=L_factor, dep_beta=dep_beta,
                                   deadline_factor=deadline_factor, deadline_weight=deadline_weight)
    n_scheduled = sum(len(d) for d in schedule)
    print(f"    {n_scheduled} nodes across {len(schedule)} days")

    # 6. Local search (swap-based)
    node_map = {n.id: n for n in nodes}
    # Compute avg coherence before local search for comparison
    coh_before = sum(
        day_coherence(day, node_map)[0] for day in schedule
    ) / len(schedule) if schedule else 0.0
    print(f"\n[6] Swap local search improvement (avg coherence before: {coh_before:.4f})...")
    # Persist coherence-before so background capture doesn't lose it
    try:
        import json as _json
        output_dir.mkdir(parents=True, exist_ok=True)
        _coh_path = output_dir / "coh_before.json"
        with _coh_path.open("w") as _f:
            _json.dump({"coh_before": round(coh_before, 6)}, _f)
    except Exception as _e:
        print(f"  [warn] coh_before write failed: {_e}")
    # Scale iterations and window with schedule size; large plans converge quickly
    _swap_max_iters = max(10, min(200, 600 // max(1, N // 10)))
    _day_window = min(15, max(5, N // 10))
    schedule = swap_local_search(schedule, nodes, M=M, N=N, w=w, dep_beta=dep_beta,
                                 max_iters=_swap_max_iters, day_window=_day_window,
                                 freq_early_weight=freq_early_weight)

    # 7. Build output (exclude phantom nodes from schedule and coherence)
    print(f"\n[7] Building output...")
    output_schedule: dict = {}
    per_day_stats = []

    for d, day_node_ids in enumerate(schedule, 1):
        real_node_ids = [nid for nid in day_node_ids if not node_map[nid].is_phantom]
        if not real_node_ids:
            continue  # skip days that only have phantom nodes (dependency-only days)
        day_chars = [ch for nid in real_node_ids for ch in node_map[nid].chars]
        output_schedule[str(d)] = day_chars
        coh, _ = day_coherence(real_node_ids, node_map)
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
            "freq_boost_cap": freq_boost_cap,
            "dep_beta": dep_beta,
            "importance_mode": importance_mode,
            "importance_decay": importance_decay if importance_mode == "decayed" else None,
            "jit_gamma": jit_gamma if importance_mode == "jit" else None,
            "add_phantom_deps": add_phantom_deps,
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
    if importance_mode == "decayed":
        mode_tag = f"decayed{importance_decay}"
    elif importance_mode in ("additive", "additive_gap", "additive_freq_gated"):
        # Include decay/alpha value in tag to distinguish parameter sweeps
        mode_tag = f"{importance_mode}{importance_decay}"
    else:
        mode_tag = importance_mode
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
    plan50 = "--plan50" in sys.argv
    plan150 = "--plan150" in sys.argv

    project_root = Path(__file__).resolve().parent.parent.parent

    if mvp:
        # MVP: 100 chars, 5 days, 15/day
        params = dict(max_chars=100, N=5, M=15)
        emb_file = "embeddings_mvp.json"
        modes = [("raw", 0.5)]
        print("Running MVP (100 chars, 5 days, 15/day)")
    elif plan30:
        # All chars, 30 days, 20/day — run all modes for comparison
        params = dict(max_chars=None, N=30, M=20)
        emb_file = "embeddings_full.json"
        modes = [("raw", 0.5), ("max_descendant", 0.5), ("additive", 0.3),
                 ("additive_freq_gated", 0.3), ("additive_gap", 0.3), ("jit", 0.5)]
        print("Running plan30 (all chars, 30 days, 20/day) — 6 modes")
    elif plan50:
        # 50 days, 20/day = 1000 chars — additive_gap as best mode
        params = dict(max_chars=None, N=50, M=20)
        emb_file = "embeddings_full.json"
        modes = [("additive_gap", 0.3)]
        print("Running plan50 (all chars, 50 days, 20/day) — additive_gap")
    elif plan150:
        # 150 days, 20/day = 3000 chars — additive_gap as best mode
        params = dict(max_chars=None, N=150, M=20)
        emb_file = "embeddings_full.json"
        modes = [("additive_gap", 0.3)]
        print("Running plan150 (all chars, 150 days, 20/day) — additive_gap")
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
        lambda_val=0.001,
        L_factor=30,
        embedding_model="text-embedding-3-small",
        add_phantom_deps=True,
        radical_map_path=project_root / "data" / "radical_map_proposal.json",
        freq_boost_cap=3000,
        dep_beta=0.5,
        deadline_factor=5.0,
        deadline_weight=0.5,
        freq_early_weight=0.3,
    )

    results = {}
    for imp_mode, imp_decay in modes:
        print(f"\n{'='*60}")
        print(f"MODE: {imp_mode}" + (f"  decay={imp_decay}" if imp_mode == "decayed" else ""))
        print('='*60)
        jit_g = imp_decay if imp_mode == "jit" else 1.0
        results[imp_mode] = run(**common, **params,
                                importance_mode=imp_mode, importance_decay=imp_decay,
                                jit_gamma=jit_g)

    # --- Comparison summary ---
    print(f"\n{'='*60}")
    print("COMPARISON SUMMARY")
    print('='*60)
    check_chars = ['的', '勺', '日', '一', '是', '不', '了', '在', '人', '有', '缶']
    bundle_checks = [('还', ['瞏', '辵']), ('的', ['勺', '日'])]
    for imp_mode, _ in modes:
        r = results[imp_mode]
        schedule = r["schedule"]
        all_scheduled = {c: d for d, chars in schedule.items() for c in chars}
        print(f"\n[{imp_mode}]  avg_coherence={r['stats']['avg_daily_coherence']}  "
              f"total={r['stats']['total_chars_scheduled']}")
        print("  Key chars — day scheduled (- = not in plan):")
        for c in check_chars:
            print(f"    {c}: day {all_scheduled.get(c, '-')}")
        print("  Phantom bundling check:")
        for char, phantoms in bundle_checks:
            char_day = all_scheduled.get(char, '-')
            for ph in phantoms:
                ph_day = all_scheduled.get(ph, '-')
                ok = "✓" if char_day == ph_day and char_day != '-' else ("✗ VIOLATION" if char_day != '-' and ph_day != '-' else "- (not scheduled)")
                print(f"    {char}(day {char_day}) + {ph}(day {ph_day}): {ok}")
        print("  Day 1:", schedule.get("1", []))
