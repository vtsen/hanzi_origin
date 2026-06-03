# Hanzi Learning Plan Generator — Methodology

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Data Pipeline](#2-data-pipeline)
3. [Importance Function](#3-importance-function)
4. [Importance Propagation Modes](#4-importance-propagation-modes)
5. [Greedy Scheduler](#5-greedy-scheduler)
6. [Comparative Results](#6-comparative-results-30-day-plan-m20-charday)
7. [Key Tensions and Open Problems](#7-key-tensions-and-open-problems)

---

## 1. Problem Statement

**Goal.** Given a universe of ~6500 Chinese characters (Hanzi), generate an N-day learning plan that assigns M characters per day to a learner, subject to three simultaneous constraints:

1. **Dependency ordering.** A character cannot be taught before its components are taught. For example, 的 (rank 1 by frequency) has 勺 as a component, which in turn has 日 as a component. Therefore 日 must precede 勺, which must precede 的.

2. **Frequency prioritization.** High-frequency characters are more useful to the learner. 的 is the single most frequent character in Chinese text; it should appear in the plan as early as the dependency constraint allows.

3. **Semantic coherence within a day.** Characters that are thematically related (share similar meanings, belong to the same semantic field) are easier to learn together. A day whose characters are all body-part words is more memorable than a random assortment.

These three goals are in tension with each other. Resolving that tension is the central design problem of the system.

---

## 2. Data Pipeline

### 2.1 Source Data

| Dataset | Description |
|---|---|
| `dep_forest/dep_forest_for_chars/` | Etymology and dependency data for 6507 characters, stored as JSON chunks. Each entry lists the character's `senses` (for meaning text) and `dependencies` (component characters). |
| `data/char_freq_rank.json` | Ordered list of 8943 characters by corpus frequency (most frequent first). Used to assign 1-based ranks: rank 1 = most frequent. |
| `data/chars.json` | Fallback index. Characters not appearing in `char_freq_rank.json` receive a rank beyond the frequency list, preserving `chars.json` order. |

Loading is handled by `build_char_dataset()` in `data_loader.py`, which produces three dictionaries:

- `char_deps`: `{char: [dep_char, ...]}`
- `char_meanings`: `{char: meaning_text}` (used for embeddings)
- `char_ranks`: `{char: int}` (1-based, lower = more frequent)

### 2.2 Phantom Dependency Injection

Not all component characters that appear as dependencies are themselves in the working character set. For example, archaic radicals like 辵, 亼, or 丿 are referenced as components of known characters but may not exist as standalone learnable items.

**Problem.** If 辵 is needed by 还 but 辵 is not in the working set, Tarjan's algorithm simply ignores the edge. The character 还 would be treated as having no prerequisites and could be scheduled independently of its actual component structure.

**Solution: phantom node injection** (`_inject_phantom_deps` in `data_loader.py`). For every dependency reference that points outside the working set:

1. A phantom node is created for the missing component.
2. The phantom is assigned the **median rank** of the current universe. This is a neutral weight — the phantom is neither treated as highly frequent nor as extremely rare.
3. A **reverse dependency edge** is added: the phantom depends back on each character that needs it. This creates a cycle: `missing_dep → dependent → missing_dep`.
4. Tarjan's SCC will detect this cycle and merge the phantom with its dependents into a single SCC node, ensuring they are scheduled on the **same day**.

In a full run (6507 characters), this injects **414 phantom nodes**. The phantoms carry no embedding (since they have no meaning text in the dataset); the SCC node's embedding falls back to the real character's vector.

```python
# Reverse dep creates a cycle: phantom ↔ dependent → same SCC → same day
char_deps[phantom] = dependents
char_ranks[phantom] = median_rank
```

### 2.3 Condensed DAG via Tarjan's SCC

Raw character dependencies can contain cycles — either genuine etymological cycles or cycles introduced by phantom injection. A schedule requires a DAG (directed acyclic graph), so cycles must be collapsed.

**Tarjan's strongly-connected-components (SCC)** algorithm (`tarjan_scc` in `graph.py`) is run on the filtered dependency graph. Every set of mutually-dependent characters is merged into a single `CondensedNode`. Properties of the merged node:

- `chars`: all original characters in the SCC
- `importance`: **sum** of member importances
- `embedding`: L2-normalized average of available member vectors
- `prereqs`: list of prerequisite `CondensedNode` IDs (deduplicated, excluding the node itself)

In the full 30-day run, **313 merged SCCs** result from cycles (mostly phantom-induced). The condensed graph is a DAG and is amenable to topological scheduling.

```python
# graph.py — build_condensed_graph
sccs = tarjan_scc(filtered)
for scc_id, scc in enumerate(sccs):
    imp = sum(importances.get(ch, 0.0) for ch in scc)  # sum, not max
    embs = [embeddings[ch] for ch in scc if ch in embeddings]
    avg = np.mean(embs, axis=0); emb = avg / np.linalg.norm(avg)
    prereq_ids = list({char_to_scc[dep] for ch in scc
                       for dep in filtered.get(ch, [])
                       if char_to_scc.get(dep, scc_id) != scc_id})
```

---

## 3. Importance Function

Each character is assigned a base importance score derived from its corpus frequency rank:

```
I(c) = exp(-λ × rank(c))
```

With `λ = 0.001` (the value used in all 30-day runs):

| Rank | Character (example) | I(c) |
|---|---|---|
| 1 | 的 | ≈ 0.999 |
| 101 | 日 | ≈ 0.904 |
| 500 | (mid-frequency) | ≈ 0.607 |
| 1000 | | ≈ 0.368 |
| 3000 | | ≈ 0.050 |
| 3269 | 勺 | ≈ 0.036 |
| 7000+ | (archaic/rare) | ≈ 0.001 |

The exponential decay was chosen to:
- Give very high frequency characters (ranks 1–200) nearly equal, high importance.
- Create a steep drop-off in the mid-thousands, naturally deprioritizing rare characters.
- Remain differentiable, enabling smooth gradient signals during importance propagation.

The `λ` parameter controls how quickly importance decays. Higher `λ` creates steeper decay; the current value of 0.001 gives moderate spread across the 6500-character universe.

---

## 4. Importance Propagation Modes

The base importance function creates a fundamental conflict: rare prerequisite characters (like 勺 at rank 3269, I ≈ 0.036) will be deprioritized far below their dependents (的 at rank 1, I ≈ 1.0). Since the scheduler cannot schedule 的 until 勺 has appeared, 勺's low importance may prevent it from being scheduled within a 30-day window, blocking 的 entirely.

Five modes address this conflict. All except `jit` use a reverse-topological BFS (Kahn's algorithm on the transpose graph) so each node's effective importance is finalized before propagating to its prerequisites.

---

### 4.1 `raw` — No Propagation

**Description.** Importances are used exactly as computed by `I(c) = exp(-λ × rank)`. No adjustment for dependency structure.

**Formula.**
```
eff(c) = I(c)
```

**Advantage.** Produces the most frequency-faithful schedule. Day 1 is a clean set of the most frequent atomic characters (一, 么, 只, 上, 下, 小, 大, 高, 子, 以, 者, 不, 之, 为, 来, 其, 而, 于, 了, 也).

**Issue.** 勺 has rank 3269 and I ≈ 0.036. In a 30-day plan with M=20 chars/day, only the top ~600 characters by effective importance can be scheduled. 勺 falls far outside this window, so it is never scheduled, and consequently **的 never appears in the plan at all** (0 out of 30 days). Any character blocked by a rare-but-necessary prerequisite is silently dropped.

**Total chars scheduled (30 days, M=20):** 721

---

### 4.2 `max_descendant` — Full Propagation

**Description.** Each node's effective importance is overridden by its most important descendant.

**Formula (reverse-topological, propagating from leaves toward roots):**
```
eff(prereq) = max(eff(prereq), eff(child))
```

**Example.** 勺 has 的 as a descendant (via: 的 depends on 勺). Since eff(的) ≈ 1.0, eff(勺) gets lifted to ≈ 1.0. 勺 becomes indistinguishable in priority from 的 itself.

**Advantage.** Guarantees that 的 appears in the plan (Day 21 in one run). All characters with high-frequency descendants are promoted early.

**Issue.** The promotion is indiscriminate. Any character that is ancestral to *any* high-frequency character inherits that character's full importance. Characters like 缶 (rank 5280), 耒 (rank 7000+), and 鼎 get lifted to near-1.0 because they are ancestral to some common word. This **floods Day 1 with obscure radicals** (勺, 壶, 尊, 丰, 皿, 酉, 缶, 豆, 甬, 耒, 鼎, 弓, 匕, 角, 殳, 戈, 刀, 干, 甲, 盾) — pedagogically counterproductive.

**Total chars scheduled:** 1706 | **Avg coherence:** 0.3448

---

### 4.3 `decayed` — Softened Propagation

**Description.** Same direction as `max_descendant`, but the propagated value is attenuated by a factor `decay` (default 0.5) at each hop.

**Formula:**
```
eff(prereq) = max(eff(prereq), decay × eff(child))
```

**Example.** With decay=0.5: eff(勺) ← max(0.036, 0.5 × 1.0) = 0.5. This is a meaningful boost, but not as extreme as the full override. At two hops: eff(日's-prereq) ← max(own, 0.5 × 0.5) = 0.25.

**Advantage.** Softens the flooding problem of `max_descendant`. Rare prereqs get a boost proportional to distance from high-frequency descendants; direct prerequisites are boosted more than grandparent prerequisites.

**Issue.** The shape of the decay (geometric per hop) may still produce distortions over long chains. The mode does not preserve frequency hierarchy: a rare direct prereq of 的 still gets a boost of 0.5, higher than many moderately-frequent independent characters at rank ~700 (I ≈ 0.50).

---

### 4.4 `additive` — Boost Without Override

**Description.** The own importance is preserved, and a boost proportional to the best descendant's effective importance is *added* rather than used as a replacement.

**Formula:**
```
eff(prereq) = own(prereq) + α × max_eff(best_child)
```

where `α` is the `decay` parameter (used as an additive coefficient; default 0.3 in 30-day runs).

**Example.**
- `own(勺) = I(3269) ≈ 0.036`
- `max_eff(best_child of 勺) = eff(的) ≈ 1.0`
- `eff(勺) = 0.036 + 0.3 × 1.0 = 0.336`

This preserves hierarchy: 的 (eff ≈ 1.0) still outranks 勺 (eff ≈ 0.336), which still outranks characters with no high-frequency descendants. The boost is meaningful but bounded.

**Advantage.** Day 1 becomes a **radical primer** — high-importance characters that are themselves common AND serve as components for many others: 日, 人, 目, 土, 者, 口, 木, 二, 水, 手, 肉, 甲, 火, 言, 刀, 心, 女, 虫, 禾, 又. This is pedagogically sound: the learner starts with foundational building blocks.

**Issue.**
- 的 is pushed to **Day 27**, because even with additive boosting, the many intermediate prerequisite chains must be satisfied first, and the moderate boost is not enough to pull 的 through all its dependencies quickly.
- Some obscure dependency chains get early-scheduled characters that pollute the plan: the additive boost can propagate through long chains, causing surprising early appearances of mid-frequency chars.

**Total chars scheduled:** 1687 | **Avg coherence:** 0.3014

---

### 4.5 `jit` — Just-In-Time Scheduling

**Description.** A two-pass approach that avoids static importance propagation entirely. Instead, urgency is computed *dynamically* during scheduling based on when dependents are estimated to be needed.

**Pass 1 (pilot schedule).** Run `greedy_schedule` with `w=1.0` (pure importance, no coherence) and `L_factor=1` (small pool) to quickly estimate each node's "natural day" — the day it would be scheduled under raw importance alone.

**Pass 2 (real schedule).** Re-run `greedy_schedule` with the full objective, but add a dynamic urgency boost to each candidate's score:

```
score = w × importance + (1-w) × avg_cosine_sim
        + w × γ / max(1, pilot_day[best_child] - current_day)
```

The urgency term spikes when a dependent is scheduled "tomorrow" in the pilot (days_until = 1 → urgency = γ) and decays to near-zero when the dependent is far away (days_until = 25 → urgency ≈ 0.04γ). This ensures prerequisites are scheduled just before they are needed, rather than being pulled all the way to Day 1.

**Advantage.** Avoids the 20-day wasteful early-scheduling of rare radicals. The pilot provides just enough information to pull each prereq into the window where it is actually needed.

**Issue (structural failure for deep chains with rare prereqs).** If a prerequisite (like 勺) has rank 3269 and never appears in the pilot schedule (because it falls beyond the 30-day horizon under raw importance), then `pilot_day[勺]` does not exist. No urgency propagates back to 勺, so 勺 is never boosted in Pass 2, and 的 remains blocked. This is a chicken-and-egg failure:

> The JIT boost for 勺 depends on knowing when 的 needs it.
> But 的 can't be scheduled until 勺 is scheduled.
> And 勺 never appears in the pilot (rank too low for 30 days).

**Result:** 的 does not appear in the JIT schedule within 30 days.

**Total chars scheduled:** 757 | **Avg coherence:** 0.3427

The JIT mode is structurally equivalent to `raw` for deep prerequisite chains whose roots fall outside the pilot horizon. It provides meaningful improvement only when all characters in a chain are already within the planning window.

---

## 5. Greedy Scheduler

### 5.1 Topological Ordering

The scheduler enforces dependency constraints rigorously via **in-degree tracking**:

- Each node starts with `in_degree` = number of prerequisite nodes not yet scheduled.
- A node becomes a **candidate** (eligible for scheduling) when `in_degree` drops to 0.
- When a node is scheduled, `in_degree` is decremented for all its dependents; any that reach 0 are added to the candidate heap.

This is Kahn's topological sort, extended with the greedy selection logic below.

### 5.2 Candidate Pool

On each day, the scheduler pulls the top-L candidates from a max-heap ordered by `(-importance, id)`. The pool size `L = L_factor × M`. In the 30-day runs, `L_factor = 200` and `M = 20`, giving `L = 4000`. This large pool ensures that the greedy selection has wide choice across importance and semantic similarity simultaneously.

### 5.3 Day Assembly (Greedy Selection)

Characters are added to the current day one at a time. Each selection maximizes a composite score:

```
score(c) = w × importance(c)
         + (1 - w) × avg_cosine_sim(c, today_chars_so_far)
```

- `w = 0.3`: 30% weight on importance, 70% on semantic coherence.
- On the first character of the day, `avg_cosine_sim = 0` (no anchors yet), so the first pick is always the highest-importance available candidate.
- Subsequent picks are those that best match the thematic direction established by the first pick.

Semantic similarity uses **OpenAI text-embedding-3-small** vectors for each character's meaning text. Embeddings are cached locally (`embeddings_full.json`) to avoid repeated API calls. Cosine similarity is computed as a dot product (vectors are pre-normalized to unit length).

### 5.4 JIT Urgency Term

When running in `jit` mode, an additional urgency term is added to the importance component:

```python
# From scheduler.py — greedy_schedule()
if pilot_days is not None and jit_gamma > 0 and children[cand.id]:
    child_deadlines = [pilot_days[c] for c in children[cand.id] if c in pilot_days]
    if child_deadlines:
        days_until = max(1, min(child_deadlines) - _day)
        imp_term += w * jit_gamma / days_until
```

The urgency is anchored to the *soonest* child's pilot day, not the average, to prioritize critical-path prerequisites.

### 5.5 Local Search Post-Processing

After the greedy schedule is produced, a **local search** phase attempts single-node moves: each scheduled character is tried at every other day in the window `[earliest_valid_day, latest_valid_day]`, where validity is determined by dependency constraints.

A move from day `d1` to day `d2` is accepted if it strictly improves the combined objective:

```
w × ΔA + (1 - w) × ΔB > ε
```

where `ΔA` is the change in total importance coverage (nonzero only if the move crosses the N-day boundary), and `ΔB` is the change in average daily coherence, computed efficiently using cached pairwise similarity sums.

**Observed behavior.** In all runs, local search **converges after exactly 1 iteration** — meaning the greedy schedule, with its large candidate pool (`L = 4000`), already produces a near-optimal arrangement. The local search phase is essentially inert under current parameters.

---

## 6. Comparative Results (30-day plan, M=20 chars/day)

Parameters common to all runs: `λ=0.001`, `w=0.3`, `L_factor=200`, `add_phantom_deps=True`, OpenAI `text-embedding-3-small` embeddings.

### 6.1 Summary Table

| Mode | Day 1 character profile | 的 day | 勺 day | 日 day | Total chars | Avg coherence |
|---|---|---|---|---|---|---|
| `raw` | High-freq abstract chars (一么只上下…) | — (missing) | — (missing) | Day 8 | 721 | 0.344 |
| `max_descendant` | Rare radicals flood Day 1 (勺壶尊丰皿…) | Day 21† | Day 1 | Day 2 | 1706 | 0.345 |
| `additive` | Radical primer (日人目土者口木…) | Day 27 | Day 9 | Day 1 | 1687 | 0.301 |
| `jit` | High-freq abstract chars (一大小也人…) | — (missing) | — (missing) | Day 2 | 757 | 0.343 |

† `max_descendant` achieves 的 on Day 21, but at the cost of Day 1 being dominated by obscure radicals.

### 6.2 Day 1 Character Sets

**`raw`:** 一、么、只、上、下、小、大、高、子、以、者、不、之、为、来、其、而、于、了、也

*Profile:* Top-20 characters by pure frequency rank. Many are grammatical particles and abstract function words. Coherent from a frequency standpoint, but the set mixes diverse semantic categories.

**`max_descendant`:** 勺、壶、尊、丰、皿、酉、缶、豆、甬、耒、鼎、弓、匕、角、殳、戈、刀、干、甲、盾

*Profile:* Ancient weapons, vessels, and agricultural tools — the characters whose descendants include the most frequent characters in the corpus. High semantic coherence (Day 1 coherence = 0.458, highest of any mode), but the characters themselves are rare and unfamiliar to a modern learner starting from scratch.

**`additive`:** 日、人、目、土、者、口、木、二、水、手、肉、甲、火、言、刀、心、女、虫、禾、又

*Profile:* Common radicals and elemental concepts. This set is pedagogically well-motivated: these characters are both frequent and serve as components of many others. A learner starting here builds a functional foundation.

**`jit`:** 一、大、小、也、人、上、下、么、子、二、以、不、之、其、者、为、而、行、来、十

*Profile:* Near-identical to `raw` — top-frequency characters, mostly abstract function words. JIT provides no advantage over raw for characters whose prerequisite chains fall outside the scheduling window.

### 6.3 Key Observations

- **Coverage vs. depth.** `max_descendant` and `additive` schedule more than twice as many characters (1706/1687) as `raw` and `jit` (721/757) in 30 days. The propagation modes unlock prerequisite chains that would otherwise remain blocked.
- **Coherence tradeoff.** `additive` has the lowest average coherence (0.301) because the additive boost pulls prerequisite characters into the same timeframe as diverse high-frequency descendants, reducing thematic clustering. `max_descendant` maintains higher coherence (0.345) because it schedules radical families together.
- **的 appears late or never.** Even with the best propagation modes, 的 (the most frequent character) does not appear until Day 21 (`max_descendant`) or Day 27 (`additive`). This reflects the genuine constraint: 的 requires 勺, which requires 日 — and satisfying all dependencies while managing the full 6500-character universe pushes common-but-deep characters back.

---

## 7. Key Tensions and Open Problems

### 7.1 Frequency-First vs. Dependency-First

The system encodes a fundamental pedagogical choice: should learners encounter the most useful characters immediately (frequency-first), or should they first master the building blocks those characters are composed of (dependency-first)?

- `raw` and `jit` are frequency-first. 的 should ideally be on Day 1, but the dependency constraint makes this impossible.
- `additive` is dependency-first. Day 1 is a genuine radical primer, but the learner waits until Day 27 to encounter 的.
- `max_descendant` is a compromise that overshoots in the dependency direction.

There is no objectively correct answer. The right balance depends on the learner's goals and the extent to which character components are taught as part of character instruction.

### 7.2 Radical Primers as Abstract Content

The `additive` Day 1 (日人目土口木水手火言心女虫禾又) is pedagogically sound in the sense that these characters unlock many others. However, some of them (particularly archaic forms and radicals introduced via phantom injection, such as 辵, 亼, 丿) are meaningful only as components — they rarely appear as standalone characters in modern text. Presenting these to a learner as "Day 1 characters" may be confusing without additional pedagogical framing.

### 7.3 JIT Structural Failure for Long Prerequisite Chains

The JIT approach fails precisely when it is most needed: for high-frequency characters blocked by low-frequency prerequisites that fall outside the scheduling horizon. The pilot schedule, which uses raw importance, has no knowledge of deep prerequisite chains. A potential fix would be to run the pilot with propagated importances, but this reintroduces the same tradeoffs as the static propagation modes.

An alternative: run the pilot with a larger horizon (e.g., N=200) to ensure all prerequisites appear in it, then use the JIT urgency during the real 30-day schedule. This would allow urgency to propagate back through prerequisite chains that are only learnable in the longer term.

### 7.4 Local Search Is Inert

The local search phase converges after a single iteration in every run tested. This is not a failure — it reflects that the greedy algorithm with `L = 4000` candidates already produces near-optimal day assignments. However, it raises the question of whether the local search infrastructure is worth maintaining. It adds code complexity and runtime without measurable benefit. If the objective function were changed to something harder for the greedy to optimize, or if `L_factor` were reduced, local search might become useful again.

### 7.5 False VIOLATION Labels in Bundling Check

The post-run comparison script checks whether phantom-bundled characters land on the same day:

```python
bundle_checks = [('还', ['瞏', '辵']), ('的', ['勺', '日'])]
```

For the pair `('的', ['勺', '日'])`, the check reports a VIOLATION when 勺 and 日 appear on different days from 的. This is not a real violation — 勺 and 日 are genuine characters in the working set that must be scheduled *before* 的 (not same-day). The bundling check is meaningful only for true phantoms (like 辵, which is only a component and was injected as a phantom node bound to 还). Applying the same check to real characters that happen to be prerequisites produces false alarms.

### 7.6 SCC Importance Summation

When multiple characters are merged into a single SCC node (due to cycles), their importances are **summed**:

```python
imp = sum(importances.get(ch, 0.0) for ch in scc)
```

This means an SCC containing 5 characters is boosted 5× relative to a singleton. For phantom-merged SCCs (one real char + one phantom), the phantom's importance (median rank ≈ I(3000) ≈ 0.05) adds a small but nonzero boost to the real character's score. This is an implicit and somewhat arbitrary choice; alternatives include using `max` or treating the real character's importance as the SCC's importance.

### 7.7 Embedding Quality for Rare Characters

Embeddings are computed from the character's `meaning_text` — the concatenated sense definitions in the etymology data. For very rare or archaic characters, the meaning text may be sparse, terse, or absent (falling back to the character itself as the embedding input). This degrades the semantic coherence signal for those characters, potentially causing them to cluster poorly with or against semantically related characters.

---

*Document generated: 2026-06-01*
