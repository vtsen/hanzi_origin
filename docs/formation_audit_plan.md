# Formation Audit Plan

Compare and revise formation data in `data/dep_forest/dep_forest_for_chars/` against Wiktionary.
Goal: identify wrong formation_type, wrong components, and wrong depicted objects across all chars.

---

## Principles (learned from day 16 pilot)

1. **Use the traditional form for Wiktionary lookup.** Simplified char pages often have less etymology or just redirect. Get the traditional form from `char_info.json`'s `trad` field; if none, the simplified is also the traditional.
2. **Never fabricate.** If Wiktionary says "etymology missing" or has no Etymology section, record `"no_data"` — do not infer or guess.
3. **Extract only the Etymology section**, not the Definitions or Usage sections.
4. **Compare four things** (see below).
5. **Flag differences, don't auto-fix.** Human reviews all flagged chars before any data change.

---

## What to Compare

For each character, compare our dep_forest `formations[0]` entry against Wiktionary's etymology:

| Field | Our data field | What to extract from Wiktionary |
|-------|---------------|----------------------------------|
| Formation type | `formation_type` | Pictograph / Ideogrammic compound / Phono-semantic / Indicative |
| Semantic component | described in `note` | The meaning-carrying component |
| Phonetic component | described in `note` (for phono-semantic) | The sound-carrying component |
| Depicted object | described in `note` (for pictographs) | What the original drawing represents |

**Valid formation_type values in our schema:**
- `pictograph`
- `simple_indicative`
- `compound_ideograph`
- `phono_semantic_compound`

**Wiktionary → our schema mapping:**
- "Pictogram / 象形" → `pictograph`
- "Ideogrammic compound / 會意" → `compound_ideograph`
- "Phono-semantic compound / 形聲" → `phono_semantic_compound`
- "Ideographic / 指事 / Indicative" → `simple_indicative`

---

## Difference Severity

Flag as **SIGNIFICANT** (must review):
- Formation type mismatch (e.g., our data says compound_ideograph, Wiktionary says phono_semantic)
- Wrong phonetic component (phono_semantic chars — e.g., 部: we say 阜, Wiktionary says 咅)
- Wrong semantic component
- Wrong depicted object for pictographs (e.g., 凡: we say mold/cast, Wiktionary says plate/basin)
- Our note is self-referential / circular (e.g., "奄声" as phonetic for 奄)

Flag as **MINOR** (note for later):
- Same type, different nuance in description
- Our note picks one theory among disputed alternatives (record what alternatives exist)
- Wiktionary says "etymology unclear/disputed" — note this

---

## Execution: How Agents Should Run This

For a batch of N characters:

**Step 1 — Gather our data**
For each char, extract from dep_forest:
```
{
  "char": "X",
  "trad": ["T1", "T2"],         // from char_info.json, empty if same as simplified
  "formation_type": "...",
  "note": "..."
}
```

**Step 2 — Fetch Wiktionary**
- Lookup URL: `https://en.wiktionary.org/wiki/<URL_ENCODED_CHAR>`
- Use the **first traditional form** if available; otherwise use the simplified.
- If the page says "Redirect" to the traditional, follow it.
- Extract only the **Chinese > Etymology** section.

**Step 3 — Compare and output**
For each char, output one of:
```
MATCH    — formation type and components agree
MINOR    — same type, minor description difference
SIGNIF   — significant mismatch (specify which field)
NO_DATA  — Wiktionary has no etymology section
```

For SIGNIF entries, record:
```
{
  "char": "X",
  "trad_used": "T",
  "wiktionary_url": "...",
  "our_type": "...",
  "wiki_type": "...",
  "our_note_summary": "...",
  "wiki_note_summary": "...",
  "difference": "type_mismatch | wrong_phonetic | wrong_semantic | wrong_object | circular_note"
}
```

---

## Revision Process

After all chars are flagged:

1. **Human reviews each SIGNIF entry** — decide: accept Wiktionary, keep ours, or note as "disputed"
2. **Edit dep_forest JSON** — update `formation_type` and `note` for accepted corrections
3. **Re-run `generate_char_info.py`** to rebuild `data/char_info.json`
4. **Commit** with a clear message listing which chars were changed and why

---

## Website Integration (future)

Options for exposing this on the site:

**Option A — Wiktionary link only**
Add a "📖 Wiktionary" link in the char detail panel pointing to the traditional form's page.
Simple, zero data work, always up-to-date.

**Option B — Alternative etymology note**
Add an `alt_formation` field to dep_forest entries for chars where our interpretation differs from Wiktionary's mainstream view. Render this as a collapsible "Alternative view" in the formation section of the char detail.

**Option C — Dispute flag**
Add a boolean `formation_disputed: true` field. Render a small indicator in the UI so learners know the etymology is contested.

Recommended: start with **Option A** (trivial to implement), add **Option C** after the audit is complete.

---

## Swapping Primary Formation and Dependency Revision

After human review, for each SIGNIF char the decision is one of:
- **Keep ours** — our explanation is preferred or equally valid
- **Swap to Wiktionary** — replace our `formation_type` and `note` with the Wiktionary-based account
- **Mark disputed** — both are plausible; keep ours but set `formation_disputed: true`

When **Swap** is chosen, the `dependencies` field must also be reviewed:

- The `dependencies` array lists the component chars that make up the formation (e.g., for a phono_semantic_compound the phonetic char and the semantic radical).
- If the formation changes (e.g., 进: we said 止+隹, Wiktionary says 辵+隹), the dependency on 止 may need to be replaced with 辵, and 辵 must exist in the learning universe or be noted as absent.
- If the formation type changes (e.g., compound_ideograph → phono_semantic_compound), check whether the previously listed deps were semantic guesses that are now wrong — they may need to be removed or reordered (phonetic dep listed first by convention).
- After any dep change, re-run the learning plan coherence scoring if the affected char is in the first ~20 days (high-frequency chars have the most downstream impact on the graph).

**Checklist per swapped char:**
1. Update `formation_type` and `note` in the dep_forest JSON
2. Diff the old vs. new components — identify added/removed/changed deps
3. Edit `dependencies` array to match new components
4. Verify each new dep char exists in `data/chars.json` (the learning universe)
5. Regenerate `data/char_info.json` via `generate_char_info.py`
6. Commit with message format: `fix formation: 進 compound_ideograph→phono_semantic, dep 止→辵`

---

## Scope and Priority

Total chars: **6,515** across 4 tiers (see `data/formation_audit/audit_priority.json`).

| Tier | Chars | Condition | Why this priority |
|------|------:|-----------|-------------------|
| 1    |   450 | In plan30s | Highest-impact learner chars |
| 2    |   551 | In plan50 but not plan30s | Common chars in medium plan |
| 3    | 3,014 | In plan100 but not plan50 | Less frequent but covered by long plan |
| 4    | 2,500 | In dep_forest universe only | Background chars, audit last |

Within each tier, chars are sorted by **frequency rank** (most frequent first).

**Already audited:** 100 chars (days 1–5 of plan50 — basic radicals). These are structurally
important but not the most frequent; most top-100 frequency chars remain unaudited.

**Remaining:** ~6,415 chars.

### Batching plan

- **Batch size:** 10 chars per agent (Wiktionary fetches are the bottleneck)
- **Parallelism:** run up to 10 agents at a time = 100 chars per round
- **Total rounds:** ~65 rounds to cover all tiers, but stop after Tier 2 (1,001 chars, ~10 rounds) for
  meaningful coverage of all learner-facing chars
- **Expected SIGNIF rate:** ~15–20% based on days 1–5 pilot

### How to pick the next batch

Read `data/formation_audit/audit_priority.json` in order, skip entries with `"audited": true`,
take the next 10. After each round, re-run `_tmp_audit_priority.py` to regenerate the file with
`audited` flags updated from new batch outputs.

### Naming convention for new batch files

`data/formation_audit/tier{N}_batch{M}.json` — e.g. `tier1_batch1.json` for the first 10 tier-1 chars.
(Old `days1to5_batchN.json` files are the completed days-1–5 batches; keep them as-is.)

---

## Output Location

- Batch results → `data/formation_audit/tier{N}_batch{M}.json`
- Priority index → `data/formation_audit/audit_priority.json` (regenerate after each round)
- Website-facing notes → `data/formation_audit/formation_notes.json` (rebuilt by `build_notes.js`)
