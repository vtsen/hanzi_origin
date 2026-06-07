import heapq
import math
from collections import deque
from typing import Dict, List, Literal, Optional, Tuple

import numpy as np

from .graph import CondensedNode


# ---------------------------------------------------------------------------
# Importance
# ---------------------------------------------------------------------------

def compute_importance(
    rank: int,
    lambda_val: float = 0.001,
    freq_boost_cap: int = 3000,
    linear_boost_weight: float = 1.0,
) -> float:
    """
    I(rank) = exp(-λ × rank) + linear_boost_weight × max(0, (freq_boost_cap - rank) / freq_boost_cap)

    The second term is a linear ramp that gives an extra bonus up to +linear_boost_weight for
    rank-1 chars, tapering to 0 at rank == freq_boost_cap and beyond.
    Combined effect: the top-freq_boost_cap chars are pulled ahead of the long tail.
    Set freq_boost_cap=0 to disable the linear term (pure exponential decay).
    linear_boost_weight > 1.0 amplifies the frequency signal relative to the graph topology.
    """
    exp_term = math.exp(-lambda_val * rank)
    linear_bonus = max(0.0, (freq_boost_cap - rank) / freq_boost_cap) if freq_boost_cap > 0 else 0.0
    return exp_term + linear_boost_weight * linear_bonus


ImportanceMode = Literal["raw", "max_descendant", "decayed", "additive", "additive_freq_gated", "additive_gap", "jit"]


def propagate_importance(
    nodes: List[CondensedNode],
    mode: ImportanceMode,
    decay: float = 0.5,
    freq_threshold: float = 0.135,
) -> None:
    """
    Adjust node importances in-place before scheduling.

    Modes
    -----
    "raw"                 : no change.
    "max_descendant"      : effective(c) = max(own(c), max effective(descendant)).
                            Fully overrides own importance — rare prereqs get the same
                            score as their most frequent descendant.
    "decayed"             : same as max_descendant but propagated value is multiplied
                            by `decay` at each hop before taking the max.
    "additive"            : effective(c) = own(c) + decay * max effective(descendant).
                            Preserves the own-importance hierarchy: 的 still outranks 勺,
                            but 勺 gets a meaningful boost for unlocking 的.
                            `decay` here acts as the additive coefficient α.
    "additive_freq_gated" : like "additive" but only descendants whose BASE importance
                            >= freq_threshold can sponsor their prerequisites.
                            Prevents chains of obscure chars from bootstrapping each
                            other's importance (e.g., rank-4000 chars won't push
                            rank-5000 radicals into early days).
                            Gate uses own_importance (pre-propagation) so it's not
                            self-reinforcing.
    "additive_gap"        : like "additive" but the boost is proportional to the
                            importance gap between the best descendant and the prereq
                            itself. Only boosts if a descendant is MORE important than
                            the prereq:
                                gap = max(0, best_child_eff - own[prereq])
                                eff[prereq] = own[prereq] + α × gap
                            Rare prereqs unlocking common chars get large boosts;
                            chains of equally rare chars yield near-zero gaps.

    All modes use a reverse-topological BFS so each node's effective importance
    is fully known before propagating to its prerequisites.
    """
    if mode == "raw":
        return

    node_map: Dict[int, CondensedNode] = {n.id: n for n in nodes}

    # children[p] = list of node ids that have p as a prerequisite
    children: Dict[int, List[int]] = {n.id: [] for n in nodes}
    for n in nodes:
        for prereq_id in n.prereqs:
            if prereq_id in children:
                children[prereq_id].append(n.id)

    # Snapshot of base (pre-propagation) importance — used as the gate in
    # additive_freq_gated so the threshold never becomes self-reinforcing.
    own_importance: Dict[int, float] = {n.id: n.importance for n in nodes}

    # Effective importance starts as own importance
    eff: Dict[int, float] = {n.id: n.importance for n in nodes}

    # Kahn's on reverse DAG: process nodes whose dependents are all done first
    remaining_children = {n.id: len(children[n.id]) for n in nodes}
    queue: deque = deque(nid for nid, cnt in remaining_children.items() if cnt == 0)

    while queue:
        nid = queue.popleft()
        for prereq_id in node_map[nid].prereqs:
            if mode == "max_descendant":
                eff[prereq_id] = max(eff[prereq_id], eff[nid])
            elif mode == "decayed":
                eff[prereq_id] = max(eff[prereq_id], decay * eff[nid])
            elif mode == "additive":
                # Boost prereq by α × best-descendant's effective importance,
                # but only if that descendant is more important than the prereq itself
                best_desc = max(eff[c] for c in children[prereq_id]) if children[prereq_id] else 0.0
                eff[prereq_id] = eff[prereq_id] + decay * best_desc
            elif mode == "additive_gap":
                # Only boost by the gap: how much more important is the best descendant
                # than the prereq itself? Rare prereqs unlocking common chars get large
                # boosts; equally rare chains yield near-zero gaps.
                best_desc_eff = max(eff[c] for c in children[prereq_id]) if children[prereq_id] else 0.0
                gap = max(0.0, best_desc_eff - own_importance[prereq_id])
                eff[prereq_id] = eff[prereq_id] + decay * gap
            elif mode == "additive_freq_gated":
                # Like additive, but only children whose BASE importance >= freq_threshold
                # can sponsor the prereq.  This prevents chains of obscure chars from
                # bootstrapping each other into early days.
                qualified = [c for c in children[prereq_id]
                             if own_importance[c] >= freq_threshold]
                if qualified:
                    best_desc_q = max(eff[c] for c in qualified)
                    eff[prereq_id] = eff[prereq_id] + decay * best_desc_q
                # else: no boost — prereq keeps its raw own importance
            remaining_children[prereq_id] -= 1
            if remaining_children[prereq_id] == 0:
                queue.append(prereq_id)

    for n in nodes:
        n.importance = eff[n.id]


# ---------------------------------------------------------------------------
# Similarity
# ---------------------------------------------------------------------------

def _sim(a: CondensedNode, b: CondensedNode) -> float:
    if a.embedding is None or b.embedding is None:
        return 0.0
    return float(np.dot(a.embedding, b.embedding))


def _dep_sim(
    a: CondensedNode,
    b: CondensedNode,
    prereq_sets: Dict[int, set],
) -> float:
    """
    Normalised prerequisite overlap between two nodes.
    Score = |prereqs(a) ∩ prereqs(b)| / max(|prereqs(a)|, |prereqs(b)|, 1).
    Returns 0 if either node has no prerequisites (no shared-ancestor signal).
    Rewards scheduling chars that share the same immediate dependency on the
    same day, reinforcing component-based learning clusters.
    """
    sa, sb = prereq_sets[a.id], prereq_sets[b.id]
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    denom = max(len(sa), len(sb))
    return inter / denom


# ---------------------------------------------------------------------------
# Day coherence helpers
# ---------------------------------------------------------------------------

def day_coherence(node_ids: List[int], node_map: Dict[int, CondensedNode]) -> Tuple[float, float]:
    """
    Returns (coherence, pairwise_sum).
    coherence = 0 when |day| < 2.
    """
    n = len(node_ids)
    if n < 2:
        return 0.0, 0.0
    pair_sum = sum(
        _sim(node_map[node_ids[i]], node_map[node_ids[j]])
        for i in range(n)
        for j in range(i + 1, n)
    )
    return 2 * pair_sum / (n * (n - 1)), pair_sum


def _coh_from_sum(pair_sum: float, n: int) -> float:
    return 2 * pair_sum / (n * (n - 1)) if n >= 2 else 0.0


# ---------------------------------------------------------------------------
# Greedy scheduler
# ---------------------------------------------------------------------------

def greedy_schedule(
    nodes: List[CondensedNode],
    M: int,
    N: int,
    w: float,
    L_factor: int = 3,
    pilot_days: Optional[Dict[int, int]] = None,
    jit_gamma: float = 0.0,
    dep_beta: float = 0.0,
    deadline_factor: float = 0.0,   # 0 = disabled; try 5.0
    deadline_weight: float = 0.5,   # how hard the penalty hits
    importance_cap_factor: float = 0.0,
) -> List[List[int]]:
    """
    Greedy topological batching.
    Returns schedule: list of up to N day-lists, each containing node ids.

    dep_beta             : weight of dependency-overlap similarity within the coherence term.
                           coherence = (1-dep_beta)*embedding_sim + dep_beta*dep_overlap_sim
                           Higher values cluster chars sharing the same immediate prereq;
                           0.5 gives dep-overlap equal weight to embeddings.
    importance_cap_factor: heap priority = min(propagated_importance, cap × raw_importance).
                           Caps how much additive_gap propagation can boost rare chars.
                           A node with low raw importance (e.g. rank 8000) cannot displace
                           frequent chars in the candidate pool even if it unlocks something
                           common.  0 disables the cap (full propagated importance used).
    """
    L = L_factor * M
    node_map = {n.id: n for n in nodes}

    # Build children index and in-degree
    in_degree: Dict[int, int] = {n.id: 0 for n in nodes}
    children: Dict[int, List[int]] = {n.id: [] for n in nodes}
    for n in nodes:
        for prereq_id in n.prereqs:
            if prereq_id in in_degree:
                in_degree[n.id] += 1
                children[prereq_id].append(n.id)

    # Prereq sets for dependency-overlap similarity (built once, reused per day)
    prereq_sets: Dict[int, set] = {n.id: set(n.prereqs) for n in nodes}

    def _heap_priority(n: CondensedNode) -> float:
        """Propagated importance, optionally capped to cap_factor × raw_importance."""
        if importance_cap_factor > 0 and n.raw_importance > 0:
            return min(n.importance, importance_cap_factor * n.raw_importance)
        return n.importance

    # Separate ready queues: phantoms are free (no quota); reals count toward M
    phantom_ready: deque = deque()
    real_heap: List[Tuple[float, int]] = []
    for n in nodes:
        if in_degree[n.id] == 0:
            if n.is_phantom:
                phantom_ready.append(n.id)
            else:
                heapq.heappush(real_heap, (-_heap_priority(n), n.id))

    completed: set = set()
    schedule: List[List[int]] = []

    def _mark_ready(nid: int) -> None:
        """Called when in_degree[nid] hits 0."""
        n = node_map[nid]
        if n.is_phantom:
            phantom_ready.append(nid)
        else:
            heapq.heappush(real_heap, (-_heap_priority(n), nid))

    for _day in range(N):
        if not phantom_ready and not real_heap:
            break

        # --- Auto-schedule all ready phantoms for free (no quota impact) ---
        today_ids: List[int] = []
        while phantom_ready:
            nid = phantom_ready.popleft()
            if nid in completed:
                continue
            today_ids.append(nid)
            completed.add(nid)
            for child_id in children[nid]:
                in_degree[child_id] -= 1
                if in_degree[child_id] == 0:
                    _mark_ready(child_id)

        if not real_heap:
            if today_ids:
                schedule.append(today_ids)
            break

        # --- Pull top-L real candidates (lazy-delete completed) ---
        candidates: List[CondensedNode] = []
        temp: List[Tuple[float, int]] = []
        while real_heap and len(candidates) < L:
            neg_imp, nid = heapq.heappop(real_heap)
            if nid in completed:
                continue
            candidates.append(node_map[nid])
            temp.append((neg_imp, nid))
        for item in temp:
            heapq.heappush(real_heap, item)

        if not candidates:
            if today_ids:
                schedule.append(today_ids)
            break

        # --- Greedy selection of up to M real nodes ---
        today_nodes: List[CondensedNode] = []
        remaining = list(candidates)

        while len(today_nodes) < M and remaining:
            best_score = -1e18
            best_idx = -1
            n_today = len(today_nodes)

            for ci, cand in enumerate(remaining):
                imp_term = w * cand.importance
                if n_today == 0:
                    sim_term = 0.0
                else:
                    emb_avg = sum(_sim(cand, t) for t in today_nodes) / n_today
                    if dep_beta > 0:
                        dep_avg = sum(_dep_sim(cand, t, prereq_sets) for t in today_nodes) / n_today
                        mixed = (1 - dep_beta) * emb_avg + dep_beta * dep_avg
                    else:
                        mixed = emb_avg
                    sim_term = (1 - w) * mixed

                # JIT urgency: boost prereqs whose dependents are imminent
                if pilot_days is not None and jit_gamma > 0 and children[cand.id]:
                    child_deadlines = [pilot_days[c] for c in children[cand.id] if c in pilot_days]
                    if child_deadlines:
                        days_until = max(1, min(child_deadlines) - _day)
                        imp_term += w * jit_gamma / days_until

                # Deadline urgency: boost chars approaching/past their expected day
                if deadline_factor > 0:
                    deadline_day = deadline_factor * cand.base_rank / M
                    if deadline_day > 0:
                        lateness = _day / deadline_day  # 0=early, 1=at deadline, >1=past
                        if lateness > 0.5:  # start ramping at 50% of deadline
                            imp_term += w * deadline_weight * (lateness - 0.5)

                score = imp_term + sim_term
                if score > best_score:
                    best_score = score
                    best_idx = ci

            chosen = remaining.pop(best_idx)
            today_ids.append(chosen.id)
            today_nodes.append(chosen)
            completed.add(chosen.id)

        # Update in-degrees for children of newly scheduled real nodes
        for node in today_nodes:
            for child_id in children[node.id]:
                in_degree[child_id] -= 1
                if in_degree[child_id] == 0:
                    _mark_ready(child_id)

        schedule.append(today_ids)

    return schedule


# ---------------------------------------------------------------------------
# JIT (just-in-time) two-pass scheduling
# ---------------------------------------------------------------------------

def jit_greedy_schedule(
    nodes: List[CondensedNode],
    M: int,
    N: int,
    w: float,
    L_factor: int = 3,
    gamma: float = 1.0,
    dep_beta: float = 0.0,
    deadline_factor: float = 0.0,
    deadline_weight: float = 0.5,
) -> List[List[int]]:
    """
    Two-pass just-in-time scheduler.

    Pass 1 (pilot): fast raw importance schedule (w=1, L=1) — estimates each
                    node's "natural day" without JIT influence.
    Pass 2 (real):  re-runs the greedy scheduler with an urgency boost:
                        score += w * gamma / days_until_soonest_dependent
                    A prereq whose dependent is scheduled tomorrow gets a large
                    boost; one whose dependent is 25 days away gets almost none.
                    Prereqs are scheduled just-in-time rather than maximally early.
    """
    # Pass 1: pilot — pure importance, small pool, fast
    print("    [JIT] Pass 1: pilot schedule...")
    pilot = greedy_schedule(nodes, M=M, N=N, w=1.0, L_factor=1)
    pilot_days: Dict[int, int] = {
        nid: d for d, day_ids in enumerate(pilot) for nid in day_ids
    }
    print(f"    [JIT] Pass 2: real schedule (gamma={gamma})...")
    return greedy_schedule(nodes, M=M, N=N, w=w, L_factor=L_factor,
                           pilot_days=pilot_days, jit_gamma=gamma, dep_beta=dep_beta,
                           deadline_factor=deadline_factor, deadline_weight=deadline_weight)


# ---------------------------------------------------------------------------
# Local search
# ---------------------------------------------------------------------------

def local_search(
    schedule: List[List[int]],
    nodes: List[CondensedNode],
    M: int,
    N: int,
    w: float,
    max_iters: int = 500,
    dep_beta: float = 0.0,
) -> List[List[int]]:
    """
    Improve schedule by trying to move each node to a different day.
    Accepts any move that strictly increases the objective w*A + (1-w)*B.
    dep_beta mirrors the same parameter used in greedy_schedule.
    """
    node_map = {n.id: n for n in nodes}
    scheduled_set = {nid for day in schedule for nid in day}
    D = len(schedule)
    prereq_sets: Dict[int, set] = {n.id: set(n.prereqs) for n in nodes}

    node_day: Dict[int, int] = {}
    for d, day in enumerate(schedule):
        for nid in day:
            node_day[nid] = d

    prereqs_of: Dict[int, List[int]] = {
        nid: [p for p in node_map[nid].prereqs if p in scheduled_set]
        for nid in scheduled_set
    }
    children_of: Dict[int, List[int]] = {nid: [] for nid in scheduled_set}
    for nid in scheduled_set:
        for p in prereqs_of[nid]:
            children_of[p].append(nid)

    def _mixed(a: CondensedNode, b: CondensedNode) -> float:
        emb = _sim(a, b)
        if dep_beta <= 0:
            return emb
        dep = _dep_sim(a, b, prereq_sets)
        return (1 - dep_beta) * emb + dep_beta * dep

    # Per-day pairwise mixed-similarity sums
    pair_sums: Dict[int, float] = {}
    for d, day in enumerate(schedule):
        if len(day) < 2:
            pair_sums[d] = 0.0
        else:
            pair_sums[d] = sum(
                _mixed(node_map[day[i]], node_map[day[j]])
                for i in range(len(day))
                for j in range(i + 1, len(day))
            )

    improved = True
    iters = 0
    while improved and iters < max_iters:
        improved = False
        iters += 1
        for nid in list(scheduled_set):
            d1 = node_day[nid]
            n_node = node_map[nid]

            earliest = max((node_day[p] + 1 for p in prereqs_of[nid]), default=0)
            latest = min((node_day[ch] - 1 for ch in children_of[nid]), default=D - 1)

            for d2 in range(earliest, min(latest + 1, D)):
                if d2 == d1:
                    continue
                if len(schedule[d2]) >= M:
                    continue

                dA = 0.0
                if d1 < N <= d2:
                    dA = -n_node.importance
                elif d2 < N <= d1:
                    dA = n_node.importance

                day1 = schedule[d1]
                day2 = schedule[d2]
                n1, n2 = len(day1), len(day2)

                sim_with_d1 = sum(_mixed(n_node, node_map[j]) for j in day1 if j != nid)
                sim_with_d2 = sum(_mixed(n_node, node_map[j]) for j in day2)

                ps1_new = pair_sums[d1] - sim_with_d1
                ps2_new = pair_sums[d2] + sim_with_d2

                coh_d1_old = _coh_from_sum(pair_sums[d1], n1)
                coh_d1_new = _coh_from_sum(ps1_new, n1 - 1)
                coh_d2_old = _coh_from_sum(pair_sums[d2], n2)
                coh_d2_new = _coh_from_sum(ps2_new, n2 + 1)

                dB = (coh_d1_new - coh_d1_old + coh_d2_new - coh_d2_old) / D

                if w * dA + (1 - w) * dB > 1e-9:
                    schedule[d1].remove(nid)
                    schedule[d2].append(nid)
                    node_day[nid] = d2
                    pair_sums[d1] = ps1_new
                    pair_sums[d2] = ps2_new
                    improved = True
                    break

    print(f"  Local search converged after {iters} iteration(s).")
    return schedule


def swap_local_search(
    schedule: List[List[int]],
    nodes: List[CondensedNode],
    M: int,
    N: int,
    w: float,
    max_iters: int = 200,
    dep_beta: float = 0.0,
    day_window: int = 15,
    freq_early_weight: float = 0.0,
) -> List[List[int]]:
    """
    Improve schedule via pairwise swaps: pick nodes A (on day D1) and B (on day D2),
    swap if it improves the combined objective:

        w * dA  +  (1-w) * dB  +  freq_early_weight * d_freq_early  > 0

    where:
      dA            — importance delta (non-zero only when crossing the N-day boundary)
      dB            — normalised coherence delta across both affected days
      d_freq_early  — (imp_B − imp_A) × (d2 − d1) / D
                      Positive when the swap moves the higher-importance node to an
                      earlier day; drives frequent chars toward the front of the plan
                      independent of the N-boundary crossing.

    Swaps keep day sizes constant (capacity constraint always satisfied).
    Uses a precomputed pairwise similarity cache for O(1) per-pair lookups.
    day_window limits the search to ±day_window days around each node.
    Phantoms are excluded from swaps and from coherence calculations.

    Parameters
    ----------
    dep_beta         : weight of dependency-overlap within the mixed similarity
                       coherence = (1-dep_beta)*embedding_sim + dep_beta*dep_overlap_sim
    freq_early_weight: bonus weight for moving high-importance chars earlier.
                       Values in [0.1, 0.5] are effective; 0 disables the term.
    """
    node_map = {n.id: n for n in nodes}
    scheduled_set = {nid for day in schedule for nid in day}
    # Phantoms are free structural nodes — exclude from swaps and coherence
    real_set = {nid for nid in scheduled_set if not node_map[nid].is_phantom}
    scheduled_list = sorted(real_set)
    D = len(schedule)
    prereq_sets: Dict[int, set] = {n.id: set(n.prereqs) for n in nodes}

    node_day: Dict[int, int] = {}
    for d, day in enumerate(schedule):
        for nid in day:
            node_day[nid] = d

    prereqs_of: Dict[int, List[int]] = {
        nid: [p for p in node_map[nid].prereqs if p in scheduled_set]
        for nid in scheduled_set
    }
    children_of: Dict[int, List[int]] = {nid: [] for nid in scheduled_set}
    for nid in scheduled_set:
        for p in prereqs_of[nid]:
            children_of[p].append(nid)

    # Pre-compute pairwise similarity cache: sim_cache[a][b] = _mixed(node_a, node_b)
    # Use numpy matrix multiplication for embedding similarities, then add dep_sim if needed
    print(f"  Building similarity cache for {len(scheduled_list)} nodes...", flush=True)

    # Map node ids to compact indices
    idx_of: Dict[int, int] = {nid: i for i, nid in enumerate(scheduled_list)}
    n_nodes = len(scheduled_list)

    # Stack embeddings: shape (n_nodes, embed_dim), None-embeddings → zero row
    sample_emb = next((node_map[nid].embedding for nid in scheduled_list
                       if node_map[nid].embedding is not None), None)
    if sample_emb is not None:
        dim = len(sample_emb)
        emb_matrix = np.zeros((n_nodes, dim), dtype=np.float32)
        for i, nid in enumerate(scheduled_list):
            e = node_map[nid].embedding
            if e is not None:
                emb_matrix[i] = e
        # Full pairwise cosine similarity (embeddings already normalized)
        sim_matrix = emb_matrix @ emb_matrix.T  # shape (n_nodes, n_nodes)
    else:
        sim_matrix = np.zeros((n_nodes, n_nodes), dtype=np.float32)

    if dep_beta > 0:
        # Add dep_sim scaled by dep_beta; compute on-the-fly (sparse, so fast)
        def _sim_lookup(nid_a: int, nid_b: int) -> float:
            base = float(sim_matrix[idx_of[nid_a], idx_of[nid_b]])
            dep = _dep_sim(node_map[nid_a], node_map[nid_b], prereq_sets)
            return (1 - dep_beta) * base + dep_beta * dep
    else:
        def _sim_lookup(nid_a: int, nid_b: int) -> float:
            return float(sim_matrix[idx_of[nid_a], idx_of[nid_b]])

    # Per-day real-node lists (exclude phantoms from coherence calculation)
    real_day: Dict[int, List[int]] = {
        d: [nid for nid in day if nid in real_set]
        for d, day in enumerate(schedule)
    }

    # Per-day pairwise similarity sums (real nodes only)
    pair_sums: Dict[int, float] = {}
    for d, rday in real_day.items():
        if len(rday) < 2:
            pair_sums[d] = 0.0
        else:
            pair_sums[d] = sum(
                _sim_lookup(rday[i], rday[j])
                for i in range(len(rday))
                for j in range(i + 1, len(rday))
            )

    improved = True
    iters = 0
    total_swaps = 0

    while improved and iters < max_iters:
        improved = False
        iters += 1
        for nid_a in scheduled_list:
            d1 = node_day[nid_a]

            # Only try nearby days (within ±day_window) to keep tractable
            d2_min = max(0, d1 - day_window)
            d2_max = min(D - 1, d1 + day_window)
            found_swap = False

            for d2 in range(d2_min, d2_max + 1):
                if d2 == d1:
                    continue

                for nid_b in list(real_day[d2]):  # only swap real nodes
                    # Feasibility: A can go to D2
                    if not all(node_day[p] < d2 for p in prereqs_of[nid_a]):
                        continue
                    if not all(node_day[ch] > d2 for ch in children_of[nid_a]):
                        continue

                    # Feasibility: B can go to D1
                    if not all(node_day[p] < d1 for p in prereqs_of[nid_b]):
                        continue
                    if not all(node_day[ch] > d1 for ch in children_of[nid_b]):
                        continue

                    # Importance delta: only changes if one crosses the N-day boundary
                    dA = 0.0
                    if d1 < N <= d2:
                        dA = node_map[nid_b].importance - node_map[nid_a].importance
                    elif d2 < N <= d1:
                        dA = node_map[nid_a].importance - node_map[nid_b].importance

                    rday1 = real_day[d1]
                    rday2 = real_day[d2]
                    n1, n2 = len(rday1), len(rday2)

                    # Coherence delta using precomputed cache — O(M) lookups
                    sim_a_in_d1 = sum(_sim_lookup(nid_a, j) for j in rday1 if j != nid_a)
                    sim_b_in_d1 = sum(_sim_lookup(nid_b, j) for j in rday1 if j != nid_a)
                    ps1_new = pair_sums[d1] - sim_a_in_d1 + sim_b_in_d1

                    sim_b_in_d2 = sum(_sim_lookup(nid_b, j) for j in rday2 if j != nid_b)
                    sim_a_in_d2 = sum(_sim_lookup(nid_a, j) for j in rday2 if j != nid_b)
                    ps2_new = pair_sums[d2] - sim_b_in_d2 + sim_a_in_d2

                    coh_d1_old = _coh_from_sum(pair_sums[d1], n1)
                    coh_d1_new = _coh_from_sum(ps1_new, n1)  # size unchanged after swap
                    coh_d2_old = _coh_from_sum(pair_sums[d2], n2)
                    coh_d2_new = _coh_from_sum(ps2_new, n2)

                    dB = (coh_d1_new - coh_d1_old + coh_d2_new - coh_d2_old) / D

                    # Frequency-earliness bonus: reward moving higher-importance
                    # chars to earlier days regardless of N-boundary crossing.
                    d_freq_early = (
                        (node_map[nid_b].importance - node_map[nid_a].importance)
                        * (d2 - d1) / D
                    ) if freq_early_weight > 0 else 0.0

                    if w * dA + (1 - w) * dB + freq_early_weight * d_freq_early > 1e-9:
                        # Execute swap in schedule and real_day
                        schedule[d1].remove(nid_a)
                        schedule[d1].append(nid_b)
                        schedule[d2].remove(nid_b)
                        schedule[d2].append(nid_a)
                        real_day[d1].remove(nid_a)
                        real_day[d1].append(nid_b)
                        real_day[d2].remove(nid_b)
                        real_day[d2].append(nid_a)
                        node_day[nid_a] = d2
                        node_day[nid_b] = d1
                        pair_sums[d1] = ps1_new
                        pair_sums[d2] = ps2_new
                        total_swaps += 1
                        improved = True
                        found_swap = True
                        break

                if found_swap:
                    break

    print(f"  Swap local search: {total_swaps} swap(s) accepted over {iters} iteration(s).")
    # Write stats to a side-file so Windows background capture doesn't lose them
    try:
        import pathlib, json as _json
        # Walk up from scheduler.py -> hanzi_learning_plan -> src -> project root
        _proj = pathlib.Path(__file__).resolve().parent.parent.parent
        _stats = _proj / "data" / "learning_plan" / "swap_stats.json"
        _stats.parent.mkdir(parents=True, exist_ok=True)
        with _stats.open("w") as _f:
            _json.dump({"total_swaps": total_swaps, "iters": iters}, _f)
    except Exception as _e:
        print(f"  [warn] swap_stats write failed: {_e}")
    return schedule
