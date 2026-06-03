# Hanzi Learning Plan — Website

A static GitHub Pages site that displays the 150-day Chinese character learning plan
as an interactive web app.

## Pages

| Route | Description |
|---|---|
| `#home` | Overview with key stats and links |
| `#day/N` | Characters for day N (1–150), with ranks and coherence score |
| `#search` | Look up a character or jump to a day by number |
| `#overview` | 150-cell grid, colour-coded by daily coherence |

## Enabling GitHub Pages

1. Push this repository to GitHub (if not already done).
2. Go to **Settings → Pages** in the repository.
3. Under **Source**, select **Deploy from a branch**.
4. Choose branch `main` (or whichever branch you use) and folder **`/website`**.
5. Click **Save**. GitHub will publish the site at `https://<username>.github.io/<repo>/`.

> GitHub Pages can serve from any folder on any branch. The `/website` option
> appears in the dropdown once you select the branch.

## Local development

Because the site uses `fetch()` to load JSON data, it must be served over HTTP —
opening `index.html` directly as a `file://` URL will fail due to CORS restrictions.

Serve locally with any static server, for example:

```bash
# Python (from the project root)
python -m http.server 8000 --directory website

# Then open: http://localhost:8000
```

## Updating the learning plan

The site reads two data files from `website/data/`:

| File | Source |
|---|---|
| `plan.json` | Copy of `data/learning_plan/learning_plan_150days_additive_gap0.3.json` |
| `char_freq_rank.json` | Copy of `data/char_freq_rank.json` |

To update after regenerating the plan, copy the new files into `website/data/` and
commit. No build step is needed.
