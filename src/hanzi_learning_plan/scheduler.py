import heapq
import math
from collections import deque
from typing import Dict, List, Literal, Optional, Tuple

import numpy as np

from .graph import CondensedNode


# ---------------------------------------------------------------------------
# Importance
# ---------------------------------------------------------------------------

def compute_importance(rank: int, lambda_val: float = 0.002) -> float:
    return math.exp(-lambda_val * rank)


ImportanceMode = Literal["raw", "max_descendant", "decayed"]


def propagate_importance(
    nodes: List[CondensedNode],
    mode: ImportanceMode,
    decay: float = 0.5,
) -> None:
    """
    Adjust node importances in-place before scheduling.

    Modes
    -----
    "raw"            : no change (current behaviour)
    "max_descendant" : each node's importance = max(own, max descendant importance).
                       A prerequisite is at least as important as its most important dependent.
    "decayed"        : same, but importance is multiplied by `decay` at each hop.
                       e.g. 的 (rank 1) contributes decay * I(的) to 勺, decay^2 * I(的) to 勺's prereqs, etc.

    Uses a reverse-topological BFS (Kahn's on the reverse DAG) so that a node's
    effective importance is fully known before it is propagated to its prerequisites.
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

    # Effective importance starts as own importance
    eff: Dict[int, float] = {n.id: n.importance for n in nodes}

    # Kahn's on reverse DAG: process nodes whose dependents are all done first
    remaining_children = {n.id: len(children[n.id]) for n in nodes}
    queue: deque = deque(nid for nid, cnt in remaining_children.items() if cnt == 0)

    while queue:
        nid = queue.popleft()
        prop_val = decay * eff[nid] if mode == "decayed" else eff[nid]
        for prereq_id in node_map[nid].prereqs:
            eff[prereq_id] = max(eff[prereq_id], prop_val)
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
) -> List[List[int]]:
    """
    Greedy topological batching.
    Returns schedule: list of up to N day-lists, each containing node ids.
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

    # Max-heap keyed by (-importance, id) for stable ordering
    heap: List[Tuple[float, int]] = []
    for n in nodes:
        if in_degree[n.id] == 0:
            heapq.heappush(heap, (-n.importance, n.id))

    completed: set = set()
    schedule: List[List[int]] = []

    for _day in range(N):
        if not heap:
            break

        # --- Pull top-L candidates (lazy-delete completed) ---
        candidates: List[CondensedNode] = []
        temp: List[Tuple[float, int]] = []
        while heap and len(candidates) < L:
            neg_imp, nid = heapq.heappop(heap)
            if nid in completed:
                continue
            candidates.append(node_map[nid])
            temp.append((neg_imp, nid))
        # Restore unconsumed candidates to heap
        for item in temp:
            heapq.heappush(heap, item)

        if not candidates:
            break

        # --- Greedy selection within day ---
        today_ids: List[int] = []
        today_nodes: List[CondensedNode] = []
        remaining = list(candidates)

        while len(today_ids) < M and remaining:
            best_score = -1e18
            best_idx = -1
            n_today = len(today_nodes)

            for ci, cand in enumerate(remaining):
                imp_term = w * cand.importance
                if n_today == 0:
                    sim_term = 0.0
                else:
                    sim_term = (1 - w) * sum(_sim(cand, t) for t in today_nodes) / n_today
                score = imp_term + sim_term
                if score > best_score:
                    best_score = score
                    best_idx = ci

            chosen = remaining.pop(best_idx)
            today_ids.append(chosen.id)
            today_nodes.append(chosen)
            completed.add(chosen.id)

        # Remove scheduled nodes from heap (lazy: they're in completed)
        # Update in-degrees for children
        for nid in today_ids:
            for child_id in children[nid]:
                in_degree[child_id] -= 1
                if in_degree[child_id] == 0:
                    heapq.heappush(heap, (-node_map[child_id].importance, child_id))

        schedule.append(today_ids)

    return schedule


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
) -> List[List[int]]:
    """
    Improve schedule by trying to move each node to a different day.
    Accepts any move that strictly increases the objective w*A + (1-w)*B.
    """
    node_map = {n.id: n for n in nodes}
    scheduled_set = {nid for day in schedule for nid in day}
    D = len(schedule)

    # node -> day index
    node_day: Dict[int, int] = {}
    for d, day in enumerate(schedule):
        for nid in day:
            node_day[nid] = d

    # Prereq / children restricted to scheduled set
    prereqs_of: Dict[int, List[int]] = {
        nid: [p for p in node_map[nid].prereqs if p in scheduled_set]
        for nid in scheduled_set
    }
    children_of: Dict[int, List[int]] = {nid: [] for nid in scheduled_set}
    for nid in scheduled_set:
        for p in prereqs_of[nid]:
            children_of[p].append(nid)

    # Per-day pairwise similarity sums
    pair_sums: Dict[int, float] = {}
    for d, day in enumerate(schedule):
        _, ps = day_coherence(day, node_map)
        pair_sums[d] = ps

    improved = True
    iters = 0
    while improved and iters < max_iters:
        improved = False
        iters += 1
        for nid in list(scheduled_set):
            d1 = node_day[nid]
            n_node = node_map[nid]

            # Earliest day: all prereqs must be on day < d2
            earliest = max(
                (node_day[p] + 1 for p in prereqs_of[nid]),
                default=0,
            )
            # Latest day: all children must be on day > d2
            latest = min(
                (node_day[ch] - 1 for ch in children_of[nid]),
                default=D - 1,
            )

            for d2 in range(earliest, min(latest + 1, D)):
                if d2 == d1:
                    continue
                if len(schedule[d2]) >= M:
                    continue

                # --- Delta A ---
                dA = 0.0
                if d1 < N <= d2:
                    dA = -n_node.importance
                elif d2 < N <= d1:
                    dA = n_node.importance

                # --- Delta B ---
                day1 = schedule[d1]
                day2 = schedule[d2]
                n1, n2 = len(day1), len(day2)

                sim_with_d1 = sum(_sim(n_node, node_map[j]) for j in day1 if j != nid)
                sim_with_d2 = sum(_sim(n_node, node_map[j]) for j in day2)

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
