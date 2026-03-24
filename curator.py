#!/usr/bin/env python3
"""
Daily link curator — fetches 8 interesting links twice a day using Claude.
Run directly or via GitHub Actions (see .github/workflows/update.yml).
"""

import os
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import anthropic

# ─────────────────────────────────────────────────────────────────
# Taste profile — edit this to shape what Claude looks for
# ─────────────────────────────────────────────────────────────────

TASTE_PROFILE = """
Reader profile (patent litigation attorney, intellectual, selective):

STRONG interests:
- IP law: Federal Circuit decisions, § 101/Alice doctrine, PTAB developments, legal AI tools
- AI/ML: interpretability research, capabilities milestones, governance & policy debates
- Economics & policy: depth of Marginal Revolution / Works in Progress / Asterisk level
- Roguelike / deckbuilder game design theory (Slay the Spire-tier games)
- Organizational psychology: psychological safety, evidence-based management, firm culture
- Minimalist design, typography, architecture, design-forward product aesthetics
- History and narrative nonfiction
- Developer tools, workflow automation, Python ecosystem

Preferred sources and publication tier:
  LessWrong, ACX / Astral Codex Ten, Works in Progress, Asterisk Magazine,
  Marginal Revolution, Lawfare, Hacker News (standout posts only), ArXiv
  (accessible papers), SSRN (IP/tech law), The Browser picks, Ribbonfarm,
  long-form journalism (The Atlantic, Wired features), academic blogs.

Hard avoids:
  Hot takes under 800 words, SEO listicles, press-release rewrites,
  social media drama, generic "AI will change everything" boosterism,
  celebrity gossip, sports scores, crypto price speculation.
"""

CATEGORIES = [
    "Law & Policy",
    "AI & Tech",
    "Economics",
    "Games & Design",
    "History & Science",
    "Tools & Dev",
]

NUM_LINKS  = 8
OUTPUT_FILE = Path(__file__).parent / "index.html"


# ─────────────────────────────────────────────────────────────────
# Agent — calls Claude with web_search
# ─────────────────────────────────────────────────────────────────

def build_prompt() -> str:
    today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")
    cats  = " | ".join(CATEGORIES)
    return f"""Today is {today}. You are an expert content curator with refined taste.

Search the web across multiple queries to find exactly {NUM_LINKS} genuinely interesting
links that would resonate with the reader described below. Spread picks across their
different interest areas — don't cluster everything in one topic.

{TASTE_PROFILE}

For each candidate: verify the URL resolves, the article was published recently (last
72h for news/blogs; last 2 weeks for research papers or slower-moving topics), and the
content matches your description. Prefer depth over virality.

Return ONLY a valid JSON array — no preamble, no markdown fences, no commentary:
[
  {{
    "title": "article title (rewrite to be more descriptive if the original is vague)",
    "url": "https://actual-verified-url.com/path",
    "source": "Publication or site name",
    "description": "2 sentences: what this piece covers and why it earns a read for this specific reader.",
    "category": "one of: {cats}"
  }}
]"""


def fetch_links() -> list[dict]:
    """Run the Claude curator agent and return a list of link dicts."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": build_prompt()}],
    )

    # web_search_20250305 is handled server-side — the final text block
    # contains Claude's answer after all searches are complete.
    text = "\n".join(
        block.text for block in response.content
        if block.type == "text"
    ).strip()

    return _parse_links(text)


def _parse_links(text: str) -> list[dict]:
    """Extract and validate the JSON array from Claude's response."""
    # Strip accidental markdown fences
    text = re.sub(r"```(?:json)?\s*", "", text).strip()

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON array found in response:\n{text[:600]}")

    links = json.loads(match.group())

    validated = []
    for item in links:
        if "title" in item and "url" in item and item["url"].startswith("http"):
            validated.append(item)

    if len(validated) < 4:
        raise ValueError(f"Too few valid links returned ({len(validated)}). Raw:\n{text[:600]}")

    return validated


# ─────────────────────────────────────────────────────────────────
# HTML renderer
# ─────────────────────────────────────────────────────────────────

# Light-bg / text-color pairs for each category tag
CATEGORY_STYLES: dict[str, tuple[str, str]] = {
    "Law & Policy":      ("#E6F1FB", "#0C447C"),
    "AI & Tech":         ("#EEEDFE", "#3C3489"),
    "Economics":         ("#E1F5EE", "#085041"),
    "Games & Design":    ("#FAEEDA", "#633806"),
    "History & Science": ("#EAF3DE", "#27500A"),
    "Tools & Dev":       ("#F1EFE8", "#444441"),
}

DARK_CATEGORY_STYLES: dict[str, tuple[str, str]] = {
    "Law & Policy":      ("#0C447C", "#B5D4F4"),
    "AI & Tech":         ("#3C3489", "#CECBF6"),
    "Economics":         ("#085041", "#9FE1CB"),
    "Games & Design":    ("#633806", "#FAC775"),
    "History & Science": ("#27500A", "#C0DD97"),
    "Tools & Dev":       ("#444441", "#D3D1C7"),
}


def render_html(links: list[dict]) -> str:
    now       = datetime.now(timezone.utc)
    timestamp = now.strftime("%B %d, %Y at %H:%M UTC")

    cards = []
    for link in links:
        cat          = link.get("category", "Tools & Dev")
        light_bg, tc = CATEGORY_STYLES.get(cat,  ("#F1EFE8", "#444441"))
        dark_bg,  dtc = DARK_CATEGORY_STYLES.get(cat, ("#444441", "#D3D1C7"))

        cards.append(f"""
    <a href="{link['url']}" class="card" target="_blank" rel="noopener noreferrer">
      <div class="card-meta">
        <span class="tag"
          style="--tag-bg:{light_bg};--tag-tc:{tc};--tag-dbg:{dark_bg};--tag-dtc:{dtc}"
        >{cat}</span>
        <span class="source">{link.get('source','')}</span>
      </div>
      <h2>{link['title']}</h2>
      <p>{link.get('description','')}</p>
    </a>""")

    cards_html = "\n".join(cards)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Daily Reads</title>
<style>
  :root {{
    --bg:      #faf9f7;
    --surface: #ffffff;
    --text:    #1a1a18;
    --muted:   #6b6b67;
    --border:  rgba(0,0,0,0.08);
    --hover:   rgba(0,0,0,0.14);
    --radius:  12px;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg:      #111113;
      --surface: #1c1c1e;
      --text:    #e4e2da;
      --muted:   #8c8a82;
      --border:  rgba(255,255,255,0.08);
      --hover:   rgba(255,255,255,0.15);
    }}
  }}
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
  }}
  header {{
    max-width: 720px;
    margin: 0 auto;
    padding: 52px 24px 28px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 24px;
    flex-wrap: wrap;
  }}
  header h1 {{
    font-size: 20px;
    font-weight: 500;
    letter-spacing: -0.3px;
  }}
  header .meta {{
    font-size: 12px;
    color: var(--muted);
    white-space: nowrap;
  }}
  main {{
    max-width: 720px;
    margin: 0 auto;
    padding: 20px 24px 48px;
    display: grid;
    gap: 10px;
  }}
  .card {{
    display: block;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px 22px 20px;
    text-decoration: none;
    color: inherit;
    transition: border-color 0.12s;
  }}
  .card:hover {{ border-color: var(--hover); }}
  .card-meta {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 9px;
  }}
  .tag {{
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.2px;
    padding: 3px 8px;
    border-radius: 4px;
    background: var(--tag-bg);
    color: var(--tag-tc);
  }}
  @media (prefers-color-scheme: dark) {{
    .tag {{
      background: var(--tag-dbg);
      color: var(--tag-dtc);
    }}
  }}
  .source {{
    font-size: 12px;
    color: var(--muted);
  }}
  h2 {{
    font-size: 15px;
    font-weight: 500;
    line-height: 1.45;
    margin-bottom: 6px;
  }}
  p {{
    font-size: 13px;
    color: var(--muted);
    line-height: 1.65;
  }}
  footer {{
    max-width: 720px;
    margin: 0 auto;
    padding: 0 24px 52px;
    font-size: 12px;
    color: var(--muted);
  }}
</style>
</head>
<body>
<header>
  <h1>Daily Reads</h1>
  <span class="meta">Updated {timestamp} · Curated by Claude</span>
</header>
<main>
{cards_html}
</main>
<footer>Refreshed twice daily. Links open in a new tab.</footer>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Fetching curated links…")
    links = fetch_links()
    print(f"  Got {len(links)} links.")

    html = render_html(links)
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"  Wrote → {OUTPUT_FILE}")
