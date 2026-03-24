# Daily Link Curator

A personal link digest that refreshes twice a day using Claude Opus and web search.

## How it works

1. GitHub Actions triggers `curator.py` at 8am and 8pm UTC.
2. The script calls Claude Opus with the `web_search_20250305` tool.
3. Claude searches across your interest areas and returns 8 curated links as JSON.
4. The script renders them into `index.html` and commits the file back to the repo.
5. GitHub Pages serves `index.html` publicly.

## Setup (≈10 minutes)

### 1. Fork or clone this repo

```bash
git clone https://github.com/YOUR_USERNAME/link-curator.git
cd link-curator
```

### 2. Add your Anthropic API key as a GitHub Secret

In your repo: **Settings → Secrets and variables → Actions → New repository secret**

- Name: `ANTHROPIC_API_KEY`
- Value: your key from console.anthropic.com

### 3. Enable GitHub Pages

In your repo: **Settings → Pages**

- Source: **Deploy from a branch**
- Branch: `main`, folder: `/ (root)`
- Save

Your page will appear at `https://YOUR_USERNAME.github.io/link-curator/`

### 4. Trigger your first run

Go to **Actions → Curate Links → Run workflow** to generate the first `index.html`
without waiting for the next scheduled run.

### 5. Customise your taste profile

Edit the `TASTE_PROFILE` string near the top of `curator.py`. Be specific — the more
precise your description, the better Claude's picks will be. Commit and push; the next
run will use the updated profile.

## Running locally

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...
python curator.py
open index.html
```

## Estimated cost

Each run makes one Claude Opus API call with web search. Typical cost is **$0.03–0.08
per run**, or roughly **$1.80–$4.80/month** for twice-daily refreshes.

## Files

| File | Purpose |
|------|---------|
| `curator.py` | Main agent: prompts Claude, parses JSON, renders HTML |
| `index.html` | The generated page (updated by the workflow) |
| `requirements.txt` | Python dependencies |
| `.github/workflows/update.yml` | Scheduled GitHub Actions workflow |
