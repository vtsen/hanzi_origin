# Scheduler Parameters

All tunable parameters for the learning plan generator (`src/hanzi_learning_plan/run.py`).
**Keep this file up to date when adding new parameters.**

---

## Data Loading

| Param | Default | Where set | Effect |
|-------|---------|-----------|--------|
| `max_chars` | `None` | `run.py` params block | Limit universe to top-N chars by frequency rank. `None` = use all chars in dep_forest. |
| `add_phantom_deps` | `True` | `common` | Inject phantom nodes for deps absent from dep_forest. Phantoms are bundled same-day with the char that needs them (if ≤3 dependents) or scheduled standalone. |
| `max_real_dep_rank` | `None` | `common` | Strip dep edges to chars ranked beyond this threshold, making rare prereqs non-blocking. The rare char stays learnable but is no longer a hard prerequisite. Good rule of thumb: `2 × (N × M)` so only chars outside the plan window block. E.g. `2000` for a 50-day plan. |

---

## Base Importance Formula

`I(rank) = exp(-λ × rank) + linear_boost_weight × max(0, (freq_boost_cap - rank) / freq_boost_cap)`

| Param | Default | Where set | Effect |
|-------|---------|-----------|--------|
| `lambda_val` | `0.001` | `common` | Exponential decay rate. Higher → steeper drop-off for less-frequent chars. |
| `freq_boost_cap` | `1000` | `common` | Chars ranked above this get zero linear bonus. Lower cap = sharper cliff, top-N chars stand out more. E.g. `1000` means only top-1000 chars get the ramp bonus. |
| `linear_boost_weight` | `2.0` | `common` | Multiplier on the linear frequency ramp. Higher = raw frequency matters more relative to graph topology boosts. `1.0` = original behaviour. |

**Interaction:** lowering `freq_boost_cap` tightens who gets the bonus; raising `linear_boost_weight` amplifies how much that bonus is worth. Together they control how aggressively frequency overrides graph-derived importance.

---

## Importance Propagation (Graph Topology)

| Param | Default | Where set | Effect |
|-------|---------|-----------|--------|
| `importance_mode` | `"additive_gap"` | per-plan `modes` list | Algorithm for propagating importance through the dependency graph. Options: `raw`, `max_descendant`, `decayed`, `additive`, `additive_freq_gated`, `additive_gap`, `jit`. |
| `importance_decay` | `0.3` | per-plan `modes` list | α coefficient for propagation. In `additive_gap`: `eff[prereq] += α × max(0, best_child_eff - own[prereq])`. Lower = weaker boost from descendants. |
| `importance_cap_factor` | `10.0` | `common` | Caps heap priority at `cap × raw_importance`. Prevents rare prereqs from being wildly over-boosted. `0` disables cap. Lower values keep rare chars from crowding out common ones. |
| `freq_threshold` | `0.135` | `run.py` default | Gate for `additive_freq_gated` mode only: only descendants with base importance ≥ this value can sponsor their prereqs. (~rank 2000 threshold) |

---

## Scheduling

| Param | Default | Where set | Effect |
|-------|---------|-----------|--------|
| `N` | plan-specific | per-plan params | Number of days to schedule. |
| `M` | plan-specific | per-plan params | Max new chars per day (phantoms are free and don't count). |
| `w` | `0.3` | `common` | Importance vs. coherence balance `[0,1]`. Higher = prioritise frequency rank; lower = prioritise same-topic clustering. |
| `L_factor` | `30` | `common` | Greedy candidate pool size = `L_factor × M`. Larger pool = better daily coherence at cost of speed. |
| `dep_beta` | `0.5` | `common` | Coherence formula weight: `coherence = (1-dep_beta)×embedding_sim + dep_beta×dep_overlap_sim`. `0.5` = equal weight to semantic similarity and structural overlap. |
| `deadline_factor` | `5.0` | `common` | Controls urgency: a char whose dependents are scheduled within `deadline_factor × base_rank / M` days gets an urgency boost. |
| `deadline_weight` | `0.5` | `common` | How much the deadline urgency bonus contributes to heap priority. |
| `freq_early_weight` | `0.3` | `common` | Swap bias rewarding moving high-importance chars earlier. Added as `Δ = (imp_B − imp_A) × (d2 − d1) / D` during local search. `0` disables. |

---

## Experiment Log

Track parameter changes and outcomes here to avoid re-running experiments.

| Date | Plan | Changed params | Key outcome |
|------|------|---------------|-------------|
| 2026-06-07 | plan50 | baseline: `freq_boost_cap=3000, importance_cap_factor=20, linear_boost_weight=1.0` | 12 top-200 freq chars missing (得发家成实使点将代通原声), all blocked by rare deps or low slot priority |
| 2026-06-07 | plan50 | `freq_boost_cap=1000, importance_cap_factor=10, linear_boost_weight=2.0` | 4 of 12 now appear (成使点原); 8 still missing — root cause: rare deps (豕 rank 4922, 殳 rank 5914 etc.) are hard prereqs that never get scheduled |
| 2026-06-07 | plan50 | + `max_real_dep_rank=2000` | All 12 now appear; zero top-200 freq chars missing. Total 1000 chars scheduled. |
| 2026-06-07 | plan30s | `freq_boost_cap=500, linear_boost_weight=2.5, importance_cap_factor=8, max_real_dep_rank=900` | 450 chars, 30 days, 15/day. max_real_dep_rank=900≈2×450 so only in-plan chars can hard-block. Avg coherence 0.29. |
| 2026-06-07 | plan100 | `freq_boost_cap=3000, linear_boost_weight=1.5, importance_cap_factor=15, max_real_dep_rank=8000` | 4000 chars, 100 days, 40/day. max_real_dep_rank=8000≈2×4000 for broad coverage. |
