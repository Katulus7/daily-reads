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
This is a DOWNTIME read — tone should be like TechMeme: bite-sized, sharp, substantive
but never dry or academic. Think "smart friend texting you something interesting" not
"research digest." Each pick should feel like a small reward to click on.

CATEGORY GUIDELINES:

1. Movies & Shows
   Find new releases (last 2-3 weeks) that are BOTH critically acclaimed AND
   audience-approved. Must have strong scores on both ends — Rotten Tomatoes critic
   score AND audience score above 80%, or equivalent Letterboxd/IMDb consensus.
   If critics love it but audiences are cold, skip it. If audiences love it but
   critics pan it, skip it. Both must agree it's excellent.
   Include theatrical films and streaming shows (Netflix, HBO, Apple TV+, etc.).
   Hard avoids: rom-coms, reality TV, anything described as a "feel-good romp."

2. Games
   70% new releases (last 4-6 weeks, highly reviewed), 30% hidden gems from
   the last 12 months worth revisiting.
   The reader's taste: games with deep systems AND strong narrative or world-building.
   Reference points: Elden Ring (challenging, rewarding exploration), Slay the Spire
   (roguelike depth, replayability), Disco Elysium (writing-first RPG, meaningful choices),
   Baldur's Gate 3 (rich RPG systems), Outer Wilds / Blue Prince (genuine mystery and
   discovery), Cyberpunk 2077 (immersive open world), Last of Us (narrative craft),
   XCOM (turn-based tactics, strategic depth).
   Look for: deep RPGs, roguelikes, deckbuilders, tactics games, narrative adventures,
   exploration-driven games, puzzle games with real substance.
   Skip: twitch shooters, sports games, battle royale, mobile casual, live-service
   games with no real ending, anything described as "cozy."

3. Books
   70% new releases (last 4-6 weeks), 30% hidden gems from the last 12 months.
   The reader's taste: literary sci-fi (Station Eleven, Never Let Me Go, Hyperion tier),
   narrative nonfiction with novelistic quality (Bad Blood, The Wager tier),
   literary fiction with structural ambition (Trust, Cloud Cuckoo Land, Goon Squad tier),
   richly researched historical fiction (Shogun tier), grounded original fantasy
   (Piranesi, Circe tier). NOT: epic quest fantasy, cozy mysteries, domestic realism,
   beach reads, self-help.

4. Economics
   Big-picture ideas about how the world works — NOT market news or Fed rate updates.
   Think: Freakonomics-style insights, long-run trends, counterintuitive findings,
   "why does this work this way?" essays. Marginal Revolution / Works in Progress /
   Asterisk Magazine quality. Must be accessible and genuinely interesting, not
   academic for its own sake.

5. Visuals
   Something genuinely stunning to look at. The reader loves: space photography
   (Hubble, JWST, astrophotography), nature and wildlife photography, travel and
   landscape photography, photojournalism. Look for: a newly released NASA/ESA image,
   a photo series that's getting attention, a breathtaking travel shot, a nature
   documentary still or clip, a geographic or aerial image. Quality bar is high —
   should feel like a genuine "wow." Not AI-generated art, not graphic design,
   not illustrations. Real photography of real things.

6. Trends & Ideas
   Things catching the zeitgeist RIGHT NOW with real substance behind them — not dumb
   viral moments. Think: ai-2027.com (a serious speculative piece that blew up), a new
   framework for thinking about something, an essay or project that's suddenly everywhere
   in smart circles, a genuinely interesting new podcast worth subscribing to, a cultural
   shift that's just becoming visible. The bar: "smart people are talking about this for
   good reason." Not: "this got a million views." Avoid pure political takes, outrage
   bait, and anything that will feel irrelevant in two weeks.

OVERALL TONE: Assume the reader is smart and busy. Every pick should clear the bar of
"I'm genuinely glad I clicked this." No padding, no filler. One excellent pick per
category beats five mediocre ones.

Hard avoids across all categories: celebrity gossip, sports scores, crypto speculation,
political hot takes, SEO listicles, press-release rewrites, anything that exists purely
to generate clicks.

NEVER link to these domains — they are known for interstitial ads, auto-playing video,
aggressive paywalls, or just low quality:
  forbes.com, businessinsider.com, insider.com, cnet.com, screenrant.com, cbr.com,
  mashable.com, buzzfeed.com, buzzfeednews.com, theclicker.com, gamerant.com,
  fandom.com, wikia.com, complex.com, ranker.com, menshealth.com, popsugar.com,
  thedailybeast.com, salon.com, huffpost.com, nypost.com, dailymail.co.uk,
  mirror.co.uk, the-sun.com, tmz.com, people.com, eonline.com, tvline.com,
  comingsoon.net, movieweb.com, collider.com (acceptable for some articles but
  often has autoplaying video — skip if alternatives exist).

PREFER these source types — known for clean reading experiences:
  Substack newsletters, The Atlantic, Ars Technica, Kottke.org, Daring Fireball,
  The Verge (features only), Polygon (features only), Eurogamer, Rock Paper Shotgun,
  publisher/studio official sites, YouTube (for visual content), Vimeo, NASA.gov,
  ESA.int, NationalGeographic.com, NPR, BBC (features), LitHub, The Guardian (features),
  academic or institutional sites, personal blogs with strong reputations.
"""

CATEGORIES = [
    "Movies & Shows",
    "Games",
    "Books",
    "Economics",
    "Visuals",
    "Trends & Ideas",
]

NUM_LINKS  = 12
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
    "Movies & Shows":  ("#EEEDFE", "#3C3489"),
    "Games":           ("#FAECE7", "#993C1D"),
    "Books":           ("#E1F5EE", "#085041"),
    "Economics":       ("#FAEEDA", "#633806"),
    "Visuals":         ("#E6F1FB", "#0C447C"),
    "Trends & Ideas":  ("#FBEAF0", "#72243E"),
}

DARK_CATEGORY_STYLES: dict[str, tuple[str, str]] = {
    "Movies & Shows":  ("#3C3489", "#CECBF6"),
    "Games":           ("#712B13", "#F5C4B3"),
    "Books":           ("#085041", "#9FE1CB"),
    "Economics":       ("#633806", "#FAC775"),
    "Visuals":         ("#0C447C", "#B5D4F4"),
    "Trends & Ideas":  ("#72243E", "#F4C0D1"),
}


def render_html(links: list[dict]) -> str:
    now       = datetime.now(timezone.utc)
    timestamp = now.strftime("%B %d, %Y at %H:%M UTC")

    cards = []
    for link in links:
        cat          = link.get("category", "Tools & Dev")
        light_bg, tc = CATEGORY_STYLES.get(cat,  ("#F1EFE8", "#444441"))
        dark_bg,  dtc = DARK_CATEGORY_STYLES.get(cat, ("#444441", "#D3D1C7"))

        import urllib.parse
        title = link['title']
        url   = link['url']
        desc  = link.get('description', '')
        subject = urllib.parse.quote(f"Read later: {title}")
        body    = urllib.parse.quote(f"{title}\n{url}\n\n{desc}")
        mailto  = f"mailto:karim.oussayef@gmail.com?subject={subject}&body={body}"

        cards.append(f"""
    <div class="card">
      <div class="card-meta">
        <span class="tag"
          style="--tag-bg:{light_bg};--tag-tc:{tc};--tag-dbg:{dark_bg};--tag-dtc:{dtc}"
        >{cat}</span>
        <span class="source">{link.get('source','')}</span>
      </div>
      <div style="display:flex;align-items:baseline;justify-content:space-between;gap:12px">
        <h2 style="flex:1"><a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a></h2>
        <a href="{mailto}" title="Email to myself" style="flex-shrink:0;font-size:13px;color:var(--muted);text-decoration:none;border:1px solid var(--border);border-radius:6px;padding:3px 9px;white-space:nowrap;transition:border-color 0.12s" onmouseover="this.style.borderColor='var(--hover)'" onmouseout="this.style.borderColor='var(--border)'">✉ Send</a>
      </div>
      <p>{desc}</p>
    </div>""")

    cards_html = "\n".join(cards)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Karim's Daily Reads</title>
<style>
  :root {{
    --bg:      #faf9f7;
    --surface: #ffffff;
    --text:    #1a1a18;
    --muted:   #9a9994;
    --border:  rgba(0,0,0,0.08);
    --hover:   rgba(0,0,0,0.14);
    --radius:  12px;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg:      #111113;
      --surface: #1c1c1e;
      --text:    #e4e2da;
      --muted:   #6e6c66;
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
  }}
  h2 a {{
    color: var(--text);
    text-decoration: none;
    border-bottom: 1px solid var(--border);
    transition: border-color 0.12s;
  }}
  h2 a:hover {{
    border-bottom-color: var(--text);
  }}
  .card-meta {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 9px;
  }}
  .tag {{
    font-size: 12px;
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
    font-size: 14px;
    color: var(--muted);
  }}
  h2 {{
    font-size: 17px;
    font-weight: 500;
    line-height: 1.45;
    margin-bottom: 6px;
  }}
  p {{
    font-size: 15px;
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
  <h1>Karim's Daily Reads</h1>
  <div style="display:flex;align-items:center;gap:16px">
    <div style="display:flex;align-items:center;gap:4px">
      <button onclick="adjustFont(-1)" style="background:none;border:1px solid var(--border);border-radius:6px;color:var(--muted);cursor:pointer;font-size:13px;padding:3px 9px;line-height:1">A−</button>
      <button onclick="adjustFont(1)"  style="background:none;border:1px solid var(--border);border-radius:6px;color:var(--muted);cursor:pointer;font-size:15px;padding:3px 9px;line-height:1">A+</button>
    </div>
    <span class="meta">Updated {timestamp} · Curated by Claude</span>
  </div>
</header>
<main>
{cards_html}
</main>
<footer>Refreshed twice daily. Links open in a new tab.</footer>
<script>
  const SIZES = [14, 16, 18, 20, 22];
  let idx = parseInt(localStorage.getItem('font-idx') ?? '1');
  function applySize() {{
    document.documentElement.style.setProperty('--base', SIZES[idx] + 'px');
    document.querySelectorAll('h2').forEach(el => el.style.fontSize = (SIZES[idx] + 2) + 'px');
    document.querySelectorAll('p').forEach(el => el.style.fontSize = SIZES[idx] + 'px');
    document.querySelectorAll('.source').forEach(el => el.style.fontSize = (SIZES[idx] - 2) + 'px');
  }}
  function adjustFont(dir) {{
    idx = Math.max(0, Math.min(SIZES.length - 1, idx + dir));
    localStorage.setItem('font-idx', idx);
    applySize();
  }}
  applySize();
</script>
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
