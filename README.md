# 汉字 Learning Plan

A data-driven website for learning Chinese characters, ordered by frequency and structural
dependency, with daily batches grouped for semantic coherence.

Live site: **https://vtsen.github.io/hanzi_origin/**

---

## What it is

The site generates a multi-day learning schedule across ~6,500 Chinese characters.
Each day's batch is chosen to balance three goals:

1. **Frequency-first** — the most useful characters appear as early as their prerequisites allow.
2. **Dependency ordering** — a character is never introduced before the components it is built from.
3. **Semantic coherence** — characters within a day share structural or thematic connections,
   making them easier to memorize together.

Three plan sizes are available (switchable via the nav bar):

| Plan | Days | Chars/day | Total chars |
|------|-----:|----------:|------------:|
| Small | 30 | 15 | 450 |
| Medium (default) | 50 | 20 | 1,000 |
| Large | 100 | 40 | 4,015 |

---

## Features

- **Day view** — browse characters day by day; click any character for full detail
- **Character detail** — formation explanation, meaning senses, dependency graph, historical
  scripts (oracle bone / seal / regular), Wiktionary-linked etymology notes
- **Debated formation flags** — characters where our formation data diverges from Wiktionary's
  mainstream etymology are marked ⚑ with an alternative-explanation note
- **Search** — find any character and jump to its scheduled day
- **Overview grid** — all scheduled characters at a glance

---

## Repository layout

```
hanzi_origin/
├── index.html                        # Single-page app entry point
├── app.js                            # All routing, rendering, and data logic
├── style.css                         # Styles
│
├── data/
│   ├── char_freq_rank.json           # ~8,900 chars ordered by corpus frequency
│   ├── char_info.json                # Per-char: senses, edges, formation, deps, trad forms
│   ├── chars.json                    # Master character list
│   ├── dep_forest/                   # Etymology & dependency data (6,507 chars, chunked JSON)
│   ├── learning_plan/                # Generated plan files + embeddings cache
│   │   ├── learning_plan_30days_additive_gap0.3.json
│   │   ├── learning_plan_50days_additive_gap0.3.json
│   │   └── learning_plan_100days_additive_gap0.3.json
│   └── formation_audit/
│       ├── formation_notes.json      # Website-facing audit results (SIGNIF + MINOR, 103 entries)
│       ├── audit_priority.json       # All 6,515 chars sorted by audit priority; tracks progress
│       ├── tier1_batch{01-21}.json   # Raw agent audit output, tier-1 first half
│       └── days1to5_batch{1-10}.json # Raw agent audit output, initial pilot
│
├── src/hanzi_learning_plan/          # Python scheduler package
│   ├── run.py                        # Entry point: --plan30s | --plan50 | --plan100
│   ├── scheduler.py                  # Greedy scheduler + local search
│   ├── data_loader.py                # Dependency graph builder
│   └── graph.py                      # Tarjan SCC + condensed DAG
│
└── docs/
    ├── methodology.md                # Algorithm design and mode comparisons
    ├── scheduler_params.md           # All tunable parameters + experiment log
    └── formation_audit_plan.md       # Formation audit methodology and progress
```

---

## Regenerating a plan

Requires Python 3.10+, dependencies in `requirements.txt`, and an OpenAI API key
(for embedding generation on first run; cached afterward).

```bash
# activate virtualenv
source hanzi_venv/Scripts/activate        # Windows
# source hanzi_venv/bin/activate          # macOS/Linux

# regenerate the 50-day plan (default params)
python -m src.hanzi_learning_plan.run --plan50

# other sizes
python -m src.hanzi_learning_plan.run --plan30s
python -m src.hanzi_learning_plan.run --plan100
```

See `docs/scheduler_params.md` for all tunable parameters and the experiment log.

---

## Formation audit

The `data/dep_forest/` formation data is being compared against Wiktionary etymology entries.
Characters with significant discrepancies are shown in-app with a ⚑ badge.

**Current progress** (as of 2026-06-09):
- 309 / 6,515 chars audited
- 103 entries in `formation_notes.json` (92 SIGNIF, 11 MINOR)
- Tier-1 first half complete (top 225 frequency-rank chars in plan30s)

See `docs/formation_audit_plan.md` for methodology, batch structure, and next steps.

---

## Development

Serve locally with any static HTTP server:

```bash
python -m http.server 8080
# then open http://localhost:8080
```

The app is a plain HTML/JS/CSS single-page app — no build step required.
