from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Iterative Tarjan's SCC
# ---------------------------------------------------------------------------

def tarjan_scc(graph: Dict[str, List[str]]) -> List[List[str]]:
    """
    Iterative Tarjan's strongly-connected-components algorithm.
    graph: {node: [neighbor, ...]}  (edges point from node → dependency)
    Returns a list of SCCs; each SCC is a list of node names.
    Nodes not in graph keys are ignored.
    """
    index_counter = [0]
    stack: List[str] = []
    on_stack: set = set()
    index_map: Dict[str, int] = {}
    lowlink: Dict[str, int] = {}
    sccs: List[List[str]] = []

    def _iter_neighbors(v: str) -> Iterator[str]:
        return iter(graph.get(v, []))

    for start in list(graph.keys()):
        if start in index_map:
            continue

        # Call stack entries: (node, neighbor_iterator)
        call_stack: List[Tuple[str, Iterator[str]]] = []

        index_map[start] = lowlink[start] = index_counter[0]
        index_counter[0] += 1
        stack.append(start)
        on_stack.add(start)
        call_stack.append((start, _iter_neighbors(start)))

        while call_stack:
            v, it = call_stack[-1]
            try:
                w = next(it)
                if w not in index_map:
                    index_map[w] = lowlink[w] = index_counter[0]
                    index_counter[0] += 1
                    stack.append(w)
                    on_stack.add(w)
                    call_stack.append((w, _iter_neighbors(w)))
                elif w in on_stack:
                    lowlink[v] = min(lowlink[v], index_map[w])
            except StopIteration:
                call_stack.pop()
                if call_stack:
                    parent = call_stack[-1][0]
                    lowlink[parent] = min(lowlink[parent], lowlink[v])
                if lowlink[v] == index_map[v]:
                    scc: List[str] = []
                    while True:
                        w = stack.pop()
                        on_stack.discard(w)
                        scc.append(w)
                        if w == v:
                            break
                    sccs.append(scc)

    return sccs


# ---------------------------------------------------------------------------
# Condensed DAG
# ---------------------------------------------------------------------------

@dataclass
class CondensedNode:
    id: int
    chars: List[str]           # all chars in this SCC (usually just one)
    importance: float
    embedding: Optional[np.ndarray]
    prereqs: List[int] = field(default_factory=list)   # ids of prerequisite nodes


def build_condensed_graph(
    char_deps: Dict[str, List[str]],
    importances: Dict[str, float],
    embeddings: Dict[str, np.ndarray],
) -> Tuple[List[CondensedNode], Dict[str, int]]:
    """
    Build a condensed DAG from raw char dependencies.

    Steps:
      1. Filter deps to working set.
      2. Run Tarjan's SCC to merge any cyclic groups.
      3. Build CondensedNode list with merged importances and embeddings.

    Returns:
      nodes         : list of CondensedNode
      char_to_node  : {char: node_id}
    """
    working_set = set(char_deps.keys())

    # Filter deps: only keep edges to chars in the working set
    filtered: Dict[str, List[str]] = {
        ch: [d for d in deps if d in working_set]
        for ch, deps in char_deps.items()
    }

    sccs = tarjan_scc(filtered)

    # Map each char to its SCC index
    char_to_scc: Dict[str, int] = {}
    for scc_id, scc in enumerate(sccs):
        for ch in scc:
            char_to_scc[ch] = scc_id

    nodes: List[CondensedNode] = []
    for scc_id, scc in enumerate(sccs):
        # Merged importance
        imp = sum(importances.get(ch, 0.0) for ch in scc)

        # Merged embedding: average of available member vectors (already normalized)
        embs = [embeddings[ch] for ch in scc if ch in embeddings]
        if embs:
            avg = np.mean(embs, axis=0).astype(np.float32)
            norm = np.linalg.norm(avg)
            emb: Optional[np.ndarray] = avg / norm if norm > 0 else avg
        else:
            emb = None

        # External prereq SCC ids
        prereq_ids: List[int] = list({
            char_to_scc[dep]
            for ch in scc
            for dep in filtered.get(ch, [])
            if char_to_scc.get(dep, scc_id) != scc_id
        })

        nodes.append(CondensedNode(
            id=scc_id,
            chars=scc,
            importance=imp,
            embedding=emb,
            prereqs=prereq_ids,
        ))

    return nodes, char_to_scc
